"""Test settings — sqlite + fast hashers so `manage.py test` needs no Postgres superuser.

Usage: venv/bin/python manage.py test --settings=config.settings.test
(CI with CREATEDB postgres can still run plain `manage.py test`.)
"""

from .base import *  # noqa

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "test_db.sqlite3",  # noqa: F821 — from base import
    }
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
