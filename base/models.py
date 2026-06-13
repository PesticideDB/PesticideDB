from django.db import models
from django.db.models.functions import Lower


class Pesticide(models.Model):
    """
    Represents biodegradation evidence records.
    IMPORTANT: This table is record-level, so duplicates by pesticide name are allowed.
    """

    pesticide = models.CharField(max_length=200, db_index=True)

    microorganism = models.CharField(max_length=200, blank=True, null=True)
    gene = models.CharField(max_length=200, blank=True, null=True)

    enzyme = models.CharField(max_length=200, blank=True, null=True)
    enzyme_name_reported = models.CharField(max_length=255, blank=True, null=True)

    evidence_by_microbe = models.TextField(blank=True, null=True)
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

    def __str__(self):
        parts = [self.pesticide]
        if self.microorganism:
            parts.append(f"→ {self.microorganism}")
        if self.publication_year:
            parts.append(f"[{self.publication_year}]")
        return " ".join(parts)


class NoEvidencePesticide(models.Model):
    """
    Pesticides with no biodegradation evidence.
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

    def __str__(self):
        return self.pesticide


class DataSubmission(models.Model):
    """
    User-submitted biodegradation data.
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
# Protein Section (MVP)
# =========================
class ProteinRecord(models.Model):
    """
    Protein module (MVP)
    """

    pesticide = models.CharField(max_length=255, blank=True, null=True)
    microorganism = models.CharField(max_length=255, blank=True, null=True)

    evidence_type = models.CharField(max_length=255, blank=True, null=True)
    enzyme_class = models.CharField(max_length=255, blank=True, null=True)
    reported_protein_name = models.CharField(max_length=255, blank=True, null=True)

    pesticidedb_protein_id = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        db_index=True
    )

    pbdb_protein_id = models.CharField(max_length=50, blank=True, null=True, db_index=True)

    gene_name = models.CharField(max_length=255, blank=True, null=True)
    year = models.IntegerField(blank=True, null=True)
    doi = models.CharField(max_length=255, blank=True, null=True)

    ncbi_protein_accession = models.CharField(max_length=255, blank=True, null=True)
    uniprot_accession = models.CharField(max_length=255, blank=True, null=True)

    fasta_sequence = models.TextField(blank=True, null=True)
    sequence_available = models.CharField(max_length=50, blank=True, null=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if not self.pesticidedb_protein_id:
            self.pesticidedb_protein_id = f"PBDBP{self.id:06d}"
            super().save(update_fields=["pesticidedb_protein_id"])

    def __str__(self):
        label = self.pesticidedb_protein_id or self.pbdb_protein_id or "PROT"
        return f"{label} | {self.reported_protein_name or ''}"


class AnnotationResult(models.Model):
    """
    Stores results from DIAMOND + HMMER annotation pipeline
    """

    query = models.CharField(max_length=100)

    ncbi_protein_accession = models.CharField(max_length=50)
    pesticidedb_protein_id = models.CharField(max_length=50)

    pesticide = models.CharField(max_length=255, blank=True, null=True)
    microorganism = models.CharField(max_length=255, blank=True, null=True)

    enzyme_class = models.CharField(max_length=100, blank=True, null=True)
    reported_protein_name = models.CharField(max_length=255, blank=True, null=True)
    gene_name = models.CharField(max_length=100, blank=True, null=True)

    family_size = models.IntegerField(blank=True, null=True)
    family_confidence = models.CharField(max_length=20, blank=True, null=True)

    hmmer_family = models.CharField(max_length=100, blank=True, null=True)

    identity = models.FloatField(blank=True, null=True)
    evalue = models.FloatField(blank=True, null=True)
    bitscore = models.FloatField(blank=True, null=True)

    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"{self.query} → {self.pesticidedb_protein_id}"


# separate model for tracking annotation jobs
class AnnotationJob(models.Model):
    job_id = models.CharField(max_length=30, unique=True)
    status = models.CharField(max_length=20, default="running")
    message = models.TextField(blank=True, null=True)
    result_file = models.CharField(max_length=255, blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.job_id
    
#for annotategenome pipeline
class GenomeAnnotationJob(models.Model):
    job_id = models.CharField(max_length=30, unique=True)
    status = models.CharField(max_length=20, default="running")
    message = models.TextField(blank=True, null=True)
    result_file = models.CharField(max_length=255, blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.job_id