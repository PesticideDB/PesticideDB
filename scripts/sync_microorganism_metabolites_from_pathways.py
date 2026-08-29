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

from base.models import DegradationPathwayStep, Pesticide  # noqa: E402


CORE_DIR = PROJECT_ROOT / "data_files" / "core"
FILES_TO_SYNC = [
    CORE_DIR / "pesticide_data.xlsx",
    CORE_DIR / "pesticide_data.csv",
    CORE_DIR / "pesticide_data_with_2025_2026.xlsx",
    CORE_DIR / "pesticide_data_with_2025_2026.csv",
    CORE_DIR / "additional_2025-2026-search.xlsx",
]
METABOLITE_COLUMN = "Metabolite_or_product"
DOI_PATTERN = re.compile(r"10\.\d{4,9}/[^\s;,]+", re.IGNORECASE)
UNRESOLVED_PRODUCT_PHRASES = (
    "not resolved in current database source",
    "products/intermediates not identified",
    "microbial transformation products",
    "transformation products not resolved",
    "degradation products not resolved",
)


def clean(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def canonical(value) -> str:
    return clean(value).casefold()


def normalize_doi(value: str) -> str:
    doi = clean(value).rstrip(".;,)")
    return doi.casefold()


def dois_from_text(value: str) -> set[str]:
    return {normalize_doi(match.group(0)) for match in DOI_PATTERN.finditer(clean(value))}


def product_is_useful(product: str) -> bool:
    lower = clean(product).casefold()
    return bool(lower) and not any(phrase in lower for phrase in UNRESOLVED_PRODUCT_PHRASES)


def split_product_label(product: str) -> list[str]:
    product = clean(product)
    if " + " not in product:
        return [product] if product_is_useful(product) else []
    return [part.strip() for part in product.split(" + ") if product_is_useful(part)]


def build_product_lookup() -> dict[tuple[str, str], list[str]]:
    lookup: dict[tuple[str, str], list[str]] = {}
    steps = DegradationPathwayStep.objects.select_related("pathway").all()
    for step in steps:
        doi_text = " ".join([clean(step.doi), clean(step.pathway.doi)])
        dois = dois_from_text(doi_text)
        if not dois:
            continue
        products = split_product_label(step.product)
        if not products:
            continue
        pesticide_key = canonical(step.pathway.pesticide)
        for doi in dois:
            key = (pesticide_key, doi)
            lookup.setdefault(key, [])
            for product in products:
                if canonical(product) not in {canonical(existing) for existing in lookup[key]}:
                    lookup[key].append(product)
    return lookup


def product_summary(products: list[str]) -> str:
    return "; ".join(products)


def update_database(lookup: dict[tuple[str, str], list[str]]) -> int:
    updated = 0
    for record in Pesticide.objects.all():
        dois = dois_from_text(" ".join([clean(record.doi), clean(record.reference)]))
        if not dois:
            continue
        products = []
        for doi in dois:
            products.extend(lookup.get((canonical(record.pesticide), doi), []))
        unique_products = []
        seen = set()
        for product in products:
            key = canonical(product)
            if key and key not in seen:
                seen.add(key)
                unique_products.append(product)
        if not unique_products:
            continue
        summary = product_summary(unique_products)
        if clean(record.metabolite_or_product) == summary:
            continue
        record.metabolite_or_product = summary
        record.save(update_fields=["metabolite_or_product", "updated"])
        updated += 1
    return updated


def backup_files() -> Path:
    backup_dir = PROJECT_ROOT / "backups" / f"metabolite_product_sync_{datetime.now():%Y%m%d_%H%M%S}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for path in FILES_TO_SYNC:
        if path.exists():
            shutil.copy2(path, backup_dir / path.name)
    return backup_dir


def read_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".xlsx":
        df = pd.read_excel(path).fillna("")
    else:
        df = pd.read_csv(path).fillna("")
    if METABOLITE_COLUMN not in df.columns:
        df[METABOLITE_COLUMN] = ""
    return df


def write_table(df: pd.DataFrame, path: Path) -> None:
    if path.suffix.lower() == ".xlsx":
        df.to_excel(path, index=False)
    else:
        df.to_csv(path, index=False)


def update_file(path: Path, lookup: dict[tuple[str, str], list[str]]) -> int:
    if not path.exists():
        return 0
    df = read_table(path)
    required = {"Pesticide", "Reference"}
    if not required.issubset(df.columns):
        return 0
    updated = 0
    for index, row in df.iterrows():
        dois = dois_from_text(row.get("Reference", ""))
        products = []
        for doi in dois:
            products.extend(lookup.get((canonical(row.get("Pesticide", "")), doi), []))
        unique_products = []
        seen = set()
        for product in products:
            key = canonical(product)
            if key and key not in seen:
                seen.add(key)
                unique_products.append(product)
        if not unique_products:
            continue
        summary = product_summary(unique_products)
        if clean(row.get(METABOLITE_COLUMN, "")) == summary:
            continue
        df.at[index, METABOLITE_COLUMN] = summary
        updated += 1
    write_table(df, path)
    return updated


def main() -> None:
    lookup = build_product_lookup()
    backup_dir = backup_files()
    db_updated = update_database(lookup)
    print("Metabolite/product sync complete")
    print(f"backup_dir={backup_dir}")
    print(f"pathway_doi_product_keys={len(lookup)}")
    print(f"database_rows_updated={db_updated}")
    for path in FILES_TO_SYNC:
        file_updated = update_file(path, lookup)
        if path.exists():
            print(f"{path.relative_to(PROJECT_ROOT)} rows_updated={file_updated}")


if __name__ == "__main__":
    main()
