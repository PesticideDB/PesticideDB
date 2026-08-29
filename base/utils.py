import csv
import re

from django.conf import settings
from django.db.models.functions import Lower

from base.models import (
    DegradationPathway,
    DegradationPathwayStep,
    LiteratureReference,
    NoEvidencePesticide,
    PathwayEvidence,
    Pesticide,
    ProteinRecord,
)


DATABASE_VERSION = "1.0"
DATABASE_RELEASE_DATE = "July 21, 2026"
DATABASE_LAST_UPDATE = "July 21, 2026"


def clean_pesticide_name(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def canonical_pesticide_names():
    """Return one case-insensitive, whitespace-normalized name per evidenced pesticide."""
    names = {}
    values = (
        Pesticide.objects
        .exclude(pesticide__isnull=True)
        .exclude(pesticide="")
        .values_list("pesticide", flat=True)
    )
    for value in values:
        cleaned = clean_pesticide_name(value)
        key = cleaned.casefold()
        if cleaned and key not in names:
            names[key] = cleaned
    return sorted(names.values(), key=str.casefold)


def curated_pathway_pesticide_names():
    """Return pesticide groups that are eligible for curated pathway maps."""
    curated_path = (
        settings.BASE_DIR
        / "curation_outputs"
        / "pathway_evidence_curated_20260625"
        / "curated_biodegradation_evidence_all_pesticides.csv"
    )
    names = {}
    if curated_path.exists():
        with curated_path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                cleaned = clean_pesticide_name(row.get("canonical_pesticide"))
                key = cleaned.casefold()
                if cleaned and key not in names:
                    names[key] = cleaned
    else:
        values = (
            DegradationPathway.objects
            .exclude(pesticide__isnull=True)
            .exclude(pesticide="")
            .values_list("pesticide", flat=True)
        )
        for value in values:
            cleaned = clean_pesticide_name(value)
            key = cleaned.casefold()
            if cleaned and key not in names:
                names[key] = cleaned
    return sorted(names.values(), key=str.casefold)


def supplemental_dataset_summary():
    discovery_path = (
        settings.BASE_DIR
        / "curation_outputs"
        / "supplemented_discovery_candidates_179_clean.csv"
    )
    evidence_path = (
        settings.BASE_DIR
        / "curation_outputs"
        / "supplemented_validated_protein_evidence_15_clean.csv"
    )

    evidence_rows = 0
    discovery_counts = {
        "Gene Only": 0,
        "Gene Only + whole-cell/ Crude": 0,
        "Whole-cell / Crude": 0,
    }

    if evidence_path.exists():
        with evidence_path.open(newline="", encoding="utf-8") as handle:
            evidence_rows = sum(1 for _ in csv.DictReader(handle))

    if discovery_path.exists():
        with discovery_path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                evidence_type = (row.get("evidence_type") or "").strip()
                if evidence_type in discovery_counts:
                    discovery_counts[evidence_type] += 1

    curated_proteins = ProteinRecord.objects.filter(collection_category="CURATED").count()
    supplemented_proteins = ProteinRecord.objects.filter(collection_category="SUPPLEMENTED").count()

    return {
        "curated_protein_count": curated_proteins,
        "supplemented_protein_count": supplemented_proteins,
        "validated_supplemental_evidence_rows": evidence_rows,
        "discovery_candidate_count": sum(discovery_counts.values()),
        "gene_only_candidate_count": discovery_counts["Gene Only"],
        "gene_whole_cell_candidate_count": discovery_counts["Gene Only + whole-cell/ Crude"],
        "whole_cell_candidate_count": discovery_counts["Whole-cell / Crude"],
    }


def pesticide_counts():
    """
    Returns correct pesticide statistics:
    - with experimental evidence
    - with no experimental evidence
    - total unique pesticides (union, no double counting)
    """

    with_evidence = set(
        Pesticide.objects
        .exclude(pesticide="")
        .exclude(pesticide__isnull=True)
        .annotate(p=Lower("pesticide"))
        .values_list("p", flat=True)
    )

    no_evidence_raw = set(
        NoEvidencePesticide.objects
        .exclude(pesticide="")
        .exclude(pesticide__isnull=True)
        .annotate(p=Lower("pesticide"))
        .values_list("p", flat=True)
    )
    no_evidence = no_evidence_raw - with_evidence

    return {
        "with_evidence": len(with_evidence),
        "no_evidence": len(no_evidence),
        "total": len(with_evidence | no_evidence_raw),
    }


def microorganism_count():
    """
    Count unique microorganisms, not pesticide-microorganism pairs.
    """
    return (
        Pesticide.objects
        .exclude(microorganism="")
        .exclude(microorganism__isnull=True)
        .exclude(microorganism__iexact="not specified")
        .annotate(m=Lower("microorganism"))
        .values("m")
        .distinct()
        .count()
    )


def microorganism_record_count():
    """
    Count reported microorganism records, including repeated microorganism labels.
    """
    return (
        Pesticide.objects
        .exclude(microorganism="")
        .exclude(microorganism__isnull=True)
        .exclude(microorganism__iexact="not specified")
        .count()
    )


def structure_file_count():
    structure_dir = settings.MEDIA_ROOT / "protein_structures" / "pdb"
    if not structure_dir.exists():
        return 0
    return sum(1 for _ in structure_dir.glob("*.pdb"))


def curated_publication_count():
    """
    Count distinct curated publication labels in the biodegradation evidence table.
    This is the publication-level denominator used by the evidence-profile figures.
    """
    return (
        Pesticide.objects
        .exclude(reference__isnull=True)
        .exclude(reference="")
        .annotate(r=Lower("reference"))
        .values("r")
        .distinct()
        .count()
    )


def reference_count():
    references = set()

    for value in (
        Pesticide.objects
        .exclude(doi__isnull=True)
        .exclude(doi="")
        .values_list("doi", flat=True)
    ):
        references.add(value.strip().lower())

    for value in (
        Pesticide.objects
        .exclude(reference__isnull=True)
        .exclude(reference="")
        .values_list("reference", flat=True)
    ):
        references.add(value.strip().lower())

    for value in (
        ProteinRecord.objects
        .exclude(doi__isnull=True)
        .exclude(doi="")
        .values_list("doi", flat=True)
    ):
        references.add(value.strip().lower())

    for value in (
        LiteratureReference.objects
        .exclude(doi__isnull=True)
        .exclude(doi="")
        .values_list("doi", flat=True)
    ):
        references.add(value.strip().lower())

    return len({reference for reference in references if reference and reference != "nan"})


def pathway_summary():
    return {
        "pathway_evidence_count": PathwayEvidence.objects.count(),
        "pathway_record_count": DegradationPathway.objects.count(),
        "pathway_step_count": DegradationPathwayStep.objects.count(),
        "pathway_pesticide_count": (
            DegradationPathway.objects
            .exclude(pesticide="")
            .exclude(pesticide__isnull=True)
            .annotate(p=Lower("pesticide"))
            .values("p")
            .distinct()
            .count()
        ),
    }


def database_summary():
    return {
        "database_version": DATABASE_VERSION,
        "release_date": DATABASE_RELEASE_DATE,
        "last_update_date": DATABASE_LAST_UPDATE,
        "structure_count": structure_file_count(),
        "curated_publication_count": curated_publication_count(),
        "reference_count": reference_count(),
        **pathway_summary(),
        **supplemental_dataset_summary(),
    }
