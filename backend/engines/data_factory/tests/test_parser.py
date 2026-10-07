"""
engines/data_factory/tests/test_parser.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Act 0, phase 0.3 -- bytes to the text a claim is located in.
Spec: 00_MASTER_RECAP.md 16.6.3, 2.7 (layout-aware parsing).

🔴 This module owns the LAST transformation before offsets exist, so what it
returns IS `df_chunk.normalised_text`, and every char_start in the system is an
index into it. Hence the group that matters most is not extraction quality --
it is that output is always canonical.

⚠️ PDF tests mock `pdfplumber.open`. That is deliberate: a hand-built PDF
fixture tests pdfminer's recovery from a broken xref table, not our logic, and
a correct one is ~500 bytes of byte-offset bookkeeping that breaks whenever it
is edited. These pin OUR behaviour -- dispatch, page joining, offset recording,
scanned-page detection, failure isolation.
🔴 Real PDFs are verified when 0.3 runs against the three actual Act 0 sources
(UN peacekeeping, Lok Sabha committee, BPR&D), which is a stronger test than
any fixture because they are the documents we will cite.

What each group pins:
  dispatch      magic bytes beat the header; HTML is sniffed when unlabelled
  🔴 chrome     navigation is not evidence -- a citation resolving to
                "Skip to main content" is worse than no citation
  selectors     per-source config beats convention, and a bad one cannot crash
  separators    block boundaries survive, so adjacent cells never fuse into a
                word that never existed
  pdf           pages joined, offsets recorded, scanned files reported
  🔴 canonical  every ok result is already normalised
  refusal       corrupted and undecodable input is rejected, not repaired
"""

from unittest.mock import patch

import pytest

from engines.data_factory.services.parser import (
    ParseFailure,
    looks_like_pdf,
    parse_document,
)
from engines.data_factory.services.text_normaliser import is_normalised

PDFPLUMBER_OPEN = "engines.data_factory.services.parser.pdfplumber.open"

PDF_HEADER = b"%PDF-1.7\n"

# Long enough to clear _MIN_CONTENT_CHARS (200), as a real release is.
ARTICLE = (
    "India submitted its Fourth Biennial Update Report (BUR-4) to the UNFCCC "
    "in December 2024. The report recorded a decrease of around 8% in GHG "
    "emissions in 2020 over 2019, excluding LULUCF. Energy remained the "
    "largest contributor to the national inventory, followed by agriculture "
    "and industrial processes."
)

PIB_PAGE = f"""<!DOCTYPE html>
<html>
<head>
  <title>Press Information Bureau</title>
  <style>body {{ margin: 0 }}</style>
  <script>var analytics = true;</script>
</head>
<body>
  <nav>Skip to main content | Home | Ministries | Language</nav>
  <header>Government of India</header>
  <main><h1>India submits BUR-4</h1><p>{ARTICLE}</p></main>
  <aside>Related releases</aside>
  <footer>Copyright Press Information Bureau</footer>
</body>
</html>"""


class _FakePage:
    def __init__(self, text: str | None):
        self._text = text

    def extract_text(self) -> str | None:
        return self._text


class _FakePdf:
    def __init__(self, pages):
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def fake_pdf(*page_texts):
    return _FakePdf([_FakePage(t) for t in page_texts])


# ── Dispatch ───────────────────────────────────────────────────────────────


def test_looks_like_pdf_reads_the_magic_bytes():
    assert looks_like_pdf(b"%PDF-1.4 whatever")
    assert not looks_like_pdf(b"<html>")
    assert not looks_like_pdf(b"")


def test_pdf_magic_beats_a_wrong_content_type():
    """Government hosts mislabel PDFs routinely. The body cannot lie."""
    with patch(PDFPLUMBER_OPEN, return_value=fake_pdf(ARTICLE)):
        result = parse_document(PDF_HEADER + b"body", content_type="text/html")

    assert result.ok
    assert result.extracted_via == "pdf_text_layer"


def test_html_is_detected_even_without_a_content_type():
    result = parse_document(PIB_PAGE.encode("utf-8"), content_type="")

    assert result.ok
    assert "BUR-4" in result.text


def test_plain_text_passes_through_normalised():
    result = parse_document(b"Just  text.\r\nSecond line.", content_type="text/plain")

    assert result.ok
    assert result.extracted_via == "plain"
    assert result.text == "Just text.\nSecond line."


def test_empty_input_is_a_failure():
    result = parse_document(b"", content_type="text/html")

    assert not result.ok
    assert result.failure is ParseFailure.EMPTY_INPUT


# ── 🔴 Chrome: navigation is not evidence ──────────────────────────────────


def test_navigation_and_scripts_never_reach_the_text():
    """🔴 A correctness issue, not tidiness.

    Extracting chrome does not merely add noise -- it creates atoms whose spans
    point at a menu item. A citation that resolves to "Skip to main content" is
    worse than no citation at all, because it looks like evidence.
    """
    result = parse_document(PIB_PAGE.encode("utf-8"), content_type="text/html")

    assert result.ok
    assert "Skip to main content" not in result.text
    assert "Ministries" not in result.text
    assert "var analytics" not in result.text
    assert "margin: 0" not in result.text
    assert "Copyright" not in result.text
    assert "Related releases" not in result.text
    # ... and the actual evidence survived.
    assert "decrease of around 8% in GHG emissions" in result.text


def test_main_content_container_is_preferred_over_the_whole_body():
    result = parse_document(PIB_PAGE.encode("utf-8"), content_type="text/html")

    assert result.extracted_via == "main"


def test_chrome_is_stripped_even_when_falling_back_to_the_body():
    """Chrome removal happens BEFORE selection, so a page with no recognisable
    content container still cannot leak its navigation into a span.
    """
    page = f"""<html><body>
      <nav>Skip to main content</nav>
      <script>var x = 1;</script>
      <div class="unknown-wrapper"><p>{ARTICLE}</p></div>
    </body></html>"""

    result = parse_document(page.encode("utf-8"), content_type="text/html")

    assert result.ok
    assert result.extracted_via == "body"
    assert "Skip to main content" not in result.text
    assert "var x" not in result.text
    assert "8% in GHG emissions" in result.text


def test_a_short_content_container_is_skipped_as_chrome():
    """A <main> holding one breadcrumb is chrome that happened to use a content
    tag. Below the threshold we keep looking rather than returning a span's
    worth of nothing.
    """
    page = f"""<html><body>
      <main>Home &gt; Releases</main>
      <article><p>{ARTICLE}</p></article>
    </body></html>"""

    result = parse_document(page.encode("utf-8"), content_type="text/html")

    assert result.ok
    assert result.extracted_via == "article"
    assert "8% in GHG emissions" in result.text


# ── Selectors from df_source.config ────────────────────────────────────────


def test_per_source_selectors_beat_the_generic_ones():
    """config beats convention -- the reason df_source.config exists.

    Both containers here clear the length threshold, so ordering is the ONLY
    reason the configured one wins. The shipped rss_scraper hardcodes selectors
    for two publishers, and that approach does not survive fifty.
    """
    page = f"""<html><body>
      <main><p>Generic container. {ARTICLE}</p></main>
      <div class="pib-release"><p>Configured container. {ARTICLE}</p></div>
    </body></html>"""

    result = parse_document(
        page.encode("utf-8"),
        content_type="text/html",
        selectors=("div.pib-release",),
    )

    assert result.extracted_via == "div.pib-release"
    assert "Configured container" in result.text
    assert "Generic container" not in result.text


def test_a_malformed_selector_in_config_does_not_crash_the_parse():
    """Config is data, and data is wrong sometimes. A bad selector must cost
    that selector, never the document -- and never the other 18 sources.
    """
    result = parse_document(
        PIB_PAGE.encode("utf-8"),
        content_type="text/html",
        selectors=("div[", "main"),
    )

    assert result.ok
    assert result.extracted_via == "main"


def test_a_selector_matching_nothing_falls_through():
    result = parse_document(
        PIB_PAGE.encode("utf-8"),
        content_type="text/html",
        selectors=("div.does-not-exist",),
    )

    assert result.ok
    assert result.extracted_via == "main"


# ── Separators: words that never existed ───────────────────────────────────


def test_adjacent_cells_do_not_fuse_into_a_word_that_never_existed():
    """🔴 Without separator="\\n", BeautifulSoup joins block contents directly:
    two table cells holding "8%" and "2020" become the string "8%2020".

    That is not cosmetic. The span checker extracts numbers as HARD anchors, so
    a fused token means the real figure is absent from the span and a true
    claim gets marked unverifiable -- or worse, a fabricated number matches.
    """
    page = (
        "<html><body><main><table><tr>"
        "<td>8%</td><td>2020</td><td>2019</td>"
        "</tr></table>"
        f"<p>{ARTICLE}</p></main></body></html>"
    )

    result = parse_document(page.encode("utf-8"), content_type="text/html")

    assert result.ok
    assert "8%2020" not in result.text
    assert "20202019" not in result.text
    assert "8%" in result.text
    assert "2020" in result.text


# ── PDF ────────────────────────────────────────────────────────────────────


def test_pdf_pages_are_joined_and_counted():
    with patch(
        PDFPLUMBER_OPEN, return_value=fake_pdf("Page one text.", "Page two text.")
    ):
        result = parse_document(PDF_HEADER, content_type="application/pdf")

    assert result.ok
    assert result.page_count == 2
    assert "Page one text." in result.text
    assert "Page two text." in result.text


def test_pdf_page_offsets_point_into_the_final_text():
    """Recorded so a disputed span can be traced back to a page number.

    Computed against the joined-and-normalised string, never against the
    per-page fragments -- otherwise they would index into text that is not
    what got stored.
    """
    with patch(
        PDFPLUMBER_OPEN,
        return_value=fake_pdf("First page sentence.", "Second page sentence."),
    ):
        result = parse_document(PDF_HEADER, content_type="application/pdf")

    assert result.ok
    assert len(result.page_offsets) == 2
    assert result.page_offsets[0] == 0
    # The offset genuinely locates page 2 inside the stored text.
    assert result.text[result.page_offsets[1] :].startswith("Second page")


def test_a_scanned_pdf_is_reported_not_silently_empty():
    """Image-only PDFs are a real condition for Indian government sources.

    The answer is a VLM pass in Act II. Returning an empty chunk here would
    create an artifact that looks ingested and can never yield an atom.
    """
    with patch(PDFPLUMBER_OPEN, return_value=fake_pdf(None, "", "   ")):
        result = parse_document(PDF_HEADER, content_type="application/pdf")

    assert not result.ok
    assert result.failure is ParseFailure.NO_TEXT_LAYER
    assert result.page_count == 3  # the count survives, for diagnosis


def test_a_pdf_with_some_blank_pages_still_parses():
    """A cover page with only a logo is normal, not a failure."""
    with patch(PDFPLUMBER_OPEN, return_value=fake_pdf(None, ARTICLE, "")):
        result = parse_document(PDF_HEADER, content_type="application/pdf")

    assert result.ok
    assert "8% in GHG emissions" in result.text


def test_a_malformed_pdf_is_one_sources_failure_not_the_runs():
    """8.4: fail-safe, never fail-stop. pdfminer raises a wide variety of
    types, so the handler is deliberately broad -- a 19-source run must not end
    because one file is truncated.
    """
    with patch(PDFPLUMBER_OPEN, side_effect=ValueError("xref table broken")):
        result = parse_document(PDF_HEADER, content_type="application/pdf")

    assert not result.ok
    assert result.failure is ParseFailure.MALFORMED
    assert "xref" in result.detail


# ── 🔴 Every ok result is canonical ────────────────────────────────────────


@pytest.mark.parametrize(
    ("body", "content_type"),
    [
        (PIB_PAGE.encode("utf-8"), "text/html"),
        (b"plain\r\n\r\n\r\n\r\ntext  with   runs", "text/plain"),
        (b"<html><body><main>" + ARTICLE.encode() + b"</main></body></html>", ""),
    ],
)
def test_output_is_always_normalised(body, content_type):
    """🔴 The contract 16.6.3 actually cares about.

    Whatever this returns becomes df_chunk.normalised_text and every offset
    indexes into it. If any path returned un-normalised text, offsets computed
    against it would not survive a re-parse from the archive.
    """
    result = parse_document(body, content_type=content_type)

    assert result.ok
    assert is_normalised(result.text)


def test_pdf_output_is_normalised_too():
    with patch(
        PDFPLUMBER_OPEN,
        return_value=fake_pdf("Text with\r\nCRLF and nbsp.", "Second   page."),
    ):
        result = parse_document(PDF_HEADER, content_type="application/pdf")

    assert result.ok
    assert is_normalised(result.text)
    assert "\r" not in result.text
    assert " " not in result.text


# ── Refusal: inherited from the fetcher on 2026-10-06 ──────────────────────


def test_undecodable_bytes_are_refused_rather_than_forced():
    """`errors="strict"`, never `errors="replace"`.

    A decode that "succeeds" by inserting U+FFFD has thrown the original
    characters away. Those spans would point at text that does not match the
    source, which is the one thing the product promises cannot happen.
    """
    result = parse_document(b"\xff\xfe\xfd", content_type="text/html", encoding="utf-8")

    assert not result.ok
    assert result.failure is ParseFailure.UNDECODABLE


def test_an_unknown_codec_is_a_failure_not_a_crash():
    result = parse_document(b"text", content_type="text/plain", encoding="not-a-codec")

    assert not result.ok
    assert result.failure is ParseFailure.UNDECODABLE


def test_source_text_already_containing_replacement_chars_is_refused():
    """⚠️ The deliberate divergence from current_affairs.rss_scraper.

    The scraper LOGS this and keeps the article, because damaged text is still
    useful for event discovery. The Factory REFUSES it: every atom derived
    would carry a span over characters that no longer exist. Rejecting costs a
    re-fetch; accepting costs a wrong citation sold to a student.

    Strict decoding cannot INTRODUCE U+FFFD, so anything caught here was
    already corrupt at the publisher.
    """
    corrupted = (
        f"<html><body><main><p>Emissions fell 8�. {ARTICLE}</p></main></body></html>"
    )

    result = parse_document(corrupted.encode("utf-8"), content_type="text/html")

    assert not result.ok
    assert result.failure is ParseFailure.CORRUPTED


def test_the_corruption_gate_is_central_not_per_format():
    """Applied once, after dispatch, so a format added later cannot skip it."""
    with patch(PDFPLUMBER_OPEN, return_value=fake_pdf(f"Damaged 8�. {ARTICLE}")):
        result = parse_document(PDF_HEADER, content_type="application/pdf")

    assert not result.ok
    assert result.failure is ParseFailure.CORRUPTED
