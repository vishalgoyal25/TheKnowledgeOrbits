"""
engines/book_content/services/classifier_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LLM Call #1 in the Deep Content Engine.
Determines WHERE in the UPSC syllabus a topic or chapter belongs.

PRIORITY ORDER:
  1. Check cross_subject_map first (instant, zero LLM call, zero hallucination)
  2. Fall back to LLM classification for unknown topics

Returns: { "subject", "module", "confirmed_topic", "secondary_subjects" }
Ported from: upsc-agent-lab/src/classifier.py
Changes: logging (structlog), imports updated to local service paths.
Preserved exactly: prompt builders, JSON parsing fallback, validation logic.
"""

import json
from typing import Optional

import structlog

from .cross_subject_map import SUBJECTS, fuzzy_lookup
from .llm_service import llm_call

logger = structlog.get_logger(__name__)

# ── UPSC Syllabus Subjects (canonical names — must match cross_subject_map.py) ─
UPSC_SUBJECTS = list(SUBJECTS.values())


def classify_hierarchy(
    topic_name: Optional[str] = None, ncert_text: Optional[str] = None
) -> dict:
    """
    LLM Call #1 (or instant map lookup): Places a topic in the UPSC hierarchy.

    Args:
        topic_name: Direct topic string (Mode A — no PDF)
        ncert_text: First ~1500 chars of cleaned NCERT chapter (Mode B — PDF)

    Returns:
        {
          "subject":            "Indian Constitution & Polity",
          "module":             "Union Legislature",
          "confirmed_topic":    "Parliament of India",
          "secondary_subjects": ["Governance & Social Justice"]
        }
    """
    logger.info("classifier_start", topic_name=topic_name)

    # ── Priority 1: Map Lookup (instant, no LLM cost) ─────────────────────────
    if topic_name:
        map_entry = fuzzy_lookup(topic_name)
        if map_entry:
            result = {
                "subject": map_entry["primary_subject"],
                "module": map_entry["module"],
                "confirmed_topic": topic_name,
                "secondary_subjects": map_entry.get("secondary_subjects", []),
            }
            logger.info(
                "classifier_map_hit", subject=result["subject"], module=result["module"]
            )
            if result["secondary_subjects"]:
                logger.info(
                    "classifier_cross_subject", spans=result["secondary_subjects"]
                )
            return result

    # ── Priority 2: LLM Classification (for unknown topics or PDF mode) ───────
    logger.info("classifier_llm_fallback", topic_name=topic_name)
    if ncert_text:
        prompt = _build_ncert_prompt(ncert_text[:1500])
    else:
        prompt = _build_topic_prompt(topic_name or "")

    response = llm_call(prompt, mode="standard")
    result = _parse_json(response)

    # Validate subject against known list (prevent hallucinated subject names)
    if result.get("subject") not in UPSC_SUBJECTS:
        resp_lower = result.get("subject", "").lower()
        for known in UPSC_SUBJECTS:
            if any(w in resp_lower for w in known.lower().split() if len(w) > 4):
                result["subject"] = known
                break
        else:
            logger.warning(
                "classifier_unknown_subject",
                defaulting_to="Indian Constitution & Polity",
            )
            result["subject"] = "Indian Constitution & Polity"

    # Ensure all keys exist
    if not result.get("confirmed_topic"):
        result["confirmed_topic"] = topic_name or "Unknown Topic"
    if not result.get("secondary_subjects"):
        result["secondary_subjects"] = []

    logger.info(
        "classifier_llm_success", subject=result["subject"], module=result["module"]
    )
    if result["secondary_subjects"]:
        logger.info("classifier_cross_subject", spans=result["secondary_subjects"])

    return result


# ── Prompt Builders ───────────────────────────────────────────────────────────


def _build_topic_prompt(topic_name: str) -> str:
    return f"""You are a UPSC Civil Services Examination syllabus expert.

Determine the exact place of this topic in the UPSC syllabus:
Topic: "{topic_name}"

Available top-level subjects (use EXACT wording):
{chr(10).join(f"  - {s}" for s in UPSC_SUBJECTS)}

Also identify if this topic SPANS multiple subjects (cross-subject topics
like Budget, Climate Change, etc. typically appear in 2-3 subjects).

Return ONLY a valid JSON object. No explanation, no markdown:
{{
  "subject": "primary subject from the list above (exact wording)",
  "module": "specific module within that subject (2-5 words)",
  "confirmed_topic": "{topic_name}",
  "secondary_subjects": ["other subject if cross-subject", "..."]
}}

If the topic belongs to only one subject, set secondary_subjects to [].
"""


def _build_ncert_prompt(ncert_excerpt: str) -> str:
    return f"""You are a UPSC Civil Services Examination syllabus expert.

Analyze this excerpt from an NCERT chapter and determine its place in the UPSC syllabus:

NCERT EXCERPT:
\"\"\"
{ncert_excerpt}
\"\"\"

Available top-level subjects (use EXACT wording):
{chr(10).join(f"  - {s}" for s in UPSC_SUBJECTS)}

Return ONLY a valid JSON object. No explanation, no markdown:
{{
  "subject": "primary subject from the list above (exact wording)",
  "module": "specific module within that subject (2-5 words)",
  "confirmed_topic": "the main topic of this chapter (3-6 words)",
  "secondary_subjects": ["other subject if cross-subject", "..."]
}}

If the chapter belongs to only one subject, set secondary_subjects to [].
"""


# ── JSON Parser ───────────────────────────────────────────────────────────────


def _parse_json(text: str) -> dict:
    """Robustly extracts JSON dict from LLM response."""
    for attempt in [
        text,
        text[text.find("{") : text.rfind("}") + 1] if "{" in text else "",
    ]:
        try:
            result = json.loads(attempt)
            if isinstance(result, dict):
                return result
        except Exception:
            pass
    logger.warning("classifier_json_parse_failed", using="safe defaults")
    return {
        "subject": "Indian Constitution & Polity",
        "module": "General Topics",
        "confirmed_topic": "",
        "secondary_subjects": [],
    }
