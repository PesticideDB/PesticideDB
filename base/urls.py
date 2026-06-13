from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('microorganisms/', views.microorganisms, name='microorganisms'),

    path('proteins/', views.proteins, name='proteins'),
    path('proteins/<str:pesticidedb_protein_id>/', views.protein_detail, name='protein_detail'),
    path('proteins/<str:pesticidedb_protein_id>/fasta/', views.protein_fasta_download, name='protein_fasta_download'),
    path("proteins/<str:pesticidedb_protein_id>/fetch-fasta/", views.fetch_ncbi_fasta, name="fetch_ncbi_fasta"),


    path('submit_your_data/', views.submit_your_data, name='submit_your_data'),
    path('statistics/', views.statistics, name='statistics'),

    # Tool URLs
    path('annotategene/', views.annotategene, name='annotategene'),
    
    #new changes for annotationgene pipeline
    path("annotategene/status/<str:job_id>/", views.annotategene_status, name="annotategene_status"),
    path("annotategene/download/<str:job_id>/", views.annotategene_download, name="annotategene_download"),
    path("annotategene/status/<str:job_id>/", views.annotategene_status, name="annotategene_status"),
    path("annotategene/download/<str:job_id>/", views.annotategene_download, name="annotategene_download"),

    #new changes for annotategenome pipeline
    path("annotategenome/running/<str:job_id>/", views.annotategenome_running, name="annotategenome_running"),
    path("annotategenome/result/<str:job_id>/", views.annotategenome_result, name="annotategenome_result"),
    path("annotategenome/download/<str:job_id>/", views.annotategenome_download, name="annotategenome_download"),

    path('annotategenome/', views.annotategenome, name='annotategenome'),
    path("annotategenome/", views.annotategenome, name="annotategenome"),
    path('pathwayanalysis/', views.pathwayanalysis, name='pathwayanalysis'),
    path('pesticideclassification/', views.pesticideclassification, name='pesticideclassification'),
]

