from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0012_evidence_curation_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="annotationjob",
            name="result_file",
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AlterField(
            model_name="genomeannotationjob",
            name="result_file",
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
    ]
