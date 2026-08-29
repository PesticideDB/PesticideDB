# PesticideDB

PesticideDB is a curated database and annotation platform for pesticide-degrading microorganisms, genes, proteins, enzymes, and biodegradation pathways. The resource integrates literature-derived biodegradation evidence with searchable microorganism and protein records, curated pathway information, protein structure assets, and DIAMOND/HMMER-based annotation tools for uploaded gene, protein, genome, or contig FASTA files.

## Overview

PesticideDB was developed to support research on microbial pesticide biodegradation, environmental bioremediation, and discovery of degradation-associated genes and enzymes. The database provides a structured web interface for browsing pesticide-microorganism associations, protein and enzyme evidence, predicted protein structures, curated transformation pathways, and summary statistics describing taxonomic, biochemical, and literature evidence patterns.

## Key Features

- Curated pesticide biodegradation records linked to microorganisms, isolation sources, publications, genes, enzymes, metabolites, and evidence summaries.
- Searchable microorganism and protein pages for exploring reported pesticide-degrading taxa and degradation-associated proteins.
- Curated pathway and compound pages for reviewing pesticide transformation routes and supporting evidence.
- Interactive annotation tools using DIAMOND and HMMER to compare user-submitted FASTA sequences against PesticideDB reference protein datasets.
- Statistics and visualization pages summarizing database coverage, taxonomic breadth, evidence support, transformation families, and reporting gaps.
- Deployment-ready Django application with local SQLite support and PostgreSQL configuration for shared or production hosting.

## Repository Contents

- `base/`: Django application logic, models, views, templates, tests, and management commands.
- `PepDatabase/`: Django project settings and URL configuration.
- `data_files/`: Curated core, protein, and pathway input datasets.
- `PBDB_annotation/`: Reference FASTA files, DIAMOND databases, HMMER profiles, and annotation helper scripts.
- `static/`: Website styling, images, JavaScript assets, and database summary figures.
- `media/protein_structures/`: Local predicted protein structure files and preview images.
- `curation_outputs/`: Supporting curated pathway, taxonomy, evidence, and supplemental protein data exports.

## Setup

```bash
python -m venv env
source env/bin/activate
pip install -r requirements.txt
export DJANGO_DEBUG=True
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
- `DJANGO_ALLOW_DEVTUNNELS`
- `DATABASE_URL`
- `DATABASE_SSLMODE`
- `DATABASE_CONN_MAX_AGE`
- `PBDB_ANNOTATION_DIR`

Annotation jobs write per-job intermediate and downloadable files under `MEDIA_ROOT`, which prevents simultaneous jobs from overwriting each other.

For broad candidate discovery, the annotation forms default to DIAMOND `1e-3` and 25 percent identity. Users can tighten these thresholds for higher-confidence homologs.

## Private Testing

For private multi-user testing, use PostgreSQL instead of SQLite and keep Django in non-debug mode:

```bash
export DJANGO_SECRET_KEY=<long-random-secret>
export DJANGO_DEBUG=False
export DJANGO_ALLOWED_HOSTS=<your-private-testing-domain>
export DJANGO_CSRF_TRUSTED_ORIGINS=https://<your-private-testing-domain>
export DJANGO_SECURE_COOKIES=True
export DJANGO_SECURE_SSL_REDIRECT=True
export DJANGO_SECURE_HSTS_SECONDS=31536000
export DJANGO_TRUST_PROXY_SSL_HEADER=True
export DJANGO_ENABLE_ADMIN=False
export DJANGO_SERVE_MEDIA=False
export DATABASE_URL=postgres://USER:PASSWORD@HOST:5432/DBNAME
python manage.py migrate
```

SQLite remains available only when `DATABASE_URL` is not set, which is useful for local development but not recommended for several testers using the site at the same time.

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
