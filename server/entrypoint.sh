#!/bin/sh
set -e

echo "Running migrations..."
python manage.py migrate

if [ "$DEBUG" = "True" ]; then
    echo "Starting Django dev server with hot-reload..."
    exec python manage.py runserver 0.0.0.0:8000
else
    echo "Starting Gunicorn..."
    exec gunicorn --bind 0.0.0.0:8000 --workers 2 config.wsgi:application
fi
