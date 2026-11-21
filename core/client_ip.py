"""The one place that decides which IP address a request came from (#111).

Production sits behind Cloudflare, then a Linode NodeBalancer, then nginx.
X-Forwarded-For can't be trusted as a whole: every proxy *appends* to
whatever the client sent, so its leftmost entries are attacker-controlled.
Using it (as DRF's default ``get_ident()`` does) let a client send a new
made-up value on every request and get a fresh rate-limit bucket each time.

Resolution order:

1. ``settings.CLIENT_IP_HEADER`` (default ``HTTP_CF_CONNECTING_IP``).
   Cloudflare sets ``CF-Connecting-IP`` itself and overwrites any value the
   client sent, so on requests that came through Cloudflare it is the real
   client address. Set ``CLIENT_IP_HEADER=""`` to turn this off.
2. The **last** X-Forwarded-For hop: the address our nearest proxy saw.
   The client can't forge that one (anything it sends lands to the left).
3. ``REMOTE_ADDR`` (no proxy at all, e.g. local dev).

A header value that isn't a valid IP address is ignored, so garbage can't
be used to mint new identities either.

The trusted header is only as good as the network in front of it: if the
origin accepts traffic that didn't come through Cloudflare, a client can
send its own CF-Connecting-IP. Keep the NodeBalancer/firewall limited to
Cloudflare's IP ranges (see docs/ADMIN_HARDENING.md).
"""
import ipaddress

from django.conf import settings

DEFAULT_CLIENT_IP_HEADER = 'HTTP_CF_CONNECTING_IP'


def _valid_ip(value):
    """Return the normalised IP in ``value``, or None if it isn't one."""
    if not value:
        return None
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


def get_client_ip(request):
    """Best trustworthy client IP for ``request``, or None without one.

    Accepts a Django HttpRequest or a DRF Request (both expose ``.META``).
    ``request`` may be None: authenticate() and the login signals allow it.
    """
    if request is None:
        return None
    meta = request.META

    header = getattr(settings, 'CLIENT_IP_HEADER', DEFAULT_CLIENT_IP_HEADER)
    if header:
        ip = _valid_ip(meta.get(header, ''))
        if ip:
            return ip

    forwarded = meta.get('HTTP_X_FORWARDED_FOR', '')
    hops = [hop.strip() for hop in forwarded.split(',') if hop.strip()]
    if hops:
        ip = _valid_ip(hops[-1])
        if ip:
            return ip

    return _valid_ip(meta.get('REMOTE_ADDR', '')) or meta.get('REMOTE_ADDR')
