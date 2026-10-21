#!/bin/sh
# One table and one instance at a time, so migrating at start-up is safe and simple.
# Change when: several replicas or risky migrations -> run them as a separate pre-deploy step.
set -e
python manage.py migrate --noinput
exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8080}" \
  --workers 2 --threads 4 --timeout 30
