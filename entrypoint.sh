#!/bin/bash

# Exit on error
set -e

echo "Waiting for PostgreSQL to be ready..."
until pg_isready -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$POSTGRES_USER" > /dev/null 2>&1; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 1
done

echo "PostgreSQL is up - executing command"

# Run migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput --clear || true

# Create superuser if it doesn't exist (optional)
# Uncomment the following lines if you want to auto-create a superuser
# echo "Creating superuser..."
# python manage.py shell -c "from myapp.models import User; User.objects.filter(username='admin').exists() or User.objects.create_superuser('admin', 'admin@example.com', 'admin123')"

echo "Starting application..."
exec "$@"
