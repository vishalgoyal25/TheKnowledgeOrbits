"""
engines/assessment/services/daily_quiz_prompt_builder.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Prompt builder for the Daily Public Quiz pipeline.

Architecture role: Pure string-builder — zero DB access, zero LLM calls, zero network.
Called by: DailyQuizGeneratorService._build_question_for_proposal()

Source material used (NO NCERT/static chunks involved here):
  1. NEWS HOOK      — Today's enriched CA chunk text (scraped articles)
  2. WIKI REFERENCE — Wikipedia background for the topic (conceptual depth)
  3. SOURCE URLS    — Original news article URLs for explanation attribution

Question diversity:
  • Multi-statement   (3–5 statements, any combination of T/F)
  • Assertion-Reason  (A & R pair, 4 standard options)
  • Single Best Answer (direct MCQ, one clearly correct option)
  • Match-the-following style (items ↔ descriptions in statement text)
  All question types are valid; the LLM picks the best fit for the source material.

JSON contract returned by llm_call_json:
  {
    "question_text": "...",
    "question_type": "multi_statement" | "assertion_reasoning" | "single_mcq",
    "statements": ["...", "...", ...],   // list[str]; empty for single_mcq
    "options":    {"A": "...", "B": "...", "C": "...", "D": "..."},
    "correct_answer": "A"|"B"|"C"|"D",
    "explanation": "..."                 // statement-by-statement + source URL
  }
"""

# ── Subject-specific framing hints ───────────────────────────────────────────
# Tells the LLM what angle/depth to test for each GS subject.

_SUBJECT_QUIZ_HINT: dict[str, str] = {
    "Indian Polity & Constitution": (
        "Angle: constitutional provisions, landmark judgements, amendment history, "
        "Centre-State relations, electoral process, parliamentary procedures. "
        "Mix current political/legal news with constitutional framework knowledge."
    ),
    "Indian Economy": (
        "Angle: fiscal/monetary policy mechanics, RBI/SEBI/NABARD mandates, "
        "scheme eligibility, budget allocation, trade data, inflation indices. "
        "Combine today's economic news with underlying economic principles."
    ),
    "Environment & Ecology": (
        "Angle: international conventions (CITES, Ramsar, CBD, Paris Agreement), "
        "biodiversity zones, pollution norms, climate targets, protected area "
        "categories, species classification. Link news event to convention/treaty."
    ),
    "International Relations": (
        "Angle: bilateral/multilateral agreements, India's treaty obligations, "
        "grouping memberships (QUAD, SCO, BRICS, G20), UN body mandates, "
        "geopolitical implications. Test India's specific diplomatic position."
    ),
    "Science & Technology": (
        "Angle: mission parameters, technology specs, ISRO/DRDO/DST mandates, "
        "recent launches, discoveries, India-specific R&D. Mix technical detail "
        "with policy/institutional background."
    ),
    "Indian Society": (
        "Angle: demographic data, social welfare legislation, gender/SC/ST "
        "constitutional protections, National Policy targets, census figures. "
        "Connect current social news to legislative/constitutional framework."
    ),
    "Indian Heritage & Culture": (
        "Angle: UNESCO heritage criteria, classical art form origins, regional "
        "attribution, ancient text connections, festival-region links. "
        "Test precision of attribution and historical accuracy."
    ),
    "Modern Indian History": (
        "Angle: chronology of events, session/act dates, leadership roles, "
        "outcomes of specific negotiations or battles. Use a news anniversary "
        "or current commemoration as the hook."
    ),
    "Indian & World Geography": (
        "Angle: river systems, watershed boundaries, mineral/resource distribution, "
        "climate zones, strategic passes and waterways. Connect a geographic "
        "news event to physical/political geography facts."
    ),
    "World History": (
        "Angle: treaty provisions, revolution causes, colonial policy impacts, "
        "ideological differences, post-WW2 institutional origins. "
        "Use current geopolitical parallels as the news hook."
    ),
    "Governance & Social Justice": (
        "Angle: scheme coverage rules, eligibility criteria, implementing ministry, "
        "beneficiary targets, RTI/grievance mechanisms. Test precise scheme details "
        "against a recent governance news event."
    ),
    "Disaster Management": (
        "Angle: NDMA guidelines, Sendai Framework targets (2015–2030), early "
        "warning systems, vulnerability indices, state relief norms. "
        "Link a recent disaster event to the policy/institutional response."
    ),
    "Internal Security": (
        "Angle: UAPA/NSA provisions, border management agencies, cyber security "
        "framework, terror-financing conventions, Left Wing Extremism policy. "
        "Test legal provisions against a recent security news event."
    ),
    "Ethics Integrity & Aptitude": (
        "Angle: ethical frameworks (deontology, consequentialism, virtue ethics), "
        "constitutional values, public service codes, whistle-blower protections. "
        "Test application of an ethical principle to a real governance dilemma."
    ),
}

_DEFAULT_SUBJECT_HINT = (
    "Focus on core conceptual definitions, key provisions, relevant data points, "
    "and the policy/institutional framework. Combine today's news hook with "
    "conceptual depth to craft a question that rewards genuine understanding."
)

# ── Context formatters ────────────────────────────────────────────────────────


def _format_wiki_context(wiki_data: dict | None) -> str:
    """Format WikiEnrichmentService output for the prompt."""
    if not wiki_data:
        return "Not available."

    lines: list[str] = []

    intro = wiki_data.get("intro", "")
    if intro:
        lines.append(f"Background summary: {intro[:600]}")

    key_facts = wiki_data.get("key_facts", [])
    if key_facts:
        lines.append("Key facts:")
        for f in key_facts[:6]:
            lines.append(f"  • {f}")

    related = wiki_data.get("related_terms", [])
    if related:
        lines.append(f"Related concepts: {', '.join(related[:5])}")

    wiki_url = wiki_data.get("wiki_url", "")
    if wiki_url:
        lines.append(f"Wikipedia source: {wiki_url}")

    return "\n".join(lines) if lines else "Not available."


def _format_source_urls(source_urls: list[str] | None) -> str:
    """Format source article URLs for the prompt."""
    if not source_urls:
        return "Not available."
    return "\n".join(f"  {i+1}. {u}" for i, u in enumerate(source_urls[:3]))


# ── Master prompt template ────────────────────────────────────────────────────

_QUIZ_PROMPT_TEMPLATE = """\
You are a senior question setter for India's most competitive examinations.
Your task: generate exactly ONE original, challenging question based on the
source material below. The question must reward genuine understanding, not
pattern-matching or rote recall.

═══════════════════════════════════════════════════════════
SUBJECT: {subject_name}   |   TOPIC: {topic_name}
═══════════════════════════════════════════════════════════
{subject_hint}

═══════════════════════════════════════════════════════════
SOURCE MATERIAL
═══════════════════════════════════════════════════════════

── TODAY'S NEWS CONTEXT ──
{ca_chunks_text}

── CONCEPTUAL BACKGROUND (Wikipedia) ──
{wiki_text}

── ORIGINAL SOURCE URLS (for attribution) ──
{source_urls_text}

═══════════════════════════════════════════════════════════
QUESTION TYPE — CHOOSE ONE that best fits the material
═══════════════════════════════════════════════════════════

TYPE 1 — MULTI-STATEMENT (most common, recommended)
  Format: "Consider the following statements regarding [specific subject]:
  1. [Statement]
  2. [Statement]
  3. [Statement]   ← minimum 3; you may write up to 5 statements
  4. [Optional]
  5. [Optional]
  Which of the above statements is/are correct?"
  OR: "How many of the above statements are correct?"

  Options (UPSC-authentic combination style):
  For 3 statements, examples:
    A: 1 only            A: 1 and 2 only       A: 2 only
    B: 2 and 3 only      B: 2 and 3 only       B: 1 and 3 only
    C: 1 and 3 only      C: 1 only             C: 2 and 3 only
    D: All of the above  D: All of the above   D: 1 and 2 only

  For "How many are correct?" format:
    A: Only one    B: Only two    C: Only three    D: All four/five

  — "All of the above" and "None of the above" ARE permitted as correct answers
    when the source material genuinely supports them.
  — Exactly ONE option must be unambiguously correct.
  — The number of correct/incorrect statements is YOUR choice — do not follow
    a fixed pattern. Vary it: sometimes all correct, sometimes only one,
    sometimes two out of five. Unpredictability is intentional.

TYPE 2 — ASSERTION-REASON
  Format:
    "Assertion (A): [One precise factual or causal claim]
     Reason    (R): [A second claim intended to explain A]"

  Options (fixed for this type — use exactly these four):
    A: Both A and R are true, and R is the correct explanation of A
    B: Both A and R are true, but R is NOT the correct explanation of A
    C: A is true but R is false
    D: A is false but R is true

  Tip: The most interesting A-R questions have both statements true but R only
  partially or incorrectly explains A (correct answer B), or A is a consequence
  of a different mechanism than what R claims.

TYPE 3 — SINGLE BEST ANSWER
  Format: A direct question with one clearly correct answer among four options.
  Best used when the news event has one specific, verifiable fact to test.
  Options must include plausible distractors that are factually close to correct.
  Avoid trivial "which year was X founded" type questions.

═══════════════════════════════════════════════════════════
UNIVERSAL QUALITY RULES (apply regardless of question type)
═══════════════════════════════════════════════════════════

CONTENT:
  • Every fact in the question must be derivable from the source material above.
  • Do NOT fabricate names, figures, dates, or provisions not in the sources.
  • The question must reward a student who reads quality newspapers AND understands
    underlying concepts — not just one or the other.
  • Complexity: aim for medium-to-hard difficulty. Distractors must be plausible.

LANGUAGE:
  • Precise, unambiguous statements — no hedging ("it is often said that...").
  • No passive constructions that obscure who/what is being described.
  • Each statement independent — no pronouns referring to prior statements.
  • Question stem: never reveals the answer through wording.

PROHIBITIONS:
  ✗ Never mention UPSC, GS papers, aspirants, exam pattern, or study tips.
  ✗ No trivial recall ("What is the capital of...").
  ✗ No duplicate information across two statements.
  ✗ Correct answer must NOT be predictable from the question format alone.

═══════════════════════════════════════════════════════════
EXPLANATION FORMAT (this is shown to users after submission)
═══════════════════════════════════════════════════════════

Structure the explanation like this — clear, direct, no fluff:

For MULTI-STATEMENT questions:
  Statement 1: CORRECT/INCORRECT — [one sentence stating the fact and why]
  Statement 2: CORRECT/INCORRECT — [one sentence stating the fact and why]
  Statement 3: CORRECT/INCORRECT — [one sentence stating the fact and why]
  (repeat for each statement)
  Therefore, the correct answer is [X]: [option text].
  Source: [paste the most relevant URL from the source URLs above, if available]

For ASSERTION-REASON questions:
  Assertion: CORRECT/INCORRECT — [brief factual justification]
  Reason: CORRECT/INCORRECT — [brief factual justification]
  Relationship: [one sentence explaining whether R explains A and why]
  Therefore, the correct answer is [X].
  Source: [URL if available]

For SINGLE BEST ANSWER:
  [Option A]: [correct/incorrect — one line why]
  [Option B]: [correct/incorrect — one line why]
  [Option C]: [correct/incorrect — one line why]
  [Option D]: [correct/incorrect — one line why]
  Therefore, the correct answer is [X].
  Source: [URL if available]

Rules for explanation:
  • 80–160 words total.
  • Every incorrect statement/option gets a one-line factual rebuttal.
  • The correct fact must be stated explicitly (not just "this is wrong").
  • If source URL is available, include it at the end — it authenticates the question.
  • No exam-language. No "This tests your knowledge of...".

═══════════════════════════════════════════════════════════
OUTPUT FORMAT — strict JSON, no markdown, no extra text
═══════════════════════════════════════════════════════════

{{
  "question_text": "[full question including all statements if multi_statement, or full A/R text if assertion_reasoning]",
  "question_type": "multi_statement" | "assertion_reasoning" | "single_mcq",
  "statements": [
    "[statement text only, no numbering — for multi_statement: one entry per statement; for assertion_reasoning: two entries ['Assertion: ...', 'Reason: ...']; for single_mcq: empty list []]"
  ],
  "options": {{
    "A": "[option A text]",
    "B": "[option B text]",
    "C": "[option C text]",
    "D": "[option D text]"
  }},
  "correct_answer": "A" | "B" | "C" | "D",
  "explanation": "[structured explanation per format above, including Source: URL if available]"
}}

Generate the single question now:"""


# ── Public builder function ───────────────────────────────────────────────────


def build_quiz_prompt(
    ca_chunks_text: str,
    wiki_enrichment: dict | None,
    topic_name: str,
    subject_name: str,
    source_urls: list[str] | None = None,
) -> str:
    """
    Build a complete prompt for generating one daily quiz question.

    Called once per approved CaDailyProposal by DailyQuizGeneratorService.
    No NCERT/static chunks are used here — wiki IS the conceptual background.

    Args:
        ca_chunks_text:  Enriched CA text (CAChunk + parent CAArticle content).
                         Already capped at 6000 chars by the caller.
        wiki_enrichment: Dict from WikiEnrichmentService.get_enrichment(), or None.
                         Shape: {intro, key_facts, related_terms, wiki_url}
        topic_name:      Knowledge topic name (e.g. "Monetary Policy Committee").
        subject_name:    GS subject name (e.g. "Indian Economy").
        source_urls:     Original news article URLs from CaDailyProposal.source_urls.
                         Embedded in explanation for question authentication.

    Returns:
        Fully formatted prompt string ready for llm_call_json(mode="quiz").
    """
    subject_hint = _SUBJECT_QUIZ_HINT.get(subject_name, _DEFAULT_SUBJECT_HINT)
    ca_text = ca_chunks_text[:6000] if ca_chunks_text else "Not available."
    wiki_text = _format_wiki_context(wiki_enrichment)
    source_urls_text = _format_source_urls(source_urls)

    return _QUIZ_PROMPT_TEMPLATE.format(
        subject_name=subject_name,
        topic_name=topic_name,
        subject_hint=subject_hint,
        ca_chunks_text=ca_text,
        wiki_text=wiki_text,
        source_urls_text=source_urls_text,
    )
