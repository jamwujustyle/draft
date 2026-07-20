#!/bin/sh
set -e

echo "Running migrations..."
python manage.py migrate

echo "Starting Gunicorn..."
exec gunicorn --bind 0.0.0.0:8000 config.wsgi:application
