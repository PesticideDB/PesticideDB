from django.core.management.base import BaseCommand
from base.models import ProteinRecord
import pandas as pd


class Command(BaseCommand):
    help = "Import ProteinRecord data from Excel"

    def add_arguments(self, parser):
        parser.add_argument("--file", type=str, required=True)
        parser.add_argument("--wipe", action="store_true")

    def handle(self, *args, **options):
        file_path = options["file"]
        wipe = options["wipe"]

        # ✅ WIPE existing data
        if wipe:
            ProteinRecord.objects.all().delete()
            self.stdout.write(
                self.style.WARNING("Deleted all existing ProteinRecord rows.")
            )

        # Load Excel
        df = pd.read_excel(file_path)

        # Helper: convert NaN -> "" and strip strings
        def clean(x):
            if pd.isna(x):
                return ""
            return str(x).strip()

        # Only allow real model fields
        allowed_fields = {f.name for f in ProteinRecord._meta.fields}

        created = 0
        updated = 0

        for i, (_, row) in enumerate(df.iterrows(), start=1):
            # Accept the current PesticideDB ID column and the older PBDB column.
            excel_id = clean(row.get("pesticidedb_protein_id", "")) or clean(row.get("pbdb_protein_id", ""))
            ncbi_accession = clean(row.get("ncbi_protein_accession", ""))

            data = {
                "pesticidedb_protein_id": excel_id or None,

                "pesticide": clean(row.get("pesticide", "")) or None,
                "microorganism": clean(row.get("microorganism", "")) or None,
                "evidence_type": clean(row.get("evidence_type", "")) or None,
                "collection_category": clean(row.get("collection_category", "")) or "CURATED",
                "enzyme_class": clean(row.get("enzyme_class", "")) or None,
                "reported_protein_name": clean(row.get("reported_protein_name", "")) or None,
                "gene_name": clean(row.get("gene_name", "")) or None,
                "doi": clean(row.get("doi", "")) or None,
                "ncbi_protein_accession": ncbi_accession or None,
                "uniprot_accession": clean(row.get("uniprot_accession", "")) or None,
                "sequence_available": clean(row.get("sequence_available", "")) or None,
            }

            # Year handling
            year_val = row.get("year", None)
            if not pd.isna(year_val) and str(year_val).strip() != "":
                try:
                    data["year"] = int(year_val)
                except Exception:
                    data["year"] = None
            else:
                data["year"] = None

            # Remove any fields not in model
            data = {k: v for k, v in data.items() if k in allowed_fields}

            protein = None
            if excel_id:
                protein = ProteinRecord.objects.filter(pesticidedb_protein_id=excel_id).first()
            if protein is None and ncbi_accession:
                protein = (
                    ProteinRecord.objects
                    .filter(ncbi_protein_accession__iexact=ncbi_accession)
                    .first()
                )

            if protein is None:
                ProteinRecord.objects.create(**data)
                created += 1
            else:
                if protein.pesticidedb_protein_id:
                    data.pop("pesticidedb_protein_id", None)
                for field, value in data.items():
                    setattr(protein, field, value)
                protein.save()
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported ProteinRecord rows successfully. Created: {created}. Updated: {updated}."
            )
        )
