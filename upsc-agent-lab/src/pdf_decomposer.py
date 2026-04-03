"""
src/pdf_decomposer.py
━━━━━━━━━━━━━━━━━━━━━
Steps 1, 2, and 6 of the Deep Content Engine pipeline.
Step 1: Extract raw text from NCERT PDF
Step 2: Clean the raw text (remove page numbers, headers, etc.)
Step 6: Extract the specific NCERT section relevant to a subtopic
"""

import re
import os
from pypdf import PdfReader
from src.llm_client import llm_call, log_info, log_warning


# ── STEP 1: Extract Raw Text ──────────────────────────────────────────────────


def extract_raw_text(pdf_path: str) -> str:
    """
    Extracts all text from a PDF file using pypdf.
    Joins all pages into a single string.

    Args:
        pdf_path: Absolute or relative path to the PDF file

    Returns:
        Raw text string (may contain noise: page numbers, headers, etc.)
    """
    log_info(f"  📄 PDF Decomposer: reading '{os.path.basename(pdf_path)}'...")
    try:
        reader = PdfReader(pdf_path)
        pages = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text and text.strip():
                pages.append(text)

        raw = "\n".join(pages)
        log_info(
            f"     └─ Extracted {len(reader.pages)} pages, "
            f"{len(raw)} chars, ~{len(raw)//4} tokens"
        )
        return raw
    except Exception as e:
        log_warning(f"  ❌ PDF read failed: {e}")
        return ""


# ── STEP 2: Clean the Text ────────────────────────────────────────────────────


def clean_text(raw_text: str) -> str:
    """
    Cleans raw NCERT PDF text in two passes:
      Pass 1: Regex (fast, handles obvious noise)
      Pass 2: LLM (handles subtle issues regex misses)

    Args:
        raw_text: The raw extracted PDF text

    Returns:
        clean_ncert_text: Ready-to-use as research material
    """
    log_info("  🧹 PDF Decomposer: cleaning text (regex pass)...")
    regex_cleaned = _regex_clean(raw_text)

    log_info("  🧹 PDF Decomposer: cleaning text (LLM pass)...")
    final_cleaned = _llm_clean(regex_cleaned)

    reduction = (1 - len(final_cleaned) / max(len(raw_text), 1)) * 100
    log_info(
        f"     └─ Clean text: {len(final_cleaned)} chars "
        f"({reduction:.1f}% noise removed)"
    )
    return final_cleaned


def _regex_clean(text: str) -> str:
    """Pass 1: Regex-based noise removal."""

    # Fix hyphenated line-breaks from PDF (e.g., "Parlia-\nment" → "Parliament")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)

    # Remove standalone page numbers (line that is just digits)
    text = re.sub(r"^\s*\d{1,3}\s*$", "", text, flags=re.MULTILINE)

    # Remove common NCERT running headers/footers
    patterns_to_remove = [
        r"POLITICAL SCIENCE\s*",
        r"INDIAN CONSTITUTION AT WORK\s*",
        r"NCERT\s*",
        r"© NCERT.*?\n",
        r"not to be republished.*?\n",
        r"not to be reproduced.*?\n",
        r"Intext Question.*?\n",
        r"Fig\s*\d+\.\d+.*?\n",  # Figure references
        r"Table\s*\d+\.\d+.*?\n",  # Table references
        r"\[Activity\].*?\n",
        r"Let us do.*?\n",
    ]
    for pattern in patterns_to_remove:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.MULTILINE)

    # Remove excessive blank lines (more than 2)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Remove lines that are just chapter/section numbers
    text = re.sub(r"^\s*\d+\.\d+\s*$", "", text, flags=re.MULTILINE)

    return text.strip()


def _llm_clean(text: str) -> str:
    """
    Pass 2: LLM-based cleaning for subtle issues regex can't handle.
    Only cleans — does NOT modify, summarize, or add content.
    Processes in chunks if text is very long.
    """
    # For very long texts, process in chunks to avoid token limits
    CHUNK_SIZE = 6000  # chars per LLM cleaning call

    if len(text) <= CHUNK_SIZE:
        return _llm_clean_chunk(text)

    # Process in overlapping chunks and join
    log_info(f"     └─ Long text ({len(text)} chars): cleaning in chunks...")
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        chunk = text[start:end]
        cleaned_chunk = _llm_clean_chunk(chunk)
        chunks.append(cleaned_chunk)
        start = end
    return "\n\n".join(chunks)


def _llm_clean_chunk(chunk: str) -> str:
    """Cleans a single chunk of NCERT text with one LLM call."""
    prompt = f"""Clean the following raw NCERT educational text extracted from a PDF.

YOUR TASK — Remove ONLY these types of noise:
  - Page numbers (standalone numbers like "85", "Chapter 6")
  - Running headers/footers (e.g., repeated subject names)
  - Copyright notices
  - Incomplete figure/table references without content (e.g., "See Fig 6.1")
  - Broken words from PDF line-wrapping (e.g., "constitu- tion" → "constitution")
  - Duplicate blank lines (max 1 blank line between paragraphs)

DO NOT:
  - Change, summarize, or rewrite any educational content
  - Remove any actual text, definitions, or explanations
  - Add anything new
  - Change paragraph ordering

Return the cleaned text ONLY. No preamble, no explanation:

RAW TEXT:
{chunk}"""

    cleaned = llm_call(prompt, mode="standard")
    # If LLM returns empty (failed), fall back to regex-cleaned chunk
    return cleaned if cleaned.strip() else chunk


# ── STEP 6: Extract Section for a Subtopic ────────────────────────────────────


def extract_section(clean_ncert_text: str, subtopic_name: str) -> str:
    """
    LLM Call #3 (per subtopic): Extracts the portion of the NCERT chapter
    that specifically covers `subtopic_name`.

    Args:
        clean_ncert_text: Full cleaned chapter text
        subtopic_name: e.g. "Speaker of Lok Sabha"

    Returns:
        The relevant NCERT section (verbatim extraction, not a summary)
        OR the string "NOT_IN_NCERT" if the subtopic isn't covered
    """
    log_info(f"     📖 NCERT section extract: '{subtopic_name}'...")

    # First: try simple string search to avoid unnecessary LLM call
    if subtopic_name.lower() not in clean_ncert_text.lower():
        # Check if any key word of the subtopic is in the text
        key_words = [w for w in subtopic_name.split() if len(w) > 4]
        if not any(kw.lower() in clean_ncert_text.lower() for kw in key_words):
            log_info(
                "        └─ Not mentioned in NCERT chapter — will use Wikipedia only"
            )
            return "NOT_IN_NCERT"

    prompt = f"""From the NCERT chapter text below, extract ALL content specifically
about "{subtopic_name}".

Rules:
  - Extract verbatim — do NOT paraphrase or summarize
  - Include: definitions, examples, constitutional references, key points
  - Include: anything in the chapter that is related to "{subtopic_name}"
  - If "{subtopic_name}" is NOT covered in this chapter at all: output exactly "NOT_IN_NCERT"
  - Do not add anything not present in the chapter

NCERT CHAPTER TEXT:
\"\"\"
{clean_ncert_text}
\"\"\"

Output the extracted section on "{subtopic_name}" (verbatim from chapter):"""

    result = llm_call(prompt, mode="standard")

    if not result or "NOT_IN_NCERT" in result.upper():
        log_info("        └─ NOT_IN_NCERT → will use Wikipedia only")
        return "NOT_IN_NCERT"

    log_info(
        f"        └─ Extracted {len(result)} chars from NCERT for '{subtopic_name}'"
    )
    return result
