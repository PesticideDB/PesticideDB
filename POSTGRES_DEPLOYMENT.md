# PostgreSQL Deployment Notes

These notes describe how to run PesticideDB with PostgreSQL in production while keeping SQLite for local development.

## 1. Create Production Environment Variables

Set these variables in the hosting provider dashboard:

```bash
DJANGO_SECRET_KEY=<long-random-secret>
DJANGO_DEBUG=False
DJANGO_PUBLIC_DEMO=True
DJANGO_ALLOWED_HOSTS=<your-hosting-domain>
DJANGO_CSRF_TRUSTED_ORIGINS=https://<your-hosting-domain>
DJANGO_SECURE_COOKIES=True
DATABASE_URL=postgres://USER:PASSWORD@HOST:5432/DBNAME
DATABASE_SSLMODE=require
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

## 4. Load the SQLite Export into PostgreSQL

From the current SQLite database, the local export is:

```text
backups/postgres_migration/pesticidedb_sqlite_export_20260731.json
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
- Do not commit `db.sqlite3` or real `.env` files to GitHub.
- Keep a timestamped SQLite backup before every public release.
