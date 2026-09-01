import ssl

from chip_tracker.sources.http import _verified_ssl_context


def test_verified_ssl_context_keeps_certificate_and_hostname_checks():
    context = _verified_ssl_context()

    assert context.verify_mode is ssl.CERT_REQUIRED
    assert context.check_hostname is True
    if hasattr(ssl, "VERIFY_X509_STRICT"):
        assert not (context.verify_flags & ssl.VERIFY_X509_STRICT)
