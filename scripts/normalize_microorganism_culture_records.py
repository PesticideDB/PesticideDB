from __future__ import annotations

import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

import django
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "PepDatabase.settings")
django.setup()

from base.models import Pesticide  # noqa: E402


CORE_DIR = PROJECT_ROOT / "data_files" / "core"
FILES_TO_NORMALIZE = [
    CORE_DIR / "additional_2025-2026-search.xlsx",
    CORE_DIR / "additional_existing_curated_evidence.xlsx",
    CORE_DIR / "pesticide_data.xlsx",
    CORE_DIR / "pesticide_data.csv",
    CORE_DIR / "pesticide_data_with_2025_2026.xlsx",
    CORE_DIR / "pesticide_data_with_2025_2026.csv",
]
OUTPUT_COLUMNS = [
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


SPLIT_RULES = {
    "Anaerobic enrichment; Pseudomonas and Shewanella dominant": [
        ("Pseudomonas spp. dominant in anaerobic enrichment", "Enrichment culture member"),
        ("Shewanella spp. dominant in anaerobic enrichment", "Enrichment culture member"),
    ],
    "Beauveria bassiana B-Tg1 + Metarhizium anisopliae M-Tg1 consortium": [
        ("Beauveria bassiana B-Tg1", "Consortium member"),
        ("Metarhizium anisopliae M-Tg1", "Consortium member"),
    ],
    "Tunisian hypersaline sediment microbial community (Pseudomonas 45%; Marinobacter 16%)": [
        ("Pseudomonas spp. in Tunisian hypersaline sediment community", "Microbial community member"),
        ("Marinobacter spp. in Tunisian hypersaline sediment community", "Microbial community member"),
    ],
    "Bacillus licheniformis + Bacillus pumilus consortium": [
        ("Bacillus licheniformis", "Consortium member"),
        ("Bacillus pumilus", "Consortium member"),
    ],
}

TYPE_RULES = {
    "Mixed microbe": "Mixed culture - members not specified",
    "Undefined mixed aerobic bacterial biofilm cultures from rotating-drum systems": "Mixed biofilm culture",
    "Sulfate-reducing Jilin Oilfield production-water enrichment": "Enrichment culture",
    "Anaerobic flooded-soil microbial community": "Microbial community",
    "Anaerobic aquatic microbial community": "Microbial community",
    "Anaerobic microbial community": "Microbial community",
    "Microbial consortium AT1": "Microbial consortium - members not specified",
    "Klebsiella spp. isolates": "Isolate group",
}

LEGACY_TYPE_LABELS = {
    "mixed culture, unresolved": "Mixed culture - members not specified",
    "microbial consortium, unresolved": "Microbial consortium - members not specified",
}


def clean(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def canonical(value) -> str:
    return clean(value).casefold()


def read_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".xlsx":
        df = pd.read_excel(path).fillna("")
    else:
        df = pd.read_csv(path).fillna("")
    df.columns = [clean(column) for column in df.columns]
    if "Culture_type" not in df.columns:
        df["Culture_type"] = ""
    for column in OUTPUT_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    return df[OUTPUT_COLUMNS].copy()


def normalize_culture_type(microorganism: str, existing_type: str) -> str:
    existing = clean(existing_type)
    if existing:
        return LEGACY_TYPE_LABELS.get(existing.casefold(), existing)
    return TYPE_RULES.get(clean(microorganism), "Individual strain")


def normalize_rows(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        microorganism = clean(row["Microorganism"])
        if microorganism in SPLIT_RULES:
            for member, culture_type in SPLIT_RULES[microorganism]:
                new_row = row.copy()
                new_row["Microorganism"] = member
                new_row["Culture_type"] = culture_type
                rows.append(new_row)
        else:
            row = row.copy()
            row["Microorganism"] = microorganism
            row["Culture_type"] = normalize_culture_type(microorganism, row.get("Culture_type", ""))
            rows.append(row)

    normalized = pd.DataFrame(rows, columns=OUTPUT_COLUMNS).fillna("")
    for column in OUTPUT_COLUMNS:
        normalized[column] = normalized[column].map(clean)
    normalized = normalized.drop_duplicates(subset=OUTPUT_COLUMNS, keep="first")
    return normalized


def write_table(df: pd.DataFrame, path: Path) -> None:
    if path.suffix.lower() == ".xlsx":
        df.to_excel(path, index=False)
    else:
        df.to_csv(path, index=False)


def backup_files() -> Path:
    backup_dir = PROJECT_ROOT / "backups" / f"microorganism_culture_normalization_{datetime.now():%Y%m%d_%H%M%S}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for path in FILES_TO_NORMALIZE:
        if path.exists():
            shutil.copy2(path, backup_dir / path.name)
    return backup_dir


def refresh_database_from_master(master: pd.DataFrame) -> None:
    existing_by_key = {
        (
            canonical(record.microorganism),
            canonical(record.pesticide),
            canonical(record.reference),
        ): record
        for record in Pesticide.objects.all()
    }

    desired_keys = set()
    created = 0
    updated = 0
    for _, row in master.iterrows():
        key = (
            canonical(row["Microorganism"]),
            canonical(row["Pesticide"]),
            canonical(row["Reference"]),
        )
        desired_keys.add(key)
        year = clean(row["Publication_Year"])
        defaults = {
            "pesticide": clean(row["Pesticide"]),
            "microorganism": clean(row["Microorganism"]),
            "culture_type": clean(row["Culture_type"]) or "Individual strain",
            "evidence_by_microbe": clean(row["Evidence"]),
            "isolation_environment": clean(row["Isolation_environment"]),
            "isolation_location": clean(row["Isolation_Location"]),
            "publication_year": int(float(year)) if year else None,
            "enzyme": clean(row["Enzyme"]),
            "enzyme_name_reported": clean(row["Enzyme_name_reported"]),
            "gene": clean(row["Gene"]),
            "reference": clean(row["Reference"]),
            "doi": clean(row["Reference"]) if clean(row["Reference"]).startswith("10.") else None,
        }
        record = existing_by_key.get(key)
        if record:
            for field, value in defaults.items():
                setattr(record, field, value)
            record.save()
            updated += 1
        else:
            Pesticide.objects.create(**defaults)
            created += 1

    removed = 0
    for key, record in existing_by_key.items():
        if key in desired_keys:
            continue
        original_name = clean(record.microorganism)
        if original_name in SPLIT_RULES:
            record.delete()
            removed += 1

    return created, updated, removed


def unique_reference_count(df: pd.DataFrame) -> int:
    return len({canonical(value) for value in df["Reference"] if canonical(value) and canonical(value) != "nan"})


def main() -> None:
    backup_dir = backup_files()
    normalized_tables = {}
    for path in FILES_TO_NORMALIZE:
        if not path.exists():
            continue
        normalized = normalize_rows(read_table(path))
        normalized_tables[path] = normalized
        write_table(normalized, path)

    master = normalized_tables[CORE_DIR / "pesticide_data.xlsx"]
    created, updated, removed = refresh_database_from_master(master)
    print("Microorganism culture normalization complete")
    print(f"backup_dir={backup_dir}")
    print(f"master_rows={len(master)}")
    print(f"master_unique_references={unique_reference_count(master)}")
    print(f"database_created={created}")
    print(f"database_updated={updated}")
    print(f"database_removed_grouped_rows={removed}")
    print("split_rules_applied:")
    for original, members in SPLIT_RULES.items():
        print(f" - {original} -> {', '.join(member for member, _, _ in members)}")


if __name__ == "__main__":
    main()
