from pathlib import Path

import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from base.models import ProteinRecord


class Command(BaseCommand):
    help = "Standardize PesticideDB protein IDs to the PDBP prefix and keep old IDs as aliases."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        proteins = list(
            ProteinRecord.objects
            .filter(pesticidedb_protein_id__startswith="PBDBP")
            .order_by("pesticidedb_protein_id", "id")
        )

        existing_numbers = []
        existing_ids = set()
        for protein_id in ProteinRecord.objects.values_list("pesticidedb_protein_id", flat=True):
            if not protein_id:
                continue
            existing_ids.add(protein_id)
            if protein_id.startswith("PDBP") and protein_id[4:].isdigit():
                existing_numbers.append(int(protein_id[4:]))

        next_number = max(existing_numbers or [0]) + 1
        mapping = {}
        for protein in proteins:
            old_id = protein.pesticidedb_protein_id
            while True:
                new_id = f"PDBP{next_number:04d}"
                next_number += 1
                if new_id not in existing_ids and new_id not in mapping.values():
                    break
            mapping[old_id] = new_id

        for protein in ProteinRecord.objects.exclude(pbdb_protein_id__isnull=True).exclude(pbdb_protein_id=""):
            if protein.pbdb_protein_id.startswith("PBDBP") and protein.pesticidedb_protein_id:
                mapping.setdefault(protein.pbdb_protein_id, protein.pesticidedb_protein_id)

        if not proteins and not mapping:
            updated_tables = self.update_metadata_tables({})
            self.stdout.write(
                self.style.SUCCESS(
                    f"No PBDBP protein IDs need standardization. Updated metadata/result files: {updated_tables}."
                )
            )
            return

        self.stdout.write(f"Standardizing {len(proteins)} current protein ID(s).")
        for old_id, new_id in mapping.items():
            self.stdout.write(f"  {old_id} -> {new_id}")

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run only; no changes written."))
            return

        with transaction.atomic():
            for protein in proteins:
                old_id = protein.pesticidedb_protein_id
                protein.pesticidedb_protein_id = mapping[old_id]
                if not protein.pbdb_protein_id:
                    protein.pbdb_protein_id = old_id
                protein.save(update_fields=["pesticidedb_protein_id", "pbdb_protein_id", "updated"])

        renamed_files = self.rename_structure_files(mapping)
        updated_tables = self.update_metadata_tables(mapping)

        self.stdout.write(
            self.style.SUCCESS(
                f"Protein ID standardization complete. Updated records: {len(proteins)}. "
                f"Renamed structure files: {renamed_files}. Updated metadata/result files: {updated_tables}."
            )
        )

    def rename_structure_files(self, mapping):
        renamed = 0
        structure_root = settings.MEDIA_ROOT / "protein_structures"
        for subdir, extension in [("pdb", ".pdb"), ("images", ".svg"), ("images", ".png")]:
            folder = structure_root / subdir
            if not folder.exists():
                continue
            for old_id, new_id in mapping.items():
                old_path = folder / f"{old_id}{extension}"
                new_path = folder / f"{new_id}{extension}"
                if old_path.exists():
                    if new_path.exists():
                        new_path.unlink()
                    old_path.rename(new_path)
                    renamed += 1
        return renamed

    def update_metadata_tables(self, mapping):
        updated = 0
        candidates = [
            Path("PBDB_annotation/data/PBDB_master_with_ids.xlsx"),
            Path("PBDB_annotation/data/PBDB_master.xlsx"),
            Path("PBDB_annotation/results/final_annotation.csv"),
            Path("PBDB_annotation/results/final_annotation_with_hmmer.csv"),
            settings.MEDIA_ROOT / "protein_structures" / "metadata" / "alphafold_download_report.csv",
        ]
        candidates.extend(settings.MEDIA_ROOT.glob("annotation_jobs/*/*_annotation_results.csv"))
        candidates.extend(settings.MEDIA_ROOT.glob("genome_jobs/*/*_genome_annotation_results.csv"))

        for path in candidates:
            if not path.exists() or path.name.startswith("~$"):
                continue
            suffix = path.suffix.lower()
            try:
                if suffix == ".xlsx":
                    if self.update_excel_file(path, mapping):
                        updated += 1
                elif suffix == ".csv":
                    if self.update_csv_file(path, mapping):
                        updated += 1
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"Could not update {path}: {exc}"))

        return updated

    def update_excel_file(self, path, mapping):
        df = pd.read_excel(path)
        changed = self.replace_dataframe_values(df, mapping)
        changed = self.sync_ids_by_accession(df) or changed
        if changed:
            df.to_excel(path, index=False)
        return changed

    def update_csv_file(self, path, mapping):
        df = pd.read_csv(path, dtype=str)
        changed = self.replace_dataframe_values(df, mapping)
        changed = self.sync_ids_by_accession(df) or changed
        if changed:
            df.to_csv(path, index=False)
        return changed

    def replace_dataframe_values(self, df, mapping):
        changed = False
        for column in df.columns:
            if df[column].dtype != object and column != "pesticidedb_protein_id":
                continue
            df[column] = df[column].astype(object)
            replaced = df[column].apply(
                lambda value: mapping.get(value, value) if isinstance(value, str) else value
            )
            for old_id, new_id in mapping.items():
                replaced = replaced.apply(
                    lambda value: value.replace(old_id, new_id)
                    if isinstance(value, str) and old_id in value else value
                )
            if not replaced.equals(df[column]):
                df[column] = replaced
                changed = True
        return changed

    def sync_ids_by_accession(self, df):
        if (
            "pesticidedb_protein_id" not in df.columns
            or ("ncbi_protein_accession" not in df.columns and "ncbi_accession" not in df.columns)
        ):
            return False

        df["pesticidedb_protein_id"] = df["pesticidedb_protein_id"].astype(object)
        accession_lookup = self.build_unique_accession_lookup()
        changed = False
        for index, row in df.iterrows():
            accession = self.clean_accession(row.get("ncbi_protein_accession"))
            if not accession:
                accession = self.clean_accession(row.get("ncbi_accession"))
            if not accession:
                continue
            protein_id = accession_lookup.get(accession.lower())
            if not protein_id:
                protein_id = accession_lookup.get(accession.split(".")[0].lower())
            if protein_id and row.get("pesticidedb_protein_id") != protein_id:
                df.at[index, "pesticidedb_protein_id"] = protein_id
                changed = True
        return changed

    def build_unique_accession_lookup(self):
        candidates = {}
        duplicate_keys = set()
        for protein in ProteinRecord.objects.all():
            accession = self.clean_accession(protein.ncbi_protein_accession)
            if not accession or not protein.pesticidedb_protein_id:
                continue
            for key in {accession.lower(), accession.split(".")[0].lower()}:
                if key in candidates and candidates[key] != protein.pesticidedb_protein_id:
                    duplicate_keys.add(key)
                else:
                    candidates[key] = protein.pesticidedb_protein_id

        for key in duplicate_keys:
            candidates.pop(key, None)
        return candidates

    def clean_accession(self, value):
        text = str(value or "").strip()
        if not text or text.lower() in {"nan", "none", "not available", "n/a", "-"}:
            return ""
        return text
