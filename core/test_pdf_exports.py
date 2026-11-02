from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError
from packages.pdf_exports import document, response


class PDFExportTests(SimpleTestCase):
    def test_pdf_is_paginated_and_response_is_private(self):
        content = document(
            'Résultats - Québec',
            ['Nom', 'Présences', 'Montant CAD'],
            [[f'Conseiller {i}', i, '125.00'] for i in range(70)],
            'Période du 1 au 30 novembre 2026. Heure du Québec.',
        )
        self.assertTrue(content.startswith(b'%PDF-'))
        self.assertIn(b'%%EOF', content[-30:])
        self.assertGreater(content.count(b'/Type /Page'), 2)
        result = response('Résultats', ['Nom'], [['Émery']], 'resultats')
        self.assertEqual(result['Content-Type'], 'application/pdf')
        self.assertEqual(result['Cache-Control'], 'no-store')
        self.assertIn('resultats.pdf', result['Content-Disposition'])

    def test_wide_records_and_escape_source_markup(self):
        content = document(
            'Dossiers', [f'Champ {i}' for i in range(10)], [['<b>Texte fourni</b>'] * 10]
        )
        self.assertTrue(content.startswith(b'%PDF-'))
        for headers, rows in [(['Nom'], [['x']] * 501), (['Note'], [['x' * 801]])]:
            with self.assertRaises(ValidationError):
                document('Trop grand', headers, rows)
