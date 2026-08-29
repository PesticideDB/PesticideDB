import csv
from pathlib import Path

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from base.models import ProteinRecord


ALPHAFOLD_PDB_URL = "https://alphafold.ebi.ac.uk/files/AF-{accession}-F1-model_v{version}.pdb"
ALPHAFOLD_API_URL = "https://alphafold.ebi.ac.uk/api/prediction/{accession}"
ALPHAFOLD_VERSIONS = [6, 5, 4, 3, 2, 1]


def clean_value(value):
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none", "not available", "n/a", "-"}:
        return ""
    return text


class Command(BaseCommand):
    help = "Download local AlphaFold predicted PDB structures for ProteinRecord rows with UniProt accessions."

    def add_arguments(self, parser):
        parser.add_argument("--timeout", type=int, default=60)
        parser.add_argument("--overwrite", action="store_true")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Optional maximum number of proteins to process.",
        )

    def handle(self, *args, **options):
        timeout = options["timeout"]
        overwrite = options["overwrite"]
        dry_run = options["dry_run"]
        limit = options["limit"]

        pdb_dir = settings.MEDIA_ROOT / "protein_structures" / "pdb"
        metadata_dir = settings.MEDIA_ROOT / "protein_structures" / "metadata"
        pdb_dir.mkdir(parents=True, exist_ok=True)
        metadata_dir.mkdir(parents=True, exist_ok=True)

        queryset = (
            ProteinRecord.objects
            .exclude(uniprot_accession__isnull=True)
            .exclude(uniprot_accession="")
            .order_by("pesticidedb_protein_id", "id")
        )
        if limit:
            queryset = queryset[:limit]

        report_rows = []
        downloaded = 0
        skipped = 0
        missing = 0

        for protein in queryset:
            display_id = protein.pesticidedb_protein_id or protein.pbdb_protein_id or f"protein_{protein.id}"
            uniprot_accession = clean_value(protein.uniprot_accession)
            output_path = pdb_dir / f"{display_id}.pdb"

            row = {
                "pesticidedb_protein_id": display_id,
                "uniprot_accession": uniprot_accession,
                "ncbi_protein_accession": clean_value(protein.ncbi_protein_accession),
                "status": "",
                "source_url": "",
                "local_path": str(output_path),
            }

            if not uniprot_accession:
                row["status"] = "no_uniprot_accession"
                missing += 1
                report_rows.append(row)
                continue

            if output_path.exists() and not overwrite:
                row["status"] = "already_exists"
                skipped += 1
                report_rows.append(row)
                self.stdout.write(f"Skipping existing structure: {display_id}")
                continue

            source_url, content = self.fetch_pdb(uniprot_accession, timeout=timeout)
            if not source_url:
                row["status"] = "not_found_in_alphafold"
                missing += 1
                report_rows.append(row)
                self.stdout.write(
                    self.style.WARNING(
                        f"No AlphaFold PDB found for {display_id} ({uniprot_accession})."
                    )
                )
                continue

            row["source_url"] = source_url
            if dry_run:
                row["status"] = "would_download"
                downloaded += 1
                self.stdout.write(f"Would download {display_id}: {source_url}")
            else:
                output_path.write_text(content)
                row["status"] = "downloaded"
                downloaded += 1
                self.stdout.write(self.style.SUCCESS(f"Downloaded {display_id}: {source_url}"))

            report_rows.append(row)

        report_path = metadata_dir / "alphafold_download_report.csv"
        if not dry_run:
            self.write_report(report_path, report_rows)

        self.stdout.write(
            self.style.SUCCESS(
                f"Structure download complete. Downloaded: {downloaded}. "
                f"Skipped existing: {skipped}. Not found/no accession: {missing}."
            )
        )
        if not dry_run:
            self.stdout.write(f"Report written to: {report_path}")

    def fetch_pdb(self, uniprot_accession, timeout):
        api_url = ALPHAFOLD_API_URL.format(accession=uniprot_accession)
        response = requests.get(api_url, timeout=timeout)
        if response.status_code == 200:
            predictions = response.json()
            if predictions:
                pdb_url = predictions[0].get("pdbUrl")
                if pdb_url:
                    pdb_response = requests.get(pdb_url, timeout=timeout)
                    pdb_response.raise_for_status()
                    if self.looks_like_pdb(pdb_response.text):
                        return pdb_url, pdb_response.text
        elif response.status_code not in {404, 400}:
            response.raise_for_status()

        for version in ALPHAFOLD_VERSIONS:
            url = ALPHAFOLD_PDB_URL.format(
                accession=uniprot_accession,
                version=version,
            )
            response = requests.get(url, timeout=timeout)
            if response.status_code == 200 and self.looks_like_pdb(response.text):
                return url, response.text
            if response.status_code not in {404, 400}:
                response.raise_for_status()
        return None, None

    def looks_like_pdb(self, text):
        return text.startswith(("HEADER", "MODEL", "ATOM")) or "\nATOM" in text[:5000]

    def write_report(self, report_path, rows):
        fieldnames = [
            "pesticidedb_protein_id",
            "uniprot_accession",
            "ncbi_protein_accession",
            "status",
            "source_url",
            "local_path",
        ]
        with report_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
