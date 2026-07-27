from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader


CANDIDATES = {
    "Mandipropamid": [
        "Indigenous functional microbial degradation of the chiral fungicide mandipropamid in repeatedly treated soils Preferential changes in the R-enantiomer..pdf",
        "Insights on the isolation, identification, and degradation characteristics of three bacterial strains against mandipropamid and their application potential for polluted soil remediation..pdf",
        "The enantioselective environmental fate of mandipropamid in water-sediment microcosms Distribution, degradation, degradation pathways and toxicity assessment..pdf",
    ],
    "Pinoxaden": [
        "Degradation Characteristics of Pinoxaden by Acinetobacter and Prediction of Related Genes.pdf",
        "Aryldiones incorporating a [1,4,5]oxadiazepane ring. Part 2 chemistry and biology of the cereal herbicide pinoxaden..pdf",
    ],
    "Imazamox": [
        "Characterization of imazamox degradation by-products by using liquid chromatography mass spectrometry and high-resolution Fourier transform ion cyclotron resonance mass spectrometry..pdf",
        "Behavior of the Chiral Herbicide Imazamox in Soils pH-Dependent, Enantioselective Degradation, Formation and Degradation of Several Chiral Metabolites..pdf",
        "Behavior of the Chiral Herbicide Imazamox in Soils Enantiomer Composition Differentiates between Biodegradation and Photodegradation..pdf",
    ],
    "Thiophanate-Methyl": [
        "Biodegradation kinetics of the benzimidazole fungicide thiophanate-methyl by bacteria isolated from loamy sand soil..pdf",
        "Substrate sterilization with thiophanate-methyl and its biodegradation to carbendazim in oyster mushroom (Pleurotus ostreatus var. florida)..pdf",
        "Characterization of the ultraviolet-visible photoproducts of thiophanate-methyl using high performance liquid chromatography coupled with high resolution tandem mass spectrometry-Detection in grapes and tomatoes..pdf",
    ],
}

ROOT = Path("/Volumes/WENTBROKE/Pesticide degradation database/pesticidepdf")
OUT = Path("/Users/nana/Desktop/PepDB/PepDatabase/curation_outputs/pathway_batch4_screening_20260707")
TERMS = re.compile(
    r"metabolite|product|by-product|degradat|pathway|LC-MS|LC/MS|GC-MS|HPLC|carbendazim|MBC|"
    r"pinoxaden|imazamox|mandipropamid|thiophanate",
    re.IGNORECASE,
)


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def snippets(text: str, limit: int = 10) -> list[str]:
    found = []
    for match in TERMS.finditer(text):
        start = max(0, match.start() - 260)
        end = min(len(text), match.end() + 360)
        snippet = clean_text(text[start:end])
        if snippet and snippet not in found:
            found.append(snippet)
        if len(found) >= limit:
            break
    return found


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = []
    for pesticide, filenames in CANDIDATES.items():
        for filename in filenames:
            path = ROOT / pesticide / filename
            report.append(f"\n## {pesticide} :: {filename}\n")
            if not path.exists():
                report.append("MISSING\n")
                continue
            try:
                reader = PdfReader(str(path))
                pages = []
                for index, page in enumerate(reader.pages[:12], start=1):
                    text = clean_text(page.extract_text() or "")
                    if text:
                        pages.append(f"[page {index}] {text}")
                all_text = "\n".join(pages)
                report.append(f"pages_read={len(reader.pages)} extracted_chars={len(all_text)}\n")
                for item in snippets(all_text, 12):
                    report.append(f"- {item}\n")
            except Exception as exc:
                report.append(f"READ_ERROR: {exc}\n")
    (OUT / "candidate_snippets.md").write_text("\n".join(report), encoding="utf-8")
    print(OUT / "candidate_snippets.md")


if __name__ == "__main__":
    main()
