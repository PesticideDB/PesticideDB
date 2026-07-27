import os
import sys
import django
import pandas as pd

# ==============================
# Django setup
# ==============================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)  # folder containing manage.py
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "PepDatabase.settings")
django.setup()

from django.db import IntegrityError
from base.models import Pesticide, NoEvidencePesticide


ADDITIONAL_EVIDENCE_FILES = [
    os.path.join(BASE_DIR, "data_files", "core", "additional_existing_curated_evidence.xlsx"),
    os.path.join(BASE_DIR, "data_files", "core", "additional_2025-2026-search.xlsx"),
]
PROMOTED_TO_WITH_EVIDENCE = {"ethiprole", "spinetoram"}


# ==============================
# Helpers
# ==============================
def _clean_str(v) -> str:
    """Convert NaN/None to empty string and strip."""
    if v is None:
        return ""
    if isinstance(v, float) and pd.isna(v):
        return ""
    if pd.isna(v):
        return ""
    return str(v).strip()


def _canonical(v) -> str:
    return " ".join(_clean_str(v).split()).casefold()


def _read_evidence_workbook(path):
    df = pd.read_excel(path)
    df.columns = [c.strip() for c in df.columns]
    return df


# ==============================
# IMPORT: WITH EVIDENCE
# ==============================
def import_pesticide_data():
    """
    Import ALL record-level biodegradation evidence.
    - Keeps duplicates (DDT can appear many times)
    - Clears table before import
    """
    excel_path = os.path.join(BASE_DIR, "data_files", "core", "pesticide_data.xlsx")

    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"❌ File not found: {excel_path}")

    df = _read_evidence_workbook(excel_path)
    if "Culture_type" not in df.columns:
        df["Culture_type"] = "Individual strain"
    if "Metabolite_or_product" not in df.columns:
        df["Metabolite_or_product"] = ""

    if "Pesticide" not in df.columns:
        raise ValueError("❌ 'Pesticide' column missing in data_files/core/pesticide_data.xlsx")

    source_frames = [df]
    for additional_path in ADDITIONAL_EVIDENCE_FILES:
        if os.path.exists(additional_path):
            additional_df = _read_evidence_workbook(additional_path)
            if "Culture_type" not in additional_df.columns:
                additional_df["Culture_type"] = "Individual strain"
            if "Metabolite_or_product" not in additional_df.columns:
                additional_df["Metabolite_or_product"] = ""
            missing = [c for c in df.columns if c not in additional_df.columns]
            if missing:
                raise ValueError(
                    f"❌ Additional evidence file missing columns {missing}: {additional_path}"
                )
            source_frames.append(additional_df[df.columns])
    df = pd.concat(source_frames, ignore_index=True)

    # Clean pesticide column
    df["Pesticide"] = df["Pesticide"].astype(str).str.strip()
    df = df[df["Pesticide"] != ""]

    # Clear existing data
    Pesticide.objects.all().delete()

    created = 0
    failed = 0

    for i, row in df.iterrows():
        row_data = row.to_dict()

        try:
            Pesticide.objects.create(
                pesticide=_clean_str(row_data.get("Pesticide")),
                microorganism=_clean_str(row_data.get("Microorganism")),
                culture_type=_clean_str(row_data.get("Culture_type")) or "Individual strain",
                evidence_by_microbe=_clean_str(row_data.get("Evidence")),
                isolation_environment=_clean_str(row_data.get("Isolation_environment")),
                isolation_location=_clean_str(row_data.get("Isolation_Location")),
                publication_year=int(row_data.get("Publication_Year"))
                if _clean_str(row_data.get("Publication_Year")) else None,
                enzyme=_clean_str(row_data.get("Enzyme")),
                enzyme_name_reported=_clean_str(row_data.get("Enzyme_name_reported")),
                gene=_clean_str(row_data.get("Gene")),
                reference=_clean_str(row_data.get("Reference")),
                metabolite_or_product=_clean_str(row_data.get("Metabolite_or_product")) or None,
                doi=_clean_str(row_data.get("Reference"))
                if _clean_str(row_data.get("Reference")).startswith("10.") else None,
            )
            created += 1

        except IntegrityError as e:
            failed += 1
            print("❌ IntegrityError:", e)
            print("   Pesticide =", row_data.get("Pesticide"))

        except Exception as e:
            failed += 1
            print("❌ Unexpected error:", e)
            print("   Pesticide =", row_data.get("Pesticide"))

        if i % 200 == 0:
            print(f"Processed {i} rows...")

    unique_with_evidence = (
        Pesticide.objects.exclude(pesticide="")
        .values("pesticide")
        .distinct()
        .count()
    )

    print(
        f"✅ WITH-EVIDENCE imported | rows={created}, "
        f"failed={failed}, unique_pesticides={unique_with_evidence}"
    )


# ==============================
# IMPORT: NO EVIDENCE
# ==============================
def import_no_evidence_data():
    """
    Import pesticides with NO experimental evidence.
    - One row per pesticide (deduplicated)
    """
    excel_path = os.path.join(BASE_DIR, "data_files", "core", "no_evidence_pesticide.xlsx")

    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"❌ File not found: {excel_path}")

    df = pd.read_excel(excel_path)
    df.columns = [c.strip() for c in df.columns]

    # Normalize column name
    if "Pesticide" not in df.columns:
        for c in df.columns:
            if c.lower() == "pesticide":
                df.rename(columns={c: "Pesticide"}, inplace=True)

    if "Pesticide" not in df.columns:
        raise ValueError("❌ 'Pesticide' column missing in data_files/core/no_evidence_pesticide.xlsx")

    df["Pesticide"] = df["Pesticide"].astype(str).str.strip()
    df = df[df["Pesticide"] != ""]
    df = df[~df["Pesticide"].map(_canonical).isin(PROMOTED_TO_WITH_EVIDENCE)]

    # Deduplicate (correct for no-evidence list)
    df = df.drop_duplicates(subset=["Pesticide"], keep="first")

    # Clear existing data
    NoEvidencePesticide.objects.all().delete()

    for _, row in df.iterrows():
        NoEvidencePesticide.objects.create(
            pesticide=_clean_str(row.get("Pesticide")),
            evidence_of_biodegradation="No experimental biodegradation evidence found",
        )

    unique_no_evidence = (
        NoEvidencePesticide.objects.exclude(pesticide="")
        .values("pesticide")
        .distinct()
        .count()
    )

    print(
        f"✅ NO-EVIDENCE imported | unique_pesticides={unique_no_evidence}"
    )


# ==============================
# RUN BOTH
# ==============================
if __name__ == "__main__":
    import_pesticide_data()
    import_no_evidence_data()

    with_e = (
        Pesticide.objects.exclude(pesticide="")
        .values("pesticide")
        .distinct()
        .count()
    )

    no_e = (
        NoEvidencePesticide.objects.exclude(pesticide="")
        .values("pesticide")
        .distinct()
        .count()
    )

    print(
        f"🎉 DONE | with_evidence_unique={with_e}, "
        f"no_evidence_unique={no_e}, total_unique={with_e + no_e}"
    )
