from __future__ import annotations

import csv
import re
from pathlib import Path

from pypdf import PdfReader


PROJECT_ROOT = Path("/Users/nana/Desktop/PepDB/PepDatabase")
USB_ROOT = Path("/Volumes/WENTBROKE/Pesticide degradation database/pesticidepdf")
OUT_DIR = PROJECT_ROOT / "curation_outputs" / "remaining_ready_pathway_screening_20260707"
MISSING = PROJECT_ROOT / "PesticideDB_Missing_Stepwise_Pathway_Information.csv"

PRODUCT_TERMS = re.compile(
    r"metabolite|product|intermediate|pathway|LC-MS|LC/MS|LCMS|GC-MS|GC/MS|HPLC|UPLC|"
    r"hydrolysis|oxidation|reduction|demethyl|dealkyl|dechlor|cleavage|mineralization|"
    r"carbendazim|glufosinate|MPP|MPPA|AMPA|phosmet|phosmet-oxon|propargite|fenamiphos|"
    r"sulfoxide|sulfone|trifloxystrobin acid|pinoxaden|metabolites?",
    re.IGNORECASE,
)


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\x00", " ")).strip()


def safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_")


def read_remaining_ready() -> list[dict[str, str]]:
    with MISSING.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    ready = [
        row for row in rows
        if row["current_pathway_status"].startswith("Needs stepwise product/intermediate screening")
    ]
    ready.sort(key=lambda row: (-int(row.get("real_pdf_count") or 0), row["pesticide"]))
    return ready


def candidate_filenames(row: dict[str, str]) -> list[str]:
    values = []
    for part in (row.get("top_candidate_papers") or "").split(" | "):
        part = part.strip()
        if part and not part.startswith("+"):
            values.append(part)
    return values[:5]


def snippets_for_pdf(path: Path, limit: int = 12) -> tuple[int, int, list[str]]:
    reader = PdfReader(str(path))
    snippets = []
    chars = 0
    for page_index, page in enumerate(reader.pages[:15], start=1):
        text = clean_text(page.extract_text() or "")
        chars += len(text)
        for match in PRODUCT_TERMS.finditer(text):
            start = max(0, match.start() - 260)
            end = min(len(text), match.end() + 520)
            snippet = f"[page {page_index}] {clean_text(text[start:end])}"
            if snippet not in snippets:
                snippets.append(snippet)
            if len(snippets) >= limit:
                return len(reader.pages), chars, snippets
    return len(reader.pages), chars, snippets


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_rows = []
    report_parts = []
    for row in read_remaining_ready():
        pesticide = row["pesticide"]
        report_parts.append(f"\n# {pesticide}\n")
        folder = USB_ROOT / pesticide
        for filename in candidate_filenames(row):
            path = folder / filename
            report_parts.append(f"\n## {filename}\n")
            if not path.exists():
                report_parts.append("MISSING\n")
                summary_rows.append({
                    "pesticide": pesticide,
                    "pdf_file": filename,
                    "status": "missing",
                    "pages": "",
                    "extracted_chars": "",
                    "snippet_count": 0,
                })
                continue
            try:
                pages, chars, snippets = snippets_for_pdf(path)
                report_parts.append(f"pages={pages} extracted_chars={chars} snippets={len(snippets)}\n")
                for snippet in snippets:
                    report_parts.append(f"- {snippet}\n")
                summary_rows.append({
                    "pesticide": pesticide,
                    "pdf_file": filename,
                    "status": "screened",
                    "pages": pages,
                    "extracted_chars": chars,
                    "snippet_count": len(snippets),
                })
            except Exception as exc:
                report_parts.append(f"READ_ERROR: {exc}\n")
                summary_rows.append({
                    "pesticide": pesticide,
                    "pdf_file": filename,
                    "status": f"read_error: {exc}",
                    "pages": "",
                    "extracted_chars": "",
                    "snippet_count": 0,
                })
    (OUT_DIR / "remaining_ready_candidate_snippets.md").write_text("\n".join(report_parts), encoding="utf-8")
    with (OUT_DIR / "remaining_ready_candidate_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["pesticide", "pdf_file", "status", "pages", "extracted_chars", "snippet_count"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary_rows)
    print(OUT_DIR)
    print(f"screened_files={len(summary_rows)}")


if __name__ == "__main__":
    main()
