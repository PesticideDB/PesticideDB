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
- `PBDB_ANNOTATION_DIR`

Annotation jobs write per-job intermediate and downloadable files under `MEDIA_ROOT`, which prevents simultaneous jobs from overwriting each other.

For broad candidate discovery, the annotation forms default to DIAMOND `1e-3` and 25 percent identity. Users can tighten these thresholds for higher-confidence homologs.
