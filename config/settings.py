import os
import secrets
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured


def local_secret():
    value = os.environ.get("DJANGO_SECRET_KEY")
    if value:
        return value
    if os.environ.get("DJANGO_DEBUG", "1") != "1":
        raise ImproperlyConfigured("Для запуска без DEBUG задайте DJANGO_SECRET_KEY.")
    path = Path(__file__).resolve().parents[1] / ".django-secret-key"
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(secrets.token_urlsafe(64))
    value = path.read_text(encoding="utf-8").strip()
    if len(value) < 50:
        raise ImproperlyConfigured("Локальный ключ Django отсутствует или повреждён.")
    return value

SECRET_KEY = local_secret()
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "core.apps.CoreConfig",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
AUTH_USER_MODEL = "core.User"
USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": os.environ.get("PGDATABASE", "pc_architect"),
    "USER": os.environ.get("PGUSER", "postgres"),
    "PASSWORD": os.environ.get("PGPASSWORD", ""),
    "HOST": os.environ.get("PGHOST", "127.0.0.1"),
    "PORT": os.environ.get("PGPORT", "5432"),
}}

CSRF_FAILURE_VIEW = "core.auth_views.csrf_failure"
CSRF_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_SECURE = not DEBUG
X_FRAME_OPTIONS = "DENY"
AUTH_ACCESS_SECONDS = 900
AUTH_REFRESH_DAYS = 30
AUTH_REFRESH_COOKIE = "pc_refresh"
AUTH_TOKEN_ISSUER = "pc-architect"
AUTH_TOKEN_AUDIENCE = "pc-architect-web"
AUTH_LOGIN_ACCOUNT_LIMIT = 5
AUTH_LOGIN_IP_LIMIT = 20
AUTH_LOGIN_WINDOW_SECONDS = 900
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "ru-ru"


def frontend_directory():
    configured = os.environ.get("FRONTEND_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    workspace = Path(__file__).resolve().parents[2]
    for name in ("frontend", "pc-architect-frontend", "pc-architect-frontend-main", "pc-architect-frontend-master"):
        candidate = workspace / name
        if (candidate / "index.html").is_file():
            return candidate
    return workspace / "frontend"


FRONTEND_DIR = frontend_directory()
