import csv
import shutil
from datetime import datetime

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

from base.models import DegradationPathway, LiteratureReference, PathwayEvidence, Pesticide, NoEvidencePesticide, ProteinRecord


class Command(BaseCommand):
    help = "Export a reproducible PesticideDB release bundle."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            default=None,
            help="Directory for the export bundle. Defaults to backups/pesticidedb_release_<timestamp>.",
        )

    def handle(self, *args, **options):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = (
            settings.BASE_DIR / "backups" / f"pesticidedb_release_{timestamp}"
            if options["output_dir"] is None
            else settings.BASE_DIR / options["output_dir"]
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        self._write_csv(output_dir / "proteins.csv", ProteinRecord.objects.all(), [
            "pesticidedb_protein_id",
            "pbdb_protein_id",
            "reported_protein_name",
            "pesticide",
            "microorganism",
            "evidence_type",
            "collection_category",
            "enzyme_class",
            "gene_name",
            "ncbi_protein_accession",
            "uniprot_accession",
            "year",
            "doi",
        ])
        self._write_csv(output_dir / "biodegradation_records.csv", Pesticide.objects.all(), [
            "pesticide",
            "microorganism",
            "gene",
            "enzyme",
            "evidence_by_microbe",
            "evidence_of_enzyme",
            "evidence_level",
            "assay_type",
            "isolation_environment",
            "isolation_location",
            "degradation_time_days",
            "degradation_percent",
            "metabolite_or_product",
            "publication_year",
            "doi",
            "pmid",
            "reference",
        ])
        self._write_csv(output_dir / "no_evidence_pesticides.csv", NoEvidencePesticide.objects.all(), [
            "pesticide",
            "evidence_of_biodegradation",
        ])
        self._write_csv(output_dir / "pathway_evidence_records.csv", DegradationPathway.objects.all(), [
            "pesticide",
            "title",
            "microorganism",
            "completeness",
            "summary",
            "doi",
            "reference",
        ])
        self._write_csv(output_dir / "literature_references.csv", LiteratureReference.objects.all(), [
            "title",
            "authors",
            "year",
            "journal",
            "doi",
            "pmid",
            "notes",
        ])
        self._write_pathway_links_csv(output_dir / "pathway_evidence_links.csv")

        with (output_dir / "database_dump.json").open("w", encoding="utf-8") as handle:
            call_command("dumpdata", "base", indent=2, stdout=handle)

        assets = [
            settings.BASE_DIR / "PBDB_annotation" / "data" / "PBDB_master_with_ids.xlsx",
            settings.BASE_DIR / "PBDB_annotation" / "data" / "pbdb_validated_reference_proteins.faa",
            settings.BASE_DIR / "PBDB_annotation" / "data" / "supplemental_validated_proteins.faa",
            settings.BASE_DIR / "PBDB_annotation" / "hmmer_db" / "pbdb_validated_profiles.hmm",
            settings.BASE_DIR / "data_files" / "core" / "pesticide_data.xlsx",
            settings.BASE_DIR / "data_files" / "core" / "pesticide_data.csv",
            settings.BASE_DIR / "data_files" / "core" / "additional_existing_curated_evidence.xlsx",
            settings.BASE_DIR / "data_files" / "core" / "additional_2025-2026-search.xlsx",
            settings.BASE_DIR / "data_files" / "core" / "pesticide_data_with_2025_2026.xlsx",
            settings.BASE_DIR / "data_files" / "core" / "pesticide_data_with_2025_2026.csv",
            settings.BASE_DIR / "data_files" / "core" / "no_evidence_pesticide.xlsx",
            settings.BASE_DIR / "data_files" / "protein" / "PBDB_Proteins_Master.xlsx",
            settings.BASE_DIR / "data_files" / "protein" / "PBDB_Proteins_Master.csv",
            settings.BASE_DIR / "data_files" / "protein" / "PBDB_Proteins_Master_With_2025_2026.xlsx",
            settings.BASE_DIR / "data_files" / "protein" / "PBDB_Proteins_Master_With_2025_2026.csv",
            settings.BASE_DIR / "data_files" / "protein" / "PBDB_Protein_Gene_Records_2025_2026_Additions.xlsx",
            settings.BASE_DIR / "data_files" / "protein" / "PBDB_Protein_Gene_Records_2025_2026_Additions.csv",
            settings.BASE_DIR / "data_files" / "protein" / "PBDB_Protein_Structure_Curation_2025_2026.xlsx",
            settings.BASE_DIR / "data_files" / "protein" / "PBDB_Protein_Structure_Curation_2025_2026.csv",
            settings.BASE_DIR / "curation_outputs" / "supplemented_validated_protein_evidence_15.xlsx",
            settings.BASE_DIR / "curation_outputs" / "supplemented_discovery_candidates_179.xlsx",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Pathway_Evidence_Master.xlsx",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Pathway_Evidence_Master.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch1.xlsx",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch1.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch2.xlsx",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch2.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch3.xlsx",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch3.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch4.xlsx",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch4.csv",
            settings.BASE_DIR / "curation_outputs" / "stepwise_pathway_batch4_20260707" / "pesticidedb_stepwise_pathway_batch4_screening_decisions.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch5.xlsx",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch5.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch6.xlsx",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch6.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch7.xlsx",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch7.csv",
            settings.BASE_DIR / "curation_outputs" / "stepwise_pathway_batch7_20260707" / "pesticidedb_stepwise_pathway_batch7_screening_decisions.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch8.xlsx",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch8.csv",
            settings.BASE_DIR / "curation_outputs" / "stepwise_pathway_batch8_20260708" / "pesticidedb_stepwise_pathway_batch8_screening_decisions.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch9.xlsx",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch9.csv",
            settings.BASE_DIR / "curation_outputs" / "stepwise_pathway_batch9_20260708" / "pesticidedb_stepwise_pathway_batch9_screening_decisions.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch10.xlsx",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch10.csv",
            settings.BASE_DIR / "curation_outputs" / "stepwise_pathway_batch10_20260708" / "pesticidedb_stepwise_pathway_batch10_screening_decisions.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch11.xlsx",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch11.csv",
            settings.BASE_DIR / "curation_outputs" / "stepwise_pathway_batch11_20260708" / "pesticidedb_stepwise_pathway_batch11_screening_decisions.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch12.xlsx",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch12.csv",
            settings.BASE_DIR / "curation_outputs" / "stepwise_pathway_batch12_20260708" / "pesticidedb_stepwise_pathway_batch12_screening_decisions.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch13.xlsx",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch13.csv",
            settings.BASE_DIR / "curation_outputs" / "stepwise_pathway_batch13_20260708" / "pesticidedb_stepwise_pathway_batch13_screening_decisions.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch14.xlsx",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch14.csv",
            settings.BASE_DIR / "curation_outputs" / "stepwise_pathway_batch14_20260709" / "pesticidedb_stepwise_pathway_batch14_screening_decisions.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch15.xlsx",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch15.csv",
            settings.BASE_DIR / "curation_outputs" / "stepwise_pathway_batch15_20260709" / "pesticidedb_stepwise_pathway_batch15_screening_decisions.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch16.xlsx",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch16.csv",
            settings.BASE_DIR / "curation_outputs" / "stepwise_pathway_batch16_20260710" / "pesticidedb_stepwise_pathway_batch16_screening_decisions.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch17.xlsx",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch17.csv",
            settings.BASE_DIR / "curation_outputs" / "stepwise_pathway_batch17_20260710" / "pesticidedb_stepwise_pathway_batch17_screening_decisions.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch18.xlsx",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch18.csv",
            settings.BASE_DIR / "curation_outputs" / "stepwise_pathway_batch18_20260711" / "pesticidedb_stepwise_pathway_batch18_screening_decisions.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch19.xlsx",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch19.csv",
            settings.BASE_DIR / "curation_outputs" / "stepwise_pathway_batch19_20260711" / "pesticidedb_stepwise_pathway_batch19_screening_decisions.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch20.xlsx",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch20.csv",
            settings.BASE_DIR / "curation_outputs" / "stepwise_pathway_batch20_20260711" / "pesticidedb_stepwise_pathway_batch20_screening_decisions.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch21.xlsx",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch21.csv",
            settings.BASE_DIR / "curation_outputs" / "stepwise_pathway_batch21_20260712" / "pesticidedb_stepwise_pathway_batch21_screening_decisions.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch22.xlsx",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch22.csv",
            settings.BASE_DIR / "curation_outputs" / "stepwise_pathway_batch22_20260712" / "pesticidedb_stepwise_pathway_batch22_screening_decisions.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch23.xlsx",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch23.csv",
            settings.BASE_DIR / "curation_outputs" / "stepwise_pathway_batch23_20260712" / "pesticidedb_stepwise_pathway_batch23_screening_decisions.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch24.xlsx",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch24.csv",
            settings.BASE_DIR / "curation_outputs" / "stepwise_pathway_batch24_20260712" / "pesticidedb_stepwise_pathway_batch24_screening_decisions.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch25.xlsx",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch25.csv",
            settings.BASE_DIR / "curation_outputs" / "stepwise_pathway_batch25_20260712" / "pesticidedb_stepwise_pathway_batch25_screening_decisions.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch26.xlsx",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch26.csv",
            settings.BASE_DIR / "curation_outputs" / "stepwise_pathway_batch26_20260712" / "pesticidedb_stepwise_pathway_batch26_screening_decisions.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch27.xlsx",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master_Batch27.csv",
            settings.BASE_DIR / "curation_outputs" / "stepwise_pathway_batch27_20260712" / "pesticidedb_stepwise_pathway_batch27_screening_decisions.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master.xlsx",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Stepwise_Pathway_Master.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Missing_Stepwise_Pathway_Information.xlsx",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Missing_Stepwise_Pathway_Information.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_All_Evidence_Positive_Pathway_Audit.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Pathway_Source_Acquisition_Priority.xlsx",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Pathway_Source_Acquisition_Priority.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Pathway_DOI_Redownload_Manifest.xlsx",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Pathway_DOI_Redownload_Manifest.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Remaining_Pathway_Curation_Batches.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Remaining_Pathway_Curation_Batches_Summary.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Priority1_Open_Access_Check.xlsx",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Priority1_Open_Access_Check.csv",
            settings.BASE_DIR / "data_files" / "pathway" / "PesticideDB_Priority1_Open_Access_Summary.csv",
            settings.BASE_DIR / "curation_outputs" / "priority1_oa_pathway_screening_20260708" / "priority1_oa_candidate_transformations.csv",
            settings.BASE_DIR / "curation_outputs" / "priority1_oa_pathway_screening_20260708" / "priority1_oa_pathway_screening_summary.csv",
            settings.BASE_DIR / "curation_outputs" / "priority1_oa_pathway_screening_20260708" / "priority1_oa_pathway_snippets.md",
            settings.BASE_DIR / "curation_outputs" / "verified_oa_pathway_batch12_screening_20260708" / "verified_oa_batch12_summary.csv",
            settings.BASE_DIR / "curation_outputs" / "verified_oa_pathway_batch12_screening_20260708" / "verified_oa_batch12_snippets.md",
            settings.BASE_DIR / "curation_outputs" / "pathway_open_access_all_remaining_20260709" / "pesticidedb_all_remaining_open_access_check.csv",
            settings.BASE_DIR / "curation_outputs" / "pathway_open_access_all_remaining_20260709" / "pesticidedb_all_remaining_open_access_check.xlsx",
            settings.BASE_DIR / "curation_outputs" / "pathway_open_access_all_remaining_20260709" / "pesticidedb_all_remaining_open_access_summary.csv",
            settings.BASE_DIR / "curation_outputs" / "downloaded_oa_pathway_screening_20260709" / "downloaded_oa_pathway_screening_summary.csv",
            settings.BASE_DIR / "curation_outputs" / "downloaded_oa_pathway_screening_20260709" / "downloaded_oa_pathway_snippets.md",
            settings.BASE_DIR / "curation_outputs" / "pdf_readability_audit_20260707" / "pesticide_pdf_readability_summary.csv",
            settings.BASE_DIR / "curation_outputs" / "pdf_readability_audit_20260707" / "pesticide_pdf_readability_details.csv",
            settings.MEDIA_ROOT / "protein_structures" / "metadata" / "alphafold_download_report.csv",
        ]
        assets_dir = output_dir / "assets"
        assets_dir.mkdir(exist_ok=True)
        for asset in assets:
            if asset.exists():
                shutil.copy2(asset, assets_dir / asset.name)

        structure_dir = settings.MEDIA_ROOT / "protein_structures"
        for subdir_name in ["pdb", "images", "metadata"]:
            source_dir = structure_dir / subdir_name
            target_dir = assets_dir / "protein_structures" / subdir_name
            if source_dir.exists():
                if target_dir.exists():
                    shutil.rmtree(target_dir)
                shutil.copytree(source_dir, target_dir)

        self.stdout.write(self.style.SUCCESS(f"Exported PesticideDB release bundle to {output_dir}"))

    def _write_csv(self, path, queryset, fields):
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(fields)
            for obj in queryset.order_by("id"):
                writer.writerow([getattr(obj, field, "") or "" for field in fields])

    def _write_pathway_links_csv(self, path):
        fields = [
            "pesticide",
            "pathway_title",
            "reference_doi",
            "reference_title",
            "evidence_type",
            "directness",
            "confidence",
            "method",
            "summary",
        ]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(fields)
            queryset = PathwayEvidence.objects.select_related("pathway", "reference").order_by("id")
            for obj in queryset:
                writer.writerow([
                    obj.pathway.pesticide if obj.pathway_id else "",
                    obj.pathway.title if obj.pathway_id else "",
                    obj.reference.doi if obj.reference_id else "",
                    obj.reference.title if obj.reference_id else "",
                    obj.evidence_type,
                    obj.directness,
                    obj.confidence,
                    obj.method,
                    obj.summary,
                ])
