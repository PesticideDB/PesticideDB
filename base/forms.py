from django import forms
from .models import DataSubmission

class DataSubmissionForm(forms.ModelForm):
    class Meta:
        model = DataSubmission
        fields = ['pesticide', 'microorganism_name', 'protein', 'gene', 
                  'evidence', 'doi', 'email']
        widgets = {
            'pesticide': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Atrazine',
                'maxlength': '70'
            }),
            'microorganism_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Pseudomonas sp. strain ADP',
                'maxlength': '100'
            }),
            'protein': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Atrazine chlorohydrolase (AtzA)',
                'maxlength': '70'
            }),
            'gene': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., atzA',
                'maxlength': '50'
            }),
            'evidence': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Briefly describe the experimental evidence...',
                'maxlength': '500'
            }),
            'doi': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 10.1016/j.scitotenv.2024.123456',
                'pattern': '10\.\d{4,9}/[-._;()/:A-Z0-9]+',
                'title': 'Enter a DOI starting with 10.xxxx/...'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'you@example.com',
                'maxlength': '100'
            }),
        }