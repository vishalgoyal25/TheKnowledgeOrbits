"""
engines/data_factory/tests/test_fetcher.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Act 0, phase 0.3 -- Contract 1 at the point bytes enter the system.
Spec: 00_MASTER_RECAP.md 16.6.3, 7.5a (the status IS the diagnosis).

⚠️ REWRITTEN 2026-10-06. The fetcher used to decode and normalise; it now
returns BYTES and a codec name, and the parser owns extraction. The tests that
asserted `result.text`, UNDECODABLE and CORRUPTED moved with that behaviour to
test_parser.py. What triggered the change is pinned below as
`test_pdf_bytes_are_fetched_not_rejected`.

⚠️ NO NETWORK. Every test patches `requests.get`. A test that reaches a real
government site is slow, flaky, and fails in CI for reasons unrelated to the
code.

⚠️ `unittest.mock` (stdlib) rather than pytest-mock or responses: neither is in
requirements/dev.txt, and adding a library for test convenience fails step 2 of
CLAUDE.md 4.1.

What each group pins:
  🔴 the trap   requests defaults text/* with no charset to ISO-8859-1, and
                that default silently mangles every UTF-8 Indian source
  resolution    declared charset -> sniff the bytes -> UTF-8 floor
  🔴 binary     PDFs carry NO text codec. A fetcher that decoded everything
                rejected all three PDF sources in the Act 0 set
  non-200       the body is NEVER read, because a 403 error page parsed as
                content hid an IP block for weeks (7.5a)
  fail-safe     nothing raises; 19 sources means 19 independent outcomes (8.4)
  hashing       the hash covers RAW BYTES, so a normaliser bump does not
                invalidate the whole archive
"""

import hashlib
from unittest.mock import patch

import pytest
import requests
from requests.utils import get_encoding_from_headers

from engines.data_factory.services.fetcher import (
    NO_ENCODING,
    FetchFailure,
    fetch_document,
    looks_binary,
    resolve_encoding,
)

GET = "engines.data_factory.services.fetcher.requests.get"

# A realistic bilingual government paragraph. Deliberately long: charset
# detection over 20 bytes is a coin flip, over a paragraph it is reliable, and
# real PIB pages are paragraphs.
HINDI_BODY = (
    "भारत ने संयुक्त राष्ट्र जलवायु परिवर्तन फ्रेमवर्क कन्वेंशन को अपनी चौथी द्विवार्षिक "
    "अद्यतन रिपोर्ट (BUR-4) दिसंबर 2024 में प्रस्तुत की। रिपोर्ट में वर्ष 2019 की तुलना "
    "में 2020 में ग्रीनहाउस गैस उत्सर्जन में लगभग 8% की कमी दर्ज की गई।"
)
HINDI_BYTES = HINDI_BODY.encode("utf-8")

ENGLISH_BODY = (
    "India submitted its Fourth Biennial Update Report (BUR-4) to the UNFCCC "
    "in December 2024. The report recorded a decrease of around 8% in GHG "
    "emissions in 2020 over 2019, excluding LULUCF."
)

# 🔴 The exact shape that broke the first implementation: PDF magic bytes
# followed by binary that is NOT valid UTF-8. A strict decode of this raises.
PDF_BYTES = b"%PDF-1.7\n1 0 obj\n<<>>\nstream\n\xff\xfe\x00\xd0binary\nendstream"


class _EncodingStub:
    """The two attributes `resolve_encoding` actually reads.

    Smaller and clearer than a MagicMock: if the function ever starts reading a
    third attribute, this stub fails loudly instead of silently handing back
    another mock.
    """

    def __init__(self, encoding, apparent_encoding):
        self.encoding = encoding
        self.apparent_encoding = apparent_encoding


def make_response(
    body: bytes,
    *,
    status: int = 200,
    content_type: str | None = "text/html",
) -> requests.Response:
    """A real `requests.Response`, not a mock.

    🔴 Built with the real `get_encoding_from_headers`, which is the function
    requests itself uses to populate `.encoding`. That makes these tests
    exercise the ACTUAL library behaviour rather than my belief about it -- the
    whole module exists because of what that function returns.
    """
    response = requests.Response()
    response.status_code = status
    response._content = body
    if content_type is not None:
        response.headers["Content-Type"] = content_type
    response.encoding = get_encoding_from_headers(response.headers)
    return response


# ── 🔴 The trap is real: proved against the library, not assumed ────────────


def test_requests_really_does_default_to_iso_8859_1():
    """The premise this entire module rests on, verified rather than believed.

    If a future requests release changes this, the module's reason for existing
    changes with it -- and this test is how we would find out, instead of
    discovering it through mangled citations.
    """
    headers = requests.structures.CaseInsensitiveDict({"Content-Type": "text/html"})

    assert get_encoding_from_headers(headers) == "ISO-8859-1"


def test_utf8_hindi_decoded_as_iso_8859_1_is_mangled():
    """Why the default is dangerous, shown rather than asserted abstractly.

    This is precisely what reached the database before the CA scraper fix: text
    that looks like garbage, with no exception raised anywhere.
    """
    mangled = HINDI_BYTES.decode("ISO-8859-1")

    assert mangled != HINDI_BODY
    assert "भारत" not in mangled


# ── Encoding resolution ────────────────────────────────────────────────────


def test_declared_charset_is_honoured():
    """If the server stated a charset, it knows what it sent."""
    stub = _EncodingStub(encoding="utf-8", apparent_encoding="windows-1252")

    assert resolve_encoding(stub) == "utf-8"


@pytest.mark.parametrize("rfc_default", ["ISO-8859-1", "iso-8859-1", "latin-1"])
def test_the_rfc_default_is_distrusted_and_the_bytes_are_sniffed(rfc_default):
    """🔴 The core decision.

    ISO-8859-1 here does not mean "the server said latin-1" -- it means "the
    server said NOTHING and requests filled in a 1990s European default". So it
    is a signal to look at the bytes, never a value to trust.
    """
    stub = _EncodingStub(encoding=rfc_default, apparent_encoding="utf-8")

    assert resolve_encoding(stub) == "utf-8"


def test_missing_encoding_falls_through_to_sniffing():
    stub = _EncodingStub(encoding=None, apparent_encoding="utf-8")

    assert resolve_encoding(stub) == "utf-8"


def test_utf8_is_the_floor_when_sniffing_yields_nothing():
    """Detection returns None on short or ambiguous bodies. UTF-8 is right far
    more often than anything else for Indian government sources.
    """
    stub = _EncodingStub(encoding=None, apparent_encoding=None)

    assert resolve_encoding(stub) == "utf-8"


def test_hindi_served_without_a_charset_resolves_to_a_codec_that_works():
    """🔴 END TO END, and the single reason this module exists.

    A PIB page serving UTF-8 Hindi as `text/html` with no charset. requests
    sets ISO-8859-1; resolving explicitly recovers the real text.
    """
    response = make_response(HINDI_BYTES, content_type="text/html")

    assert response.encoding == "ISO-8859-1"  # the trap, armed

    encoding = resolve_encoding(response)
    assert HINDI_BYTES.decode(encoding) == HINDI_BODY


# ── 🔴 Binary: the bug that triggered the rewrite ───────────────────────────


def test_pdf_bytes_are_fetched_not_rejected():
    """🔴 REGRESSION. The first implementation rejected every PDF source.

    It called `raw.decode(encoding, errors="strict")` on every 200, which
    raises on binary, so all three PDFs in the Act 0 set -- the UN peacekeeping
    list, the Lok Sabha committee page and the BPR&D SOP -- came back as
    UNDECODABLE. The tests missed it because they only fed it text bodies.
    """
    # Prove the body really is undecodable, so this test cannot pass vacuously.
    with pytest.raises(UnicodeDecodeError):
        PDF_BYTES.decode("utf-8", errors="strict")

    response = make_response(PDF_BYTES, content_type="application/pdf")

    with patch(GET, return_value=response):
        result = fetch_document("https://peacekeeping.un.org/list.pdf")

    assert result.ok
    assert result.raw_bytes == PDF_BYTES
    assert result.is_binary
    assert result.encoding_used == NO_ENCODING


def test_a_pdf_mislabelled_as_html_is_still_recognised_as_binary():
    """Magic bytes beat the header. Government hosts mislabel PDFs routinely,
    and the body cannot lie about what it is.
    """
    response = make_response(PDF_BYTES, content_type="text/html")

    with patch(GET, return_value=response):
        result = fetch_document("https://bprd.nic.in/sop.pdf")

    assert result.ok
    assert result.is_binary


@pytest.mark.parametrize(
    ("body", "content_type", "binary"),
    [
        (PDF_BYTES, "application/pdf", True),
        (PDF_BYTES, "text/html", True),  # magic beats a wrong header
        (b"plain", "application/octet-stream", True),  # header, no magic
        (b"<html></html>", "text/html", False),
        (b"plain text", "text/plain", False),
        (b"", "text/html", False),  # empty is not binary
    ],
)
def test_looks_binary(body, content_type, binary):
    assert looks_binary(body, content_type) is binary


def test_encoding_is_not_sniffed_for_binary_bodies():
    """Sniffing a PDF is meaningless AND slow -- `apparent_encoding` runs
    charset detection over the whole body, which on a 40 MB report is pure
    waste. Asserting the property was never touched is how we know it is
    skipped rather than merely ignored.
    """
    response = make_response(PDF_BYTES, content_type="application/pdf")
    sniffed = []

    class _Watched(requests.Response):
        @property
        def apparent_encoding(self):
            sniffed.append(True)
            return "utf-8"

    response.__class__ = _Watched

    with patch(GET, return_value=response):
        result = fetch_document("https://peacekeeping.un.org/list.pdf")

    assert result.ok
    assert sniffed == []  # never consulted


# ── fetch_document: the happy path ─────────────────────────────────────────


def test_successful_fetch_returns_bytes_a_codec_and_a_hash():
    body = ENGLISH_BODY.encode("utf-8")
    response = make_response(body, content_type="text/html; charset=utf-8")

    with patch(GET, return_value=response):
        result = fetch_document("https://pib.gov.in/release/1")

    assert result.ok
    assert bool(result) is True
    assert result.http_status == 200
    assert result.encoding_used == "utf-8"
    assert result.raw_bytes == body
    assert result.byte_size == len(body)
    assert result.content_hash == hashlib.sha256(body).hexdigest()
    assert not result.is_binary


def test_hash_covers_raw_bytes_so_a_normaliser_bump_does_not_invalidate_the_archive():
    """🔴 A subtle decision with an expensive failure mode.

    Dedup level 1 asks "have we already fetched this exact document?". Hashing
    anything derived -- decoded or normalised text -- would mean a
    NORMALISER_VERSION bump makes every previously fetched document look new,
    and the entire archive re-downloads.

    This body carries CRLF and a non-breaking space that normalisation removes,
    so the raw hash and any text-derived hash necessarily differ.
    """
    raw = b"India submitted BUR-4.\r\nEmissions\xc2\xa0fell 8%."
    response = make_response(raw, content_type="text/html; charset=utf-8")

    with patch(GET, return_value=response):
        result = fetch_document("https://pib.gov.in/release/2")

    assert result.content_hash == hashlib.sha256(raw).hexdigest()

    from engines.data_factory.services.text_normaliser import normalise_document

    normalised = normalise_document(raw.decode("utf-8"))
    assert result.content_hash != hashlib.sha256(normalised.encode()).hexdigest()


# ── Non-200: the body is never read ────────────────────────────────────────


@pytest.mark.parametrize("status", [301, 403, 404, 429, 500, 503])
def test_non_200_is_recorded_and_the_body_discarded(status):
    """🔴 The 7.5a lesson, pinned.

    A 403 HTML error page fed to an XML parser reported itself as malformed
    XML and hid an IP block for weeks. The status IS the diagnosis, so it is
    checked BEFORE anything touches the body, and the body is discarded.
    """
    error_page = b"<html><body>Access Denied</body></html>"
    response = make_response(error_page, status=status)

    with patch(GET, return_value=response):
        result = fetch_document("https://pib.gov.in/blocked")

    assert not result.ok
    assert result.failure is FetchFailure.HTTP_ERROR
    assert result.http_status == status
    assert result.raw_bytes == b""  # never kept
    assert result.content_hash == ""  # never hashed


def test_empty_body_with_200_is_a_failure_not_an_empty_document():
    """A 200 with no body is a broken source, not a document with no content.
    Storing it would create an artifact that can never yield an atom.
    """
    response = make_response(b"", content_type="text/html; charset=utf-8")

    with patch(GET, return_value=response):
        result = fetch_document("https://pib.gov.in/empty")

    assert not result.ok
    assert result.failure is FetchFailure.EMPTY_BODY


# ── Fail-safe: nothing raises, so one bad source cannot stop a run ─────────


@pytest.mark.parametrize(
    ("exception", "expected"),
    [
        (requests.Timeout("timed out"), FetchFailure.TIMEOUT),
        (requests.ConnectionError("no route"), FetchFailure.NETWORK),
        (requests.TooManyRedirects("loop"), FetchFailure.NETWORK),
    ],
)
def test_network_failures_return_a_result_instead_of_raising(exception, expected):
    """8.4: fail-safe, never fail-stop.

    A caller looping over 19 sources must record the failure against that one
    source and continue. A raise here would lose the other 18.
    """
    with patch(GET, side_effect=exception):
        result = fetch_document("https://unreachable.invalid/x")

    assert not result.ok
    assert result.failure is expected
    assert result.detail  # the reason is preserved, not swallowed


# ── The result object itself ───────────────────────────────────────────────


def test_fetch_result_is_frozen():
    """A fetch result is evidence about one moment. If a caller could rewrite
    `encoding_used` afterwards, the stored artifact would no longer describe
    how its own bytes were read.
    """
    response = make_response(b"ok", content_type="text/html; charset=utf-8")

    with patch(GET, return_value=response):
        result = fetch_document("https://pib.gov.in/release/3")

    with pytest.raises(AttributeError):
        result.encoding_used = "windows-1252"  # type: ignore[misc]
