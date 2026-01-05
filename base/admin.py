from django.contrib import admin
from .models import Pesticide, NoEvidencePesticide

# Register your models here.
admin.site.register(Pesticide)
admin.site.register(NoEvidencePesticide)