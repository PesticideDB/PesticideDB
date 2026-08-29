# Generated manually for optional evidence-curation metadata.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0011_genomeannotationjob"),
    ]

    operations = [
        migrations.AddField(
            model_name="pesticide",
            name="assay_type",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="pesticide",
            name="degradation_percent",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="pesticide",
            name="doi",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="pesticide",
            name="evidence_level",
            field=models.CharField(
                blank=True,
                help_text="Examples: reported biodegradation, enzyme assay, gene knockout, sequence homology prediction.",
                max_length=100,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="pesticide",
            name="metabolite_or_product",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="pesticide",
            name="pesticide_identifier",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="pesticide",
            name="pmid",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name="proteinrecord",
            name="annotation_basis",
            field=models.CharField(
                blank=True,
                help_text="Examples: curated literature, DIAMOND hit, HMMER family, NCBI accession.",
                max_length=100,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="proteinrecord",
            name="characterization_status",
            field=models.CharField(
                blank=True,
                help_text="Examples: experimentally characterized, literature reported, homology predicted.",
                max_length=100,
                null=True,
            ),
        ),
    ]
