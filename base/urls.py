from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('microorganisms/', views.microorganisms, name='microorganisms'),
    path('proteins/', views.proteins, name='proteins'),
    path('submit_your_data/', views.submit_your_data, name='submit_your_data'),
    path('statistics/', views.statistics, name='statistics'),
    
    # Tool URLs
    path('annotategene/', views.annotategene, name='annotategene'),
    path('annotategenome/', views.annotategenome, name='annotategenome'),
    path('pathwayanalysis/', views.pathwayanalysis, name='pathwayanalysis'),
    path('pesticideclassification/', views.pesticideclassification, name='pesticideclassification'),
]