"""Generate a local HTML gallery with synthetic links only; never sends mail.

Usage: python scripts/preview_crm_emails.py PATH.html
"""

import argparse
from html import escape
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from django.conf import settings

if not settings.configured:
    settings.configure(DEBUG=False)
from portal.backend.identity.email_layout import layout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    variants = [
        dict(
            title='Bienvenue dans votre équipe',
            intro='Vous êtes invité dans l’espace Assurance en tant que Conseiller. Activez votre compte en choisissant votre mot de passe.',
            action='Activer mon compte',
            name='camille.exemple',
            url='https://example.invalid/crm#invite=EXEMPLE:NON-UTILISABLE',
            notice='Ce lien personnel expire dans 24 heures et ne peut être utilisé qu’une fois.',
            details=(
                ('Espace', 'Assurance'),
                ('Votre rôle', 'Conseiller'),
                ('Votre identifiant', 'camille.exemple'),
            ),
        ),
        dict(
            title='Un nouvel accès, en toute sécurité',
            intro='Une réinitialisation de votre mot de passe a été demandée. Choisissez un nouveau mot de passe pour retrouver votre espace Orvia CRM.',
            action='Choisir mon mot de passe',
            name='camille.exemple',
            url='https://example.invalid/crm#reset=EXEMPLE:NON-UTILISABLE',
            notice='Ce lien personnel expire dans 30 minutes et ne peut être utilisé qu’une fois. Si vous n’êtes pas à l’origine de cette demande, ignorez cet e-mail : votre mot de passe reste inchangé.',
        ),
        dict(
            title='Votre prochain suivi vous attend',
            intro='Un rappel nécessite votre attention dans votre espace Assurance. Connectez-vous pour consulter vos notifications, rendez-vous et tâches.',
            action='Consulter mon espace',
            name='camille.exemple',
            url='https://example.invalid/crm',
            notice='La lecture de cet e-mail ne clôture aucune tâche et ne renseigne aucun compte rendu. Retrouvez les détails uniquement après connexion à votre espace autorisé.',
            details=(('Espace', 'Assurance'),),
        ),
    ]
    sections = []
    for values in variants:
        html = escape(layout(**values), quote=True)
        sections.append(
            '<section><h2>'
            + escape(values['title'])
            + '</h2><div class="views"><iframe title="Aperçu bureau" srcdoc="'
            + html
            + '"></iframe><iframe class="mobile" title="Aperçu mobile" srcdoc="'
            + html
            + '"></iframe></div></section>'
        )
    gallery = (
        '<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Aperçus des e-mails Orvia CRM</title><style>body{margin:0;padding:28px;background:#e9edf6;color:#182b40;font-family:Arial,sans-serif}h1{margin-bottom:8px}p{line-height:1.6}section{margin:35px 0}.views{display:flex;gap:24px;flex-wrap:wrap;align-items:flex-start}iframe{border:1px solid #d1d9e8;border-radius:12px;width:660px;max-width:100%;height:900px;background:white}.mobile{width:360px}</style><h1>Orvia CRM · E-mails transactionnels</h1><p>Aperçus bureau et mobile. Données fictives ; aucun lien actif et aucun e-mail envoyé.</p>'
        + ''.join(sections)
        + '</html>'
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(gallery, encoding='utf-8')
    print(args.output.resolve())


if __name__ == '__main__':
    main()
