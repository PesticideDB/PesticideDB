from __future__ import annotations

from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand

from base.models import (
    Compound,
    DegradationPathway,
    DegradationPathwayStep,
    LiteratureReference,
    PathwayEvidence,
)


def clean(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def evidence_type(value: str) -> str:
    allowed = {"PURIFIED_ENZYME", "GENETIC", "METABOLITE", "WHOLE_CELL", "PROPOSED"}
    cleaned = clean(value).upper()
    return cleaned if cleaned in allowed else "PROPOSED"


class Command(BaseCommand):
    help = "Import stepwise pesticide degradation pathway reactions from a curated master file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default="data_files/pathway/PesticideDB_Stepwise_Pathway_Master_Batch1.xlsx",
            help="Path to the stepwise pathway master .xlsx or .csv file.",
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Replace pathways whose names are present in the import file.",
        )

    def handle(self, *args, **options):
        path = Path(options["file"])
        if not path.is_absolute():
            path = Path.cwd() / path
        if not path.exists():
            self.stderr.write(self.style.ERROR(f"File not found: {path}"))
            return

        df = pd.read_csv(path) if path.suffix.lower() == ".csv" else pd.read_excel(path)
        pathway_names = sorted({clean(v) for v in df["pathway_name"].dropna() if clean(v)})

        if options["replace"] and pathway_names:
            deleted_count = 0
            for name in pathway_names:
                qs = DegradationPathway.objects.filter(title=name)
                deleted_count += qs.count()
                qs.delete()
            self.stdout.write(f"Removed {deleted_count} previously imported stepwise pathways.")

        pathways_created = 0
        steps_created = 0
        evidence_links_created = 0
        references_created = 0

        for _, row in df.iterrows():
            pesticide = clean(row.get("pesticide"))
            pathway_name = clean(row.get("pathway_name"))
            microorganism = clean(row.get("microorganism"))
            completeness = clean(row.get("completeness")).upper() or "PARTIAL"
            step_order = int(row.get("step_order"))
            substrate = clean(row.get("substrate"))
            product = clean(row.get("product"))
            enzyme = clean(row.get("enzyme"))
            gene = clean(row.get("gene"))
            doi = clean(row.get("doi"))
            reference_title = clean(row.get("reference_title"))
            source_pdf = clean(row.get("source_pdf"))
            note = clean(row.get("evidence_note"))
            etype = evidence_type(row.get("evidence_type"))

            if not pesticide or not pathway_name or not substrate or not product:
                continue

            substrate_compound, _ = Compound.objects.get_or_create(
                name=substrate,
                defaults={"role": "PESTICIDE" if substrate.casefold() == pesticide.casefold() else "METABOLITE"},
            )
            product_compound, _ = Compound.objects.get_or_create(
                name=product,
                defaults={"role": "METABOLITE"},
            )

            reference_lookup = {"doi": doi} if doi else {"title": reference_title}
            reference, reference_created = LiteratureReference.objects.get_or_create(
                **reference_lookup,
                defaults={"title": reference_title, "notes": source_pdf},
            )
            if reference_created:
                references_created += 1

            pathway, pathway_created = DegradationPathway.objects.get_or_create(
                pesticide=pesticide,
                title=pathway_name,
                defaults={
                    "microorganism": microorganism,
                    "completeness": completeness if completeness in {"COMPLETE", "PARTIAL", "PROPOSED"} else "PARTIAL",
                    "summary": f"Stepwise pathway imported from curated batch file. {note}",
                    "doi": doi,
                    "reference": reference_title,
                },
            )
            pathway.references.add(reference)
            if pathway_created:
                pathways_created += 1

            step, step_created = DegradationPathwayStep.objects.get_or_create(
                pathway=pathway,
                step_order=step_order,
                defaults={
                    "substrate": substrate,
                    "substrate_compound": substrate_compound,
                    "product": product,
                    "product_compound": product_compound,
                    "gene": gene,
                    "enzyme": enzyme,
                    "microorganism": microorganism,
                    "evidence_type": etype,
                    "doi": doi,
                    "notes": note,
                },
            )
            step.references.add(reference)
            if step_created:
                steps_created += 1

            _, evidence_created = PathwayEvidence.objects.get_or_create(
                pathway=pathway,
                step=step,
                reference=reference,
                defaults={
                    "evidence_type": etype,
                    "directness": "DIRECT" if etype != "PROPOSED" else "PROPOSED",
                    "confidence": "Stepwise curated pathway batch",
                    "method": clean(row.get("reaction_label")),
                    "summary": note,
                },
            )
            if evidence_created:
                evidence_links_created += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Imported stepwise pathway master | "
                f"pathways_created={pathways_created}, "
                f"steps_created={steps_created}, "
                f"references_created={references_created}, "
                f"evidence_links_created={evidence_links_created}"
            )
        )
