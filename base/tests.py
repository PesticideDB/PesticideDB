from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
from django.contrib import admin
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from .annotation_utils import (
    annotate_diamond_hits,
    detect_fasta_sequence_type,
    write_best_match_results,
)
from .management.commands.benchmark_annotation_thresholds import calculate_metrics
from .models import (
    AnnotationJob,
    GenomeAnnotationJob,
    NoEvidencePesticide,
    Pesticide,
    ProteinRecord,
    SiteVisitCounter,
)
from .views import _pathway_reference_context
from .utils import microorganism_count, pesticide_counts


class StatisticsTests(TestCase):
    def test_counts_are_case_normalized_and_microorganisms_are_unique(self):
        Pesticide.objects.create(pesticide="Atrazine", microorganism="Pseudomonas sp.")
        Pesticide.objects.create(pesticide="atrazine", microorganism="Pseudomonas sp.")
        Pesticide.objects.create(pesticide="Chlorpyrifos", microorganism="Bacillus sp.")
        NoEvidencePesticide.objects.create(pesticide="ATRAZINE")
        NoEvidencePesticide.objects.create(pesticide="Glyphosate")

        counts = pesticide_counts()

        self.assertEqual(counts["with_evidence"], 2)
        self.assertEqual(counts["no_evidence"], 1)
        self.assertEqual(counts["total"], 3)
        self.assertEqual(microorganism_count(), 2)


class PageSmokeTests(TestCase):
    def test_core_pages_render(self):
        for name in ["home", "about", "microorganisms", "proteins", "statistics", "citation_download", "help", "pathwayanalysis", "evidence_galaxy"]:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, name)

    def test_evidence_galaxy_data_links_database_entities(self):
        Pesticide.objects.create(
            pesticide="Carbaryl",
            microorganism="Pseudomonas sp.",
            gene="mcbA",
            enzyme="Hydrolases",
            enzyme_name_reported="Carbaryl hydrolase",
            metabolite_or_product="1-naphthol",
            publication_year=2020,
            doi="10.1000/carbaryl",
            reference="10.1000/carbaryl",
        )
        ProteinRecord.objects.create(
            pesticide="Carbaryl",
            microorganism="Pseudomonas sp.",
            reported_protein_name="Carbaryl hydrolase",
            gene_name="mcbA",
            doi="10.1000/carbaryl",
        )

        response = self.client.get(reverse("evidence_galaxy_data"), {"pesticide": "Carbaryl"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        kinds = {node["kind"] for node in payload["nodes"]}
        self.assertIn("pesticide", kinds)
        self.assertIn("reference", kinds)
        self.assertIn("microorganism", kinds)
        self.assertIn("gene", kinds)
        self.assertIn("protein", kinds)
        self.assertGreaterEqual(len(payload["links"]), 4)

    def test_evidence_galaxy_keeps_chemical_commas_in_enzyme_names(self):
        Pesticide.objects.create(
            pesticide="2,4-D",
            microorganism="Alcaligenes eutrophus JMP134",
            enzyme_name_reported="2,4-D monooxygenase",
            enzyme="Monooxygenases",
            publication_year=1987,
            doi="10.1128/jb.169.7.2950-2955.1987",
        )

        response = self.client.get(reverse("evidence_galaxy_data"), {"pesticide": "2,4-D"})

        self.assertEqual(response.status_code, 200)
        labels = {node["label"] for node in response.json()["nodes"]}
        self.assertIn("2,4-D monooxygenase", labels)
        self.assertNotIn("2", labels)

    def test_evidence_galaxy_pesticide_selector_includes_no_evidence_items(self):
        Pesticide.objects.create(pesticide="Carbaryl", microorganism="Pseudomonas sp.")
        NoEvidencePesticide.objects.create(pesticide="Imaginaryzine")

        response = self.client.get(reverse("evidence_galaxy_pesticides"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        by_name = {item["label"]: item for item in payload["pesticides"]}
        self.assertTrue(by_name["Carbaryl"]["has_evidence"])
        self.assertFalse(by_name["Imaginaryzine"]["has_evidence"])

    def test_reference_text_containing_doi_links_to_doi_resolver(self):
        reference = _pathway_reference_context("", "10.1128/jb.161.1.85-90.1985")

        self.assertEqual(reference["url"], "https://doi.org/10.1128/jb.161.1.85-90.1985")
        self.assertEqual(reference["text"], "10.1128/jb.161.1.85-90.1985")

    def test_supplemental_download_assets_are_available(self):
        for asset_name in ["validated-supplemental-proteins", "discovery-candidates"]:
            response = self.client.get(
                reverse("download_annotation_asset", args=[asset_name])
            )
            self.assertEqual(response.status_code, 200, asset_name)

    def test_protein_structure_routes_serve_local_files_without_media_urlconf(self):
        with TemporaryDirectory() as tmp:
            media_root = Path(tmp)
            pdb_dir = media_root / "protein_structures" / "pdb"
            image_dir = media_root / "protein_structures" / "images"
            pdb_dir.mkdir(parents=True)
            image_dir.mkdir(parents=True)
            (pdb_dir / "TEST0001.pdb").write_text(
                "ATOM      1  CA  ALA A   1      11.104  13.207   2.100  1.00 96.20           C\n"
            )
            (image_dir / "TEST0001.svg").write_text(
                "<svg xmlns=\"http://www.w3.org/2000/svg\"></svg>"
            )
            ProteinRecord.objects.create(
                pesticidedb_protein_id="TEST0001",
                reported_protein_name="Example enzyme",
            )

            with override_settings(MEDIA_ROOT=media_root, DJANGO_SERVE_MEDIA=False):
                detail_response = self.client.get(reverse("protein_detail", args=["TEST0001"]))
                pdb_response = self.client.get(reverse("protein_pdb_file", args=["TEST0001"]))
                preview_response = self.client.get(
                    reverse("protein_structure_preview", args=["TEST0001"])
                )

            self.assertEqual(detail_response.status_code, 200)
            self.assertContains(detail_response, "/proteins/TEST0001/structure/pdb/")
            self.assertNotContains(detail_response, "/media/protein_structures/pdb/TEST0001.pdb")
            self.assertEqual(pdb_response.status_code, 200)
            self.assertIn(b"ATOM", b"".join(pdb_response.streaming_content))
            self.assertEqual(preview_response.status_code, 200)

    def test_all_match_csv_downloads_are_separate(self):
        with TemporaryDirectory() as tmp:
            media_root = Path(tmp)
            gene_job = AnnotationJob.objects.create(job_id="MS1234567", status="done")
            genome_job = GenomeAnnotationJob.objects.create(job_id="SM1234567", status="done")
            gene_dir = media_root / "annotation_jobs" / gene_job.job_id
            genome_dir = media_root / "genome_jobs" / genome_job.job_id
            gene_dir.mkdir(parents=True)
            genome_dir.mkdir(parents=True)
            (gene_dir / f"{gene_job.job_id}_all_validated_matches.csv").write_text("query\nq1\n")
            (genome_dir / f"{genome_job.job_id}_all_validated_matches.csv").write_text("query\nq1\n")

            with override_settings(MEDIA_ROOT=media_root):
                gene_response = self.client.get(
                    reverse("annotategene_all_matches_download", args=[gene_job.job_id])
                )
                genome_response = self.client.get(
                    reverse("annotategenome_all_matches_download", args=[genome_job.job_id])
                )

            self.assertEqual(gene_response.status_code, 200)
            self.assertEqual(genome_response.status_code, 200)

    def test_site_visit_counter_counts_successful_html_pages(self):
        self.client.get(reverse("home"))
        self.client.get(reverse("about"))
        self.client.get("/missing-page/")

        counter = SiteVisitCounter.objects.get(key="site")
        self.assertEqual(counter.total_visits, 2)

        response = self.client.get(reverse("home"))
        self.assertNotContains(response, "Website visits:")

    def test_site_visit_counter_is_available_in_admin(self):
        self.assertIn(SiteVisitCounter, admin.site._registry)


class AnnotationUtilityTests(TestCase):
    def test_fasta_type_detection(self):
        with TemporaryDirectory() as tmp:
            dna_path = Path(tmp) / "dna.fasta"
            protein_path = Path(tmp) / "protein.fasta"
            dna_path.write_text(">q1\nATGCNNATGC\n")
            protein_path.write_text(">q1\nMKWVTFISLL\n")

            self.assertEqual(detect_fasta_sequence_type(dna_path), "dna")
            self.assertEqual(detect_fasta_sequence_type(protein_path), "protein")

    def test_diamond_hits_map_to_protein_records(self):
        protein = ProteinRecord.objects.create(
            pesticide="Atrazine",
            microorganism="Pseudomonas sp.",
            evidence_type="enzyme assay",
            enzyme_class="hydrolase",
            reported_protein_name="Atrazine chlorohydrolase",
            gene_name="atzA",
            ncbi_protein_accession="ABC123.1",
            doi="10.1000/example",
        )

        with TemporaryDirectory() as tmp:
            diamond_path = Path(tmp) / "diamond.tsv"
            output_path = Path(tmp) / "annotation.csv"
            diamond_path.write_text("query1\tABC123.1\t82.5\t300\t1e-50\t240\n")

            result_count = annotate_diamond_hits(diamond_path, output_path)

            self.assertEqual(result_count, 1)
            output = output_path.read_text()
            self.assertIn(protein.pesticidedb_protein_id, output)
            self.assertIn("Atrazine chlorohydrolase", output)

    def test_diamond_hits_calculate_query_and_subject_coverage(self):
        ProteinRecord.objects.create(
            pesticide="Atrazine",
            microorganism="Pseudomonas sp.",
            evidence_type="enzyme assay",
            enzyme_class="hydrolase",
            reported_protein_name="Atrazine chlorohydrolase",
            ncbi_protein_accession="ABC123.1",
        )

        with TemporaryDirectory() as tmp:
            diamond_path = Path(tmp) / "diamond.tsv"
            output_path = Path(tmp) / "annotation.csv"
            diamond_path.write_text(
                "query1\tABC123.1\t82.5\t150\t1e-50\t240\t50\t75\t90\n"
            )

            annotate_diamond_hits(diamond_path, output_path)
            output = pd.read_csv(output_path).iloc[0]

            self.assertEqual(output["query_coverage"], 50.0)
            self.assertEqual(output["subject_coverage"], 75.0)
            self.assertEqual(output["similarity"], 90.0)
            self.assertEqual(output["passes_screening_thresholds"], "Yes")

    def test_diamond_hits_retain_and_rank_all_significant_matches(self):
        for accession, name in [
            ("ABC123.1", "Best hydrolase"),
            ("XYZ789.1", "Second hydrolase"),
        ]:
            ProteinRecord.objects.create(
                pesticide="Atrazine",
                microorganism="Pseudomonas sp.",
                evidence_type="enzyme assay",
                enzyme_class="hydrolase",
                reported_protein_name=name,
                ncbi_protein_accession=accession,
            )

        with TemporaryDirectory() as tmp:
            diamond_path = Path(tmp) / "diamond.tsv"
            output_path = Path(tmp) / "annotation.csv"
            diamond_path.write_text(
                "query1\tXYZ789.1\t55\t180\t1e-30\t180\t75\t70\t65\n"
                "query1\tABC123.1\t80\t200\t1e-60\t300\t85\t80\t88\n"
            )

            result_count = annotate_diamond_hits(
                diamond_path,
                output_path,
                review_identity=70,
                review_evalue=1e-50,
                review_query_coverage=80,
            )
            output = pd.read_csv(output_path)

            self.assertEqual(result_count, 2)
            self.assertEqual(output["match_rank"].tolist(), [1, 2])
            self.assertEqual(output.iloc[0]["ncbi_protein_accession"], "ABC123.1")
            self.assertEqual(
                output["passes_screening_thresholds"].tolist(),
                ["Yes", "No"],
            )

            best_path = Path(tmp) / "best.csv"
            best_count = write_best_match_results(output_path, best_path)
            best = pd.read_csv(best_path)

            self.assertEqual(best_count, 1)
            self.assertEqual(best.iloc[0]["match_rank"], 1)

    def test_threshold_metrics(self):
        truth = pd.Series([True, True, False, False])
        predicted = pd.Series([True, False, True, False])

        metrics = calculate_metrics(truth, predicted)

        self.assertEqual(metrics["tp"], 1)
        self.assertEqual(metrics["fp"], 1)
        self.assertEqual(metrics["tn"], 1)
        self.assertEqual(metrics["fn"], 1)
        self.assertEqual(metrics["sensitivity"], 0.5)
        self.assertEqual(metrics["specificity"], 0.5)

    def test_diamond_hits_fallback_to_master_metadata(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            diamond_path = tmp_path / "diamond.tsv"
            output_path = tmp_path / "annotation.csv"
            master_path = tmp_path / "PBDB_master.xlsx"

            diamond_path.write_text("query1\tQCG69016.1\t99.0\t120\t1e-80\t300\n")
            pd_data = {
                "pesticide": ["Flonicamid"],
                "microorganism": ["Ensifer adhaerens"],
                "evidence_type": ["Purified"],
                "enzyme_class": ["Hydrolase"],
                "reported_protein_name": ["Nitrile hydratase"],
                "pesticidedb_protein_id": [""],
                "gene_name": ["pnhA"],
                "ncbi_protein_accession": ["QCG69016.1"],
                "year": [2021],
                "doi": ["10.1186/example"],
                "collection_category": ["CURATED"],
            }
            pd.DataFrame(pd_data).to_excel(master_path, index=False)

            result_count = annotate_diamond_hits(
                diamond_path,
                output_path,
                master_metadata_path=master_path,
            )

            output = output_path.read_text()
            self.assertEqual(result_count, 1)
            self.assertIn("Flonicamid", output)
            self.assertIn("QCG69016.1", output)

    def test_diamond_hits_use_master_pesticidedb_id_when_no_record_exists(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            diamond_path = tmp_path / "diamond.tsv"
            output_path = tmp_path / "annotation.csv"
            master_path = tmp_path / "PBDB_master_with_ids.xlsx"

            diamond_path.write_text("query1\tAAR31035.1\t40.0\t120\t1e-20\t100\n")
            pd.DataFrame({
                "pesticide": ["2,4-D"],
                "microorganism": ["Ralstonia eutropha"],
                "evidence_type": ["Genome annotation"],
                "enzyme_class": ["Monooxygenase"],
                "reported_protein_name": ["2,4-dichlorophenol 6-monooxygenase"],
                "pesticidedb_protein_id": ["PDBP9999"],
                "gene_name": ["tfdB"],
                "ncbi_protein_accession": ["AAR31035.1"],
                "year": [2003],
                "doi": ["10.1000/example"],
                "collection_category": ["CURATED"],
            }).to_excel(master_path, index=False)

            result_count = annotate_diamond_hits(
                diamond_path,
                output_path,
                master_metadata_path=master_path,
            )

            output = output_path.read_text()
            self.assertEqual(result_count, 1)
            self.assertIn("PDBP9999", output)
