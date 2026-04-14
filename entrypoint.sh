#!/usr/bin/env bash
set -o errexit

echo "==> Environment check..."
echo "DATABASE_URL is set: $([ -n \"$DATABASE_URL\" ] && echo 'yes' || echo 'no')"
echo "DJANGO_DEBUG: $DJANGO_DEBUG"

echo "==> Collecting static files..."
python manage.py collectstatic --no-input --verbosity 2 2>&1 || echo "WARNING: collectstatic failed, continuing..."

echo "==> Running migrations..."
python manage.py migrate --no-input 2>&1 || echo "WARNING: migrate failed, continuing..."

echo "==> Starting Gunicorn on port 10000..."
exec gunicorn eyefoncier.wsgi:application --bind 0.0.0.0:10000
