# PostgreSQL Deployment Notes

These notes describe how to run PesticideDB with PostgreSQL in production while keeping SQLite for local development.

## 1. Create Production Environment Variables

Set these variables in the hosting provider dashboard:

```bash
DJANGO_SECRET_KEY=<long-random-secret>
DJANGO_DEBUG=False
DJANGO_PUBLIC_DEMO=False
DJANGO_ALLOWED_HOSTS=<your-hosting-domain>
DJANGO_CSRF_TRUSTED_ORIGINS=https://<your-hosting-domain>
DJANGO_SECURE_COOKIES=True
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_SECURE_HSTS_SECONDS=31536000
DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=True
DJANGO_SECURE_HSTS_PRELOAD=False
DJANGO_TRUST_PROXY_SSL_HEADER=True
DJANGO_ENABLE_ADMIN=False
DJANGO_SERVE_MEDIA=False
DATABASE_URL=postgres://USER:PASSWORD@HOST:5432/DBNAME
DATABASE_SSLMODE=require
DATABASE_CONN_MAX_AGE=60
```

Use `.env.example` as the template, but never commit real passwords or secrets.

## 2. Install Dependencies

```bash
pip install -r requirements.txt
```

`psycopg2-binary` is included so Django can connect to PostgreSQL when `DATABASE_URL` is set.

## 3. Migrate the PostgreSQL Database

Run this on the production server after `DATABASE_URL` is configured:

```bash
python manage.py migrate
```

If you are testing locally over plain HTTP, temporarily set `DJANGO_DEBUG=True` and `DJANGO_SECURE_COOKIES=False`. Do not use those local settings for a shared testing URL.

## 4. Load the SQLite Export into PostgreSQL

From the current SQLite database, the local export is:

```text
backups/postgres_migration/pesticidedb_sqlite_export_20260803.json
```

Copy that file to the production server and run:

```bash
python manage.py loaddata pesticidedb_sqlite_export_20260731.json
```

## 5. Collect Static Files

Run this on the production server so CSS, JavaScript, and Statistics figures are served:

```bash
python manage.py collectstatic --noinput
```

## 6. Smoke Test

After deployment, check:

- `/`
- `/statistics/`
- pesticide and microorganism search pages
- CSV/download pages
- annotation tools, if enabled for public use

## Notes

- Local development uses `db.sqlite3` automatically when `DATABASE_URL` is not set.
- Multi-user private testing should use `DATABASE_URL` so all testers read and write the same PostgreSQL database.
- Do not commit `db.sqlite3` or real `.env` files to GitHub.
- Keep a timestamped SQLite backup before every public release.
- Keep `DJANGO_DEBUG=False` for every shared URL, including private test links.
- `DJANGO_SECURE_HSTS_PRELOAD` is intentionally `False` for private testing. Turn it on only after the final public domain and HTTPS setup are permanent.
