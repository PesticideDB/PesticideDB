import shutil
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


def read_fasta(path):
    records = []
    header = None
    sequence = []

    def store():
        if header and sequence:
            records.append((header, "".join(sequence)))

    for line in Path(path).read_text(errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(">"):
            store()
            header = line[1:]
            sequence = []
        else:
            sequence.append(line)
    store()
    return records


class Command(BaseCommand):
    help = (
        "Build the validated DIAMOND reference from the original curated FASTA plus "
        "validated supplemental protein sequences. HMMER profiles are not changed."
    )

    def handle(self, *args, **options):
        annotation_dir = settings.PBDB_ANNOTATION_DIR
        data_dir = annotation_dir / "data"
        diamond_dir = annotation_dir / "diamond_db"

        curated_fasta = data_dir / "pbdb_reference_proteins.faa"
        supplemental_fasta = data_dir / "supplemental_validated_proteins.faa"
        combined_fasta = data_dir / "pbdb_validated_reference_proteins.faa"
        diamond_prefix = diamond_dir / "pbdb_validated"

        for path in (curated_fasta, supplemental_fasta):
            if not path.exists():
                raise CommandError(f"Required FASTA not found: {path}")

        records = []
        seen_accessions = set()
        seen_sequences = set()
        skipped_duplicates = 0

        for source_path in (curated_fasta, supplemental_fasta):
            for header, sequence in read_fasta(source_path):
                accession = header.split("|", 1)[0].split()[0]
                normalized_sequence = sequence.upper()
                if accession in seen_accessions or normalized_sequence in seen_sequences:
                    skipped_duplicates += 1
                    continue
                seen_accessions.add(accession)
                seen_sequences.add(normalized_sequence)
                records.append((header, normalized_sequence))

        with combined_fasta.open("w", encoding="utf-8") as handle:
            for header, sequence in records:
                handle.write(f">{header}\n")
                for start in range(0, len(sequence), 80):
                    handle.write(sequence[start:start + 80] + "\n")

        diamond = shutil.which("diamond")
        if not diamond:
            raise CommandError("DIAMOND executable was not found.")

        diamond_dir.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [
                diamond,
                "makedb",
                "--in",
                str(combined_fasta),
                "-d",
                str(diamond_prefix),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise CommandError(result.stderr or "DIAMOND makedb failed.")

        self.stdout.write(
            self.style.SUCCESS(
                f"Built validated annotation reference with {len(records)} unique sequences. "
                f"Skipped {skipped_duplicates} duplicate accession/sequence record(s). "
                f"FASTA: {combined_fasta}; DIAMOND: {diamond_prefix}.dmnd"
            )
        )
