from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0013_expand_job_result_file_paths"),
    ]

    operations = [
        migrations.AddField(
            model_name="proteinrecord",
            name="collection_category",
            field=models.CharField(
                db_index=True,
                default="CURATED",
                help_text="CURATED for experimentally reported records; SUPPLEMENTED for additional homology/literature-supported records.",
                max_length=50,
            ),
        ),
    ]
