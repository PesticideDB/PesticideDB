from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pdfplumber


PROJECT_ROOT = Path("/Users/nana/Desktop/PepDB/PepDatabase")
CHECK_FILE = PROJECT_ROOT / "PesticideDB_Priority1_Open_Access_Check.csv"
OUT_DIR = PROJECT_ROOT / "curation_outputs" / "priority1_oa_pathway_screening_20260708"
OUT_CSV = OUT_DIR / "priority1_oa_candidate_transformations.csv"


SEARCH_TERMS = {
    "Acetamiprid": [
        "N-methyl-(6-chloro-3-pyridyl)methylamine",
        "degradation pathway",
        "metabolic intermediate",
    ],
    "Chlorothalonil": [
        "4-hydroxy-2,5,6-trichloroisophthalonitrile",
        "hydroxy-2,5,6-trichloroisophthalonitrile",
        "TPN-OH",
        "hydrolytic dehalogenase",
    ],
    "DDT": ["DDD", "DDE", "DDMU", "dehydrochlorinase", "degradation pathway"],
    "Endosulfan": [
        "endosulfan sulfate",
        "endosulfan diol",
        "endosulfan ether",
        "endosulfan lactone",
        "degradation pathway",
    ],
    "Malathion": [
        "malaoxon",
        "malathion monocarboxylic acid",
        "malathion dicarboxylic acid",
        "carboxylesterase",
        "degradation pathway",
    ],
    "Dichlorvos": ["dimethyl phosphate", "dichloroacetaldehyde", "degradation pathway"],
    "Glyphosate": ["AMPA", "sarcosine", "C-P lyase", "glyphosate oxidoreductase"],
    "Imidacloprid": ["6-chloronicotinic acid", "nitroso", "olefin", "degradation pathway"],
    "Paraquat": ["insoluble product", "crystals", "anaerobic transformation"],
}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def snippets_for_pdf(pdf_path: Path, terms: list[str]) -> str:
    snippets: list[str] = []
    lowered_terms = [term.lower() for term in terms]
    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text = normalize(page.extract_text() or "")
            lowered = text.lower()
            for term in lowered_terms:
                idx = lowered.find(term)
                if idx < 0:
                    continue
                start = max(0, idx - 260)
                end = min(len(text), idx + 520)
                snippets.append(f"p{page_number}: {text[start:end]}")
                break
    return "\n---\n".join(snippets[:8])


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    checks = pd.read_csv(CHECK_FILE)
    rows = []
    for _, record in checks.iterrows():
        if str(record.get("download_status", "")).lower() != "downloaded_open_access_pdf":
            continue
        pesticide = str(record.get("pesticide", "")).strip()
        terms = SEARCH_TERMS.get(pesticide)
        if not terms:
            continue
        pdf_path = Path(str(record.get("downloaded_pdf_path", "")).strip())
        if not pdf_path.exists():
            continue
        rows.append({
            "pesticide": pesticide,
            "doi": record.get("doi", ""),
            "title": record.get("title", ""),
            "pdf_path": str(pdf_path),
            "candidate_snippets": snippets_for_pdf(pdf_path, terms),
        })
    pd.DataFrame(rows).to_csv(OUT_CSV, index=False)
    print(f"screened={len(rows)}")
    print(OUT_CSV)


if __name__ == "__main__":
    main()
