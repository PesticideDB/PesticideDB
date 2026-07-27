# PesticideDB

PesticideDB is a Django database for curated microbial pesticide biodegradation records, with browse pages for microorganisms and proteins plus DIAMOND/HMMER annotation tools for uploaded gene, protein, genome, or contig FASTA files.

## Setup

```bash
python -m venv env
source env/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Annotation Tool Dependencies

The web annotation tools call external command-line programs:

- `diamond`
- `hmmscan` from HMMER
- `prodigal` for nucleotide FASTA translation before `blastp`

Make sure these commands are installed and available on `PATH` for the Django process.

The annotation assets are read from `PBDB_annotation/` by default. To place them elsewhere, set:

```bash
export PBDB_ANNOTATION_DIR=/path/to/PBDB_annotation
```

## Deployment Settings

The app reads these optional environment variables:

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_PUBLIC_DEMO`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `DJANGO_ENABLE_ADMIN`
- `DJANGO_SERVE_MEDIA`
- `PBDB_ANNOTATION_DIR`

Annotation jobs write per-job intermediate and downloadable files under `MEDIA_ROOT`, which prevents simultaneous jobs from overwriting each other.

For broad candidate discovery, the annotation forms default to DIAMOND `1e-3` and 25 percent identity. Users can tighten these thresholds for higher-confidence homologs.

## Temporary Public Demo

For a short VS Code Port Forwarding, ngrok, or Cloudflare Tunnel demo, run Django in public-demo mode. This forces `DEBUG=False`, disables the Django admin URL, and stops serving raw files from `/media/`.

After your tunnel gives you a public hostname, run:

```bash
scripts/run_public_demo.sh your-public-hostname 8000
```

Use only the hostname, without `https://`. For example:

```bash
scripts/run_public_demo.sh abc-8000.app.github.dev 8000
```

Stop the server when the demo is finished. If you need admin access, do it locally in a separate private session rather than through a public tunnel.
