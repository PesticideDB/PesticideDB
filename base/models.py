from django.conf import settings
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


class Pesticide(models.Model):
    """
    Represents biodegradation evidence records.
    IMPORTANT: This table is record-level, so duplicates by pesticide name are allowed.
    """

    pesticide = models.CharField(max_length=200, db_index=True)
    pesticide_identifier = models.CharField(max_length=255, blank=True, null=True)

    microorganism = models.CharField(max_length=200, blank=True, null=True)
    culture_type = models.CharField(
        max_length=80,
        blank=True,
        null=True,
        help_text="Examples: Individual strain, Consortium member, Microbial community, Enrichment culture, Isolate group.",
    )
    gene = models.CharField(max_length=200, blank=True, null=True)

    enzyme = models.CharField(max_length=200, blank=True, null=True)
    enzyme_name_reported = models.CharField(max_length=255, blank=True, null=True)

    evidence_by_microbe = models.TextField(blank=True, null=True)
    evidence_of_enzyme = models.TextField(blank=True, null=True)
    evidence_level = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Examples: reported biodegradation, enzyme assay, gene knockout, sequence homology prediction.",
    )
    assay_type = models.CharField(max_length=255, blank=True, null=True)

    isolation_environment = models.CharField(max_length=255, blank=True, null=True)
    isolation_location = models.CharField(max_length=200, blank=True, null=True)

    degradation_time_days = models.CharField(max_length=100, blank=True, null=True)
    degradation_percent = models.CharField(max_length=100, blank=True, null=True)
    metabolite_or_product = models.CharField(max_length=255, blank=True, null=True)

    publication_year = models.IntegerField(blank=True, null=True)
    reference = models.TextField(blank=True, null=True)
    doi = models.CharField(max_length=255, blank=True, null=True)
    pmid = models.CharField(max_length=50, blank=True, null=True)

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

    REVIEW_STATUS_CHOICES = [
        ("PENDING", "Pending review"),
        ("IN_REVIEW", "In review"),
        ("NEEDS_REVISION", "Needs revision"),
        ("APPROVED", "Approved and imported"),
        ("PARTIALLY_IMPORTED", "Partially imported"),
        ("REJECTED", "Rejected"),
    ]

    pesticide = models.CharField(max_length=200, db_index=True)
    microorganism_name = models.CharField(max_length=200, db_index=True)

    protein = models.CharField(max_length=200, blank=True, null=True)
    gene = models.CharField(max_length=200, blank=True, null=True)

    evidence = models.TextField()
    doi = models.CharField(max_length=300)
    email = models.EmailField(max_length=150)

    submitted_at = models.DateTimeField(auto_now_add=True)
    review_status = models.CharField(
        max_length=30,
        choices=REVIEW_STATUS_CHOICES,
        default="PENDING",
        db_index=True,
    )
    detected_sections = models.CharField(
        max_length=255,
        blank=True,
        help_text="Automatically suggested database sections related to this submission.",
    )
    review_notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="reviewed_data_submissions",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)

    approve_biodegradation_record = models.BooleanField(
        default=False,
        help_text="If checked, admin approval can create a curated microorganism/pesticide evidence record.",
    )
    approve_protein_record = models.BooleanField(
        default=False,
        help_text="If checked, admin approval can create a protein record when protein/gene evidence is supplied.",
    )
    flag_for_pathway_curation = models.BooleanField(
        default=False,
        help_text="Use when the paper appears to contain metabolite, product, pathway, or transformation information.",
    )
    imported_biodegradation_record = models.ForeignKey(
        "Pesticide",
        related_name="source_submissions",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    imported_protein_record = models.ForeignKey(
        "ProteinRecord",
        related_name="source_submissions",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ["-submitted_at"]

    def save(self, *args, **kwargs):
        self.detected_sections = ", ".join(self.suggested_sections())
        super().save(*args, **kwargs)

    def suggested_sections(self):
        sections = ["Microorganism evidence"]
        if self.protein or self.gene:
            sections.append("Protein/gene evidence")
        pathway_terms = [
            "pathway",
            "metabolite",
            "intermediate",
            "product",
            "transformation",
            "mineralization",
            "degradation route",
        ]
        evidence_text = (self.evidence or "").lower()
        if any(term in evidence_text for term in pathway_terms):
            sections.append("Pathway curation candidate")
        return sections

    def mark_reviewed(self, user=None, status=None):
        self.reviewed_by = user
        self.reviewed_at = timezone.now()
        if status:
            self.review_status = status

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
    collection_category = models.CharField(
        max_length=50,
        default="CURATED",
        db_index=True,
        help_text="CURATED for experimentally reported records; SUPPLEMENTED for additional homology/literature-supported records.",
    )
    characterization_status = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Examples: experimentally characterized, literature reported, homology predicted.",
    )
    annotation_basis = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Examples: curated literature, DIAMOND hit, HMMER family, NCBI accession.",
    )
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
            used_ids = set(
                ProteinRecord.objects
                .exclude(pesticidedb_protein_id__isnull=True)
                .exclude(pesticidedb_protein_id="")
                .values_list("pesticidedb_protein_id", flat=True)
            )
            next_number = 1
            while f"PDBP{next_number:04d}" in used_ids:
                next_number += 1
            self.pesticidedb_protein_id = f"PDBP{next_number:04d}"
            super().save(update_fields=["pesticidedb_protein_id"])

    def __str__(self):
        label = self.pesticidedb_protein_id or self.pbdb_protein_id or "PROT"
        return f"{label} | {self.reported_protein_name or ''}"


class Compound(models.Model):
    COMPOUND_ROLE_CHOICES = [
        ("PESTICIDE", "Parent pesticide"),
        ("METABOLITE", "Metabolite/intermediate"),
        ("END_PRODUCT", "End product"),
        ("UNKNOWN", "Unknown/unresolved compound"),
    ]

    name = models.CharField(max_length=255, unique=True, db_index=True)
    role = models.CharField(
        max_length=30,
        choices=COMPOUND_ROLE_CHOICES,
        default="METABOLITE",
    )
    cas_number = models.CharField(max_length=100, blank=True)
    pubchem_cid = models.CharField(max_length=100, blank=True)
    smiles = models.TextField(blank=True)
    inchikey = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    @property
    def pubchem_url(self):
        if self.pubchem_cid:
            return f"https://pubchem.ncbi.nlm.nih.gov/compound/{self.pubchem_cid}"
        return ""

    @property
    def pubchem_structure_image_url(self):
        if self.pubchem_cid:
            return (
                "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/"
                f"{self.pubchem_cid}/PNG?record_type=2d&image_size=700x520"
            )
        return ""

    @property
    def pubchem_sdf_url(self):
        if self.pubchem_cid:
            return f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{self.pubchem_cid}/SDF"
        return ""

    def __str__(self):
        return self.name


class LiteratureReference(models.Model):
    title = models.TextField(blank=True)
    authors = models.TextField(blank=True)
    year = models.IntegerField(blank=True, null=True)
    journal = models.CharField(max_length=255, blank=True)
    doi = models.CharField(max_length=255, unique=True, blank=True, null=True)
    pmid = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["year", "title"]

    @property
    def doi_url(self):
        if self.doi:
            return f"https://doi.org/{self.doi}"
        return ""

    def __str__(self):
        label = self.title or self.doi or "Reference"
        if self.year:
            return f"{label} ({self.year})"
        return label


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
    result_file = models.CharField(max_length=500, blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.job_id
    
#for annotategenome pipeline
class GenomeAnnotationJob(models.Model):
    job_id = models.CharField(max_length=30, unique=True)
    status = models.CharField(max_length=20, default="running")
    message = models.TextField(blank=True, null=True)
    result_file = models.CharField(max_length=500, blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.job_id


class DegradationPathway(models.Model):
    COMPLETENESS_CHOICES = [
        ("COMPLETE", "Complete mineralization reported"),
        ("PARTIAL", "Partial degradation reported"),
        ("PROPOSED", "Proposed pathway"),
    ]

    pesticide = models.CharField(max_length=200, db_index=True)
    title = models.CharField(max_length=255)
    microorganism = models.CharField(max_length=255, blank=True)
    completeness = models.CharField(
        max_length=20,
        choices=COMPLETENESS_CHOICES,
        default="PARTIAL",
    )
    summary = models.TextField(blank=True)
    doi = models.CharField(max_length=255, blank=True)
    reference = models.TextField(blank=True)
    references = models.ManyToManyField(
        LiteratureReference,
        related_name="pathways",
        blank=True,
    )

    class Meta:
        ordering = ["pesticide", "title"]

    def __str__(self):
        return f"{self.pesticide}: {self.title}"


class DegradationPathwayStep(models.Model):
    EVIDENCE_CHOICES = [
        ("PURIFIED_ENZYME", "Purified/recombinant enzyme"),
        ("GENETIC", "Gene knockout/expression evidence"),
        ("METABOLITE", "Metabolite experimentally detected"),
        ("WHOLE_CELL", "Whole-cell or crude extract"),
        ("PROPOSED", "Proposed/inferred step"),
    ]

    pathway = models.ForeignKey(
        DegradationPathway,
        related_name="steps",
        on_delete=models.CASCADE,
    )
    step_order = models.PositiveIntegerField()
    substrate = models.CharField(max_length=255)
    substrate_compound = models.ForeignKey(
        Compound,
        related_name="pathway_steps_as_substrate",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    product = models.CharField(max_length=255)
    product_compound = models.ForeignKey(
        Compound,
        related_name="pathway_steps_as_product",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    gene = models.CharField(max_length=255, blank=True)
    enzyme = models.CharField(max_length=255, blank=True)
    protein = models.ForeignKey(
        ProteinRecord,
        related_name="pathway_steps",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    microorganism = models.CharField(max_length=255, blank=True)
    evidence_type = models.CharField(
        max_length=30,
        choices=EVIDENCE_CHOICES,
        default="PROPOSED",
    )
    doi = models.CharField(max_length=255, blank=True)
    references = models.ManyToManyField(
        LiteratureReference,
        related_name="pathway_steps",
        blank=True,
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["pathway", "step_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["pathway", "step_order"],
                name="unique_pathway_step_order",
            )
        ]

    @property
    def arrow_class(self):
        if self.evidence_type in {"PURIFIED_ENZYME", "GENETIC"}:
            return "arrow-strong"
        if self.evidence_type in {"METABOLITE", "WHOLE_CELL"}:
            return "arrow-supported"
        return "arrow-proposed"

    def __str__(self):
        return f"{self.pathway} step {self.step_order}"


class PathwayEvidence(models.Model):
    EVIDENCE_DIRECTNESS_CHOICES = [
        ("DIRECT", "Direct evidence"),
        ("INDIRECT", "Indirect evidence"),
        ("PROPOSED", "Proposed/inferred"),
    ]

    pathway = models.ForeignKey(
        DegradationPathway,
        related_name="evidence_links",
        on_delete=models.CASCADE,
    )
    step = models.ForeignKey(
        DegradationPathwayStep,
        related_name="evidence_links",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    reference = models.ForeignKey(
        LiteratureReference,
        related_name="pathway_evidence",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    pesticide_record = models.ForeignKey(
        Pesticide,
        related_name="pathway_evidence",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    evidence_type = models.CharField(max_length=255, blank=True)
    directness = models.CharField(
        max_length=20,
        choices=EVIDENCE_DIRECTNESS_CHOICES,
        default="DIRECT",
    )
    confidence = models.CharField(max_length=100, blank=True)
    method = models.CharField(max_length=255, blank=True)
    summary = models.TextField(blank=True)

    class Meta:
        ordering = ["pathway", "step__step_order", "id"]

    def __str__(self):
        return f"{self.pathway} evidence: {self.evidence_type or self.directness}"


class SiteVisitCounter(models.Model):
    key = models.CharField(max_length=50, unique=True, default="site")
    total_visits = models.PositiveBigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "site visit counter"
        verbose_name_plural = "site visit counters"

    def __str__(self):
        return f"{self.key}: {self.total_visits} visits"
