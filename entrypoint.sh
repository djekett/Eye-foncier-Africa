#!/usr/bin/env bash
set -o errexit

echo "==> Collecting static files..."
python manage.py collectstatic --no-input

echo "==> Running migrations..."
python manage.py migrate --no-input

echo "==> Starting Gunicorn on port 10000..."
exec gunicorn eyefoncier.wsgi:application --bind 0.0.0.0:10000
