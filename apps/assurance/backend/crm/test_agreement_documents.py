from uuid import uuid4
from unittest.mock import patch
from unittest import skipUnless
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.test import TestCase, TransactionTestCase, override_settings
from django.db import connection, close_old_connections
from rest_framework.test import APIClient
from packages.access.tickets import issue
from .models import Contact, AgreementDocument, ContactDocument, BusinessAudit
from . import test_agreements as agreement_fixtures


@override_settings(DEBUG=True)
class AgreementDocumentTests(TestCase):
    def setUp(self):
        fixture = agreement_fixtures.AgreementTests(
            methodName='test_create_update_archive_history_and_no_side_effects'
        )
        fixture.setUp()
        result = fixture.create()
        self.client = fixture.client
        self.contact = fixture.contact
        self.token = fixture.token
        self.base = fixture.base
        self.agreement_id = result.data['agreement']['id']
        self.url = fixture.url + f'{self.agreement_id}/documents/'
        self.doc = self.document()

    def document(self, **changes):
        return ContactDocument.objects.create(
            contact=self.contact,
            request_id=uuid4(),
            author_id=21,
            channel='internal',
            filename='piece.pdf',
            content_type='application/pdf',
            size=8,
            sha256='test',
            content=b'%PDF-test',
            **changes,
        )

    def body(self, **changes):
        return {
            'token': self.token,
            'contact_revision': 1,
            'revision': 0,
            'document_id': self.doc.pk,
            'enabled': True,
            'reason': 'Pièce du dossier',
            **changes,
        }

    def change(self, **changes):
        return self.client.post(self.url, self.body(**changes), format='json')

    def test_link_list_download_unlink_and_relink_keep_file_and_sharing(self):
        self.assertEqual(self.change().status_code, 200)
        result = self.client.get(self.url)
        self.assertEqual(result.data['count'], 1)
        self.assertEqual(result['Cache-Control'], 'no-store')
        self.assertEqual(result.data['agreement_revision'], 1)
        self.assertNotIn('content', result.data['results'][0])
        self.assertEqual(self.client.get(self.url + '?view=available').data['count'], 0)
        response = self.client.get(self.base + f'documents/{self.doc.pk}/download/')
        self.assertEqual(response.content, b'%PDF-test')
        self.assertEqual(
            self.change(contact_revision=2, revision=1, enabled=False).status_code, 200
        )
        self.assertEqual(self.client.get(self.url).data['count'], 0)
        self.doc.refresh_from_db()
        self.assertFalse(self.doc.advisor_visible)
        self.assertEqual(bytes(self.doc.content), b'%PDF-test')
        self.assertEqual(self.client.get(self.url + '?view=available').data['count'], 1)
        self.assertEqual(self.change(contact_revision=3, revision=2).status_code, 200)
        self.assertEqual(AgreementDocument.objects.count(), 1)
        history = self.client.get(self.base + f'agreements/{self.agreement_id}/history/').data[
            'results'
        ]
        self.assertEqual(history[0]['after']['document_ids'], [self.doc.pk])
        self.assertEqual(history[0]['before']['document_ids'], [])

    def test_other_contact_and_personal_advisor_document_refused(self):
        other = Contact.objects.create(name='Other', phone='raw', created_by_id=99)
        ContactDocument.objects.filter(pk=self.doc.pk).update(contact=other)
        self.assertEqual(self.change().status_code, 404)
        ContactDocument.objects.filter(pk=self.doc.pk).update(
            contact=self.contact, channel='advisor', author_id=31
        )
        self.assertEqual(self.change().status_code, 404)
        self.assertEqual(self.client.get(self.url + '?view=available').data['count'], 0)

    def test_roles_and_workspace_cannot_read_or_modify(self):
        for pk, role in ((21, 'setter'), (31, 'advisor')):
            self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(pk, 'assurance', role))
            self.assertEqual(self.client.get(self.url).status_code, 403)
            self.assertEqual(self.change().status_code, 403)
        self.client.credentials(
            HTTP_AUTHORIZATION='Bearer ' + issue(99, 'isolation', 'administrator')
        )
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_lease_and_both_revisions_and_reason_required(self):
        for changes, expected in (
            ({'token': str(uuid4())}, 409),
            ({'contact_revision': 99}, 409),
            ({'revision': 99}, 409),
            ({'reason': ' '}, 400),
            ({'channel': 'advisor'}, 400),
        ):
            self.assertEqual(self.change(**changes).status_code, expected)
        self.assertFalse(AgreementDocument.objects.exists())

    def test_noop_and_stale_retries_do_not_add_audits(self):
        self.change()
        count = BusinessAudit.objects.count()
        self.assertEqual(self.change().status_code, 409)
        self.assertEqual(self.change(contact_revision=2, revision=1).status_code, 200)
        self.assertEqual(BusinessAudit.objects.count(), count)

    def test_audit_failure_rolls_back_link_contact_and_agreement(self):
        with patch(
            'apps.assurance.backend.crm.agreements.BusinessAudit.objects.create',
            side_effect=RuntimeError('audit'),
        ):
            with self.assertRaises(RuntimeError):
                self.change()
        self.assertFalse(AgreementDocument.objects.exists())
        self.contact.refresh_from_db()
        self.assertEqual(self.contact.revision, 1)
        self.assertEqual(self.client.get(self.url).data['agreement_revision'], 0)

    def test_same_contact_foreign_agreement_url_and_invalid_view(self):
        other = Contact.objects.create(name='Other', phone='raw', created_by_id=99)
        url = f'/api/assurance/contacts/{other.pk}/agreements/{self.agreement_id}/documents/'
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(self.url + '?view=unknown').status_code, 400)

    def test_pagination_and_fifty_active_document_limit(self):
        from .models import Agreement

        agreement = Agreement.objects.get(pk=self.agreement_id)
        docs = [self.document() for _ in range(50)]
        AgreementDocument.objects.bulk_create(
            [AgreementDocument(agreement=agreement, document=doc) for doc in docs]
        )
        result = self.client.get(self.url)
        self.assertEqual(result.data['count'], 50)
        self.assertEqual(len(result.data['results']), 25)
        self.assertEqual(self.change().status_code, 400)
        self.assertEqual(AgreementDocument.objects.filter(active=True).count(), 50)


@skipUnless(connection.vendor == 'postgresql', 'Document link concurrency requires PostgreSQL')
@override_settings(DEBUG=True)
class AgreementDocumentConcurrencyTests(TransactionTestCase):
    def test_two_links_with_same_versions_only_one_commits(self):
        fixture = AgreementDocumentTests(
            methodName='test_link_list_download_unlink_and_relink_keep_file_and_sharing'
        )
        fixture.setUp()
        second = fixture.document()
        barrier = Barrier(2)

        def worker(pk):
            close_old_connections()
            try:
                client = APIClient()
                client.credentials(
                    HTTP_AUTHORIZATION='Bearer ' + issue(99, 'assurance', 'administrator')
                )
                barrier.wait(timeout=10)
                return client.post(
                    fixture.url, fixture.body(document_id=pk), format='json'
                ).status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(worker, [fixture.doc.pk, second.pk]))
        self.assertEqual(sorted(results), [200, 409])
        self.assertEqual(AgreementDocument.objects.count(), 1)
