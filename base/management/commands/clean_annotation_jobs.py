import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from base.models import AnnotationJob, GenomeAnnotationJob


class Command(BaseCommand):
    help = "Remove generated annotation job files and optionally clear job database rows."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Actually delete files. Without this flag, only reports what would be deleted.")
        parser.add_argument("--clear-db", action="store_true", help="Also delete AnnotationJob and GenomeAnnotationJob rows.")

    def handle(self, *args, **options):
        apply = options["apply"]
        clear_db = options["clear_db"]
        targets = [
            settings.MEDIA_ROOT / "annotation_jobs",
            settings.MEDIA_ROOT / "genome_jobs",
        ]

        files = []
        dirs = []
        for target in targets:
            if not target.exists():
                continue
            dirs.append(target)
            files.extend(path for path in target.rglob("*") if path.is_file())

        action = "Deleting" if apply else "Would delete"
        self.stdout.write(f"{action} {len(files)} generated annotation file(s).")

        if apply:
            for target in dirs:
                shutil.rmtree(target)
                target.mkdir(parents=True, exist_ok=True)

            if clear_db:
                annotation_count = AnnotationJob.objects.count()
                genome_count = GenomeAnnotationJob.objects.count()
                AnnotationJob.objects.all().delete()
                GenomeAnnotationJob.objects.all().delete()
                self.stdout.write(f"Deleted {annotation_count + genome_count} annotation job database row(s).")

            self.stdout.write(self.style.SUCCESS("Annotation job cleanup complete."))
        else:
            self.stdout.write("Dry run only. Re-run with --apply to delete these generated files.")
