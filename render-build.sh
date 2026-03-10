#!/usr/bin/env bash
# exit on error
set -o errexit

# Install dependencies if not using Docker (fallback)
# pip install -r backend/requirements/base.txt -r backend/requirements/prod.txt

# Collect static files with Build Shield active
# This ensures we don't attempt to connect to the DB during static collection
export IS_BUILD_PHASE=true
python backend/manage.py collectstatic --no-input --clear
