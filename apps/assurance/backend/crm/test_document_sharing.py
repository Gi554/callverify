from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch
from uuid import uuid4
from django.test import TestCase, TransactionTestCase, override_settings
from django.db import connection, close_old_connections
from rest_framework.test import APIClient
from packages.access.tickets import issue
from .models import Contact, ContactDocument, BusinessAudit


def fixture():
    contact = Contact.objects.create(
        name='Contact', phone='raw', created_by_id=21, assigned_advisor_id=31
    )
    document = ContactDocument.objects.create(
        contact=contact,
        request_id=uuid4(),
        author_id=21,
        channel='internal',
        filename='SECRET-SETTER.pdf',
        content_type='application/pdf',
        size=8,
        sha256='secret-hash',
        content=b'%PDF-test',
    )
    return contact, document


@override_settings(DEBUG=True)
class DocumentSharingTests(TestCase):
    def setUp(self):
        self.contact, self.document = fixture()
        self.client = APIClient()
        self.auth(99, 'administrator')
        self.base = f'/api/assurance/contacts/{self.contact.pk}/'
        self.url = self.base + f'documents/{self.document.pk}/sharing/'
        self.download = self.base + f'documents/{self.document.pk}/download/'

    def auth(self, pk, role, workspace='assurance'):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(pk, workspace, role))

    def payload(self, **changes):
        return {
            'revision': 0,
            'enabled': True,
            'filename': 'Dossier.pdf',
            'reviewed': True,
            'reason': 'Version vérifiée pour le conseiller',
            **changes,
        }

    def share(self, **changes):
        return self.client.post(self.url, self.payload(**changes), format='json')

    def test_default_private_then_public_name_across_list_download_and_chronology(self):
        self.auth(31, 'advisor')
        self.assertEqual(self.client.get(self.base + 'documents/').data['count'], 0)
        self.assertEqual(self.client.get(self.download).status_code, 404)
        self.auth(99, 'administrator')
        self.assertEqual(self.share().status_code, 200)
        self.auth(31, 'advisor')
        rows = self.client.get(self.base + 'documents/')
        self.assertEqual(rows.data['count'], 1)
        row = rows.data['results'][0]
        self.assertEqual(row['filename'], 'Dossier.pdf')
        self.assertEqual(row['channel'], 'shared')
        timeline = self.client.get(self.base + 'interactions/').data
        self.assertEqual(timeline['results'][0]['detail'], 'Dossier.pdf')
        for value in (
            'SECRET-SETTER',
            'secret-hash',
            'author_id',
            'sharing_revision',
            'advisor_filename',
        ):
            self.assertNotIn(value, str(rows.data) + str(timeline))
        response = self.client.get(self.download)
        self.assertEqual(response.content, b'%PDF-test')
        self.assertIn('Dossier.pdf', response['Content-Disposition'])
        self.assertNotIn('SECRET', response['Content-Disposition'])
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_revoke_removes_all_advisor_reads_without_deleting_internal_file(self):
        self.share()
        self.assertEqual(self.share(revision=1, enabled=False, reviewed=False).status_code, 200)
        self.auth(31, 'advisor')
        self.assertEqual(self.client.get(self.download).status_code, 404)
        self.assertEqual(self.client.get(self.base + 'documents/').data['count'], 0)
        self.assertEqual(self.client.get(self.base + 'interactions/').data['count'], 0)
        self.document.refresh_from_db()
        self.assertEqual(bytes(self.document.content), b'%PDF-test')
        self.assertEqual(self.document.filename, 'SECRET-SETTER.pdf')
        self.assertEqual(self.document.advisor_filename, '')
        self.auth(21, 'setter')
        self.assertEqual(self.client.get(self.download).status_code, 200)

    def test_only_admin_publishes_and_advisor_remains_contact_scoped(self):
        for pk, role in ((21, 'setter'), (31, 'advisor')):
            self.auth(pk, role)
            self.assertEqual(self.share().status_code, 403)
        self.auth(99, 'administrator')
        self.share()
        self.auth(32, 'advisor')
        self.assertEqual(self.client.get(self.download).status_code, 404)
        self.assertEqual(self.client.get(self.base + 'documents/').status_code, 404)
        self.auth(31, 'advisor', 'isolation')
        self.assertEqual(self.client.get(self.download).status_code, 401)
        self.auth(31, 'advisor')
        Contact.objects.filter(pk=self.contact.pk).update(assigned_advisor_id=None)
        self.assertEqual(self.client.get(self.download).status_code, 404)

    def test_personal_advisor_file_and_foreign_contact_cannot_be_published(self):
        ContactDocument.objects.filter(pk=self.document.pk).update(channel='advisor', author_id=31)
        self.assertEqual(self.share().status_code, 404)
        ContactDocument.objects.filter(pk=self.document.pk).update(channel='internal')
        other = Contact.objects.create(name='Other', phone='other', created_by_id=99)
        self.assertEqual(
            self.client.post(
                f'/api/assurance/contacts/{other.pk}/documents/{self.document.pk}/sharing/',
                self.payload(),
                format='json',
            ).status_code,
            404,
        )

    def test_review_reason_public_name_extension_and_strict_fields_required(self):
        for changes in (
            {'reviewed': False},
            {'reason': ' '},
            {'filename': ' '},
            {'filename': '../file.pdf'},
            {'filename': 'folder/file.pdf'},
            {'filename': 'file.exe'},
            {'filename': 'file\\name.pdf'},
            {'filename': 'bad\nname.pdf'},
            {'author_id': 31},
        ):
            self.assertEqual(self.share(**changes).status_code, 400, changes)
        self.document.refresh_from_db()
        self.assertFalse(self.document.advisor_visible)

    def test_expected_revision_and_audit_before_after(self):
        self.assertEqual(self.share(revision=99).status_code, 409)
        self.assertEqual(self.share().status_code, 200)
        self.assertEqual(self.share().status_code, 409)
        audit = BusinessAudit.objects.get(action='contact.document_sharing_changed')
        self.assertFalse(audit.metadata['before']['enabled'])
        self.assertTrue(audit.metadata['after']['enabled'])
        self.assertTrue(audit.metadata['reviewed'])
        self.assertEqual(audit.metadata['after']['revision'], 1)

    def test_audit_failure_rolls_back_publication(self):
        with patch(
            'apps.assurance.backend.crm.documents.BusinessAudit.objects.create',
            side_effect=RuntimeError('audit'),
        ):
            with self.assertRaises(RuntimeError):
                self.share()
        self.document.refresh_from_db()
        self.assertFalse(self.document.advisor_visible)
        self.assertEqual(self.document.sharing_revision, 0)

    def test_download_audit_and_shared_metadata_do_not_change_upload_ownership(self):
        self.share()
        self.auth(31, 'advisor')
        self.client.get(self.download)
        self.document.refresh_from_db()
        self.assertEqual(self.document.author_id, 21)
        self.assertEqual(self.document.channel, 'internal')
        self.assertEqual(
            BusinessAudit.objects.filter(action='contact.document_downloaded').count(), 1
        )


@skipUnless(connection.vendor == 'postgresql', 'Sharing concurrency requires PostgreSQL')
@override_settings(DEBUG=True)
class ConcurrentDocumentSharingTests(TransactionTestCase):
    def test_two_publications_of_same_revision_only_one_succeeds(self):
        contact, document = fixture()
        barrier = Barrier(2)

        def worker(name):
            close_old_connections()
            try:
                client = APIClient()
                client.credentials(
                    HTTP_AUTHORIZATION='Bearer ' + issue(99, 'assurance', 'administrator')
                )
                barrier.wait(timeout=10)
                return client.post(
                    f'/api/assurance/contacts/{contact.pk}/documents/{document.pk}/sharing/',
                    {
                        'revision': 0,
                        'enabled': True,
                        'filename': name + '.pdf',
                        'reviewed': True,
                        'reason': 'Version contrôlée',
                    },
                    format='json',
                ).status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(worker, ['One', 'Two']))
        self.assertEqual(sorted(results), [200, 409])
        self.assertEqual(
            BusinessAudit.objects.filter(action='contact.document_sharing_changed').count(), 1
        )
