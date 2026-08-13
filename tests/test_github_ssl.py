import ssl
import urllib.error
from taskmanager.infrastructure.github_http import (
    CERT_ERROR_MESSAGE,
    github_network_error_message,
    github_ssl_context,
    github_urlopen,
    is_certificate_error,
    wrap_github_url_error,
)
from taskmanager.services.update_service import UpdateError, UpdateService


def test_github_ssl_context_verifies():
    ctx = github_ssl_context()
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True


def test_github_urlopen_passes_ssl_context(monkeypatch):
    captured: dict = {}

    class FakeResp:
        def read(self):
            return b"{}"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        headers = {}

    def fake_urlopen(request, timeout=None, context=None):
        captured["context"] = context
        captured["timeout"] = timeout
        return FakeResp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    req = __import__("urllib.request", fromlist=["Request"]).Request("https://example.com")
    github_urlopen(req, timeout=12)
    assert captured["context"] is not None
    assert captured["context"].verify_mode == ssl.CERT_REQUIRED
    assert captured["timeout"] == 12


def test_update_service_urlopen_gets_ssl_context(monkeypatch):
    captured: dict = {}

    class FakeResp:
        def read(self):
            return (
                b'{"tag_name":"v1.0.0","assets":[{"name":"TaskManager",'
                b'"browser_download_url":"https://example.com/x","size":1}]}'
            )

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(request, timeout=None, context=None):
        captured["context"] = context
        return FakeResp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    release = UpdateService().fetch_latest_release()
    assert release.tag == "v1.0.0"
    assert captured["context"] is not None
    assert captured["context"].verify_mode == ssl.CERT_REQUIRED


def test_certificate_error_is_not_network_message():
    exc = ssl.SSLCertVerificationError("CERTIFICATE_VERIFY_FAILED")
    wrapped = urllib.error.URLError(exc)
    assert is_certificate_error(wrapped)
    assert github_network_error_message(wrapped) == CERT_ERROR_MESSAGE
    assert "сертификат" in wrap_github_url_error(wrapped).lower()
    assert "нет сети" not in wrap_github_url_error(wrapped).lower()


def test_update_service_maps_cert_error(monkeypatch):
    def boom(request, timeout=None, context=None):
        raise urllib.error.URLError(ssl.SSLCertVerificationError("CERTIFICATE_VERIFY_FAILED"))

    monkeypatch.setattr("urllib.request.urlopen", boom)
    try:
        UpdateService().fetch_latest_release()
    except UpdateError as exc:
        assert "сертификат" in str(exc).lower()
        assert "нет сети" not in str(exc).lower()
    else:
        raise AssertionError("expected UpdateError")
