"""Copy the three M-Pesa secrets into a PythonAnywhere deployment's .env.

Run this on your own machine, not on PythonAnywhere:

    python deploy/set_mpesa_secrets.py <username>

It reads MPESA_CONSUMER_KEY, MPESA_CONSUMER_SECRET and MPESA_PASSKEY from the
local .env, rewrites those three lines in /home/<username>/Fashion-Shop/.env,
and reloads the web app — the same thing step 5 of DEPLOY.md does by hand, but
without opening a console.

Only those three lines are touched. Everything else in the remote .env is
host-specific (ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, MPESA_CALLBACK_BASE_URL,
that account's SECRET_KEY) and is left byte-for-byte alone, which is what makes
this safe in a way that copying a whole .env across accounts is not.

Needs an API token: https://www.pythonanywhere.com/account/#api_token, then
either export PYTHONANYWHERE_API_TOKEN or save it to ~/.pythonanywhere_token.
Free accounts have the API too, so nothing here needs a paid plan.

Prints key names, value lengths and HTTP statuses — never a secret's value, so
the output is safe to leave on screen while presenting.
"""

import os
import sys
from pathlib import Path

import requests

KEYS = ('MPESA_CONSUMER_KEY', 'MPESA_CONSUMER_SECRET', 'MPESA_PASSKEY')
LOCAL_ENV = Path(__file__).resolve().parent.parent / '.env'


def read_secrets(text):
    """Pull KEYS out of an .env body as {key: value}."""
    found = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        if key.strip() in KEYS:
            found[key.strip()] = value.strip()
    return found


def api_token():
    token = os.environ.get('PYTHONANYWHERE_API_TOKEN')
    if not token:
        saved = Path.home() / '.pythonanywhere_token'
        if saved.exists():
            token = saved.read_text().strip()
    if not token:
        sys.exit('No API token. Set PYTHONANYWHERE_API_TOKEN or write '
                 '~/.pythonanywhere_token (see the module docstring).')
    return token


def summarise(label, values):
    print(label, ', '.join(f'{k}={len(values.get(k, ""))} chars' for k in KEYS))


def main():
    if len(sys.argv) != 2:
        sys.exit(f'usage: python {sys.argv[0]} <pythonanywhere-username>')
    username = sys.argv[1]
    remote_env = f'/home/{username}/Fashion-Shop/.env'
    api = f'https://www.pythonanywhere.com/api/v0/user/{username}'

    session = requests.Session()
    session.headers['Authorization'] = f'Token {api_token()}'

    local = read_secrets(LOCAL_ENV.read_text())
    missing = [key for key in KEYS if not local.get(key)]
    if missing:
        sys.exit(f'{LOCAL_ENV} has no value for: {", ".join(missing)}')
    summarise('local  :', local)

    response = session.get(f'{api}/files/path{remote_env}')
    if response.status_code == 404:
        sys.exit(f'{remote_env} does not exist — run the setup script first.')
    response.raise_for_status()
    body = response.content.decode()
    summarise('remote :', read_secrets(body))

    # Rewrite in place rather than regenerating the file, so comments, ordering
    # and line endings survive untouched.
    patched, seen = [], set()
    for line in body.splitlines(keepends=True):
        stripped = line.rstrip('\r\n')
        ending = line[len(stripped):] or '\n'
        if '=' in stripped and not stripped.lstrip().startswith('#'):
            key = stripped.split('=', 1)[0].strip()
            if key in KEYS and key not in seen:
                seen.add(key)
                patched.append(f'{key}={local[key]}{ending}')
                continue
        patched.append(line)
    for key in KEYS:                     # absent from the remote file entirely
        if key not in seen:
            if patched and not patched[-1].endswith('\n'):
                patched[-1] += '\n'
            patched.append(f'{key}={local[key]}\n')
            print(f'note   : {key} was not present remotely — appended')
    new_body = ''.join(patched)

    if new_body == body:
        print('no change needed — remote already matches local')
        return

    response = session.post(f'{api}/files/path{remote_env}',
                            files={'content': ('.env', new_body.encode())})
    response.raise_for_status()
    print(f'upload : HTTP {response.status_code}')

    # Read it back rather than trusting the upload, because the next step
    # restarts the site and a half-written .env would take it down.
    response = session.get(f'{api}/files/path{remote_env}')
    response.raise_for_status()
    after = read_secrets(response.content.decode())
    summarise('verify :', after)
    if any(after.get(key) != local[key] for key in KEYS):
        sys.exit('remote values do not match local after upload — not reloading')

    domain = f'{username}.pythonanywhere.com'
    response = session.post(f'{api}/webapps/{domain}/reload/')
    response.raise_for_status()
    print(f'reload : HTTP {response.status_code} ({domain})')


if __name__ == '__main__':
    main()
