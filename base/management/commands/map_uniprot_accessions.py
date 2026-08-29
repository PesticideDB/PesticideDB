import time

import requests
from django.core.management.base import BaseCommand, CommandError

from base.models import ProteinRecord


UNIPROT_ID_MAPPING_URL = "https://rest.uniprot.org/idmapping"
DEFAULT_FROM_DATABASES = [
    "RefSeq_Protein",
    "EMBL-GenBank-DDBJ_CDS",
]


def clean_accession(value):
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none", "not available", "n/a", "-"}:
        return ""
    return text


class Command(BaseCommand):
    help = "Map NCBI protein accessions to UniProt accessions using the UniProt ID mapping API."

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=100)
        parser.add_argument("--timeout", type=int, default=120)
        parser.add_argument("--poll-interval", type=float, default=3.0)
        parser.add_argument(
            "--from-db",
            action="append",
            dest="from_databases",
            help=(
                "UniProt source database name. Can be supplied multiple times. "
                "Defaults to RefSeq_Protein and EMBL-GenBank-DDBJ_CDS."
            ),
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Replace existing UniProt accessions if a new mapping is found.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report mappings without updating ProteinRecord rows.",
        )

    def handle(self, *args, **options):
        from_databases = options["from_databases"] or DEFAULT_FROM_DATABASES
        batch_size = max(options["batch_size"], 1)
        timeout = options["timeout"]
        poll_interval = options["poll_interval"]
        overwrite = options["overwrite"]
        dry_run = options["dry_run"]

        queryset = ProteinRecord.objects.exclude(ncbi_protein_accession__isnull=True)
        if not overwrite:
            queryset = queryset.filter(uniprot_accession__isnull=True) | queryset.filter(uniprot_accession="")

        records_by_accession = {}
        for protein in queryset:
            accession = clean_accession(protein.ncbi_protein_accession)
            if accession:
                records_by_accession.setdefault(accession, []).append(protein)

        accessions = sorted(records_by_accession)
        if not accessions:
            self.stdout.write(self.style.WARNING("No NCBI protein accessions need UniProt mapping."))
            return

        self.stdout.write(f"Mapping {len(accessions)} NCBI protein accession(s).")
        self.stdout.write(f"UniProt source database(s): {', '.join(from_databases)}")

        mapped = {}
        for from_db in from_databases:
            remaining = [acc for acc in accessions if acc not in mapped]
            if not remaining:
                break

            self.stdout.write(f"Trying UniProt mapping source: {from_db}")
            for start in range(0, len(remaining), batch_size):
                batch = remaining[start:start + batch_size]
                batch_mapping = self.map_batch(
                    batch,
                    from_db=from_db,
                    timeout=timeout,
                    poll_interval=poll_interval,
                )
                mapped.update(batch_mapping)
                self.stdout.write(
                    f"  Batch {start // batch_size + 1}: mapped {len(batch_mapping)} of {len(batch)}"
                )

        updated = 0
        for ncbi_accession, uniprot_accession in mapped.items():
            for protein in records_by_accession.get(ncbi_accession, []):
                if dry_run:
                    self.stdout.write(
                        f"Would update {protein.pesticidedb_protein_id}: "
                        f"{ncbi_accession} -> {uniprot_accession}"
                    )
                    continue

                protein.uniprot_accession = uniprot_accession
                protein.save(update_fields=["uniprot_accession", "updated"])
                updated += 1

        unmapped = len(accessions) - len(mapped)
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Dry run complete. Mapped: {len(mapped)} accession(s). Unmapped: {unmapped}."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"UniProt mapping complete. Updated rows: {updated}. "
                    f"Mapped accessions: {len(mapped)}. Unmapped accessions: {unmapped}."
                )
            )

    def map_batch(self, accessions, from_db, timeout, poll_interval):
        job_id = self.submit_mapping_job(accessions, from_db=from_db, timeout=timeout)
        self.wait_for_job(job_id, timeout=timeout, poll_interval=poll_interval)
        return self.fetch_results(job_id, timeout=timeout)

    def submit_mapping_job(self, accessions, from_db, timeout):
        response = requests.post(
            f"{UNIPROT_ID_MAPPING_URL}/run",
            data={
                "from": from_db,
                "to": "UniProtKB",
                "ids": ",".join(accessions),
            },
            timeout=timeout,
        )
        if response.status_code >= 400:
            raise CommandError(
                f"UniProt mapping submission failed for {from_db}: "
                f"{response.status_code} {response.text[:300]}"
            )

        job_id = response.json().get("jobId")
        if not job_id:
            raise CommandError("UniProt did not return a mapping job ID.")
        return job_id

    def wait_for_job(self, job_id, timeout, poll_interval):
        deadline = time.time() + timeout
        while time.time() < deadline:
            response = requests.get(
                f"{UNIPROT_ID_MAPPING_URL}/status/{job_id}",
                timeout=timeout,
            )
            response.raise_for_status()
            status = response.json()

            if "jobStatus" not in status:
                return

            job_status = status["jobStatus"]
            if job_status == "FINISHED":
                return
            if job_status in {"FAILED", "ERROR"}:
                raise CommandError(f"UniProt mapping job {job_id} failed: {status}")

            time.sleep(poll_interval)

        raise CommandError(f"Timed out waiting for UniProt mapping job {job_id}.")

    def fetch_results(self, job_id, timeout):
        next_url = f"{UNIPROT_ID_MAPPING_URL}/uniprotkb/results/{job_id}?format=json&size=500"
        mapping = {}

        while next_url:
            response = requests.get(next_url, timeout=timeout)
            response.raise_for_status()
            payload = response.json()

            for item in payload.get("results", []):
                source_accession = item.get("from")
                target = item.get("to")
                if isinstance(target, dict):
                    uniprot_accession = target.get("primaryAccession")
                else:
                    uniprot_accession = str(target or "").strip()

                if source_accession and uniprot_accession:
                    mapping.setdefault(source_accession, uniprot_accession)

            next_url = self.next_link(response.headers.get("Link", ""))

        return mapping

    def next_link(self, link_header):
        for part in link_header.split(","):
            section = part.strip()
            if 'rel="next"' not in section:
                continue
            start = section.find("<")
            end = section.find(">")
            if start != -1 and end != -1:
                return section[start + 1:end]
        return None
