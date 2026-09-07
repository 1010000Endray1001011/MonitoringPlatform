"""
The second SSRF check — the one that runs immediately before every real
probe, not just when a Monitor is saved. `socket.getaddrinfo` is
monkeypatched throughout instead of relying on real DNS: it keeps these
tests fast and deterministic, and it's the only way to exercise "a hostname
that resolves to a private address" without controlling actual DNS records.
"""

import socket

from integrations.http_probe.ssrf_guard import check_target_is_allowed
from integrations.http_probe.types import BLOCKED_TARGET


def test_literal_private_ipv4_is_blocked(settings):
    settings.MONITORING_ALLOW_PRIVATE_TARGETS = False

    assert check_target_is_allowed("127.0.0.1", 80) == BLOCKED_TARGET


def test_hostname_resolving_to_a_public_address_is_allowed(settings, monkeypatch):
    settings.MONITORING_ALLOW_PRIVATE_TARGETS = False
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))],
    )

    assert check_target_is_allowed("example.com", 80) is None


def test_hostname_resolving_to_a_private_address_is_blocked(settings, monkeypatch):
    settings.MONITORING_ALLOW_PRIVATE_TARGETS = False
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 80))],
    )

    assert check_target_is_allowed("internal.example.com", 80) == BLOCKED_TARGET


def _resolves_to(*addresses):
    """getaddrinfo stand-in returning one entry per address, with the family
    inferred from the address itself so callers only list the addresses."""

    def _fake(*args, **kwargs):
        entries = []
        for address in addresses:
            if ":" in address:
                entries.append((socket.AF_INET6, socket.SOCK_STREAM, 6, "", (address, 80, 0, 0)))
            else:
                entries.append((socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 80)))
        return entries

    return _fake


def test_public_ipv6_resolution_is_allowed(settings, monkeypatch):
    # Regression: this used to be blocked purely for being IPv6, which took
    # out every host publishing an AAAA record — google.com, youtube.com,
    # example.com — without a single packet leaving the worker.
    settings.MONITORING_ALLOW_PRIVATE_TARGETS = False
    monkeypatch.setattr(socket, "getaddrinfo", _resolves_to("2606:2800:220:1::1"))

    assert check_target_is_allowed("example.com", 80) is None


def test_dual_stack_host_with_public_addresses_is_allowed(settings, monkeypatch):
    # The realistic shape of the bug: a normal public host answers with
    # both an A and an AAAA record.
    settings.MONITORING_ALLOW_PRIVATE_TARGETS = False
    monkeypatch.setattr(
        socket, "getaddrinfo", _resolves_to("142.250.130.102", "2a00:1450:4010:c07::71")
    )

    assert check_target_is_allowed("google.com", 80) is None


def test_private_ipv6_resolution_is_blocked(settings, monkeypatch):
    settings.MONITORING_ALLOW_PRIVATE_TARGETS = False
    monkeypatch.setattr(socket, "getaddrinfo", _resolves_to("fd00::1"))

    assert check_target_is_allowed("internal.example.com", 80) == BLOCKED_TARGET


def test_ipv6_loopback_resolution_is_blocked(settings, monkeypatch):
    settings.MONITORING_ALLOW_PRIVATE_TARGETS = False
    monkeypatch.setattr(socket, "getaddrinfo", _resolves_to("::1"))

    assert check_target_is_allowed("localhost6.example.com", 80) == BLOCKED_TARGET


def test_ipv4_mapped_loopback_is_blocked(settings, monkeypatch):
    # ::ffff:127.0.0.1 is loopback wearing an IPv6 costume — it has to be
    # unwrapped and judged by the IPv4 table, not waved through because it
    # misses every IPv6 range.
    settings.MONITORING_ALLOW_PRIVATE_TARGETS = False
    monkeypatch.setattr(socket, "getaddrinfo", _resolves_to("::ffff:127.0.0.1"))

    assert check_target_is_allowed("sneaky.example.com", 80) == BLOCKED_TARGET


def test_a_single_private_address_blocks_the_whole_hostname(settings, monkeypatch):
    # The OS resolver, not this guard, picks which address requests uses,
    # so a hostname is only safe when every address it offers is safe.
    settings.MONITORING_ALLOW_PRIVATE_TARGETS = False
    monkeypatch.setattr(socket, "getaddrinfo", _resolves_to("93.184.216.34", "fd00::1"))

    assert check_target_is_allowed("mixed.example.com", 80) == BLOCKED_TARGET


def test_dns_failure_is_not_treated_as_a_security_block(settings, monkeypatch):
    # A hostname that fails to resolve isn't a security concern — it's
    # about to fail the same way when the real request tries it, and gets
    # classified as a DNS error then, not as BLOCKED_TARGET here.
    settings.MONITORING_ALLOW_PRIVATE_TARGETS = False

    def _raise(*args, **kwargs):
        raise socket.gaierror("not found")

    monkeypatch.setattr(socket, "getaddrinfo", _raise)

    assert check_target_is_allowed("does-not-exist.example", 80) is None


def test_allow_private_targets_flag_skips_resolution_entirely(settings, monkeypatch):
    settings.MONITORING_ALLOW_PRIVATE_TARGETS = True

    def _fail(*args, **kwargs):
        raise AssertionError("should not resolve anything when the flag is on")

    monkeypatch.setattr(socket, "getaddrinfo", _fail)

    assert check_target_is_allowed("127.0.0.1", 80) is None
