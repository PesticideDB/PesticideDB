from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader


PDFS = [
    Path("/Volumes/WENTBROKE/Pesticide degradation database/pesticidepdf/Ametoctradin/Accelerated Biodegradation of the Agrochemical Ametoctradin by Soil-Derived Microbial Consortia..pdf"),
    Path("/Volumes/WENTBROKE/Pesticide degradation database/pesticidepdf/Phosmet/Microbial degradation of phosmet on blueberry fruit and in aqueous systems by indigenous bacterial flora on lowbush blueberries (Vaccinium angustifolium)..pdf"),
]

NEEDLES = [
    "doi",
    "10.",
    "M650F01",
    "M650F02",
    "M650F03",
    "M650F04",
    "phthalimide",
    "phthalamic",
    "phthalic acid",
    "phosmet oxon",
    "phosphorodithioate",
]


def compact(text: str) -> str:
    return " ".join(text.split())


def main() -> None:
    for pdf in PDFS:
        print(f"FILE: {pdf.name}")
        reader = PdfReader(str(pdf))
        text = "\n".join(page.extract_text() or "" for page in reader.pages[:8])
        lowered = text.lower()
        for needle in NEEDLES:
            idx = lowered.find(needle.lower())
            print(f"NEEDLE: {needle} IDX: {idx}")
            if idx >= 0:
                print(compact(text[max(0, idx - 300):idx + 700]))
        print("---")


if __name__ == "__main__":
    main()
