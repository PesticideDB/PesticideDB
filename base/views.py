from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Count, Q
from django.http import HttpResponse, FileResponse, Http404, JsonResponse
from django.conf import settings
from django.urls import reverse
from django.views.decorators.http import require_POST

import csv
import json
import os
import re
import threading
import random
import subprocess

import requests
import xml.etree.ElementTree as ET

from .annotation_utils import (
    annotate_diamond_hits,
    detect_fasta_sequence_type,
    read_annotation_results,
    write_best_match_results,
)
from .forms import DataSubmissionForm
from .models import (
    AnnotationJob,
    Compound,
    DataSubmission,
    DegradationPathway,
    DegradationPathwayStep,
    GenomeAnnotationJob,
    NoEvidencePesticide,
    PathwayEvidence,
    Pesticide,
    ProteinRecord,
)
from base.utils import (
    canonical_pesticide_names,
    clean_pesticide_name,
    curated_pathway_pesticide_names,
    database_summary,
    microorganism_count,
    microorganism_record_count,
    pesticide_counts,
)


EVIDENCE_TYPE_CATEGORIES = [
    "Purified (Kinetics)",
    "Purified (Activity)",
    "Purified (Product ID)",
    "Recombinant (Activity)",
    "Genetic / Expression",
    "Whole-cell / Crude",
    "Gene Only",
    "Structure Only",
]


def categorize_protein_evidence_type(value):
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    lower = text.casefold()
    if not text:
        return ""
    if "structure only" in lower:
        return "Structure Only"
    if "kinetic" in lower or "kinetics" in lower:
        return "Purified (Kinetics)"
    if "product id" in lower or "product identification" in lower:
        return "Purified (Product ID)"
    if "recombinant" in lower:
        return "Recombinant (Activity)"
    if "knockout" in lower or "expression" in lower or "genetic evidence" in lower or "experimental/genetic" in lower:
        return "Genetic / Expression"
    if lower == "gene only" or lower.startswith("gene only"):
        return "Gene Only"
    if "purified" in lower or "enzymatic evidence" in lower or "enzyme cleaved" in lower or "enzyme assay" in lower or "c-p lyase" in lower:
        return "Purified (Activity)"
    if "whole-cell" in lower or "whole cell" in lower or "crude" in lower or "experimental evidence" in lower or "experimental and enzymatic" in lower:
        return "Whole-cell / Crude"
    return "Whole-cell / Crude"


def categorize_biodegradation_evidence(record):
    evidence_text = " ".join(
        str(value or "")
        for value in [
            record.evidence_by_microbe,
            record.evidence_of_enzyme,
            record.evidence_level,
            record.assay_type,
            record.gene,
            record.enzyme,
        ]
    )
    lower = evidence_text.casefold()
    gene_only_terms = [
        "genomic evidence",
        "genome evidence",
        "gene only",
        "sequence homology",
        "homology prediction",
        "metagenomic",
    ]
    direct_experimental_terms = [
        "experimental evidence",
        "enzymatic evidence",
        "enzyme assay",
        "purified",
        "recombinant",
        "kinetic",
        "knockout",
        "expression",
    ]
    if any(term in lower for term in gene_only_terms) and not any(
        term in lower for term in direct_experimental_terms
    ):
        return "Gene Only"
    return categorize_protein_evidence_type(evidence_text)


def home(request):
    counts = pesticide_counts()
    summary = database_summary()

    proteins_count = ProteinRecord.objects.count()

    context = {
        "total_pesticides": counts["total"],
        "pesticides_with_evidence": counts["with_evidence"],
        "pesticides_no_evidence": counts["no_evidence"],
        "pesticide_count": counts["total"],
        "microorganisms_count": microorganism_count(),
        "proteins_count": proteins_count,
        "protein_version": "1.0",
        **summary,
    }
    return render(request, "base/home.html", context)


def about(request):
    counts = pesticide_counts()

    context = {
        "total_pesticides": counts["total"],
        "pesticides_with_evidence": counts["with_evidence"],
        "pesticides_no_evidence": counts["no_evidence"],
        "pesticide_count": counts["total"],
        "microorganisms_count": microorganism_count(),
    }
    return render(request, "base/about.html", context)


def contact(request):
    return render(request, "base/contact.html")


def help(request):
    counts = pesticide_counts()
    context = {
        "total_pesticides": counts["total"],
        "pesticides_with_evidence": counts["with_evidence"],
        "pesticides_no_evidence": counts["no_evidence"],
        "microorganisms_count": microorganism_count(),
        **database_summary(),
    }
    return render(request, "base/help.html", context)


def citation_download(request):
    counts = pesticide_counts()
    summary = database_summary()
    context = {
        "total_pesticides": counts["total"],
        "pesticides_with_evidence": counts["with_evidence"],
        "pesticides_no_evidence": counts["no_evidence"],
        "microorganisms_count": microorganism_count(),
        "proteins_count": ProteinRecord.objects.count(),
        **summary,
    }
    return render(request, "base/citation_download.html", context)


def download_proteins_csv(request):
    fields = [
        "pesticidedb_protein_id",
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
    ]
    return queryset_csv_response(
        ProteinRecord.objects.all().order_by("pesticidedb_protein_id"),
        fields,
        "pesticidedb_proteins.csv",
    )


def download_pesticides_csv(request):
    fields = [
        "pesticide",
        "microorganism",
        "culture_type",
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
    ]
    return queryset_csv_response(
        Pesticide.objects.all().order_by("pesticide", "microorganism"),
        fields,
        "pesticidedb_biodegradation_records.csv",
    )


def download_no_evidence_csv(request):
    fields = ["pesticide", "evidence_of_biodegradation"]
    evidenced = {
        name.casefold()
        for name in Pesticide.objects
        .exclude(pesticide="")
        .exclude(pesticide__isnull=True)
        .values_list("pesticide", flat=True)
    }
    records = [
        row
        for row in NoEvidencePesticide.objects.all().order_by("pesticide")
        if (row.pesticide or "").strip().casefold() not in evidenced
    ]
    return queryset_csv_response(
        records,
        fields,
        "pesticidedb_no_evidence_pesticides.csv",
    )


def download_pathway_evidence_csv(request):
    fields = [
        "pesticide",
        "title",
        "microorganism",
        "completeness",
        "summary",
        "doi",
        "reference",
    ]
    return queryset_csv_response(
        DegradationPathway.objects.all().order_by("pesticide", "title"),
        fields,
        "pesticidedb_pathway_evidence_records.csv",
    )


def download_annotation_asset(request, asset_name):
    pathway_data_dir = settings.BASE_DIR / "data_files" / "pathway"
    allowed_assets = {
        "protein-master": settings.BASE_DIR / "data_files" / "protein" / "PBDB_Proteins_Master.xlsx",
        "reference-fasta": settings.PBDB_ANNOTATION_DIR / "data" / "pbdb_validated_reference_proteins.faa",
        "validated-supplemental-proteins": (
            settings.BASE_DIR
            / "curation_outputs"
            / "supplemented_validated_protein_evidence_15.xlsx"
        ),
        "discovery-candidates": (
            settings.BASE_DIR
            / "curation_outputs"
            / "supplemented_discovery_candidates_179.xlsx"
        ),
        "structure-report": settings.MEDIA_ROOT / "protein_structures" / "metadata" / "alphafold_download_report.csv",
        "biodegradation-master-xlsx": settings.BASE_DIR / "data_files" / "core" / "pesticide_data.xlsx",
        "biodegradation-master-csv": settings.BASE_DIR / "data_files" / "core" / "pesticide_data.csv",
        "no-evidence-master": settings.BASE_DIR / "data_files" / "core" / "no_evidence_pesticide.xlsx",
        "protein-master-with-2025-2026": settings.BASE_DIR / "data_files" / "protein" / "PBDB_Proteins_Master.xlsx",
        "pathway-evidence-master": pathway_data_dir / "PesticideDB_Pathway_Evidence_Master.xlsx",
        "pathway-evidence-master-csv": pathway_data_dir / "PesticideDB_Pathway_Evidence_Master.csv",
        "stepwise-pathway-master": pathway_data_dir / "PesticideDB_Stepwise_Pathway_Master.xlsx",
        "stepwise-pathway-master-csv": pathway_data_dir / "PesticideDB_Stepwise_Pathway_Master.csv",
        "compound-smiles-structure-inventory": pathway_data_dir / "PesticideDB_Compound_SMILES_Structure_Inventory.csv",
        "compound-smiles-smi": pathway_data_dir / "PesticideDB_Compound_SMILES.smi",
        "missing-stepwise-pathway-information": pathway_data_dir / "PesticideDB_Missing_Stepwise_Pathway_Information.xlsx",
        "pathway-doi-redownload-manifest": pathway_data_dir / "PesticideDB_Pathway_DOI_Redownload_Manifest.csv",
    }
    path = allowed_assets.get(asset_name)
    if not path or not path.exists():
        raise Http404("Download file not found.")
    return FileResponse(open(path, "rb"), as_attachment=True, filename=path.name)


def queryset_csv_response(queryset, fields, filename):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(fields)
    for obj in queryset:
        writer.writerow([getattr(obj, field, "") or "" for field in fields])
    return response


def microorganisms(request):
    results = []
    is_search = False

    microorganism = request.GET.get('microorganism', '').strip()
    pesticide = request.GET.get('pesticide', '').strip()
    evidence = request.GET.get('evidence', '').strip()
    gene = request.GET.get('gene', '').strip()
    protein = request.GET.get('protein', '').strip()
    environment = request.GET.get('environment', '').strip()
    location = request.GET.get('location', '').strip()
    culture_type = request.GET.get('culture_type', '').strip()

    no_evidence_message = None
    if pesticide:
        ne_obj = NoEvidencePesticide.objects.filter(pesticide__iexact=pesticide).first()
        if ne_obj:
            no_evidence_message = ne_obj.evidence_of_biodegradation

    queryset = Pesticide.objects.all()
    filters = {}

    if microorganism:
        filters['microorganism__icontains'] = microorganism
        is_search = True
    if pesticide:
        filters['pesticide__iexact'] = pesticide
        is_search = True
    if evidence:
        is_search = True
    if gene:
        filters['gene__icontains'] = gene
        is_search = True
    if protein:
        filters['enzyme__icontains'] = protein
        is_search = True
    if environment:
        filters['isolation_environment__icontains'] = environment
        is_search = True
    if location:
        filters['isolation_location__icontains'] = location
        is_search = True
    if culture_type:
        filters['culture_type__iexact'] = culture_type
        is_search = True

    if pesticide and no_evidence_message:
        results = queryset.none()
        is_search = True
    else:
        if filters or evidence:
            results = queryset.filter(**filters).order_by('microorganism', 'pesticide')
            if evidence:
                results = [
                    record for record in results
                    if categorize_biodegradation_evidence(record) == evidence
                ]
            is_search = True
        else:
            results = queryset.order_by('microorganism', 'pesticide')[:100]
            is_search = False

    base_qs = Pesticide.objects.all()

    microorganisms_list = (
        base_qs.values_list("microorganism", flat=True)
        .exclude(microorganism__isnull=True).exclude(microorganism="")
        .exclude(microorganism__iexact="not specified")
        .distinct().order_by("microorganism")
    )

    pesticides_list = canonical_pesticide_names()

    evidence_list = EVIDENCE_TYPE_CATEGORIES

    gene_list = (
        base_qs.values_list("gene", flat=True)
        .exclude(gene__isnull=True).exclude(gene="")
        .distinct().order_by("gene")
    )

    protein_list = (
        base_qs.values_list("enzyme", flat=True)
        .exclude(enzyme__isnull=True).exclude(enzyme="")
        .distinct().order_by("enzyme")
    )

    environment_list = (
        base_qs.values_list("isolation_environment", flat=True)
        .exclude(isolation_environment__isnull=True).exclude(isolation_environment="")
        .distinct().order_by("isolation_environment")
    )

    location_list = (
        base_qs.values_list("isolation_location", flat=True)
        .exclude(isolation_location__isnull=True).exclude(isolation_location="")
        .distinct().order_by("isolation_location")
    )

    culture_type_list = (
        base_qs.values_list("culture_type", flat=True)
        .exclude(culture_type__isnull=True).exclude(culture_type="")
        .distinct().order_by("culture_type")
    )

    total_count = len(results) if isinstance(results, list) else results.count()

    context = {
        'results': results,
        'is_search': is_search,
        'total_count': total_count,
        'no_evidence_message': no_evidence_message,

        'microorganisms_list': microorganisms_list,
        'pesticides_list': pesticides_list,
        'evidence_list': evidence_list,
        'gene_list': gene_list,
        'protein_list': protein_list,
        'environment_list': environment_list,
        'location_list': location_list,
        'culture_type_list': culture_type_list,

        'selected_microorganism': microorganism,
        'selected_pesticide': pesticide,
        'selected_evidence': evidence,
        'selected_gene': gene,
        'selected_protein': protein,
        'selected_environment': environment,
        'selected_location': location,
        'selected_culture_type': culture_type,
    }
    return render(request, 'base/microorganisms.html', context)


# ================= PROTEINS LIST =================

def proteins(request):
    """
    Proteins list with cascading dropdowns.
    IMPORTANT:
    - Filters applied to results AND dropdown values (cascading behavior)
    - Supports both pesticidedb_protein_id and pbdb_protein_id
    """

    base_qs = ProteinRecord.objects.all().order_by("id")

    selected_protein = request.GET.get("protein", "").strip()
    selected_protein_id = request.GET.get("protein_id", "").strip()
    selected_microorganism = request.GET.get("microorganism", "").strip()
    selected_pesticide = request.GET.get("pesticide", "").strip()
    selected_enzyme_class = request.GET.get("enzyme_class", "").strip()
    selected_evidence_type = request.GET.get("evidence_type", "").strip()
    selected_collection_category = request.GET.get("collection_category", "").strip()
    selected_uniprot_available = request.GET.get("uniprot_available", "").strip()
    selected_structure_available = request.GET.get("structure_available", "").strip()

    qs = base_qs

    if selected_protein:
        qs = qs.filter(reported_protein_name=selected_protein)

    if selected_protein_id:
        qs = qs.filter(
            Q(pesticidedb_protein_id=selected_protein_id) |
            Q(pbdb_protein_id=selected_protein_id)
        )

    if selected_microorganism:
        qs = qs.filter(microorganism=selected_microorganism)

    if selected_pesticide:
        qs = qs.filter(pesticide__iexact=selected_pesticide)

    if selected_enzyme_class:
        qs = qs.filter(enzyme_class=selected_enzyme_class)

    if selected_evidence_type:
        matching_evidence_types = [
            value for value in base_qs.values_list("evidence_type", flat=True).distinct()
            if categorize_protein_evidence_type(value) == selected_evidence_type
        ]
        qs = qs.filter(evidence_type__in=matching_evidence_types)

    if selected_collection_category:
        qs = qs.filter(collection_category=selected_collection_category)

    if selected_uniprot_available == "available":
        qs = qs.exclude(uniprot_accession__isnull=True).exclude(uniprot_accession="")
    elif selected_uniprot_available == "not_available":
        qs = qs.filter(Q(uniprot_accession__isnull=True) | Q(uniprot_accession=""))

    if selected_structure_available:
        structure_ids = []
        structure_dir = settings.MEDIA_ROOT / "protein_structures" / "pdb"
        for protein in qs.only("id", "pesticidedb_protein_id", "pbdb_protein_id"):
            display_id = protein.pesticidedb_protein_id or protein.pbdb_protein_id
            has_structure = bool(display_id and (structure_dir / f"{display_id}.pdb").exists())
            if (selected_structure_available == "available" and has_structure) or (
                selected_structure_available == "not_available" and not has_structure
            ):
                structure_ids.append(protein.id)
        qs = qs.filter(id__in=structure_ids)

    is_search = any([
        selected_protein, selected_protein_id, selected_microorganism,
        selected_pesticide, selected_enzyme_class, selected_evidence_type,
        selected_collection_category, selected_uniprot_available,
        selected_structure_available
    ])

    total_count = qs.count()
    results = list(qs[:100])
    for protein in results:
        display_id = protein.pesticidedb_protein_id or protein.pbdb_protein_id
        protein.has_structure = bool(
            display_id
            and (settings.MEDIA_ROOT / "protein_structures" / "pdb" / f"{display_id}.pdb").exists()
        )
        protein.evidence_type_category = categorize_protein_evidence_type(protein.evidence_type)

    proteins_list = (
        qs.values_list("reported_protein_name", flat=True)
        .exclude(reported_protein_name__isnull=True)
        .exclude(reported_protein_name="")
        .distinct()
        .order_by("reported_protein_name")
    )

    ids_a = (
        qs.exclude(pesticidedb_protein_id__isnull=True)
          .exclude(pesticidedb_protein_id="")
          .exclude(pesticidedb_protein_id__iexact="nan")
          .values_list("pesticidedb_protein_id", flat=True)
    )
    protein_ids_list = sorted(set(ids_a))

    microorganisms_list = (
        qs.values_list("microorganism", flat=True)
        .exclude(microorganism__isnull=True)
        .exclude(microorganism="")
        .distinct()
        .order_by("microorganism")
    )

    pesticides_list = canonical_pesticide_names()

    enzyme_class_list = (
        qs.values_list("enzyme_class", flat=True)
        .exclude(enzyme_class__isnull=True)
        .exclude(enzyme_class="")
        .distinct()
        .order_by("enzyme_class")
    )

    evidence_values = (
        qs.values_list("evidence_type", flat=True)
        .exclude(evidence_type__isnull=True)
        .exclude(evidence_type="")
        .distinct()
    )
    available_evidence_categories = {
        categorize_protein_evidence_type(value) for value in evidence_values
    }
    evidence_type_list = [
        category for category in EVIDENCE_TYPE_CATEGORIES
        if category in available_evidence_categories
    ]

    collection_category_list = (
        qs.values_list("collection_category", flat=True)
        .exclude(collection_category__isnull=True)
        .exclude(collection_category="")
        .distinct()
        .order_by("collection_category")
    )

    context = {
        "results": results,
        "total_count": total_count,
        "is_search": is_search,

        "proteins_list": proteins_list,
        "protein_ids_list": protein_ids_list,
        "microorganisms_list": microorganisms_list,
        "pesticides_list": pesticides_list,
        "enzyme_class_list": enzyme_class_list,
        "evidence_type_list": evidence_type_list,
        "collection_category_list": collection_category_list,

        "selected_protein": selected_protein,
        "selected_protein_id": selected_protein_id,
        "selected_microorganism": selected_microorganism,
        "selected_pesticide": selected_pesticide,
        "selected_enzyme_class": selected_enzyme_class,
        "selected_evidence_type": selected_evidence_type,
        "selected_collection_category": selected_collection_category,
        "selected_uniprot_available": selected_uniprot_available,
        "selected_structure_available": selected_structure_available,
    }

    return render(request, "base/proteins.html", context)


# ================= PROTEIN DETAIL =================

def protein_detail(request, pesticidedb_protein_id):
    p = get_object_or_404(
        ProteinRecord,
        Q(pesticidedb_protein_id=pesticidedb_protein_id) |
        Q(pbdb_protein_id=pesticidedb_protein_id)
    )

    display_id = p.pesticidedb_protein_id or p.pbdb_protein_id or pesticidedb_protein_id

    pdb_abs = protein_structure_pdb_path(display_id)

    structure_image_url = None
    for image_ext in ("png", "svg"):
        img_abs = protein_structure_preview_path(display_id, image_ext)
        if os.path.exists(img_abs):
            structure_image_url = reverse("protein_structure_preview", args=[display_id])
            break

    pdb_structure_url = reverse("protein_pdb_file", args=[display_id]) if os.path.exists(pdb_abs) else None
    pdb_download_url = f"{pdb_structure_url}?download=1" if pdb_structure_url else None
    uniprot_accession = (p.uniprot_accession or "").strip()
    uniprot_url = (
        f"https://www.uniprot.org/uniprotkb/{uniprot_accession}/entry"
        if uniprot_accession else None
    )
    structure_summary = parse_pdb_structure_summary(pdb_abs) if os.path.exists(pdb_abs) else {}
    structure_source = alphafold_structure_source(display_id)
    if structure_summary and structure_source:
        structure_summary.update(structure_source)
    if structure_summary and p.microorganism:
        structure_summary["organism"] = p.microorganism

    context = {
        "p": p,
        "structure_image_url": structure_image_url,
        "pdb_structure_url": pdb_structure_url,
        "pdb_download_url": pdb_download_url,
        "uniprot_url": uniprot_url,
        "structure_summary": structure_summary,
        "prediction_software": structure_summary.get("method", "-") if pdb_download_url else "-",
        "file_format": "PDB",
    }

    return render(request, "base/protein_detail.html", context)


def protein_structure_pdb_path(display_id):
    return os.path.join(
        settings.MEDIA_ROOT,
        "protein_structures",
        "pdb",
        f"{display_id}.pdb",
    )


def protein_structure_preview_path(display_id, image_ext):
    return os.path.join(
        settings.MEDIA_ROOT,
        "protein_structures",
        "images",
        f"{display_id}.{image_ext}",
    )


def protein_pdb_file(request, pesticidedb_protein_id):
    p = get_object_or_404(
        ProteinRecord,
        Q(pesticidedb_protein_id=pesticidedb_protein_id) |
        Q(pbdb_protein_id=pesticidedb_protein_id)
    )
    display_id = p.pesticidedb_protein_id or p.pbdb_protein_id or pesticidedb_protein_id
    pdb_path = protein_structure_pdb_path(display_id)
    if not os.path.exists(pdb_path):
        raise Http404("Protein structure file not found.")
    return FileResponse(
        open(pdb_path, "rb"),
        as_attachment=request.GET.get("download") == "1",
        filename=f"{display_id}.pdb",
        content_type="chemical/x-pdb",
    )


def protein_structure_preview(request, pesticidedb_protein_id):
    p = get_object_or_404(
        ProteinRecord,
        Q(pesticidedb_protein_id=pesticidedb_protein_id) |
        Q(pbdb_protein_id=pesticidedb_protein_id)
    )
    display_id = p.pesticidedb_protein_id or p.pbdb_protein_id or pesticidedb_protein_id
    for image_ext, content_type in (("png", "image/png"), ("svg", "image/svg+xml")):
        image_path = protein_structure_preview_path(display_id, image_ext)
        if os.path.exists(image_path):
            return FileResponse(
                open(image_path, "rb"),
                as_attachment=False,
                filename=f"{display_id}.{image_ext}",
                content_type=content_type,
            )
    raise Http404("Protein structure preview not found.")


def parse_pdb_structure_summary(pdb_path):
    summary = {
        "method": "AlphaFold2 monomer prediction",
        "model_source": "AlphaFold Protein Structure Database",
        "database_model_version": "-",
        "source_url": "",
        "resolution": "Not applicable",
        "chain": "-",
        "organism": "-",
        "tax_id": "-",
        "molecule": "-",
        "atom_count": 0,
        "residue_count": 0,
        "mean_plddt": None,
        "confidence_label": "-",
    }
    residues = set()
    ca_confidences = []

    with open(pdb_path, "r", errors="ignore") as handle:
        for line in handle:
            if line.startswith("COMPND") and "MOLECULE:" in line:
                summary["molecule"] = clean_pdb_header_value(line.split("MOLECULE:", 1)[1])
            elif line.startswith("COMPND") and "CHAIN:" in line:
                summary["chain"] = clean_pdb_header_value(line.split("CHAIN:", 1)[1])
            elif line.startswith("SOURCE") and "ORGANISM_SCIENTIFIC:" in line:
                summary["organism"] = clean_pdb_header_value(
                    line.split("ORGANISM_SCIENTIFIC:", 1)[1]
                )
            elif line.startswith("SOURCE") and "ORGANISM_TAXID:" in line:
                summary["tax_id"] = clean_pdb_header_value(line.split("ORGANISM_TAXID:", 1)[1])
            elif line.startswith("ATOM"):
                summary["atom_count"] += 1
                chain_id = line[21].strip()
                residue_number = line[22:26].strip()
                insertion_code = line[26].strip()
                if residue_number:
                    residues.add((chain_id, residue_number, insertion_code))
                if line[12:16].strip() == "CA":
                    try:
                        ca_confidences.append(float(line[60:66].strip()))
                    except ValueError:
                        pass

    summary["residue_count"] = len(residues)
    if ca_confidences:
        mean_plddt = sum(ca_confidences) / len(ca_confidences)
        summary["mean_plddt"] = round(mean_plddt, 1)
        if mean_plddt >= 90:
            summary["confidence_label"] = "Very high"
        elif mean_plddt >= 70:
            summary["confidence_label"] = "Confident"
        elif mean_plddt >= 50:
            summary["confidence_label"] = "Low"
        else:
            summary["confidence_label"] = "Very low"
    return summary


def alphafold_structure_source(display_id):
    report_path = (
        settings.MEDIA_ROOT
        / "protein_structures"
        / "metadata"
        / "alphafold_download_report.csv"
    )
    if not report_path.exists():
        return {}

    with report_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("pesticidedb_protein_id") != display_id:
                continue
            source_url = row.get("source_url", "")
            version_match = re.search(r"model_v(\d+)", source_url)
            return {
                "model_source": "AlphaFold Protein Structure Database",
                "database_model_version": (
                    f"AFDB model v{version_match.group(1)}"
                    if version_match else "Current AFDB API model"
                ),
                "source_url": source_url,
            }
    return {}


def clean_pdb_header_value(value):
    return value.replace(";", "").strip().title() or "-"


def _efetch_fasta(db, acc, timeout=20):
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    params = {"db": db, "id": acc, "rettype": "fasta", "retmode": "text"}
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.text.strip()


def _esearch_uid(db, term, timeout=20):
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {"db": db, "term": term, "retmode": "xml"}
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    ids = root.findall(".//IdList/Id")
    return ids[0].text if ids else None


def _elink(dbfrom, dbto, uid, timeout=20):
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
    params = {"dbfrom": dbfrom, "db": dbto, "id": uid, "retmode": "xml"}
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    ids = root.findall(".//LinkSetDb/Link/Id")
    return ids[0].text if ids else None


@require_POST
def fetch_ncbi_fasta(request, pesticidedb_protein_id):
    """
    Handles BOTH protein and nucleotide accessions.
    Always stores PROTEIN FASTA (amino acid sequence).
    Python 3.9 compatible.
    """
    p = get_object_or_404(
        ProteinRecord,
        Q(pesticidedb_protein_id=pesticidedb_protein_id) |
        Q(pbdb_protein_id=pesticidedb_protein_id)
    )

    acc = (p.ncbi_protein_accession or "").strip()
    if not acc:
        return HttpResponse(
            "No NCBI accession found in ncbi_protein_accession.",
            status=400
        )

    # 1) Try as protein accession
    try:
        fasta = _efetch_fasta("protein", acc)

    except requests.HTTPError:
        # 2) Try resolving nucleotide -> protein
        try:
            nuccore_uid = _esearch_uid("nuccore", acc)
            if not nuccore_uid:
                return HttpResponse(
                    f"Could not find accession {acc} in NCBI protein or nuccore.",
                    status=400
                )

            protein_uid = _elink("nuccore", "protein", nuccore_uid)
            if not protein_uid:
                return HttpResponse(
                    f"Accession {acc} is nucleotide and has no linked protein record.",
                    status=400
                )

            fasta = _efetch_fasta("protein", protein_uid)

        except Exception as e:
            return HttpResponse(
                f"Failed to resolve nucleotide→protein from NCBI: {e}",
                status=500
            )

    except requests.RequestException as e:
        return HttpResponse(
            f"Failed to fetch FASTA from NCBI: {e}",
            status=500
        )

    if not fasta.startswith(">"):
        return HttpResponse(
            "NCBI did not return a FASTA record. Check accession.",
            status=400
        )

    # Save amino-acid sequence only (remove FASTA header)
    lines = fasta.splitlines()
    seq = "".join([ln.strip() for ln in lines[1:] if ln.strip()])

    p.fasta_sequence = seq
    p.save(update_fields=["fasta_sequence"])

    return redirect(
        "protein_detail",
        pesticidedb_protein_id=pesticidedb_protein_id
    )


def protein_fasta_download(request, pesticidedb_protein_id):
    p = get_object_or_404(
        ProteinRecord,
        Q(pesticidedb_protein_id=pesticidedb_protein_id) |
        Q(pbdb_protein_id=pesticidedb_protein_id)
    )

    display_id = p.pesticidedb_protein_id or p.pbdb_protein_id or pesticidedb_protein_id

    seq = (getattr(p, "fasta_sequence", "") or "").strip()
    fasta_text = f">{display_id}\n{seq}\n" if seq else f">{display_id}\n\n"

    response = HttpResponse(fasta_text, content_type="text/plain")
    response["Content-Disposition"] = f'attachment; filename="{display_id}.fasta"'
    return response


def submit_your_data(request):
    if request.method == 'POST':
        form = DataSubmissionForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('submit_your_data')
    else:
        form = DataSubmissionForm()

    recent_submissions = DataSubmission.objects.all().order_by('-submitted_at')[:10]

    return render(request, 'base/submit_your_data.html', {
        'form': form,
        'recent_submissions': recent_submissions,
    })


def statistics(request):
    counts = pesticide_counts()
    summary = database_summary()

    total_proteins = ProteinRecord.objects.count()

    publications_by_year = (
        Pesticide.objects
        .exclude(publication_year__isnull=True)
        .values('publication_year')
        .annotate(count=Count('id'))
        .order_by('-publication_year')
    )

    return render(request, "base/statistics.html", {
        "total_pesticides": counts["total"],
        "pesticides_with_evidence": counts["with_evidence"],
        "pesticides_no_evidence": counts["no_evidence"],
        "pesticide_count": counts["total"],
        "total_microorganisms": microorganism_count(),
        "microorganism_record_count": microorganism_record_count(),
        "total_proteins": total_proteins,
        **summary,
        "publications_by_year": publications_by_year,
    })


def evidence_galaxy(request):
    pesticide_names = canonical_pesticide_names()
    selected_pesticide = request.GET.get("pesticide", "").strip()
    if not selected_pesticide and pesticide_names:
        selected_pesticide = pesticide_names[0]

    context = {
        "pesticide_names": pesticide_names,
        "selected_pesticide": selected_pesticide,
    }
    return render(request, "base/tools/evidence_galaxy.html", context)


def evidence_galaxy_pesticides(request):
    pesticides = {}

    evidence_rows = (
        Pesticide.objects
        .exclude(pesticide__isnull=True)
        .exclude(pesticide="")
        .values("pesticide")
        .annotate(
            evidence_records=Count("id"),
            microorganisms=Count("microorganism", distinct=True),
            references=Count("doi", distinct=True),
        )
    )
    for row in evidence_rows:
        name = clean_pesticide_name(row["pesticide"])
        if not name:
            continue
        key = name.casefold()
        existing = pesticides.get(key)
        if existing:
            existing["evidence_records"] += row["evidence_records"]
            existing["microorganisms"] += row["microorganisms"]
            existing["references"] += row["references"]
            existing["has_evidence"] = True
        else:
            pesticides[key] = {
                "label": name,
                "has_evidence": True,
                "evidence_records": row["evidence_records"],
                "microorganisms": row["microorganisms"],
                "references": row["references"],
            }

    no_evidence_rows = (
        NoEvidencePesticide.objects
        .exclude(pesticide__isnull=True)
        .exclude(pesticide="")
        .values_list("pesticide", flat=True)
    )
    for value in no_evidence_rows:
        name = clean_pesticide_name(value)
        if not name:
            continue
        key = name.casefold()
        pesticides.setdefault(key, {
            "label": name,
            "has_evidence": False,
            "evidence_records": 0,
            "microorganisms": 0,
            "references": 0,
        })

    items = sorted(pesticides.values(), key=lambda item: item["label"].casefold())
    summary = {
        "total": len(items),
        "with_evidence": sum(1 for item in items if item["has_evidence"]),
        "without_evidence": sum(1 for item in items if not item["has_evidence"]),
    }
    return JsonResponse({"pesticides": items, "summary": summary})


def evidence_galaxy_data(request):
    pesticide = request.GET.get("pesticide", "").strip()
    if not pesticide:
        return JsonResponse({"nodes": [], "links": [], "summary": {"message": "Select a pesticide."}})

    records = list(
        Pesticide.objects.filter(pesticide__iexact=pesticide)
        .order_by("publication_year", "microorganism", "id")
    )
    proteins = list(
        ProteinRecord.objects.filter(pesticide__iexact=pesticide)
        .order_by("year", "microorganism", "gene_name", "id")
    )
    pathways = list(
        DegradationPathway.objects.filter(pesticide__iexact=pesticide)
        .prefetch_related("steps")
        .order_by("title", "id")
    )

    nodes = {}
    links = {}

    def clean_node(value):
        return re.sub(r"\s+", " ", str(value or "")).strip()

    def node_id(kind, label):
        key = re.sub(r"[^a-z0-9]+", "-", clean_node(label).casefold()).strip("-") or "unknown"
        return f"{kind}-{key}"

    def add_node(kind, label, layer, color, size=6, detail=None, url=""):
        label = clean_node(label)
        if not label:
            return ""
        identifier = node_id(kind, label)
        existing = nodes.get(identifier)
        if existing:
            existing["size"] = max(existing["size"], size)
            existing["record_count"] = existing.get("record_count", 1) + 1
            return identifier
        nodes[identifier] = {
            "id": identifier,
            "label": label,
            "kind": kind,
            "layer": layer,
            "color": color,
            "size": size,
            "detail": detail or label,
            "url": url,
            "record_count": 1,
        }
        return identifier

    def add_link(source, target, label, color="#8ea4c8"):
        if not source or not target or source == target:
            return
        key = (source, target, label)
        if key in links:
            links[key]["weight"] += 1
            return
        links[key] = {
            "source": source,
            "target": target,
            "label": label,
            "color": color,
            "weight": 1,
        }

    pesticide_id = add_node(
        "pesticide",
        pesticide,
        "pesticide",
        "#f7c948",
        14,
        f"{pesticide}: selected pesticide evidence cluster",
    )

    for record in records:
        doi = clean_node(record.doi) or clean_node(record.reference)
        reference_label = doi or f"Reference {record.id}"
        reference_id = add_node(
            "reference",
            reference_label,
            "reference",
            "#60a5fa",
            7,
            f"{record.publication_year or 'Year not recorded'} | {record.reference or doi}",
            f"https://doi.org/{doi}" if doi.startswith("10.") else "",
        )
        microbe_id = add_node(
            "microorganism",
            record.microorganism,
            "microorganism",
            "#34d399",
            8,
            f"{record.microorganism or 'Microorganism not recorded'} | {record.culture_type or 'Individual strain'}",
        )
        add_link(pesticide_id, reference_id, "reported in", "#93c5fd")
        add_link(reference_id, microbe_id, "reports", "#86efac")
        add_link(microbe_id, pesticide_id, "degrades", "#facc15")

        for gene in _split_galaxy_terms(record.gene):
            gene_id = add_node("gene", gene, "gene/protein", "#c084fc", 5, f"Gene linked to {record.microorganism}")
            add_link(microbe_id, gene_id, "has gene", "#d8b4fe")
            add_link(gene_id, pesticide_id, "linked to", "#e9d5ff")

        enzyme_terms = _split_galaxy_terms(record.enzyme_name_reported) or _split_galaxy_terms(record.enzyme)
        for enzyme in enzyme_terms:
            enzyme_id = add_node("enzyme", enzyme, "gene/protein", "#f472b6", 5, f"Protein/enzyme reported for {record.microorganism}")
            add_link(microbe_id, enzyme_id, "enzyme", "#f9a8d4")
            add_link(enzyme_id, pesticide_id, "acts on", "#fbcfe8")

        for product in _split_galaxy_terms(record.metabolite_or_product):
            product_id = add_node("metabolite", product, "pathway", "#fb923c", 5, f"Metabolite/product reported for {pesticide}")
            add_link(pesticide_id, product_id, "forms", "#fdba74")
            add_link(reference_id, product_id, "supports", "#fed7aa")

    for protein in proteins:
        microbe_id = add_node(
            "microorganism",
            protein.microorganism,
            "microorganism",
            "#34d399",
            8,
            f"{protein.microorganism or 'Microorganism not recorded'}",
        )
        protein_label = protein.reported_protein_name or protein.pesticidedb_protein_id or protein.gene_name
        protein_id = add_node(
            "protein",
            protein_label,
            "gene/protein",
            "#f472b6",
            6,
            f"{protein.pesticidedb_protein_id or ''} | {protein.gene_name or ''} | {protein.doi or ''}",
            request_path("protein_detail", protein.pesticidedb_protein_id) if protein.pesticidedb_protein_id else "",
        )
        add_link(microbe_id, protein_id, "protein", "#f9a8d4")
        add_link(protein_id, pesticide_id, "evidence", "#fbcfe8")
        if protein.doi:
            reference_id = add_node(
                "reference",
                protein.doi,
                "reference",
                "#60a5fa",
                7,
                f"Protein record reference | {protein.year or 'Year not recorded'}",
                f"https://doi.org/{protein.doi}" if protein.doi.startswith("10.") else "",
            )
            add_link(reference_id, protein_id, "reports", "#bfdbfe")

        for gene in _split_galaxy_terms(protein.gene_name):
            gene_id = add_node("gene", gene, "gene/protein", "#c084fc", 5, f"Gene for {protein_label}")
            add_link(gene_id, protein_id, "encodes", "#d8b4fe")

    for pathway in pathways:
        pathway_id = add_node(
            "pathway",
            pathway.title,
            "pathway",
            "#fb923c",
            8,
            f"{pathway.completeness} | {pathway.summary or pathway.reference}",
        )
        add_link(pesticide_id, pathway_id, "pathway", "#fdba74")
        if pathway.doi:
            reference_id = add_node(
                "reference",
                pathway.doi,
                "reference",
                "#60a5fa",
                7,
                f"Pathway reference | {pathway.reference}",
                f"https://doi.org/{pathway.doi}" if pathway.doi.startswith("10.") else "",
            )
            add_link(reference_id, pathway_id, "supports", "#bfdbfe")
        if pathway.microorganism:
            microbe_id = add_node("microorganism", pathway.microorganism, "microorganism", "#34d399", 8)
            add_link(microbe_id, pathway_id, "pathway", "#86efac")
        for step in pathway.steps.all():
            for product in _split_galaxy_terms(step.product):
                product_id = add_node("metabolite", product, "pathway", "#fb923c", 5, f"Step {step.step_order}: {step.substrate} to {step.product}")
                add_link(pathway_id, product_id, "step", "#fdba74")
            for gene in _split_galaxy_terms(step.gene):
                gene_id = add_node("gene", gene, "gene/protein", "#c084fc", 5, f"Pathway step gene | {step.evidence_type}")
                add_link(gene_id, pathway_id, "step gene", "#d8b4fe")
            for enzyme in _split_galaxy_terms(step.enzyme):
                enzyme_id = add_node("enzyme", enzyme, "gene/protein", "#f472b6", 5, f"Pathway step enzyme | {step.evidence_type}")
                add_link(enzyme_id, pathway_id, "step enzyme", "#f9a8d4")

    summary = {
        "pesticide": pesticide,
        "evidence_records": len(records),
        "references": len([node for node in nodes.values() if node["kind"] == "reference"]),
        "microorganisms": len([node for node in nodes.values() if node["kind"] == "microorganism"]),
        "genes": len([node for node in nodes.values() if node["kind"] == "gene"]),
        "proteins_or_enzymes": len([node for node in nodes.values() if node["kind"] in {"protein", "enzyme"}]),
        "pathway_nodes": len([node for node in nodes.values() if node["kind"] in {"pathway", "metabolite"}]),
    }
    return JsonResponse({"nodes": list(nodes.values()), "links": list(links.values()), "summary": summary})


def _split_galaxy_terms(value):
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text or text in {"-", "Not linked", "Not specified", "None", "nan"}:
        return []
    protected_commas = []

    def protect_chemical_comma(match):
        protected_commas.append(match.group(0))
        return f"__CHEMICAL_COMMA_{len(protected_commas) - 1}__"

    # Keep numeric chemical locants intact, e.g. 2,4-D and 2,4-dichlorophenol.
    text = re.sub(r"\b\d+,\d+(?=[A-Za-z-])", protect_chemical_comma, text)
    parts = re.split(r"\s*(?:;|,|\||/|\band\b)\s*", text)
    cleaned = []
    seen = set()
    for part in parts:
        item = part.strip()
        for index, original in enumerate(protected_commas):
            item = item.replace(f"__CHEMICAL_COMMA_{index}__", original)
        if not item or item in {"-", "Not linked", "Not specified"}:
            continue
        key = item.casefold()
        if key not in seen:
            cleaned.append(item[:90])
            seen.add(key)
    return cleaned[:8]


def classification(request):
    return render(request, 'base/tools/classification.html')


# ================= ANNOTATE GENE JOB SYSTEM =================

def _safe_int(value, default, minimum=0, maximum=100):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default

    return min(max(parsed, minimum), maximum)


def _new_job_id(prefix, model):
    job_id = f"{prefix}{random.randint(1000000, 9999999)}"
    while model.objects.filter(job_id=job_id).exists():
        job_id = f"{prefix}{random.randint(1000000, 9999999)}"
    return job_id


def _run_command(command, cwd=None):
    try:
        return subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    except FileNotFoundError as exc:
        missing = command[0]
        raise RuntimeError(
            f"Required command '{missing}' was not found. Install {missing} and make sure it is available on PATH."
        ) from exc


def _run_diamond_search(command, result_path):
    if result_path.exists():
        result_path.unlink()

    run = _run_command(command)
    has_hits = result_path.exists() and result_path.stat().st_size > 0
    return run, has_hits


def _diamond_no_hit_message(
    diamond_mode,
    diamond_db,
    query_path,
    output_dir,
    identity_threshold,
    evalue_threshold,
    coverage_threshold,
):
    diagnostic_path = output_dir / "diamond_permissive_diagnostic.tsv"
    diagnostic = _run_command([
        "diamond", diamond_mode,
        "-d", str(diamond_db),
        "-q", str(query_path),
        "-o", str(diagnostic_path),
        "--outfmt", "6",
        "qseqid", "sseqid", "pident", "length", "evalue", "bitscore",
        "qcovhsp", "scovhsp", "ppos",
        "--evalue", "10",
        "--id", "0",
        "--query-cover", "0",
        "--max-target-seqs", "1",
        "--very-sensitive",
        "--threads", "4",
    ])
    if diagnostic.returncode == 0 and diagnostic_path.exists():
        first_line = next(
            (line for line in diagnostic_path.read_text(errors="ignore").splitlines() if line),
            "",
        )
        fields = first_line.split("\t")
        if len(fields) >= 8:
            return (
                "A weak similarity was detected, but it did not satisfy the selected "
                f"thresholds: identity >= {identity_threshold}%, E-value <= "
                f"{evalue_threshold}, and query coverage >= {coverage_threshold}%. "
                f"The strongest permissive match was {fields[1]} with {fields[2]}% "
                f"identity, E-value {fields[4]}, query coverage {fields[6]}%, and "
                f"subject coverage {fields[7]}%. Lower the thresholds only for "
                "exploratory analysis and review the match manually."
            )

    return (
        "No detectable similarity to the validated PesticideDB reference proteins was "
        "found, even with a permissive diagnostic search. Confirm that the FASTA "
        "contains the expected sequence type and that the reference protein has an "
        "available sequence in the validated annotation database."
    )


def _master_metadata_path(pipeline_dir):
    master_with_ids = pipeline_dir / "data" / "PBDB_master_with_ids.xlsx"
    if master_with_ids.exists():
        return master_with_ids
    return pipeline_dir / "data" / "PBDB_master.xlsx"


def _annotation_pipeline_worker(job_id, uploaded_query, options):
    """Background worker for Annotate Gene."""
    pipeline_dir = settings.PBDB_ANNOTATION_DIR
    job_output_dir = settings.MEDIA_ROOT / "annotation_jobs" / job_id
    job_output_dir.mkdir(parents=True, exist_ok=True)

    predicted_proteins = job_output_dir / f"{job_id}_predicted_proteins.faa"
    diamond_result = job_output_dir / "diamond_results.tsv"
    hmmer_result = job_output_dir / "hmmer_results.tbl"
    hmmer_domains = job_output_dir / "hmmer_domains.tbl"
    downloadable_result = job_output_dir / f"{job_id}_annotation_results.csv"
    all_matches_result = job_output_dir / f"{job_id}_all_validated_matches.csv"

    diamond_db = pipeline_dir / "diamond_db" / "pbdb_validated"
    hmmer_db = pipeline_dir / "hmmer_db" / "pbdb_validated_profiles.hmm"
    master_metadata = _master_metadata_path(pipeline_dir)
    reference_fasta = pipeline_dir / "data" / "pbdb_validated_reference_proteins.faa"
    search_type = options.get("search_type", "diamond_hmmer")
    evalue = f"1e-{options.get('evalue_exp', 3)}"
    pident = str(options.get("pident", 25))
    query_coverage = str(options.get("query_coverage", 30))

    try:
        job = AnnotationJob.objects.get(job_id=job_id)
        job.status = "running"
        job.message = "Annotation job is running."
        job.save(update_fields=["status", "message"])

        sequence_type = detect_fasta_sequence_type(uploaded_query)
        if sequence_type == "empty":
            job.status = "failed"
            job.message = "Uploaded FASTA file has no sequence data."
            job.save(update_fields=["status", "message"])
            return

        diamond_mode = "blastp"
        query_for_tools = uploaded_query
        query_for_hmmer = uploaded_query
        if sequence_type == "dna":
            diamond_mode = "blastx"
            query_for_hmmer = None

        diamond_run = _run_command([
            "diamond", diamond_mode,
            "-d", str(diamond_db),
            "-q", query_for_tools,
            "-o", str(diamond_result),
            "--outfmt", "6",
            "qseqid", "sseqid", "pident", "length", "evalue", "bitscore",
            "qcovhsp", "scovhsp", "ppos",
            "--evalue", "10",
            "--id", "0",
            "--query-cover", "0",
            "--max-target-seqs", "500",
            "--very-sensitive",
            "--threads", "4"
        ])

        if diamond_run.returncode != 0:
            job.status = "failed"
            job.message = diamond_run.stderr or "DIAMOND failed."
            job.save(update_fields=["status", "message"])
            return

        if (not diamond_result.exists()) or diamond_result.stat().st_size == 0:
            job.status = "no_hit"
            job.message = _diamond_no_hit_message(
                diamond_mode,
                diamond_db,
                query_for_tools,
                job_output_dir,
                pident,
                evalue,
                query_coverage,
            )
            job.save(update_fields=["status", "message"])
            return

        hmmer_path = None
        if search_type == "diamond_hmmer" and query_for_hmmer:
            hmmer_run = _run_command([
                "hmmscan",
                "--tblout", str(hmmer_result),
                "--domtblout", str(hmmer_domains),
                str(hmmer_db),
                query_for_hmmer
            ])

            if hmmer_run.returncode != 0:
                job.status = "failed"
                job.message = hmmer_run.stderr or "HMMER failed."
                job.save(update_fields=["status", "message"])
                return

            hmmer_path = hmmer_result

        result_count = annotate_diamond_hits(
            diamond_result,
            all_matches_result,
            hmmer_tbl_path=hmmer_path,
            master_metadata_path=master_metadata,
            reference_fasta_path=reference_fasta,
            query_fasta_path=query_for_hmmer or query_for_tools,
            review_identity=float(pident),
            review_evalue=float(evalue),
            review_query_coverage=float(query_coverage),
        )
        if result_count == 0:
            job.status = "no_hit"
            job.message = "Your job completed successfully, however your sequences did not match any proteins in the database."
            job.save(update_fields=["status", "message"])
            return

        write_best_match_results(all_matches_result, downloadable_result)

        job.status = "done"
        job.message = "Your job completed successfully."
        job.result_file = str(downloadable_result)
        job.save(update_fields=["status", "message", "result_file"])

    except Exception as e:
        try:
            job = AnnotationJob.objects.get(job_id=job_id)
            job.status = "failed"
            job.message = str(e)
            job.save(update_fields=["status", "message"])
        except Exception:
            pass


def annotategene(request):
    """
    Upload page for Annotate Gene.
    Creates a job and redirects to running/status page.
    """
    if request.method == "POST":
        fasta_file = request.FILES.get("fasta_file")
        if not fasta_file:
            return render(request, "base/tools/annotategene.html", {
                "error": "Please upload a FASTA file."
            })

        job_id = _new_job_id("MS", AnnotationJob)
        job_output_dir = settings.MEDIA_ROOT / "annotation_jobs" / job_id
        job_output_dir.mkdir(parents=True, exist_ok=True)

        uploaded_query = job_output_dir / f"{job_id}_query.fasta"
        with open(uploaded_query, "wb+") as destination:
            for chunk in fasta_file.chunks():
                destination.write(chunk)

        AnnotationJob.objects.create(
            job_id=job_id,
            status="running",
            message="Annotation job is running."
        )

        options = {
            "search_type": request.POST.get("search_type", "diamond_hmmer"),
            "evalue_exp": _safe_int(request.POST.get("evalue"), 3, 0, 100),
            "pident": _safe_int(request.POST.get("pident"), 25, 0, 100),
            "query_coverage": _safe_int(
                request.POST.get("query_coverage"), 30, 0, 100
            ),
        }

        thread = threading.Thread(
            target=_annotation_pipeline_worker,
            args=(job_id, str(uploaded_query), options),
            daemon=True
        )
        thread.start()

        return redirect("annotategene_status", job_id=job_id)

    return render(request, "base/tools/annotategene.html")

def annotategene_status(request, job_id):
    job = get_object_or_404(AnnotationJob, job_id=job_id)

    if job.status == "running":
        return render(request, "base/tools/annotategene_running.html", {
            "job": job,
        })

    if job.status == "failed":
        return render(request, "base/tools/annotategene_result.html", {
            "job": job,
            "error": job.message,
            "results": [],
            "nohit": False,
        })

    if job.status in {"no_hit", "No Hit"}:
        return render(request, "base/tools/annotategene_result.html", {
            "job": job,
            "results": [],
            "nohit": True,
            "message": job.message,
        })

    results = []
    pesticide_hits = []
    hmmer_hits = []
    all_matches_available = (
        settings.MEDIA_ROOT
        / "annotation_jobs"
        / job_id
        / f"{job_id}_all_validated_matches.csv"
    ).exists()

    if job.status == "done" and job.result_file and os.path.exists(job.result_file):
        df = read_annotation_results(job.result_file)
        best_df = df
        results = best_df.to_dict(orient="records")
        _attach_pathway_links(results)

        if "pesticide" in best_df.columns:
            pesticide_hits = (
                best_df.groupby("pesticide")
                .size()
                .reset_index(name="hit_count")
                .to_dict(orient="records")
            )

        if "hmmer_family" in best_df.columns:
            hmmer_hits = (
                best_df.groupby("hmmer_family")
                .size()
                .reset_index(name="hit_count")
                .to_dict(orient="records")
            )

    return render(request, "base/tools/annotategene_result.html", {
        "job": job,
        "results": results,
        "pesticide_hits": pesticide_hits,
        "hmmer_hits": hmmer_hits,
        "all_matches_available": all_matches_available,
        "nohit": False,
    })


def annotategene_download(request, job_id):
    """
    Download final annotation CSV from the web interface.
    """
    job = get_object_or_404(AnnotationJob, job_id=job_id)

    if not job.result_file or not os.path.exists(job.result_file):
        raise Http404("Result file not found.")

    return FileResponse(
        open(job.result_file, "rb"),
        as_attachment=True,
        filename=f"{job_id}_annotation_results.csv"
    )


def annotategene_all_matches_download(request, job_id):
    job = get_object_or_404(AnnotationJob, job_id=job_id)
    all_matches_path = (
        settings.MEDIA_ROOT
        / "annotation_jobs"
        / job_id
        / f"{job_id}_all_validated_matches.csv"
    )
    if not all_matches_path.exists():
        raise Http404("All-matches result file not found.")
    return FileResponse(
        open(all_matches_path, "rb"),
        as_attachment=True,
        filename=all_matches_path.name,
    )

# ================= ANNOTATE GENOME JOB SYSTEM =================
def _genome_annotation_pipeline_worker(job_id, uploaded_query, options):
    pipeline_dir = settings.PBDB_ANNOTATION_DIR
    job_output_dir = settings.MEDIA_ROOT / "genome_jobs" / job_id
    job_output_dir.mkdir(parents=True, exist_ok=True)

    predicted_proteins = job_output_dir / f"{job_id}_predicted_proteins.faa"
    diamond_result = job_output_dir / "genome_diamond_results.tsv"
    hmmer_result = job_output_dir / "genome_hmmer_results.tbl"
    hmmer_domains = job_output_dir / "genome_hmmer_domains.tbl"
    downloadable_result = job_output_dir / f"{job_id}_genome_annotation_results.csv"
    all_matches_result = job_output_dir / f"{job_id}_all_validated_matches.csv"

    diamond_db = pipeline_dir / "diamond_db" / "pbdb_validated"
    hmmer_db = pipeline_dir / "hmmer_db" / "pbdb_validated_profiles.hmm"
    master_metadata = _master_metadata_path(pipeline_dir)
    reference_fasta = pipeline_dir / "data" / "pbdb_validated_reference_proteins.faa"
    blast_type = options.get("blast_type", "auto")
    search_type = options.get("search_type", "diamond_hmmer")
    evalue = f"1e-{options.get('evalue_exp', 3)}"
    pident = str(options.get("pident", 25))
    query_coverage = str(options.get("query_coverage", 30))

    try:
        job = GenomeAnnotationJob.objects.get(job_id=job_id)
        job.status = "running"
        job.message = "Genome annotation is running."
        job.save(update_fields=["status", "message"])

        sequence_type = detect_fasta_sequence_type(uploaded_query)
        if sequence_type == "empty":
            job.status = "failed"
            job.message = "Uploaded FASTA file has no sequence data."
            job.save(update_fields=["status", "message"])
            return

        diamond_mode = "blastp"
        query_for_diamond = uploaded_query
        query_for_hmmer = uploaded_query
        used_blastx_fallback = False

        if sequence_type == "dna" and blast_type == "blastx":
            diamond_mode = "blastx"
            query_for_hmmer = None
        elif sequence_type == "dna":
            prodigal_run = _run_command([
                "prodigal",
                "-i", uploaded_query,
                "-a", str(predicted_proteins),
                "-p", "meta",
                "-q"
            ])

            if prodigal_run.returncode != 0:
                if blast_type == "auto":
                    diamond_mode = "blastx"
                    query_for_diamond = uploaded_query
                    query_for_hmmer = None
                    used_blastx_fallback = True
                else:
                    job.status = "failed"
                    job.message = prodigal_run.stderr or "Prodigal failed."
                    job.save(update_fields=["status", "message"])
                    return
            elif not predicted_proteins.exists() or predicted_proteins.stat().st_size == 0:
                if blast_type == "auto":
                    diamond_mode = "blastx"
                    query_for_diamond = uploaded_query
                    query_for_hmmer = None
                    used_blastx_fallback = True
                else:
                    job.status = "no_hit"
                    job.message = "Prodigal did not predict any proteins from the uploaded nucleotide FASTA."
                    job.save(update_fields=["status", "message"])
                    return
            else:
                query_for_diamond = str(predicted_proteins)
                query_for_hmmer = str(predicted_proteins)
        elif blast_type == "blastx":
            job.status = "failed"
            job.message = "BLASTX requires nucleotide FASTA input. Use BLASTP for protein FASTA."
            job.save(update_fields=["status", "message"])
            return

        diamond_command = [
            "diamond", diamond_mode,
            "-d", str(diamond_db),
            "-q", query_for_diamond,
            "-o", str(diamond_result),
            "--outfmt", "6",
            "qseqid", "sseqid", "pident", "length", "evalue", "bitscore",
            "qcovhsp", "scovhsp", "ppos",
            "--evalue", "10",
            "--id", "0",
            "--query-cover", "0",
            "--max-target-seqs", "500",
            "--very-sensitive",
            "--threads", "6"
        ]
        diamond_run, diamond_has_hits = _run_diamond_search(diamond_command, diamond_result)

        if diamond_run.returncode != 0:
            job.status = "failed"
            job.message = diamond_run.stderr or "DIAMOND failed."
            job.save(update_fields=["status", "message"])
            return

        if (
            not diamond_has_hits
            and sequence_type == "dna"
            and blast_type == "auto"
            and not used_blastx_fallback
        ):
            diamond_mode = "blastx"
            query_for_diamond = uploaded_query
            query_for_hmmer = None
            used_blastx_fallback = True
            diamond_command = [
                "diamond", "blastx",
                "-d", str(diamond_db),
                "-q", query_for_diamond,
                "-o", str(diamond_result),
                "--outfmt", "6",
                "qseqid", "sseqid", "pident", "length", "evalue", "bitscore",
                "qcovhsp", "scovhsp", "ppos",
                "--evalue", "10",
                "--id", "0",
                "--query-cover", "0",
                "--max-target-seqs", "500",
                "--very-sensitive",
                "--threads", "6"
            ]
            diamond_run, diamond_has_hits = _run_diamond_search(diamond_command, diamond_result)

            if diamond_run.returncode != 0:
                job.status = "failed"
                job.message = diamond_run.stderr or "DIAMOND BLASTX fallback failed."
                job.save(update_fields=["status", "message"])
                return

        if not diamond_has_hits:
            job.status = "no_hit"
            job.message = _diamond_no_hit_message(
                diamond_mode,
                diamond_db,
                query_for_diamond,
                job_output_dir,
                pident,
                evalue,
                query_coverage,
            )
            job.save(update_fields=["status", "message"])
            return

        hmmer_path = None
        if search_type == "diamond_hmmer" and query_for_hmmer:
            hmmer_run = _run_command([
                "hmmscan",
                "--tblout", str(hmmer_result),
                "--domtblout", str(hmmer_domains),
                str(hmmer_db),
                query_for_hmmer,
            ])

            if hmmer_run.returncode != 0:
                job.status = "failed"
                job.message = hmmer_run.stderr or "HMMER failed."
                job.save(update_fields=["status", "message"])
                return

            hmmer_path = hmmer_result

        result_count = annotate_diamond_hits(
            diamond_result,
            all_matches_result,
            hmmer_tbl_path=hmmer_path,
            master_metadata_path=master_metadata,
            reference_fasta_path=reference_fasta,
            query_fasta_path=query_for_hmmer or query_for_diamond,
            review_identity=float(pident),
            review_evalue=float(evalue),
            review_query_coverage=float(query_coverage),
        )
        if result_count == 0:
            job.status = "no_hit"
            fallback_note = " after BLASTX fallback" if used_blastx_fallback else ""
            job.message = (
                f"DIAMOND found alignments{fallback_note}, but none could be mapped to PesticideDB metadata. "
                "Check that the PesticideDB master metadata and reference FASTA match the DIAMOND database."
            )
            job.save(update_fields=["status", "message"])
            return

        write_best_match_results(all_matches_result, downloadable_result)

        job.status = "done"
        job.message = "Genome annotation completed successfully."
        job.result_file = str(downloadable_result)
        job.save(update_fields=["status", "message", "result_file"])

    except Exception as e:
        job = GenomeAnnotationJob.objects.get(job_id=job_id)
        job.status = "failed"
        job.message = str(e)
        job.save(update_fields=["status", "message"])

def annotategenome(request):
    if request.method == "POST":
        fasta_file = request.FILES.get("fasta_file")
        if not fasta_file:
            return render(request, "base/tools/annotategenome.html", {
                "error": "Please upload a FASTA file."
            })

        job_id = _new_job_id("SM", GenomeAnnotationJob)

        GenomeAnnotationJob.objects.create(
            job_id=job_id,
            status="running",
            message="Genome annotation job is running."
        )
        
        job_dir = settings.MEDIA_ROOT / "genome_jobs" / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        uploaded_query = job_dir / f"{job_id}_query.fasta"

        with open(uploaded_query, "wb+") as f:
            for chunk in fasta_file.chunks():
                f.write(chunk)

        options = {
            "blast_type": request.POST.get("blast_type", "auto"),
            "search_type": request.POST.get("search_type", "diamond_hmmer"),
            "evalue_exp": _safe_int(request.POST.get("evalue"), 5, 0, 100),
            "pident": _safe_int(request.POST.get("pident"), 35, 0, 100),
            "query_coverage": _safe_int(
                request.POST.get("query_coverage"), 30, 0, 100
            ),
        }

        thread = threading.Thread(
            target=_genome_annotation_pipeline_worker,
            args=(job_id, str(uploaded_query), options),
            daemon=True
        )
        thread.start()

        return redirect("annotategenome_running", job_id=job_id)

    return render(request, "base/tools/annotategenome.html")


def annotategenome_running(request, job_id):
    job = get_object_or_404(GenomeAnnotationJob, job_id=job_id)

    if job.status in {"done", "failed", "no_hit", "No Hit"}:
        return redirect("annotategenome_result", job_id=job_id)

    return render(request, "base/tools/annotategenome_running.html", {
        "job": job
    })


def annotategenome_result(request, job_id):
    job = get_object_or_404(GenomeAnnotationJob, job_id=job_id)

    results = []
    pesticide_hits = []
    hmmer_hits = []
    all_matches_available = (
        settings.MEDIA_ROOT
        / "genome_jobs"
        / job_id
        / f"{job_id}_all_validated_matches.csv"
    ).exists()

    if job.status == "failed":
        return render(request, "base/tools/annotategenome_result.html", {
            "job": job,
            "error": job.message,
            "results": [],
            "nohit": False,
        })

    if job.status in {"no_hit", "No Hit"}:
        return render(request, "base/tools/annotategenome_result.html", {
            "job": job,
            "results": [],
            "nohit": True,
            "message": job.message,
        })

    if job.result_file and os.path.exists(job.result_file):
        df = read_annotation_results(job.result_file)
        best_df = df
        results = best_df.to_dict(orient="records")
        _attach_pathway_links(results)

        if "pesticide" in best_df.columns:
            pesticide_hits = (
                best_df.groupby("pesticide")
                .size()
                .reset_index(name="hit_count")
                .to_dict(orient="records")
            )

        if "hmmer_family" in best_df.columns:
            hmmer_hits = (
                best_df.groupby("hmmer_family")
                .size()
                .reset_index(name="hit_count")
                .to_dict(orient="records")
            )

    return render(request, "base/tools/annotategenome_result.html", {
        "job": job,
        "results": results,
        "pesticide_hits": pesticide_hits,
        "hmmer_hits": hmmer_hits,
        "all_matches_available": all_matches_available,
        "nohit": False,
    })


def annotategenome_download(request, job_id):
    job = get_object_or_404(GenomeAnnotationJob, job_id=job_id)

    if not job.result_file or not os.path.exists(job.result_file):
        raise Http404("Result file not found.")

    return FileResponse(
        open(job.result_file, "rb"),
        as_attachment=True,
        filename=f"{job_id}_genome_annotation_results.csv"
    )


def annotategenome_all_matches_download(request, job_id):
    job = get_object_or_404(GenomeAnnotationJob, job_id=job_id)
    all_matches_path = (
        settings.MEDIA_ROOT
        / "genome_jobs"
        / job_id
        / f"{job_id}_all_validated_matches.csv"
    )
    if not all_matches_path.exists():
        raise Http404("All-matches result file not found.")
    return FileResponse(
        open(all_matches_path, "rb"),
        as_attachment=True,
        filename=all_matches_path.name,
    )

def _concise_pathway_reaction_label(step, detailed=False):
    label = step.gene or ""
    label_lower = label.lower()
    enzyme = (step.enzyme or "").strip()
    enzyme_lower = enzyme.lower()
    gene_is_locus_code = bool(re.search(r"(^|[.\s_-])orf\d*($|[.\s_-])", label_lower))
    enzyme_is_named = bool(enzyme) and not any(
        phrase in enzyme_lower
        for phrase in ("not assigned", "not identified", "activity not assigned", "unassigned")
    )
    if (
        label
        and step.evidence_type == "PURIFIED_ENZYME"
        and gene_is_locus_code
        and enzyme_is_named
    ):
        return enzyme
    if label and not detailed and (
        "inferred" in label_lower
        or "plasmid" in label_lower
        or "not required" in label_lower
        or len(label) > 28
    ):
        label = ""
    if not label and step.protein:
        label = (
            step.protein.gene_name
            or step.protein.pesticidedb_protein_id
            or step.protein.reported_protein_name
            or ""
        )
    if label:
        return label

    if not detailed:
        return ""

    if "; enzyme not genetically assigned" in enzyme_lower:
        clean_enzyme = enzyme.split(";", 1)[0].strip()
        if clean_enzyme and detailed:
            return f"{clean_enzyme} (enzyme not genetically assigned)"
        if clean_enzyme:
            return clean_enzyme
    if "hydrolysis" in enzyme_lower or "hydrolase" in enzyme_lower:
        return "Hydrolysis (enzyme not identified)" if detailed else "Hydrolysis"
    if "transformation" in enzyme_lower:
        return "Transformation (enzyme not identified)" if detailed else "Transformation"
    if "unassigned" in enzyme_lower or not enzyme:
        return "Enzyme not identified"
    return enzyme


def _is_unresolved_pathway_step(step):
    product = (step.product or "").casefold()
    unresolved_phrases = (
        "not resolved in current database source",
        "products/intermediates not identified",
        "microbial transformation products",
        "transformation products not resolved",
        "degradation products not resolved",
    )
    return any(phrase in product for phrase in unresolved_phrases)


def _split_pathway_products(product):
    product = (product or "").strip()
    if " + " not in product:
        return [product] if product else []
    return [
        part.strip()
        for part in product.split(" + ")
        if part.strip()
    ]


def _pathway_confidence_status(pathway_steps, drawable_step_count):
    total_steps = len(pathway_steps)
    unresolved_count = sum(1 for step in pathway_steps if _is_unresolved_pathway_step(step))
    strong_count = sum(
        1
        for step in pathway_steps
        if step.evidence_type in {"PURIFIED_ENZYME", "GENETIC"}
    )
    if not total_steps:
        return {
            "label": "Evidence record only",
            "class": "secondary",
            "detail": "Biodegradation evidence exists, but no curated pathway step is available yet.",
        }
    if drawable_step_count == 0:
        return {
            "label": "Transformation evidence only",
            "class": "warning",
            "detail": "Biodegradation evidence is curated, but products/intermediates are not resolved enough to draw a chemical pathway.",
        }
    if unresolved_count:
        label = "Gene/enzyme-supported partial pathway" if strong_count else "Partial pathway"
        return {
            "label": label,
            "class": "info",
            "detail": f"{drawable_step_count} drawable step(s); {unresolved_count} unresolved evidence record(s) kept in the table.",
        }
    if strong_count:
        return {
            "label": "Gene/enzyme-supported pathway",
            "class": "success",
            "detail": f"{drawable_step_count} drawable step(s), including purified-enzyme or genetic evidence.",
        }
    return {
        "label": "Metabolite-supported pathway",
        "class": "primary",
        "detail": f"{drawable_step_count} drawable metabolite-supported step(s).",
    }


def _pathway_graph_elements(pathways, selected_pesticide):
    elements = []
    added_nodes = set()
    added_edges = set()
    selected_compound = None
    if selected_pesticide:
        selected_compound = Compound.objects.filter(name__iexact=selected_pesticide).first()

    metabolite_code_pattern = re.compile(r"^(?:CGA|SYN|NOA)\s+\d+$", re.IGNORECASE)
    metabolite_mass_pattern = re.compile(
        r"^(Metabolite\s+[A-Za-z0-9-]+)\s*\((m/z\s*[\d.]+)(?:;[^)]*)?\)$",
        re.IGNORECASE,
    )

    def graph_label(label):
        clean_label = (label or "").strip()
        match = metabolite_mass_pattern.match(clean_label)
        if match:
            return f"{match.group(1)} ({match.group(2)})"
        return clean_label

    def pathway_node_label(label):
        clean_label = graph_label(label)
        if metabolite_code_pattern.match(clean_label):
            return f"{clean_label}\n(metabolite code)"
        return clean_label

    def add_node(node_id, label, node_type, url="", extra=None):
        if node_id in added_nodes:
            return
        data = {
            "id": node_id,
            "label": pathway_node_label(label),
            "compound_name": label,
            "node_type": node_type,
            "url": url,
        }
        if extra:
            data.update(extra)
        elements.append({"data": data})
        added_nodes.add(node_id)

    def compound_node_id(compound, fallback_label):
        normalized_label = graph_label(fallback_label)
        if normalized_label and metabolite_mass_pattern.match((fallback_label or "").strip()):
            normalized = re.sub(r"[^a-z0-9]+", "-", normalized_label.casefold()).strip("-")
            return f"compound-label-{normalized or 'unknown'}"
        if compound:
            return f"compound-{compound.id}"
        normalized = re.sub(r"[^a-z0-9]+", "-", fallback_label.casefold()).strip("-")
        return f"compound-label-{normalized or 'unknown'}"

    compound_lookup = {}

    def compound_for_label(label):
        clean_label = clean_pesticide_name(label)
        if not clean_label:
            return None
        key = clean_label.casefold()
        if key not in compound_lookup:
            compound_lookup[key] = Compound.objects.filter(name__iexact=clean_label).first()
        return compound_lookup[key]

    def compound_extra(compound):
        if not compound:
            return {}
        return {
            "compound_id": compound.id,
            "smiles": compound.smiles,
            "pubchem_cid": compound.pubchem_cid,
            "structure_url": compound.pubchem_structure_image_url,
            "chemical_status": (
                "structure available"
                if compound.pubchem_structure_image_url
                else "SMILES available"
                if compound.smiles
                else "no single structure assigned"
            ),
        }

    pathway_list = list(pathways)
    selected_pesticide_label = (selected_pesticide or "").strip()
    selected_pesticide_key = selected_pesticide_label.casefold()

    for pathway in pathway_list:
        steps = list(pathway.steps.all())
        if not steps:
            continue

        for step in steps:
            if _is_unresolved_pathway_step(step):
                continue
            substrate_label = step.substrate
            substrate_compound = step.substrate_compound
            substrate_key = (substrate_label or "").strip().casefold()
            if (
                selected_pesticide_key
                and substrate_key.startswith(f"{selected_pesticide_key}/")
                and "route" in substrate_key
            ):
                substrate_label = selected_pesticide_label
                substrate_compound = selected_compound
            substrate_id = compound_node_id(substrate_compound, substrate_label)
            add_node(
                substrate_id,
                substrate_label,
                "compound",
                substrate_compound and request_path("compound_detail", substrate_compound.id),
                compound_extra(substrate_compound),
            )
            for product_index, product_label in enumerate(_split_pathway_products(step.product)):
                product_compound = (
                    step.product_compound
                    if product_label == step.product
                    else compound_for_label(product_label)
                )
                product_id = compound_node_id(product_compound, product_label)
                add_node(
                    product_id,
                    product_label,
                    "compound",
                    product_compound and request_path("compound_detail", product_compound.id),
                    compound_extra(product_compound),
                )
                edge_label = _concise_pathway_reaction_label(step)
                edge_key = (
                    substrate_id,
                    product_id,
                    edge_label.casefold(),
                    step.evidence_type,
                )
                if edge_key in added_edges:
                    continue
                added_edges.add(edge_key)
                elements.append({
                    "data": {
                        "id": f"step-{step.id}-{product_index}",
                        "source": substrate_id,
                        "target": product_id,
                        "label": edge_label,
                        "reaction": _concise_pathway_reaction_label(step, detailed=True),
                        "organism": step.microorganism or pathway.microorganism,
                        "pathway_title": pathway.title,
                        "evidence_type": step.evidence_type,
                        "url": request_path("pathway_step_detail", step.id),
                    }
                })

    return elements


def _pathway_display_substrate(step, selected_pesticide):
    substrate = (step.substrate or "").strip()
    selected = (selected_pesticide or "").strip()
    substrate_key = substrate.casefold()
    selected_key = selected.casefold()
    if selected_key and substrate_key.startswith(f"{selected_key}/") and "route" in substrate_key:
        return selected
    return substrate


PATHWAY_DOI_RE = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", re.IGNORECASE)


def _pathway_reference_context(*values):
    fallback = ""
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        if not fallback:
            fallback = text
        match = PATHWAY_DOI_RE.search(text)
        if match:
            doi = match.group(1).rstrip(".,;")
            return {
                "text": doi,
                "url": f"https://doi.org/{doi}",
            }
    return {
        "text": fallback,
        "url": "",
    }


def request_path(route_name, *args):
    from django.urls import reverse

    return reverse(route_name, args=args)


def _attach_pathway_links(results):
    pesticides = {
        str(row.get("pesticide", "")).strip()
        for row in results
        if str(row.get("pesticide", "")).strip() and str(row.get("pesticide", "")).strip() != "-"
    }
    pathway_counts = {
        pesticide.casefold(): DegradationPathway.objects.filter(pesticide__iexact=pesticide).count()
        for pesticide in pesticides
    }
    for row in results:
        pesticide = str(row.get("pesticide", "")).strip()
        count = pathway_counts.get(pesticide.casefold(), 0)
        row["pathway_record_count"] = count
        row["has_pathway"] = bool(count)


def pathwayanalysis(request):
    selected_pesticide = request.GET.get("pesticide", "").strip()
    pathway_aliases = {
        "aldrin": "Aldrin and Dieldrin",
        "dieldrin": "Aldrin and Dieldrin",
    }
    selected_pesticide = pathway_aliases.get(selected_pesticide.casefold(), selected_pesticide)
    pathway_pesticides = curated_pathway_pesticide_names()
    eligible_pathway_names = {name.casefold(): name for name in pathway_pesticides}
    selected_pesticide = eligible_pathway_names.get(selected_pesticide.casefold(), selected_pesticide)
    selected_is_pathway_eligible = not selected_pesticide or selected_pesticide.casefold() in eligible_pathway_names
    pathways = DegradationPathway.objects.none()
    evidence_records = Pesticide.objects.none()
    graph_elements = []
    pathway_steps = []
    pathway_status = None
    selected_compound = None
    has_unresolved_only_graph = False

    if selected_pesticide and selected_is_pathway_eligible:
        selected_compound = Compound.objects.filter(name__iexact=selected_pesticide).first()
        pathways = (
            DegradationPathway.objects
            .filter(pesticide__iexact=selected_pesticide)
            .prefetch_related(
                "steps__protein",
                "steps__substrate_compound",
                "steps__product_compound",
                "steps__references",
                "references",
            )
        )
        evidence_records = (
            Pesticide.objects
            .filter(pesticide__iexact=selected_pesticide)
            .order_by("publication_year", "microorganism")
        )
        graph_elements = _pathway_graph_elements(pathways, selected_pesticide)
        pathway_steps = [
            step
            for pathway in pathways
            for step in pathway.steps.all()
        ]
        for step in pathway_steps:
            step.display_reaction_label = _concise_pathway_reaction_label(step, detailed=True)
            step.display_substrate = _pathway_display_substrate(step, selected_pesticide)
            step.display_reference = _pathway_reference_context(
                step.doi,
                step.pathway.doi,
                step.pathway.reference,
            )
        evidence_records = list(evidence_records)
        for record in evidence_records:
            record.display_reference = _pathway_reference_context(
                record.doi,
                record.reference,
            )
        drawable_step_count = sum(1 for step in pathway_steps if not _is_unresolved_pathway_step(step))
        pathway_status = _pathway_confidence_status(pathway_steps, drawable_step_count)
        has_unresolved_only_graph = bool(graph_elements) and not pathway_steps

    return render(request, "base/tools/pathwayanalysis.html", {
        "pesticides_list": pathway_pesticides,
        "selected_pesticide": selected_pesticide,
        "pathways": pathways,
        "pathway_steps": pathway_steps,
        "pathway_status": pathway_status,
        "evidence_records": evidence_records,
        "selected_compound": selected_compound,
        "has_unresolved_only_graph": has_unresolved_only_graph,
        "pathway_graph_json": json.dumps(graph_elements),
        **database_summary(),
    })


def compound_detail(request, compound_id):
    compound = get_object_or_404(Compound, id=compound_id)
    substrate_steps = (
        compound.pathway_steps_as_substrate
        .select_related("pathway", "product_compound", "protein")
        .prefetch_related("references")
    )
    product_steps = (
        compound.pathway_steps_as_product
        .select_related("pathway", "substrate_compound", "protein")
        .prefetch_related("references")
    )
    return render(request, "base/compound_detail.html", {
        "compound": compound,
        "substrate_steps": substrate_steps,
        "product_steps": product_steps,
    })


def pathway_step_detail(request, step_id):
    step = get_object_or_404(
        DegradationPathwayStep.objects
        .select_related("pathway", "protein", "substrate_compound", "product_compound")
        .prefetch_related("references", "evidence_links__reference"),
        id=step_id,
    )
    evidence_links = PathwayEvidence.objects.filter(step=step).select_related(
        "reference",
        "pesticide_record",
    )
    return render(request, "base/pathway_step_detail.html", {
        "step": step,
        "evidence_links": evidence_links,
    })


def pesticideclassification(request):
    counts = pesticide_counts()
    return render(request, 'base/tools/pesticideclassification.html', {
        "pesticide_count": counts["total"],
        "total_pesticides": counts["total"],
        "pesticides_with_evidence": counts["with_evidence"],
        "pesticides_no_evidence": counts["no_evidence"],
    })
