"""
The second, mandatory half of the SSRF guard.

`apps.common.validators.validate_monitor_url` only runs when a Monitor is
created or edited — it has no way to know what a hostname will resolve to
by the time a check actually runs, possibly months later. This module
re-resolves the hostname and re-checks every address it comes back with,
right before the outbound request, using the exact same denylist
(`apps.common.validators.is_denied_ipv4`) so the two checks can never drift
into different policies.

This still isn't airtight: `requests` resolves the hostname a second time,
independently, when it actually opens the connection — so there's a small
window between the check here and the real connection where a name could
flip to a different address. Closing that fully means connecting to the
address already validated instead of letting the hostname be re-resolved: a
custom connection adapter that pins the IP while still sending the correct
Host header and SNI. That's real work and is deliberately not done here —
the window is narrow and only exploitable by someone who controls the
target's own DNS.
"""

import ipaddress
import socket

from django.conf import settings

from apps.common.validators import is_denied_ipv4

from .types import BLOCKED_TARGET


def check_target_is_allowed(hostname: str, port: int) -> str | None:
    """None if it's safe to connect to `hostname` right now, otherwise the
    error_type the caller should record instead of making the request."""
    if settings.MONITORING_ALLOW_PRIVATE_TARGETS:
        return None

    try:
        resolved = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        # Not a security question — the request itself is about to fail
        # the same way and will be classified as a DNS error when it does.
        return None

    for family, _, _, _, sockaddr in resolved:
        if family == socket.AF_INET6:
            # IPv6 is unconditionally unsupported everywhere in the system,
            # not just at write time — nothing to compare against a
            # denylist for an address type we never let through.
            return BLOCKED_TARGET
        if is_denied_ipv4(ipaddress.ip_address(sockaddr[0])):
            return BLOCKED_TARGET

    return None
