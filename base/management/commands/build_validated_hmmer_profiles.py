import re
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from base.annotation_utils import accession_keys, clean_hit_id
from base.models import ProteinRecord


MIN_UNIQUE_SEQUENCES = 2
EXCLUDED_CLASSES = {"", "not mentioned"}


def clean_family_name(value):
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def read_fasta(path):
    records = []
    header = None
    sequence = []

    def store():
        if header and sequence:
            records.append((header, "".join(sequence).upper()))

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
        "Build and press HMMER profiles using only curated and validated supplemented "
        "ProteinRecord metadata and the validated reference FASTA."
    )

    def handle(self, *args, **options):
        annotation_dir = settings.PBDB_ANNOTATION_DIR
        fasta_path = annotation_dir / "data" / "pbdb_validated_reference_proteins.faa"
        hmmer_dir = annotation_dir / "hmmer_db"
        family_dir = hmmer_dir / "validated_families"
        combined_hmm = hmmer_dir / "pbdb_validated_profiles.hmm"

        if not fasta_path.exists():
            raise CommandError(f"Validated FASTA not found: {fasta_path}")

        mafft = shutil.which("mafft")
        hmmbuild = shutil.which("hmmbuild")
        hmmpress = shutil.which("hmmpress")
        missing = [
            name for name, path in (
                ("mafft", mafft),
                ("hmmbuild", hmmbuild),
                ("hmmpress", hmmpress),
            )
            if not path
        ]
        if missing:
            raise CommandError("Missing required executables: " + ", ".join(missing))

        lookup = {}
        for protein in ProteinRecord.objects.filter(
            collection_category__in=["CURATED", "SUPPLEMENTED"]
        ):
            for identifier in (
                protein.ncbi_protein_accession,
                protein.uniprot_accession,
                protein.pesticidedb_protein_id,
                protein.pbdb_protein_id,
            ):
                for key in accession_keys(identifier):
                    lookup.setdefault(key, protein)

        families = defaultdict(list)
        unmapped = []
        duplicate_sequences = 0
        seen_by_family = defaultdict(set)

        for header, sequence in read_fasta(fasta_path):
            identifier = clean_hit_id(header.split()[0])
            protein = next(
                (lookup[key] for key in accession_keys(identifier) if key in lookup),
                None,
            )
            if protein is None:
                unmapped.append(identifier)
                continue

            enzyme_class = (protein.enzyme_class or "").strip()
            if enzyme_class.lower() in EXCLUDED_CLASSES:
                continue
            if sequence in seen_by_family[enzyme_class]:
                duplicate_sequences += 1
                continue

            seen_by_family[enzyme_class].add(sequence)
            record_header = "|".join([
                protein.pesticidedb_protein_id or identifier,
                protein.uniprot_accession or protein.ncbi_protein_accession or identifier,
                protein.gene_name or "-",
                protein.collection_category,
            ])
            families[enzyme_class].append((record_header, sequence))

        buildable = {
            family: records
            for family, records in families.items()
            if len(records) >= MIN_UNIQUE_SEQUENCES
        }
        excluded = {
            family: len(records)
            for family, records in families.items()
            if len(records) < MIN_UNIQUE_SEQUENCES
        }
        if not buildable:
            raise CommandError("No enzyme classes have enough unique validated sequences.")

        if family_dir.exists():
            shutil.rmtree(family_dir)
        family_dir.mkdir(parents=True)

        hmm_paths = []
        family_summary = []
        for family in sorted(buildable):
            records = buildable[family]
            family_name = clean_family_name(family)
            raw_fasta = family_dir / f"{family_name}.faa"
            aligned_fasta = family_dir / f"{family_name}_aligned.faa"
            hmm_path = family_dir / f"{family_name}.hmm"

            with raw_fasta.open("w", encoding="utf-8") as handle:
                for header, sequence in records:
                    handle.write(f">{header}\n")
                    for start in range(0, len(sequence), 80):
                        handle.write(sequence[start:start + 80] + "\n")

            with aligned_fasta.open("w", encoding="utf-8") as handle:
                alignment = subprocess.run(
                    [mafft, "--auto", "--quiet", str(raw_fasta)],
                    stdout=handle,
                    stderr=subprocess.PIPE,
                    text=True,
                )
            if alignment.returncode != 0:
                raise CommandError(
                    f"MAFFT failed for {family}: {alignment.stderr or 'unknown error'}"
                )

            build = subprocess.run(
                [hmmbuild, "-n", family_name, str(hmm_path), str(aligned_fasta)],
                capture_output=True,
                text=True,
            )
            if build.returncode != 0:
                raise CommandError(
                    f"hmmbuild failed for {family}: {build.stderr or build.stdout}"
                )

            hmm_paths.append(hmm_path)
            family_summary.append((family, len(records)))

        with combined_hmm.open("wb") as output:
            for hmm_path in hmm_paths:
                output.write(hmm_path.read_bytes())

        for suffix in (".h3f", ".h3i", ".h3m", ".h3p"):
            pressed_path = Path(str(combined_hmm) + suffix)
            if pressed_path.exists():
                pressed_path.unlink()

        press = subprocess.run(
            [hmmpress, "-f", str(combined_hmm)],
            capture_output=True,
            text=True,
        )
        if press.returncode != 0:
            raise CommandError(f"hmmpress failed: {press.stderr or press.stdout}")

        self.stdout.write(self.style.SUCCESS(
            f"Built {len(family_summary)} validated HMMER profiles at {combined_hmm}."
        ))
        for family, count in family_summary:
            self.stdout.write(f"  {family}: {count} unique validated sequences")
        if excluded:
            self.stdout.write(
                "Excluded classes with fewer than "
                f"{MIN_UNIQUE_SEQUENCES} unique sequences: "
                + ", ".join(f"{name} ({count})" for name, count in sorted(excluded.items()))
            )
        if unmapped:
            self.stdout.write(
                self.style.WARNING(
                    f"Unmapped validated FASTA identifiers: {', '.join(sorted(set(unmapped)))}"
                )
            )
        self.stdout.write(f"Skipped {duplicate_sequences} duplicate sequence(s) within families.")
