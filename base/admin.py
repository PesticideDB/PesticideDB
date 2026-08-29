from django.contrib import admin
from django.utils import timezone
from .models import (
    AnnotationJob,
    Compound,
    DataSubmission,
    DegradationPathway,
    DegradationPathwayStep,
    GenomeAnnotationJob,
    LiteratureReference,
    NoEvidencePesticide,
    PathwayEvidence,
    Pesticide,
    ProteinRecord,
    SiteVisitCounter,
)

# Register your models here.
admin.site.register(Pesticide)
admin.site.register(NoEvidencePesticide)
admin.site.register(AnnotationJob)
admin.site.register(GenomeAnnotationJob)
admin.site.register(ProteinRecord)
admin.site.register(DegradationPathway)
admin.site.register(DegradationPathwayStep)
admin.site.register(Compound)
admin.site.register(LiteratureReference)
admin.site.register(PathwayEvidence)


@admin.register(SiteVisitCounter)
class SiteVisitCounterAdmin(admin.ModelAdmin):
    list_display = ("key", "total_visits", "updated_at")
    readonly_fields = ("key", "total_visits", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DataSubmission)
class DataSubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "pesticide",
        "microorganism_name",
        "protein",
        "gene",
        "review_status",
        "detected_sections",
        "submitted_at",
    )
    list_filter = (
        "review_status",
        "approve_biodegradation_record",
        "approve_protein_record",
        "flag_for_pathway_curation",
        "submitted_at",
    )
    search_fields = (
        "pesticide",
        "microorganism_name",
        "protein",
        "gene",
        "doi",
        "email",
        "evidence",
    )
    readonly_fields = (
        "submitted_at",
        "detected_sections",
        "reviewed_by",
        "reviewed_at",
        "imported_biodegradation_record",
        "imported_protein_record",
    )
    fieldsets = (
        ("Submitted evidence", {
            "fields": (
                "pesticide",
                "microorganism_name",
                "protein",
                "gene",
                "evidence",
                "doi",
                "email",
                "submitted_at",
            )
        }),
        ("Review decision", {
            "fields": (
                "review_status",
                "detected_sections",
                "approve_biodegradation_record",
                "approve_protein_record",
                "flag_for_pathway_curation",
                "review_notes",
                "reviewed_by",
                "reviewed_at",
            )
        }),
        ("Import links", {
            "fields": (
                "imported_biodegradation_record",
                "imported_protein_record",
            )
        }),
    )
    actions = (
        "mark_in_review",
        "approve_and_import_selected_sections",
        "mark_rejected",
    )

    @admin.action(description="Mark selected submissions as in review")
    def mark_in_review(self, request, queryset):
        count = queryset.update(
            review_status="IN_REVIEW",
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )
        self.message_user(request, f"{count} submission(s) marked as in review.")

    @admin.action(description="Approve and import checked database sections")
    def approve_and_import_selected_sections(self, request, queryset):
        imported_biodegradation = 0
        imported_proteins = 0
        pathway_flagged = 0
        skipped = 0

        for submission in queryset:
            created_any = False

            if submission.approve_biodegradation_record and not submission.imported_biodegradation_record:
                pesticide_record = Pesticide.objects.create(
                    pesticide=submission.pesticide,
                    microorganism=submission.microorganism_name,
                    gene=submission.gene or "",
                    enzyme=submission.protein or "",
                    evidence_by_microbe=submission.evidence,
                    evidence_of_enzyme=submission.evidence if submission.protein or submission.gene else "",
                    evidence_level="Submitted literature evidence; admin approved",
                    doi=submission.doi,
                    reference=f"Submitted by {submission.email}",
                )
                submission.imported_biodegradation_record = pesticide_record
                imported_biodegradation += 1
                created_any = True

            if (
                submission.approve_protein_record
                and not submission.imported_protein_record
                and (submission.protein or submission.gene)
            ):
                protein_record = ProteinRecord.objects.create(
                    pesticide=submission.pesticide,
                    microorganism=submission.microorganism_name,
                    evidence_type="Submitted literature evidence; admin approved",
                    collection_category="SUPPLEMENTED",
                    enzyme_class="",
                    reported_protein_name=submission.protein or submission.gene or "",
                    gene_name=submission.gene or "",
                    doi=submission.doi,
                    sequence_available="No sequence stored from submission",
                )
                submission.imported_protein_record = protein_record
                imported_proteins += 1
                created_any = True

            if submission.flag_for_pathway_curation:
                pathway_flagged += 1

            if created_any:
                submission.review_status = "PARTIALLY_IMPORTED" if submission.flag_for_pathway_curation else "APPROVED"
            elif submission.flag_for_pathway_curation:
                submission.review_status = "IN_REVIEW"
            else:
                skipped += 1

            submission.reviewed_by = request.user
            submission.reviewed_at = timezone.now()
            submission.save()

        self.message_user(
            request,
            (
                f"Imported {imported_biodegradation} biodegradation record(s), "
                f"{imported_proteins} protein record(s), "
                f"flagged {pathway_flagged} pathway candidate(s), "
                f"and skipped {skipped} submission(s) with no checked import section."
            ),
        )

    @admin.action(description="Reject selected submissions")
    def mark_rejected(self, request, queryset):
        count = queryset.update(
            review_status="REJECTED",
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )
        self.message_user(request, f"{count} submission(s) rejected.")
