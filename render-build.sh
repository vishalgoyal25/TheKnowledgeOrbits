#!/usr/bin/env bash
# exit on error
set -o errexit

# Install dependencies if not using Docker (fallback)
# pip install -r backend/requirements/base.txt -r backend/requirements/prod.txt

# Run migrations
python backend/manage.py migrate --noinput

# Collect static files
python backend/manage.py collectstatic --no-input --clear
