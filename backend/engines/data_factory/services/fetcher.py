"""Fetch a document and decide, explicitly, what codec its bytes are in.

Act 0, phase 0.3. Contract 1: resolve the encoding FIRST, never let a parser
guess. Spec: 00_MASTER_RECAP.md 16.6.3, 7.5a (the status IS the diagnosis).

    fetch -> resolve encoding EXPLICITLY -> hash the RAW BYTES
          -> hand bytes + codec to the parser

🔴 This module returns BYTES, never text.
--------------------------------------------
It deliberately does not decode and does not normalise, for two reasons found
while writing the parser:

1. **PDFs are binary.** A strict decode of PDF bytes raises, so a fetcher that
   decoded everything would reject every PDF source -- which is three of the
   nineteen in the Act 0 set, including the UN peacekeeping list.
2. **For HTML, decoded bytes are MARKUP, not document text.** Normalising
   markup and then extracting from it yields final text that was never
   normalised as a unit, which violates 16.6.3: the stored
   ``df_chunk.normalised_text`` must be exactly what the normaliser produced.

So the boundary is: this module owns the NETWORK and the CODEC DECISION; the
parser owns extraction and runs normalisation last, at the one point where the
text is final. The U+FFFD corruption check lives with the parser for the same
reason -- it needs text, and only the parser has it.

Why the codec decision is the hard part
----------------------------------------
``requests`` follows RFC 2616 and defaults ``response.encoding`` to ISO-8859-1
for any ``text/*`` response whose Content-Type omits a charset. Indian
government and news sites are UTF-8 and routinely omit it, so the default
mangles curly quotes, em dashes, rupee signs and every diacritic in a
transliterated name -- silently, before anything else runs.

For the Factory that is not cosmetic. Corrupted bytes mean corrupted chunk
text, which means ``char_span`` offsets pointing at garbage, which means a
citation that cannot be traced to its evidence. That single rule is the
product (00_MASTER_RECAP.md 8.1).

Precedent: the shipped fix in ``current_affairs.services.rss_scraper``
(2026-10-02), which diagnosed this after BeautifulSoup's UnicodeDammit emitted
replacement characters on every article. The approach is reused; the module is
not imported, because the Factory must not depend on a shipped engine's
internals.

Fail-safe, never fail-stop (8.4)
---------------------------------
Nothing here raises on a bad fetch. Every failure returns a ``FetchResult``
with ``ok=False`` and a reason, so a caller looping over 19 sources records the
failure against that one source and keeps going. A blocked publisher must never
take a run down.
"""

import hashlib
from dataclasses import dataclass
from enum import Enum

import requests
import structlog

logger = structlog.get_logger(__name__)

# Same shape as the shipped scraper's. Several government hosts return 403 to
# an obvious bot UA, and a 403 HTML body parsed as XML once reported itself as
# malformed XML and hid the real cause for weeks (00_MASTER_RECAP.md 7.5a).
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "application/pdf;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

DEFAULT_TIMEOUT_SECONDS = 20

# Encodings `requests` falls back to when no charset is declared. Seeing one of
# these means "nothing was declared", not "the server said latin-1", so it is a
# signal to sniff rather than a value to trust.
_UNTRUSTED_DEFAULTS = frozenset({"iso-8859-1", "latin-1", "latin1"})

# Last resort when neither the header nor sniffing yields anything. Correct for
# the overwhelming majority of Indian government sources.
_FALLBACK_ENCODING = "utf-8"

# Binary formats have no text encoding, and sniffing one is both meaningless
# and slow -- `apparent_encoding` runs charset detection over the whole body,
# which on a 40 MB report PDF is pure waste. Magic bytes are checked as well as
# the header because several government hosts serve PDFs as
# application/octet-stream, and at least one as text/html.
_PDF_MAGIC = b"%PDF-"
_BINARY_CONTENT_HINTS = ("application/pdf", "application/octet-stream")

# Not applicable, recorded explicitly rather than left blank by accident.
NO_ENCODING = ""


class FetchFailure(str, Enum):
    """Why a fetch produced nothing usable. Values are stored and logged."""

    NETWORK = "network"
    TIMEOUT = "timeout"
    HTTP_ERROR = "http_error"
    EMPTY_BODY = "empty_body"


@dataclass(frozen=True)
class FetchResult:
    """Everything the artifact row needs, plus why it failed if it did.

    Frozen because a fetch result is evidence about one moment: if the caller
    could mutate ``encoding_used`` after the fact, the stored artifact would no
    longer describe how its own bytes were read.
    """

    url: str
    ok: bool
    failure: FetchFailure | None = None
    detail: str = ""
    http_status: int | None = None
    declared_content_type: str = ""
    encoding_used: str = NO_ENCODING
    raw_bytes: bytes = b""
    content_hash: str = ""
    byte_size: int = 0

    def __bool__(self) -> bool:
        return self.ok

    @property
    def is_binary(self) -> bool:
        """Whether this was fetched as bytes with no text codec.

        True for PDFs. The parser uses it to skip decoding entirely rather
        than attempting one and handling the failure.
        """
        return self.encoding_used == NO_ENCODING


def looks_binary(raw_bytes: bytes, content_type: str = "") -> bool:
    """Whether these bytes have no meaningful text encoding.

    Magic bytes beat the header: the body cannot lie about what it is, and
    government hosts mislabel PDFs routinely.
    """
    if raw_bytes[:5] == _PDF_MAGIC:
        return True
    lowered = content_type.lower()
    return any(hint in lowered for hint in _BINARY_CONTENT_HINTS)


def resolve_encoding(response: requests.Response) -> str:
    """Decide explicitly which codec decodes this body. Never guess implicitly.

    Order, and why:

    1. **A declared charset wins.** If the server stated one, honour it -- it
       knows what it sent. Trust is withdrawn only for the RFC default below.
    2. **Sniff when nothing was declared.** ``apparent_encoding`` runs charset
       detection over the actual bytes, which is strictly better than assuming
       a 1990s European default for an Indian government page.
    3. **UTF-8 as the floor.** Detection returns None on short or ambiguous
       bodies; UTF-8 is right far more often than anything else here.

    Returns the codec name actually used, which the caller MUST store on the
    artifact. Without it, a re-parse from the archive cannot reproduce the same
    characters, and every offset computed against the original text is void.
    """
    declared = (response.encoding or "").strip()

    if declared and declared.lower() not in _UNTRUSTED_DEFAULTS:
        return declared

    # Either nothing was declared, or `requests` supplied its RFC 2616 default.
    # Both mean "the server told us nothing", so look at the bytes.
    sniffed = response.apparent_encoding
    if sniffed:
        return sniffed

    return _FALLBACK_ENCODING


def fetch_document(url: str, *, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> FetchResult:
    """Fetch one document. Returns raw bytes and the codec to read them with.

    Keyword-only timeout so a positional argument can never be mistaken for it.

    🔴 A non-200 body is NEVER read. The shipped CA scraper learned this the
    hard way: a 403 HTML error page fed to an XML parser reported itself as
    malformed XML, and the real cause -- an IP block -- stayed hidden for weeks
    (7.5a). The status IS the diagnosis.

    Args:
        url: the exact URL to fetch, stored as ``source_url``.
        timeout: seconds before giving up, applied to connect and read.

    Returns:
        A ``FetchResult``. Check ``ok`` before using anything else; this
        function does not raise on a bad fetch. Pass ``raw_bytes`` and
        ``encoding_used`` to ``parser.parse_document`` to obtain text.
    """
    try:
        response = requests.get(url, headers=BROWSER_HEADERS, timeout=timeout)
    except requests.Timeout as exc:
        logger.warning("df_fetch_timeout", url=url, timeout=timeout)
        return FetchResult(
            url=url, ok=False, failure=FetchFailure.TIMEOUT, detail=str(exc)
        )
    except requests.RequestException as exc:
        logger.warning("df_fetch_network_error", url=url, error=str(exc))
        return FetchResult(
            url=url, ok=False, failure=FetchFailure.NETWORK, detail=str(exc)
        )

    status = response.status_code
    declared_type = response.headers.get("Content-Type", "")

    if status != 200:
        # Deliberately before anything touches the body. Recording the real
        # status is what makes "blocked" distinguishable from "malformed".
        logger.warning("df_fetch_http_error", url=url, status=status)
        return FetchResult(
            url=url,
            ok=False,
            failure=FetchFailure.HTTP_ERROR,
            detail=f"HTTP {status}",
            http_status=status,
            declared_content_type=declared_type,
        )

    raw = response.content
    if not raw:
        logger.warning("df_fetch_empty_body", url=url)
        return FetchResult(
            url=url,
            ok=False,
            failure=FetchFailure.EMPTY_BODY,
            detail="200 with an empty body",
            http_status=status,
            declared_content_type=declared_type,
        )

    # Binary bodies get no codec at all, rather than a meaningless one. Sniffing
    # a PDF would waste detection over the whole file and record a codec nobody
    # should ever decode it with.
    encoding = (
        NO_ENCODING if looks_binary(raw, declared_type) else resolve_encoding(response)
    )

    # Hash the RAW BYTES, not any derived text. Dedup level 1 asks "did we
    # already fetch this exact document?", and that must stay true across a
    # normaliser version bump -- otherwise changing a whitespace rule would
    # make every previously fetched document look new.
    content_hash = hashlib.sha256(raw).hexdigest()

    logger.info(
        "df_fetch_ok",
        url=url,
        encoding=encoding or "binary",
        byte_size=len(raw),
        status=status,
    )

    return FetchResult(
        url=url,
        ok=True,
        http_status=status,
        declared_content_type=declared_type,
        encoding_used=encoding,
        raw_bytes=raw,
        content_hash=content_hash,
        byte_size=len(raw),
    )
