"""
engines/book_content/services/subtopic_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LLM Call #2 (subtopic discovery) and Call #5 (sub-subtopic discovery).
This is what defines the DEPTH of the knowledge book.
For complex topics flagged as [DEEP], it recurses one level further.
Ported from: upsc-agent-lab/src/subtopic_finder.py
Changes: logging (structlog), imports updated to local service paths.
Preserved exactly: all prompt builders, all parsers (_parse_subtopic_list,
                   _parse_string_list, _extract_json_array), all logic.
"""

import json

import structlog

from .llm_service import llm_call

logger = structlog.get_logger(__name__)


def find_subtopics(topic_name: str, ncert_text: str = None) -> list:
    """
    LLM Call #2: Discovers ALL subtopics under a main topic.

    Args:
        topic_name: e.g. "Parliament of India"
        ncert_text: Full cleaned NCERT chapter text (if available — Mode B)

    Returns:
        List of dicts:
        [
          {"name": "Composition of Parliament", "needs_deep": False, "source": "ncert"},
          {"name": "Powers of Parliament",       "needs_deep": True,  "source": "ncert"},
          {"name": "Anti-Defection Law",         "needs_deep": False, "source": "added"},
          ...
        ]
        - needs_deep=True means this subtopic gets sub-subtopics (Step 8)
        - source="ncert" found in chapter | source="added" not in NCERT but UPSC-critical
    """
    logger.info("subtopic_finder_start", topic_name=topic_name)

    if ncert_text:
        prompt = _build_ncert_subtopic_prompt(topic_name, ncert_text)
    else:
        prompt = _build_topic_subtopic_prompt(topic_name)

    response = llm_call(prompt, mode="standard")
    subtopics = _parse_subtopic_list(response)

    deep_count = sum(1 for s in subtopics if s["needs_deep"])
    logger.info(
        "subtopic_finder_done",
        topic_name=topic_name,
        count=len(subtopics),
        deep=deep_count,
    )
    for s in subtopics:
        logger.info(
            "subtopic_found",
            name=s["name"],
            needs_deep=s["needs_deep"],
            source=s.get("source"),
        )

    return subtopics


def find_sub_subtopics(subtopic_name: str, parent_topic: str) -> list:
    """
    LLM Call #5 (recursive): Discovers sub-subtopics for a [DEEP] subtopic.

    Args:
        subtopic_name: e.g. "Powers of the President"
        parent_topic:  e.g. "President of India" (for context)

    Returns:
        List of sub-subtopic name strings:
        ["Executive Powers", "Legislative Powers", "Judicial Powers", ...]
    """
    logger.info(
        "sub_subtopic_finder_start",
        subtopic_name=subtopic_name,
        parent_topic=parent_topic,
    )

    prompt = f"""You are a UPSC syllabus expert.

The subtopic "{subtopic_name}" (under "{parent_topic}") is complex and needs
to be broken down further for complete UPSC coverage.

List ALL sub-subtopics that belong under "{subtopic_name}".
Each sub-subtopic should be a specific, distinct concept — not a paraphrase.

Return ONLY a valid JSON array of strings. No explanation, no markdown:
["sub-subtopic 1", "sub-subtopic 2", "sub-subtopic 3", ...]

If "{subtopic_name}" does NOT need further subdivision, return an empty array: []"""

    response = llm_call(prompt, mode="standard")
    sub_subtopics = _parse_string_list(response)

    logger.info(
        "sub_subtopic_finder_done",
        subtopic_name=subtopic_name,
        count=len(sub_subtopics),
    )
    for ss in sub_subtopics:
        logger.info("sub_subtopic_found", name=ss)

    return sub_subtopics


# ── Prompt Builders ───────────────────────────────────────────────────────────


def _build_topic_subtopic_prompt(topic_name: str) -> str:
    return f"""You are a senior UPSC educator building a comprehensive study book.

List ALL subtopics required for a COMPLETE study of "{topic_name}" for UPSC.
Be exhaustive — include every concept a serious aspirant must know.

For each subtopic, decide:
  - "needs_deep": true if it is a complex concept with multiple sub-divisions
                  false if it stands alone as a single study unit
  - "source": "added" (this is what you're adding based on UPSC requirements)

Return ONLY a valid JSON array. No explanation, no markdown, no extra text:
[
  {{"name": "subtopic name", "needs_deep": false, "source": "added"}},
  {{"name": "complex subtopic", "needs_deep": true, "source": "added"}},
  ...
]"""


def _build_ncert_subtopic_prompt(topic_name: str, ncert_text: str) -> str:
    # Use full NCERT text (not truncated) — classifier already classified using first 1500 chars
    # Here we feed the full chapter for accurate subtopic extraction
    return f"""You are a senior UPSC educator building a comprehensive study book.

Analyze this complete NCERT chapter on "{topic_name}" and extract ALL subtopics.

NCERT CHAPTER TEXT:
\"\"\"
{ncert_text}
\"\"\"

Your tasks:
1. Extract EVERY distinct subtopic explicitly covered in the chapter above.
   Mark these with "source": "ncert"
2. Add any UPSC-critical subtopics NOT in the chapter but essential for exam completeness.
   Mark these with "source": "added"
3. Mark any complex subtopic with "needs_deep": true if it needs further sub-division
   (e.g., "Powers of Parliament" has Legislative, Financial, Judicial sub-powers —
    those need a level deeper)

Return ONLY a valid JSON array. No explanation, no markdown, no extra text:
[
  {{"name": "subtopic from chapter", "needs_deep": false, "source": "ncert"}},
  {{"name": "complex subtopic", "needs_deep": true, "source": "ncert"}},
  {{"name": "UPSC-critical addition", "needs_deep": false, "source": "added"}},
  ...
]"""


# ── Parsers ───────────────────────────────────────────────────────────────────


def _parse_subtopic_list(text: str) -> list:
    """Parses a JSON array of subtopic dicts from LLM response."""
    raw = _extract_json_array(text)
    if raw is None:
        logger.warning("subtopic_json_parse_failed", returning="empty list")
        return []

    result = []
    for item in raw:
        if isinstance(item, str):
            # LLM returned plain strings instead of dicts — normalize
            result.append({"name": item, "needs_deep": False, "source": "added"})
        elif isinstance(item, dict) and "name" in item:
            result.append(
                {
                    "name": str(item.get("name", "")).strip(),
                    "needs_deep": bool(item.get("needs_deep", False)),
                    "source": str(item.get("source", "added")),
                }
            )

    # Deduplicate by name (case-insensitive)
    seen = set()
    deduped = []
    for s in result:
        key = s["name"].lower()
        if key not in seen:
            seen.add(key)
            deduped.append(s)

    return deduped


def _parse_string_list(text: str) -> list:
    """Parses a JSON array of strings."""
    raw = _extract_json_array(text)
    if raw is None:
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def _extract_json_array(text: str):
    """Extracts a JSON array from potentially noisy LLM output."""
    # Direct parse
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except Exception:
        pass

    # Extract between first [ and last ]
    try:
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            result = json.loads(text[start:end])
            if isinstance(result, list):
                return result
    except Exception:
        pass

    return None
