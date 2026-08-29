from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pdfplumber


PROJECT_ROOT = Path("/Users/nana/Desktop/PepDB/PepDatabase")
CHECK_FILE = PROJECT_ROOT / "PesticideDB_Priority1_Open_Access_Check.csv"
OUT_DIR = PROJECT_ROOT / "curation_outputs" / "verified_oa_pathway_batch12_screening_20260708"
TARGETS = {
    "Malathion": [
        "malathion",
        "malaoxon",
        "monocarboxylic",
        "dicarboxylic",
        "hydroly",
        "carboxylesterase",
        "product",
    ],
    "Paraquat": ["paraquat", "insoluble crystals", "transformation", "reduction", "product"],
    "Chlorpyrifos-methyl": [
        "chlorpyrifos-methyl",
        "3,5,6-trichloro-2-pyridinol",
        "TCP",
        "hydroly",
        "degradation",
        "product",
    ],
    "Dichlorvos": [
        "dichlorvos",
        "dimethyl phosphate",
        "dichloroacetaldehyde",
        "hydroly",
        "degradation",
        "product",
    ],
    "Endosulfan": [
        "endosulfan sulfate",
        "endosulfan diol",
        "endosulfan ether",
        "endosulfan lactone",
        "endosulfan dialdehyde",
        "metabolite",
        "degradation",
    ],
    "Chlorothalonil": [
        "chlorothalonil",
        "4-hydroxy-2,5,6-trichloroisophthalonitrile",
        "TPN-OH",
        "trichloroisophthalonitrile",
        "dehalogenase",
        "hydroly",
    ],
}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def snippets(pdf_path: Path, terms: list[str], limit: int = 16) -> tuple[int, int, list[str]]:
    lowered_terms = [term.lower() for term in terms]
    found: list[str] = []
    chars = 0
    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text = normalize(page.extract_text() or "")
            chars += len(text)
            lowered = text.lower()
            for term in lowered_terms:
                start = lowered.find(term)
                if start < 0:
                    continue
                snippet = normalize(text[max(0, start - 280): min(len(text), start + 700)])
                line = f"[page {page_number}] {snippet}"
                if line not in found:
                    found.append(line)
                break
            if len(found) >= limit:
                break
    return page_number if "page_number" in locals() else 0, chars, found


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    checks = pd.read_csv(CHECK_FILE).fillna("")
    rows = []
    report = []
    for pesticide, terms in TARGETS.items():
        report.append(f"\n# {pesticide}\n")
        matches = checks[
            (checks["pesticide"] == pesticide)
            & (checks["download_status"] == "downloaded_open_access_pdf")
        ]
        for _, row in matches.iterrows():
            path = Path(row["downloaded_pdf_path"])
            report.append(f"\n## {row['doi']}\nPDF: {path}\n")
            if not path.exists():
                report.append("missing\n")
                continue
            pages, chars, found = snippets(path, terms)
            report.append(f"pages={pages} extracted_chars={chars} snippets={len(found)}\n")
            for item in found:
                report.append(f"- {item}\n")
            rows.append({
                "pesticide": pesticide,
                "doi": row["doi"],
                "pdf_path": str(path),
                "pages_checked": pages,
                "extracted_chars": chars,
                "snippet_count": len(found),
            })
    (OUT_DIR / "verified_oa_batch12_snippets.md").write_text("\n".join(report), encoding="utf-8")
    pd.DataFrame(rows).to_csv(OUT_DIR / "verified_oa_batch12_summary.csv", index=False)
    print(OUT_DIR)
    print(f"screened={len(rows)}")


if __name__ == "__main__":
    main()
