"""
Django Development Settings
============================
Extends base.py with development-friendly overrides:
  - DEBUG mode with verbose error pages
  - SQLite fallback if PostgreSQL is not running
  - Redis channel layer (with InMemory fallback for CI)
  - Detailed per-module logging to stdout
  - CORS open to local dev clients

Author: Sanyam Gehlot
"""
from __future__ import annotations

import os

from config.settings.base import *  # noqa: F401, F403

# ── Core ──────────────────────────────────────────────────────────────────────

DEBUG = True
ALLOWED_HOSTS = ["*"]

# ── Database — PostgreSQL primary, SQLite fallback ────────────────────────────
# Use SQLite automatically if POSTGRES_HOST is not set (e.g. local quick-start
# without Docker). Production always uses PostgreSQL.

if os.environ.get("POSTGRES_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "defence_db"),
            "USER": os.environ.get("POSTGRES_USER", "defence_user"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "defence_password"),
            "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": 60,
            "OPTIONS": {"connect_timeout": 5},
        }
    }
else:
    import os as _os
    _BASE_DIR = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": _os.path.join(_BASE_DIR, "db.sqlite3"),
        }
    }
    import warnings
    warnings.warn(
        "POSTGRES_HOST not set — using SQLite. Set POSTGRES_HOST to use PostgreSQL.",
        stacklevel=1,
    )

# ── Django Channels — Redis with InMemory CI fallback ─────────────────────────
_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

try:
    import redis as _redis_lib
    _r = _redis_lib.from_url(_REDIS_URL, socket_connect_timeout=2)
    _r.ping()
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [_REDIS_URL],
                "capacity": 1500,        # max messages per channel
                "expiry": 10,            # message TTL in seconds
            },
        }
    }
except Exception:
    # Redis not available (CI or local without Docker) → in-memory layer
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }

# ── CORS — allow local dev clients ────────────────────────────────────────────
CORS_ALLOW_ALL_ORIGINS = False

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
CORS_ALLOW_CREDENTIALS = True

# ── Email (dev — print to console) ────────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ── Static files ──────────────────────────────────────────────────────────────
STATIC_URL = "/static/"
STATICFILES_DIRS: list = []

# ── Logging — structured per-module output ────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} [{levelname}] {name} — {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "simple": {
            "format": "[{levelname}] {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": "WARNING",   # suppress SQL query noise unless debugging
            "propagate": False,
        },
        "channels": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}
