from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError


USB_ROOT = Path("/Volumes/WENTBROKE/Pesticide degradation database/pesticidepdf")

TARGETS = [
    ("carbaryl", "Compartmentalization_of_the_Carbaryl_Degradation_Pathway"),
    ("carbaryl", "Metabolism_of_carbaryl_via_1_2_dihydroxynaphthalene"),
    ("Chlorothalonil", "A_novel_hydrolytic_dehalogenase"),
    ("Dicamba", "A_Tetrahydrofolate_Dependent_Methyltransferase"),
    ("Dicamba", "A_Three_Component_Enzyme_System"),
    ("Dichlobenil", "Degradation_and_mineralization_of_nanomolar_concentrations"),
    ("Dichlobenil", "Fungal_degradation_of_aromatic_nitriles"),
    ("Cyromazine", "Biodegradation_of_cyromazine_by_melamine_degrading_bacteria"),
    ("Cyromazine", "Bacterial_degradation_of_N_cyclopropylmelamine"),
    ("Trifloxystrobin", "Detoxification Esterase StrH"),
    ("Pyraclostrobin", "Detoxification_Esterase_StrH"),
    ("Propiconazole", "Biodegradation_of_propiconazole_by_newly_isolated_Burkholderia"),
    ("Carbendazim", "Complete_Genome_Sequence_of_Carbendazim_Degrading"),
    ("Carbendazim", "Microbes_as_carbendazim_degraders"),
]

NEEDLES = [
    "doi",
    "10.",
    "pathway",
    "metabolite",
    "product",
    "intermediate",
    "identified",
    "gene",
    "enzyme",
    "hydrolase",
    "dehalogenase",
    "methyltransferase",
    "carbaryl",
    "1-naphthol",
    "1,2-dihydroxynaphthalene",
    "salicylate",
    "chlorothalonil",
    "4-hydroxy",
    "dicamba",
    "3,6-dichlorosalicylate",
    "dichlobenil",
    "2,6-dichlorobenzamide",
    "2,6-dichlorobenzoic acid",
    "cyromazine",
    "melamine",
    "ammeline",
    "trifloxystrobin acid",
    "pyraclostrobin",
    "propiconazole",
    "carbendazim",
]


def compact(text: str) -> str:
    return " ".join(text.split())


def find_pdf(folder: str, token: str) -> Path | None:
    candidates = list((USB_ROOT / folder).glob("*.pdf"))
    token_l = token.casefold()
    for path in candidates:
        if token_l in path.name.casefold():
            return path
    return None


def main() -> None:
    out_dir = Path("/Users/nana/Desktop/PepDB/PepDatabase/curation_outputs/high_value_pathway_snippets_20260707")
    out_dir.mkdir(parents=True, exist_ok=True)
    report = []
    for folder, token in TARGETS:
        pdf = find_pdf(folder, token)
        report.append(f"# {folder} | {token}\n")
        if not pdf:
            report.append("MISSING\n\n---\n")
            continue
        report.append(f"PDF: {pdf.name}\n")
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
            snippet = compact(text[max(0, idx - 400): idx + 1000])
            if snippet in seen:
                continue
            seen.add(snippet)
            report.append(f"\n## {needle}\n{snippet}\n")
        report.append("\n---\n")
    path = out_dir / "high_value_pathway_snippets.md"
    path.write_text("\n".join(report), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
