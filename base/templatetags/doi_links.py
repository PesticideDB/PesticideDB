import re

from django import template


register = template.Library()

DOI_RE = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", re.IGNORECASE)


def _extract_doi(value):
    text = str(value or "").strip()
    match = DOI_RE.search(text)
    if not match:
        return ""
    return match.group(1).rstrip(".,;)")


@register.filter
def doi_text(value):
    return _extract_doi(value)


@register.filter
def doi_url(value):
    doi = _extract_doi(value)
    if not doi:
        return ""
    return f"https://doi.org/{doi}"
