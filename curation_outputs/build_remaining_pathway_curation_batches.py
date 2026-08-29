from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path("/Users/nana/Desktop/PepDB/PepDatabase")
OUT_DIR = PROJECT_ROOT / "curation_outputs" / "remaining_pathway_curation_batches_20260710"
MISSING = PROJECT_ROOT / "PesticideDB_Missing_Stepwise_Pathway_Information.csv"
SOURCE_PRIORITY = PROJECT_ROOT / "PesticideDB_Pathway_Source_Acquisition_Priority.csv"
DOI_MANIFEST = PROJECT_ROOT / "PesticideDB_Pathway_DOI_Redownload_Manifest.csv"


BATCHES = [
    ("batch_16", "Highest priority: database-rich records and papers closest to pathway extraction"),
    ("batch_17", "Second priority: strong database/source leads requiring full-text replacement"),
    ("batch_18", "Third priority: broader DOI/source acquisition and screening"),
    ("batch_19", "Final priority: lowest-evidence records, missing folders, or papers needing replacement"),
]


PRIORITY_ORDER = {
    "Readable PDFs available - screen next": 0,
    "Screened readable files - needs different product paper": 1,
    "Placeholder files - redownload PDFs by DOI/title": 2,
    "No local readable file - literature search needed": 3,
}


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def to_int(value: object) -> int:
    try:
        return int(float(str(value or "0")))
    except ValueError:
        return 0


def short_doi_list(rows: list[dict], limit: int = 8) -> str:
    dois = []
    for row in rows:
        doi = (row.get("doi") or "").strip()
        if doi and doi not in dois:
            dois.append(doi)
    if len(dois) > limit:
        return " | ".join(dois[:limit]) + f" | +{len(dois) - limit} more"
    return " | ".join(dois)


def batch_action(row: dict) -> str:
    priority_group = row.get("priority_group") or ""
    if priority_group == "Readable PDFs available - screen next":
        return "Screen readable PDFs first. Add pathway arrows only when substrate, named product/intermediate, organism, and evidence wording are clear."
    if priority_group == "Screened readable files - needs different product paper":
        return "Search for a different metabolite/product paper; current readable file is not enough for a KEGG-like arrow."
    if priority_group == "Placeholder files - redownload PDFs by DOI/title":
        return "Replace placeholder files with real full-text PDFs using DOI leads, then screen for products/intermediates."
    return "Create or locate the pesticide PDF folder, then add full-text biodegradation/metabolite papers."


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source_rows = read_csv(SOURCE_PRIORITY)
    doi_rows = read_csv(DOI_MANIFEST)
    missing_rows = {row["pesticide"]: row for row in read_csv(MISSING)}
    doi_by_pesticide: dict[str, list[dict]] = {}
    for row in doi_rows:
        doi_by_pesticide.setdefault(row["pesticide"], []).append(row)

    rows = []
    for row in source_rows:
        pesticide = row["pesticide"]
        merged = {**missing_rows.get(pesticide, {}), **row}
        merged["doi_count"] = len(doi_by_pesticide.get(pesticide, []))
        merged["top_doi_leads_for_batch"] = short_doi_list(doi_by_pesticide.get(pesticide, []))
        merged["batch_action"] = batch_action(merged)
        rows.append(merged)

    rows.sort(
        key=lambda row: (
            to_int(row.get("acquisition_priority")),
            PRIORITY_ORDER.get(row.get("priority_group", ""), 99),
            -to_int(row.get("protein_record_count")),
            -to_int(row.get("database_record_count")),
            row.get("pesticide", "").lower(),
        )
    )

    batch_sizes = [19, 19, 19, 18]
    fieldnames = [
        "curation_batch",
        "batch_focus",
        "batch_order",
        "pesticide",
        "acquisition_priority",
        "priority_group",
        "current_pathway_status",
        "batch_action",
        "specific_next_action",
        "database_record_count",
        "protein_record_count",
        "doi_count",
        "top_doi_leads_for_batch",
        "database_gene_leads",
        "database_enzyme_leads",
        "database_microbe_leads",
        "year_range",
        "real_pdf_count",
        "html_placeholder_count",
        "folder_found",
        "top_candidate_papers",
        "needed_information_for_kegg_like_arrow",
        "sample_files_from_usb_folder",
    ]

    start = 0
    all_batched = []
    summary_rows = []
    for batch_index, ((batch_name, focus), size) in enumerate(zip(BATCHES, batch_sizes), start=1):
        batch_rows = rows[start:start + size]
        start += size
        for order, row in enumerate(batch_rows, start=1):
            row["curation_batch"] = batch_name
            row["batch_focus"] = focus
            row["batch_order"] = order
        all_batched.extend(batch_rows)
        counts = Counter(row.get("priority_group", "") for row in batch_rows)
        summary_rows.append(
            {
                "curation_batch": batch_name,
                "batch_focus": focus,
                "pesticide_count": len(batch_rows),
                "doi_rows": sum(to_int(row.get("doi_count")) for row in batch_rows),
                "readable_or_candidate": counts.get("Readable PDFs available - screen next", 0)
                + counts.get("Screened readable files - needs different product paper", 0),
                "redownload_needed": counts.get("Placeholder files - redownload PDFs by DOI/title", 0),
                "folder_missing": counts.get("No local readable file - literature search needed", 0),
            }
        )
        write_csv(OUT_DIR / f"pesticidedb_remaining_pathway_{batch_name}.csv", batch_rows, fieldnames)

    write_csv(OUT_DIR / "pesticidedb_remaining_pathway_batches_all.csv", all_batched, fieldnames)
    write_csv(
        OUT_DIR / "pesticidedb_remaining_pathway_batches_summary.csv",
        summary_rows,
        ["curation_batch", "batch_focus", "pesticide_count", "doi_rows", "readable_or_candidate", "redownload_needed", "folder_missing"],
    )
    root_all = PROJECT_ROOT / "PesticideDB_Remaining_Pathway_Curation_Batches.csv"
    root_summary = PROJECT_ROOT / "PesticideDB_Remaining_Pathway_Curation_Batches_Summary.csv"
    write_csv(root_all, all_batched, fieldnames)
    write_csv(root_summary, summary_rows, ["curation_batch", "batch_focus", "pesticide_count", "doi_rows", "readable_or_candidate", "redownload_needed", "folder_missing"])

    print(f"rows={len(all_batched)}")
    print(f"batches={len(BATCHES)}")
    for row in summary_rows:
        print(row)
    print(OUT_DIR)


if __name__ == "__main__":
    main()
