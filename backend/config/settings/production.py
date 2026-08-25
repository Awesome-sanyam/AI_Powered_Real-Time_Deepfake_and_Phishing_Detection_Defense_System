"""
Django production settings.
Extends base settings with security hardening.
"""
from config.settings.base import *  # noqa: F401, F403

DEBUG = False
ALLOWED_HOSTS = []  # Set via environment variable in production
