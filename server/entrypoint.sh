#!/bin/bash
set -e

echo "Waiting for database..."
python -c "
import time
import psycopg2
import sys
import os

db_url = os.environ.get('DATABASE_URL')
for i in range(30):
    try:
        conn = psycopg2.connect(db_url)
        conn.close()
        sys.exit(0)
    except Exception as e:
        print(f'Database not ready yet (attempt {i+1}/30): {e}')
        time.sleep(1)
sys.exit(1)
"

echo "Database is ready. Running migrations..."
python manage.py migrate

echo "Starting server..."
exec gunicorn --bind 0.0.0.0:8000 config.wsgi:application
