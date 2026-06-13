import pandas as pd

# Load DIAMOND annotated result
diamond = pd.read_csv("results/final_annotation.csv")

# Load HMMER result
hmmer = pd.read_csv(
    "results/hmmer_results.tbl",
    comment="#",
    sep=r"\s+",
    header=None,
    usecols=[0, 2, 4],
    names=["hmmer_family", "query", "hmmer_evalue"]
)

# Keep best HMMER hit per query
hmmer = hmmer.sort_values("hmmer_evalue").drop_duplicates("query")

# Clean HMMER family name
hmmer["hmmer_family"] = (
    hmmer["hmmer_family"]
    .astype(str)
    .str.replace("_aligned", "", regex=False)
)

# Merge DIAMOND + HMMER
merged = diamond.merge(hmmer, on="query", how="left")

# Save final result
merged.to_csv("results/final_annotation_with_hmmer.csv", index=False)

print("✅ Final combined annotation saved → results/final_annotation_with_hmmer.csv")