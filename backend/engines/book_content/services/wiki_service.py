"""
engines/book_content/services/wiki_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Fetches the FULL Wikipedia page for any topic.
NOT just the 5-sentence summary — the complete article.
Handles disambiguation, page errors, and network failures gracefully.
Ported from: upsc-agent-lab/src/wiki_fetcher.py
Changes: logging (structlog), imports.
Preserved exactly: section-scoring algorithm, _split_into_sections(),
                   _keyword_window() fallback, disambiguation logic.
"""

import re
import time

import structlog
import wikipedia

logger = structlog.get_logger(__name__)


def fetch_full_page(term: str, fallback_suffix: str = "India") -> dict:
    """
    Fetches the full Wikipedia page for `term`.

    Returns:
        dict with keys:
          - title   (str): Actual Wikipedia article title
          - content (str): Full article text (can be 5000-15000 words)
          - summary (str): Wikipedia's own intro summary (first paragraph)
          - url     (str): Wikipedia URL
          - found   (bool): False if nothing was found
    """
    logger.info("wiki_fetch_start", term=term)

    result = _try_fetch(term)
    if result["found"]:
        logger.info(
            "wiki_fetch_success", title=result["title"], chars=len(result["content"])
        )
        return result

    # Retry with " India" appended (helps for India-specific UPSC topics)
    if fallback_suffix and fallback_suffix.lower() not in term.lower():
        fallback_term = f"{term} {fallback_suffix}"
        logger.warning("wiki_fetch_retry", fallback_term=fallback_term)
        result = _try_fetch(fallback_term)
        if result["found"]:
            logger.info(
                "wiki_fetch_success",
                title=result["title"],
                chars=len(result["content"]),
            )
            return result

    logger.warning("wiki_fetch_not_found", term=term)
    return {"title": term, "content": "", "summary": "", "url": "", "found": False}


def _try_fetch(term: str) -> dict:
    """Internal: attempts a single Wikipedia fetch."""
    try:
        page = wikipedia.page(term, auto_suggest=True, preload=False)
        return {
            "title": page.title,
            "content": page.content,  # Full article — NOT just summary
            "summary": page.summary,
            "url": page.url,
            "found": True,
        }

    except wikipedia.exceptions.DisambiguationError as e:
        # LLM topic might be ambiguous (e.g., "Emergency" → State Emergency / Medical)
        # Pick the first option that doesn't have parentheses (most direct match)
        clean_options = [o for o in e.options if "(" not in o]
        best = clean_options[0] if clean_options else e.options[0]
        logger.warning("wiki_disambiguation", term=term, resolved_to=best)
        try:
            page = wikipedia.page(best, auto_suggest=False)
            return {
                "title": page.title,
                "content": page.content,
                "summary": page.summary,
                "url": page.url,
                "found": True,
            }
        except Exception:
            return _empty(term)

    except wikipedia.exceptions.PageError:
        return _empty(term)

    except Exception as e:
        logger.warning("wiki_fetch_error", term=term, error=str(e)[:60])
        time.sleep(3)  # Brief pause on network errors
        return _empty(term)


def extract_relevant_section(
    wiki_content: str, subtopic: str, max_chars: int = 3000
) -> str:
    """
    UPGRADED: Extracts ALL relevant sections from Wikipedia for a subtopic.

    Old approach: Find keyword, cut 5000-char window. Got 1 section.
    New approach: Find ALL sections containing relevant content. Merge them.
    This ensures the LLM gets complete research material, not just a fragment.
    """
    if not wiki_content:
        return ""

    # Split article into sections by == headings ==
    sections = _split_into_sections(wiki_content)

    if not sections:
        # No section structure — fall back to keyword window
        return _keyword_window(wiki_content, subtopic, max_chars)

    # Score each section for relevance to subtopic
    subtopic_lower = subtopic.lower()
    subtopic_words = [w for w in subtopic_lower.split() if len(w) > 3]

    scored_sections = []
    for section in sections:
        score = 0
        section_lower = section["content"].lower()
        title_lower = section["title"].lower()

        # Title match scores highest
        if subtopic_lower in title_lower:
            score += 10
        for word in subtopic_words:
            if word in title_lower:
                score += 3

        # Content keyword frequency
        for word in subtopic_words:
            score += section_lower.count(word)

        scored_sections.append({**section, "score": score})

    # Sort by relevance
    scored_sections.sort(key=lambda x: x["score"], reverse=True)

    # Take top relevant sections up to max_chars
    result_parts = []
    total_chars = 0
    for section in scored_sections:
        if section["score"] == 0:
            break
        content = f"=== {section['title']} ===\n{section['content']}"
        if total_chars + len(content) <= max_chars:
            result_parts.append(content)
            total_chars += len(content)
        else:
            # Take partial
            remaining = max_chars - total_chars
            if remaining > 200:
                result_parts.append(content[:remaining])
            break

    if result_parts:
        return "\n\n".join(result_parts)

    # Fallback: return beginning of article
    return wiki_content[:max_chars]


def _split_into_sections(wiki_content: str) -> list:
    """Splits Wikipedia content into titled sections."""
    sections = []
    # Match == Section == or === Subsection === patterns
    pattern = re.compile(r"^(={2,4})\s*(.+?)\s*\1\s*$", re.MULTILINE)
    matches = list(pattern.finditer(wiki_content))

    if not matches:
        return []

    # Add intro section (before first heading)
    if matches[0].start() > 0:
        sections.append(
            {
                "title": "Introduction",
                "content": wiki_content[: matches[0].start()].strip(),
            }
        )

    for i, match in enumerate(matches):
        title = match.group(2)
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(wiki_content)
        content = wiki_content[start:end].strip()
        if content:
            sections.append({"title": title, "content": content})

    return sections


def _keyword_window(wiki_content: str, subtopic: str, max_chars: int) -> str:
    """Fallback: keyword-based window extraction (original method)."""
    content_lower = wiki_content.lower()
    term_lower = subtopic.lower()
    idx = content_lower.find(term_lower)
    if idx == -1:
        words = [w for w in term_lower.split() if len(w) > 4]
        for word in words:
            idx = content_lower.find(word)
            if idx != -1:
                break
    if idx == -1:
        return wiki_content[:max_chars]
    start = max(0, idx - 800)
    boundary = wiki_content.rfind("\n\n", 0, idx)
    if boundary != -1 and boundary > start:
        start = boundary
    return wiki_content[start : start + max_chars]


def _empty(term: str) -> dict:
    return {"title": term, "content": "", "summary": "", "url": "", "found": False}
