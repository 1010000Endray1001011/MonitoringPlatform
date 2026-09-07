"""
Table-driven tests for the SSRF write-time guard.

No database needed — `validate_monitor_url` is a pure function over a
string, so these run in milliseconds and can afford to enumerate every
denied range explicitly rather than trusting a handful of spot checks.

`settings.MONITORING_ALLOW_PRIVATE_TARGETS` defaults to True in
config/settings/test.py. These tests flip it back to False via the `settings` fixture
whenever they're testing the policy the flag would otherwise switch off.
"""

import pytest
from django.core.exceptions import ValidationError

from apps.common.validators import validate_monitor_url

BLOCKED_URLS = [
    pytest.param("http://127.0.0.1/", id="loopback-ipv4"),
    pytest.param("http://localhost/", id="localhost"),
    pytest.param("http://sub.localhost/", id="localhost-subdomain"),
    pytest.param("http://10.0.0.5/", id="rfc1918-10"),
    pytest.param("http://172.16.0.1/", id="rfc1918-172-16-low"),
    pytest.param("http://172.31.255.255/", id="rfc1918-172-16-high"),
    pytest.param("http://192.168.1.1/", id="rfc1918-192-168"),
    pytest.param("http://169.254.169.254/", id="link-local-cloud-metadata"),
    pytest.param("http://100.64.0.1/", id="cgnat"),
    pytest.param("http://0.0.0.0/", id="unspecified"),
    pytest.param("http://[::1]/", id="ipv6-loopback"),
    pytest.param("http://[fc00::1]/", id="ipv6-ula"),
    pytest.param("http://[fe80::1]/", id="ipv6-link-local"),
    pytest.param("http://[::ffff:127.0.0.1]/", id="ipv6-mapped-loopback"),
    pytest.param("http://example.com:9999/", id="port-not-whitelisted"),
    pytest.param("http://user:pass@example.com/", id="userinfo-in-url"),
    pytest.param("ftp://example.com/", id="scheme-ftp"),
    pytest.param("file:///etc/passwd", id="scheme-file"),
    pytest.param("http://service.internal/", id="internal-suffix"),
    pytest.param("http://metadata.google.internal/", id="cloud-metadata-hostname"),
]

ALLOWED_URLS = [
    pytest.param("http://example.com/", id="plain-http"),
    pytest.param("https://example.com/health", id="plain-https-path"),
    pytest.param("https://api.example.com:8443/status", id="whitelisted-port"),
    pytest.param("http://93.184.216.34/", id="public-ip-literal"),
    pytest.param("http://[2606:2800:220:1::1]/", id="public-ipv6-literal"),
]


@pytest.mark.parametrize("url", BLOCKED_URLS)
def test_blocked_urls_are_rejected(settings, url):
    settings.MONITORING_ALLOW_PRIVATE_TARGETS = False
    with pytest.raises(ValidationError):
        validate_monitor_url(url)


@pytest.mark.parametrize("url", ALLOWED_URLS)
def test_allowed_urls_pass(settings, url):
    settings.MONITORING_ALLOW_PRIVATE_TARGETS = False
    validate_monitor_url(url)  # must not raise


def test_allow_private_targets_flag_lets_loopback_through(settings):
    # This is the escape hatch local/test settings use — production settings
    # refuse to start with it enabled at all (config/settings/production.py).
    settings.MONITORING_ALLOW_PRIVATE_TARGETS = True
    validate_monitor_url("http://127.0.0.1/")  # must not raise


def test_allow_private_targets_flag_lifts_the_ipv6_ban_too(settings):
    # IPv6 literals are now judged by the same private/reserved policy as
    # IPv4 ones instead of being refused outright for being IPv6, so the
    # escape hatch has to cover both families or local development over
    # ::1 would be the one thing it couldn't unblock.
    settings.MONITORING_ALLOW_PRIVATE_TARGETS = True
    validate_monitor_url("http://[::1]/")  # must not raise
