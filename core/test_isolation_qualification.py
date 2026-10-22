from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from packages.access.tickets import issue
from .models import AdminUser, Campaign, PhoneNumber, Prospect


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class IsolationQualificationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.credentials(
            HTTP_AUTHORIZATION='Bearer ' + issue(41, 'isolation', 'administrator')
        )

    def test_administrator_creates_a_centrally_scoped_campaign(self):
        response = self.client.post(
            '/api/qualification/',
            {
                'name': 'Qualification Isolation',
                'source': 'Recette',
                'budget': '3.0000',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        campaign = Campaign.objects.get(pk=response.data['id'])
        self.assertEqual(campaign.portal_workspace, 'isolation')
        self.assertEqual(campaign.portal_owner_id, 41)
        self.assertFalse(campaign.owner.is_active)
        self.assertTrue(campaign.owner.password.startswith('!'))

    def test_setter_cannot_operate_the_qualification_process(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(42, 'isolation', 'setter'))
        self.assertEqual(self.client.get('/api/qualification/').status_code, 403)

    def test_entire_qualification_process_requires_an_isolation_administrator_ticket(self):
        endpoints = [
            ('get', '/api/qualification/'),
            ('post', '/api/qualification/'),
            ('post', '/api/qualification/1/lookup/'),
            ('get', '/api/qualification/imports/'),
            ('post', '/api/qualification/imports/'),
            ('post', '/api/qualification/imports/1/preview/'),
            ('post', '/api/qualification/imports/1/confirm/'),
            ('get', '/api/qualification/results/'),
            ('get', '/api/qualification/exports/'),
            ('post', '/api/qualification/exports/'),
            ('get', '/api/qualification/exports/1/download/'),
        ]
        for workspace, role in [
            ('isolation', 'setter'),
            ('isolation', 'client'),
            ('isolation', 'closer'),
            ('assurance', 'administrator'),
            ('assurance', 'setter'),
            ('assurance', 'advisor'),
        ]:
            self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(42, workspace, role))
            for method, url in endpoints:
                with self.subTest(workspace=workspace, role=role, method=method, url=url):
                    response = getattr(self.client, method)(url, {}, format='json')
                    self.assertIn(response.status_code, (401, 403))
        self.assertFalse(Campaign.objects.exists())

    def test_legacy_staff_session_cannot_enter_the_integrated_process(self):
        legacy = AdminUser.objects.create_user('legacy-session', is_staff=True, is_superuser=True)
        self.client.credentials()
        self.client.force_login(legacy)
        self.assertIn(self.client.get('/api/qualification/').status_code, (401, 403))

    def test_admin_can_load_all_four_integrated_tabs_without_starting_work(self):
        from unittest.mock import patch

        with (
            patch('core.isolation_qualification.enqueue') as enqueue,
            patch('core.isolation_qualification.schedule_lookup') as lookup,
        ):
            for url in (
                '/api/qualification/',
                '/api/qualification/imports/',
                '/api/qualification/results/',
                '/api/qualification/exports/',
            ):
                with self.subTest(url=url):
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, 200, response.data)
                    self.assertEqual(response.data['count'], 0)
            enqueue.assert_not_called()
            lookup.assert_not_called()

    def test_integrated_import_export_and_download_use_the_central_ticket(self):
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from io import BytesIO
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.core.files.base import ContentFile
        from openpyxl import Workbook
        from .models import ExportJob

        with (
            TemporaryDirectory() as media,
            override_settings(MEDIA_ROOT=media),
            patch('core.isolation_qualification.enqueue') as enqueue,
        ):
            campaign = self.client.post(
                '/api/qualification/', {'name': 'Liste intégrée'}, format='json'
            ).data['id']
            uploaded = self.client.post(
                '/api/qualification/imports/',
                {
                    'campaign': campaign,
                    'file': SimpleUploadedFile(
                        'liste.csv', b'name,phone\nDemo,+10000000001\n', content_type='text/csv'
                    ),
                },
                format='multipart',
            )
            self.assertEqual(uploaded.status_code, 201, uploaded.data)
            batch = uploaded.data['id']
            self.assertEqual(self.client.get('/api/qualification/imports/').data['count'], 1)
            confirmed = self.client.post(
                f'/api/qualification/imports/{batch}/confirm/',
                {'mapping': {'phone': 'phone', 'name': 'name'}},
                format='json',
            )
            self.assertEqual(confirmed.status_code, 202, confirmed.data)
            enqueue.assert_called_with('import', batch)
            requested = self.client.post(
                '/api/qualification/exports/',
                {'campaign': campaign, 'format': 'xlsx'},
                format='json',
            )
            self.assertEqual(requested.status_code, 202, requested.data)
            job = ExportJob.objects.get(pk=requested.data['id'])
            enqueue.assert_called_with('export', job.pk)
            self.assertEqual(self.client.get('/api/qualification/exports/').data['count'], 1)
            book = Workbook()
            book.active.append(['Donnée fictive'])
            output = BytesIO()
            book.save(output)
            job.file.save('demo.xlsx', ContentFile(output.getvalue()))
            job.status = 'completed'
            job.save()
            url = f'/api/qualification/exports/{job.pk}/download/'
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b''.join(response.streaming_content), output.getvalue())
            response.close()
            self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(42, 'isolation', 'setter'))
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_results_do_not_expose_legacy_campaigns(self):
        legacy_owner = AdminUser.objects.create_user('legacy-owner', is_staff=True)
        legacy = Campaign.objects.create(owner=legacy_owner, name='Legacy', purpose='', source='')
        isolated = Campaign.objects.create(
            owner=legacy_owner,
            portal_workspace='isolation',
            portal_owner_id=41,
            name='Isolation',
            purpose='',
            source='',
        )
        phone = PhoneNumber.objects.create(e164='+14165550124')
        Prospect.objects.create(campaign=legacy, phone=phone, raw_phone='5145550124')
        Prospect.objects.create(campaign=isolated, phone=phone, raw_phone='5145550124')
        response = self.client.get('/api/qualification/results/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['campaign'], isolated.pk)
