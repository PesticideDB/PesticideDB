from django.core.exceptions import ImproperlyConfigured
from django.db import OperationalError, ProgrammingError
from django.db.models import F

from .models import SiteVisitCounter


class SiteVisitCounterMiddleware:
    SKIPPED_PREFIXES = (
        "/admin/",
        "/static/",
        "/media/",
        "/favicon",
        "/robots.txt",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if self.should_count(request, response):
            self.increment_counter()
        return response

    def should_count(self, request, response):
        if request.method != "GET" or response.status_code >= 400:
            return False
        path = request.path_info or ""
        if any(path.startswith(prefix) for prefix in self.SKIPPED_PREFIXES):
            return False
        content_type = response.headers.get("Content-Type", "")
        return "text/html" in content_type

    def increment_counter(self):
        try:
            counter, _ = SiteVisitCounter.objects.get_or_create(key="site")
            SiteVisitCounter.objects.filter(pk=counter.pk).update(
                total_visits=F("total_visits") + 1
            )
        except (OperationalError, ProgrammingError, ImproperlyConfigured):
            return
