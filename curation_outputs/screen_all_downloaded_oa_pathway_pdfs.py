from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pdfplumber


PROJECT_ROOT = Path("/Users/nana/Desktop/PepDB/PepDatabase")
CHECK_FILE = PROJECT_ROOT / "curation_outputs" / "pathway_open_access_all_remaining_20260709" / "pesticidedb_all_remaining_open_access_check.csv"
OUT_DIR = PROJECT_ROOT / "curation_outputs" / "downloaded_oa_pathway_screening_20260709"

COMMON_TERMS = [
    "metabolite",
    "metabolites",
    "product",
    "products",
    "intermediate",
    "intermediates",
    "degradation pathway",
    "pathway",
    "LC-MS",
    "LC/MS",
    "GC-MS",
    "GC/MS",
    "HPLC",
    "UPLC",
    "hydrolysis",
    "hydrolyzed",
    "oxidation",
    "reduction",
    "dechlorination",
    "dehalogenation",
    "demethylation",
    "cleavage",
    "mineralization",
]

PESTICIDE_TERMS = {
    "Lindane": ["gamma-HCH", "pentachlorocyclohexene", "tetrachlorocyclohexene", "chlorobenzene"],
    "Flonicamid": ["TFNG", "TFNA", "TFNA-AM", "4-trifluoromethylnicotinic acid"],
    "Iprodione": ["3,5-dichloroaniline", "isopropylamine", "hydantoin"],
    "Dicamba": ["3,6-dichlorosalicylic acid", "DCSA", "demethylation"],
    "Fenvalerate": ["3-phenoxybenzoic acid", "PBA", "3-PBA", "fenvaleric acid"],
    "Phorate": ["phorate sulfoxide", "phorate sulfone", "phoratoxon"],
    "Thiacloprid": ["thiacloprid amide", "6-chloronicotinic acid", "descyano"],
    "Deltamethrin": ["3-phenoxybenzaldehyde", "3-phenoxybenzoic acid", "deltamethric acid"],
    "Oxamyl": ["oxamyl oxime", "methylamine", "dimethyl oxalate"],
    "Cyromazine": ["melamine", "ammeline", "ammelide", "cyanuric acid"],
    "Bifenthrin": ["4-hydroxy bifenthrin", "bifenthrin alcohol", "3-phenoxybenzoic acid"],
    "Flubendiamide": ["desiodo", "phthalic acid", "benzoic acid"],
    "Propiconazole": ["1,2,4-triazole", "hydroxypropiconazole", "triazole alanine"],
    "Bentazone": ["6-hydroxy bentazone", "8-hydroxy bentazone", "anthranilic acid"],
    "Permethrin": ["3-phenoxybenzyl alcohol", "3-phenoxybenzaldehyde", "3-phenoxybenzoic acid"],
}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def snippets_for_pdf(path: Path, pesticide: str, limit: int = 14) -> tuple[int, int, list[str]]:
    terms = [pesticide, *PESTICIDE_TERMS.get(pesticide, []), *COMMON_TERMS]
    lowered_terms = [term.lower() for term in terms]
    found: list[str] = []
    chars = 0
    pages = 0
    with pdfplumber.open(path) as pdf:
        pages = len(pdf.pages)
        for page_number, page in enumerate(pdf.pages[:20], start=1):
            text = normalize(page.extract_text() or "")
            chars += len(text)
            lowered = text.lower()
            for term in lowered_terms:
                idx = lowered.find(term)
                if idx < 0:
                    continue
                snippet = normalize(text[max(0, idx - 260): min(len(text), idx + 760)])
                line = f"[page {page_number}] {snippet}"
                if line not in found:
                    found.append(line)
                break
            if len(found) >= limit:
                break
    return pages, chars, found


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    checks = pd.read_csv(CHECK_FILE).fillna("")
    downloads = checks[checks["download_status"] == "downloaded_open_access_pdf"].copy()
    rows = []
    report = []
    for _, item in downloads.iterrows():
        pesticide = item["pesticide"]
        doi = item["doi"]
        path = Path(item["downloaded_pdf_path"])
        report.append(f"\n# {pesticide} | {doi}\nPDF: {path}\n")
        try:
            pages, chars, snippets = snippets_for_pdf(path, pesticide)
            report.append(f"pages={pages} extracted_chars={chars} snippets={len(snippets)}\n")
            for snippet in snippets:
                report.append(f"- {snippet}\n")
            rows.append({
                "pesticide": pesticide,
                "doi": doi,
                "pdf_path": str(path),
                "pages": pages,
                "extracted_chars": chars,
                "snippet_count": len(snippets),
                "screening_status": "screened",
            })
        except Exception as exc:
            report.append(f"READ_ERROR: {exc}\n")
            rows.append({
                "pesticide": pesticide,
                "doi": doi,
                "pdf_path": str(path),
                "pages": "",
                "extracted_chars": "",
                "snippet_count": 0,
                "screening_status": f"read_error: {exc}",
            })
    (OUT_DIR / "downloaded_oa_pathway_snippets.md").write_text("\n".join(report), encoding="utf-8")
    pd.DataFrame(rows).to_csv(OUT_DIR / "downloaded_oa_pathway_screening_summary.csv", index=False)
    print(OUT_DIR)
    print(f"screened={len(rows)}")


if __name__ == "__main__":
    main()
