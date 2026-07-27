from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import django
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "PepDatabase.settings")
django.setup()

from base.models import NoEvidencePesticide, Pesticide, ProteinRecord  # noqa: E402


CORE_DIR = PROJECT_ROOT / "data_files" / "core"
PROTEIN_DIR = PROJECT_ROOT / "data_files" / "protein"
ORIGINAL_EVIDENCE = CORE_DIR / "pesticide_data.xlsx"
RECENT_EVIDENCE = CORE_DIR / "additional_2025-2026-search.xlsx"
EXISTING_CURATED_EVIDENCE = CORE_DIR / "additional_existing_curated_evidence.xlsx"
NO_EVIDENCE = CORE_DIR / "no_evidence_pesticide.xlsx"
COMBINED_EVIDENCE_XLSX = CORE_DIR / "pesticide_data_with_2025_2026.xlsx"
COMBINED_EVIDENCE_CSV = CORE_DIR / "pesticide_data_with_2025_2026.csv"
CURRENT_EVIDENCE_CSV = CORE_DIR / "pesticide_data.csv"
RECENT_PROTEIN_XLSX = PROTEIN_DIR / "PBDB_Protein_Gene_Records_2025_2026_Additions.xlsx"
RECENT_PROTEIN_CSV = PROTEIN_DIR / "PBDB_Protein_Gene_Records_2025_2026_Additions.csv"
COMBINED_PROTEIN_XLSX = PROTEIN_DIR / "PBDB_Proteins_Master_With_2025_2026.xlsx"
COMBINED_PROTEIN_CSV = PROTEIN_DIR / "PBDB_Proteins_Master_With_2025_2026.csv"
STRUCTURE_CURATION_XLSX = PROTEIN_DIR / "PBDB_Protein_Structure_Curation_2025_2026.xlsx"
STRUCTURE_CURATION_CSV = PROTEIN_DIR / "PBDB_Protein_Structure_Curation_2025_2026.csv"

NO_EVIDENCE_PROMOTED_TO_EVIDENCE = {"ethiprole", "spinetoram"}
KNOWN_RECENT_PROTEIN_ACCESSIONS = {
    (
        "lindane",
        "sphingobium japonicum ut26 lina expressed in arabidopsis",
        "lina",
        "10.1111/1751-7915.70409",
    ): {
        "uniprot_accession": "P51697",
        "sequence_available": "Yes",
    },
}
CORE_COLUMNS = [
    "Microorganism",
    "Culture_type",
    "Pesticide",
    "Evidence",
    "Isolation_environment",
    "Isolation_Location",
    "Publication_Year",
    "Enzyme",
    "Enzyme_name_reported",
    "Gene",
    "Reference",
    "Metabolite_or_product",
]
PROTEIN_COLUMNS = [
    "pesticide",
    "microorganism",
    "evidence_type",
    "enzyme_class",
    "reported_protein_name",
    "pesticidedb_protein_id",
    "gene_name",
    "ncbi_protein_accession",
    "year",
    "doi",
    "uniprot_accession",
    "sequence_available",
    "collection_category",
    "annotation_basis",
]
PUBLIC_PROTEIN_COLUMNS = [
    "pesticidedb_protein_id",
    "reported_protein_name",
    "pesticide",
    "microorganism",
    "evidence_type",
    "collection_category",
    "enzyme_class",
    "gene_name",
    "ncbi_protein_accession",
    "uniprot_accession",
    "year",
    "doi",
]


def clean(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def canonical(value) -> str:
    return clean(value).casefold()


def read_evidence(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path).fillna("")
    df.columns = [clean(column) for column in df.columns]
    if "Culture_type" not in df.columns:
        df["Culture_type"] = ""
    if "Metabolite_or_product" not in df.columns:
        df["Metabolite_or_product"] = ""
    missing = [column for column in CORE_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"{path} is missing required columns: {', '.join(missing)}")
    df = df[CORE_COLUMNS].copy()
    for column in CORE_COLUMNS:
        df[column] = df[column].map(clean)
    df = df[df["Pesticide"] != ""]
    return df


def write_table(df: pd.DataFrame, xlsx_path: Path, csv_path: Path, sheet_name: str) -> None:
    xlsx_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(xlsx_path, index=False, sheet_name=sheet_name)
    df.to_csv(csv_path, index=False)


def row_key(row: pd.Series, columns: list[str]) -> tuple[str, ...]:
    return tuple(canonical(row[column]) for column in columns)


def build_combined_evidence() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    original = read_evidence(ORIGINAL_EVIDENCE)
    recent_all = read_evidence(RECENT_EVIDENCE)
    existing_curated = read_evidence(EXISTING_CURATED_EVIDENCE) if EXISTING_CURATED_EVIDENCE.exists() else pd.DataFrame(columns=CORE_COLUMNS)

    original_keys = {
        row_key(row, ["Microorganism", "Pesticide", "Reference"])
        for _, row in original.iterrows()
    }
    existing_curated = existing_curated[
        ~existing_curated.apply(
            lambda row: row_key(row, ["Microorganism", "Pesticide", "Reference"]) in original_keys,
            axis=1,
        )
    ].copy()
    existing_curated_keys = {
        row_key(row, ["Microorganism", "Pesticide", "Reference"])
        for _, row in existing_curated.iterrows()
    }
    recent_new = recent_all[
        ~recent_all.apply(
            lambda row: row_key(row, ["Microorganism", "Pesticide", "Reference"])
            in original_keys | existing_curated_keys,
            axis=1,
        )
    ].copy()
    recent_new["source_dataset"] = "additional_2025-2026-search.xlsx"

    original_for_combined = original.copy()
    if "source_dataset" not in original_for_combined.columns:
        original_for_combined["source_dataset"] = "pesticide_data.xlsx"
    existing_curated_for_combined = existing_curated.copy()
    existing_curated_for_combined["source_dataset"] = EXISTING_CURATED_EVIDENCE.name
    combined = pd.concat(
        [original_for_combined, existing_curated_for_combined, recent_new],
        ignore_index=True,
    )
    return original, recent_all, combined


def refresh_no_evidence() -> int:
    no_evidence = pd.read_excel(NO_EVIDENCE).fillna("")
    no_evidence.columns = [clean(column) for column in no_evidence.columns]
    pesticide_column = next(
        (column for column in no_evidence.columns if column.casefold() == "pesticide"),
        None,
    )
    if pesticide_column is None:
        raise ValueError(f"{NO_EVIDENCE} is missing a Pesticide column.")

    before = len(no_evidence)
    no_evidence[pesticide_column] = no_evidence[pesticide_column].map(clean)
    no_evidence = no_evidence[
        ~no_evidence[pesticide_column].map(canonical).isin(NO_EVIDENCE_PROMOTED_TO_EVIDENCE)
    ].copy()
    no_evidence = no_evidence[no_evidence[pesticide_column] != ""]
    no_evidence = no_evidence.drop_duplicates(subset=[pesticide_column], keep="first")
    no_evidence.to_excel(NO_EVIDENCE, index=False)

    NoEvidencePesticide.objects.filter(
        pesticide__iregex=r"^(ethiprole|spinetoram)\s*$"
    ).delete()

    existing_no = {
        canonical(value)
        for value in NoEvidencePesticide.objects.values_list("pesticide", flat=True)
    }
    created = 0
    for pesticide in no_evidence[pesticide_column]:
        if canonical(pesticide) not in existing_no:
            NoEvidencePesticide.objects.create(
                pesticide=pesticide,
                evidence_of_biodegradation="No experimental biodegradation evidence found",
            )
            existing_no.add(canonical(pesticide))
            created += 1
    return before - len(no_evidence)


def import_recent_biodegradation(recent: pd.DataFrame) -> int:
    existing_keys = {
        (
            canonical(row[0]),
            canonical(row[1]),
            canonical(row[2]),
        )
        for row in Pesticide.objects.values_list("microorganism", "pesticide", "reference")
    }
    created = 0
    for _, row in recent.iterrows():
        key = (
            canonical(row["Microorganism"]),
            canonical(row["Pesticide"]),
            canonical(row["Reference"]),
        )
        if key in existing_keys:
            continue
        year = clean(row["Publication_Year"])
        Pesticide.objects.create(
            pesticide=clean(row["Pesticide"]),
            microorganism=clean(row["Microorganism"]),
            culture_type=clean(row["Culture_type"]) or "Individual strain",
            evidence_by_microbe=clean(row["Evidence"]),
            isolation_environment=clean(row["Isolation_environment"]),
            isolation_location=clean(row["Isolation_Location"]),
            publication_year=int(float(year)) if year else None,
            enzyme=clean(row["Enzyme"]),
            enzyme_name_reported=clean(row["Enzyme_name_reported"]),
            gene=clean(row["Gene"]),
            reference=clean(row["Reference"]),
            metabolite_or_product=clean(row["Metabolite_or_product"]) or None,
            doi=clean(row["Reference"]) if clean(row["Reference"]).startswith("10.") else None,
        )
        existing_keys.add(key)
        created += 1
    return created


def build_recent_protein_rows(recent: pd.DataFrame) -> pd.DataFrame:
    candidates = recent[
        recent["Gene"].map(clean).ne("")
        | recent["Enzyme_name_reported"].map(clean).ne("")
        | recent["Enzyme"].map(clean).ne("")
    ].copy()

    rows = []
    for _, row in candidates.iterrows():
        enzyme = clean(row["Enzyme"])
        enzyme_class = "" if enzyme.casefold() in {"yes", "multiple"} else enzyme
        protein_row = {
            "pesticide": clean(row["Pesticide"]),
            "microorganism": clean(row["Microorganism"]),
            "evidence_type": clean(row["Evidence"]),
            "enzyme_class": enzyme_class,
            "reported_protein_name": clean(row["Enzyme_name_reported"]) or enzyme_class,
            "pesticidedb_protein_id": "",
            "gene_name": clean(row["Gene"]),
            "ncbi_protein_accession": "",
            "year": int(float(clean(row["Publication_Year"]))) if clean(row["Publication_Year"]) else "",
            "doi": clean(row["Reference"]),
            "uniprot_accession": "",
            "sequence_available": "No",
            "collection_category": "CURATED",
            "annotation_basis": "additional_2025-2026-search.xlsx",
        }
        known = KNOWN_RECENT_PROTEIN_ACCESSIONS.get(
            (
                canonical(protein_row["pesticide"]),
                canonical(protein_row["microorganism"]),
                canonical(protein_row["gene_name"]),
                canonical(protein_row["doi"]),
            )
        )
        if known:
            protein_row.update(known)
        rows.append(protein_row)
    df = pd.DataFrame(rows, columns=PROTEIN_COLUMNS)
    df = df.drop_duplicates(
        subset=["pesticide", "microorganism", "gene_name", "reported_protein_name", "doi"],
        keep="first",
    )
    return df


def import_recent_proteins(recent_proteins: pd.DataFrame) -> int:
    existing_keys = {
        (
            canonical(row[0]),
            canonical(row[1]),
            canonical(row[2]),
            canonical(row[3]),
            canonical(row[4]),
        )
        for row in ProteinRecord.objects.values_list(
            "pesticide", "microorganism", "gene_name", "reported_protein_name", "doi"
        )
    }
    created = 0
    for _, row in recent_proteins.iterrows():
        key = (
            canonical(row["pesticide"]),
            canonical(row["microorganism"]),
            canonical(row["gene_name"]),
            canonical(row["reported_protein_name"]),
            canonical(row["doi"]),
        )
        if key in existing_keys:
            ProteinRecord.objects.filter(
                pesticide__iexact=clean(row["pesticide"]),
                microorganism__iexact=clean(row["microorganism"]),
                gene_name__iexact=clean(row["gene_name"]),
                reported_protein_name__iexact=clean(row["reported_protein_name"]),
                doi__iexact=clean(row["doi"]),
            ).update(
                uniprot_accession=clean(row["uniprot_accession"]) or None,
                sequence_available=clean(row["sequence_available"]) or "No",
            )
            continue
        ProteinRecord.objects.create(
            pesticide=clean(row["pesticide"]) or None,
            microorganism=clean(row["microorganism"]) or None,
            evidence_type=clean(row["evidence_type"]) or None,
            collection_category=clean(row["collection_category"]) or "CURATED",
            enzyme_class=clean(row["enzyme_class"]) or None,
            reported_protein_name=clean(row["reported_protein_name"]) or None,
            gene_name=clean(row["gene_name"]) or None,
            doi=clean(row["doi"]) or None,
            year=int(float(clean(row["year"]))) if clean(row["year"]) else None,
            uniprot_accession=clean(row["uniprot_accession"]) or None,
            sequence_available=clean(row["sequence_available"]) or "No",
            annotation_basis=clean(row["annotation_basis"]) or None,
        )
        existing_keys.add(key)
        created += 1
    return created


def build_combined_protein_workbook(recent_proteins: pd.DataFrame) -> pd.DataFrame:
    master = pd.read_excel(PROTEIN_DIR / "PBDB_Proteins_Master.xlsx").fillna("")
    for column in PROTEIN_COLUMNS:
        if column not in master.columns:
            master[column] = ""
    master = master[PROTEIN_COLUMNS].copy()
    combined = pd.concat([master, recent_proteins], ignore_index=True)
    combined = combined.drop_duplicates(
        subset=["pesticide", "microorganism", "gene_name", "reported_protein_name", "doi"],
        keep="last",
    )
    recent_ids = {
        (
            canonical(row[0]),
            canonical(row[1]),
            canonical(row[2]),
            canonical(row[3]),
            canonical(row[4]),
        ): row[5]
        for row in ProteinRecord.objects.filter(
            annotation_basis="additional_2025-2026-search.xlsx"
        ).values_list(
            "pesticide",
            "microorganism",
            "gene_name",
            "reported_protein_name",
            "doi",
            "pesticidedb_protein_id",
        )
    }
    for index, row in combined.iterrows():
        key = (
            canonical(row["pesticide"]),
            canonical(row["microorganism"]),
            canonical(row["gene_name"]),
            canonical(row["reported_protein_name"]),
            canonical(row["doi"]),
        )
        if key in recent_ids:
            combined.at[index, "pesticidedb_protein_id"] = recent_ids[key]
    return combined


def write_structure_curation_report() -> pd.DataFrame:
    rows = []
    recent_records = ProteinRecord.objects.filter(
        annotation_basis="additional_2025-2026-search.xlsx"
    ).order_by("pesticidedb_protein_id", "id")
    broad_terms = {
        "community",
        "metatranscriptomics",
        "functional genes",
        "functional genes identified",
        "functional genes profiled",
        "multiple",
        "unresolved",
        "not isolated",
        "enzyme activities reported",
        "intracellular enzymes",
        "ros implicated",
    }
    for record in recent_records:
        gene = clean(record.gene_name)
        protein_name = clean(record.reported_protein_name)
        uniprot = clean(record.uniprot_accession)
        ncbi = clean(record.ncbi_protein_accession)
        combined_text = f"{gene} {protein_name} {record.microorganism or ''}".casefold()
        has_broad_term = any(term in combined_text for term in broad_terms)
        if uniprot:
            status = "structure_ready"
            reason = "Reviewed UniProt accession curated for this record."
            next_step = "Download AlphaFold/RCSB model and regenerate preview/report."
        elif not gene or has_broad_term or ";" in gene:
            status = "not_structure_eligible_from_current_metadata"
            reason = "The row names a community, broad gene family, multiple genes, or unresolved enzyme rather than one accession-backed protein."
            next_step = "Return to the full text or sequence databases and split into single protein records only when a valid accession or sequence is available."
        else:
            status = "needs_accession_or_sequence_curation"
            reason = "A specific gene/protein is reported, but no public UniProt/NCBI accession or FASTA sequence has been curated yet."
            next_step = "Check the article supplement, GenBank/NCBI Protein, UniProt, or contact/source data for the exact accession or sequence."
        rows.append(
            {
                "pesticidedb_protein_id": record.pesticidedb_protein_id,
                "pesticide": record.pesticide,
                "microorganism": record.microorganism,
                "gene_name": gene,
                "reported_protein_name": protein_name,
                "doi": record.doi,
                "uniprot_accession": uniprot,
                "ncbi_protein_accession": ncbi,
                "structure_curation_status": status,
                "reason": reason,
                "recommended_next_step": next_step,
            }
        )
    report = pd.DataFrame(rows)
    write_table(report, STRUCTURE_CURATION_XLSX, STRUCTURE_CURATION_CSV, "structure curation")
    return report


def write_public_protein_master_from_database() -> pd.DataFrame:
    rows = list(
        ProteinRecord.objects.all()
        .order_by("pesticidedb_protein_id", "id")
        .values(*PUBLIC_PROTEIN_COLUMNS)
    )
    df = pd.DataFrame(rows, columns=PUBLIC_PROTEIN_COLUMNS).fillna("")
    write_table(
        df,
        PROTEIN_DIR / "PBDB_Proteins_Master.xlsx",
        PROTEIN_DIR / "PBDB_Proteins_Master.csv",
        "protein records",
    )
    return df


def main() -> None:
    _, recent, combined = build_combined_evidence()
    write_table(combined, COMBINED_EVIDENCE_XLSX, COMBINED_EVIDENCE_CSV, "with evidence")
    write_table(combined[CORE_COLUMNS], ORIGINAL_EVIDENCE, CURRENT_EVIDENCE_CSV, "yes evidence")

    removed_no_evidence = refresh_no_evidence()
    biodegradation_created = import_recent_biodegradation(recent)

    recent_proteins = build_recent_protein_rows(recent)
    write_table(recent_proteins, RECENT_PROTEIN_XLSX, RECENT_PROTEIN_CSV, "2025-2026 additions")

    protein_created = import_recent_proteins(recent_proteins)
    combined_proteins = build_combined_protein_workbook(recent_proteins)
    write_table(combined_proteins, COMBINED_PROTEIN_XLSX, COMBINED_PROTEIN_CSV, "protein records")
    public_protein_master = write_public_protein_master_from_database()
    structure_curation = write_structure_curation_report()

    print("2025-2026 refresh complete")
    print(f"recent_biodegradation_rows_available={len(recent)}")
    print(f"recent_biodegradation_rows_created={biodegradation_created}")
    print(f"promoted_removed_from_no_evidence={removed_no_evidence}")
    print(f"recent_protein_gene_candidate_rows={len(recent_proteins)}")
    print(f"recent_protein_records_created={protein_created}")
    print(f"combined_evidence_file={COMBINED_EVIDENCE_XLSX}")
    print(f"recent_protein_file={RECENT_PROTEIN_XLSX}")
    print(f"combined_protein_file={COMBINED_PROTEIN_XLSX}")
    print(f"public_protein_master_rows={len(public_protein_master)}")
    print(f"structure_curation_rows={len(structure_curation)}")
    print(f"structure_curation_file={STRUCTURE_CURATION_XLSX}")


if __name__ == "__main__":
    main()
