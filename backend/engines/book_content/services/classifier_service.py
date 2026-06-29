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
# NOTE: this static list is STALE — it carries only 9 names, several mis-spelled,
# and is missing whole seeded subjects (Ethics, Geography, Heritage, Economy,
# Society, Modern/World History). It is kept ONLY as an offline fallback.
# Validation now uses _seeded_subject_names() (the live DB) — see Phase 6.
UPSC_SUBJECTS = list(SUBJECTS.values())

# Phase 6 — cache of the ACTUAL seeded Subject names, loaded once per process.
_SUBJECT_NAME_CACHE: dict = {"names": []}


def _seeded_subject_names() -> list:
    """Return the live seeded Subject names (cached per process).

    This is the authoritative whitelist for validating a classified subject.
    Falls back to the stale static map ONLY if the DB is unreachable, so an
    offline/edge call never crashes.
    """
    if _SUBJECT_NAME_CACHE["names"]:
        return _SUBJECT_NAME_CACHE["names"]
    try:
        from engines.knowledge.models import Subject

        names = list(Subject.objects.values_list("name", flat=True))
        if names:
            _SUBJECT_NAME_CACHE["names"] = names
            return names
    except Exception as exc:
        logger.warning("classifier_subject_list_load_failed", error=str(exc)[:120])
    return UPSC_SUBJECTS


def _load_seeded_hierarchy() -> str:
    """
    Queries the live DB for all seeded subjects and their modules.
    Returns a formatted string for injection into the LLM classifier prompt.

    Format:
      Subject: Indian Polity & Constitution
        - Union Legislature
        - Union Executive
        - Union Judiciary
        ...

    Cached per-process in _HIERARCHY_CACHE so the DB is only queried once
    per worker restart (subjects/modules don't change at runtime).
    """
    if _HIERARCHY_CACHE["text"]:
        return _HIERARCHY_CACHE["text"]

    try:
        from engines.knowledge.models import Module, Subject

        lines = ["EXACT subject and module names seeded in the database:"]
        subjects = Subject.objects.prefetch_related("modules").order_by("name")

        for subj in subjects:
            lines.append(f"\nSubject: {subj.name}")
            modules = Module.objects.filter(subject=subj).order_by("name")
            for mod in modules:
                lines.append(f"  - {mod.name}")

        text = "\n".join(lines)
        _HIERARCHY_CACHE["text"] = text
        return text

    except Exception as exc:
        logger.warning("classifier_hierarchy_load_failed", error=str(exc)[:120])
        # Fallback: just list subject names from cross_subject_map
        lines = ["Available subjects (exact wording):"]
        for s in UPSC_SUBJECTS:
            lines.append(f"  - {s}")
        return "\n".join(lines)


# Module-level cache — populated on first LLM call, reused for all subsequent calls.
_HIERARCHY_CACHE: dict = {"text": ""}


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
          "subject":            "Indian Polity & Constitution",
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

    # Validate subject against the ACTUAL seeded subjects (Phase 6).
    # Previously this checked the stale static list and, on no match, FORCE-set
    # the subject to "Indian Polity & Constitution" — which silently mis-routed
    # entire subjects (Ethics/Geography/Economy/Heritage) to Polity, then failed
    # module resolution → skip → empty-complete. Now: if the LLM's subject isn't
    # an exact seeded name, try word-overlap against the SEEDED names; if still
    # no match, KEEP the LLM's answer and let the downstream strict resolver
    # (_get_subject_strict) fuzzy-match or raise a clean skip. No blind default.
    seeded_subjects = _seeded_subject_names()
    if result.get("subject") not in seeded_subjects:
        resp_lower = result.get("subject", "").lower()
        for known in seeded_subjects:
            if any(w in resp_lower for w in known.lower().split() if len(w) > 4):
                result["subject"] = known
                break
        else:
            logger.warning(
                "classifier_unknown_subject",
                llm_subject=result.get("subject"),
                note="kept as-is; strict resolver will fuzzy-match or skip",
            )

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
    hierarchy = _load_seeded_hierarchy()
    return f"""You are a UPSC Civil Services Examination syllabus expert.

Determine the exact place of this topic in the UPSC syllabus:
Topic: "{topic_name}"

{hierarchy}

CRITICAL RULES — you MUST follow these without exception:
1. Use ONLY the subject names listed above. Copy the name character-for-character.
2. Use ONLY the module names listed under your chosen subject. Copy exactly.
3. Do NOT invent new subject or module names. Do NOT paraphrase or rename.
4. If you are unsure of the module, pick the closest existing module name from the list.

Also identify if this topic SPANS multiple subjects (cross-subject topics
like Budget, Climate Change, etc. typically appear in 2-3 subjects).

Return ONLY a valid JSON object. No explanation, no markdown:
{{
  "subject": "EXACT subject name from the list above",
  "module": "EXACT module name from the list above",
  "confirmed_topic": "{topic_name}",
  "secondary_subjects": ["other subject if cross-subject", "..."]
}}

If the topic belongs to only one subject, set secondary_subjects to [].
"""


def _build_ncert_prompt(ncert_excerpt: str) -> str:
    hierarchy = _load_seeded_hierarchy()
    return f"""You are a UPSC Civil Services Examination syllabus expert.

Analyze this excerpt from an NCERT chapter and determine its place in the UPSC syllabus:

NCERT EXCERPT:
\"\"\"
{ncert_excerpt}
\"\"\"

{hierarchy}

CRITICAL RULES — you MUST follow these without exception:
1. Use ONLY the subject names listed above. Copy the name character-for-character.
2. Use ONLY the module names listed under your chosen subject. Copy exactly.
3. Do NOT invent new subject or module names. Do NOT paraphrase or rename.
4. If you are unsure of the module, pick the closest existing module name from the list.

Return ONLY a valid JSON object. No explanation, no markdown:
{{
  "subject": "EXACT subject name from the list above",
  "module": "EXACT module name from the list above",
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
        "subject": "Indian Polity & Constitution",
        "module": "General Topics",
        "confirmed_topic": "",
        "secondary_subjects": [],
    }
