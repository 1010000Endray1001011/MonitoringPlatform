"""
SSRF guard, echelon 1 (ARCHITECTURE.md §12.3 / ADR-011).

This validator runs at *write time* — whenever a Monitor's `url` is created
or changed (it's wired in as a Django model field validator, see
apps/monitors/models.py). It gives the user an immediate, understandable
400 for the obvious cases: wrong scheme, banned hostname, or a raw IP that
already points at a private/reserved network.

It does NOT protect against DNS rebinding: a hostname can resolve to a
public IP today and a private one tomorrow. That's why a *second*, mandatory
check re-resolves the hostname immediately before every HTTP probe
(integrations/http_probe, landing in Chunk 3). Echelon 1 is a UX nicety;
echelon 2 is the actual security boundary. Both must exist — see ADR-011 in
docs/DECISIONS.md for why one alone isn't enough.
"""

import ipaddress
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError

ALLOWED_SCHEMES = {"http", "https"}

# Hostnames/suffixes that are obviously not "the public internet", even
# though they aren't literal IPs and so can't be caught by the IP-range
# check below. Suffix entries start with "." and match any subdomain too.
BLOCKED_HOSTNAMES = {"localhost", "metadata.google.internal"}
BLOCKED_HOSTNAME_SUFFIXES = (".localhost", ".local", ".internal")

# Networks a monitor is never allowed to target, even if MONITORING_ALLOW_PRIVATE_TARGETS
# is off by default in every environment except local/test (see settings/base.py).
# Spelled out explicitly (rather than relying on ipaddress.is_private, whose
# exact coverage has changed across Python versions) so the policy is easy
# to read, test, and audit line by line.
_DENIED_IPV4_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),  # "this network" / unspecified
    ipaddress.ip_network("10.0.0.0/8"),  # RFC1918 private
    ipaddress.ip_network("100.64.0.0/10"),  # carrier-grade NAT (RFC6598)
    ipaddress.ip_network("127.0.0.0/8"),  # loopback
    ipaddress.ip_network("169.254.0.0/16"),  # link-local, includes cloud metadata .254.169
    ipaddress.ip_network("172.16.0.0/12"),  # RFC1918 private
    ipaddress.ip_network("192.168.0.0/16"),  # RFC1918 private
    ipaddress.ip_network("224.0.0.0/4"),  # multicast
    ipaddress.ip_network("240.0.0.0/4"),  # reserved
    ipaddress.ip_network("255.255.255.255/32"),  # broadcast
]


def _is_denied_ipv4(address: ipaddress.IPv4Address) -> bool:
    return any(address in network for network in _DENIED_IPV4_NETWORKS)


def validate_monitor_url(url: str) -> None:
    """Raise ValidationError if `url` fails the SSRF write-time policy.

    Used as a Django validator, so it's picked up automatically by:
    - the Monitor model field (full_clean / .save() via services),
    - the DRF ModelSerializer (auto-derives field validators from the model),
    - the Django Admin form (ModelForm does the same thing).
    One function, three surfaces — no duplicated rules to keep in sync.
    """
    parts = urlsplit(url)

    if parts.scheme not in ALLOWED_SCHEMES:
        raise ValidationError(
            f"Unsupported URL scheme '{parts.scheme}'. Only http and https are allowed."
        )

    # A URL like http://user:pass@host is a classic way to smuggle a
    # different-looking string past naive parsers; we simply don't allow it.
    if parts.username or parts.password:
        raise ValidationError("Credentials in the URL (user:pass@host) are not allowed.")

    hostname = parts.hostname
    if not hostname:
        raise ValidationError("URL must include a hostname.")
    hostname = hostname.lower()

    # `settings.MONITORING_ALLOW_PRIVATE_TARGETS` exists purely so the test
    # suite (and only the test suite — see settings/test.py) can point
    # monitors at a local mock server. It must never be True in production
    # (settings/production.py raises at startup if it is).
    allow_private = settings.MONITORING_ALLOW_PRIVATE_TARGETS

    if not allow_private:
        if hostname in BLOCKED_HOSTNAMES or hostname.endswith(BLOCKED_HOSTNAME_SUFFIXES):
            raise ValidationError(f"Hostname '{hostname}' is not allowed.")

    port = parts.port
    if port is not None and port not in settings.MONITORING_ALLOWED_PORTS:
        raise ValidationError(
            f"Port {port} is not allowed. Allowed ports: {settings.MONITORING_ALLOWED_PORTS}."
        )

    # If the hostname is a literal IP (not a domain name), we can check it
    # against the denylist right now. If it's a domain name, we can't know
    # what it resolves to until request time — that's echelon 2's job.
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return  # a domain name — nothing more to check at write time

    if isinstance(address, ipaddress.IPv6Address):
        # IPv6 support (and its own private-range checks) is out of scope
        # for the MVP — see ARCHITECTURE.md §12.3. Rejecting all IPv6
        # literals is simpler and strictly safer than a half-implemented
        # check, and it's not gated by MONITORING_ALLOW_PRIVATE_TARGETS.
        raise ValidationError("IPv6 literal addresses are not supported.")

    if not allow_private and _is_denied_ipv4(address):
        raise ValidationError(f"IP address {address} is in a private or reserved range.")
