# config/__init__.py
#
# DO NOT import Celery here at module level.
# Importing Celery here causes `config/__init__.py` to be executed whenever
# Python imports anything from the `config` package (e.g. settings), which
# breaks environments where Celery isn't installed (CI, tests, migrations).
#
# The Celery app is exposed via config/celery.py and loaded explicitly by:
#   - The Celery worker:  celery -A config.celery worker
#   - The run script:     run_dev.sh
#
# See: https://docs.celeryq.dev/en/stable/django/first-steps-with-django.html
