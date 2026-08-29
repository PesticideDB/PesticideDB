from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('help/', views.help, name='help'),
    path('citation-download/', views.citation_download, name='citation_download'),
    path('downloads/proteins.csv', views.download_proteins_csv, name='download_proteins_csv'),
    path('downloads/biodegradation-records.csv', views.download_pesticides_csv, name='download_pesticides_csv'),
    path('downloads/no-evidence-pesticides.csv', views.download_no_evidence_csv, name='download_no_evidence_csv'),
    path('downloads/pathway-evidence.csv', views.download_pathway_evidence_csv, name='download_pathway_evidence_csv'),
    path('downloads/assets/<str:asset_name>/', views.download_annotation_asset, name='download_annotation_asset'),
    path('microorganisms/', views.microorganisms, name='microorganisms'),

    path('proteins/', views.proteins, name='proteins'),
    path('proteins/<str:pesticidedb_protein_id>/', views.protein_detail, name='protein_detail'),
    path('proteins/<str:pesticidedb_protein_id>/structure/pdb/', views.protein_pdb_file, name='protein_pdb_file'),
    path('proteins/<str:pesticidedb_protein_id>/structure/preview/', views.protein_structure_preview, name='protein_structure_preview'),
    path('proteins/<str:pesticidedb_protein_id>/fasta/', views.protein_fasta_download, name='protein_fasta_download'),
    path("proteins/<str:pesticidedb_protein_id>/fetch-fasta/", views.fetch_ncbi_fasta, name="fetch_ncbi_fasta"),


    path('submit_your_data/', views.submit_your_data, name='submit_your_data'),
    path('statistics/', views.statistics, name='statistics'),

    # Tool URLs
    path('annotategene/', views.annotategene, name='annotategene'),
    
    #new changes for annotationgene pipeline
    path("annotategene/status/<str:job_id>/", views.annotategene_status, name="annotategene_status"),
    path("annotategene/download/<str:job_id>/", views.annotategene_download, name="annotategene_download"),
    path("annotategene/download-all/<str:job_id>/", views.annotategene_all_matches_download, name="annotategene_all_matches_download"),

    #new changes for annotategenome pipeline
    path("annotategenome/running/<str:job_id>/", views.annotategenome_running, name="annotategenome_running"),
    path("annotategenome/result/<str:job_id>/", views.annotategenome_result, name="annotategenome_result"),
    path("annotategenome/download/<str:job_id>/", views.annotategenome_download, name="annotategenome_download"),
    path("annotategenome/download-all/<str:job_id>/", views.annotategenome_all_matches_download, name="annotategenome_all_matches_download"),

    path('annotategenome/', views.annotategenome, name='annotategenome'),
    path('pathwayanalysis/', views.pathwayanalysis, name='pathwayanalysis'),
    path('evidence-galaxy/', views.evidence_galaxy, name='evidence_galaxy'),
    path('evidence-galaxy/pesticides/', views.evidence_galaxy_pesticides, name='evidence_galaxy_pesticides'),
    path('evidence-galaxy/data/', views.evidence_galaxy_data, name='evidence_galaxy_data'),
    path('compounds/<int:compound_id>/', views.compound_detail, name='compound_detail'),
    path('pathway-steps/<int:step_id>/', views.pathway_step_detail, name='pathway_step_detail'),
    path('pesticideclassification/', views.pesticideclassification, name='pesticideclassification'),
]
