"""
engines/daily_ca/services/prompt_builder.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase I  — CA_DAILY_PROMPT Builder
Phase D2 (FEATURES3) — Richer context window (4000 chars), CONCEPT-NEWS BRIDGE,
                        DATA INTEGRITY instruction, all-subject paragraph guidance.
L10 (FEATURES_LLM_FIX.md Part II, 2026-09-20) — the template rewritten to fit
                        Groq: every rule stated once, only the current subject's
                        bridge example and structure guidance injected, ASCII
                        rules, one length cap. Data inputs untouched (D1).

Single public function:
  build_ca_prompt(ca_chunks_text, static_key_facts, wiki_enrichment,
                  subject_name, topic_name) -> str

The prompt is engineered for genuinely excellent editorial writing —
not exam notes, not bullet dumps, not generic "this is important" filler.
The target is an article that a well-read curious person WANTS to read,
that happens to align perfectly with the analytical depth required for India's
most competitive examinations AND for any informed, curious reader.

Key design decisions:
  - Subject tone is injected per article — 14 different tones, each precise
    (covers all DB subjects: GS1 × 5 subjects, GS2 × 3, GS3 × 5, GS4 × 1)
  - CONCEPT-NEWS BRIDGE: LLM is explicitly instructed to use the news event as
    the hook and the FACTUAL ANCHOR as the conceptual depth layer — this is the
    core editorial principle that makes articles feel authoritative
  - DATA INTEGRITY: LLM explicitly told never to invent statistics, names,
    figures, or dates not present in its source material
  - Multi-dimensional topics (geopolitics, environment-economy crossovers, etc.)
    are explicitly encouraged — LLM is told to bring in other dimensions if relevant
  - Concept links [[double brackets]] and TAGS are clearly distinguished in the prompt
  - Callout box position is mid-article (not end) for better reading UX
  - Factual anchor is "use for conceptual depth, do NOT copy prose" — prevents plagiarism
  - Hard caps: 6000 chars for CA input (up from 4000), 750 words output target

WHY THE TEMPLATE IS SIZE-BUDGETED (L10):
  The pool routes on estimated tokens (len/4). The old template was ~27,200 chars of
  the ~35,000-char prompt — nine GS-paper examples where one applies, three per-paper
  guidance tables, every mandatory rule stated twice, three contradictory length caps
  and box-drawing characters that tokenise badly — which put the article prompt
  above Groq's gate. The article body was then served only by Mistral (quota-dead)
  and OpenRouter's daily free-model pick, which broke on 2026-09-18: three days of
  zero articles behind a green cron tick. Measured on 2026-09-20 with
  scripts/dev/ca_prompt_budget.py: real tokens = 0.873 x estimate; Groq accepts at
  least 10,889 tokens per request (prompt + max_tokens); the CA-article completion
  needs max_tokens 4,000 with reasoning_effort "low". Hence the budget below.
"""

# ── Prompt budget (L10) ───────────────────────────────────────────────────────
# Estimated tokens (len // 4, the pool's own estimator) the WHOLE article prompt
# may reach with worst-case inputs. Arithmetic, all measured 2026-09-20:
#   proven Groq request envelope   10,889 tokens  (prompt 6,889 + max_tokens 4,000)
#   CA-article completion budget    4,000 tokens  (284 reasoning + ~1,000 article + margin)
#   real tokens / estimate          0.873
#   6,000 est. x 0.873 = 5,238 real + 4,000 = 9,238  ->  1,650 under the envelope,
#   and comfortably under the pool's Groq gate, so the article always routes to Groq.
# Data maximum is ~10,800 chars (news cap 6,000 + facts <= ~2,500 + wiki <= ~2,000 +
# tone ~300), which leaves the template ~12,000 chars. Guarded by
# tests/test_prompt_budget.py — a template that grows past this breaks the build,
# not the cron.
CA_PROMPT_TOKEN_BUDGET = 6_000
CA_NEWS_CONTEXT_MAX_CHARS = 6_000  # Phase F cap on the news excerpts — unchanged (D1)

# ── Subject Tone Map ──────────────────────────────────────────────────────────
# Daily CA version — independent of book_content engine's copy.
# Maps exact subject names (from knowledge.Subject) to tone directives.
# Each tone directive tells the LLM HOW to write, not what to write.
# A topic may belong to one subject but draw on other dimensions — that's encouraged.

SUBJECT_TONE_MAP: dict[str, str] = {
    "Indian Polity & Constitution": (
        "constitutional, legal, institutional tone — "
        "reference specific Articles, Acts, landmark judgements, and constitutional provisions where relevant; "
        "analyse how institutions have responded to or shaped this development; "
        "where relevant, bring in federal, rights-based, or democratic accountability dimensions"
    ),
    "Indian Economy": (
        "analytical, data-driven tone — "
        "include statistics, policy implications, trade and fiscal figures; "
        "analyse demand-supply dynamics, macroeconomic impacts, and sectoral effects; "
        "where relevant, draw in geopolitical dimensions of economic decisions "
        "(trade wars, sanctions, supply chain realignments) or environmental costs of economic policy"
    ),
    "Environment & Ecology": (
        "scientific, conservation-oriented tone — "
        "reference international frameworks (UNFCCC, CBD, Ramsar, CITES), India's NDCs and targets, "
        "biodiversity data, and ecosystem services; "
        "where relevant, bring in the economic cost of environmental damage or "
        "geopolitical dimensions of climate negotiations"
    ),
    "International Relations": (
        "diplomatic, strategic, and multi-layered tone — "
        "reference bilateral frameworks, India's stated positions, multilateral forums, and strategic interests; "
        "analyse geoeconomic underpinnings of diplomatic moves (trade routes, energy corridors, investment flows); "
        "where relevant, bring in the domestic policy or constitutional implications of external developments"
    ),
    "Science & Technology": (
        "technical but accessible tone — "
        "explain concepts clearly for a non-specialist reader; "
        "highlight India's achievements, gaps, and strategic ambitions; "
        "where relevant, bring in the geopolitical and geoeconomic dimension of technology "
        "(semiconductor wars, space race, critical minerals) or ethical and governance concerns"
    ),
    "Indian Society": (
        "sociological, ground-level tone — "
        "focus on vulnerable groups, structural inequalities, and lived realities; "
        "anchor analysis in data (census, NFHS, NSS) and constitutional provisions on equality and justice; "
        "where relevant, draw in economic dimensions (poverty, labour markets) or "
        "governance failures that perpetuate social challenges"
    ),
    "Indian Heritage & Culture": (
        "cultural, art-historical, and contextual tone — "
        "reference dynasties, movements, specific artefacts, UNESCO designations, and oral traditions; "
        "connect heritage to contemporary identity, soft power, or tourism; "
        "where relevant, bring in the international dimension of cultural diplomacy or "
        "threats to intangible heritage from climate change and urbanisation"
    ),
    "Modern Indian History": (
        "narrative-historical tone — "
        "anchor in specific dates, leaders, turning points, cause-effect chains; "
        "use colonial-nationalist framing where relevant; "
        "connect historical events to contemporary India's laws, institutions, or unresolved questions; "
        "where relevant, draw in the global context that shaped the event"
    ),
    "Indian & World Geography": (
        "spatial, analytical, and interconnected tone — "
        "anchor in physical geography concepts (tectonic settings, river systems, climate zones, "
        "soil types, natural vegetation) alongside human geography dimensions "
        "(migration patterns, urbanisation, demographic transitions, resource distribution); "
        "reference India's geographical features as drivers of historical, economic, and security outcomes; "
        "use precise locational and quantitative detail — coordinates, altitudes, catchment areas, "
        "rainfall figures — where they add clarity; "
        "where relevant, bring in the geopolitical dimension of geographical positioning "
        "(maritime chokepoints, border disputes, transboundary rivers, critical minerals) or "
        "the environmental impact of human activity on India's diverse physical landscapes"
    ),
    "World History": (
        "global-comparative tone — "
        "situate international events in historical continuity; "
        "relate to India's contemporary context where applicable; "
        "where relevant, draw in how historical patterns mirror or inform current geopolitical realignments"
    ),
    "Governance & Social Justice": (
        "policy-implementation tone — "
        "go beyond scheme names to examine delivery mechanisms, last-mile gaps, and accountability structures; "
        "use RTI, DPSP, and constitutional provisions to frame governance obligations; "
        "where relevant, draw in the economic cost of governance failures or "
        "judicial interventions that reshaped policy"
    ),
    "Disaster Management": (
        "preparedness-focused, systems-thinking tone — "
        "reference NDMA mandate, Sendai Framework targets, and India's DRR progress; "
        "analyse early warning systems, inter-agency coordination, and community resilience; "
        "where relevant, bring in the climate change dimension driving increased disaster frequency, "
        "or the economic and human development cost of poor preparedness"
    ),
    "Internal Security": (
        "factual, legally grounded, neutral tone — "
        "classify threats precisely using legal frameworks (UAPA, AFSPA, NIA Act); "
        "avoid sensationalism; "
        "analyse the socioeconomic roots of security challenges alongside the law enforcement response; "
        "where relevant, bring in the geopolitical dimension (cross-border linkages, state-sponsored threats)"
    ),
    "Ethics, Integrity & Aptitude": (
        "philosophical-reflective, case-grounded tone — "
        "engage with values, dilemmas, and the gap between intent and action; "
        "draw on thinkers, landmark whistleblower cases, or institutional accountability failures; "
        "where relevant, bring in systemic dimensions — how policy design itself can create ethical traps "
        "for civil servants and institutions"
    ),
    "default": (
        "factual, analytical, intellectually curious tone — "
        "accessible to a well-read general reader; "
        "include relevant data points, institutional context, and cross-cutting dimensions where they add genuine insight"
    ),
}

# ── Subject → GS paper (drives the ONE example and ONE structure line injected) ─
# The old template carried every paper's examples and guidance in every prompt;
# the model needs only the ones for the article it is writing.
_SUBJECT_PAPER: dict[str, str] = {
    "Indian Heritage & Culture": "GS1",
    "Modern Indian History": "GS1",
    "World History": "GS1",
    "Indian Society": "GS1",
    "Indian & World Geography": "GS1",
    "Indian Polity & Constitution": "GS2",
    "Governance & Social Justice": "GS2",
    "International Relations": "GS2",
    "Indian Economy": "GS3",
    "Science & Technology": "GS3",
    "Environment & Ecology": "GS3",
    "Disaster Management": "GS3",
    "Internal Security": "GS3",
    "Ethics, Integrity & Aptitude": "GS4",
}

# The news-to-concept bridge, one worked example per subject: the hook on the left of
# the arrow, the conceptual depth the article must supply on the right.
SUBJECT_BRIDGE_MAP: dict[str, str] = {
    "Indian Polity & Constitution": (
        "The Supreme Court strikes down a law or issues a landmark order -> explain the "
        "constitutional Article or doctrine invoked, the precedent chain, what the judgement "
        "changes institutionally and why it shifts the balance of power."
    ),
    "Governance & Social Justice": (
        "A state expands a welfare scheme or a court orders its delivery -> explain the delivery "
        "mechanism, the constitutional or DPSP basis, the last-mile gaps and who is accountable."
    ),
    "International Relations": (
        "An India-China disengagement or a bilateral summit outcome -> explain the Line of Actual "
        "Control's legal ambiguity, the 1993/1996 framework agreements, what 'disengagement' and "
        "'patrolling' mean under them."
    ),
    "Indian Economy": (
        "RBI changes the repo rate or a major allocation is announced -> explain the monetary "
        "transmission mechanism or the fiscal framework in use, and how it reaches inflation, "
        "credit, EMIs, the rupee and specific sectors."
    ),
    "Science & Technology": (
        "An ISRO launch, a reactor milestone or a technology policy -> explain the technology "
        "precisely (what the satellite does, the reactor type, the spectrum) and the capability "
        "gap it fills strategically."
    ),
    "Environment & Ecology": (
        "A tiger census, coral bleaching or a new protected area -> explain the conservation "
        "framework (Project Tiger, Wildlife Protection Act, IUCN categories) and what the numbers "
        "mean against targets and benchmarks."
    ),
    "Disaster Management": (
        "Floods, a cyclone or a heatwave declared -> explain the NDMA/SDMA mandate, the Sendai "
        "targets, early warning and inter-agency coordination, and the preparedness gap the event "
        "exposed."
    ),
    "Internal Security": (
        "A terrorist designation, a border incident or an enforcement action -> explain the legal "
        "framework (UAPA, NIA Act, AFSPA), the agency mandates, and the socioeconomic roots "
        "alongside the law-enforcement response."
    ),
    "Indian Society": (
        "A caste survey or a reservation dispute resurfaces -> explain the constitutional "
        "provisions (Articles 15-16, Indra Sawhney), the data (Census, NFHS, NSS) and the "
        "structural inequality behind the headline."
    ),
    "Indian Heritage & Culture": (
        "A site is inscribed, restored or damaged -> explain the dynasty or movement behind it, "
        "the artistic conventions, the UNESCO or ASI framework, and what it means for identity, "
        "soft power or tourism today."
    ),
    "Modern Indian History": (
        "An anniversary, a memorial or a recovered archive -> explain the cause-effect chain of "
        "the event, the leaders' positions, and what it left in today's laws, institutions or "
        "unresolved questions."
    ),
    "World History": (
        "A treaty anniversary or a border row with old roots -> explain the historical sequence, "
        "the settlement that created today's map, and how the pattern mirrors current "
        "realignments, with India's position where it applies."
    ),
    "Indian & World Geography": (
        "A cyclone makes landfall in Tamil Nadu -> explain cyclone formation, the Bay of Bengal's "
        "warm surface temperature, why that coast is structurally vulnerable, and the "
        "October-November pattern."
    ),
    "Ethics, Integrity & Aptitude": (
        "A whistleblower is transferred or a corruption verdict lands -> explain the ethical "
        "framework at stake (conflicting duties, public trust), the Whistleblower Protection Act, "
        "and the tension between institutional loyalty and public duty."
    ),
    "default": (
        "A policy decision or a court order -> explain the framework, provision or mechanism that "
        "makes it matter beyond today."
    ),
}

# How the paragraph layer and the bullet layer separate, per paper.
_PAPER_STRUCTURE: dict[str, str] = {
    "GS1": (
        "Paragraphs: event -> context -> legacy. Bullets: key dates, named actors, turning "
        "points, data."
    ),
    "GS2": (
        "Paragraphs: legal provision -> institutional interpretation -> real-world impact. "
        "Bullets: specific Articles, judgement citations, treaty clauses, mandates."
    ),
    "GS3": (
        "Paragraphs: data -> policy response -> gap. Bullets: figures, targets, scheme "
        "components, gaps."
    ),
    "GS4": (
        "Paragraphs: dilemma -> competing values -> resolution framework. Bullets: competing "
        "values, principle names, case precedents, resolution steps."
    ),
    "default": (
        "Paragraphs: what -> why/how -> so what. Bullets: figures, provisions, named "
        "institutions, dates."
    ),
}


# ── News Category List ────────────────────────────────────────────────────────
# Fixed list — must stay in sync with NEWS_CATEGORY_CHOICES in models.py.
# Never add custom categories here without a corresponding model migration.
_NEWS_CATEGORIES = [
    "national",
    "international",
    "geo-politics",
    "geo-economics",
    "economy",
    "science-tech",
    "environment",
    "society",
    "law-justice",
    "defence",
    "health",
    "sports-awards",
]

# ── Prompt Template ───────────────────────────────────────────────────────────
# This is the master prompt that drives every Daily CA article.
# It is designed to produce editorial-quality writing, not exam notes.
# Every instruction has a reason:
#   - "never as exam notes" + the NEVER list -> prevents exam-note regression
#   - "cut across domains" -> enables multi-dimensional articles
#   - "never copy its prose" for the depth anchor -> prevents plagiarism
#   - Forbidden headings list -> prevents the LLM's habitual UPSC filler
#   - [[double brackets]] vs TAGS distinction -> prevents system confusion
#   - Callout mid-article -> better UX than a callout at the end
#   - "# Title" first line + blank lines between blocks -> the parser finds the
#     title and the normaliser never sees the single-line (C7) shape
# Budgeted: every rule once, ASCII only, one length cap (see CA_PROMPT_TOKEN_BUDGET).

CA_DAILY_PROMPT_TEMPLATE = """\
SYSTEM:
You are a senior editorial writer for a knowledge platform read by curious citizens,
students, researchers, policymakers and civil-service aspirants. Your standard is The
Hindu's editorial page meets an intelligent explainer from a top policy think-tank.
Write for all of those readers - informative, factual, deeply analytical - never as
exam notes.

SUBJECT: {subject_name}
TONE: {subject_tone}
A topic may cut across domains (an economic policy with geopolitical effects, an
environmental issue with governance or rights dimensions); bring those dimensions in
where they add genuine depth.

--- TODAY'S NEWS CONTEXT (the trigger and hook for this article) ---
{ca_chunks_text}

--- CONCEPTUAL DEPTH ANCHOR (verified facts, frameworks and provisions for the
underlying concept - explain from it with precision; never copy its prose) ---
{static_key_facts}

--- SUPPLEMENTARY REFERENCE (Wikipedia background - context only, never copy) ---
{wiki_enrichment}
---

THE EDITORIAL PRINCIPLE - NEWS AS THE HOOK, CONCEPT AS THE DEPTH
Every article achieves two things, both well: (a) it tells today's story precisely -
what happened, who, when, the exact figures from TODAY'S NEWS CONTEXT; (b) it explains
the concept, law, mechanism or framework behind it from the CONCEPTUAL DEPTH ANCHOR,
so the reader finishes knowing both what happened and why it has lasting significance.
Bridge for this subject: {subject_bridge}
If the depth anchor is "Not available.", build both layers from the news context and
the reference; never invent a framework that is not in your sources, and write at the
confidence level the sources support.

DATA INTEGRITY (non-negotiable - your readers are researchers, policymakers and
civil-service aspirants, and they WILL notice a fabricated figure)
State a number, percentage, rupee or dollar figure, date, ranking, Article or treaty
number, name of an official, judge or scientist, or a quotation ONLY if it appears in
the three source blocks above. Do not invent: rupee amounts or percentages; GDP,
population, employment or growth figures; rankings; budget outlays or allocations;
names of ministers, officials, judges or scientists; case names or judgement years;
treaty or constitutional Article numbers; quotations attributed to named people;
precise dates; and studies, reports, surveys, pilots or task forces ("a 2024 IIM
study estimated...") that are not in your sources. If a fact supports your analysis
but you lack the precise figure, write directionally ("among the top five globally",
"a substantial allocation") or omit the claim. If the sources carry few facts, write
fewer and shorter sections: 550 words built on true facts beats 750 words padded with
invented ones. Widely known institutional facts (which Article establishes a body,
what an Act is named for) may be used without a figure attached.

DEPTH AND CLARITY
Every ## section carries at least two named facts drawn from the sources: a figure, a
named Act, Article or provision, a named person with their role, a date, a named
scheme or institution with its mandate, or a place tied to the development. Every
sentence must teach the reader something specific. Delete, or replace with the fact,
the mechanism, the agency or the amount, any sentence that only announces importance
("This is a significant development"), restates the topic ("Water scarcity is a major
concern in India") or describes a process in a circle ("The policy aims to improve
the situation"). Conceptual explanations without figures - how a mechanism works -
are welcome; an evaluative claim is fine only when the next sentence says what
specifically changes.

LANGUAGE
Indian quality-newspaper register (The Hindu, Indian Express). Formal English and the
legal phrasing common in Indian discourse (prima facie, inter alia, notwithstanding)
are fine. Domain terms are the substance of the article - explain each in plain words
at first use, and give the full form before an acronym: "the National Mission for
Clean Ganga (NMCG)". Avoid obscure literary vocabulary (ameliorate, eschew, propitious,
quotidian, vitiate - write improve, avoid, favourable, everyday, undermine). Direct,
active voice; never stacked passives.

STRUCTURE - every item is mandatory
1. TITLE - the first line, written as "# Title". A news headline of 8 to 14 words with at
   least one specific noun (a person, place, law, number or event), shaped "[Specific
   subject]: [what happened / what it means]". Good: "Centre's Fiscal Deficit Hits 5.1% -
   Why RBI Is Watching Closely"; "Supreme Court Strikes Down Electoral Bonds: Five
   Things That Change Now". Bad: "Nuclear Energy in India"; "Understanding the
   Delimitation Controversy"; "What is UAPA?". Never open with: Introduction to,
   Overview of, Understanding, A Look at, Examining, An Analysis of, The Role of,
   Importance of, All You Need to Know, Everything About, What is, What are, A Brief,
   A Study of, Exploring.
2. OPENING - two or three self-contained sentences that lead with what happened today
   and why it matters; no dictionary definition. They are extracted as the summary box,
   so the rest of the article must build on them, never repeat them.
3. BODY - plan FOUR or FIVE ## sections of 110 to 150 words each (that is the whole
   550-750 word budget; do not add sections to seem thorough).
   ## headings only (no ###), chosen for what THIS topic needs; for example "What is
   [X]?" (only for a genuinely unfamiliar concept), "How It Works / How It Happened",
   "Key Provisions / Legal Framework", "The Numbers That Matter", "Historical
   Context", "Stakeholders and Their Interests", "International Dimension",
   "Challenges on the Ground", "Significance and What Changes Now", "Way Forward"
   (only with something concrete to say). Forbidden headings: UPSC Angle, Exam
   Relevance, Prelims Focus, Mains Value, Practice Questions, Important for UPSC,
   Why in News.
   Under each heading write two short paragraphs of two to four sentences - what/
   who/where, then why/how (the mechanism, cause or legal basis) or so what (the
   implication) - and, between them, one bullet list of three or four facts too
   dense for prose: one verifiable fact per bullet, under 25 words, with real
   specifics from the sources (Article numbers, figures, scheme names, dates).
   {subject_structure}
   Pattern:
   ## Key Provisions / Legal Framework

   [Paragraph: what the provision is and what it does]

   - Article 21 guarantees life and personal liberty against state action
   - [[Maneka Gandhi Judgment]] (1978) read due process into Article 21

   [Paragraph: how it has been applied in this case, and what follows]

   FORMAT - markdown must render: a blank line after the title, after the opening,
   before and after every ## heading, between paragraphs, around every bullet list
   and around the callout. Never run the article together on one line.
4. ANTI-REPETITION - every fact, figure, provision or name appears exactly once in the
   article. Before each new section ask "have I already said this?"; if you feel the
   urge to write "as mentioned above", delete the repetition, not the reference.
5. CONCEPT LINKS - embed 5 to 8 terms in [[double brackets]], spread across sections:
   specific Acts and laws ([[Right to Information Act 2005]]), named schemes
   ([[PM-KUSUM]]), technical terms a non-specialist would not know ([[Small Modular
   Reactors]]), landmark amendments and judgements ([[Kesavananda Bharati Case]]),
   institutions with a specific mandate ([[National Disaster Management Authority]]),
   international frameworks and treaties ([[Montreal Protocol]]). Bracket the term at
   its first mention. If the sources name fewer than five such items, bracket the
   concepts the article itself explains - the scheme, the statute, the body, the
   technology, the doctrine. Not for generic words (federalism, judiciary, climate
   change - those belong in TAGS), never more than 8. Fewer than 5 fails quality
   review - this is the rule most often missed, so count them before you finish.
6. CALLOUT - exactly one, at a natural mid-article break, never at the end and never a
   summary:
   :::callout
   **Did You Know?** [one genuinely surprising or little-known fact about this topic]
   :::
7. LENGTH - 550 to 750 words of body text; hard maximum 900. Quality over quantity:
   every sentence must earn its place.
8. CLOSING - the last three lines of the output, exactly this shape:
   CATEGORY: exactly one of {categories} - by the PRIMARY angle of this article, not
   the subject (economic impact of India-China tensions -> geo-economics; a Supreme
   Court judgement on forest rights -> law-justice; an ISRO launch -> science-tech;
   state election results -> national)
   TAGS: 5 to 8 comma-separated keywords, lowercase-hyphenated, 1 to 3 words each,
   generic and discoverable (nuclear-energy, fiscal-policy, india-china); different
   from the [[concept links]]; no organisation names, no article titles
   SOURCE: [publication name] - [URL]

NEVER IN THE BODY
- The words UPSC, GS1, GS2, GS3, GS4, exam, aspirants, syllabus; practice questions,
  answer pointers or hints; "it matters for UPSC", "civil services perspective",
  "from an exam standpoint", "for Mains preparation", "for Prelims", "this is
  important from the perspective of".
- Filler openers: "In the context of", "It is pertinent to note that", "India has a
  long history of", "In recent times", "In recent years", "Against this backdrop",
  "In the wake of", "Amid growing concerns", "It goes without saying".
- Unanchored hedging: "This may have implications", "Experts believe", "Some analysts
  say", "It is widely acknowledged", "It is believed that", "Many feel that" - cite a
  name or a study, or cut the sentence.
- ### sub-headings; prose copied from the depth anchor or the reference.

CHECKLIST - verify before you finish, and fix, do not explain:
1. Body is 550 to 750 words. If longer, cut a whole section or the weakest bullets.
2. There are 5 to 8 [[bracketed]] concept links, counted.
3. Every number, name, date and quotation traces to the source blocks; delete any
   that does not.
4. At least four lines start with "## ", each with a blank line before and after.
5. Exactly one callout box, mid-article.
6. The last three lines are CATEGORY:, TAGS:, SOURCE: - nothing after them.
"""


# ── Static facts formatter ────────────────────────────────────────────────────


def _format_static_facts(static_facts: dict | None) -> str:
    """
    Converts StaticBackgroundService.get_background_facts() output into
    a clean, LLM-readable text block.

    Returns "Not available." if static_facts is None or empty.
    """
    if not static_facts:
        return "Not available."

    parts: list[str] = []

    title = static_facts.get("title", "")
    if title:
        parts.append(f"Topic: {title}")

    provisions = static_facts.get("key_provisions", [])
    if provisions:
        parts.append("Key Provisions / Constitutional References:")
        for p in provisions[:5]:
            parts.append(f"  • {p}")

    facts = static_facts.get("key_facts", [])
    if facts:
        parts.append("Key Facts:")
        for f in facts[:5]:
            parts.append(f"  • {f}")

    statistics = static_facts.get("statistics", [])
    if statistics:
        parts.append(f"Data Points: {', '.join(statistics[:6])}")

    return "\n".join(parts) if parts else "Not available."


# ── Wiki enrichment formatter ─────────────────────────────────────────────────


def _format_wiki_enrichment(wiki_data: dict | None) -> str:
    """
    Converts WikiEnrichmentService.get_enrichment() output into
    a clean, LLM-readable text block.

    Returns "Not available." if wiki_data is None or empty.
    """
    if not wiki_data:
        return "Not available."

    parts: list[str] = []

    intro = wiki_data.get("intro", "").strip()
    if intro:
        parts.append(f"Overview: {intro}")

    key_facts = wiki_data.get("key_facts", [])
    if key_facts:
        parts.append("Background Facts:")
        for f in key_facts[:5]:
            parts.append(f"  • {f}")

    related = wiki_data.get("related_terms", [])
    if related:
        parts.append(f"Related Concepts: {', '.join(related[:5])}")

    return "\n".join(parts) if parts else "Not available."


# ── Public API ────────────────────────────────────────────────────────────────


def subject_guidance(subject_name: str) -> tuple[str, str]:
    """
    The one bridge example and the one structure line for this subject.

    Unknown subject names (the DB may carry a name the maps do not) fall back to
    the generic entries — never a KeyError on the generation path.
    """
    bridge = SUBJECT_BRIDGE_MAP.get(subject_name, SUBJECT_BRIDGE_MAP["default"])
    paper = _SUBJECT_PAPER.get(subject_name, "default")
    return bridge, _PAPER_STRUCTURE[paper]


def build_ca_prompt(
    ca_chunks_text: str,
    static_key_facts: dict | None,
    wiki_enrichment: dict | None,
    subject_name: str,
    topic_name: str,
) -> str:
    """
    Builds the complete LLM prompt for one Daily CA article generation cycle.

    Args:
        ca_chunks_text:   Raw text from top 3 CA article chunks (today's news).
        static_key_facts: Dict from StaticBackgroundService.get_background_facts()
                          OR None if no published static exists.
        wiki_enrichment:  Dict from WikiEnrichmentService.get_enrichment()
                          OR empty dict {} if not fetched / not found.
        subject_name:     UPSC subject name (e.g. "Indian Economy").
                          Selects the tone, the bridge example and the structure
                          guidance injected into the template.
        topic_name:       Knowledge topic name (e.g. "Fiscal Federalism").
                          Currently unused in the template but available for
                          future prompt personalisation (e.g., topic-specific
                          section heading suggestions).

    Returns:
        Fully formatted prompt string ready for llm_call().
    """
    tone = SUBJECT_TONE_MAP.get(subject_name, SUBJECT_TONE_MAP["default"])
    bridge, structure = subject_guidance(subject_name)

    formatted_static = _format_static_facts(static_key_facts)
    formatted_wiki = _format_wiki_enrichment(wiki_enrichment)

    # Phase F: raised cap 4000 → 6000 chars — richer context = more named
    # facts, dates, figures available to the LLM for authoritative writing
    ca_text_capped = (
        ca_chunks_text[:CA_NEWS_CONTEXT_MAX_CHARS]
        if ca_chunks_text
        else "Not available."
    )

    return CA_DAILY_PROMPT_TEMPLATE.format(
        subject_name=subject_name or "General Studies",
        subject_tone=tone,
        subject_bridge=bridge,
        subject_structure=structure,
        ca_chunks_text=ca_text_capped,
        static_key_facts=formatted_static,
        wiki_enrichment=formatted_wiki,
        categories=" | ".join(_NEWS_CATEGORIES),
    )
