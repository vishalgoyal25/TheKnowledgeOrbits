"""
engines/book_content/services/book_planner_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAYER 1: Book Intelligence
Runs ONCE per subject before any article generation begins.

What it does:
  1. Generates complete Table of Contents for a subject
  2. Defines logical reading order and prerequisite chains
  3. Creates concept registry (tracks what's explained where)
  4. Stores book_plan in DB for all subsequent generation to reference

Why this matters:
  Without this, every article is generated in isolation.
  With this, each article knows what came before and what comes after.
  This is what creates Laxmikanth-style progressive depth.
Ported from: upsc-agent-lab/src/book_planner.py
Changes: logging (structlog), imports, ALL DB ops replaced with Django ORM.
Preserved exactly: TOC generation prompt, prerequisite chains prompt,
                   _flatten_reading_order(), _build_initial_concept_registry(),
                   get_previously_covered_concepts() logic.
"""

import json

import sentry_sdk
import structlog

from engines.book_content.models import BookPlan
from engines.knowledge.models import Subject

from .llm_service import llm_call

logger = structlog.get_logger(__name__)


def generate_book_plan(subject: str, modules: list) -> dict:
    """
    LAYER 1 ENTRY POINT.
    Call this ONCE before ingesting any topic in a subject.

    Args:
        subject: e.g. "Indian Constitution & Polity"
        modules: list of module names in this subject
                 e.g. ["Union Legislature", "Union Executive", ...]

    Returns:
        book_plan dict with toc, reading_order, concept_registry
    """
    logger.info("book_planner_start", subject=subject)

    # Step 1: Generate full TOC
    toc = _generate_toc(subject, modules)

    # Step 2: Define prerequisite chains
    prereq_chains = _generate_prerequisite_chains(subject, toc)

    # Step 3: Build initial concept registry (populated as articles are generated)
    concept_registry = _build_initial_concept_registry(toc)

    book_plan = {
        "subject": subject,
        "toc": toc,
        "prerequisite_chains": prereq_chains,
        "concept_registry": concept_registry,
        "reading_order": _flatten_reading_order(toc),
    }

    # Save to DB via Django ORM
    _save_book_plan(subject, book_plan)

    topic_count = sum(len(m.get("topics", [])) for m in toc)
    logger.info(
        "book_planner_done", subject=subject, modules=len(toc), topics=topic_count
    )
    return book_plan


def get_book_plan(subject_name: str) -> dict | None:
    """Retrieves existing book plan from DB. Returns None if not found."""
    try:
        plan = BookPlan.objects.filter(subject__name=subject_name).first()
        if plan:
            return plan.toc_json
        return None
    except Exception as e:
        logger.error("get_book_plan_failed", subject=subject_name, error=str(e))
        sentry_sdk.capture_exception(e)
        return None


def update_concept_registry(
    subject_name: str, concept_name: str, topic_id: str, topic_label: str
) -> None:
    """
    Called after each article is generated.
    Registers what concept is explained in which node.
    This is what enables cross-references in Layer 3.
    """
    try:
        plan = BookPlan.objects.filter(subject__name=subject_name).first()
        if not plan:
            logger.warning("update_concept_registry_no_plan", subject=subject_name)
            return

        registry = (
            plan.concept_registry if isinstance(plan.concept_registry, dict) else {}
        )
        registry[concept_name.lower()] = {
            "topic_id": topic_id,
            "node_label": topic_label,
        }
        plan.concept_registry = registry
        plan.save(update_fields=["concept_registry", "updated_at"])
        logger.info(
            "concept_registry_updated", subject=subject_name, concept=concept_name
        )

    except Exception as e:
        logger.error(
            "update_concept_registry_failed", subject=subject_name, error=str(e)
        )
        sentry_sdk.capture_exception(e)


def get_concept_registry(subject_name: str) -> dict:
    """Returns the concept registry for cross-reference injection."""
    try:
        plan = BookPlan.objects.filter(subject__name=subject_name).first()
        if plan and plan.concept_registry:
            return (
                plan.concept_registry if isinstance(plan.concept_registry, dict) else {}
            )
        return {}
    except Exception as e:
        logger.error("get_concept_registry_failed", subject=subject_name, error=str(e))
        sentry_sdk.capture_exception(e)
        return {}


def get_previously_covered_concepts(subject: str, current_topic: str) -> str:
    """
    Returns a summary string of what concepts have already been covered
    in previously generated articles within this subject.
    Used in article generation prompts to prevent repetition.
    """
    registry = get_concept_registry(subject)
    if not registry:
        return ""

    covered = [
        label
        for concept, data in registry.items()
        if data
        for label in [data.get("node_label", concept)]
        if data.get("node_label", "").lower() != current_topic.lower()
    ]

    if not covered:
        return ""

    # Return as a compact summary string (not full articles — just concept names)
    return (
        "CONCEPTS ALREADY COVERED IN PREVIOUS CHAPTERS "
        "(do NOT re-explain these from scratch — reference them briefly):\n"
        + "\n".join(f"  • {c}" for c in covered[:30])  # Cap at 30 to save tokens
    )


# ── Internal Functions ────────────────────────────────────────────────────────


def _generate_toc(subject: str, modules: list) -> list:
    """LLM Call: Generates complete TOC for a subject."""
    prompt = f"""You are building a comprehensive UPSC study book on "{subject}".
This book must be as complete as M. Laxmikanth's Indian Polity.

The book has these modules:
{chr(10).join(f"  {i+1}. {m}" for i, m in enumerate(modules))}

For EACH module, list ALL topics it must contain for complete UPSC coverage.
For each topic, list ALL subtopics that must be covered.

Return ONLY valid JSON. No explanation:
[
  {{
    "module": "module name",
    "order": 1,
    "topics": [
      {{
        "name": "topic name",
        "order": 1,
        "subtopics": ["subtopic 1", "subtopic 2", "subtopic 3"],
        "prerequisites": ["earlier topic name if any"]
      }}
    ]
  }}
]"""
    response = llm_call(
        prompt, mode="writer"
    )  # UPGRADED: Needs more tokens for full subject TOC
    toc = _parse_json_list(response) or []

    if not toc:
        logger.warning("book_planner_toc_failed", subject=subject)
        return []
    return toc


def _generate_prerequisite_chains(subject: str, toc: list) -> dict:
    """LLM Call: Maps what each topic requires as prior knowledge."""
    all_topics = []
    for module in toc:
        for topic in module.get("topics", []):
            all_topics.append(topic["name"])

    if not all_topics:
        return {}

    prompt = f"""For the UPSC subject "{subject}", map prerequisite knowledge chains.

Topics in this book:
{chr(10).join(f"  {i+1}. {t}" for i, t in enumerate(all_topics))}

For each topic, list which OTHER topics from this list must be read first
for a student to fully understand it.

Return ONLY valid JSON:
{{
  "topic name": ["prerequisite topic 1", "prerequisite topic 2"],
  "another topic": []
}}

Only list STRONG prerequisites (not just "helpful to know").
If a topic has no prerequisites, set it to [].
"""
    response = llm_call(prompt, mode="standard")
    return _parse_json_dict(response) or {}


def _build_initial_concept_registry(toc: list) -> dict:
    """Builds initial empty registry from TOC — populated as articles generate."""
    registry = {}
    for module in toc:
        for topic in module.get("topics", []):
            for subtopic in topic.get("subtopics", []):
                registry[subtopic.lower()] = None  # None = not yet generated
    return registry


def _flatten_reading_order(toc: list) -> list:
    """Creates flat reading order list from TOC tree."""
    order = []
    for module in sorted(toc, key=lambda m: m.get("order", 99)):
        for topic in sorted(module.get("topics", []), key=lambda t: t.get("order", 99)):
            order.append(
                {
                    "module": module["module"],
                    "topic": topic["name"],
                    "prerequisites": topic.get("prerequisites", []),
                }
            )
    return order


def _save_book_plan(subject_name: str, book_plan: dict) -> None:
    """Saves book plan to DB via Django ORM."""
    try:
        subject_obj = Subject.objects.filter(name=subject_name).first()
        if not subject_obj:
            logger.warning("book_planner_subject_not_found", subject=subject_name)
            return

        toc = book_plan.get("toc", [])
        topic_count = sum(len(m.get("topics", [])) for m in toc)

        BookPlan.objects.update_or_create(
            subject=subject_obj,
            defaults={
                "toc_json": book_plan.get("toc", []),
                "concept_registry": book_plan.get("concept_registry", {}),
                "prerequisite_chains": book_plan.get("prerequisite_chains", {}),
                "reading_order": book_plan.get("reading_order", []),
                "generation_status": "planned",
                "topics_planned": topic_count,
            },
        )
        logger.info("book_plan_saved", subject=subject_name, topics_planned=topic_count)

    except Exception as e:
        logger.error("book_plan_save_failed", subject=subject_name, error=str(e))
        sentry_sdk.capture_exception(e)


def _parse_json_list(text: str) -> list:
    for attempt in [
        text,
        text[text.find("[") : text.rfind("]") + 1] if "[" in text else "",
    ]:
        try:
            result = json.loads(attempt)
            if isinstance(result, list):
                return result
        except Exception:
            pass
    logger.warning("book_planner_json_list_parse_failed")
    return []


def _parse_json_dict(text: str) -> dict:
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
    return {}
