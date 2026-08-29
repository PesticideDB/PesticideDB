from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand, CommandError

from base.models import ProteinRecord


ALLOWED_EVIDENCE = {
    "Purified (Activity)",
    "Purified (Kinetics)",
    "Recombinant (Activity)",
}

EVIDENCE_RANK = {
    "Purified (Kinetics)": 3,
    "Purified (Activity)": 2,
    "Recombinant (Activity)": 1,
}


def clean(value):
    if pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def read_fasta(path):
    sequences = {}
    current_accession = None
    chunks = []

    def store():
        if current_accession and chunks:
            sequences[current_accession] = "".join(chunks)

    for line in Path(path).read_text(errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(">"):
            store()
            current_accession = line[1:].split("|", 1)[0].split()[0]
            chunks = []
        else:
            chunks.append(line)
    store()
    return sequences


class Command(BaseCommand):
    help = (
        "Import validated supplemental protein records without modifying the master workbook. "
        "Only purified/recombinant protein evidence is accepted."
    )

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="CSV or XLSX file with validated supplemental rows.")
        parser.add_argument("--fasta", required=True, help="FASTA keyed by UniProt accession.")

    def handle(self, *args, **options):
        source_path = Path(options["file"])
        fasta_path = Path(options["fasta"])
        if not source_path.exists():
            raise CommandError(f"Supplemental file not found: {source_path}")
        if not fasta_path.exists():
            raise CommandError(f"Supplemental FASTA not found: {fasta_path}")

        if source_path.suffix.lower() == ".csv":
            df = pd.read_csv(source_path)
        else:
            df = pd.read_excel(source_path, sheet_name="Candidates")
        df = df.fillna("")

        invalid = sorted(set(df["evidence_type"]) - ALLOWED_EVIDENCE)
        if invalid:
            raise CommandError(
                "File contains evidence types not allowed in the validated protein library: "
                + ", ".join(invalid)
            )

        df["evidence_rank"] = df["evidence_type"].map(EVIDENCE_RANK).fillna(0)
        df["has_ncbi"] = df["ncbi_protein_accession"].map(lambda value: bool(clean(value)))
        df = (
            df.sort_values(
                ["uniprot_accession", "evidence_rank", "has_ncbi"],
                ascending=[True, False, False],
            )
            .drop_duplicates("uniprot_accession")
        )

        sequences = read_fasta(fasta_path)
        created = 0
        updated = 0
        skipped = 0

        for _, row in df.iterrows():
            uniprot = clean(row.get("uniprot_accession"))
            ncbi = clean(row.get("ncbi_protein_accession"))
            sequence = sequences.get(uniprot, "")
            if not uniprot or not sequence:
                self.stderr.write(
                    self.style.WARNING(
                        f"Skipped row without UniProt accession or sequence: {uniprot or ncbi or 'unknown'}"
                    )
                )
                skipped += 1
                continue

            protein = ProteinRecord.objects.filter(uniprot_accession__iexact=uniprot).first()
            if protein is None and ncbi:
                protein = ProteinRecord.objects.filter(ncbi_protein_accession__iexact=ncbi).first()

            if protein is not None and protein.collection_category == "CURATED":
                self.stdout.write(
                    self.style.WARNING(
                        f"Preserved existing CURATED record {protein.pesticidedb_protein_id} "
                        f"for {uniprot}; no supplemental duplicate created."
                    )
                )
                skipped += 1
                continue

            data = {
                "pesticide": clean(row.get("pesticide")) or None,
                "microorganism": clean(row.get("microorganism")) or None,
                "evidence_type": clean(row.get("evidence_type")) or None,
                "collection_category": "SUPPLEMENTED",
                "enzyme_class": clean(row.get("enzyme_class")) or None,
                "reported_protein_name": clean(row.get("reported_protein_name")) or None,
                "gene_name": clean(row.get("gene_name")) or None,
                "doi": clean(row.get("doi")) or None,
                "ncbi_protein_accession": ncbi or None,
                "uniprot_accession": uniprot,
                "fasta_sequence": sequence,
                "sequence_available": "Yes",
            }

            year = clean(row.get("year"))
            try:
                data["year"] = int(float(year)) if year else None
            except ValueError:
                data["year"] = None

            if protein is None:
                ProteinRecord.objects.create(**data)
                created += 1
            else:
                for field, value in data.items():
                    setattr(protein, field, value)
                protein.save()
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Validated supplemental import complete. Created: {created}; "
                f"updated: {updated}; skipped: {skipped}. Master workbook unchanged."
            )
        )
