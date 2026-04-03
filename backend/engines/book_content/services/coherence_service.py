"""
engines/book_content/services/coherence_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAYER 3: Cross-Article Coherence

Runs AFTER all subtopic articles in a topic are generated.
Does three things:
  1. Detects duplicate content across articles (same fact in 3 places)
  2. Injects cross-references ("See: Rajya Sabha → Money Bills")
  3. Validates consistency (no contradictions between articles)

This is what makes a collection of articles feel like a BOOK
rather than a collection of isolated Wikipedia pages.
Ported from: upsc-agent-lab/src/coherence_engine.py
Changes: logging (structlog), imports, ALL DB ops replaced with Django ORM.
Preserved exactly: duplicate detection prompts, overlap detection prompts,
                   consistency validation prompt, all algorithm logic.
"""

import json

import sentry_sdk
import structlog
from django.db import transaction

from engines.book_content.models import BookContent, CrossReference

from .book_planner_service import get_concept_registry
from .llm_service import llm_call

logger = structlog.get_logger(__name__)


def run_coherence_pass(topic_id: str, topic_name: str, subject_name: str) -> None:
    """
    LAYER 3 ENTRY POINT.
    Call this after all subtopics of a topic are generated.

    Args:
        topic_id:    UUID of the parent topic node (knowledge_topic.id)
        topic_name:  e.g. "Parliament of India"
        subject_name: e.g. "Indian Constitution & Polity"
    """
    logger.info("coherence_engine_start", topic_name=topic_name, subject=subject_name)

    # Fetch all subtopic articles for this topic
    subtopics = _fetch_subtopics(topic_id)
    if len(subtopics) < 2:
        logger.info(
            "coherence_engine_skipped",
            topic_name=topic_name,
            reason="less_than_2_subtopics",
        )
        return

    concept_registry = get_concept_registry(subject_name)

    # Step 1: Detect and flag duplicates
    logger.info(
        "coherence_duplicate_detection_start",
        topic_name=topic_name,
        subtopic_count=len(subtopics),
    )
    duplicate_map = _detect_duplicates(subtopics)

    # Step 2: Inject cross-references
    logger.info("coherence_cross_ref_injection_start", topic_name=topic_name)
    _inject_cross_references(subtopics, concept_registry, duplicate_map)

    # Step 3: Consistency check (spot-check 3 pairs max — API cost control)
    logger.info("coherence_consistency_check_start", topic_name=topic_name)
    _validate_consistency(subtopics[:3])

    logger.info("coherence_engine_done", topic_name=topic_name)


def _fetch_subtopics(topic_id: str) -> list:
    """Fetches all subtopic BookContent records under a parent topic."""
    try:
        contents = (
            BookContent.objects.filter(topic__parent_topic_id=topic_id)
            .select_related("topic")
            .order_by("topic__order_index")
        )

        return [
            {
                "id": str(bc.id),
                "topic_id": str(bc.topic.id),
                "label": bc.topic.name,
                "content": bc.content_markdown or "",
            }
            for bc in contents
        ]
    except Exception as e:
        logger.error(
            "coherence_fetch_subtopics_failed", topic_id=topic_id, error=str(e)
        )
        sentry_sdk.capture_exception(e)
        return []


def _detect_duplicates(subtopics: list) -> dict:
    """
    Detects which facts/definitions appear in multiple articles.
    Returns a map of {content_id: [facts that appear elsewhere]}
    """
    if len(subtopics) < 2:
        return {}

    # Build summaries of key facts per article (to avoid massive token usage)
    summaries = []
    for sub in subtopics[:10]:  # Cap at 10 for API cost
        summary_prompt = f"""Extract the 5 most important specific facts from this article.
Each fact: one sentence, precise (include numbers, articles, years).
Return as JSON array of strings:

ARTICLE: {sub['content'][:2000]}

Return ONLY JSON array:"""
        response = llm_call(summary_prompt, mode="standard")
        try:
            facts = json.loads(response)
            if isinstance(facts, list):
                summaries.append(
                    {"id": sub["id"], "label": sub["label"], "facts": facts}
                )
        except Exception:
            summaries.append({"id": sub["id"], "label": sub["label"], "facts": []})

    # Now find overlapping facts
    duplicate_map = {}
    for i, sub_a in enumerate(summaries):
        for sub_b in summaries[i + 1 :]:
            overlap_prompt = f"""Compare these two fact lists. Which facts are essentially the SAME
(same information, even if worded differently)?

Article A ({sub_a['label']}):
{json.dumps(sub_a['facts'])}

Article B ({sub_b['label']}):
{json.dumps(sub_b['facts'])}

Return ONLY JSON array of duplicate facts (from Article A's perspective):
["fact that appears in both", ...]
If no duplicates: []"""
            response = llm_call(overlap_prompt, mode="standard")
            try:
                overlaps = json.loads(response)
                if overlaps and isinstance(overlaps, list):
                    if sub_a["id"] not in duplicate_map:
                        duplicate_map[sub_a["id"]] = []
                    duplicate_map[sub_a["id"]].extend(overlaps)
            except Exception:
                pass

    return duplicate_map


def _inject_cross_references(
    subtopics: list, concept_registry: dict, duplicate_map: dict
) -> None:
    """
    For each subtopic article, finds concepts that are explained elsewhere
    and injects "See also: [concept] → [article]" references.
    Updates the article in DB via Django ORM.
    """
    for sub in subtopics[:10]:  # Cap for API cost
        content = sub["content"]
        if not content:
            continue

        # Find concepts in this article that are covered in other articles
        refs_to_inject = []
        for concept, data in concept_registry.items():
            if data is None:
                continue
            # Check if concept is mentioned in this article but not its home article
            if (
                concept.lower() in content.lower()
                and data.get("topic_id") != sub["topic_id"]
            ):
                refs_to_inject.append(
                    {
                        "concept": concept,
                        "target_label": data.get("node_label", concept),
                        "target_id": data.get("topic_id"),
                    }
                )

        if not refs_to_inject:
            continue

        # Build cross-reference block
        ref_block = "\n\n---\n### See Also\n"
        for ref in refs_to_inject[:5]:  # Max 5 cross-refs per article
            ref_block += f"- **{ref['target_label']}** — covered in detail separately\n"

            # Save to knowledge_cross_reference table via ORM
            if ref.get("target_id"):
                try:
                    source_bc = BookContent.objects.filter(id=sub["id"]).first()
                    target_bc = BookContent.objects.filter(
                        topic_id=ref["target_id"]
                    ).first()

                    if source_bc and target_bc:
                        with transaction.atomic():
                            CrossReference.objects.get_or_create(
                                source_content=source_bc,
                                target_content=target_bc,
                                defaults={
                                    "ref_type": "see_also",
                                    "ref_text": ref["concept"],
                                    "display_label": f"{sub['label']} → {ref['target_label']}",
                                },
                            )
                except Exception as e:
                    logger.warning(
                        "coherence_crossref_save_failed",
                        source=sub["id"],
                        target=ref["target_id"],
                        error=str(e),
                    )
                    sentry_sdk.capture_exception(e)

        # Append cross-references to article in DB
        if ref_block and "### See Also" not in content:
            try:
                updated_content = content + ref_block
                BookContent.objects.filter(id=sub["id"]).update(
                    content_markdown=updated_content
                )
            except Exception as e:
                logger.error(
                    "coherence_article_update_failed", id=sub["id"], error=str(e)
                )
                sentry_sdk.capture_exception(e)


def _validate_consistency(subtopics: list) -> None:
    """
    Spot-checks pairs of articles for factual contradictions.
    Logs warnings but does NOT auto-correct (human review needed).
    """
    if len(subtopics) < 2:
        return

    # Check first pair only (API cost control)
    sub_a = subtopics[0]
    sub_b = subtopics[1]

    prompt = f"""Compare these two UPSC study articles for factual contradictions.
A contradiction = Article A states X but Article B states NOT-X about the same fact.

Article A ({sub_a['label']}): {sub_a['content'][:1500]}
Article B ({sub_b['label']}): {sub_b['content'][:1500]}

Return ONLY JSON:
{{
  "contradictions": [
    {{"fact": "description of contradiction", "article_a_says": "...", "article_b_says": "..."}}
  ],
  "verdict": "consistent" or "has_issues"
}}
If no contradictions: {{"contradictions": [], "verdict": "consistent"}}"""

    response = llm_call(prompt, mode="standard")
    try:
        result = json.loads(response)
        if result.get("verdict") == "has_issues":
            logger.warning(
                "coherence_consistency_issues_detected",
                article_a=sub_a["label"],
                article_b=sub_b["label"],
            )
            for c in result.get("contradictions", []):
                logger.warning("coherence_contradiction", fact=c.get("fact", ""))
    except Exception:
        pass
