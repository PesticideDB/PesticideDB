from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd


BASE = Path(__file__).resolve().parents[1]

CORE_FILES = [
    BASE / "data_files/core/pesticide_data.csv",
    BASE / "data_files/core/pesticide_data_with_2025_2026.csv",
]

PROTEIN_FILES = [
    BASE / "data_files/protein/PBDB_Proteins_Master.csv",
    BASE / "data_files/protein/PBDB_Proteins_Master_With_2025_2026.csv",
]


def write_csv_and_xlsx(df: pd.DataFrame, csv_path: Path) -> None:
    df.to_csv(csv_path, index=False)
    xlsx_path = csv_path.with_suffix(".xlsx")
    if xlsx_path.exists():
        df.to_excel(xlsx_path, index=False)


def update_core_file(path: Path) -> int:
    df = pd.read_csv(path)
    mask = df["Enzyme_name_reported"].fillna("").astype(str).str.strip().str.casefold().eq("laccase")
    changed = int((df.loc[mask, "Enzyme"].fillna("").astype(str) != "Oxidoreductases").sum())
    df.loc[mask, "Enzyme"] = "Oxidoreductases"
    df.loc[mask, "Enzyme_name_reported"] = "Laccase"
    write_csv_and_xlsx(df, path)
    return changed


def update_protein_file(path: Path) -> int:
    df = pd.read_csv(path)
    mask = df["reported_protein_name"].fillna("").astype(str).str.strip().str.casefold().eq("laccase")
    changed = int((df.loc[mask, "enzyme_class"].fillna("").astype(str) != "Oxidoreductase").sum())
    df.loc[mask, "enzyme_class"] = "Oxidoreductase"
    df.loc[mask, "reported_protein_name"] = "Laccase"
    write_csv_and_xlsx(df, path)
    return changed


def update_django_database() -> tuple[int, int]:
    sys.path.insert(0, str(BASE))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "PepDatabase.settings")
    import django

    django.setup()

    from base.models import Pesticide, ProteinRecord

    pesticide_qs = Pesticide.objects.filter(enzyme_name_reported__iexact="Laccase")
    pesticide_changed = pesticide_qs.exclude(enzyme="Oxidoreductases").update(enzyme="Oxidoreductases")
    pesticide_qs.update(enzyme_name_reported="Laccase")

    protein_qs = ProteinRecord.objects.filter(reported_protein_name__iexact="Laccase")
    protein_changed = protein_qs.exclude(enzyme_class="Oxidoreductase").update(enzyme_class="Oxidoreductase")
    protein_qs.update(reported_protein_name="Laccase")

    return pesticide_changed, protein_changed


def main() -> None:
    for path in CORE_FILES:
        print(f"{path}: core_laccase_class_rows_changed={update_core_file(path)}")
    for path in PROTEIN_FILES:
        print(f"{path}: protein_laccase_class_rows_changed={update_protein_file(path)}")
    pesticide_changed, protein_changed = update_django_database()
    print(f"django:Pesticide laccase rows changed={pesticide_changed}")
    print(f"django:ProteinRecord laccase rows changed={protein_changed}")


if __name__ == "__main__":
    main()
