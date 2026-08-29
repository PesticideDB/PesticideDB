from Bio import Entrez
import time

Entrez.email = "gurungsaru634@gmail.com"

input_file = "data/accessions.txt"
output_file = "data/pbdb_reference_proteins.faa"

with open(input_file) as f:
    accessions = [line.strip() for line in f if line.strip()]

with open(output_file, "w") as out:
    for acc in accessions:
        print(f"Fetching {acc}")
        try:
            handle = Entrez.efetch(
                db="protein",
                id=acc,
                rettype="fasta",
                retmode="text"
            )
            fasta = handle.read()
            out.write(fasta)
            time.sleep(0.4)
        except Exception as e:
            print(f"Failed: {acc} | {e}")

print("Done. FASTA saved to:", output_file)