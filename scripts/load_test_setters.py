"""Simulates several setters working at the same time and reports response times.

Reads only: each virtual setter signs in, then keeps loading the prospect board and the
dashboard, like a real screen does. No prospect is changed and no call is placed.

Accounts are never written in this file: pass them through the environment.

    LOAD_USERS="setter1:password1,setter2:password2" \
      python scripts/load_test_setters.py https://orvia-crm.com --setters 20 --seconds 60 --yes

With fewer accounts than setters, accounts are reused. Use test accounts, ideally on a copy of
the platform: every sign-in is recorded in the audit log and the sign-in rate limit applies.
"""

import argparse
import json
import os
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar

results = []
lock = threading.Lock()


def record(label, started, status):
    with lock:
        results.append((label, time.perf_counter() - started, status))


class Client:
    def __init__(self, base):
        self.base = base.rstrip('/')
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
        self.csrf = ''
        self.ticket = ''

    def call(self, label, method, path, body=None, bearer=False):
        headers = {'Content-Type': 'application/json'}
        if self.csrf:
            headers['X-CSRFToken'] = self.csrf
        if bearer:
            headers['Authorization'] = 'Bearer ' + self.ticket
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            self.base + path, data=data, method=method, headers=headers
        )
        started = time.perf_counter()
        try:
            with self.opener.open(request, timeout=30) as response:
                payload = response.read()
                record(label, started, response.status)
                return json.loads(payload or b'{}')
        except urllib.error.HTTPError as error:
            record(label, started, error.code)
        except Exception:
            record(label, started, 0)
        return {}

    def sign_in(self, username, password, workspace):
        self.csrf = self.call('csrf', 'GET', '/api/portal/csrf/').get('csrfToken', '')
        self.call(
            'login', 'POST', '/api/portal/login/', {'username': username, 'password': password}
        )
        # The session token is renewed at sign-in: read the new one before posting again.
        self.csrf = self.call('csrf', 'GET', '/api/portal/csrf/').get('csrfToken', '')
        self.ticket = self.call('access', 'POST', f'/api/portal/access/{workspace}/', {}).get(
            'token', ''
        )
        return bool(self.ticket)


def setter(base, account, workspace, until, offset):
    time.sleep(offset)  # Spread the sign-ins over a few seconds, as people arrive.
    client = Client(base)
    if not client.sign_in(*account, workspace):
        return
    prefix = '/api/assurance' if workspace == 'assurance' else '/api/isolation'
    while time.perf_counter() < until:
        if workspace == 'assurance':
            client.call('board: stages', 'GET', prefix + '/pipeline/', bearer=True)
            client.call(
                'board: column',
                'GET',
                prefix + '/contacts/?status=to_contact&queue=active',
                bearer=True,
            )
            client.call('dashboard', 'GET', prefix + '/dashboard/', bearer=True)
        else:
            client.call(
                'board: column',
                'GET',
                prefix + '/work-queue/?queue=active&commercial_status=to_contact',
                bearer=True,
            )
            client.call('dashboard', 'GET', prefix + '/workspace-dashboard/', bearer=True)
        time.sleep(2)


def percentile(values, share):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * share))]


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('base_url')
    parser.add_argument('--setters', type=int, default=20)
    parser.add_argument('--seconds', type=int, default=60)
    parser.add_argument('--workspace', choices=['assurance', 'isolation'], default='assurance')
    parser.add_argument(
        '--yes', action='store_true', help='confirm the target is meant to be loaded'
    )
    args = parser.parse_args()
    raw = os.environ.get('LOAD_USERS', '')
    accounts = [tuple(part.split(':', 1)) for part in raw.split(',') if ':' in part]
    if not accounts:
        sys.exit('Définissez LOAD_USERS="identifiant:motdepasse,..." (comptes de test).')
    if not args.yes:
        sys.exit(
            f'Ce test connecte {args.setters} setters virtuels à {args.base_url}. Relancez avec --yes.'
        )
    until = time.perf_counter() + args.seconds
    threads = [
        threading.Thread(
            target=setter,
            args=(args.base_url, accounts[i % len(accounts)], args.workspace, until, i * 0.3),
        )
        for i in range(args.setters)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    print(f'{len(results)} requêtes, {args.setters} setters, {args.seconds} s')
    for label in sorted({row[0] for row in results}):
        rows = [row for row in results if row[0] == label]
        times = [row[1] for row in rows]
        bad = sum(1 for row in rows if row[2] != 200)
        print(
            f'{label:18} n={len(rows):4}  médiane={statistics.median(times) * 1000:6.0f} ms  '
            f'p95={percentile(times, 0.95) * 1000:6.0f} ms  max={max(times) * 1000:6.0f} ms  '
            f'erreurs={bad}'
        )
    errors = {}
    for _, _, status in results:
        if status != 200:
            errors[status] = errors.get(status, 0) + 1
    if errors:
        print('Codes en erreur :', errors, '(429 = limite de connexions ou de requêtes atteinte)')


if __name__ == '__main__':
    main()
