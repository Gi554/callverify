from unittest.mock import patch
from django.test import TestCase, override_settings
from packages.newt import cdr
from packages.newt.directory import DirectoryUnavailable
from . import test_phone_cdr as fixtures
from . import test_phone_status as status_fixtures

HEADER = b'"From","To","Description","DNID","Date","Time","Duration","Amount"\n'


class ConfirmedCdrParserTests(TestCase):
    def test_confirmed_columns_parse_quoted_french_description_and_raw_duration(self):
        raw = HEADER + '501,5145550100,"Montréal, Québec",,2026-10-15,09:40:25,8,0\n'.encode()
        records = cdr.parse_records(raw)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['occurred_at'], '2026-10-15T13:40:25+00:00')
        self.assertEqual(records[0]['description'], 'Montréal, Québec')
        self.assertEqual(records[0]['duration_raw'], '8')
        self.assertNotIn('answered', records[0])
        self.assertNotIn('duration_seconds', records[0])

    def test_montreal_uses_seasonal_offset_not_permanent_utc_minus_four(self):
        self.assertEqual(cdr.local_instant('2026-12-15', '09:40:25'), '2026-12-15T14:40:25+00:00')
        self.assertEqual(cdr.local_instant('2026-10-15', '09:40:25'), '2026-10-15T13:40:25+00:00')
        self.assertIsNone(cdr.local_instant('2026-11-01', '01:30:00'))
        self.assertIsNone(cdr.local_instant('2027-03-14', '02:30:00'))
        self.assertIsNone(cdr.local_instant('2026-02-30', '09:00:00'))

    def test_schema_drift_malformed_and_oversized_reports_are_refused(self):
        for raw in (
            b'Extension,Destination\n501,5145550100',
            HEADER + b'501,5145550100',
            b'\xff',
            HEADER + b'"unterminated',
        ):
            with self.assertRaises(DirectoryUnavailable):
                cdr.parse_records(raw)
        with self.assertRaises(DirectoryUnavailable):
            cdr.parse_records(b'x' * (cdr.MAX_BYTES + 1))
        self.assertEqual(cdr.parse_records(HEADER), [])


class ConfirmedSchemaTests(TestCase):
    setUp = fixtures.CdrTests.setUp

    @override_settings(
        DEBUG=True,
        NEWT_CDR_SCHEMA_ENABLED=True,
        NEWT_USERNAME='test-user',
        NEWT_PASSWORD='test-secret',
    )
    def test_provider_confirmed_header_is_recognized_without_leaking_records(self):
        with patch(
            'portal.backend.identity.phone_cdr.fetch_schema',
            return_value={
                'columns': cdr.CONFIRMED_COLUMNS,
                'row_count': 3,
                'schema_fingerprint': 'a' * 64,
            },
        ):
            response = self.client.post(self.url, self.body, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data['mapping_confirmed'])
        self.assertEqual(response.data['timezone'], 'America/Toronto')
        self.assertFalse(response.data['duration_unit_confirmed'])
        self.assertNotIn('records', response.data)


class ConfirmedPostStateTests(TestCase):
    setUp = status_fixtures.StatusTests.setUp

    @override_settings(
        DEBUG=True, NEWT_STATUS_ENABLED=True, NEWT_USERNAME='test-user', NEWT_PASSWORD='test-secret'
    )
    def test_post_states_are_labeled_without_claiming_recipient_answer(self):
        with patch(
            'portal.backend.identity.phone_status.fetch_status',
            return_value={
                'codes': ['C', 'H', 'R'],
                'observations': 3,
                'conclusion': 'indeterminate',
            },
        ):
            response = self.client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            [row['label'] for row in response.data['states']],
            ['En communication', 'En attente', 'Sonnerie du poste'],
        )
        self.assertEqual(response.data['conclusion'], 'indeterminate')
        self.assertIn('ne prouvent', response.data['definition'])
