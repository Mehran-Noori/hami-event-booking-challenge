#!/bin/sh
set -e

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Seeding the database with test data..."
python manage.py seed_data

echo "Starting application..."
exec "$@"