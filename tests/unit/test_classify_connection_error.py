import socket

from integrations.http_probe.requests_probe import _classify_connection_error
from integrations.http_probe.types import CONNECTION_ERROR, CONNECTION_REFUSED, DNS_ERROR


def test_classifies_gaierror_as_dns_error():
    assert (
        _classify_connection_error(socket.gaierror("nodename nor servname provided")) == DNS_ERROR
    )


def test_classifies_connection_refused_error():
    assert _classify_connection_error(ConnectionRefusedError("refused")) == CONNECTION_REFUSED


def test_walks_the_exception_chain_to_find_the_real_cause():
    # requests/urllib3 wrap the actual failure several layers deep instead
    # of raising it directly — this is what that looks like from the
    # outside: the exception `_classify_connection_error` actually sees has
    # a __cause__, not the gaierror itself.
    wrapped = Exception("outer wrapper raised by some intermediate layer")
    wrapped.__cause__ = socket.gaierror("dns failed")

    assert _classify_connection_error(wrapped) == DNS_ERROR


def test_falls_back_to_connection_error_for_anything_unrecognised():
    assert _classify_connection_error(ValueError("some other failure")) == CONNECTION_ERROR
