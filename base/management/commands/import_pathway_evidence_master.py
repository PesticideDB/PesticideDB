from __future__ import annotations

from pathlib import Path
import re

import pandas as pd
from django.core.management.base import BaseCommand

from base.models import (
    Compound,
    DegradationPathway,
    LiteratureReference,
    PathwayEvidence,
    Pesticide,
)


def clean(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


class Command(BaseCommand):
    help = "Import the final PesticideDB pathway evidence master file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default="data_files/pathway/PesticideDB_Pathway_Evidence_Master.xlsx",
            help="Path to the final pathway evidence master .xlsx or .csv file.",
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Replace previously imported pathway-evidence records generated from the final master.",
        )

    def handle(self, *args, **options):
        path = Path(options["file"])
        if not path.is_absolute():
            path = Path.cwd() / path
        if not path.exists():
            self.stderr.write(self.style.ERROR(f"File not found: {path}"))
            return

        if path.suffix.lower() == ".csv":
            df = pd.read_csv(path)
        else:
            df = pd.read_excel(path)

        if options["replace"]:
            imported = DegradationPathway.objects.filter(
                title__startswith="Literature evidence:"
            )
            count = imported.count()
            imported.delete()
            self.stdout.write(f"Removed {count} previously imported pathway evidence pathways.")

        created_pathways = 0
        created_references = 0
        created_evidence = 0

        for _, row in df.iterrows():
            pesticide = clean(row.get("pesticide"))
            title = clean(row.get("paper_title"))
            doi = clean(row.get("doi"))
            year_raw = clean(row.get("publication_year"))
            microorganism = clean(row.get("microorganism_or_strain"))
            evidence_category = clean(row.get("evidence_category"))
            context = clean(row.get("pesticide_specific_context"))
            source_pdf = clean(row.get("source_pdf"))

            if not pesticide or not title:
                continue

            try:
                year = int(year_raw) if year_raw else None
            except ValueError:
                year = None

            Compound.objects.get_or_create(
                name=pesticide,
                defaults={
                    "role": "PESTICIDE",
                    "description": f"Parent pesticide represented in PesticideDB pathway evidence records.",
                },
            )

            reference_lookup = {"doi": doi} if doi else {"title": title, "year": year}
            reference, reference_created = LiteratureReference.objects.get_or_create(
                **reference_lookup,
                defaults={
                    "title": title,
                    "year": year,
                    "notes": source_pdf,
                },
            )
            if reference_created:
                created_references += 1
            else:
                changed = False
                if title and not reference.title:
                    reference.title = title
                    changed = True
                if year and not reference.year:
                    reference.year = year
                    changed = True
                if source_pdf and not reference.notes:
                    reference.notes = source_pdf
                    changed = True
                if changed:
                    reference.save()

            pathway_title = f"Literature evidence: {title[:210]}"
            pathway, pathway_created = DegradationPathway.objects.get_or_create(
                pesticide=pesticide,
                title=pathway_title,
                defaults={
                    "microorganism": microorganism[:255],
                    "completeness": "PARTIAL",
                    "summary": context,
                    "doi": doi,
                    "reference": title,
                },
            )
            if pathway_created:
                created_pathways += 1
            pathway.references.add(reference)

            pesticide_record = (
                Pesticide.objects.filter(pesticide__iexact=pesticide, doi__iexact=doi).first()
                if doi
                else Pesticide.objects.filter(pesticide__iexact=pesticide).first()
            )

            evidence, evidence_created = PathwayEvidence.objects.get_or_create(
                pathway=pathway,
                reference=reference,
                pesticide_record=pesticide_record,
                defaults={
                    "evidence_type": evidence_category,
                    "directness": "DIRECT",
                    "confidence": "Curated literature evidence",
                    "method": "",
                    "summary": context,
                },
            )
            if evidence_created:
                created_evidence += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Imported pathway evidence master | "
                f"pathways_created={created_pathways}, "
                f"references_created={created_references}, "
                f"evidence_links_created={created_evidence}"
            )
        )
