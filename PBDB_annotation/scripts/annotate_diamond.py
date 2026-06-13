import os
import sys
import django
import pandas as pd

BASE_DIR = "/Users/nana/Desktop/PepDB/PepDatabase"
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "PepDatabase.settings")
django.setup()

from base.models import ProteinRecord

# Load DIAMOND output
diamond = pd.read_csv(
    "results/diamond_results.tsv",
    sep="\t",
    header=None,
    names=[
        "query",
        "ncbi_protein_accession",
        "identity",
        "length",
        "diamond_evalue",
        "bitscore"
    ]
)

# Load your Excel database file
db = pd.read_excel("data/PBDB_master.xlsx")

# Clean column names
db.columns = db.columns.str.strip()

# Keep the real PesticideDB Protein ID already stored in database file
db["pesticidedb_protein_id"] = db["pesticidedb_protein_id"].astype(str).str.strip()

# ---- ADD HERE ----
family_sizes = db.groupby("enzyme_class").size().to_dict()

db["family_size"] = db["enzyme_class"].map(family_sizes)

def assign_conf(size):
    if size >= 10:
        return "HIGH"
    elif size >= 5:
        return "MEDIUM"
    elif size >= 3:
        return "LOW"
    else:
        return "VERY LOW"

db["family_confidence"] = db["family_size"].apply(assign_conf)
# ------------------

# Clean column names
db.columns = db.columns.str.strip()

# Clean accession values
diamond["ncbi_protein_accession"] = diamond["ncbi_protein_accession"].astype(str).str.strip()
db["ncbi_protein_accession"] = db["ncbi_protein_accession"].astype(str).str.strip()

# Merge DIAMOND result with your database
merged = diamond.merge(db, on="ncbi_protein_accession", how="left")

# Select best hit per query
best_hits = (
    merged
    .sort_values(["identity", "bitscore"], ascending=[False, False])
    .drop_duplicates("query")
)

def get_real_protein_id(accession):
    accession = str(accession).strip()

    protein = ProteinRecord.objects.filter(
        ncbi_protein_accession__iexact=accession
    ).first()

    if protein:
        return protein.pesticidedb_protein_id or protein.pbdb_protein_id or "-"

    return "-"

best_hits["pesticidedb_protein_id"] = best_hits["ncbi_protein_accession"].apply(get_real_protein_id)
# Final selected columns
final = best_hits[
    [
        "query",
        "ncbi_protein_accession",
        "identity",
        "diamond_evalue",
        "bitscore",
        "pesticidedb_protein_id",
        "pesticide",
        "microorganism",
        "enzyme_class",
        "reported_protein_name",
        "gene_name",
        "evidence_type",
        "year",
        "doi",
        "collection_category",
        "family_size",
        "family_confidence"
    ]
]

# Save final annotation
final.to_csv("results/final_annotation.csv", index=False)

print("✅ Annotation complete → results/final_annotation.csv")