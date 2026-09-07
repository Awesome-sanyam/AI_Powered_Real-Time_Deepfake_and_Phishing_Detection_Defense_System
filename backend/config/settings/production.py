"""
Django production settings.
Extends base settings with security hardening.
"""
from config.settings.base import *  # noqa: F401, F403

import os
from django.core.exceptions import ImproperlyConfigured

DEBUG = False
ALLOWED_HOSTS = []  # Set via environment variable in production

if not os.environ.get("DJANGO_SECRET_KEY"):
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set in production")
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
