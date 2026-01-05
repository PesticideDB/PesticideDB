from django.shortcuts import render, redirect
from django.db.models import Count, Q
from .models import Pesticide, NoEvidencePesticide, DataSubmission
from .forms import DataSubmissionForm

def home(request):
    """Home page view with carousel and statistics"""
    # Get counts for statistics
    pesticide_count = Pesticide.objects.count()
    microorganisms_count = Pesticide.objects.exclude(microorganism='').values('microorganism').distinct().count()
    
    # Count proteins (non-empty enzyme field)
    proteins_count = Pesticide.objects.exclude(enzyme='').exclude(enzyme__isnull=True).count()
    
    context = {
        'pesticide_count': pesticide_count,
        'microorganisms_count': microorganisms_count,
        'proteins_count': proteins_count,
        'protein_version': '1.0',
    }
    return render(request, 'base/home.html', context)

def about(request):
    """About page view"""
    pesticide_count = Pesticide.objects.count()
    microorganisms_count = Pesticide.objects.exclude(microorganism='').values('microorganism').distinct().count()
    
    context = {
        'pesticide_count': pesticide_count,
        'microorganisms_count': microorganisms_count,
    }
    return render(request, 'base/about.html', context)

def contact(request):
    """Contact page view"""
    return render(request, 'base/contact.html')

def microorganisms(request):
    """Microorganisms list view with search functionality"""
    # Initialize variables
    microorganisms_list = []
    pesticides_list = []
    evidence_list = []
    gene_list = []
    protein_list = []
    environment_list = []
    location_list = []
    results = []
    is_search = False
    
    # Get filter parameters from GET request
    microorganism = request.GET.get('microorganism', '')
    taxid = request.GET.get('taxid', '')
    pesticide = request.GET.get('pesticide', '')
    evidence = request.GET.get('evidence', '')
    gene = request.GET.get('gene', '')
    protein = request.GET.get('protein', '')
    environment = request.GET.get('environment', '')
    location = request.GET.get('location', '')
    
    # Build the base queryset
    queryset = Pesticide.objects.all()
    
    # Apply filters if they exist
    filters = {}
    
    if microorganism:
        filters['microorganism__icontains'] = microorganism
        is_search = True
    
    if taxid:
        filters['tax_id__icontains'] = taxid
        is_search = True
    
    if pesticide:
        filters['pesticide__icontains'] = pesticide
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
    
    # Apply filters if any were specified
    if filters:
        results = queryset.filter(**filters).order_by('microorganism', 'pesticide')
    else:
        # If no filters, show first 100 records
        results = queryset.order_by('microorganism', 'pesticide')[:100]
        is_search = False
    
    # Get distinct values for dropdowns
    # These queries only execute once per request
    microorganisms_list = queryset.exclude(microorganism='')\
        .exclude(microorganism__isnull=True)\
        .values_list('microorganism', flat=True)\
        .distinct()\
        .order_by('microorganism')
    
    # Get unique tax IDs (excluding empty)
    tax_ids = queryset.exclude(tax_id='')\
        .exclude(tax_id__isnull=True)\
        .values_list('tax_id', flat=True)\
        .distinct()\
        .order_by('tax_id')
    
    pesticides_list = queryset.exclude(pesticide='')\
        .exclude(pesticide__isnull=True)\
        .values_list('pesticide', flat=True)\
        .distinct()\
        .order_by('pesticide')
    
    evidence_list = queryset.exclude(evidence_by_microbe='')\
        .exclude(evidence_by_microbe__isnull=True)\
        .values_list('evidence_by_microbe', flat=True)\
        .distinct()\
        .order_by('evidence_by_microbe')
    
    gene_list = queryset.exclude(gene='')\
        .exclude(gene__isnull=True)\
        .values_list('gene', flat=True)\
        .distinct()\
        .order_by('gene')
    
    protein_list = queryset.exclude(enzyme='')\
        .exclude(enzyme__isnull=True)\
        .values_list('enzyme', flat=True)\
        .distinct()\
        .order_by('enzyme')
    
    environment_list = queryset.exclude(isolation_environment='')\
        .exclude(isolation_environment__isnull=True)\
        .values_list('isolation_environment', flat=True)\
        .distinct()\
        .order_by('isolation_environment')
    
    location_list = queryset.exclude(isolation_location='')\
        .exclude(isolation_location__isnull=True)\
        .values_list('isolation_location', flat=True)\
        .distinct()\
        .order_by('isolation_location')
    
    # Prepare context
    context = {
        # Lists for dropdowns
        'microorganisms_list': microorganisms_list,
        'tax_ids': tax_ids,  # Added this for taxid dropdown
        'pesticides_list': pesticides_list,
        'evidence_list': evidence_list,
        'gene_list': gene_list,
        'protein_list': protein_list,
        'environment_list': environment_list,
        'location_list': location_list,
        
        # Search results
        'results': results,
        'is_search': is_search,
        'total_count': results.count() if hasattr(results, 'count') else len(results),
        
        # Keep selected values in form
        'selected_microorganism': microorganism,
        'selected_taxid': taxid,
        'selected_pesticide': pesticide,
        'selected_evidence': evidence,
        'selected_gene': gene,
        'selected_protein': protein,
        'selected_environment': environment,
        'selected_location': location,
    }
    
    return render(request, 'base/microorganisms.html', context)

def proteins(request):
    """Proteins list view"""
    # Get proteins with related data
    proteins = Pesticide.objects.exclude(enzyme='').exclude(enzyme__isnull=True)\
        .values('enzyme', 'gene', 'pesticide', 'microorganism')\
        .order_by('enzyme')
    
    context = {
        'proteins': proteins,
        'total_count': proteins.count(),
    }
    return render(request, 'base/proteins.html', context)

def submit_your_data(request):
    """Data submission form view"""
    if request.method == 'POST':
        form = DataSubmissionForm(request.POST)
        if form.is_valid():
            form.save()
            # You can add a success message here
            return redirect('submit_your_data')
    else:
        form = DataSubmissionForm()
    
    # Get recent submissions
    recent_submissions = DataSubmission.objects.all().order_by('-submitted_at')[:10]
    
    context = {
        'form': form,
        'recent_submissions': recent_submissions,
    }
    return render(request, 'base/submit_your_data.html', context)

def statistics(request):
    """Statistics page view"""
    # Get various statistics
    total_pesticides = Pesticide.objects.count()
    total_microorganisms = Pesticide.objects.exclude(microorganism='').values('microorganism').distinct().count()
    total_proteins = Pesticide.objects.exclude(enzyme='').exclude(enzyme__isnull=True).count()
    
    # Get pesticides by category
    categories = Pesticide.objects.exclude(category='').exclude(category__isnull=True)\
        .values('category').annotate(count=Count('id')).order_by('-count')
    
    # Get publications by year
    publications_by_year = Pesticide.objects.exclude(publication_year__isnull=True)\
        .values('publication_year').annotate(count=Count('id')).order_by('-publication_year')
    
    context = {
        'total_pesticides': total_pesticides,
        'total_microorganisms': total_microorganisms,
        'total_proteins': total_proteins,
        'categories': categories,
        'publications_by_year': publications_by_year,
    }
    return render(request, 'base/statistics.html', context)

# Tool views (stubs for now)
def annotategene(request):
    return render(request, 'base/tools/annotategene.html')

def annotategenome(request):
    return render(request, 'base/tools/annotategenome.html')

def pathwayanalysis(request):
    return render(request, 'base/tools/pathwayanalysis.html')

def pesticideclassification(request):
    return render(request, 'base/tools/pesticideclassification.html')