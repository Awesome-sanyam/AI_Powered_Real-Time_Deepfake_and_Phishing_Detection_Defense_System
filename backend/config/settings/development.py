"""
Django development settings.
Extends base settings with debug-friendly overrides.
"""
from config.settings.base import *  # noqa: F401, F403

DEBUG = True
ALLOWED_HOSTS = ["*"]
