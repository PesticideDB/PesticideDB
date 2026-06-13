from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Count, Q
from django.db.models.functions import Lower
from django.http import HttpResponse, FileResponse, Http404
from django.conf import settings

import os
import threading
import shutil
import random

import uuid
import pandas as pd
from django.shortcuts import render, redirect, get_object_or_404
from django.http import FileResponse, Http404
from django.conf import settings
from .models import  Pesticide, NoEvidencePesticide, DataSubmission, ProteinRecord, AnnotationJob, GenomeAnnotationJob, ProteinRecord

import requests
import xml.etree.ElementTree as ET

from .forms import DataSubmissionForm
from base.utils import pesticide_counts

from django.contrib import messages
from .models import GenomeAnnotationJob, ProteinRecord

def home(request):
    counts = pesticide_counts()

    microorganisms_count = (
        Pesticide.objects
        .exclude(pesticide='')
        .exclude(pesticide__isnull=True)
        .exclude(microorganism='')
        .exclude(microorganism__isnull=True)
        .exclude(microorganism__iexact='not specified')
        .annotate(p=Lower('pesticide'), m=Lower('microorganism'))
        .values('p', 'm')
        .distinct()
        .count()
    )

    proteins_count = ProteinRecord.objects.count()

    context = {
        "total_pesticides": counts["total"],
        "pesticides_with_evidence": counts["with_evidence"],
        "pesticides_no_evidence": counts["no_evidence"],
        "pesticide_count": counts["total"],
        "microorganisms_count": microorganisms_count,
        "proteins_count": proteins_count,
        "protein_version": "1.0",
    }
    return render(request, "base/home.html", context)


def about(request):
    counts = pesticide_counts()

    microorganisms_count = (
        Pesticide.objects
        .exclude(pesticide='')
        .exclude(pesticide__isnull=True)
        .exclude(microorganism='')
        .exclude(microorganism__isnull=True)
        .exclude(microorganism__iexact='not specified')
        .annotate(p=Lower('pesticide'), m=Lower('microorganism'))
        .values('p', 'm')
        .distinct()
        .count()
    )

    context = {
        "total_pesticides": counts["total"],
        "pesticides_with_evidence": counts["with_evidence"],
        "pesticides_no_evidence": counts["no_evidence"],
        "pesticide_count": counts["total"],
        "microorganisms_count": microorganisms_count,
    }
    return render(request, "base/about.html", context)


def contact(request):
    return render(request, "base/contact.html")


# ✅ ONLY THIS FUNCTION CHANGED: microorganisms()
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
        filters['evidence_by_microbe__icontains'] = evidence
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

    if pesticide and no_evidence_message:
        results = queryset.none()
        is_search = True
    else:
        if filters:
            results = queryset.filter(**filters).order_by('microorganism', 'pesticide')
            is_search = True
        else:
            results = queryset.order_by('microorganism', 'pesticide')[:100]
            is_search = False

    # ✅ NEW: dropdown values for microorganisms.html
    base_qs = Pesticide.objects.all()

    microorganisms_list = (
        base_qs.values_list("microorganism", flat=True)
        .exclude(microorganism__isnull=True).exclude(microorganism="")
        .exclude(microorganism__iexact="not specified")
        .distinct().order_by("microorganism")
    )

    pesticides_list = (
        base_qs.values_list("pesticide", flat=True)
        .exclude(pesticide__isnull=True).exclude(pesticide="")
        .distinct().order_by("pesticide")
    )

    evidence_list = (
        base_qs.values_list("evidence_by_microbe", flat=True)
        .exclude(evidence_by_microbe__isnull=True).exclude(evidence_by_microbe="")
        .distinct().order_by("evidence_by_microbe")
    )

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

    context = {
        'results': results,
        'is_search': is_search,
        'total_count': results.count() if hasattr(results, 'count') else len(results),
        'no_evidence_message': no_evidence_message,

        # ✅ send dropdown options
        'microorganisms_list': microorganisms_list,
        'pesticides_list': pesticides_list,
        'evidence_list': evidence_list,
        'gene_list': gene_list,
        'protein_list': protein_list,
        'environment_list': environment_list,
        'location_list': location_list,

        # ✅ keep selected values (so it stays selected after search)
        'selected_microorganism': microorganism,
        'selected_pesticide': pesticide,
        'selected_evidence': evidence,
        'selected_gene': gene,
        'selected_protein': protein,
        'selected_environment': environment,
        'selected_location': location,
    }
    return render(request, 'base/microorganisms.html', context)


# ================= PROTEINS LIST (UNCHANGED) =================

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
        qs = qs.filter(pesticide=selected_pesticide)

    if selected_enzyme_class:
        qs = qs.filter(enzyme_class=selected_enzyme_class)

    if selected_evidence_type:
        qs = qs.filter(evidence_type=selected_evidence_type)

    is_search = any([
        selected_protein, selected_protein_id, selected_microorganism,
        selected_pesticide, selected_enzyme_class, selected_evidence_type
    ])

    total_count = qs.count()
    results = qs[:100]

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
    ids_b = (
        qs.exclude(pbdb_protein_id__isnull=True)
          .exclude(pbdb_protein_id="")
          .exclude(pbdb_protein_id__iexact="nan")
          .values_list("pbdb_protein_id", flat=True)
    )
    protein_ids_list = sorted(set(list(ids_a) + list(ids_b)))

    microorganisms_list = (
        qs.values_list("microorganism", flat=True)
        .exclude(microorganism__isnull=True)
        .exclude(microorganism="")
        .distinct()
        .order_by("microorganism")
    )

    pesticides_list = (
        qs.values_list("pesticide", flat=True)
        .exclude(pesticide__isnull=True)
        .exclude(pesticide="")
        .distinct()
        .order_by("pesticide")
    )

    enzyme_class_list = (
        qs.values_list("enzyme_class", flat=True)
        .exclude(enzyme_class__isnull=True)
        .exclude(enzyme_class="")
        .distinct()
        .order_by("enzyme_class")
    )

    evidence_type_list = (
        qs.values_list("evidence_type", flat=True)
        .exclude(evidence_type__isnull=True)
        .exclude(evidence_type="")
        .distinct()
        .order_by("evidence_type")
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

        "selected_protein": selected_protein,
        "selected_protein_id": selected_protein_id,
        "selected_microorganism": selected_microorganism,
        "selected_pesticide": selected_pesticide,
        "selected_enzyme_class": selected_enzyme_class,
        "selected_evidence_type": selected_evidence_type,
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

    img_rel = f"protein_structures/images/{display_id}.png"
    pdb_rel = f"protein_structures/pdb/{display_id}.pdb"

    img_abs = os.path.join(settings.MEDIA_ROOT, img_rel)
    pdb_abs = os.path.join(settings.MEDIA_ROOT, pdb_rel)

    structure_image_url = settings.MEDIA_URL + img_rel if os.path.exists(img_abs) else None
    pdb_download_url = settings.MEDIA_URL + pdb_rel if os.path.exists(pdb_abs) else None

    context = {
        "p": p,
        "structure_image_url": structure_image_url,
        "pdb_download_url": pdb_download_url,
        "prediction_software": "ColabFold (AlphaFold2-based)",
        "file_format": "PDB",
    }

    return render(request, "base/protein_detail.html", context)


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

    total_microorganisms = (
        Pesticide.objects
        .exclude(pesticide='')
        .exclude(pesticide__isnull=True)
        .exclude(microorganism='')
        .exclude(microorganism__isnull=True)
        .exclude(microorganism__iexact='not specified')
        .annotate(p=Lower('pesticide'), m=Lower('microorganism'))
        .values('p', 'm')
        .distinct()
        .count()
    )

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
        "total_microorganisms": total_microorganisms,
        "total_proteins": total_proteins,
        "publications_by_year": publications_by_year,
    })


def classification(request):
    return render(request, 'base/tools/classification.html')


# ================= ANNOTATE GENE JOB SYSTEM =================

def _annotation_pipeline_worker(job_id, uploaded_query):
    """
    Background worker for Annotate Gene.
    Local-development version using threading.
    Later this can be moved to Celery + Redis.
    """
    import subprocess

    pipeline_dir = "/Users/nana/Desktop/PepDB/PepDatabase/PBDB_annotation"

    predicted_proteins = os.path.join(pipeline_dir, "data", f"{job_id}_predicted_proteins.faa")
    diamond_result = os.path.join(pipeline_dir, "results", "diamond_results.tsv")
    hmmer_result = os.path.join(pipeline_dir, "results", "hmmer_results.tbl")
    hmmer_domains = os.path.join(pipeline_dir, "results", "hmmer_domains.tbl")
    final_result = os.path.join(pipeline_dir, "results", "final_annotation_with_hmmer.csv")

    diamond_db = os.path.join(pipeline_dir, "diamond_db", "pbdb_diamond")
    hmmer_db = os.path.join(pipeline_dir, "hmmer_db", "pbdb_profiles.hmm")

    job_output_dir = os.path.join(settings.MEDIA_ROOT, "annotation_jobs", job_id)
    os.makedirs(job_output_dir, exist_ok=True)
    downloadable_result = os.path.join(job_output_dir, f"{job_id}_annotation_results.csv")

    try:
        job = AnnotationJob.objects.get(job_id=job_id)
        job.status = "running"
        job.message = "Annotation job is running."
        job.save(update_fields=["status", "message"])

        # Detect DNA or protein input
        with open(uploaded_query, "r") as f:
            text = f.read()

        sequence_only = "".join(
            line.strip()
            for line in text.splitlines()
            if not line.startswith(">")
        )

        if not sequence_only:
            job.status = "failed"
            job.message = "Uploaded FASTA file has no sequence data."
            job.save(update_fields=["status", "message"])
            return

        letters = [c.upper() for c in sequence_only if c.isalpha()]
        total_letters = len(letters)

        dna_count = sum(1 for c in letters if c in "ATGCN")
        dna_ratio = dna_count / total_letters if total_letters else 0

        # If 90% or more letters are DNA letters, treat as genome/contig DNA
        # Otherwise treat as protein FASTA and skip Prodigal
        is_dna = dna_ratio >= 0.90

        print("DNA ratio:", dna_ratio)
        print("Input detected as:", "DNA/genome" if is_dna else "protein")

        # If DNA, run Prodigal first
        if is_dna:
            prodigal_run = subprocess.run([
                "prodigal",
                "-i", uploaded_query,
                "-a", predicted_proteins,
                "-p", "meta",
                "-q"
            ], capture_output=True, text=True)

            if prodigal_run.returncode != 0:
                job.status = "failed"
                job.message = prodigal_run.stderr or "Prodigal failed."
                job.save(update_fields=["status", "message"])
                return

            query_for_tools = predicted_proteins
        else:
            query_for_tools = uploaded_query

        # Run DIAMOND
        diamond_run = subprocess.run([
            "diamond", "blastp",
            "-d", diamond_db,
            "-q", query_for_tools,
            "-o", diamond_result,
            "--outfmt", "6",
            "qseqid", "sseqid", "pident", "length", "evalue", "bitscore",
            "--evalue", "1e-5",
            "--id", "50",
            "--query-cover", "70",
            "--max-target-seqs", "3",
            "--threads", "4"
        ], capture_output=True, text=True)

        if diamond_run.returncode != 0:
            job.status = "failed"
            job.message = diamond_run.stderr or "DIAMOND failed."
            job.save(update_fields=["status", "message"])
            return

        # No DIAMOND hit
        if (not os.path.exists(diamond_result)) or os.path.getsize(diamond_result) == 0:
            job.status = "No Hit"
            job.message = "Your job completed successfully, however your sequences did not match any proteins in the database."
            job.save(update_fields=["status", "message"])
            return

        # Run HMMER
        hmmer_run = subprocess.run([
            "hmmscan",
            "--tblout", hmmer_result,
            "--domtblout", hmmer_domains,
            hmmer_db,
            query_for_tools
        ], capture_output=True, text=True)

        if hmmer_run.returncode != 0:
            job.status = "failed"
            job.message = hmmer_run.stderr or "HMMER failed."
            job.save(update_fields=["status", "message"])
            return

        # Run annotation scripts
        annotation_run = subprocess.run(
            ["python", "scripts/annotate_diamond.py"],
            cwd=pipeline_dir,
            capture_output=True,
            text=True
        )

        if annotation_run.returncode != 0:
            job.status = "failed"
            job.message = annotation_run.stderr or "annotate_diamond.py failed."
            job.save(update_fields=["status", "message"])
            return

        merge_run = subprocess.run(
            ["python", "scripts/merge_diamond_hmmer.py"],
            cwd=pipeline_dir,
            capture_output=True,
            text=True
        )

        if merge_run.returncode != 0:
            job.status = "failed"
            job.message = merge_run.stderr or "merge_diamond_hmmer.py failed."
            job.save(update_fields=["status", "message"])
            return

        if (not os.path.exists(final_result)) or os.path.getsize(final_result) == 0:
            job.status = "No Hit"
            job.message = "Your job completed successfully, however no final annotation result was generated."
            job.save(update_fields=["status", "message"])
            return

        # Copy result to MEDIA_ROOT so it is downloadable from the web interface
        shutil.copy(final_result, downloadable_result)

        # Confirm CSV has data rows
        df = pd.read_csv(downloadable_result)
        if df.empty:
            job.status = "No Hit"
            job.message = "Your job completed successfully, however your sequences did not match any proteins in the database."
            job.result_file = downloadable_result
            job.save(update_fields=["status", "message", "result_file"])
            return

        job.status = "done"
        job.message = "Your job completed successfully."
        job.result_file = downloadable_result
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
    pipeline_dir = "/Users/nana/Desktop/PepDB/PepDatabase/PBDB_annotation"

    if request.method == "POST":
        fasta_file = request.FILES.get("fasta_file")

        if fasta_file:
            os.makedirs(os.path.join(pipeline_dir, "data"), exist_ok=True)
            os.makedirs(os.path.join(pipeline_dir, "results"), exist_ok=True)

            job_id = f"MS{random.randint(1000000, 9999999)}"
            while AnnotationJob.objects.filter(job_id=job_id).exists():
                job_id = f"MS{random.randint(1000000, 9999999)}"

            uploaded_query = os.path.join(pipeline_dir, "data", f"{job_id}_query.fasta")

            with open(uploaded_query, "wb+") as destination:
                for chunk in fasta_file.chunks():
                    destination.write(chunk)

            AnnotationJob.objects.create(
                job_id=job_id,
                status="running",
                message="Annotation job is running."
            )

            thread = threading.Thread(
                target=_annotation_pipeline_worker,
                args=(job_id, uploaded_query),
                daemon=True
            )
            thread.start()

            return redirect("annotategene_status", job_id=job_id)

    return render(request, "base/tools/annotategene.html")

def annotategene_status(request, job_id):
    import pandas as pd

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
            "No Hit": False,
        })

    if job.status == "No Hit":
        return render(request, "base/tools/annotategene_result.html", {
            "job": job,
            "results": [],
            "No Hit": True,
            "message": job.message,
        })

    results = []
    pesticide_hits = []
    hmmer_hits = []

    if job.status == "done" and job.result_file and os.path.exists(job.result_file):
        df = pd.read_csv(job.result_file)

        if "diamond_evalue" in df.columns:
            df["diamond_evalue"] = df["diamond_evalue"].apply(lambda x: f"{float(x):.2e}" if str(x) != "nan" else "-")

        if "hmmer_evalue" in df.columns:
            df["hmmer_evalue"] = df["hmmer_evalue"].apply(lambda x: f"{float(x):.2e}" if str(x) != "nan" else "-")

        df = pd.read_csv(job.result_file)

        # Format DIAMOND evalue
        if "diamond_evalue" in df.columns:
            df["diamond_evalue"] = df["diamond_evalue"].apply(
                lambda x: f"{float(x):.2e}" if pd.notnull(x) else "-"
            )

        # Format HMMER evalue
        if "hmmer_evalue" in df.columns:
            df["hmmer_evalue"] = df["hmmer_evalue"].apply(
                lambda x: f"{float(x):.2e}" if pd.notnull(x) else "-"
            )

        results = df.to_dict(orient="records")

        if "pesticide" in df.columns:
            pesticide_hits = (
                df.groupby("pesticide")
                .size()
                .reset_index(name="hit_count")
                .to_dict(orient="records")
            )

        if "hmmer_family" in df.columns:
            hmmer_hits = (
                df.groupby("hmmer_family")
                .size()
                .reset_index(name="hit_count")
                .to_dict(orient="records")
            )

    return render(request, "base/tools/annotategene_result.html", {
        "job": job,
        "results": results,
        "pesticide_hits": pesticide_hits,
        "hmmer_hits": hmmer_hits,
        "No Hit": False,
    })


def annotategene_download(request, job_id):
    job = get_object_or_404(AnnotationJob, job_id=job_id)

    if not job.result_file or not os.path.exists(job.result_file):
        raise Http404("Result file not found.")

    return FileResponse(
        open(job.result_file, "rb"),
        as_attachment=True,
        filename=f"{job_id}_annotation_results.csv"
    )

    import pandas as pd

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
            "No Hit": False,
        })

    if job.status == "No Hit":
        return render(request, "base/tools/annotategene_result.html", {
            "job": job,
            "results": [],
            "No Hit": True,
            "message": job.message,
        })

    results = []
    pesticide_hits = []
    hmmer_hits = []

    if job.status == "done" and job.result_file and os.path.exists(job.result_file):
        df = pd.read_csv(job.result_file)
        results = df.to_dict(orient="records")

        if "pesticide" in df.columns:
            pesticide_hits = (
                df.groupby("pesticide")
                .size()
                .reset_index(name="hit_count")
                .to_dict(orient="records")
            )

        if "hmmer_family" in df.columns:
            hmmer_hits = (
                df.groupby("hmmer_family")
                .size()
                .reset_index(name="hit_count")
                .to_dict(orient="records")
            )

    return render(request, "base/tools/annotategene_result.html", {
        "job": job,
        "results": results,
        "pesticide_hits": pesticide_hits,
        "hmmer_hits": hmmer_hits,
        "No Hit": False,
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

# ================= ANNOTATE GENOME JOB SYSTEM =================
# Temporary development version: creates clean test result + downloadable Excel

#connecting to genome annotation pipeline (temporary version for development)
def _genome_annotation_pipeline_worker(job_id, uploaded_query):
    import subprocess
    import pandas as pd

    pipeline_dir = "/Users/nana/Desktop/PepDB/PepDatabase/PBDB_annotation"

    predicted_proteins = os.path.join(
        pipeline_dir, "data", f"{job_id}_predicted_proteins.faa"
    )

    diamond_result = os.path.join(
        pipeline_dir, "results", f"{job_id}_genome_diamond_results.tsv"
    )

    diamond_db = os.path.join(
        pipeline_dir, "diamond_db", "pbdb_diamond"
    )

    job_output_dir = os.path.join(settings.MEDIA_ROOT, "genome_jobs", job_id)
    os.makedirs(job_output_dir, exist_ok=True)

    downloadable_result = os.path.join(
        job_output_dir,
        f"{job_id}_genome_annotation_results.csv"
    )

    try:
        job = GenomeAnnotationJob.objects.get(job_id=job_id)
        job.status = "running"
        job.message = "Genome annotation is running."
        job.save(update_fields=["status", "message"])

        # Detect DNA or protein FASTA
        with open(uploaded_query, "r", errors="ignore") as f:
            text = f.read()

        sequence_only = "".join(
            line.strip()
            for line in text.splitlines()
            if not line.startswith(">")
        )

        if not sequence_only:
            job.status = "failed"
            job.message = "Uploaded FASTA file has no sequence data."
            job.save(update_fields=["status", "message"])
            return

        dna_letters = set("ATGCNatgcn")
        is_dna = all(c in dna_letters for c in sequence_only if c.isalpha())

        if is_dna:
            prodigal_run = subprocess.run([
                "prodigal",
                "-i", uploaded_query,
                "-a", predicted_proteins,
                "-p", "meta",
                "-q"
            ], capture_output=True, text=True)

            if prodigal_run.returncode != 0:
                job.status = "failed"
                job.message = prodigal_run.stderr or "Prodigal failed."
                job.save(update_fields=["status", "message"])
                return

            query_for_diamond = predicted_proteins
        else:
            query_for_diamond = uploaded_query

        # Run DIAMOND
        diamond_run = subprocess.run([
            "diamond", "blastp",
            "-d", diamond_db,
            "-q", query_for_diamond,
            "-o", diamond_result,
            "--outfmt", "6",
            "qseqid", "sseqid", "pident", "length", "evalue", "bitscore",
            "--evalue", "1e-6",
            "--query-cover", "60",
            "--max-target-seqs", "3",
            "--threads", "6"
        ], capture_output=True, text=True)

        if diamond_run.returncode != 0:
            job.status = "failed"
            job.message = diamond_run.stderr or "DIAMOND failed."
            job.save(update_fields=["status", "message"])
            return

        if not os.path.exists(diamond_result) or os.path.getsize(diamond_result) == 0:
            job.status = "No Hit"
            job.message = "No genome annotation hits were found."
            job.save(update_fields=["status", "message"])
            return

        diamond_df = pd.read_csv(
            diamond_result,
            sep="\t",
            header=None,
            names=[
                "query",
                "diamond_hit_id",
                "identity",
                "alignment_length",
                "diamond_evalue",
                "bitscore",
            ]
        )
        
        # Keeping best hit per query
        diamond_df["bitscore"] = pd.to_numeric(diamond_df["bitscore"], errors="coerce").fillna(0)

        diamond_df = (
            diamond_df
            .sort_values("bitscore", ascending=False)
            .drop_duplicates(subset=["query"])
        )

        final_rows = []

        # Load all ProteinRecord accessions one time
        protein_lookup = {}

        for p in ProteinRecord.objects.all():
            acc = (p.ncbi_protein_accession or "").strip()

            if acc:
                protein_lookup[acc.lower()] = p
                protein_lookup[acc.split(".")[0].lower()] = p

        for _, row in diamond_df.iterrows():
            protein = None

            raw_hit = str(row["diamond_hit_id"]).strip()

            # Clean DIAMOND hit ID
            clean_hit = raw_hit

            for prefix in ["sp|", "tr|", "ref|", "gb|", "emb|", "dbj|"]:
                if clean_hit.startswith(prefix):
                    clean_hit = clean_hit.replace(prefix, "")

            clean_hit = clean_hit.split("|")[0].strip()
            clean_hit_no_version = clean_hit.split(".")[0]

            protein = (
                protein_lookup.get(clean_hit.lower()) or
                protein_lookup.get(clean_hit_no_version.lower())
            )

            if not protein:
                print("NO MATCH:", raw_hit)
                continue

            # Extract data
            pesticidedb_id = protein.pesticidedb_protein_id or protein.pbdb_protein_id or "-"
            ncbi_accession = protein.ncbi_protein_accession or "-"
            reported_protein = protein.reported_protein_name or "-"
            gene_name = protein.gene_name or "-"
            enzyme_class = protein.enzyme_class or "-"
            microorganism = protein.microorganism or "-"
            pesticide = protein.pesticide or "-"
            evidence_type = protein.evidence_type or "-"
            year = protein.year or "-"
            doi = protein.doi or "-"

            final_rows.append({
                "query": row["query"],
                "pesticidedb_protein_id": raw_hit,
                "protein_detail_id": protein.pesticidedb_protein_id or protein.pbdb_protein_id or "-",
                "ncbi_protein_accession": ncbi_accession,
                "reported_protein_name": reported_protein,
                "identity": round(float(row["identity"]), 2),
                "alignment_length": row["alignment_length"],
                "diamond_evalue": f"{float(row['diamond_evalue']):.2e}",
                "bitscore": round(float(row["bitscore"]), 2),
                "enzyme_class": enzyme_class,
                "gene_name": gene_name,
                "microorganism": microorganism,
                "pesticide": pesticide,
                "evidence_type": evidence_type,
                "year": year,
                "doi": doi,
                "secreted": "NA",
            })

        result_df = pd.DataFrame(final_rows)
        
        if result_df.empty:
            job.status = "No Hit"
            job.message = "No mapped genome annotation hits were found."
            job.save(update_fields=["status", "message"])
            return

        result_df.to_csv(downloadable_result, index=False)

        job.status = "done"
        job.message = "Genome annotation completed successfully."
        job.result_file = downloadable_result
        job.save(update_fields=["status", "message", "result_file"])

    except Exception as e:
        job = GenomeAnnotationJob.objects.get(job_id=job_id)
        job.status = "failed"
        job.message = str(e)
        job.save(update_fields=["status", "message"])

#main connect genome
def annotategenome(request):
    if request.method == "POST":
        fasta_file = request.FILES.get("fasta_file")

        # Job number style: SM1234567
        job_id = f"SM{random.randint(1000000, 9999999)}"
        while GenomeAnnotationJob.objects.filter(job_id=job_id).exists():
            job_id = f"SM{random.randint(1000000, 9999999)}"

        job = GenomeAnnotationJob.objects.create(
            job_id=job_id,
            status="running",
            message="Genome annotation job is running."
        )
        
        job_dir = os.path.join(settings.MEDIA_ROOT, "genome_jobs", job_id)
        os.makedirs(job_dir, exist_ok=True)

        uploaded_query = os.path.join(job_dir, f"{job_id}_query.fasta")

        with open(uploaded_query, "wb+") as f:
            for chunk in fasta_file.chunks():
                f.write(chunk)

        thread = threading.Thread(
            target=_genome_annotation_pipeline_worker,
            args=(job_id, uploaded_query),
            daemon=True
        )
        thread.start()

        return redirect("annotategenome_running", job_id=job_id)
    
        # Get query name from uploaded FASTA header
        query_name = job_id
        with open(uploaded_query, "r", errors="ignore") as f:
            for line in f:
                if line.startswith(">"):
                    query_name = line.replace(">", "").strip().split()[0]
                    break

        # Get one REAL protein from your ProteinRecord database
        first_protein = (
            ProteinRecord.objects
            .exclude(pesticidedb_protein_id__isnull=True)
            .exclude(pesticidedb_protein_id="")
            .first()
        )

        if first_protein:
            real_pid = first_protein.pesticidedb_protein_id or first_protein.pbdb_protein_id or "-"
            real_ncbi = first_protein.ncbi_protein_accession or "-"
            real_enzyme = first_protein.enzyme_class or "-"
            real_gene = first_protein.gene_name or "-"
            real_microorganism = first_protein.microorganism or "-"
            real_pesticide = first_protein.pesticide or "-"
        else:
            real_pid = "-"
            real_ncbi = "-"
            real_enzyme = "-"
            real_gene = "-"
            real_microorganism = "-"
            real_pesticide = "-"

        # TEMPORARY clean test result
        results = [
            {
                "query": query_name,
                "pesticidedb_protein_id": real_pid,
                "ncbi_protein_accession": real_ncbi,
                "identity": 45.6,
                "diamond_evalue": "1.00e-50",
                "bitscore": 200,
                "enzyme_class": real_enzyme,
                "gene_name": real_gene,
                "microorganism": real_microorganism,
                "pesticide": real_pesticide,
                "secreted": "NA",
            }
        ]

        df = pd.DataFrame(results)
        df.to_excel(result_path, index=False)

        job.status = "done"
        job.message = "Genome annotation completed."
        job.result_file = result_path
        job.save()

        return redirect("annotategenome_running", job_id=job_id)

    return render(request, "base/tools/annotategenome.html")


def annotategenome_running(request, job_id):
    job = get_object_or_404(GenomeAnnotationJob, job_id=job_id)

    if job.status == "done":
        return redirect("annotategenome_result", job_id=job_id)

    return render(request, "base/tools/annotategenome_running.html", {
        "job": job
    })


def annotategenome_result(request, job_id):
    job = get_object_or_404(GenomeAnnotationJob, job_id=job_id)

    results = []
    pesticide_hits = []

    if job.result_file and os.path.exists(job.result_file):
        df = pd.read_csv(job.result_file, dtype=str)

        # Keep e-value
        if "diamond_evalue" in df.columns:
            df["diamond_evalue"] = df["diamond_evalue"].apply(
                lambda x: f"{float(x):.2e}" if pd.notnull(x) and str(x).lower() != "nan" else "-"
            )

        results = df.to_dict(orient="records")

        if "pesticide" in df.columns:
            pesticide_hits = (
                df.groupby("pesticide")
                .size()
                .reset_index(name="hit_count")
                .to_dict(orient="records")
            )

    return render(request, "base/tools/annotategenome_result.html", {
        "job": job,
        "results": results,
        "pesticide_hits": pesticide_hits,
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

def pathwayanalysis(request):
    return render(request, 'base/tools/pathwayanalysis.html')


def pesticideclassification(request):
    counts = pesticide_counts()
    return render(request, 'base/tools/pesticideclassification.html', {
        "pesticide_count": counts["total"],
        "total_pesticides": counts["total"],
        "pesticides_with_evidence": counts["with_evidence"],
        "pesticides_no_evidence": counts["no_evidence"],
    })

