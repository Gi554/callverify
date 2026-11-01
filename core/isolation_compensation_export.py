"""Administrative aggregate exports without prospect identities or free-text notes."""

import csv
import io
from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.styles import Font
from .isolation_statistics_export import safe

COLUMNS = {
    'client_id': 'Client ID',
    'client_name': 'Client',
    'setter_id': 'Setter ID',
    'setter_name': 'Setter',
    'calls': 'Appels Orvia : poste joint',
    'attempts': 'Tentatives Orvia',
    'uncertain': 'Commandes incertaines',
    'programmed': 'Visites programmées',
    'upcoming': 'À venir',
    'attended': 'Occurrences tenues',
    'absent': 'Non tenues déclarées',
    'reprogrammed': 'Nouvelles visites après absence',
    'sales': 'Ventes déclarées',
    'unqualified': 'Fiches non qualifiées enregistrées',
    'cancelled': 'Visites annulées',
    'pending_results': 'Résultats incomplets',
    'sale_unknown': 'Tenues : vente non renseignée',
    'presence_rate': 'Présence / résultats (%)',
    'closing_rate': 'Ventes / tenues (%)',
    'attendance_credits': 'Crédits de présence uniques',
    'sale_credits': 'Primes de vente uniques',
    'attendance_unpriced': 'Présences sans tarif',
    'sale_unpriced': 'Ventes sans tarif',
    'attendance_amount': 'Présences valorisées CAD',
    'sale_amount': 'Primes valorisées CAD',
    'amount_cad': 'Montant connu CAD',
    'complete': 'Tarifs et résultats complets',
}


def export(result, groups, kind):
    headers = [
        'Périmètre',
        *COLUMNS.values(),
        'Du (Québec)',
        'Au inclus (Québec)',
        'Calculé le (UTC)',
        'Appels disponibles',
        'Définition',
    ]

    def values(label, row):
        return [
            label,
            *[
                safe(row.get(key))
                if row.get(key) is not None
                else ('Indisponible' if key in ('calls', 'attempts', 'uncertain') else '')
                for key in COLUMNS
            ],
            str(result['from']),
            str(result['to']),
            result['as_of'].isoformat(),
            result['calls_available'],
            result['definition'],
        ]

    rows = [values('Total', result['totals']), *[values('Setter / client', row) for row in groups]]
    if kind == 'csv':
        output = io.StringIO(newline='')
        output.write('\ufeff')
        writer = csv.writer(output, delimiter=';')
        writer.writerow(headers)
        writer.writerows(rows)
        body = output.getvalue().encode('utf-8')
        content_type = 'text/csv; charset=utf-8'
    else:
        book = Workbook()
        sheet = book.active
        sheet.title = 'Rémunération Isolation'
        sheet.append(headers)
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for row in rows:
            sheet.append(row)
        sheet.freeze_panes = 'E2'
        sheet.auto_filter.ref = sheet.dimensions
        buffer = io.BytesIO()
        book.save(buffer)
        body = buffer.getvalue()
        content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    response = HttpResponse(body, content_type=content_type)
    response['Content-Disposition'] = (
        f'attachment; filename="remuneration-isolation-{result["from"]}-{result["to"]}.{kind}"'
    )
    response['Cache-Control'] = 'no-store'
    return response
