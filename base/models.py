from django.db import models
from django.db.models.functions import Lower


class Pesticide(models.Model):
    """
    Represents biodegradation evidence records.
    IMPORTANT: This table is record-level, so duplicates by pesticide name are allowed.
    (e.g., DDT can appear many times with different microbes/papers)
    """

    pesticide = models.CharField(max_length=200, db_index=True)

    microorganism = models.CharField(max_length=200, blank=True, null=True)
    gene = models.CharField(max_length=200, blank=True, null=True)

    # Enzyme family/class (broad) from your Excel "Enzyme" column
    enzyme = models.CharField(max_length=200, blank=True, null=True)

    # Specific enzyme name reported in the paper (your Excel "Enzyme_name_reported")
    enzyme_name_reported = models.CharField(max_length=255, blank=True, null=True)

    evidence_by_microbe = models.TextField(blank=True, null=True)

    # Keep this field if you want (optional): enzyme-level evidence text
    evidence_of_enzyme = models.TextField(blank=True, null=True)

    isolation_environment = models.CharField(max_length=255, blank=True, null=True)
    isolation_location = models.CharField(max_length=200, blank=True, null=True)

    degradation_time_days = models.CharField(max_length=100, blank=True, null=True)

    publication_year = models.IntegerField(blank=True, null=True)
    reference = models.TextField(blank=True, null=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["pesticide", "microorganism"]
        # ✅ NO unique constraint here (duplicates are allowed)

    def __str__(self):
        parts = [self.pesticide]
        if self.microorganism:
            parts.append(f"→ {self.microorganism}")
        if self.publication_year:
            parts.append(f"[{self.publication_year}]")
        return " ".join(parts)


class NoEvidencePesticide(models.Model):
    """
    Pesticides searched in literature for which NO biodegradation evidence was found.
    This is list-level, so duplicates are NOT useful.
    """

    pesticide = models.CharField(max_length=200, db_index=True)
    evidence_of_biodegradation = models.CharField(
        max_length=255,
        default="No experimental biodegradation evidence found",
    )

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["pesticide"]
        # ✅ Keep unique constraint removed

    def __str__(self):
        return self.pesticide


class DataSubmission(models.Model):
    """
    User-submitted biodegradation data (curated later).
    """

    pesticide = models.CharField(max_length=200, db_index=True)
    microorganism_name = models.CharField(max_length=200, db_index=True)

    protein = models.CharField(max_length=200, blank=True, null=True)
    gene = models.CharField(max_length=200, blank=True, null=True)

    evidence = models.TextField()
    doi = models.CharField(max_length=300)
    email = models.EmailField(max_length=150)

    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.pesticide} – {self.microorganism_name}"


# =========================
# ✅ NEW: Protein section (MVP)
# =========================

class ProteinRecord(models.Model):
    """
    Protein module (MVP):
    - One row = one paper-context record (duplicates allowed)
    - Preserves import order via Meta ordering on id
    """

    pesticide = models.CharField(max_length=255, blank=True, null=True)
    microorganism = models.CharField(max_length=255, blank=True, null=True)

    evidence_type = models.CharField(max_length=255, blank=True, null=True)
    enzyme_class = models.CharField(max_length=255, blank=True, null=True)
    reported_protein_name = models.CharField(max_length=255, blank=True, null=True)

    # ✅ NEW (display / future stable ID you want to use)
    pesticidedb_protein_id = models.CharField(max_length=50, blank=True, null=True, db_index=True)

    # ✅ Keep existing field (DO NOT remove - avoids breaking existing data/pages)
    pbdb_protein_id = models.CharField(max_length=50, blank=True, null=True, db_index=True)

    gene_name = models.CharField(max_length=255, blank=True, null=True)
    year = models.IntegerField(blank=True, null=True)
    doi = models.CharField(max_length=255, blank=True, null=True)

    ncbi_protein_accession = models.CharField(max_length=255, blank=True, null=True)
    uniprot_accession = models.CharField(max_length=255, blank=True, null=True)

    # ✅ NEW (for FASTA download + later structure prediction)
    fasta_sequence = models.TextField(blank=True, null=True)

    sequence_available = models.CharField(max_length=50, blank=True, null=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]  # ✅ keeps the same order as inserted/imported

    def __str__(self):
        # show pesticidedb_protein_id if present, otherwise pbdb_protein_id
        label = self.pesticidedb_protein_id or self.pbdb_protein_id or "PROT"
        return f"{label} | {self.reported_protein_name or ''}"
