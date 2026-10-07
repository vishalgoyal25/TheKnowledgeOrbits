"""Turn fetched bytes into the plain text a claim can be located in.

Act 0, phase 0.3. Spec: 00_MASTER_RECAP.md 16.6.3, 2.7 (layout-aware parsing).

    bytes + content type -> extract -> normalise ONCE -> the text offsets index into

🔴 This module owns the LAST transformation before offsets exist. Whatever it
returns is what goes into ``df_chunk.normalised_text``, and every
``char_start`` in the system is an index into it. That is why normalisation
happens HERE, at the end, rather than anywhere earlier: normalising markup and
then extracting from it would produce final text that was never normalised as
a unit.

Why chrome removal is a correctness issue, not tidiness
-------------------------------------------------------
A PIB release page is mostly navigation: ministry menus, language switchers,
social buttons, "related releases". Extracting that as evidence does not merely
add noise -- it creates atoms whose spans point at a menu item, and a citation
that resolves to "Skip to main content" is worse than no citation at all.

So extraction is deliberately narrow: strip the known chrome elements, prefer a
main-content container, and fall back to the body only when nothing matches.

Per-source selectors live in config, never in code
---------------------------------------------------
``selectors`` comes from ``df_source.config``, which exists precisely so that
adding source 50 is a row rather than an ``if source.name == ...`` branch. The
shipped ``rss_scraper`` hardcodes selectors for two publishers, and that
approach does not survive fifty.

Scanned PDFs are a reportable outcome, not a crash
---------------------------------------------------
``pdfplumber`` returns nothing for an image-only page. That is a real condition
for Indian government PDFs, and the answer is a VLM pass in Act II -- not a
silent empty chunk here. It returns ``NO_TEXT_LAYER`` so the caller can route
it.

Three structural extractions, added 2026-10-06
-----------------------------------------------
Government pages are badly built rather than hostile -- ASP.NET WebForms from a
decade ago, not bot defence. (The deliberate blocking is at the NEWS sites;
Indian Express blocks by IP range, which no parser fixes.) Three consequences
had to be handled explicitly, because flattening them loses the fact itself:

1. **Tables.** ``get_text()`` turns a row into a column of unrelated lines, so
   "UNMIL | 2003-2018" becomes two separate facts about nothing. For a matching
   question the ASSOCIATION is the claim, so rows are linearised onto one line.
2. **JSON-LD and meta tags.** Many pages carry machine-readable, authoritative
   structured data in ``<script type="application/ld+json">`` -- headline,
   datePublished, sometimes the whole article body. Stripping scripts threw the
   best data on the page away, so it is harvested BEFORE chrome removal.
3. **Links.** A release that links to its own annexure looks complete while the
   data sits one hop away. Targets are captured so Act II can follow them.
"""

import io
import json
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urljoin

import pdfplumber
import structlog
from bs4 import BeautifulSoup

from engines.data_factory.services.text_normaliser import (
    REPLACEMENT_CHAR,
    has_replacement_char,
    normalise_document,
)

logger = structlog.get_logger(__name__)

# Magic bytes beat the Content-Type header. Several government hosts serve PDFs
# as application/octet-stream, and at least one serves them as text/html.
_PDF_MAGIC = b"%PDF-"

# Elements that are never evidence. Removed before any text is taken, so their
# contents cannot leak into a span.
_CHROME_TAGS = (
    "script",
    "style",
    "noscript",
    "nav",
    "header",
    "footer",
    "aside",
    "button",
    "input",
    "select",
    "textarea",
    "iframe",
    "svg",
)

# ⛔ "form" IS DELIBERATELY ABSENT. Do not add it back.
#
# Found 2026-10-06 by the first real run: 8 of 19 Act 0 sources returned
# NO_CONTENT -- PIB (x4), RBI, legislative.gov.in, sansad.in -- every one of
# them a 200 with a full body.
#
# 🔴 Indian government sites are ASP.NET WebForms, which wraps the ENTIRE page
# body in a single <form id="form1" runat="server">. Stripping <form> therefore
# deletes the whole document, and the symptom is an empty parse rather than an
# error, because nothing failed -- there was simply nothing left.
#
# Form CONTROLS are stripped instead: input, select, textarea and button are UI
# furniture and never prose, while the <form> element on these sites is just
# the body by another name.
#
# ⚠️ No hand-written HTML fixture would have caught this. It took a real fetch
# of a real ministry page, which is why 0.3 runs --dry-run against live sources
# before it writes anything.

# Tried in order. The first that matches and yields text wins. Generic and
# standards-based deliberately -- publisher-specific selectors belong in
# df_source.config, not here.
_MAIN_CONTENT_SELECTORS = (
    "main",
    "article",
    "[role='main']",
    "#main-content",
    ".main-content",
)

# A match this short is chrome that happened to use a content selector, not an
# article. Below this we fall through to the next candidate.
_MIN_CONTENT_CHARS = 200

# 🔴 Maximum share of a candidate's text that may sit inside <a> tags.
#
# Found 2026-10-06 by --inspect on Q38. PIB's <main> is the "latest releases"
# browser widget, not the release: it extracted 6,021 characters of OTHER
# headlines -- "President's Secretariat... Cabinet approves..." -- and the word
# "Rainfed" appeared nowhere. Length alone could never catch that, because a
# navigation list clears 200 characters trivially.
#
# Link density is the discriminator that does: a nav block is almost entirely
# anchor text, while an article is almost entirely prose. This is the standard
# boilerplate heuristic (Readability, boilerpipe) and it generalises, which is
# the point -- the alternative is a hand-tuned selector for all fifty sources.
#
# 0.5 is deliberately permissive. A legitimate government release cites other
# documents and names schemes as links; a menu is 0.9+.
_MAX_LINK_DENSITY = 0.5


class ParseFailure(str, Enum):
    """Why extraction produced nothing usable."""

    EMPTY_INPUT = "empty_input"
    NO_TEXT_LAYER = "no_text_layer"
    UNDECODABLE = "undecodable"
    MALFORMED = "malformed"
    NO_CONTENT = "no_content"
    CORRUPTED = "corrupted"


@dataclass(frozen=True)
class MediaRef:
    """One content image: a chart, infographic, map or official photograph.

    🔴 These are EVIDENCE, not decoration. A PIB release announcing emission
    figures routinely puts the numbers in an infographic and not in the prose,
    so a text-only Factory cannot see the fact at all. Downstream they serve
    four jobs the developer named: daily CA cards, explanations that SHOW a
    diagram rather than describe it, PDF generation, and visible proof of
    source.

    ``alt`` and ``caption`` are captured because on government sites they are
    frequently the densest description of the chart available -- often better
    prose than the surrounding paragraph.

    ⚠️ Act 0 captures the REFERENCE only. Downloading, storing to S3 and
    linking an image to the atoms it supports is Act II (phase 2.5a), where
    there is a bucket to put it in. Capturing the reference now costs nothing
    and makes the gap visible rather than forgotten.
    """

    url: str
    alt: str = ""
    caption: str = ""
    order: int = 0


@dataclass(frozen=True)
class LinkRef:
    """An outbound link from the content, with the text that described it.

    A release reading "the full list is at Annexure II" LOOKS complete while
    the data sits one hop away. Capturing targets is what lets Act II follow
    them; Act 0 only records that the hop exists.

    ``is_document`` flags the ones that matter most -- a linked PDF from a
    ministry is frequently the authoritative, EXHAUSTIVE source that the HTML
    page merely summarises, which is exactly the kind that can prove a claim
    FALSE (09_FUSION_AND_EVIDENCE.md 8).
    """

    url: str
    text: str = ""
    is_document: bool = False


@dataclass(frozen=True)
class StructuredData:
    """Machine-readable metadata the page published about itself.

    🔴 Harvested BEFORE chrome removal, because JSON-LD lives in a <script>
    tag and script stripping was discarding the single most reliable data on
    the page. It is authored by the publisher for machines, so it needs no
    selector guessing and no heuristics.

    ``published_at`` matters beyond convenience: df_artifact.published_at
    drives ingestion-freshness SLOs and atom validity windows, and parsing it
    out of prose is guesswork while reading it from JSON-LD is not.
    """

    headline: str = ""
    published_at: str = ""
    modified_at: str = ""
    author: str = ""
    article_body: str = ""
    raw_types: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ParseResult:
    """Canonical text, plus how it was obtained.

    ``extracted_via`` is kept because "which selector produced this" is the
    first question asked when a span looks wrong, and reconstructing it later
    from the stored text is impossible.
    """

    ok: bool
    text: str = ""
    failure: ParseFailure | None = None
    detail: str = ""
    extracted_via: str = ""
    page_count: int = 0
    page_offsets: tuple[int, ...] = field(default_factory=tuple)
    media: tuple[MediaRef, ...] = field(default_factory=tuple)
    links: tuple[LinkRef, ...] = field(default_factory=tuple)
    structured: StructuredData | None = None

    def __bool__(self) -> bool:
        return self.ok


def looks_like_pdf(raw_bytes: bytes) -> bool:
    """Trust the bytes, not the Content-Type header."""
    return raw_bytes[:5] == _PDF_MAGIC


def parse_document(
    raw_bytes: bytes,
    *,
    content_type: str = "",
    encoding: str = "utf-8",
    selectors: tuple[str, ...] = (),
    base_url: str = "",
) -> ParseResult:
    """Extract plain text and return it in canonical form.

    Keyword-only after the bytes, so no caller can accidentally pass an
    encoding where a content type belongs.

    Args:
        raw_bytes: exactly what was fetched. PDFs need bytes, not text, which
            is why this takes bytes rather than a decoded string.
        content_type: the declared header. Advisory only -- PDF magic bytes
            override it.
        encoding: the codec the fetcher resolved explicitly (Contract 1).
        selectors: per-source CSS selectors from ``df_source.config``, tried
            before the generic ones.

    Returns:
        A ``ParseResult`` whose ``text``, when ok, is already normalised and
        ready to be chunked. Never raises.
    """
    return _reject_if_corrupted(
        _extract(
            raw_bytes,
            content_type=content_type,
            encoding=encoding,
            selectors=selectors,
            base_url=base_url,
        )
    )


def _reject_if_corrupted(result: ParseResult) -> ParseResult:
    """The last gate before text becomes evidence.

    🔴 Moved here from the fetcher on 2026-10-06, when the fetcher stopped
    decoding. It needs TEXT, and after that change only the parser has any.

    Strict decoding above cannot INTRODUCE U+FFFD, so anything reaching here
    was already corrupt at the source. Those characters are gone -- not
    recoverable by re-decoding -- so every atom extracted from this document
    would carry a span over text that does not match what the publisher wrote.

    ⚠️ A deliberate divergence from ``current_affairs.rss_scraper``, which LOGS
    this and keeps the article because damaged text is still useful for event
    discovery. The Factory REFUSES it: rejecting costs a re-fetch, accepting
    costs a wrong citation sold to a student.

    Applied centrally rather than in each extraction path, so a future format
    cannot be added that quietly skips the check.
    """
    if not result.ok or not has_replacement_char(result.text):
        return result

    logger.warning(
        "df_parse_corrupted",
        extracted_via=result.extracted_via,
        replacement_chars=result.text.count(REPLACEMENT_CHAR),
    )
    return ParseResult(
        ok=False,
        failure=ParseFailure.CORRUPTED,
        detail="U+FFFD present in the source text",
        extracted_via=result.extracted_via,
        page_count=result.page_count,
    )


def _extract(
    raw_bytes: bytes,
    *,
    content_type: str,
    encoding: str,
    selectors: tuple[str, ...],
    base_url: str = "",
) -> ParseResult:
    """Format dispatch. Everything it returns passes through the gate above."""
    if not raw_bytes:
        return ParseResult(
            ok=False, failure=ParseFailure.EMPTY_INPUT, detail="no bytes"
        )

    if looks_like_pdf(raw_bytes) or "application/pdf" in content_type.lower():
        return _parse_pdf(raw_bytes)

    try:
        decoded = raw_bytes.decode(encoding or "utf-8", errors="strict")
    except (UnicodeDecodeError, LookupError) as exc:
        logger.warning("df_parse_undecodable", encoding=encoding, error=str(exc))
        return ParseResult(
            ok=False, failure=ParseFailure.UNDECODABLE, detail=f"{encoding}: {exc}"
        )

    if "html" in content_type.lower() or "<html" in decoded[:2048].lower():
        return _parse_html(decoded, selectors=selectors, base_url=base_url)

    # Plain text, CSV, anything else textual: normalise and keep.
    text = normalise_document(decoded)
    if not text:
        return ParseResult(
            ok=False,
            failure=ParseFailure.NO_CONTENT,
            detail="empty after normalisation",
        )
    return ParseResult(ok=True, text=text, extracted_via="plain")


def _parse_pdf(raw_bytes: bytes) -> ParseResult:
    """Extract a PDF's text layer, page by page.

    ⚠️ Act 0 scope. This reads the text layer only -- it does NOT reconstruct
    multi-column newspaper layout, where articles jump across columns and
    pages and naive extraction returns interleaved nonsense. That needs a
    layout model (Surya / PP-DocLayout) and is phase 2.7.

    Government release PDFs are single-column and extract cleanly, which is why
    this is sufficient for the three PDFs in the Act 0 set.
    """
    pages: list[str] = []
    try:
        with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text() or "")
    except Exception as exc:  # noqa: BLE001 - pdfplumber raises many unrelated types
        # Deliberately broad: a malformed PDF must be a reportable outcome for
        # one source, never an exception that ends a 19-source run (8.4).
        logger.warning("df_parse_pdf_malformed", error=str(exc))
        return ParseResult(ok=False, failure=ParseFailure.MALFORMED, detail=str(exc))

    if not any(p.strip() for p in pages):
        # Scanned or image-only. A real condition for Indian government PDFs,
        # and the answer is a VLM pass in Act II -- not an empty chunk here.
        logger.info("df_parse_no_text_layer", page_count=len(pages))
        return ParseResult(
            ok=False,
            failure=ParseFailure.NO_TEXT_LAYER,
            detail=f"{len(pages)} pages, no extractable text",
            page_count=len(pages),
        )

    # Record where each page starts in the FINAL text, so a span can be traced
    # back to a page number when a citation is audited. Computed against the
    # joined-and-normalised string, never against the per-page fragments.
    joined = "\n\n".join(pages)
    text = normalise_document(joined)

    offsets: list[int] = []
    cursor = 0
    for page_text in pages:
        marker = normalise_document(page_text)
        if marker:
            found = text.find(marker[:80], cursor)
            if found >= 0:
                offsets.append(found)
                cursor = found + 1

    return ParseResult(
        ok=True,
        text=text,
        extracted_via="pdf_text_layer",
        page_count=len(pages),
        page_offsets=tuple(offsets),
    )


def _parse_html(
    html: str, *, selectors: tuple[str, ...] = (), base_url: str = ""
) -> ParseResult:
    """Strip chrome, find the content, return normalised text and its media."""
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as exc:  # noqa: BLE001 - parser backends raise varied types
        logger.warning("df_parse_html_malformed", error=str(exc))
        return ParseResult(ok=False, failure=ParseFailure.MALFORMED, detail=str(exc))

    # 🔴 BEFORE chrome removal. JSON-LD lives in a <script>, and script is a
    # chrome tag -- stripping first threw away the best data on the page.
    structured = _extract_structured_data(soup)

    # Remove chrome BEFORE selecting, so a content container that happens to
    # wrap a nav block does not drag it in.
    for tag_name in _CHROME_TAGS:
        for element in soup.find_all(tag_name):
            element.decompose()

    # Rows onto single lines, so "UNMIL | 2003-2018" survives as one fact
    # rather than two. After chrome removal, before any text is taken.
    _linearise_tables(soup)

    # Per-source selectors first: config beats convention.
    for selector in (*selectors, *_MAIN_CONTENT_SELECTORS):
        try:
            node = soup.select_one(selector)
        except Exception:  # noqa: BLE001 - a bad selector in config must not crash
            logger.warning("df_parse_bad_selector", selector=selector)
            continue
        if node is None:
            continue
        # separator="\n" so block boundaries survive; without it adjacent
        # <td> or <p> contents run together into words that never existed.
        candidate = normalise_document(node.get_text(separator="\n"))
        if len(candidate) < _MIN_CONTENT_CHARS:
            continue

        density = _link_density(node, len(candidate))
        if density > _MAX_LINK_DENSITY:
            # A navigation block wearing a content tag. Fall through rather
            # than return 6,000 characters of other people's headlines.
            logger.info(
                "df_parse_rejected_as_navigation",
                selector=selector,
                link_density=round(density, 2),
                chars=len(candidate),
            )
            continue

        return ParseResult(
            ok=True,
            text=candidate,
            extracted_via=selector,
            media=_collect_media(node, base_url=base_url),
            links=_collect_links(node, base_url=base_url),
            structured=structured,
        )

    # Nothing matched. Fall back to the whole body, chrome already stripped.
    body = soup.body or soup
    text = normalise_document(body.get_text(separator="\n"))
    if not text:
        return ParseResult(
            ok=False, failure=ParseFailure.NO_CONTENT, detail="no text after stripping"
        )

    logger.info("df_parse_fell_back_to_body", char_count=len(text))
    return ParseResult(
        ok=True,
        text=text,
        extracted_via="body",
        media=_collect_media(body, base_url=base_url),
        links=_collect_links(body, base_url=base_url),
        structured=structured,
    )


def _link_density(node, text_length: int) -> float:
    """Share of this container's text that sits inside anchors.

    The number that separates an article from a menu. A ministry release cites
    documents and names schemes, so it carries some links; a "latest releases"
    sidebar is almost nothing but links.

    Returns 0.0 for an empty container so that a short, linkless block is never
    rejected on a division by zero.
    """
    if text_length <= 0:
        return 0.0
    anchor_chars = sum(
        len(a.get_text(separator=" ").strip()) for a in node.find_all("a")
    )
    return min(anchor_chars / text_length, 1.0)


def _linearise_tables(node) -> None:
    """Rewrite every table row onto ONE line, in place, before text extraction.

    🔴 Without this, ``get_text(separator="\\n")`` turns

        | UNMIL | 2003-2018 |

    into two unrelated lines, and the ASSOCIATION -- which mission ran when --
    is destroyed. For a matching question that association IS the claim, so a
    flattened table cannot support one no matter how good the verifier is.

    Government pages are full of tables: committee compositions, scheme
    parameters, outcome lists, mission periods. Four of the Act 0 questions are
    pure table data.

    Each row becomes "cell | cell | cell", which keeps the relation inside a
    single sentence-like unit that the locator can return as one span. The
    separator is " | " rather than a comma because commas already appear inside
    cells and would be indistinguishable.

    ⚠️ Mutates the soup. That is safe here because it happens AFTER chrome
    removal and BEFORE any text is taken, so the result is still a single
    extraction that normalisation then canonicalises once.
    """
    for row in node.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if not cells:
            continue
        values = [c.get_text(separator=" ").strip() for c in cells]
        values = [v for v in values if v]
        if not values:
            continue
        # Replace the row's contents with a single text node. A trailing
        # newline keeps rows apart once separator="\n" joins blocks.
        row.clear()
        row.append(" | ".join(values) + "\n")


def _extract_structured_data(soup) -> StructuredData | None:
    """Read JSON-LD and meta tags -- the publisher's own machine-readable copy.

    🔴 Must run BEFORE chrome removal. JSON-LD lives inside
    ``<script type="application/ld+json">``, and ``script`` is a chrome tag, so
    stripping chrome first discarded the most reliable data on the page.

    Falls back to Open Graph and standard meta tags, which almost every CMS
    emits even when JSON-LD is absent.

    Never raises: malformed JSON-LD is extremely common (trailing commas,
    HTML-escaped quotes, arrays where objects are expected) and is not worth
    failing a document over.
    """
    headline = published = modified = author = body = ""
    types: list[str] = []

    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            payload = json.loads(tag.string or "{}")
        except (json.JSONDecodeError, TypeError):
            continue

        # JSON-LD is legitimately a dict, a list, or a @graph wrapper.
        candidates = payload if isinstance(payload, list) else [payload]
        if isinstance(payload, dict) and "@graph" in payload:
            graph = payload.get("@graph")
            if isinstance(graph, list):
                candidates = graph

        for item in candidates:
            if not isinstance(item, dict):
                continue
            item_type = item.get("@type", "")
            if isinstance(item_type, list):
                types.extend(str(t) for t in item_type)
            elif item_type:
                types.append(str(item_type))

            headline = headline or str(item.get("headline", "") or "")
            published = published or str(item.get("datePublished", "") or "")
            modified = modified or str(item.get("dateModified", "") or "")
            body = body or str(item.get("articleBody", "") or "")

            raw_author = item.get("author")
            if not author and raw_author:
                if isinstance(raw_author, dict):
                    author = str(raw_author.get("name", "") or "")
                elif isinstance(raw_author, list) and raw_author:
                    first = raw_author[0]
                    author = str(
                        first.get("name", "") if isinstance(first, dict) else first
                    )
                else:
                    author = str(raw_author)

    # Open Graph and friends, for the many pages with no JSON-LD at all.
    for name, target in (
        ("og:title", "headline"),
        ("article:published_time", "published"),
        ("article:modified_time", "modified"),
    ):
        meta = soup.find("meta", attrs={"property": name}) or soup.find(
            "meta", attrs={"name": name}
        )
        if meta is None:
            continue
        content = (meta.get("content") or "").strip()
        if not content:
            continue
        if target == "headline" and not headline:
            headline = content
        elif target == "published" and not published:
            published = content
        elif target == "modified" and not modified:
            modified = content

    if not any([headline, published, modified, author, body]):
        return None

    logger.info(
        "df_parse_structured_data",
        has_published=bool(published),
        has_body=bool(body),
        types=types[:3],
    )
    return StructuredData(
        headline=headline,
        published_at=published,
        modified_at=modified,
        author=author,
        article_body=body,
        raw_types=tuple(types),
    )


# Extensions whose link targets are likely to be the authoritative document
# rather than a navigation hop.
_DOCUMENT_EXTENSIONS = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv")


def _collect_links(node, *, base_url: str = "") -> tuple[LinkRef, ...]:
    """Outbound links from the content, with their anchor text.

    Deduplicated by resolved URL, because government pages repeat the same
    annexure link in a sidebar, a body paragraph and a footer list.
    """
    seen: set[str] = set()
    links: list[LinkRef] = []

    for anchor in node.find_all("a"):
        href = (anchor.get("href") or "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        url = urljoin(base_url, href) if base_url else href
        if url in seen:
            continue
        seen.add(url)
        lowered = url.lower()
        links.append(
            LinkRef(
                url=url,
                text=anchor.get_text(separator=" ").strip()[:200],
                is_document=any(lowered.endswith(ext) for ext in _DOCUMENT_EXTENSIONS),
            )
        )

    return tuple(links)


def _collect_media(node, *, base_url: str = "") -> tuple[MediaRef, ...]:
    """Content images, in document order, with their alt text and captions.

    🔴 Collected from the SELECTED CONTENT NODE, after chrome removal. That is
    what makes the result usable without any filtering heuristics: logos,
    social icons and banner furniture live in the nav and header that were
    already decomposed, so what remains inside an article is the article's own
    charts, infographics, maps and photographs.

    ``figcaption`` is preferred over ``alt`` when present, because a caption is
    written for a reader while alt text is sometimes a filename.
    """
    media: list[MediaRef] = []

    for index, img in enumerate(node.find_all("img")):
        src = (img.get("src") or img.get("data-src") or "").strip()
        if not src or src.startswith("data:"):
            # Inline data URIs on government pages are spacers and tracking
            # pixels, never content. A real chart is a file with a URL.
            continue

        caption = ""
        figure = img.find_parent("figure")
        if figure is not None:
            figcaption = figure.find("figcaption")
            if figcaption is not None:
                caption = figcaption.get_text(separator=" ").strip()

        media.append(
            MediaRef(
                url=urljoin(base_url, src) if base_url else src,
                alt=(img.get("alt") or "").strip(),
                caption=caption,
                order=index,
            )
        )

    if media:
        logger.info("df_parse_media_found", count=len(media))
    return tuple(media)
