"""Prod settings — DEBUG=False, env-driven hosts/CORS. No secrets hardcoded.

Usage (Render/Railway):
  DJANGO_SETTINGS_MODULE=config.settings.prod
  env: SECRET_KEY, DEBUG=False, DB_*, ALLOWED_HOSTS, CORS_ALLOWED_ORIGINS
"""

from .base import *  # noqa

DEBUG = False

ALLOWED_HOSTS: list[str] = [  # noqa: F811
    h.strip()
    for h in env("ALLOWED_HOSTS", "").split(",")  # noqa: F821
    if h.strip()
]

# Fail fast if prod is misconfigured — better than serving with dev defaults.
if not SECRET_KEY or SECRET_KEY == "django-insecure-dev-only-change-me":  # noqa: F821
    raise RuntimeError("SECRET_KEY env is required in prod.")
if not ALLOWED_HOSTS:
    raise RuntimeError("ALLOWED_HOSTS env is required in prod (comma-separated).")

# CORS comes from base.py env parsing — re-assert whitelist (no "*").
assert all(o.startswith("http") for o in CORS_ALLOWED_ORIGINS), (  # noqa: F821
    "CORS_ALLOWED_ORIGINS must be full http(s) origins."
)

# Production DB + JWT hardening (keep PBKDF2 default hasher — never MD5 outside tests).
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
