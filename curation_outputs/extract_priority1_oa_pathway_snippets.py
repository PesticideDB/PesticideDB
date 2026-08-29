from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from pypdf import PdfReader


PROJECT_ROOT = Path("/Users/nana/Desktop/PepDB/PepDatabase")
OA_CHECK = PROJECT_ROOT / "PesticideDB_Priority1_Open_Access_Check.csv"
OUT_DIR = PROJECT_ROOT / "curation_outputs" / "priority1_oa_pathway_screening_20260708"

NEEDLES = [
    "metabolite",
    "metabolites",
    "product",
    "products",
    "intermediate",
    "pathway",
    "degradation pathway",
    "transformation",
    "hydrolysis",
    "oxidation",
    "reduction",
    "dechlorination",
    "demethylation",
    "mineralization",
    "LC-MS",
    "GC-MS",
    "HPLC",
    "UPLC",
    "identified",
    "enzyme",
    "gene",
    "DDT",
    "DDE",
    "DDD",
    "glyphosate",
    "AMPA",
    "acetamiprid",
    "chlorothalonil",
    "endosulfan",
    "malathion",
    "imidacloprid",
    "paraquat",
    "dichlorvos",
    "chlorpyrifos",
]


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\x00", " ")).strip()


def snippets_for_pdf(path: Path, limit: int = 30) -> tuple[int, int, list[str]]:
    reader = PdfReader(str(path))
    snippets: list[str] = []
    chars = 0
    for page_index, page in enumerate(reader.pages[:25], start=1):
        text = compact(page.extract_text() or "")
        chars += len(text)
        lowered = text.casefold()
        for needle in NEEDLES:
            start_idx = lowered.find(needle.casefold())
            if start_idx < 0:
                continue
            start = max(0, start_idx - 650)
            end = min(len(text), start_idx + 1500)
            snippet = f"[page {page_index}] {compact(text[start:end])}"
            if snippet not in snippets:
                snippets.append(snippet)
            if len(snippets) >= limit:
                return len(reader.pages), chars, snippets
    return len(reader.pages), chars, snippets


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(OA_CHECK).fillna("")
    downloaded = df[df["download_status"].eq("downloaded_open_access_pdf")].copy()
    report_parts = []
    summary_rows = []
    for _, row in downloaded.iterrows():
        path = Path(row["downloaded_pdf_path"])
        report_parts.append(f"\n# {row['pesticide']} | {row['doi']}\n")
        report_parts.append(f"PDF: {path}\n")
        if not path.exists():
            report_parts.append("MISSING\n")
            summary_rows.append({**row.to_dict(), "screen_status": "missing", "pages": "", "extracted_chars": "", "snippet_count": 0})
            continue
        try:
            pages, chars, snippets = snippets_for_pdf(path)
            report_parts.append(f"pages={pages} extracted_chars={chars} snippets={len(snippets)}\n")
            for snippet in snippets:
                report_parts.append(f"- {snippet}\n")
            summary_rows.append({**row.to_dict(), "screen_status": "screened", "pages": pages, "extracted_chars": chars, "snippet_count": len(snippets)})
        except Exception as exc:
            report_parts.append(f"READ_ERROR: {exc}\n")
            summary_rows.append({**row.to_dict(), "screen_status": f"read_error: {exc}", "pages": "", "extracted_chars": "", "snippet_count": 0})

    (OUT_DIR / "priority1_oa_pathway_snippets.md").write_text("\n".join(report_parts), encoding="utf-8")
    pd.DataFrame(summary_rows).to_csv(OUT_DIR / "priority1_oa_pathway_screening_summary.csv", index=False)
    print(OUT_DIR / "priority1_oa_pathway_snippets.md")
    print(f"downloaded_screened={len(summary_rows)}")


if __name__ == "__main__":
    main()
