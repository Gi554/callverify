"""Create the server's private .env from deploy/env.production.template with fresh secrets.

Usage, on the server only:  python3 scripts/generate_production_env.py crm.example.com
Secret values are written to the file and never printed. An existing file is never replaced.
"""

import argparse
import base64
import os
import re
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / 'deploy' / 'env.production.template'
DOMAIN = re.compile(r'^(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$')
TO_FILL = ('PORTAL_EMAIL_HOST', 'PORTAL_EMAIL_USER', 'PORTAL_EMAIL_PASSWORD', 'EMAIL_HOST')


def fernet():
    # Same format as cryptography.fernet.Fernet.generate_key().
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


def render(domain):
    lines = []
    for line in TEMPLATE.read_text(encoding='utf-8').splitlines():
        line = line.replace('__DOMAIN__', domain)
        if '=__SECRET__' in line:
            line = line.replace('__SECRET__', secrets.token_urlsafe(48))
        if '=__FERNET__' in line:
            line = line.replace('__FERNET__', fernet())
        lines.append(line)
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('domain', help='Nom de domaine public, sans https:// (ex. crm.exemple.com)')
    parser.add_argument('--output', default=str(ROOT / '.env'))
    args = parser.parse_args()
    domain = args.domain.strip().lower()
    if not DOMAIN.match(domain):
        sys.exit(f'Domaine invalide : {domain!r}. Exemple attendu : crm.exemple.com')
    output = Path(args.output)
    if output.exists():
        sys.exit(
            f'{output} existe déjà : il n’est jamais remplacé (les clés en place doivent rester).'
        )
    content = render(domain)
    output.write_text(content, encoding='utf-8')
    try:
        output.chmod(0o600)
    except OSError:
        pass
    print(f'Fichier créé : {output} (domaine {domain}, clés et mots de passe générés).')
    print('Copiez ce fichier dans un coffre-fort : sans lui, les données chiffrées sont perdues.')
    print('À compléter avant le lancement :', ', '.join(TO_FILL), '(envoi des e-mails).')


if __name__ == '__main__':
    main()
