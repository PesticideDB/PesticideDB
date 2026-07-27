from __future__ import annotations

import csv
from pathlib import Path


USB_ROOT = Path("/Volumes/WENTBROKE/Pesticide degradation database/pesticidepdf")
PROJECT_ROOT = Path("/Users/nana/Desktop/PepDB/PepDatabase")
OUT_DIR = PROJECT_ROOT / "curation_outputs" / "pdf_readability_audit_20260707"


def classify(path: Path) -> str:
    try:
        head = path.read_bytes()[:16]
    except OSError:
        return "unreadable_file"
    stripped = head.lstrip()
    if stripped.startswith(b"%PDF"):
        return "pdf_header"
    if stripped.startswith(b"<") or b"<html" in stripped.lower():
        return "html_placeholder"
    if not stripped:
        return "empty_or_blank"
    return "unknown_non_pdf"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    folder_summary = {}
    for pdf in sorted(USB_ROOT.glob("*/*.pdf")):
        folder = pdf.parent.name
        status = classify(pdf)
        summary = folder_summary.setdefault(
            folder,
            {
                "pesticide_folder": folder,
                "total_pdf_named_files": 0,
                "pdf_header_files": 0,
                "html_placeholder_files": 0,
                "unknown_or_unreadable_files": 0,
                "sample_pdf_header_files": [],
                "sample_placeholder_files": [],
            },
        )
        summary["total_pdf_named_files"] += 1
        if status == "pdf_header":
            summary["pdf_header_files"] += 1
            if len(summary["sample_pdf_header_files"]) < 5:
                summary["sample_pdf_header_files"].append(pdf.name)
        elif status == "html_placeholder":
            summary["html_placeholder_files"] += 1
            if len(summary["sample_placeholder_files"]) < 5:
                summary["sample_placeholder_files"].append(pdf.name)
        else:
            summary["unknown_or_unreadable_files"] += 1
        rows.append(
            {
                "pesticide_folder": folder,
                "file_name": pdf.name,
                "readability_status": status,
            }
        )

    details_path = OUT_DIR / "pesticide_pdf_readability_details.csv"
    with details_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["pesticide_folder", "file_name", "readability_status"])
        writer.writeheader()
        writer.writerows(rows)

    summary_rows = []
    for summary in sorted(folder_summary.values(), key=lambda item: item["pesticide_folder"].casefold()):
        summary_rows.append(
            {
                **summary,
                "sample_pdf_header_files": " | ".join(summary["sample_pdf_header_files"]),
                "sample_placeholder_files": " | ".join(summary["sample_placeholder_files"]),
            }
        )
    summary_path = OUT_DIR / "pesticide_pdf_readability_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "pesticide_folder",
                "total_pdf_named_files",
                "pdf_header_files",
                "html_placeholder_files",
                "unknown_or_unreadable_files",
                "sample_pdf_header_files",
                "sample_placeholder_files",
            ],
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"details={details_path}")
    print(f"summary={summary_path}")
    print(f"files={len(rows)} folders={len(summary_rows)}")


if __name__ == "__main__":
    main()
