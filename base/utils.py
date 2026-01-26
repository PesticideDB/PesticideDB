from base.models import Pesticide, NoEvidencePesticide


def pesticide_counts():
    """
    Returns correct pesticide statistics:
    - with experimental evidence
    - with no experimental evidence
    - total unique pesticides (union, no double counting)
    """

    with_evidence = set(
        Pesticide.objects
        .exclude(pesticide="")
        .exclude(pesticide__isnull=True)
        .values_list("pesticide", flat=True)
    )

    no_evidence = set(
        NoEvidencePesticide.objects
        .exclude(pesticide="")
        .exclude(pesticide__isnull=True)
        .values_list("pesticide", flat=True)
    )

    return {
        "with_evidence": len(with_evidence),
        "no_evidence": len(no_evidence),
        "total": len(with_evidence | no_evidence),
    }
