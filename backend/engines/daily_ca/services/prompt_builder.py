"""
engines/daily_ca/services/prompt_builder.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase I  — CA_DAILY_PROMPT Builder
Phase D2 (FEATURES3) — Richer context window (4000 chars), CONCEPT-NEWS BRIDGE,
                        DATA INTEGRITY instruction, all-subject paragraph guidance.

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
  - Hard caps: 4000 chars for CA input (up from 2000), 680 words output target
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
TODAY'S NEWS CONTEXT (the trigger and hook for this article):
{ca_chunks_text}
─────────────────────────────────────────

CONCEPTUAL DEPTH ANCHOR (verified facts, frameworks, provisions for this topic —
use to explain the UNDERLYING CONCEPT with precision and depth;
do NOT copy this prose verbatim into your article):
{static_key_facts}

SUPPLEMENTARY REFERENCE (Wikipedia background — use for additional context, not to copy):
{wiki_enrichment}
─────────────────────────────────────────

WRITING INSTRUCTIONS — READ CAREFULLY:

0. THE CORE EDITORIAL PRINCIPLE — NEWS AS THE HOOK, CONCEPT AS THE DEPTH
   Every article must achieve TWO things simultaneously, and achieve both well:
     a) Tell the specific news story precisely — what happened, who, when, exact figures
        from TODAY'S NEWS CONTEXT. This is the HOOK that makes the article timely.
     b) Explain the underlying concept, mechanism, or framework — from CONCEPTUAL
        DEPTH ANCHOR. This is the DEPTH that makes the article genuinely educational.

   The reader must finish knowing BOTH:
     → Exactly what happened today and what it means immediately
     → The deeper concept, law, framework, or process that gives it lasting significance

   This is the bridge every article must build — examples across all subjects:

     GS1 / Geography:
       Cyclone makes landfall in Tamil Nadu
       → Explain cyclone formation, Bay of Bengal's warm surface temperature, why
         Tamil Nadu and Andhra Pradesh coast are structurally vulnerable, historical
         pattern of October-November cyclones in the region

     GS1 / History/Culture:
       Archaeological find challenges colonial dating of an ancient site
       → Explain the dating methodology (radiocarbon, stratigraphy), the historical
         significance of the site in India's civilisational narrative, what this
         changes in the existing archaeological consensus

     GS2 / Polity:
       Supreme Court strikes down a law or issues a landmark order
       → Explain the constitutional article or doctrine invoked, the precedent chain,
         what the judgement changes institutionally, why it shifts the balance of power

     GS2 / International Relations:
       India-China border disengagement, or a bilateral summit outcome
       → Explain the Line of Actual Control's legal ambiguity, the 1993/1996 framework
         treaties, what "disengagement" and "patrolling" mean under these agreements

     GS3 / Economy:
       RBI changes repo rate, or a major budget allocation is announced
       → Explain the monetary transmission mechanism or the fiscal framework being used,
         how this affects inflation, credit, EMIs, the rupee, and specific sectors

     GS3 / Environment:
       Tiger/elephant census released, coral bleaching reported, new protected area
       → Explain the conservation framework (Project Tiger, Wildlife Protection Act,
         IUCN categories), what the numbers mean relative to targets and benchmarks

     GS3 / Science & Technology:
       ISRO satellite launch, nuclear reactor milestone, or tech policy announcement
       → Explain the technology precisely — what the satellite does, the reactor
         type, the frequency spectrum — and what capability gap it fills strategically

     GS3 / Security:
       Terrorist designation, border incident, or new security law enforcement
       → Explain the legal framework (UAPA, NIA Act, AFSPA), the agency mandates,
         the socioeconomic roots of the threat alongside the law enforcement response

     GS4 / Ethics:
       Whistleblower faces transfer, corruption case verdict, institutional failure
       → Explain the ethical framework at stake (conflicting duties, public trust),
         reference the Whistleblower Protection Act, the philosophical tension between
         institutional loyalty and public duty

   If CONCEPTUAL DEPTH ANCHOR is "Not available":
     Use TODAY'S NEWS CONTEXT + SUPPLEMENTARY REFERENCE for both layers.
     Do NOT make up conceptual frameworks that are not in your source material.
     Be honest about what is not in the sources — write at the correct confidence level.

─────────────────────────────────────────

DATA INTEGRITY (non-negotiable — enforced strictly):
  You are writing for a highly informed Indian audience — researchers, policymakers,
  civil service aspirants, and educated citizens. They WILL notice fabricated data.

  ONLY state specific numbers, percentages, rupee figures, dates, names, or statistics
  if they appear in TODAY'S NEWS CONTEXT, CONCEPTUAL DEPTH ANCHOR, or SUPPLEMENTARY REFERENCE.

  DO NOT invent:
    - Specific rupee amounts or percentage figures not in your sources
    - Population statistics, GDP numbers, or rankings not in your sources
    - Names of officials, ministers, judges, or scientists not in your sources
    - Treaty article numbers, constitutional article numbers not in your sources
    - Direct quotes attributed to named individuals not in your sources
    - Precise dates not in your sources

  If a fact supports your analysis but you do not have the precise figure:
    ✓ Write: "India is among the top five globally in..." (directional, honest)
    ✓ Write: "The scheme allocates substantial resources to..." (directional)
    ✗ Never write: "India ranks 3rd globally" if you don't have that from sources
    ✗ Never write: "₹47,000 crore allocated" if you're guessing

  If genuinely uncertain, omit the specific claim rather than fabricate it.
  A well-written article with fewer cited facts is better than a fabricated one.

─────────────────────────────────────────

1. TITLE
   - Sharp, specific, newsworthy — 10 to 15 words maximum
   - Must reflect today's specific development, not a generic topic label
   - Good: "India's Fast Breeder Reactor Hits Full Power — What It Means for Energy Security"
   - Bad: "Nuclear Energy in India"

2. OPENING (first 2-3 sentences)
   - Lead with what happened TODAY and why it matters in the larger picture
   - Do not start with a dictionary definition
   - Create genuine curiosity — make the reader want to continue
   - SUMMARY BOX: This opening paragraph is automatically extracted as a
     "Summary Box" displayed prominently above the article body. Write it as
     2–3 self-contained, standalone sentences that summarise the core news
     development — it must make complete sense read in isolation.
     The REST of the article must NOT repeat these same sentences — it must
     BUILD on them with deeper analysis, contextual data, legal frameworks,
     historical roots, and forward-looking implications.
     Think of it as a newspaper lede: tight, factual, and compelling on its own.

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
   - Use ## headings only. No ### sub-headings.
   - PARAGRAPH STRUCTURE (critical — enforced across all subjects):
       Under each ## heading, write 2 to 3 separate paragraphs.
       Each paragraph: 2 to 4 sentences. Leave a blank line between paragraphs.
       Do NOT write one long, dense paragraph that fills the entire section.
       Each paragraph should answer one distinct sub-question:
         Para 1: What/Who/Where — the core fact, provision, or claim
         Para 2: Why/How — the mechanism, process, cause, or legal basis
         Para 3: So What — the implication, consequence, or broader significance
       Not every section requires all three — apply editorial judgment.
       Subjects-specific guidance:
         GS1 (History/Geography/Culture): Para structure helps separate event → context → legacy
         GS2 (Polity/IR): Separate the legal provision → institutional interpretation → real-world impact
         GS3 (Economy/S&T/Environment/Security): Separate the data → the policy response → the gap
         GS4 (Ethics): Separate the dilemma → competing values → resolution framework
   - Bullets ONLY for genuinely enumerable items (treaty provisions, constitutional articles,
     scheme components, statistical comparisons). Never use bullets to substitute for analysis.

3b. ANTI-REPETITION (strict — applies across all subject areas)
    Every fact, figure, provision, or named reference must appear EXACTLY ONCE
    in the entire article. Repetition signals shallow thinking — never do it.

    If you have already stated something in one section, do NOT restate it in another:
      GS1/History:     A date, a leader's name, a battle/treaty reference
      GS1/Geography:   A river's length, a state's area, a climate zone classification
      GS2/Polity:      A constitutional Article number, a landmark judgement citation
      GS2/IR:          A bilateral framework name, a treaty year, a summit outcome
      GS3/Economy:     A GDP figure, a scheme outlay, an import/export percentage
      GS3/Environment: A species count, a forest cover percentage, an emissions target
      GS3/S&T:         A satellite name, a reactor specification, a patent figure
      GS3/Security:    A legal provision, an agency mandate, an incident reference
      GS4/Ethics:      A thinker's name, a principle definition, a case reference

    Test: before writing each new section, ask "Have I already said this?"
    If yes — delete the repetition. Move on to new depth, not a restatement.
    If you feel the urge to write "as mentioned above" or "as noted earlier" —
    that is a repetition signal. Delete the repeated sentence, not the reference.

4. INLINE CONCEPT LINKS — [[double brackets]] — MANDATORY
   You MUST embed exactly 5 to 8 [[double bracket]] concept links in the article body.
   This is not optional — articles with fewer than 5 concept links fail quality review.
   These are deep-dive reference links, NOT keyword discovery labels (those go in TAGS).

   REQUIRED [[brackets]] for terms like:
     - Specific Acts and laws: [[Civil Liability for Nuclear Damage Act 2010]]
     - Named schemes with specific mandates: [[PM-KUSUM]], [[AMRUT 2.0]]
     - Technical/scientific terms non-specialists won't know: [[HALEU]], [[Small Modular Reactors]]
     - Landmark constitutional events: [[101st Constitutional Amendment]]
     - Specific institutions with specific mandates: [[Nuclear Power Corporation of India]]
     - International frameworks: [[Sendai Framework for DRR]], [[Kunming-Montreal Framework]]
     - Named court judgements: [[Kesavananda Bharati Case]], [[Maneka Gandhi Judgment]]
     - Named treaties or conventions: [[Montreal Protocol]], [[Basel Convention]]

   DO NOT use [[brackets]] for:
     - Generic topic words: federalism, parliament, judiciary, climate change (use TAGS for these)
     - Terms already fully explained within this very article
     - Every technical noun — only genuinely concept-rich, linkable terms
     - More than 8 terms total

   COUNT CHECK before submitting: ensure you have placed at least 5 [[term]] links
   distributed across the article body — not all in one section.

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

7. CLOSING THREE LINES (mandatory, exactly this format):
   CATEGORY: [exactly one from: national | international | geo-politics | geo-economics | economy | science-tech | environment | society | law-justice | defence | health | sports-awards]
   TAGS: [5-8 comma-separated keywords — short, generic, discoverable topic labels]
   SOURCE: [source publication name] — [URL]

   CATEGORY rules:
     - Pick EXACTLY ONE from the fixed list above. No custom categories.
     - Based on the PRIMARY angle of THIS article (not the GS subject):
         Economic impact of India-China tensions → geo-economics (not economy)
         Israel-Iran war impact on Indian oil prices → geo-economics
         Supreme Court judgement on forest rights → law-justice
         ISRO satellite launch → science-tech
         Climate COP summit → environment
         State election results → national

   TAGS rules:
     - Generic and discoverable: "nuclear-energy", "environment", "fiscal-policy", "india-china"
     - These are DIFFERENT from [[inline concept links]] — do not repeat the same terms
     - Lowercase-hyphenated, 1-3 words each
     - MINIMUM 5 tags required — if the article covers a narrow topic, add subject-area labels
     - No organisation names, no article titles

DO NOT INCLUDE in the article body:
  - Any mention of "UPSC", "GS1", "GS2", "GS3", "GS4", "exam", "aspirants", "syllabus"
  - Practice questions, answer pointers, or hints
  - Generic exam-language phrases (ALL of these are banned):
      "it matters for UPSC", "civil services perspective", "from an exam standpoint",
      "UPSC aspirants should note", "for Mains preparation", "for Prelims",
      "this is important from the perspective of", "important for competitive exams"
  - Clichéd opening gambits (these drain trust immediately — NEVER use):
      "In the context of...", "It is pertinent to note that...",
      "India has a long history of...", "In recent times...", "In recent years...",
      "Against this backdrop...", "In the wake of...", "Amid growing concerns..."
  - Vague hedging filler (only cite when you have a real name/study to attach):
      "This may have implications...", "Experts believe...", "Some analysts say...",
      "It is widely acknowledged...", "It goes without saying...",
      "Many feel that...", "It is believed that..."
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

    # Phase D2: raised cap 2000 → 4000 chars — enriched context includes
    # both chunk text (focused relevance) + parent article content (factual depth)
    ca_text_capped = ca_chunks_text[:4000] if ca_chunks_text else "Not available."

    return CA_DAILY_PROMPT_TEMPLATE.format(
        subject_name=subject_name or "General Studies",
        subject_tone=tone,
        ca_chunks_text=ca_text_capped,
        static_key_facts=formatted_static,
        wiki_enrichment=formatted_wiki,
    )
