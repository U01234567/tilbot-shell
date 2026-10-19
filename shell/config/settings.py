"""Django settings for the shell.

Everything secret or machine-specific comes from the environment, set from .env by compose.yaml.
A missing value stops the shell at start-up instead of failing halfway through a conversation.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from config.project import load_study

SHELL_VERSION = "0.11.0"  # shown in the mark at the bottom of the shell's pages
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
INTENT_URL = "http://vector-similarity-intent:8081/"  # phase 3, inside the Docker network only
BRIDGE_SECRET = required("BRIDGE_SECRET")
FIELD_ENCRYPTION_KEY = required("FIELD_ENCRYPTION_KEY")

# The study: project/project.toml and project/questionnaire.toml.
PROJECT_DIR = Path(required("PROJECT_DIR"))
STUDY = load_study(PROJECT_DIR)

# "shell" is the name Tilbot uses to reach /bridge/ inside the Docker network.
# 127.0.0.1:8081 is the researcher port with the researcher dashboard (compose.dev.yaml publishes it on this computer only).
RESEARCHER_ORIGIN = "http://127.0.0.1:8081"
ALLOWED_HOSTS = [SHELL_HOST, "shell", "127.0.0.1"]
CSRF_TRUSTED_ORIGINS = [f"https://{SHELL_HOST}", RESEARCHER_ORIGIN]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")  # Caddy handles HTTPS
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_AGE = 60 * 60 * 12  # seconds; also how long a chat token stays valid (bridge/tokens.py)

INSTALLED_APPS = [
    "django.contrib.auth",  # researcher accounts for the dashboard; participants are not users
    "django.contrib.contenttypes",  # needed by auth
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "accounts",
    "records",
    "bridge",
    "monitor",
    "phase2_feedback",
    # phase1_collect and phase3_questions are plain Python (rules and matching) and need no entry here.
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
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

# Researchers log in at /researcher/login (monitor app); participants never use Django's auth.
LOGIN_URL = "/researcher/login"
LOGIN_REDIRECT_URL = "/researcher/"
LOGOUT_REDIRECT_URL = "/researcher/login"
AUTH_PASSWORD_VALIDATORS = [  # checked by createsuperuser and changepassword
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
]

LANGUAGE_CODE = STUDY.language  # Django's own form messages follow the study's language too
TIME_ZONE = STUDY.time_zone
USE_TZ = True

# Caddy serves the collected files from the shared "static" volume.
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static", ("theme", PROJECT_DIR / "theme")]
