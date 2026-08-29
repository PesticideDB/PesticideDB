from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError


PDFS = [
    Path("/Volumes/WENTBROKE/Pesticide degradation database/pesticidepdf/Glufosinate-Ammonium/Initial steps in the degradation of phosphinothricin (glufosinate) by soil bacteria..pdf"),
    Path("/Volumes/WENTBROKE/Pesticide degradation database/pesticidepdf/Quintozene/Biodegradation of pentachloronitrobenzene by Arthrobacter nicotianae DH19..pdf"),
    Path("/Volumes/WENTBROKE/Pesticide degradation database/pesticidepdf/Quintozene/Biodegradation of pentachloronitrobenzene by Cupriavidus sp. YNS-85 and its potential for remediation of contaminated soils..pdf"),
    Path("/Volumes/WENTBROKE/Pesticide degradation database/pesticidepdf/Quintozene/Effective biodegradation of pentachloronitrobenzene by a novel strain Peudomonas putida QTH3 isolated from contaminated soil..pdf"),
    Path("/Volumes/WENTBROKE/Pesticide degradation database/pesticidepdf/Kresoxim-Methyl/Detoxification Esterase StrH Initiates Strobilurin Fungicide Degradation in iHyphomicrobiumi sp. Strain DY-1..pdf"),
    Path("/Volumes/WENTBROKE/Pesticide degradation database/pesticidepdf/Kresoxim-Methyl/Degradation and metabolic profiling for benzene kresoxim-methyl using carbon-14 tracing..pdf"),
]

NEEDLES = [
    "doi",
    "10.",
    "pathway",
    "metabolite",
    "product",
    "intermediate",
    "identified",
    "glufosinate",
    "phosphinothricin",
    "MPP",
    "3-methylphosphinicopropionic acid",
    "2-oxo",
    "pentachloronitrobenzene",
    "PCNB",
    "pentachloroaniline",
    "PCA",
    "pentachlorothioanisole",
    "PCTA",
    "pentachlorophenol",
    "Arthrobacter",
    "Cupriavidus",
    "Pseudomonas",
    "kresoxim",
    "kresoxim-methyl acid",
    "parent acid",
    "StrH",
    "strH",
]


def compact(text: str) -> str:
    return " ".join(text.split())


def main() -> None:
    out_dir = Path("/Users/nana/Desktop/PepDB/PepDatabase/curation_outputs/batch8_pathway_snippets_20260708")
    out_dir.mkdir(parents=True, exist_ok=True)
    report = []
    for pdf in PDFS:
        report.append(f"# {pdf.parent.name} | {pdf.name}\n")
        if not pdf.exists():
            report.append("MISSING\n\n---\n")
            continue
        try:
            reader = PdfReader(str(pdf))
            text = "\n".join(page.extract_text() or "" for page in reader.pages[:20])
        except (PdfReadError, OSError, ValueError) as exc:
            report.append(f"UNREADABLE: {exc}\n\n---\n")
            continue
        lowered = text.casefold()
        seen = set()
        for needle in NEEDLES:
            idx = lowered.find(needle.casefold())
            if idx < 0:
                continue
            snippet = compact(text[max(0, idx - 500): idx + 1400])
            if snippet in seen:
                continue
            seen.add(snippet)
            report.append(f"\n## {needle}\n{snippet}\n")
        report.append("\n---\n")
    out = out_dir / "batch8_pathway_snippets.md"
    out.write_text("\n".join(report), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
