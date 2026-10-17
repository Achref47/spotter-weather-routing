"""Per-client rate limits for POST /api/trips/analyze, built on Django REST framework.

Why: one analysis costs real quota. A cold Houston to Atlanta trip needs 100 to 240 forecast
locations from Open-Meteo plus 1 to 3 Mapbox requests. The limits stop one client from burning
the shared free-tier quota. They are deliberately generous for a person using the app: a
cold analysis takes 9 to 14 seconds, so nobody can run more than a handful a minute anyway.

Two windows are checked, both per client address:
  - a burst limit (default 10 per minute), and
  - a sustained limit (default 30 per hour).
Both rates come from settings (ANALYZE_THROTTLE_RATES) so they can be changed with environment
variables without touching code. The check runs before the view, so a throttled request never
reaches geocoding, routing or weather.
"""
import math

from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import exception_handler
from rest_framework.exceptions import Throttled


class _AnalyzeThrottle(SimpleRateThrottle):
    def get_rate(self):
        # Read at request time, so tests (and a changed setting) take effect immediately.
        return settings.ANALYZE_THROTTLE_RATES[self.scope]

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class AnalyzeBurstThrottle(_AnalyzeThrottle):
    scope = "analyze_burst"


class AnalyzeSustainedThrottle(_AnalyzeThrottle):
    scope = "analyze_hour"


def wait_text(seconds: int) -> str:
    """'45 seconds' or '12 minutes': how long until the client may try again."""
    if seconds < 90:
        return f"{seconds} second{'s' if seconds != 1 else ''}"
    minutes = math.ceil(seconds / 60)
    return f"{minutes} minutes"


def api_exception_handler(exc, context):
    """The default DRF handler, except a throttled request gets this API's usual error shape."""
    response = exception_handler(exc, context)
    if isinstance(exc, Throttled) and response is not None:
        wait = max(1, math.ceil(exc.wait or 1))
        response.data = {
            "error": f"Too many analyses in a short time. Please wait {wait_text(wait)} and try again.",
            "retry_after_s": wait,
        }
    return response
