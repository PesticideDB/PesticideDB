import pandas as pd
from Bio import SeqIO
import os
import re

metadata_file = "data/PBDB_master.xlsx"
fasta_file = "data/pbdb_reference_proteins.faa"
output_dir = "hmmer_db/families"

os.makedirs(output_dir, exist_ok=True)

db = pd.read_excel(metadata_file)
db.columns = db.columns.str.strip()

# Keep only rows with protein accession and enzyme_class
db = db.dropna(subset=["ncbi_protein_accession", "enzyme_class"])

# Clean values
db["ncbi_protein_accession"] = db["ncbi_protein_accession"].astype(str).str.strip()
db["enzyme_class"] = db["enzyme_class"].astype(str).str.strip()

# Read FASTA sequences into dictionary
# Read FASTA sequences into dictionary, ignoring duplicates
seq_records = {}

for record in SeqIO.parse(fasta_file, "fasta"):
    accession = record.id.strip()

    if accession not in seq_records:
        seq_records[accession] = record

def clean_name(name):
    name = name.lower()
    name = re.sub(r"[^a-z0-9]+", "_", name)
    name = name.strip("_")
    return name

created = 0

for enzyme_class, group in db.groupby("enzyme_class"):
    family_name = clean_name(enzyme_class)
    output_file = os.path.join(output_dir, f"{family_name}.faa")

    with open(output_file, "w") as out:
        count = 0

        for _, row in group.iterrows():
            accession = row["ncbi_protein_accession"]

            if accession in seq_records:
                record = seq_records[accession]
                SeqIO.write(record, out, "fasta")
                count += 1

        if count > 0:
            print(f"Created {output_file} with {count} sequences")
            created += 1

print(f"Done. Created {created} family FASTA files.")