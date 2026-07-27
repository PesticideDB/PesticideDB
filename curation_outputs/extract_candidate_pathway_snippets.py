from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader


PDFS = [
    Path("/Volumes/WENTBROKE/Pesticide degradation database/pesticidepdf/Pinoxaden/Degradation Characteristics of Pinoxaden by Acinetobacter and Prediction of Related Genes.pdf"),
    Path("/Volumes/WENTBROKE/Pesticide degradation database/pesticidepdf/Propamocarb/Microbial degradation of the carbamate pesticides desmedipham, phenmedipham, promecarb, and propamocarb..pdf"),
    Path("/Volumes/WENTBROKE/Pesticide degradation database/pesticidepdf/Isopyrazam/Fungicide isopyrazam degradative response toward extrinsically added fungal and bacterial strains..pdf"),
    Path("/Volumes/WENTBROKE/Pesticide degradation database/pesticidepdf/Fluxapyroxad/Dissipation kinetics and biological degradation by yeast and dietary risk assessment of fluxapyroxad in apples..pdf"),
    Path("/Volumes/WENTBROKE/Pesticide degradation database/pesticidepdf/Spirodiclofen/Enhanced degradation of spiro-insecticides and their leacher enol derivatives in soil by solarization and biosolarization techniques..pdf"),
]

NEEDLES = [
    "doi",
    "10.",
    "metabolite",
    "product",
    "intermediate",
    "pathway",
    "identified",
    "LC-MS",
    "HPLC-MS",
    "degradation product",
    "transformation product",
    "strain",
    "Acinetobacter",
    "yeast",
    "fungal",
    "bacterial",
]


def compact(text: str) -> str:
    return " ".join(text.split())


def main() -> None:
    for pdf in PDFS:
        print(f"FILE: {pdf}")
        if not pdf.exists():
            print("MISSING")
            print("---")
            continue
        reader = PdfReader(str(pdf))
        text = "\n".join(page.extract_text() or "" for page in reader.pages[:15])
        lowered = text.lower()
        for needle in NEEDLES:
            idx = lowered.find(needle.lower())
            if idx >= 0:
                print(f"NEEDLE: {needle}")
                print(compact(text[max(0, idx - 350):idx + 900]))
        print("---")


if __name__ == "__main__":
    main()
