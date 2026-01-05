from django.db import models

# Create your models here.
class Pesticide(models.Model):
    pesticide = models.CharField(max_length=200)
    microorganism = models.CharField(max_length=200, blank=True, null=True)
    phylum = models.CharField(max_length=200, blank=True, null=True)
    family = models.CharField(max_length=200, blank=True, null=True)
    strain = models.CharField(max_length=200, blank=True, null=True)
    rrna_16s = models.CharField("16s rRNA", max_length=200, blank=True, null=True)
    tax_id = models.CharField(max_length=100, blank=True, null=True)
    reference = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=100, blank=True, null=True)
    publication_year = models.IntegerField(blank=True, null=True)
    substrate = models.CharField(max_length=200, blank=True, null=True)
    manufacturer = models.CharField(max_length=200, blank=True, null=True)
    evidence_by_microbe = models.TextField(blank=True, null=True)
    microbe_equipment = models.CharField(max_length=255, blank=True, null=True)
    isolation_environment = models.CharField(max_length=255, blank=True, null=True)
    degradation_time_days = models.CharField(max_length=100, blank=True, null=True)
    isolation_location = models.CharField(max_length=200, blank=True, null=True)
    enzyme = models.CharField(max_length=200, blank=True, null=True)
    evidence_of_enzyme = models.TextField(blank=True, null=True)
    enzyme_equipment = models.CharField(max_length=255, blank=True, null=True)
    gene = models.CharField(max_length=200, blank=True, null=True)
    genbank_id = models.CharField(max_length=200, blank=True, null=True)
    enzyme_sequence = models.TextField(blank=True, null=True)
    updated = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):                                                                 
        """Return a more informative string representation"""
        parts = []
        
        # Always include pesticide name
        parts.append(self.pesticide)
        
        # Include microorganism if available
        if self.microorganism:
            parts.append(f"→ {self.microorganism}")
        
        # Include category if available
        if self.category:
            parts.append(f"({self.category})")
        
        # Include year if available
        if self.publication_year:
            parts.append(f"[{self.publication_year}]")
        
        return " ".join(parts)
    
class NoEvidencePesticide(models.Model):
    pesticide = models.CharField(max_length=200)
    evidence_of_biodegradation = models.CharField(max_length=255, default='No evidence')

    def __str__(self):
        return f"{self.pesticide} - {self.evidence_of_biodegradation}"

# Model for data submissions
class DataSubmission(models.Model):
    pesticide = models.CharField(max_length=70)
    microorganism_name = models.CharField(max_length=100)
    protein = models.CharField(max_length=70, blank=True, null=True)
    gene = models.CharField(max_length=50, blank=True, null=True)
    evidence = models.TextField(max_length=500)
    doi = models.CharField(max_length=200)
    email = models.EmailField(max_length=100)
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.pesticide} - {self.microorganism_name}"