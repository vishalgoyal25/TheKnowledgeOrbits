"""Split canonical document text into chunk-sized slices, losslessly.

Act 0, phase 0.3. Shape: 06_DESIGN.md (chunk ~= 1,200 chars of text).

    normalised document -> chunks -> df_chunk rows -> atoms index INTO a chunk

🔴 THE INVARIANT: a chunk's text is a VERBATIM SLICE of the document.
--------------------------------------------------------------------
    document[chunk.doc_offset : chunk.doc_offset + len(chunk.text)] == chunk.text

``df_atom.char_start`` indexes into ``df_chunk.normalised_text``, so a chunk is
the coordinate system every span lives in. The moment the chunker *edits* text
rather than *slicing* it -- a strip, a join, a separator inserted between
pieces -- chunk text stops being document text, and an offset that is correct
in the chunk points somewhere else in the source it claims to cite.

So this module only ever computes two integers and slices. It never builds a
string. That is also why it takes ALREADY-NORMALISED text: normalising here
would transform, and transforming is the one thing a chunker must not do.

No overlap, deliberately
-------------------------
Retrieval chunkers often overlap windows by a few hundred characters to
improve recall. This one does not, for two reasons specific to a Factory:

1. An atom extracted from overlapping text appears twice, with two different
   spans pointing at the same claim in the same document. Dedup would then be
   cleaning up a mess this module created.
2. A8 -- atoms per chunk -- is a measured capacity input (06_DESIGN.md 2.1).
   Overlap inflates it with duplicates and the number stops meaning anything.

If Act II finds retrieval recall suffers, that is a ``processing_version`` bump
producing new rows beside the old ones, not an edit to these.

Determinism
-----------
Same input, same chunks, always -- no randomness, no locale, no dict ordering.
``processing_version`` only means something if v1 of the rules can be
reproduced exactly.
"""

import re
from dataclasses import dataclass

import structlog

logger = structlog.get_logger(__name__)

# 06_DESIGN.md sizes a chunk at ~1,200 characters. A soft target, not a hard
# cut: the splitter prefers a clean boundary near it over an exact length.
DEFAULT_MAX_CHARS = 1200

# Never accept a split point before this fraction of the window. Without it, a
# paragraph break at character 40 of a 1,200-character window would emit a
# 40-character chunk and waste the rest of the budget.
_MIN_SPLIT_RATIO = 0.5

# Boundary candidates, best first. Each is searched for backwards from the end
# of the window; the first that lands after the minimum wins.
#
# The Devanagari danda is included because Hindi PIB releases are in the source
# set, and "।" is their sentence terminator -- without it a Hindi document gets
# split on whitespace, mid-sentence, every time.
_PARAGRAPH_BREAK = "\n\n"
_SENTENCE_END = re.compile(r"[.?!।]\s")
_LINE_BREAK = "\n"


@dataclass(frozen=True)
class Chunk:
    """One slice of a document, with its position in that document.

    ``doc_offset`` is NOT persisted in Act 0 -- ``df_chunk`` has no column for
    it, and atoms index into the chunk rather than the document. It is returned
    because the seeding script needs it to map a chunk back to a PDF page, and
    because a span that looks wrong is diagnosed by asking "where in the source
    did this chunk come from". When Act II needs it stored, that is an additive
    column, not a redesign.
    """

    index: int
    text: str
    doc_offset: int

    @property
    def char_count(self) -> int:
        return len(self.text)

    @property
    def doc_end(self) -> int:
        return self.doc_offset + len(self.text)


def chunk_document(text: str, *, max_chars: int = DEFAULT_MAX_CHARS) -> list[Chunk]:
    """Slice normalised text into chunks at the cleanest nearby boundary.

    Args:
        text: ALREADY normalised, from ``parser.parse_document``. Passing raw
            text here produces chunks that are not slices of what gets stored.
        max_chars: soft target per chunk.

    Returns:
        Chunks in document order, non-overlapping, each an exact slice of
        ``text``. Empty input yields an empty list rather than one empty chunk.
    """
    if not text:
        return []

    if max_chars < 1:
        raise ValueError("max_chars must be positive")

    chunks: list[Chunk] = []
    cursor = 0
    length = len(text)

    while cursor < length:
        # Skip whitespace between chunks. It belongs to neither, and letting a
        # chunk start with a newline would make every span in it off by one
        # relative to the sentence a human sees.
        while cursor < length and text[cursor].isspace():
            cursor += 1
        if cursor >= length:
            break

        remaining = length - cursor
        if remaining <= max_chars:
            piece = text[cursor:].rstrip()
            if piece:
                chunks.append(Chunk(index=len(chunks), text=piece, doc_offset=cursor))
            break

        split_at = _find_split(text, cursor, cursor + max_chars)
        piece = text[cursor:split_at].rstrip()

        if piece:
            chunks.append(Chunk(index=len(chunks), text=piece, doc_offset=cursor))

        # Guaranteed progress. _find_split never returns <= cursor, but an
        # assertion in a loop that could otherwise hang is cheap insurance.
        if split_at <= cursor:  # pragma: no cover - defensive
            logger.error("df_chunker_no_progress", cursor=cursor)
            break
        cursor = split_at

    logger.info(
        "df_chunked", chunk_count=len(chunks), char_count=length, max_chars=max_chars
    )
    return chunks


def _find_split(text: str, start: int, window_end: int) -> int:
    """Pick the cleanest boundary inside ``(start, window_end]``.

    Preference order, each searched backwards from the window end so the chunk
    stays as close to the target size as possible:

    1. **Paragraph break.** A section boundary in a government release; almost
       always also a topic boundary, so atoms do not straddle subjects.
    2. **Sentence end.** A claim is a sentence, and a span that stops mid
       sentence cannot support one.
    3. **Line break.** Table rows and list items.
    4. **Whitespace.** Avoids splitting a word, which would destroy an anchor.
    5. **Hard cut.** Only for text with no boundary at all in 1,200
       characters -- a minified blob or a very long table row. Progress matters
       more than elegance here.
    """
    floor = start + int((window_end - start) * _MIN_SPLIT_RATIO)

    paragraph = text.rfind(_PARAGRAPH_BREAK, floor, window_end)
    if paragraph > start:
        return paragraph + len(_PARAGRAPH_BREAK)

    # rfind has no regex equivalent, so scan matches and keep the last one that
    # lands inside the window.
    sentence = -1
    for match in _SENTENCE_END.finditer(text, floor, window_end):
        sentence = match.end()
    if sentence > start:
        return sentence

    line = text.rfind(_LINE_BREAK, floor, window_end)
    if line > start:
        return line + len(_LINE_BREAK)

    space = text.rfind(" ", floor, window_end)
    if space > start:
        return space + 1

    return window_end
