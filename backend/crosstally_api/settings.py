import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# --- configuration comes from environment variables so the same code runs locally and in production
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
DEBUG = os.environ.get("DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*" if DEBUG else "").split(",")
APPLE_BUNDLE_ID = os.environ.get("APPLE_BUNDLE_ID", "com.example.crosstally")   # must match the iOS app
PUZZLE_DIR = Path(os.environ.get("PUZZLE_DIR", BASE_DIR.parent / "daily"))       # folder written by make_daily.py
TOKEN_DAYS = int(os.environ.get("TOKEN_DAYS", "60"))

if not DEBUG and SECRET_KEY == "dev-only-change-me":
    raise RuntimeError("Set SECRET_KEY in production")

INSTALLED_APPS = ["django.contrib.contenttypes", "django.contrib.auth", "game"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "django.middleware.common.CommonMiddleware"]
ROOT_URLCONF = "crosstally_api.urls"
WSGI_APPLICATION = "crosstally_api.wsgi.application"

if os.environ.get("DATABASE_URL", "").startswith("postgres"):
    import urllib.parse as up
    u = up.urlparse(os.environ["DATABASE_URL"])
    DATABASES = {"default": {"ENGINE": "django.db.backends.postgresql", "NAME": u.path.lstrip("/"),
                             "USER": u.username, "PASSWORD": u.password, "HOST": u.hostname, "PORT": u.port or 5432,
                             "CONN_MAX_AGE": 60}}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"
