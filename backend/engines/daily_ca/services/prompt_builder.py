"""
engines/daily_ca/services/prompt_builder.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase I — CA_DAILY_PROMPT Builder

Single public function:
  build_ca_prompt(ca_chunks_text, static_key_facts, wiki_enrichment,
                  subject_name, topic_name) -> str

The prompt is engineered for genuinely excellent editorial writing —
not exam notes, not bullet dumps, not generic "this is important" filler.
The target is an article that a well-read curious person WANTS to read,
that happens to align perfectly with UPSC's analytical depth requirements.

Key design decisions:
  - Subject tone is injected per article — 14 different tones, each precise
  - Multi-dimensional topics (geopolitics, environment-economy crossovers, etc.)
    are explicitly encouraged — LLM is told to bring in other dimensions if relevant
  - Concept links [[double brackets]] and TAGS are clearly distinguished in the prompt
    to prevent LLM from confusing the two systems
  - Callout box position is mid-article (not end) for better reading UX
  - Factual anchor is "use for accuracy, do NOT copy prose" — prevents plagiarism
  - Hard caps: 2000 chars for CA input, 700 words output — prevent token blowout
"""

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


# ── Prompt Template ───────────────────────────────────────────────────────────
# This is the master prompt that drives every Daily CA article.
# It is designed to produce editorial-quality writing, not exam notes.
# Every instruction has a reason:
#   - "genuinely valuable to ALL readers" → prevents exam-note regression
#   - "cross-cutting dimensions" → enables multi-dimensional articles
#   - "do NOT copy prose" from static anchor → prevents plagiarism
#   - Forbidden headings list → prevents the LLM's habitual UPSC filler
#   - [[double brackets]] vs TAGS distinction → prevents system confusion
#   - Callout mid-article → better UX than a callout at the end

CA_DAILY_PROMPT_TEMPLATE = """\
SYSTEM:
You are a senior editorial writer for a premier knowledge platform read by
curious citizens, students, researchers, policymakers, and civil service aspirants.
Write content that is informative, factual, deeply analytical, and genuinely valuable
to ALL readers — not exclusively for exam preparation. Your standard is The Hindu's
editorial page meets an intelligent explainer from a top policy think-tank.

SUBJECT: {subject_name}
TONE GUIDE: {subject_tone}

IMPORTANT — MULTI-DIMENSIONAL WRITING:
A topic may have dimensions beyond its primary subject. If this topic has significant
connections to other domains (e.g., an economic policy with geopolitical implications,
an environmental issue with governance or rights dimensions, a security development with
socioeconomic roots), you are ENCOURAGED to bring those dimensions in naturally where they
add genuine depth. Do not confine yourself artificially to one lens if the topic demands more.

─────────────────────────────────────────
TODAY'S NEWS CONTEXT (the trigger for this article):
{ca_chunks_text}
─────────────────────────────────────────

FACTUAL ANCHOR (verified facts about this topic — use ONLY for factual accuracy;
do NOT copy this prose into your article):
{static_key_facts}

SUPPLEMENTARY REFERENCE (Wikipedia context — use as background, not to copy):
{wiki_enrichment}
─────────────────────────────────────────

WRITING INSTRUCTIONS — READ CAREFULLY:

1. TITLE
   - Sharp, specific, newsworthy — 10 to 15 words maximum
   - Must reflect today's specific development, not a generic topic label
   - Good: "India's Fast Breeder Reactor Hits Full Power — What It Means for Energy Security"
   - Bad: "Nuclear Energy in India"

2. OPENING (first 2-3 sentences)
   - Lead with what happened TODAY and why it matters in the larger picture
   - Do not start with a dictionary definition
   - Create genuine curiosity — make the reader want to continue

3. BODY SECTIONS
   - Choose section headings based on what THIS SPECIFIC TOPIC requires
   - Suggested heading types (pick what fits, do NOT use all):
       "What is [X]?" — only for genuinely unfamiliar concepts needing explanation
       "How It Works / How It Happened" — for process-heavy or event-driven topics
       "India's Position / Current Status" — for ongoing situations
       "Key Provisions / Legal Framework" — for constitutional or legislative topics
       "The Numbers That Matter" — for data-heavy economic or environmental topics
       "Historical Context" — when today's event only makes sense with backstory
       "Stakeholders and Their Interests" — for multi-actor policy disputes
       "International Dimension" — for cross-border or multilateral angles
       "Challenges on the Ground" — where implementation gaps are real and documented
       "Significance and What Changes Now" — for decisions/judgements with wide impact
       "Way Forward" — only when you have something concrete and non-generic to say
   - FORBIDDEN headings (instant quality failure):
       "UPSC Angle", "Exam Relevance", "Prelims Focus", "Mains Value",
       "Practice Questions", "Important for UPSC", "Why in News"
   - Use ## headings only. No ### sub-headings. No bullet-heavy sections.
   - Write in paragraphs. Bullets only when listing genuinely list-like things (e.g., treaty provisions).

4. INLINE CONCEPT LINKS — [[double brackets]]
   Use [[double brackets]] for 5 to 8 HIGH-VALUE specific terms that deserve their own
   dedicated explanation page. These are NOT keyword labels — they are deep-dive links.

   USE [[brackets]] for:
     - Specific Acts and laws: [[Civil Liability for Nuclear Damage Act 2010]]
     - Named schemes with specific mandates: [[PM-KUSUM]], [[AMRUT 2.0]]
     - Technical/scientific terms non-specialists won't know: [[HALEU]], [[Small Modular Reactors]]
     - Landmark constitutional events: [[101st Constitutional Amendment]]
     - Specific institutions with specific mandates: [[Nuclear Power Corporation of India]]
     - International frameworks: [[Sendai Framework for DRR]], [[Kunming-Montreal Framework]]

   DO NOT use [[brackets]] for:
     - Generic topic words: federalism, parliament, judiciary, climate change (use TAGS for these)
     - Terms fully explained within this very article
     - Every technical noun — only genuinely concept-rich, high-value terms
     - More than 8 terms total

5. CALLOUT BOX
   Insert exactly ONE callout box at a natural mid-article break point:
   :::callout
   **Did You Know?** [One genuinely surprising, counterintuitive, or little-known fact
   about this topic — something a well-read reader would find worth pausing for.]
   :::
   Do NOT place it at the end. Do NOT make it a summary of the article.

6. LENGTH AND QUALITY
   - Target: 500 to 680 words of body text (not counting TAGS/SOURCE lines)
   - Hard maximum: 800 words. Never exceed this.
   - Quality over quantity. Every sentence must earn its place.
   - No filler phrases: "It is pertinent to note that...", "In this context...",
     "It goes without saying...", "India has a long history of..."
   - No hedging padding: "This may have implications for...", "Some experts believe..."
     unless you have a specific expert or specific study to cite.

7. CLOSING TWO LINES (mandatory, exactly this format):
   TAGS: [5-8 comma-separated keywords — short, generic, UPSC-relevant discovery labels]
   SOURCE: [source publication name] — [URL]

   TAGS rules:
     - Generic and discoverable: "nuclear-energy", "environment", "fiscal-policy", "india-china"
     - These are DIFFERENT from [[inline concept links]] — do not repeat them
     - Lowercase-hyphenated, 1-3 words each
     - No organisation names, no article titles

DO NOT INCLUDE in the article body:
  - Any mention of "UPSC", "GS1", "GS2", "GS3", "GS4", "exam", "aspirants", "syllabus"
  - Practice questions, answer pointers, or hints
  - Generic sentences like "This is important for Mains" or "This topic is frequently asked"
  - ### sub-sub-headings (only ## allowed)
  - More than 700 words of body text
  - Copy-pasted prose from the FACTUAL ANCHOR or SUPPLEMENTARY REFERENCE
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
                          Used to select subject tone from SUBJECT_TONE_MAP.
        topic_name:       Knowledge topic name (e.g. "Fiscal Federalism").
                          Currently unused in the template but available for
                          future prompt personalisation (e.g., topic-specific
                          section heading suggestions).

    Returns:
        Fully formatted prompt string ready for llm_call().
    """
    tone = SUBJECT_TONE_MAP.get(subject_name, SUBJECT_TONE_MAP["default"])

    formatted_static = _format_static_facts(static_key_facts)
    formatted_wiki = _format_wiki_enrichment(wiki_enrichment)

    # Hard cap on CA input — prevents token overflow for long article chunks
    ca_text_capped = ca_chunks_text[:2000] if ca_chunks_text else "Not available."

    return CA_DAILY_PROMPT_TEMPLATE.format(
        subject_name=subject_name or "General Studies",
        subject_tone=tone,
        ca_chunks_text=ca_text_capped,
        static_key_facts=formatted_static,
        wiki_enrichment=formatted_wiki,
    )
