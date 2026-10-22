from uuid import uuid4
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from packages.access.tickets import issue
from .models import Contact, ContactDocument, BusinessAudit


@override_settings(DEBUG=True)
class DocumentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.contact = Contact.objects.create(
            name='Prospect', phone='brut', created_by_id=19, assigned_advisor_id=7
        )
        self.base = f'/api/assurance/contacts/{self.contact.pk}/'
        self.auth(19, 'setter')
        self.token = self.client.post(self.base + 'lease/', {}, format='json').data['token']

    def auth(self, pk, role):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(pk, 'assurance', role))

    def upload(self, request_id=None, content=b'%PDF-1.4\n%%EOF', name='preuve.pdf', **extra):
        return self.client.post(
            self.base + 'documents/',
            {
                'request_id': str(request_id or uuid4()),
                'file': SimpleUploadedFile(name, content),
                'token': self.token,
                **extra,
            },
            format='multipart',
        )

    def test_internal_upload_download_and_replay(self):
        request_id = uuid4()
        first = self.upload(request_id)
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(self.upload(request_id).status_code, 200)
        self.assertEqual(ContactDocument.objects.count(), 1)
        self.assertEqual(self.upload(request_id, content=b'%PDF-different').status_code, 409)
        response = self.client.get(self.base + f'documents/{first.data["id"]}/download/')
        self.assertEqual(response.content, b'%PDF-1.4\n%%EOF')
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        rows = self.client.get(self.base + 'documents/').data['results']
        self.assertNotIn('content', rows[0])
        self.assertNotIn('author_id', rows[0])
        self.assertTrue(BusinessAudit.objects.filter(action='contact.document_downloaded').exists())

    def test_channel_permissions_and_contact_scope(self):
        internal = self.upload().data['id']
        self.auth(7, 'advisor')
        self.assertEqual(self.client.get(self.base + 'documents/').data['count'], 0)
        self.assertEqual(
            self.client.get(self.base + f'documents/{internal}/download/').status_code, 404
        )
        own = self.upload(name='conseiller.pdf').data['id']
        self.assertEqual(self.client.get(self.base + 'documents/').data['count'], 1)
        self.auth(8, 'advisor')
        self.assertEqual(self.client.get(self.base + 'documents/').status_code, 404)
        self.contact.assigned_advisor_id = 8
        self.contact.save()
        self.assertEqual(self.client.get(self.base + 'documents/').data['count'], 0)
        self.assertEqual(self.client.get(self.base + f'documents/{own}/download/').status_code, 404)
        self.auth(19, 'setter')
        self.assertEqual(self.client.get(self.base + 'documents/').data['count'], 1)
        self.assertEqual(self.client.get(self.base + f'documents/{own}/download/').status_code, 404)
        self.auth(1, 'administrator')
        self.assertEqual(self.client.get(self.base + 'documents/').data['count'], 2)
        self.assertEqual(self.client.get(self.base + f'documents/{own}/download/').status_code, 200)

    def test_invalid_file_and_missing_lock(self):
        for content, name in [
            (b'HTML', 'preuve.pdf'),
            (b'%PDF-x', 'script.html'),
            (b'', 'vide.pdf'),
            (b'%PDF-' + b'x' * (5 * 1024 * 1024), 'grand.pdf'),
        ]:
            self.assertEqual(self.upload(content=content, name=name).status_code, 400)
        self.assertEqual(self.upload(token='').status_code, 409)
        self.auth(20, 'setter')
        self.assertEqual(self.upload().status_code, 409)
        self.assertEqual(ContactDocument.objects.count(), 0)

    def test_audit_failure_rolls_back_bytes(self):
        self.client.raise_request_exception = False
        with patch(
            'apps.assurance.backend.crm.documents.BusinessAudit.objects.create',
            side_effect=RuntimeError('audit unavailable'),
        ):
            self.assertEqual(self.upload().status_code, 500)
        self.assertEqual(ContactDocument.objects.count(), 0)

    def test_anonymous_and_no_mutation_routes(self):
        row = self.upload().data['id']
        self.assertEqual(
            self.client.delete(self.base + f'documents/{row}/download/').status_code, 405
        )
        self.client.credentials()
        self.assertEqual(self.client.get(self.base + 'documents/').status_code, 401)
