"""WSGI entry point for PythonAnywhere.

This is a template, not a live module. PythonAnywhere does not import the
project's own myproject/wsgi.py — it imports a file it owns, at

    /var/www/<username>_pythonanywhere_com_wsgi.py

Open that file from the Web tab, delete everything in it, and paste this in.
No editing needed: the paths are derived from the home directory, so the same
text works for any account name.
"""

import os
import sys

PROJECT_DIR = os.path.expanduser('~/Fashion-Shop')

# The project package (myproject) is not installed, it is only a directory on
# disk, so its parent has to be importable before Django can be configured.
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

os.environ['DJANGO_SETTINGS_MODULE'] = 'myproject.settings'

# settings.py calls load_dotenv(BASE_DIR / '.env') itself, so the secrets are
# picked up here without any extra work.
from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
