from __future__ import annotations

from collections import Counter
from pathlib import Path
import re

import pandas as pd


USB_ROOT = Path("/Volumes/WENTBROKE/Pesticide degradation database/pesticidepdf")
PROJECT_ROOT = Path("/Users/nana/Desktop/PepDB/PepDatabase")
EVIDENCE_FILE = PROJECT_ROOT / "pesticide_data.xlsx"
OUT_DIR = PROJECT_ROOT / "curation_outputs" / "evidence_pesticide_pdf_inventory_20260707"

COMPLETED = {
    "1,4-Dimethylnaphthalene": "completed_partial_unresolved_pathway",
    "Acephate": "completed_review_package_not_integrated",
    "Chlorpyrifos": "placeholder_triage_only",
    "2-Phenylphenol": "completed_review_package_not_integrated",
}


def normalize_name(value: str) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("&", "and")
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def classify_file(path: Path) -> str:
    try:
        head = path.read_bytes()[:256]
    except OSError:
        return "read_error"
    if head.startswith(b"%PDF"):
        return "real_pdf"
    if head.lstrip().startswith(b"<"):
        return "html_placeholder"
    return "other"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    evidence_df = pd.read_excel(EVIDENCE_FILE)
    pesticides = sorted(
        {
            str(v).strip()
            for v in evidence_df["Pesticide"].dropna()
            if str(v).strip()
        },
        key=str.casefold,
    )

    usb_dirs = {normalize_name(p.name): p for p in USB_ROOT.iterdir() if p.is_dir()}
    rows: list[dict[str, object]] = []

    for pesticide in pesticides:
        folder = usb_dirs.get(normalize_name(pesticide))
        if folder is None:
            rows.append(
                {
                    "pesticide": pesticide,
                    "usb_folder": "",
                    "folder_found": "No",
                    "total_pdf_named_files": 0,
                    "real_pdf_count": 0,
                    "html_placeholder_count": 0,
                    "other_count": 0,
                    "read_error_count": 0,
                    "curation_status": "missing_folder",
                    "priority": "blocked",
                    "recommended_next_action": "Create or locate the PDF folder for this evidence-positive pesticide.",
                    "sample_files": "",
                }
            )
            continue

        files = sorted(folder.glob("*.pdf"), key=lambda p: p.name.casefold())
        counts = Counter(classify_file(file) for file in files)
        sample_files = " | ".join(file.name for file in files[:4])
        curation_status = COMPLETED.get(folder.name, "not_started")

        if folder.name in COMPLETED:
            priority = "completed"
            recommended = "Review existing curation package before database integration."
        elif counts["real_pdf"] > 0:
            priority = "high" if counts["real_pdf"] >= 20 else "medium"
            recommended = "Ready for evidence/pathway screening from readable PDFs."
        elif counts["html_placeholder"] > 0:
            priority = "blocked"
            recommended = "Files are HTML download placeholders; re-download real PDFs from DOI/journal/PMC."
        else:
            priority = "blocked"
            recommended = "No readable PDFs found; add source PDFs before pathway curation."

        rows.append(
            {
                "pesticide": pesticide,
                "usb_folder": str(folder),
                "folder_found": "Yes",
                "total_pdf_named_files": len(files),
                "real_pdf_count": counts["real_pdf"],
                "html_placeholder_count": counts["html_placeholder"],
                "other_count": counts["other"],
                "read_error_count": counts["read_error"],
                "curation_status": curation_status,
                "priority": priority,
                "recommended_next_action": recommended,
                "sample_files": sample_files,
            }
        )

    inventory = pd.DataFrame(rows)
    readable = inventory[
        (inventory["real_pdf_count"] > 0)
        & ~inventory["curation_status"].astype(str).str.startswith("completed")
    ].sort_values(["real_pdf_count", "pesticide"], ascending=[False, True])
    placeholders = inventory[
        (inventory["real_pdf_count"] == 0) & (inventory["html_placeholder_count"] > 0)
    ].sort_values(["html_placeholder_count", "pesticide"], ascending=[False, True])
    completed = inventory[inventory["curation_status"].isin(COMPLETED.values())]

    summary = pd.DataFrame(
        [
            ["Evidence-positive pesticides", len(inventory)],
            ["Folders found on USB", int((inventory["folder_found"] == "Yes").sum())],
            ["Folders with readable PDFs", int((inventory["real_pdf_count"] > 0).sum())],
            ["Folders needing PDF re-download", len(placeholders)],
            ["Completed/started curation packages", len(completed)],
            ["Total readable PDFs in evidence-positive folders", int(inventory["real_pdf_count"].sum())],
            ["Total HTML placeholder files in evidence-positive folders", int(inventory["html_placeholder_count"].sum())],
            ["Next recommended folder", readable.iloc[0]["pesticide"] if len(readable) else ""],
        ],
        columns=["metric", "value"],
    )

    inventory.to_csv(OUT_DIR / "evidence_pesticide_folder_inventory.csv", index=False)
    readable.to_csv(OUT_DIR / "evidence_pesticide_readable_pdf_queue.csv", index=False)
    placeholders.to_csv(OUT_DIR / "evidence_pesticide_placeholder_redownload_queue.csv", index=False)

    xlsx_path = OUT_DIR / "pesticidedb_evidence_pesticide_pdf_inventory_20260707.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Summary", index=False)
        inventory.to_excel(writer, sheet_name="Evidence Inventory", index=False)
        readable.to_excel(writer, sheet_name="Readable Queue", index=False)
        placeholders.to_excel(writer, sheet_name="Re-download Queue", index=False)
        completed.to_excel(writer, sheet_name="Completed Curation", index=False)
        for sheet in writer.book.worksheets:
            sheet.freeze_panes = "A2"
            for cell in sheet[1]:
                cell.style = "Headline 3"
            for column_cells in sheet.columns:
                max_len = max(len(str(cell.value or "")) for cell in column_cells[:200])
                sheet.column_dimensions[column_cells[0].column_letter].width = min(max(max_len + 2, 12), 60)

    print(f"wrote={xlsx_path}")
    print(f"evidence_positive={len(inventory)}")
    print(f"readable_queue={len(readable)}")
    print(f"placeholder_queue={len(placeholders)}")
    print(f"next={readable.iloc[0]['pesticide'] if len(readable) else ''}")


if __name__ == "__main__":
    main()
