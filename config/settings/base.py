"""Bhoj Bilash — shared settings (dev/prod common). Secrets come from .env only."""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR / ".env")


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


SECRET_KEY = env("SECRET_KEY", "django-insecure-dev-only-change-me")
DEBUG = env("DEBUG", "True") == "True"

ALLOWED_HOSTS: list[str] = [h for h in env("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if h]


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third-party
    "rest_framework",
    "corsheaders",
    # local
    "core",
    "users",
    "menu",
    "orders",
    "khata",
    "settingsplus",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database — PostgreSQL, credentials from .env (never hardcoded)
# Neon cloud host hole auto SSL (neon.tech require kore, local-e lage na).
_DB_HOST = env("DB_HOST", "localhost")
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME", "bhojbilash"),
        "USER": env("DB_USER", "bhojbilash_user"),
        "PASSWORD": env("DB_PASSWORD", "changeme"),
        "HOST": _DB_HOST,
        "PORT": env("DB_PORT", "5432"),
        **({"OPTIONS": {"sslmode": "require"}} if "neon.tech" in _DB_HOST else {}),
    }
}

AUTH_USER_MODEL = "users.User"


# Password validation

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# DRF — JWT only, JSON only, paginated lists, {message} errors

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.AllowAny",),
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_PAGINATION_CLASS": "core.pagination.BhojBilashPagination",
    "PAGE_SIZE": 20,
    "EXCEPTION_HANDLER": "core.errors.bhojbilash_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=12),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}


# Internationalization — shop time = Dhaka (open-now rule uses server-local time)

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Dhaka"
USE_I18N = True
USE_TZ = True


# CORS — dev default localhost:3000, prod override via CORS_ALLOWED_ORIGINS env (comma-separated).
# Never use "*" with credentials — whitelist only (Dhap 6 security pass).
CORS_ALLOWED_ORIGINS = [
    h.strip()
    for h in env("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if h.strip()
]
CORS_ALLOW_CREDENTIALS = True


STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
