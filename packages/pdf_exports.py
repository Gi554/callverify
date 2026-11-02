"""Readable paginated PDF exports, with bounded rows and embedded Latin fonts."""

from io import BytesIO
from datetime import datetime
from packages.quebec_period import ZONE
from pathlib import Path
from xml.sax.saxutils import escape
import reportlab
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from django.http import HttpResponse
from rest_framework.exceptions import ValidationError

MAX_RECORDS = 500


def document(title, headers, rows, description=''):
    if not 1 <= len(headers) <= 100:
        raise ValidationError('PDF : entre 1 et 100 colonnes requises.')
    if len(rows) > MAX_RECORDS:
        raise ValidationError(
            'PDF limité à 500 lignes. Précisez les filtres ou choisissez Excel/CSV.'
        )
    fonts = Path(reportlab.__file__).parent / 'fonts'
    for name, file in [('Orvia', 'Vera.ttf'), ('OrviaBold', 'VeraBd.ttf')]:
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(fonts / file)))
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name='OrviaBody',
            fontName='Orvia',
            fontSize=8.5,
            leading=12,
            spaceAfter=4,
            alignment=TA_LEFT,
            splitLongWords=True,
        )
    )
    styles.add(
        ParagraphStyle(
            name='OrviaTitle',
            fontName='OrviaBold',
            fontSize=21,
            leading=27,
            textColor=colors.HexColor('#18364f'),
            spaceAfter=15,
        )
    )
    styles.add(
        ParagraphStyle(
            name='OrviaSection',
            fontName='OrviaBold',
            fontSize=11,
            leading=15,
            textColor=colors.HexColor('#604bd4'),
            spaceBefore=13,
            spaceAfter=8,
        )
    )

    def para(value, style='OrviaBody'):
        if isinstance(value, datetime) and value.tzinfo:
            value = value.astimezone(ZONE).strftime('%Y-%m-%d %H:%M') + ' (Québec)'
        text = '-' if value is None else str(value)
        text = text.replace('—', '-').replace('–', '-').replace('‑', '-')
        return Paragraph(escape(text).replace('\n', '<br/>'), styles[style])

    limit = 800 if len(headers) <= 5 else 2000
    if any(len(str(value or '')) > limit for row in rows for value in row):
        raise ValidationError(
            'Une cellule dépasse la taille lisible en PDF. Choisissez Excel ou CSV.'
        )
    stream = BytesIO()
    doc = SimpleDocTemplate(
        stream,
        pagesize=A4,
        leftMargin=38,
        rightMargin=38,
        topMargin=47,
        bottomMargin=42,
        title=title,
        author='Orvia CRM',
    )
    story = [para('ORVIA CRM', 'OrviaSection'), para(title, 'OrviaTitle')]
    if description:
        story.extend([para(description), Spacer(1, 12)])
    if len(headers) <= 5:
        table = Table(
            [[para(h) for h in headers]] + [[para(v) for v in row] for row in rows],
            colWidths=[doc.width / len(headers)] * len(headers),
            repeatRows=1,
            hAlign='LEFT',
        )
        table.setStyle(
            TableStyle(
                [
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e9e5fb')),
                    (
                        'ROWBACKGROUNDS',
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor('#f5f7fc')],
                    ),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 9),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 9),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(table)
    else:
        # Wide exports become one labelled record at a time; no unreadable tiny columns.
        for index, row in enumerate(rows, 1):
            title_text = f'Enregistrement {index}'
            table = Table(
                [[para(h), para(v)] for h, v in zip(headers, row)],
                colWidths=[doc.width * 0.43, doc.width * 0.57],
                hAlign='LEFT',
            )
            table.setStyle(
                TableStyle(
                    [
                        (
                            'ROWBACKGROUNDS',
                            (0, 0),
                            (-1, -1),
                            [colors.white, colors.HexColor('#f5f7fc')],
                        ),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('LEFTPADDING', (0, 0), (-1, -1), 8),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                        ('TOPPADDING', (0, 0), (-1, -1), 5),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                    ]
                )
            )
            story.extend([para(title_text, 'OrviaSection'), table, Spacer(1, 12)])
    if not rows:
        story.append(para('Aucune donnée dans le périmètre sélectionné.'))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor('#dce3ef'))
        canvas.line(38, 32, A4[0] - 38, 32)
        canvas.setFont('Orvia', 7)
        canvas.setFillColor(colors.HexColor('#6b7890'))
        canvas.drawString(38, 21, 'Orvia CRM - Export confidentiel')
        canvas.drawRightString(A4[0] - 38, 21, f'Page {doc.page}')
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return stream.getvalue()


def response(title, headers, rows, filename, description=''):
    result = HttpResponse(
        document(title, headers, rows, description), content_type='application/pdf'
    )
    result['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
    result['Cache-Control'] = 'no-store'
    result['X-Content-Type-Options'] = 'nosniff'
    return result
