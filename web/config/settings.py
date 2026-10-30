# web/config/settings.py: Application settings configuration.
"""Django settings for the AI Digital Locker web client.

Configuration comes from environment variables (web/.env, with the
repo-root .env as a fallback for shared values like FASTAPI_BASE_URL).
Django never holds Supabase or OpenRouter credentials - all application
data flows through the FastAPI backend over HTTP.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent

load_dotenv(REPO_ROOT / ".env")                                         
load_dotenv(BASE_DIR / ".env")                                

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if "test" in sys.argv:
        SECRET_KEY = "insecure-test-only-key"
    else:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY is not set. Copy web/.env.example to web/.env "
            "and generate a key: py -c \"import secrets; "
            "print(secrets.token_urlsafe(64))\""
        )


def _env_bool(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in ("1", "true", "yes", "on")


DEBUG = _env_bool("DEBUG", False)

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if h.strip()
]

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "django.contrib.sessions",
    "django.contrib.messages",
    "locker",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
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
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

                                                                       
                                                                            
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
                                                                           
                                                                       
COOKIE_SECURE = _env_bool("COOKIE_SECURE", not DEBUG)
SESSION_COOKIE_SECURE = COOKIE_SECURE
CSRF_COOKIE_SECURE = COOKIE_SECURE

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [REPO_ROOT / "assets"]
                                                                           
WHITENOISE_USE_FINDERS = DEBUG
WHITENOISE_AUTOREFRESH = DEBUG
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

                                                          
FASTAPI_BASE_URL = os.environ.get("FASTAPI_BASE_URL", "http://127.0.0.1:8000")

                                                                  
                                                                  
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
