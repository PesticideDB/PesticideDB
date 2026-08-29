import csv
import json
from collections import defaultdict
from pathlib import Path
import sys

import django
import os

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "PepDatabase.settings")
django.setup()

from django.db.models import Count  # noqa: E402

from base.models import DegradationPathwayStep  # noqa: E402


OUT_DIR = ROOT / "curation_outputs" / "missing_stepwise_pathway_information_20260707"
INVENTORY = ROOT / "curation_outputs" / "evidence_pesticide_pdf_inventory_20260707" / "evidence_pesticide_folder_inventory.csv"
REVIEW_QUEUE = ROOT / "curation_outputs" / "consolidated_pathway_review_queue_20260707" / "top_review_set_max5_per_pesticide.csv"


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows, fieldnames):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def normalize(name):
    return (name or "").strip().lower()


def next_status(row, has_stepwise, review_items):
    real_pdf_count = int(row.get("real_pdf_count") or 0)
    placeholder_count = int(row.get("html_placeholder_count") or 0)
    folder_found = row.get("folder_found") == "Yes"
    curation_status = row.get("curation_status") or ""

    if has_stepwise:
        return (
            "Stepwise pathway integrated",
            "No immediate action for the pathway sketch; continue literature expansion only if a more complete route is needed.",
            "Curated substrate, product, and reaction labels are already available for the current database view.",
        )
    if "completed_review_package" in curation_status:
        return (
            "Review package exists; stepwise arrows not integrated",
            "Convert the existing curation package into substrate-to-product pathway steps if product/intermediate evidence is sufficient.",
            "Substrate, product/intermediate, reaction label, evidence type, microorganism, DOI/reference.",
        )
    if not folder_found:
        return (
            "PDF folder missing",
            "Create or locate the pesticide PDF folder before pathway curation.",
            "Full-text paper PDFs or reliable source files with degradation products/intermediates.",
        )
    if placeholder_count and not real_pdf_count:
        return (
            "Full-text re-download needed",
            "Replace placeholder or unreadable files with real PDFs, then screen for products/intermediates.",
            "Readable PDFs containing chromatograms, metabolite tables, pathway schemes, or product identification.",
        )
    if real_pdf_count:
        signal = "candidate papers available" if review_items else "folder has readable PDFs"
        return (
            f"Needs stepwise product/intermediate screening ({signal})",
            "Screen the strongest papers for identified metabolites/products and convert supported reactions into pathway steps.",
            "Substrate, product/intermediate, transformation type, gene/protein/enzyme if reported, organism, DOI/reference.",
        )
    return (
        "No readable pathway source yet",
        "Add readable papers or DOI-resolved full text before creating reaction arrows.",
        "Readable source evidence with identified products/intermediates.",
    )


def compact_join(values, limit=5):
    cleaned = []
    for value in values:
        value = (value or "").strip()
        if value and value not in cleaned:
            cleaned.append(value)
    if len(cleaned) > limit:
        return " | ".join(cleaned[:limit]) + f" | +{len(cleaned) - limit} more"
    return " | ".join(cleaned)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    inventory_rows = read_csv(INVENTORY)
    review_rows = read_csv(REVIEW_QUEUE)

    review_by_pesticide = defaultdict(list)
    for row in review_rows:
        review_by_pesticide[normalize(row.get("pesticide"))].append(row)

    step_counts = {
        normalize(item["pathway__pesticide"]): item["n"]
        for item in DegradationPathwayStep.objects
        .values("pathway__pesticide")
        .annotate(n=Count("id"))
    }

    all_rows = []
    remaining_rows = []
    for row in sorted(inventory_rows, key=lambda r: (r.get("pesticide") or "").lower()):
        pesticide = row.get("pesticide", "").strip()
        key = normalize(pesticide)
        review_items = review_by_pesticide.get(key, [])
        step_count = step_counts.get(key, 0)
        status, action, needed = next_status(row, bool(step_count), review_items)
        candidate_files = compact_join([item.get("pdf_file") for item in review_items], 5)
        doi_candidates = compact_join([item.get("doi_candidates") for item in review_items], 5)
        signal = compact_join([item.get("automated_evidence_signal") for item in review_items], 5)

        out = {
            "pesticide": pesticide,
            "current_pathway_status": status,
            "stepwise_arrow_count": step_count,
            "folder_found": row.get("folder_found", ""),
            "real_pdf_count": row.get("real_pdf_count", ""),
            "html_placeholder_count": row.get("html_placeholder_count", ""),
            "top_candidate_papers": candidate_files,
            "doi_candidates_from_queue": doi_candidates,
            "automated_evidence_signal": signal,
            "needed_information_for_kegg_like_arrow": needed,
            "recommended_next_action": action,
            "sample_files_from_usb_folder": row.get("sample_files", ""),
        }
        all_rows.append(out)
        if not step_count:
            remaining_rows.append(out)

    fields = [
        "pesticide",
        "current_pathway_status",
        "stepwise_arrow_count",
        "folder_found",
        "real_pdf_count",
        "html_placeholder_count",
        "top_candidate_papers",
        "doi_candidates_from_queue",
        "automated_evidence_signal",
        "needed_information_for_kegg_like_arrow",
        "recommended_next_action",
        "sample_files_from_usb_folder",
    ]
    write_csv(OUT_DIR / "PesticideDB_Missing_Stepwise_Pathway_Information.csv", remaining_rows, fields)
    write_csv(OUT_DIR / "PesticideDB_All_Evidence_Positive_Pathway_Audit.csv", all_rows, fields)
    with (OUT_DIR / "missing_stepwise_pathway_information.json").open("w", encoding="utf-8") as handle:
        json.dump({"remaining": remaining_rows, "all": all_rows}, handle, indent=2)

    print(f"remaining={len(remaining_rows)} all={len(all_rows)} stepwise_pesticides={len(step_counts)}")
    print(OUT_DIR)


if __name__ == "__main__":
    main()
