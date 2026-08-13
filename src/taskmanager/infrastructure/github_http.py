"""TLS for GitHub downloads: OS trust store plus certifi; verify stays on."""

from __future__ import annotations

import logging
import ssl
import urllib.error
import urllib.request
from typing import Any
from urllib.request import Request

logger = logging.getLogger(__name__)

CERT_ERROR_MESSAGE = (
    "Не удалось проверить TLS-сертификат GitHub. "
    "Проверьте системное хранилище сертификатов."
)


def github_ssl_context() -> ssl.SSLContext:
    """Browser-like context: OS roots, then certifi; verification enabled."""
    context = ssl.create_default_context()
    try:
        import certifi

        context.load_verify_locations(cafile=certifi.where())
    except Exception:
        logger.warning("certifi CA bundle unavailable; using OS trust store only")
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = True
    return context


def is_certificate_error(exc: BaseException) -> bool:
    if isinstance(exc, ssl.SSLCertVerificationError):
        return True
    reason = getattr(exc, "reason", None)
    if isinstance(reason, Exception) and is_certificate_error(reason):
        return True
    cause = exc.__cause__
    if isinstance(cause, BaseException) and cause is not exc:
        if is_certificate_error(cause):
            return True
    text = str(exc).upper()
    return "CERTIFICATE_VERIFY_FAILED" in text or "CERTIFICATE VERIFY FAILED" in text


def github_network_error_message(exc: BaseException) -> str:
    if is_certificate_error(exc):
        return CERT_ERROR_MESSAGE
    return f"Нет сети или GitHub недоступен: {exc}"


def github_urlopen(request: Request, *, timeout: float) -> Any:
    return urllib.request.urlopen(
        request, timeout=timeout, context=github_ssl_context()
    )


def wrap_github_url_error(exc: urllib.error.URLError, *, download: bool = False) -> str:
    if is_certificate_error(exc):
        return CERT_ERROR_MESSAGE
    if download:
        return f"Не удалось скачать файл: {exc}"
    return github_network_error_message(exc)
