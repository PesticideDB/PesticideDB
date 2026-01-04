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
    """Microorganisms list view"""
    # Get unique microorganisms with their pesticide counts
    microorganisms = Pesticide.objects.exclude(microorganism='').exclude(microorganism__isnull=True)\
        .values('microorganism', 'phylum', 'family')\
        .annotate(pesticide_count=Count('pesticide'))\
        .order_by('microorganism')
    
    context = {
        'microorganisms': microorganisms,
        'total_count': microorganisms.count(),
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