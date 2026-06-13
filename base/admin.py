from django.contrib import admin
from .models import Pesticide, NoEvidencePesticide
from .models import Pesticide, NoEvidencePesticide, AnnotationJob

# Register your models here.
admin.site.register(Pesticide)
admin.site.register(NoEvidencePesticide)
admin.site.register(AnnotationJob)