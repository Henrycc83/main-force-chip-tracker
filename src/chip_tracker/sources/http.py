from __future__ import annotations

import json
import ssl
import time
from http.client import IncompleteRead
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from chip_tracker.sources.base import SourceError


USER_AGENT = "main-force-chip-tracker/0.1 (+GitHub Actions)"


def _verified_ssl_context() -> ssl.SSLContext:
    """Keep CA and hostname verification while tolerating legacy issuer metadata.

    Some official Taiwan market endpoints currently omit Subject Key Identifier
    metadata that OpenSSL's optional X509_STRICT mode requires.  Python 3.14 on
    Windows enables that extra flag by default.  Clearing only X509_STRICT keeps
    CERT_REQUIRED and hostname checks intact.
    """
    context = ssl.create_default_context()
    if hasattr(ssl, "VERIFY_X509_STRICT"):
        context.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return context


def fetch_bytes(url: str, *, attempts: int = 3, timeout: int = 20) -> bytes:
    error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
            with urlopen(request, timeout=timeout, context=_verified_ssl_context()) as response:
                payload = response.read()
                if not payload:
                    raise SourceError(f"empty response from {url}")
                return payload
        except (HTTPError, URLError, TimeoutError, IncompleteRead, ConnectionError, SourceError) as exc:
            error = exc
            if attempt + 1 < attempts:
                time.sleep(2**attempt)
    raise SourceError(f"failed to fetch {url}: {error}")


def fetch_json(url: str):
    try:
        return json.loads(fetch_bytes(url).decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceError(f"invalid JSON from {url}: {exc}") from exc
