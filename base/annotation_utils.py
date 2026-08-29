from pathlib import Path
import re

import pandas as pd

from .models import ProteinRecord


DIAMOND_COLUMNS = [
    "query",
    "diamond_hit_id",
    "identity",
    "alignment_length",
    "diamond_evalue",
    "bitscore",
    "query_coverage",
    "subject_coverage",
    "similarity",
]


def detect_fasta_sequence_type(fasta_path):
    """Return dna, protein, or empty based on FASTA sequence characters."""
    text = Path(fasta_path).read_text(errors="ignore")
    sequence = "".join(
        line.strip()
        for line in text.splitlines()
        if not line.startswith(">")
    )

    if not sequence:
        return "empty"

    letters = [char.upper() for char in sequence if char.isalpha()]
    if not letters:
        return "empty"

    dna_letters = sum(1 for char in letters if char in "ATGCN")
    dna_ratio = dna_letters / len(letters)
    return "dna" if dna_ratio >= 0.90 else "protein"


def format_evalue(value):
    if pd.isna(value):
        return "-"

    try:
        return f"{float(value):.2e}"
    except (TypeError, ValueError):
        return str(value)


def family_confidence(size):
    if size >= 10:
        return "HIGH"
    if size >= 5:
        return "MEDIUM"
    if size >= 3:
        return "LOW"
    return "VERY LOW"


def parse_query_headers(fasta_path):
    path = Path(fasta_path) if fasta_path else None
    if not path or not path.exists():
        return {}

    headers = {}
    for line in path.read_text(errors="ignore").splitlines():
        if not line.startswith(">"):
            continue
        header = line[1:].strip()
        query_id = header.split()[0] if header else ""
        if query_id:
            headers[query_id] = header
    return headers


def extract_bracket_value(header, key):
    if not header:
        return ""
    match = re.search(rf"\[{re.escape(key)}=([^\]]+)\]", header)
    return match.group(1).strip() if match else ""


def query_product_from_header(header):
    product = extract_bracket_value(header, "protein")
    if product:
        return product

    parts = str(header or "").split(maxsplit=1)
    if len(parts) == 2:
        return parts[1].strip()
    return ""


def query_is_pseudo(header):
    return extract_bracket_value(header, "pseudo").lower() == "true"


def parse_float(value):
    try:
        if pd.isna(value):
            return None
        text = str(value).strip()
        if not text or text == "-":
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def parse_int(value):
    number = parse_float(value)
    return int(number) if number is not None else None


def normalize_function_label(value):
    text = str(value or "").strip().lower()
    if not text or text == "-":
        return ""

    groups = {
        "dehalogenase": ["dehalogenase", "dehydrochlorinase", "halidohydrolase"],
        "oxidoreductase": ["oxidoreductase", "reductase", "dehydrogenase", "oxygenase", "monooxygenase", "dioxygenase"],
        "hydrolase": ["hydrolase", "esterase", "amidase", "nitrilase", "aminohydrolase", "chlorohydrolase"],
        "transferase": ["transferase"],
        "lyase": ["lyase"],
        "isomerase": ["isomerase"],
    }
    for canonical, terms in groups.items():
        if any(term in text for term in terms):
            return canonical
    return text


def hmmer_agrees_with_diamond(enzyme_class, hmmer_family):
    diamond_label = normalize_function_label(enzyme_class)
    hmmer_label = normalize_function_label(hmmer_family)
    if not diamond_label or not hmmer_label:
        return None
    return diamond_label == hmmer_label


def confidence_badge(identity, alignment_length, enzyme_class, hmmer_family, hmmer_evalue, pseudo):
    identity_value = parse_float(identity)
    alignment_value = parse_int(alignment_length)
    hmmer_evalue_value = parse_float(hmmer_evalue)
    agreement = hmmer_agrees_with_diamond(enzyme_class, hmmer_family)

    if agreement is False:
        return "CONFLICT"
    if pseudo:
        return "LOW"
    if identity_value is None:
        return "LOW"
    if identity_value < 30 or (alignment_value is not None and alignment_value < 100):
        return "LOW"
    if (
        identity_value >= 40
        and (alignment_value is None or alignment_value >= 100)
        and agreement is not False
        and (hmmer_evalue_value is None or hmmer_evalue_value <= 1e-5)
    ):
        return "HIGH"
    if identity_value >= 35 or agreement is True:
        return "MEDIUM"
    return "LOW"


def interpretation_for_hit(row):
    query_product = str(row.get("query_product") or "").strip()
    pseudo = str(row.get("pseudo_flag") or "").strip().lower() == "yes"
    enzyme_class = row.get("enzyme_class")
    hmmer_family = row.get("hmmer_family")
    identity = row.get("identity")
    alignment_length = row.get("alignment_length")
    hmmer_evalue = row.get("hmmer_evalue")
    confidence = confidence_badge(
        identity,
        alignment_length,
        enzyme_class,
        hmmer_family,
        hmmer_evalue,
        pseudo,
    )

    warnings = []
    identity_value = parse_float(identity)
    alignment_value = parse_int(alignment_length)
    agreement = hmmer_agrees_with_diamond(enzyme_class, hmmer_family)

    if pseudo:
        warnings.append("Query is marked as pseudo; functional interpretation may not be valid.")
    if identity_value is not None and identity_value < 30:
        warnings.append("DIAMOND identity is below 30%; this is a distant similarity hit.")
    elif identity_value is not None and identity_value < 35:
        warnings.append("DIAMOND identity is near the twilight zone; verify manually.")
    if alignment_value is not None and alignment_value < 100:
        warnings.append("Alignment length is short; annotation may be partial.")
    if agreement is False:
        warnings.append("DIAMOND closest-hit class and HMMER family disagree.")
    if not str(hmmer_family or "").strip() or str(hmmer_family).strip() == "-":
        warnings.append("No HMMER family support is available.")

    closest = str(row.get("reported_protein_name") or "-").strip()
    pesticide = str(row.get("pesticide") or "-").strip()
    if confidence == "CONFLICT":
        final = (
            f"Conflicting candidate hit. Closest PesticideDB hit is {closest} for {pesticide}, "
            f"but HMMER supports {hmmer_family or '-'}."
        )
    elif confidence == "HIGH":
        final = f"High-confidence candidate similar to {closest}; still requires experimental validation for the uploaded organism."
    elif confidence == "MEDIUM":
        final = f"Medium-confidence candidate similar to {closest}; verify coverage, family support, and substrate context."
    else:
        final = f"Low-confidence candidate similarity to {closest}; do not treat as confirmed functional assignment."

    if query_product:
        final = f"Original query product: {query_product}. {final}"

    return confidence, " | ".join(warnings) if warnings else "-", final


def clean_hit_id(raw_hit):
    value = str(raw_hit or "").strip()
    parts = value.split("|")

    if len(parts) >= 2 and parts[0] in {"sp", "tr", "ref", "gb", "emb", "dbj"}:
        value = parts[1]
    elif parts:
        value = parts[0]

    return value.strip()


def accession_keys(value):
    clean = clean_hit_id(value)
    keys = {clean.lower()}
    if "." in clean:
        keys.add(clean.split(".")[0].lower())
    return {key for key in keys if key}


def build_protein_lookup():
    lookup = {}
    family_sizes = {}

    for protein in ProteinRecord.objects.all():
        enzyme_class = (protein.enzyme_class or "").strip()
        if enzyme_class:
            family_sizes[enzyme_class] = family_sizes.get(enzyme_class, 0) + 1

        identifiers = [
            protein.ncbi_protein_accession,
            protein.uniprot_accession,
            protein.pesticidedb_protein_id,
            protein.pbdb_protein_id,
        ]

        for identifier in identifiers:
            for key in accession_keys(identifier):
                lookup.setdefault(key, protein)

    return lookup, family_sizes


def clean_cell(value):
    if pd.isna(value):
        return ""

    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def load_master_metadata(master_path):
    path = Path(master_path)
    if not path.exists():
        return {}

    df = pd.read_excel(path)
    df.columns = df.columns.str.strip()
    metadata = {}

    for _, row in df.iterrows():
        accession = clean_cell(row.get("ncbi_protein_accession"))
        if not accession:
            continue

        record = {
            "pesticidedb_protein_id": clean_cell(row.get("pesticidedb_protein_id")) or "-",
            "protein_detail_id": "-",
            "ncbi_protein_accession": accession,
            "reported_protein_name": clean_cell(row.get("reported_protein_name")) or "-",
            "enzyme_class": clean_cell(row.get("enzyme_class")) or "-",
            "gene_name": clean_cell(row.get("gene_name")) or "-",
            "microorganism": clean_cell(row.get("microorganism")) or "-",
            "pesticide": clean_cell(row.get("pesticide")) or "-",
            "evidence_type": clean_cell(row.get("evidence_type")) or "-",
            "year": clean_cell(row.get("year")) or "-",
            "doi": clean_cell(row.get("doi")) or "-",
            "collection_category": clean_cell(row.get("collection_category")) or "-",
        }

        for key in accession_keys(accession):
            metadata.setdefault(key, record)

    return metadata


def load_reference_headers(reference_fasta_path):
    path = Path(reference_fasta_path)
    if not path.exists():
        return {}

    headers = {}
    for line in path.read_text(errors="ignore").splitlines():
        if not line.startswith(">"):
            continue

        header = line[1:].strip()
        accession = header.split()[0]
        description = " ".join(header.split()[1:]).strip()
        record = {
            "pesticidedb_protein_id": "-",
            "protein_detail_id": "-",
            "ncbi_protein_accession": accession,
            "reported_protein_name": description or "-",
            "enzyme_class": "-",
            "gene_name": "-",
            "microorganism": "-",
            "pesticide": "-",
            "evidence_type": "-",
            "year": "-",
            "doi": "-",
            "collection_category": "REFERENCE_FASTA",
        }

        for key in accession_keys(accession):
            headers.setdefault(key, record)

    return headers


def load_hmmer_hits(hmmer_tbl_path):
    path = Path(hmmer_tbl_path)
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=["query", "hmmer_family", "hmmer_evalue"])

    try:
        hmmer = pd.read_csv(
            path,
            comment="#",
            sep=r"\s+",
            header=None,
            usecols=[0, 2, 4],
            names=["hmmer_family", "query", "hmmer_evalue"],
        )
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=["query", "hmmer_family", "hmmer_evalue"])

    if hmmer.empty:
        return pd.DataFrame(columns=["query", "hmmer_family", "hmmer_evalue"])

    hmmer["hmmer_evalue_numeric"] = pd.to_numeric(
        hmmer["hmmer_evalue"],
        errors="coerce",
    )
    hmmer = (
        hmmer.sort_values("hmmer_evalue_numeric", na_position="last")
        .drop_duplicates("query")
    )
    hmmer["hmmer_family"] = (
        hmmer["hmmer_family"]
        .astype(str)
        .str.replace("_aligned", "", regex=False)
    )
    return hmmer[["query", "hmmer_family", "hmmer_evalue"]]


def annotate_diamond_hits(
    diamond_tsv_path,
    output_csv_path,
    hmmer_tbl_path=None,
    master_metadata_path=None,
    reference_fasta_path=None,
    query_fasta_path=None,
    review_identity=25,
    review_evalue=1e-3,
    review_query_coverage=30,
):
    diamond_path = Path(diamond_tsv_path)
    if not diamond_path.exists() or diamond_path.stat().st_size == 0:
        return 0

    diamond = pd.read_csv(
        diamond_path,
        sep="\t",
        header=None,
        names=DIAMOND_COLUMNS,
    )

    if diamond.empty:
        return 0

    diamond["bitscore"] = pd.to_numeric(diamond["bitscore"], errors="coerce").fillna(0)
    diamond["identity"] = pd.to_numeric(diamond["identity"], errors="coerce")
    diamond["alignment_length"] = pd.to_numeric(diamond["alignment_length"], errors="coerce")
    diamond["query_coverage"] = pd.to_numeric(
        diamond["query_coverage"], errors="coerce"
    )
    diamond["subject_coverage"] = pd.to_numeric(
        diamond["subject_coverage"], errors="coerce"
    )
    diamond["similarity"] = pd.to_numeric(diamond["similarity"], errors="coerce")
    diamond["diamond_evalue_numeric"] = pd.to_numeric(
        diamond["diamond_evalue"], errors="coerce"
    )
    diamond = (
        diamond.sort_values(["query", "bitscore", "identity"], ascending=[True, False, False])
        .drop_duplicates(["query", "diamond_hit_id"])
    )
    diamond["match_rank"] = diamond.groupby("query").cumcount() + 1

    lookup, family_sizes = build_protein_lookup()
    master_metadata = load_master_metadata(master_metadata_path) if master_metadata_path else {}
    reference_headers = load_reference_headers(reference_fasta_path) if reference_fasta_path else {}
    query_headers = parse_query_headers(query_fasta_path)
    rows = []

    for _, hit in diamond.iterrows():
        protein = None
        fallback = None
        for key in accession_keys(hit["diamond_hit_id"]):
            protein = lookup.get(key)
            if protein:
                break
            fallback = master_metadata.get(key) or reference_headers.get(key) or fallback

        if not protein and not fallback:
            continue

        if protein:
            display_id = protein.pesticidedb_protein_id or protein.pbdb_protein_id or "-"
            detail_id = display_id
            ncbi_accession = protein.ncbi_protein_accession or "-"
            reported_protein = protein.reported_protein_name or "-"
            enzyme_class = protein.enzyme_class or "-"
            gene_name = protein.gene_name or "-"
            microorganism = protein.microorganism or "-"
            pesticide = protein.pesticide or "-"
            evidence_type = protein.evidence_type or "-"
            year = protein.year or "-"
            doi = protein.doi or "-"
            collection_category = protein.collection_category or "-"
        else:
            display_id = fallback["pesticidedb_protein_id"]
            detail_id = fallback["protein_detail_id"]
            ncbi_accession = fallback["ncbi_protein_accession"]
            reported_protein = fallback["reported_protein_name"]
            enzyme_class = fallback["enzyme_class"]
            gene_name = fallback["gene_name"]
            microorganism = fallback["microorganism"]
            pesticide = fallback["pesticide"]
            evidence_type = fallback["evidence_type"]
            year = fallback["year"]
            doi = fallback["doi"]
            collection_category = fallback["collection_category"]

        size = family_sizes.get(enzyme_class, 0)

        query_id = str(hit["query"])
        query_header = query_headers.get(query_id, "")
        query_product = query_product_from_header(query_header)
        pseudo_flag = "Yes" if query_is_pseudo(query_header) else "No"
        meets_review_criteria = (
            pd.notna(hit["identity"])
            and float(hit["identity"]) >= float(review_identity)
            and pd.notna(hit["diamond_evalue_numeric"])
            and float(hit["diamond_evalue_numeric"]) <= float(review_evalue)
            and pd.notna(hit["query_coverage"])
            and float(hit["query_coverage"]) >= float(review_query_coverage)
        )

        rows.append({
            "query": hit["query"],
            "match_rank": int(hit["match_rank"]),
            "is_best_match": "Yes" if int(hit["match_rank"]) == 1 else "No",
            "query_product": query_product or "-",
            "pseudo_flag": pseudo_flag,
            "pesticidedb_protein_id": display_id,
            "protein_detail_id": detail_id,
            "ncbi_protein_accession": ncbi_accession,
            "reported_protein_name": reported_protein,
            "identity": round(float(hit["identity"]), 2) if pd.notna(hit["identity"]) else "-",
            "similarity": (
                round(float(hit["similarity"]), 2)
                if pd.notna(hit["similarity"])
                else "-"
            ),
            "alignment_length": hit["alignment_length"],
            "query_coverage": (
                round(float(hit["query_coverage"]), 2)
                if pd.notna(hit["query_coverage"])
                else "-"
            ),
            "subject_coverage": (
                round(float(hit["subject_coverage"]), 2)
                if pd.notna(hit["subject_coverage"])
                else "-"
            ),
            "diamond_evalue": format_evalue(hit["diamond_evalue"]),
            "bitscore": round(float(hit["bitscore"]), 2),
            "passes_screening_thresholds": "Yes" if meets_review_criteria else "No",
            "review_identity_min": review_identity,
            "review_evalue_max": review_evalue,
            "review_query_coverage_min": review_query_coverage,
            "enzyme_class": enzyme_class,
            "gene_name": gene_name,
            "microorganism": microorganism,
            "pesticide": pesticide,
            "evidence_type": evidence_type,
            "year": year,
            "doi": doi,
            "collection_category": collection_category,
            "family_size": size or "-",
            "family_confidence": family_confidence(size) if size else "-",
        })

    result = pd.DataFrame(rows)
    if result.empty:
        return 0

    if hmmer_tbl_path:
        hmmer = load_hmmer_hits(hmmer_tbl_path)
        result = result.merge(hmmer, on="query", how="left")
        if "hmmer_evalue" in result.columns:
            result["hmmer_evalue"] = result["hmmer_evalue"].apply(format_evalue)

    if "hmmer_family" not in result.columns:
        result["hmmer_family"] = "-"
    if "hmmer_evalue" not in result.columns:
        result["hmmer_evalue"] = "-"

    interpretations = result.apply(interpretation_for_hit, axis=1)
    result["interpretation_confidence"] = [item[0] for item in interpretations]
    result["interpretation_warnings"] = [item[1] for item in interpretations]
    result["final_interpretation"] = [item[2] for item in interpretations]

    result.to_csv(output_csv_path, index=False)
    return len(result)


def read_annotation_results(csv_path):
    df = pd.read_csv(csv_path)

    for column in ["diamond_evalue", "hmmer_evalue"]:
        if column in df.columns:
            df[column] = df[column].apply(format_evalue)

    return df


def write_best_match_results(all_matches_csv_path, best_matches_csv_path):
    results = pd.read_csv(all_matches_csv_path)
    if "match_rank" in results.columns:
        results = results[results["match_rank"] == 1]
    else:
        results = results.drop_duplicates("query")
    results.to_csv(best_matches_csv_path, index=False)
    return len(results)
