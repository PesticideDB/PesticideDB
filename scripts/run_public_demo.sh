#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: scripts/run_public_demo.sh <public-hostname> [port]" >&2
  echo "Example: scripts/run_public_demo.sh abc-8000.app.github.dev 8000" >&2
  echo "Pass only the hostname, without https:// or a trailing slash." >&2
  exit 2
fi

HOSTNAME="${1#https://}"
HOSTNAME="${HOSTNAME#http://}"
HOSTNAME="${HOSTNAME%%/*}"
PORT="${2:-8000}"

export DJANGO_PUBLIC_DEMO=True
export DJANGO_DEBUG=False
export DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY:-$(./env/bin/python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')}"
export DJANGO_ENABLE_ADMIN=False
export DJANGO_SERVE_MEDIA=False
export DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1,${HOSTNAME}"
export DJANGO_CSRF_TRUSTED_ORIGINS="https://${HOSTNAME}"
export DJANGO_SECURE_COOKIES=True

./env/bin/python manage.py runserver "127.0.0.1:${PORT}"
