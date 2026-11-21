"""DRF throttles that identify anonymous clients safely (#111).

DRF's ``BaseThrottle.get_ident()`` uses the whole X-Forwarded-For header
when ``NUM_PROXIES`` isn't set, so a forged header gave every request a new
bucket. These classes use ``core.client_ip.get_client_ip`` instead. Every
throttle in the project should subclass one of these, not DRF's directly
(``core.tests`` checks this).
"""
from rest_framework import throttling

from core.client_ip import get_client_ip


class ClientIPIdentMixin:
    """Identify the client by its trusted IP, not raw X-Forwarded-For."""

    def get_ident(self, request):
        return get_client_ip(request) or ''


class AnonRateThrottle(ClientIPIdentMixin, throttling.AnonRateThrottle):
    pass


class UserRateThrottle(ClientIPIdentMixin, throttling.UserRateThrottle):
    pass


class ScopedRateThrottle(ClientIPIdentMixin, throttling.ScopedRateThrottle):
    pass
