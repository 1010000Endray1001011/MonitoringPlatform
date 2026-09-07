"""
The second, mandatory half of the SSRF guard.

`apps.common.validators.validate_monitor_url` only runs when a Monitor is
created or edited — it has no way to know what a hostname will resolve to
by the time a check actually runs, possibly months later. This module
re-resolves the hostname and re-checks every address it comes back with,
right before the outbound request, using the exact same denylist
(`apps.common.validators.is_denied_ip`) so the two checks can never drift
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

from apps.common.validators import is_denied_ip

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

    # Every address, not just the first: the OS resolver decides which one
    # `requests` actually connects to, and that choice is not visible from
    # here. A hostname is therefore only safe if *all* of its addresses are
    # safe — one denied entry anywhere in the list is enough to refuse.
    #
    # Both families go through the same is_denied_ip. An earlier version
    # short-circuited on AF_INET6 and refused the host outright, which
    # blocked every target that merely publishes an AAAA record alongside
    # its A record — i.e. most of the public internet, and the reason
    # monitoring google.com came back BLOCKED_TARGET without a single
    # packet being sent.
    for _, _, _, _, sockaddr in resolved:
        # sockaddr[0] can carry a zone id for link-local IPv6
        # ("fe80::1%eth0"); ip_address parses that form directly.
        if is_denied_ip(ipaddress.ip_address(sockaddr[0])):
            return BLOCKED_TARGET

    return None
