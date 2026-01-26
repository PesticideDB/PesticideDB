from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Count, Q
from django.db.models.functions import Lower
from django.http import HttpResponse
from django.conf import settings
import os

import requests
import xml.etree.ElementTree as ET

from .models import Pesticide, NoEvidencePesticide, DataSubmission, ProteinRecord
from .forms import DataSubmissionForm
from base.utils import pesticide_counts

from django.contrib import messages


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

    proteins_count = (
        Pesticide.objects
        .exclude(enzyme='')
        .exclude(enzyme__isnull=True)
        .count()
    )

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

    total_proteins = (
        Pesticide.objects
        .exclude(enzyme='')
        .exclude(enzyme__isnull=True)
        .count()
    )

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


def annotategene(request):
    return render(request, 'base/tools/annotategene.html')


def annotategenome(request):
    return render(request, 'base/tools/annotategenome.html')


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
