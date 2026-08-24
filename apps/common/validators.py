"""
SSRF guard, first layer.

Monitors let a user tell the system to make an HTTP request to an address
of their choosing, from inside the same network as the database and cache.
Without a guard, a "monitor" is just a way to probe internal infrastructure
by proxy — hit an internal admin panel, a cloud metadata endpoint, or the
database's own port, and read the response time / status code back out.

This function runs at *write time*: whenever a Monitor's `url` is created or
changed. It's wired in as a plain Django field validator on `Monitor.url`
(see apps/monitors/models.py), which means Django hands it to three places
for free — the model's own full_clean(), any DRF ModelSerializer built from
that model (it derives field validators from the model automatically), and
the Django Admin form. One function, three enforcement points, nothing to
keep in sync by hand.

What it can't do: protect against DNS rebinding. A hostname can resolve to
a public IP right now and a private one a second later, after this check
has already passed and been saved. So this is a write-time nicety that
gives the user an immediate, readable 400 — it is not the actual security
boundary. The real boundary is a second check that re-resolves the hostname
and re-runs the same IP-range test immediately before every outbound probe,
right before the request is made (integrations/http_probe). That second
check is mandatory and cannot be skipped by anything that got past this one.
`is_denied_ipv4` below is exported specifically so both checks share one
table of denied ranges instead of two copies that could drift apart.
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

# Networks a monitor is never allowed to target, even with
# MONITORING_ALLOW_PRIVATE_TARGETS off (its default everywhere except
# local/test settings). Spelled out explicitly — rather than relying on
# ipaddress's own is_private, whose exact coverage has shifted across
# Python versions — so the policy is one flat, auditable list instead of
# "whatever the standard library currently considers private".
DENIED_IPV4_NETWORKS = [
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


def is_denied_ipv4(address: ipaddress.IPv4Address) -> bool:
    """True if `address` falls in a network monitors may never target.

    Public on purpose: the outbound HTTP probe re-resolves the hostname and
    calls this same function on every resolved address right before it
    connects — that second call is the actual security boundary, this
    write-time validator is just the friendly early warning.
    """
    return any(address in network for network in DENIED_IPV4_NETWORKS)


def validate_monitor_url(url: str) -> None:
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

    # This flag exists purely so the test suite (and only the test suite —
    # production settings refuse to start with it on) can point monitors at
    # a local mock server without fighting the SSRF policy.
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
    # what it resolves to until request time — that's the second check's job.
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return  # a domain name — nothing more to check at write time

    if isinstance(address, ipaddress.IPv6Address):
        # IPv6 support (and the private-range table it would need) is out
        # of scope for now. Rejecting every IPv6 literal outright is
        # simpler and strictly safer than a half-implemented range check,
        # and — unlike the IPv4 policy — it isn't gated by
        # MONITORING_ALLOW_PRIVATE_TARGETS, since it's a "not built yet"
        # limitation rather than a policy choice.
        raise ValidationError("IPv6 literal addresses are not supported.")

    if not allow_private and is_denied_ipv4(address):
        raise ValidationError(f"IP address {address} is in a private or reserved range.")
