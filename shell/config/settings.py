"""Django settings for the shell.

Everything secret or machine-specific comes from the environment, set from .env by compose.yaml.
A missing value stops the shell at start-up instead of failing halfway through a conversation.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from config.project import load_study

SHELL_VERSION = "0.1.0"
BASE_DIR = Path(__file__).resolve().parent.parent


def required(name: str) -> str:
    """Return an environment variable; stop when it is missing or empty."""
    value = os.environ.get(name, "")
    if not value:
        raise ImproperlyConfigured(f"{name} is not set; see .env.example")
    return value


DEBUG = required("SHELL_ENV") == "development"
SECRET_KEY = required("DJANGO_SECRET_KEY")
SHELL_HOST = required("SHELL_HOST")
BOT_URL = f"https://{required('BOT_HOST')}"
BRIDGE_SECRET = required("BRIDGE_SECRET")
FIELD_ENCRYPTION_KEY = required("FIELD_ENCRYPTION_KEY")

# The study: /project/project.toml and /project/questionnaire.toml.
PROJECT_DIR = Path(required("PROJECT_DIR"))
STUDY = load_study(PROJECT_DIR)

# "shell" is the name Tilbot uses to reach /bridge/ inside the Docker network.
ALLOWED_HOSTS = [SHELL_HOST, "shell"]
CSRF_TRUSTED_ORIGINS = [f"https://{SHELL_HOST}"]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")  # Caddy handles HTTPS
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_AGE = 60 * 60 * 12  # seconds; the same as the chat token (bridge/tokens.py)

INSTALLED_APPS = [
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "accounts",
    "records",
    "bridge",
    # phase2_feedback, phase3_support and monitor join when they get models or pages.
    # phase1_collect is plain Python (rules only) and needs no entry here.
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "config.context_processors.study",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": required("POSTGRES_DB"),
        "USER": required("POSTGRES_USER"),
        "PASSWORD": required("POSTGRES_PASSWORD"),
        "HOST": os.environ.get("POSTGRES_HOST", "db"),
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "en"  # Django's own messages; the participant pages use STUDY.texts and STUDY.language
TIME_ZONE = "Europe/Amsterdam"
USE_I18N = True
USE_TZ = True

# Caddy serves the collected files from the shared "static" volume.
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static", ("theme", PROJECT_DIR / "theme")]
