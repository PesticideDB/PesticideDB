import re

from django.core.management.base import BaseCommand

from base.models import NoEvidencePesticide, Pesticide, ProteinRecord


def clean_name(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


class Command(BaseCommand):
    help = (
        "Normalize pesticide-name whitespace and case across biodegradation, protein, "
        "and no-evidence records without merging chemically distinct compounds."
    )

    def handle(self, *args, **options):
        canonical = {}
        for model in (Pesticide, ProteinRecord, NoEvidencePesticide):
            for value in model.objects.values_list("pesticide", flat=True):
                cleaned = clean_name(value)
                if cleaned:
                    canonical.setdefault(cleaned.casefold(), cleaned)

        changed = 0
        for model in (Pesticide, ProteinRecord, NoEvidencePesticide):
            for record in model.objects.exclude(pesticide__isnull=True).iterator():
                cleaned = clean_name(record.pesticide)
                normalized = canonical.get(cleaned.casefold(), cleaned)
                if record.pesticide != normalized:
                    record.pesticide = normalized
                    record.save(update_fields=["pesticide"])
                    changed += 1

        self.stdout.write(self.style.SUCCESS(
            f"Normalized pesticide names in {changed} record(s)."
        ))
