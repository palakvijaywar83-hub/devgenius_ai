"""DevGenius AI settings. Secrets are read from environment variables / .env."""
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:  # python-dotenv is optional; real env vars still work
    pass

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


DEBUG = os.environ.get("DJANGO_DEBUG", "True").strip().lower() in ("1", "true", "yes")
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-insecure-key-set-DJANGO_SECRET_KEY-in-.env"
    else:
        raise ImproperlyConfigured("Set DJANGO_SECRET_KEY when DJANGO_DEBUG is off.")

ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "core",
    "tools",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "devgenius.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.ai_status",
            ],
        },
    },
]

WSGI_APPLICATION = "devgenius.wsgi.application"

DATABASES = {
    "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}
}

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:dashboard"
LOGOUT_REDIRECT_URL = "core:landing"

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "Asia/Kolkata")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---- Security -------------------------------------------------------------
DATA_UPLOAD_MAX_MEMORY_SIZE = 200_000  # reject oversized request bodies
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SSL_REDIRECT", "True").lower() == "true"
    SECURE_HSTS_SECONDS = 3600

# ---- Input limits ---------------------------------------------------------
MAX_CODE_CHARS = _env_int("MAX_CODE_CHARS", 8000)
MAX_TEXT_CHARS = _env_int("MAX_TEXT_CHARS", 2000)

# ---- AI provider (configurable; key only from environment) -----------------
AI_PROVIDER = os.environ.get("AI_PROVIDER", "anthropic").strip().lower()  # anthropic | openai
_DEFAULT_MODELS = {"anthropic": "claude-sonnet-5-5", "openai": "gpt-4o-mini"}
_KEY_FALLBACK = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}
AI_API_KEY = os.environ.get("AI_API_KEY") or os.environ.get(_KEY_FALLBACK.get(AI_PROVIDER, ""), "")
AI_MODEL = os.environ.get("AI_MODEL") or _DEFAULT_MODELS.get(AI_PROVIDER, "")
AI_BASE_URL = os.environ.get("AI_BASE_URL", "").strip()  # optional, OpenAI-compatible providers
AI_TIMEOUT = _env_int("AI_TIMEOUT", 60)
AI_MAX_TOKENS = _env_int("AI_MAX_TOKENS", 3500)
AI_RATE_LIMIT_PER_MINUTE = _env_int("AI_RATE_LIMIT_PER_MINUTE", 10)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"tools": {"handlers": ["console"], "level": "INFO"}},
}
