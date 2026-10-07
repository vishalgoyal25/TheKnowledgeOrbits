"""The one place raw fetched text becomes the string offsets index into.

Act 0, phase 0.3. Spec: 00_MASTER_RECAP.md 16.6.3.

    fetch -> normalise ONCE -> store df_chunk.normalised_text
          -> locate claim -> record char_start/char_end PROGRAMMATICALLY

Why this module exists at all
-----------------------------
``span_checker._normalise_for_comparison`` already folds text, but it is
explicitly FOR COMPARISON ONLY -- it casefolds, strips digit grouping and
rewrites percent spellings. Running it over stored text would shift every
offset already computed against that text, which is the exact failure Contract
1 exists to prevent. The two are deliberately different jobs:

    _normalise_for_comparison   aggressive, lossy, never stored, never sliced
    normalise_document (here)   conservative, stored ONCE, sliced forever

🔴 The property this module lives or dies by: IDEMPOTENCE
---------------------------------------------------------
``normalise_document(normalise_document(x)) == normalise_document(x)``

If that ever fails, a re-parse from the S3 archive produces text one character
different from the original, every stored offset silently points one character
off, and the citation chain breaks with no error anywhere. The archive stops
being a safety net and becomes a liability. It is pinned by a test, and the
test is not optional.

What this does NOT do, and why
-------------------------------
Smart quotes and en/em dashes are left exactly as published. Each is a single
character, so they cannot shift an offset, and leaving them keeps the stored
text faithful to what a human auditing the citation would see on the page.
Anchor matching already tolerates them: the checker extracts numbers, years,
acronyms and capitalised words, none of which are affected by the shape of a
quotation mark.

The rule applied throughout: transform ONLY where not transforming causes an
offset bug. Every transformation is a chance to be wrong, so each one below
names the hazard it prevents.
"""

import re
import unicodedata

# Bump when any rule below changes. Chunks carry it as `processing_version`,
# so v2 text coexists with v1 text as NEW rows rather than rewriting old ones
# -- 00_MASTER_RECAP.md 8.3. Never renumber retroactively: a chunk stamped v1
# must always mean "produced by exactly these rules".
NORMALISER_VERSION = 1

# Characters that look like a space but are not U+0020. HTML and PDF sources
# emit these constantly, and they break naive matching while being invisible
# in every editor and browser. All are single characters, so substituting a
# plain space is length-preserving and cannot shift an offset.
_SPACE_LIKE = {
    " ": " ",  # NO-BREAK SPACE -- rife in government HTML
    " ": " ",  # OGHAM SPACE MARK
    " ": " ",  # EN QUAD
    " ": " ",  # EM QUAD
    " ": " ",  # EN SPACE
    " ": " ",  # EM SPACE
    " ": " ",  # THREE-PER-EM SPACE
    " ": " ",  # FOUR-PER-EM SPACE
    " ": " ",  # SIX-PER-EM SPACE
    " ": " ",  # FIGURE SPACE -- common inside numeric tables
    " ": " ",  # PUNCTUATION SPACE
    " ": " ",  # THIN SPACE
    " ": " ",  # HAIR SPACE
    " ": " ",  # NARROW NO-BREAK SPACE
    " ": " ",  # MEDIUM MATHEMATICAL SPACE
    "　": " ",  # IDEOGRAPHIC SPACE
}

# Zero-width and formatting characters: invisible, and they DO occupy an index.
# A ZWSP sitting inside "GHG" makes an exact anchor match fail while the text
# looks perfect on screen -- the worst class of bug, because the evidence of it
# is unprintable. These are REMOVED, which shortens the string; that is safe
# only because removal happens before any offset is computed.
_ZERO_WIDTH = re.compile(
    "["
    "​"  # ZERO WIDTH SPACE
    "‌"  # ZERO WIDTH NON-JOINER
    "‍"  # ZERO WIDTH JOINER
    "⁠"  # WORD JOINER
    "﻿"  # ZERO WIDTH NO-BREAK SPACE / BOM
    "­"  # SOFT HYPHEN -- PDF extraction scatters these mid-word
    "]"
)

# Control characters that carry no text meaning. Tab and newline are handled
# separately by the whitespace rules; everything else in C0/C1 is noise that
# some PDF extractors emit. Excludes \t \n \r deliberately.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

# Three or more newlines collapse to exactly two: paragraph structure is worth
# keeping (it makes a stored citation readable when audited) but arbitrary
# runs of blank lines from HTML extraction are not.
_BLANK_RUNS = re.compile(r"\n{3,}")

# Horizontal whitespace runs collapse to one space. Deliberately does NOT
# match \n, so line structure survives this step.
_HORIZONTAL_RUNS = re.compile(r"[^\S\n]+")

# Trailing/leading horizontal whitespace on each line. Applied after the runs
# collapse so a line that was "   \n" does not become " \n".
_LINE_EDGES = re.compile(r"^[^\S\n]+|[^\S\n]+$", re.MULTILINE)

REPLACEMENT_CHAR = "�"


def normalise_document(raw: str) -> str:
    """Produce the canonical text that offsets will index into, forever.

    Run EXACTLY ONCE per artifact, before any offset is computed. The result
    is what goes into ``df_chunk.normalised_text``; every ``char_start`` and
    ``char_end`` in the system is an index into a string produced here.

    Order matters and is not arbitrary:

    1. Line endings first, because CRLF is TWO characters where LF is one --
       the single largest source of offset drift between a Windows-fetched
       document and a Linux-fetched one.
    2. NFC second, because the same visible character can be one code point or
       a base plus a combining mark. Devanagari and accented transliterations
       in Indian government sources hit this routinely, and the two forms have
       different lengths.
    3. Space-like substitutions, which are 1:1 and cannot shift anything.
    4. Removals (zero-width, control), which shorten the string -- safe only
       because nothing has been measured yet.
    5. Whitespace collapsing last, so it sees the result of every step above.

    Args:
        raw: decoded text. Decoding is the fetcher's job and must already have
            resolved the encoding explicitly (Contract 1); this function takes
            ``str`` and never bytes, precisely so encoding cannot be guessed
            here by accident.

    Returns:
        The canonical form. Idempotent: normalising the result again returns
        it unchanged.
    """
    # 1. Line endings. CRLF -> LF before anything counts characters.
    text = raw.replace("\r\n", "\n").replace("\r", "\n")

    # 2. Unicode canonical composition. One visible character, one code point,
    #    one index -- chosen over NFD so that "é" is never 2 characters.
    text = unicodedata.normalize("NFC", text)

    # 3. Space-like -> plain space. Length-preserving.
    for odd, plain in _SPACE_LIKE.items():
        text = text.replace(odd, plain)

    # 4. Invisible characters out. Shortens the string.
    text = _ZERO_WIDTH.sub("", text)
    text = _CONTROL.sub("", text)

    # 5. Whitespace shape. Horizontal runs first, then line edges, then
    #    blank-line runs, then the document's own edges.
    text = _HORIZONTAL_RUNS.sub(" ", text)
    text = _LINE_EDGES.sub("", text)
    text = _BLANK_RUNS.sub("\n\n", text)

    return text.strip()


def has_replacement_char(text: str) -> bool:
    """Whether decoding went wrong somewhere upstream.

    U+FFFD means bytes were decoded with the wrong codec and the original
    characters are GONE -- not recoverable by re-normalising. The span checker
    already fails any span whose text contains one; this is the same test
    applied earlier, at ingestion, where the artifact can simply be re-fetched
    with the correct encoding instead of poisoning every chunk derived from it.
    """
    return REPLACEMENT_CHAR in text


def is_normalised(text: str) -> bool:
    """Whether ``text`` is already in canonical form.

    The cheap assertion for any code path that is about to compute an offset:
    if this is False, the text did not come from ``normalise_document`` and
    any offset derived from it is meaningless.
    """
    return normalise_document(text) == text
