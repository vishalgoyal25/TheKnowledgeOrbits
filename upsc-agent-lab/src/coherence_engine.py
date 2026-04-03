"""
src/coherence_engine.py
━━━━━━━━━━━━━━━━━━━━━━━
LAYER 3: Cross-Article Coherence

Runs AFTER all subtopic articles in a topic are generated.
Does three things:
  1. Detects duplicate content across articles (same fact in 3 places)
  2. Injects cross-references ("See: Rajya Sabha → Money Bills")
  3. Validates consistency (no contradictions between articles)

This is what makes a collection of articles feel like a BOOK
rather than a collection of isolated Wikipedia pages.
"""

import json
from src.llm_client import llm_call, log_info, log_warning
from src.database import get_db_connection
from src.book_planner import get_concept_registry


def run_coherence_pass(topic_id: int, topic_name: str, subject: str):
    """
    LAYER 3 ENTRY POINT.
    Call this after all subtopics of a topic are generated.

    Args:
        topic_id: DB node ID of the parent topic
        topic_name: e.g. "Parliament of India"
        subject: e.g. "Indian Constitution & Polity"
    """
    log_info(f"🔗 COHERENCE ENGINE: Running pass for '{topic_name}'...")

    # Fetch all subtopic articles for this topic
    subtopics = _fetch_subtopics(topic_id)
    if len(subtopics) < 2:
        log_info("   └─ Less than 2 subtopics — coherence pass skipped.")
        return

    concept_registry = get_concept_registry(subject)

    # Step 1: Detect and flag duplicates
    log_info(f"   Step 1: Duplicate detection across {len(subtopics)} articles...")
    duplicate_map = _detect_duplicates(subtopics)

    # Step 2: Inject cross-references
    log_info("   Step 2: Injecting cross-references...")
    _inject_cross_references(subtopics, concept_registry, duplicate_map)

    # Step 3: Consistency check (spot-check 3 pairs max — API cost control)
    log_info("   Step 3: Consistency validation...")
    _validate_consistency(subtopics[:3])

    log_info(f"   ✅ Coherence pass complete for '{topic_name}'")


def _fetch_subtopics(topic_id: int) -> list:
    """Fetches all subtopic nodes under a topic."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT n.id, n.label, n.content_body
        FROM nodes n
        JOIN edges e ON e.target_id = n.id
        WHERE e.source_id = %s AND n.type = 'subtopic'
        ORDER BY n.id
    """,
        (topic_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "label": r[1], "content": r[2] or ""} for r in rows]


def _detect_duplicates(subtopics: list) -> dict:
    """
    Detects which facts/definitions appear in multiple articles.
    Returns a map of {subtopic_id: [facts that appear elsewhere]}
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
):
    """
    For each subtopic article, finds concepts that are explained elsewhere
    and injects "See also: [concept] → [article]" references.
    Updates the article in DB.
    """
    conn = get_db_connection()
    cur = conn.cursor()

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
            if concept.lower() in content.lower() and data.get("node_id") != sub["id"]:
                refs_to_inject.append(
                    {
                        "concept": concept,
                        "target_label": data.get("node_label", concept),
                        "target_id": data.get("node_id"),
                    }
                )

        if not refs_to_inject:
            continue

        # Build cross-reference block
        ref_block = "\n\n---\n### See Also\n"
        for ref in refs_to_inject[:5]:  # Max 5 cross-refs per article
            ref_block += f"- **{ref['target_label']}** — covered in detail separately\n"

            # Save to cross_references table
            if ref.get("target_id"):
                try:
                    cur.execute(
                        """INSERT INTO cross_references
                           (source_node, target_node, ref_text, ref_type)
                           VALUES (%s, %s, %s, 'see_also')
                           ON CONFLICT (source_node, target_node) DO NOTHING""",
                        (sub["id"], ref["target_id"], ref["concept"]),
                    )
                except Exception:
                    pass

        # Append cross-references to article
        if ref_block and "### See Also" not in content:
            updated_content = content + ref_block
            cur.execute(
                "UPDATE nodes SET content_body = %s WHERE id = %s",
                (updated_content, sub["id"]),
            )

    conn.commit()
    conn.close()


def _validate_consistency(subtopics: list):
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
            log_warning("   ⚠️  Consistency issues detected:")
            for c in result.get("contradictions", []):
                log_warning(f"      • {c.get('fact', '')}")
    except Exception:
        pass
