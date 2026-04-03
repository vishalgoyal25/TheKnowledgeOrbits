"""
src/book_planner.py
━━━━━━━━━━━━━━━━━━━
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
"""

import json
from src.llm_client import llm_call, log_info, log_warning
from src.database import get_db_connection


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
    log_info(f"📚 BOOK PLANNER: Generating book plan for '{subject}'...")

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

    # Save to DB
    _save_book_plan(subject, book_plan)

    log_info(
        f"   ✅ Book plan created: {len(toc)} modules, "
        f"{sum(len(m.get('topics', [])) for m in toc)} topics"
    )
    return book_plan


def get_book_plan(subject: str) -> dict:
    """Retrieves existing book plan from DB. Returns None if not found."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT toc_json FROM book_plans WHERE subject = %s ORDER BY created_at DESC LIMIT 1",
        (subject,),
    )
    row = cur.fetchone()
    conn.close()
    if row:
        return row[0]
    return None


def update_concept_registry(
    subject: str, concept_name: str, node_id: int, node_label: str
):
    """
    Called after each article is generated.
    Registers what concept is explained in which node.
    This is what enables cross-references in Layer 3.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT toc_json, concept_registry FROM book_plans "
        "WHERE subject = %s ORDER BY created_at DESC LIMIT 1",
        (subject,),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return

    toc_json, registry = row
    if not isinstance(registry, dict):
        registry = {}

    registry[concept_name.lower()] = {"node_id": node_id, "node_label": node_label}

    cur.execute(
        "UPDATE book_plans SET concept_registry = %s WHERE subject = %s",
        (json.dumps(registry), subject),
    )
    conn.commit()
    conn.close()


def get_concept_registry(subject: str) -> dict:
    """Returns the concept registry for cross-reference injection."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT concept_registry FROM book_plans WHERE subject = %s "
        "ORDER BY created_at DESC LIMIT 1",
        (subject,),
    )
    row = cur.fetchone()
    conn.close()
    if row and row[0]:
        return row[0] if isinstance(row[0], dict) else {}
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
        log_warning("   ⚠️  Failed to generate master TOC. Plan will be limited.")
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


def _save_book_plan(subject: str, book_plan: dict):
    """Saves book plan to DB."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO book_plans (subject, toc_json, concept_registry)
           VALUES (%s, %s, %s)
           ON CONFLICT DO NOTHING""",
        (
            subject,
            json.dumps(book_plan["toc"]),
            json.dumps(book_plan["concept_registry"]),
        ),
    )
    conn.commit()
    conn.close()


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
    log_warning("Book planner: JSON list parse failed.")
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
