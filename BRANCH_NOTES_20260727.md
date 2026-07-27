# Branch Notes: progress-share-20260718

Saved on 2026-07-27 before starting the experimental Evidence Galaxy feature.

This branch preserves the current PesticideDB progress, including:

- 2025-2026 evidence integration into the main pesticide evidence files.
- Updated microorganism table format with `Culture_type` and metabolite/product synchronization.
- Updated citation/download assets in `data_files`.
- Updated pathway views, full-screen pathway interaction, and compound detail display improvements.
- Updated contact page interactions, Lab Cookie, and UI polish.
- Updated statistics page figures and hover interaction.
- Protein/gene additions and local protein structure preview assets.
- Public demo safety settings, site visit counter, and supporting migrations.
- Curation scripts used for recent evidence normalization, metabolite/product synchronization, taxonomy export, and release refresh.

Intentionally not committed:

- Local SQLite database file (`db.sqlite3`).
- Virtual environment (`env/`).
- Temporary files (`tmp/`) and local backup folders (`backups/`).

Next work should happen on a separate feature branch for the Evidence Galaxy / knowledge graph prototype.
