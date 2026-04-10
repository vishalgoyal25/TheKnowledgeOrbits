"""
engines/book_content/services/quality_engine_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAYER 2: Writing Quality Engine

Contains:
  1. The master writing prompt builder (with craft instructions)
  2. Section-by-section generation orchestrator
  3. Self-critique and refinement pass
  4. Quality score calculator
  5. Phase 4.5B: Formatting pass (tables, callouts, infographic markers)
  6. Phase 4.5C: Adaptive subject personas (SUBJECT_PROFILES)

This replaces the simple _generate_subtopic_article() in ingestor.py.
Ported from: upsc-agent-lab/src/quality_engine.py
Changes: logging (structlog), imports, added SUBJECT_PROFILES, added
         _run_formatting_pass(), subject param injected into _build_section_prompt().
Updated (Phase A): MASTER_STYLE_ANCHOR (subject-agnostic), SECTION_PLAN (5 sections,
                   upsc_angle removed), SUBJECT_PROFILES (all 14 subjects, extended keys).
Preserved exactly: _generate_sections(), _run_critique(), _refine_weak_sections(),
                   _assemble_article(), _parse_critique_json().
"""

import json
import re

import structlog

from .llm_service import llm_call

logger = structlog.get_logger(__name__)


# ── MASTER STYLE ANCHOR ───────────────────────────────────────────────────────
# Injected into EVERY generation prompt regardless of subject.
# Subject-specific tone and emphasis are handled by SUBJECT_PROFILES below.

MASTER_STYLE_ANCHOR = """
WRITING STYLE — NON-NEGOTIABLE RULES:

PRECISION OVER PADDING:
  ✅ "The Schedules VI tribes of Northeast India are governed by autonomous district
      councils with legislative, executive, and judicial powers under Article 244."
  ✅ "India's forest cover stands at 21.71% of geographic area (FSI 2021), of which
      dense forest constitutes only 3.04%."
  ❌ "India has a large forest area that is protected through various laws."
  Rule: Every sentence must carry maximum information. Zero filler words.
        If a sentence could appear in a 5th-grade textbook, rewrite it.

SPECIFICITY IS MANDATORY — name exact references, ALWAYS:
  ✅ Articles, Schedules, Amendments (Article 370, 6th Schedule, 42nd Amendment 1976)
  ✅ Acts with year (Forest Rights Act 2006, PESA 1996, UAPA 2019)
  ✅ Committees and reports (Swaran Singh Committee 1976, Punchhi Commission 2010)
  ✅ Case laws with year (Kesavananda Bharati v. State of Kerala, 1973)
  ✅ Data with source and year (7.2% GDP growth, RBI Annual Report 2023-24)
  ✅ Schemes with full name (PM-KISAN, MGNREGS, PMGSY, Ayushman Bharat-PMJAY)
  ✅ Organizations with full form on first use (NDMA, ISRO, CPCB, WMO)
  ❌ "Constitutional amendments have changed this over time"
  ❌ "Many committees have examined this issue"
  ❌ "Several landmark judgments have shaped this area"
  ❌ "Recent data shows improvement"

WRITING FOR PREPARED ASPIRANTS — not beginners:
  - Reader has read NCERT once and knows basic concepts
  - Do NOT define what democracy, constitution, GDP, or photosynthesis mean
  - DO explain nuances, exceptions, internal contradictions, and inter-topic links
  - Challenge the reader's existing understanding — add the 20% they don't know

ACTIVE, DIRECT SENTENCES:
  ✅ "The GST Council operates on a three-quarter majority rule, giving states
      collective veto power over Central proposals."
  ❌ "It can be seen that the GST Council has been given a structure where decisions
      are made through a majority that involves both Centre and states."

NO HEDGING — EVER:
  ❌ "It may be noted that...", "It is important to understand that..."
  ❌ "As we know...", "Needless to say...", "It goes without saying..."
  ❌ "One could argue that...", "Some experts believe..."
  ✅ State the fact, the position, the debate — directly.

HEADING DISCIPLINE:
  - Use only ## (article title) and ### (section headings)
  - NO #### sub-sub-headings — flatten into prose or a table instead
  - Section headings must be adapted to the subject: rename the default heading
    if a more accurate label exists for the topic being written

TABLES: Use only when comparison genuinely adds value.
  Good: Rajya Sabha vs Lok Sabha (same attributes, side-by-side)
  Good: Types of disasters (classification with distinct categories)
  Bad: Single-column list disguised as a 2-column table
  Bad: Table where all cells say "varies by context"
"""


# ── SECTION TEMPLATES ─────────────────────────────────────────────────────────
# 5 sections per article — generated ONE BY ONE for depth.
# upsc_angle removed (Phase A). Dynamic headings: LLM chooses per topic (Phase A).
#
# Each section has:
#   id              — internal key for tracking
#   heading_directive — tells the LLM HOW to invent a topic-specific heading,
#                       with examples, a pattern, and an explicit forbidden list.
#                       The LLM MUST begin its output with "### [chosen heading]".
#   instruction     — WHAT to write in this section (content coverage rules).
#
# Anti-duplication is enforced at runtime: _generate_sections() tracks all headings
# already written and injects them as forbidden in the next section's prompt.

SECTION_PLAN = [
    {
        "id": "definition",
        "heading_directive": """SECTION 1 OF 5 — FOUNDATION
Your job: establish WHAT {subtopic} IS and its authoritative basis.

HEADING RULE — you must write a heading that:
  ✅ Contains at least one key term directly from the topic "{subtopic}"
  ✅ Signals "what this is" and "where it comes from"
  ✅ Is 3–8 words, Title Case, starts with ###
  ✅ Pattern options: "[Topic Term]: [Basis/Origin]"  |  "[Nature] of [Topic]"
                      "[Topic] — [Source/Classification]"

Good heading examples (pick style, adapt content):
  • "Judicial Review: Constitutional Basis & Scope"
  • "Monsoon: Meteorological Definition & Classification System"
  • "GDP: Concept, Measurement Methodology & India's Framework"
  • "Ahimsa: Philosophical Origins in Jain & Gandhian Thought"
  • "Emergency Provisions: Constitutional Nature & Taxonomy"

FORBIDDEN headings (never use these):
  ✗ "Introduction"  ✗ "Overview"  ✗ "Definition"  ✗ "Background"
  ✗ "What is [topic]"  ✗ "Understanding [topic]"  ✗ Any single-word heading""",

        "instruction": """Write the precise definition and conceptual foundation of {subtopic}.
Begin with the exact NCERT or most authoritative definition (verbatim if available).
Then establish the formal basis — choose the correct type for this subject:
  Polity topics    → exact Article number, Schedule, or Constitutional provision
  History topics   → exact date, location, and periodisation
  Geography topics → the physical/chemical process and scientific classification
  Economy topics   → formal economic definition and measurement methodology
  Science topics   → the scientific principle, mechanism, or technical standard
  Ethics topics    → the philosophical tradition and its core normative claim
  Environment      → ecological definition and IUCN/international classification
  Security/DM      → legal definition and statutory classification

Also address: what {subtopic} IS NOT — dispel the most common misconception upfront.
Length: 150–250 words. No padding. Every sentence = one unit of information.""",
    },

    {
        "id": "framework",
        "heading_directive": """SECTION 2 OF 5 — GOVERNING STRUCTURE
Your job: lay out the LAWS, INSTITUTIONS, or THEORETICAL ARCHITECTURE governing {subtopic}.

HEADING RULE — you must write a heading that:
  ✅ Names the type of structure you're describing (legal / institutional / theoretical / scientific)
  ✅ Includes a structural word: "Framework", "Architecture", "Provisions", "Mandate",
     "Foundations", "Structure", "Regime", "System"
  ✅ Is specific enough that someone reading only the heading knows WHICH framework
  ✅ Is 3–8 words, Title Case, starts with ###

Good heading examples (adapt content, not just copy):
  • "Constitutional Framework: Articles 32, 226 & Writ Jurisdiction"
  • "DM Act 2005: Legislative Architecture & Three-Tier Mandate"
  • "FRBM Act & RBI Framework: Fiscal & Monetary Rule System"
  • "Theoretical Foundations: Consequentialism, Deontology & Virtue Ethics"
  • "Wildlife Protection Act 1972: Legal Regime & Protected Area System"
  • "Plate Tectonic Framework: Convergent, Divergent & Transform Boundaries"

FORBIDDEN headings:
  ✗ "Framework" alone  ✗ "Legal Basis"  ✗ "Structure"  ✗ "Overview"
  ✗ Any heading already used in this article (see forbidden list above)""",

        "instruction": """Write the complete formal framework governing {subtopic}.
For EACH element of the framework: name it precisely, state what it mandates or establishes,
and explain its practical significance. Do not list names without substance.

What counts as framework depends on the subject:
  Polity/Governance → Articles, Schedules, Amendments, landmark SC judgments
  Economy          → Acts (FRBM, RBI Act, SEBI Act), regulatory bodies, fiscal rules
  Environment      → WPA 1972, FCA 1980, EPA 1986, FRA 2006, international conventions
  Security/DM      → UAPA, AFSPA, DM Act 2005, NIA Act — with exact year and key provision
  History          → Colonial policy structure, treaty framework, or ideological forces
  Geography        → Scientific classification system, tectonic or climatic framework
  Ethics           → Philosophical traditions (Kantian, utilitarian, virtue, Gandhian)
  S&T              → Governing standards, regulatory bodies, international agreements

Include all amendments, revisions, or updates with exact years and effect.
Format: structured prose with precise citations — NOT a bare bullet dump.
Length: 200–400 words.""",
    },

    {
        "id": "core_content",
        "heading_directive": """SECTION 3 OF 5 — THE CORE (most detailed section)
Your job: write the MAIN substantive content on {subtopic} — what it IS, how it WORKS,
or what its internal DYNAMICS are. This is the richest, most fact-dense section.

HEADING RULE — you must write a heading that:
  ✅ Directly names the specific substance of {subtopic} — what the section actually covers
  ✅ Contains a topic-specific term (NOT generic words like "key aspects" or "main points")
  ✅ Reflects the actual content type: composition / mechanism / actors / patterns /
     causes-course-consequences / structure / indicators / ecosystem
  ✅ Is 4–10 words, Title Case, starts with ###
  ✅ Must be clearly DIFFERENT from sections 1 and 2

Good heading examples (these show the variety — do not copy, adapt):
  • "Bicameral Composition: Lok Sabha, Rajya Sabha & Their Asymmetric Powers"
  • "Non-Cooperation Movement: Phases, Mass Mobilisation & Internal Fractures"
  • "Western Ghats: Orographic Rainfall, Soil Types & Watershed Dynamics"
  • "GST: Rate Slab Architecture, Council Voting & Input Tax Credit Mechanism"
  • "Project Tiger: Reserve Network, Buffer-Core Zoning & Species Recovery Data"
  • "Emotional Intelligence: Goleman's Model, Components & IAS Relevance"
  • "NDRF: Battalion Deployment, Operational Mandate & Activation Protocol"

FORBIDDEN headings:
  ✗ "Core Content"  ✗ "Main Section"  ✗ "Key Aspects"  ✗ "Important Points"
  ✗ "Key Features"  ✗ "Overview"  ✗ "Details"  ✗ "Analysis"
  ✗ Any heading already used in this article""",

        "instruction": """Write the core substantive section on {subtopic}.
This is the MOST DETAILED section — a serious aspirant must find everything they need here.

Cover the type of content most relevant to {subtopic}:
  For institutions      → full composition, appointment, tenure, powers, functions
  For processes/systems → step-by-step mechanism, actors at each stage, decision rules
  For historical events → phases, key actors, their positions, turning points, internal divisions
  For geographic topics → distribution patterns, controlling factors, regional variations,
                          anomalies that need explaining
  For economic topics   → data trends (3–5 years), sectoral breakdown, structural drivers,
                          transmission mechanisms
  For S&T topics        → how the technology works, India's specific capabilities, key projects
  For environment       → species/ecosystem specifics, threat quantification, conservation
                          architecture with named reserves/schemes
  For security/DM       → threat matrix, institutional response layers, inter-agency roles

Use numbered lists only when sequence genuinely matters.
Use tables only for true comparison (≥2 entities, identical attributes).
Use prose for analysis, cause-effect, and complexity.
Length: 350–650 words.""",
    },

    {
        "id": "evolution",
        "heading_directive": """SECTION 4 OF 5 — CHANGE OVER TIME
Your job: trace HOW {subtopic} developed, reformed, or transformed across time.

HEADING RULE — you must write a heading that:
  ✅ Contains a temporal or change-signalling word:
     "Evolution", "Trajectory", "From X to Y", "Reform History", "Transformation",
     "Milestones", "Development", "Since [year]", "Pre- and Post-[event]"
  ✅ Names the SPECIFIC change arc — not just "history of [topic]"
  ✅ Anchors to a real turning point, landmark event, or year range WHERE POSSIBLE
  ✅ Is 4–10 words, Title Case, starts with ###

Good heading examples:
  • "Constitutional Evolution: Golak Nath (1967) to Basic Structure Doctrine (1973)"
  • "Trade Policy Trajectory: Import Substitution to WTO-Era Liberalisation"
  • "Tiger Conservation: Project Tiger 1973 to NTCA & 5th Cycle Census 2023"
  • "Disaster Governance: From Reactive Relief to Sendai Framework Alignment"
  • "Non-Alignment to Strategic Autonomy: India's Foreign Policy Arc"
  • "From Canal Irrigation to Micro-Irrigation: Water Policy Shifts"

FORBIDDEN headings:
  ✗ "History" alone  ✗ "Evolution" alone  ✗ "Development" alone
  ✗ "Background"  ✗ "Timeline"  ✗ "Historical Overview"
  ✗ Any heading already used in this article""",

        "instruction": """Write a precise, chronologically ordered account of how {subtopic} evolved.
Include only what is GENUINELY relevant — do not pad with unrelated history.

What to cover (select applicable items):
  - Foundational/pre-independence background (only if it directly shapes the present)
  - Original form at independence or first enactment (the baseline)
  - Each significant legislative, policy, or institutional change with EXACT year and effect
  - Landmark judicial rulings: case name, year, and the specific shift it caused
  - International agreements or conventions adopted: name, year, India's obligation
  - Committee/Commission recommendations that were actually adopted (not just proposed)
  - Post-2015 developments and current status as of 2024

Format: flowing prose with years clearly embedded in sentences.
NOT a bare date-list. Years should appear as: "The 44th Amendment (1978) reversed..."
Length: 200–350 words.""",
    },

    {
        "id": "significance",
        "heading_directive": """SECTION 5 OF 5 — CRITICAL ANALYSIS
Your job: interrogate {subtopic} — its live debates, structural tensions, failures,
and reform agenda. This section must have intellectual edge. Do NOT summarize earlier sections.

HEADING RULE — you must write a heading that:
  ✅ Signals critique, tension, or contested stakes — NOT neutral description
  ✅ Must use AT LEAST ONE of: "Debate", "Critique", "Tension", "Gap", "Paradox",
     "Failure", "Deficit", "Stakes", "Challenge", "Unresolved", "vs", "Limits of"
  ✅ Names the SPECIFIC debate or tension — not just "challenges and way forward"
  ✅ Is 4–10 words, Title Case, starts with ###

Good heading examples:
  • "Anti-Defection Law: Speaker Bias, Loopholes & Stalled Reform"
  • "Forest Rights vs Conservation: The Adivasi Dispossession Paradox"
  • "India's NDC Ambition vs Coal Dependency: The Net-Zero Tension"
  • "Electoral Bonds: Anonymity by Design & the Transparency Deficit"
  • "Naxalism vs Development: The Limits of Security-Only Response"
  • "MGNREGS: Guaranteed Right vs Chronic Underfunding Gap"
  • "Non-Alignment's Legacy: Strategic Autonomy or Fence-Sitting?"

FORBIDDEN headings:
  ✗ "Conclusion"  ✗ "Summary"  ✗ "Significance"  ✗ "Importance"
  ✗ "Critical Analysis"  ✗ "Contemporary Relevance"  ✗ "Challenges and Way Forward"
  ✗ "Way Forward"  ✗ Any heading already used in this article""",

        "instruction": """Analyze {subtopic} critically. This section must go beyond description.

Cover ALL that apply to this topic:
  - The core structural tension or unresolved contradiction at the heart of {subtopic}
  - Named ongoing debates: cite specific positions, not just "experts disagree"
  - Structural weaknesses or implementation failures — with evidence (CAG, NCRB, survey data)
  - Where India's formal commitment diverges from ground reality (name the gap precisely)
  - Comparison with international models ONLY where it genuinely illuminates — not decorative
  - Pending reforms: Law Commission recommendations, ARC reports, SC directives,
    Parliamentary Standing Committee observations, NITI Aayog strategy notes
  - How {subtopic} connects to 2–3 other areas of the UPSC syllabus (inter-topic links)

Do NOT be neutral to the point of vagueness.
Do NOT include "exam tips", "UPSC high-yield facts", or revision bullets.
Do NOT repeat content already covered in earlier sections.
Length: 200–300 words.""",
    },
]


# ── SUBJECT PROFILES ──────────────────────────────────────────────────────────
# All 14 UPSC GS subjects. Injected into every generation prompt.
# Keys:
#   tone            — writing voice and register
#   emphasis        — what to prioritize; types of facts that must appear
#   structure       — preferred section narrative arc
#   avoid           — failure modes specific to this subject
#   example_voice   — a model sentence showing the correct register
#   key_sources     — authoritative sources to cite when available
#   critical_vocab  — must-use domain terms (use them, don't avoid them)
#   comparison_pairs — entities frequently compared in this subject
#   data_types      — classes of data/statistics to weave in where available
#   section_renames — how to rename default section headings for this subject

SUBJECT_PROFILES = {

    # ── GS PAPER I ────────────────────────────────────────────────────────────

    "Indian Heritage & Culture": {
        "tone": (
            "art-historical, civilizational, analytically reverent — treat each art form "
            "and movement as a product of specific political, religious, and economic forces"
        ),
        "emphasis": (
            "dynasty patronage systems, iconographic vocabulary, regional school distinctions, "
            "UNESCO World Heritage status where applicable, specific artefact names and locations, "
            "cross-cultural exchange (Hellenistic, Persian, Central Asian influences)"
        ),
        "structure": (
            "origin/period → defining features → regional variations & schools → "
            "patronage and socio-religious context → decline or transformation → "
            "surviving legacy and modern significance"
        ),
        "avoid": (
            "nationalist hagiography ('India always had the greatest...'), vague statements "
            "like 'rich culture', listing monuments without stylistic analysis, ignoring "
            "foreign influences that shaped Indian art"
        ),
        "example_voice": (
            "The Mathura school, flourishing under Kushana patronage (1st–3rd century CE), "
            "produced the first anthropomorphic Buddha image using indigenous red sandstone — "
            "a decisive departure from the aniconic tradition of early Buddhism."
        ),
        "key_sources": (
            "NCERT Fine Arts (Class 11-12), ASI (Archaeological Survey of India) reports, "
            "UNESCO World Heritage documentation, National Museum catalogues, "
            "Marg Publications, Stella Kramrisch on Indian temple architecture"
        ),
        "critical_vocab": (
            "iconography, stupa, chaitya, vihara, gopuram, shikhara, mandapa, fresco, "
            "tempera, lost-wax casting (cire perdue), syncretism, mudra, tribhanga, "
            "Gandhara school, Mathura school, Amaravati school, Pala-Sena period"
        ),
        "comparison_pairs": (
            "Gandhara vs Mathura school | Nagara vs Dravidian vs Vesara architecture | "
            "Pallava vs Chola bronzes | Ajanta vs Ellora | Mughal vs Rajput miniature painting"
        ),
        "data_types": (
            "UNESCO listing years and site names, dynasty period dates (CE/BCE), "
            "temple heights and dimensions where notable, excavation site dates"
        ),
        "section_renames": {
            "framework": "Patronage, Period & Stylistic Framework",
            "core_content": "Defining Features, Schools & Regional Variations",
            "evolution": "Temporal Development & Cross-Cultural Influences",
            "significance": "Legacy, Preservation Challenges & Contemporary Relevance",
        },
    },

    "Modern Indian History": {
        "tone": (
            "narrative-historical, chronologically precise, cause-effect driven — "
            "every event must be traceable to prior conditions and forward to consequences"
        ),
        "emphasis": (
            "exact dates and locations, key personalities with their ideological positions, "
            "colonial economic policies and their measurable impact, turning points in the "
            "nationalist movement, competing strands within the independence movement"
        ),
        "structure": (
            "pre-event context & structural forces → trigger/catalyst → key actors and their "
            "positions → event/movement → immediate aftermath → long-term legacy and contested historiography"
        ),
        "avoid": (
            "hagiographic descriptions of leaders, teleological 'India was destined to be free' "
            "framing, oversimplifying the Congress-Muslim League relationship, ignoring the "
            "role of World Wars in accelerating independence, skipping subaltern perspectives"
        ),
        "example_voice": (
            "The Rowlatt Act (1919), which allowed detention without trial for up to two years, "
            "galvanised a previously fragmented nationalist movement — Gandhi's call for a hartal "
            "on 6 April 1919 marked the first all-India political action under his leadership."
        ),
        "key_sources": (
            "NCERT Modern India — Bipan Chandra (Class 12), Spectrum (Rajiv Ahir), "
            "R.C. Majumdar's Advanced History of India, official colonial government records, "
            "Constituent Assembly debates (for post-1946 period)"
        ),
        "critical_vocab": (
            "Subsidiary Alliance, Doctrine of Lapse, Permanent Settlement, Ryotwari system, "
            "Mahalwari system, Swadeshi, Boycott, Home Rule, Non-Cooperation, Civil Disobedience, "
            "Quit India, INA (Indian National Army), Cabinet Mission, Mountbatten Plan, Partition"
        ),
        "comparison_pairs": (
            "Moderate vs Extremist Congress (Surat Split 1907) | Gandhi vs Subhas Bose on methods | "
            "1857 Revolt vs 1947 Transfer of Power | Tilak vs Gokhale on swaraj | "
            "Nehru vs Patel on integration of princely states"
        ),
        "data_types": (
            "exact dates of events, acts, and movements; census data showing de-industrialization; "
            "drain of wealth figures (Dadabhai Naoroji's estimates); partition displacement statistics"
        ),
        "section_renames": {
            "framework": "Historical Context & Structural Forces",
            "core_content": "Key Actors, Events & Turning Points",
            "evolution": "Phases of Development & Shifting Strategies",
            "significance": "Historical Significance, Contested Interpretations & Legacy",
        },
    },

    "World History": {
        "tone": (
            "global-comparative, analytically precise, India-anchored — "
            "world events must be related to India's historical or contemporary context "
            "wherever a genuine connection exists"
        ),
        "emphasis": (
            "major systemic shifts (industrial revolution, decolonization, Cold War), "
            "ideological conflicts and their resolution, international institutions born from "
            "key events, impact on the Global South, India's explicit connections"
        ),
        "structure": (
            "global context & structural tensions → key powers/ideological actors → "
            "event/turning point → treaty/institutional outcome → aftermath for colonized world → "
            "India's specific position and takeaway"
        ),
        "avoid": (
            "Eurocentric framing that treats Europe as the only agent of history, excessive "
            "detail on intra-European politics without India relevance, ignoring the colonized "
            "perspective, treating the Cold War as purely a US-USSR affair"
        ),
        "example_voice": (
            "The Bretton Woods Conference (1944) established the IMF and World Bank under "
            "overwhelmingly American terms — institutions that India would later criticize as "
            "structurally biased toward Western creditor nations during the 1991 crisis."
        ),
        "key_sources": (
            "NCERT Themes in World History (Class 11), Norman Lowe's Mastering Modern World History, "
            "Eric Hobsbawm's Age of Extremes, UN charter documents, Treaty of Versailles text"
        ),
        "critical_vocab": (
            "imperialism, colonialism, mercantilism, fascism, Nazism, social democracy, détente, "
            "Bretton Woods, Cold War, proxy war, decolonization, Non-Aligned Movement, "
            "Truman Doctrine, Marshall Plan, Berlin Wall, Cuban Missile Crisis"
        ),
        "comparison_pairs": (
            "WWI vs WWII (causes, scale, outcomes) | American vs French Revolution | "
            "capitalism vs communism | League of Nations vs United Nations | "
            "colonialism vs neo-colonialism"
        ),
        "data_types": (
            "war dates and casualty figures, treaty signing dates, UN/international institution "
            "founding years, colonial independence dates, Cold War timeline markers"
        ),
        "section_renames": {
            "framework": "Ideological & Structural Forces",
            "core_content": "Key Powers, Events & Turning Points",
            "evolution": "Phases of the Movement/Conflict & Outcome Trajectory",
            "significance": "Global Legacy, India's Position & Contemporary Relevance",
        },
    },

    "Indian Society": {
        "tone": (
            "sociological, ground-level, empathetic but analytically rigorous — "
            "combine quantitative data with structural analysis of power and inequality"
        ),
        "emphasis": (
            "social stratification systems (caste, class, gender, tribe), constitutional "
            "provisions addressing inequality, census and NFHS data, vulnerable group specifics "
            "(SC/ST/OBC/minorities/women/disabled), urbanization and migration patterns"
        ),
        "structure": (
            "sociological concept/phenomenon → theoretical frameworks (Indian and Western) → "
            "Indian empirical context with data → constitutional and legal response → "
            "implementation reality → persistent gaps and reform directions"
        ),
        "avoid": (
            "moralistic preaching without sociological grounding, abstract Western theory "
            "without Indian application, presenting caste purely as a historical relic "
            "(it remains structurally active), ignoring intersectionality"
        ),
        "example_voice": (
            "The Scheduled Caste population constitutes 16.6% of India's total (Census 2011), "
            "yet owns only 9% of agricultural land — a structural dispossession that Article 17's "
            "abolition of untouchability has been insufficient to reverse."
        ),
        "key_sources": (
            "NCERT Sociology (Class 11-12: Indian Society + Social Change), Census of India 2011, "
            "NFHS-5 (2019-21), NCRB Crime Reports, Tribal Affairs Ministry Annual Reports, "
            "Sachar Committee Report 2006, Pinarayi Commission reports"
        ),
        "critical_vocab": (
            "varna, jati, gothra, untouchability, Dalit, Adivasi, patriarchy, intersectionality, "
            "sanskritization (M.N. Srinivas), dominant caste, creamy layer, OBC, EWS, "
            "communalism, secularism, regionalism, linguistic nationalism, tribe-caste continuum"
        ),
        "comparison_pairs": (
            "caste vs class (Weber vs Marx) | rural vs urban society | "
            "Scheduled Tribe vs Scheduled Caste constitutional provisions | "
            "traditional vs modern family structures | Panchayat Raj vs Urban Local Bodies"
        ),
        "data_types": (
            "Census 2011 percentages (SC/ST/OBC population), sex ratio (929 per 1000 males), "
            "literacy rates by group, NFHS-5 nutrition and health indicators, "
            "urbanization % (31.16%), Human Development Index scores by state"
        ),
        "section_renames": {
            "framework": "Theoretical & Constitutional Framework",
            "core_content": "Social Structure, Dynamics & Key Indicators",
            "evolution": "Historical Transformation & Reform Movements",
            "significance": "Structural Challenges, Policy Gaps & Path Forward",
        },
    },

    "Indian & World Geography": {
        "tone": (
            "spatial, process-focused, resource-oriented — geography explains WHY "
            "things are distributed the way they are; always explain the physical process "
            "before describing the pattern"
        ),
        "emphasis": (
            "India-specific physical features (river systems, climate zones, soil types, "
            "mineral distribution), geophysical processes underlying patterns, "
            "human-environment interaction, economic geography of resources"
        ),
        "structure": (
            "define the phenomenon/feature → explain the underlying physical/chemical/biological "
            "process → describe distribution pattern in India (and globally where relevant) → "
            "regional variations and anomalies → human-economic significance → "
            "environmental and policy implications"
        ),
        "avoid": (
            "rote list of features without process explanation, treating geography as pure "
            "memorization, ignoring the human-geography interface, vague descriptions like "
            "'India has diverse geography'"
        ),
        "example_voice": (
            "The Western Ghats receive 2,000–5,000 mm of annual rainfall on their windward "
            "western slopes due to orographic lift of the southwest monsoon, while the rain "
            "shadow leeward districts of Karnataka and Maharashtra receive under 500 mm — "
            "making the same mountain range simultaneously a biodiversity hotspot and an "
            "agrarian drought zone."
        ),
        "key_sources": (
            "NCERT Geography Class 11 (Fundamentals of Physical Geography + India Physical "
            "Environment) and Class 12 (Fundamentals of Human Geography + India People and "
            "Economy), IMD (India Meteorological Department) data, GSI (Geological Survey of "
            "India), Census Atlas of India, FAO land-use data"
        ),
        "critical_vocab": (
            "orographic rainfall, leeward/windward, watershed, aquifer, isohyet, isotherm, "
            "continental shelf, exclusive economic zone (EEZ), alluvial/laterite/black soil, "
            "Hadley cell, ITCZ (Inter-Tropical Convergence Zone), tectonic plates, "
            "Gondwanaland, delta vs estuary, biome, endemic species"
        ),
        "comparison_pairs": (
            "Western Ghats vs Eastern Ghats | Himalayan rivers vs Peninsular rivers | "
            "Kharif vs Rabi crops | tropical vs temperate climate | "
            "monsoon vs Mediterranean rainfall pattern | black soil vs laterite soil"
        ),
        "data_types": (
            "river lengths and discharge volumes, peak heights (m), rainfall (mm/year), "
            "temperature ranges (°C), forest cover % (FSI data), mineral reserve quantities, "
            "coastline length (7,516 km), EEZ area (2.37 million sq km)"
        ),
        "section_renames": {
            "framework": "Classification & Scientific Framework",
            "core_content": "Distribution Patterns, Regional Variations & Controlling Factors",
            "evolution": "Geological Formation & Long-Term Change",
            "significance": "Human-Economic Significance & Environmental Implications",
        },
    },

    "Indian Polity & Constitution": {
        "tone": (
            "authoritative, legislatively precise, analytically critical — "
            "write like a constitutional lawyer who also understands political science; "
            "cite provisions and then interrogate them"
        ),
        "emphasis": (
            "exact Article numbers and their content, Schedule numbers and their purpose, "
            "landmark Supreme Court and High Court judgments with year and core holding, "
            "constitutional amendment numbers with year and effect, Constituent Assembly debates "
            "for intent, committee and commission recommendations"
        ),
        "structure": (
            "constitutional definition and textual basis → full legal framework → "
            "institutional composition, powers, and working → historical evolution and key amendments → "
            "structural debates, criticism, and reform proposals"
        ),
        "avoid": (
            "narrative storytelling that obscures legal precision, emotional language, "
            "vague institutional descriptions ('Parliament is very important'), treating "
            "constitutional provisions as settled when they are actively contested"
        ),
        "example_voice": (
            "Article 352 empowers the President to proclaim a National Emergency if satisfied "
            "that the security of India or any part thereof is threatened by war, external "
            "aggression, or 'armed rebellion' — the 44th Amendment (1978) deliberately replaced "
            "'internal disturbance' with this stricter standard to prevent Executive misuse "
            "as witnessed during 1975–77."
        ),
        "key_sources": (
            "M. Laxmikanth's Indian Polity (most recent edition), bare text of the Constitution "
            "of India, Supreme Court judgment database (IndianKanoon / SCI), "
            "Constituent Assembly Debates (CAD) archive, Sarkaria Commission 1988, "
            "Punchhi Commission 2010, Law Commission reports"
        ),
        "critical_vocab": (
            "federalism, quasi-federal, separation of powers, judicial review, basic structure "
            "doctrine, writ jurisdiction, ordinance power, money bill, constitutional amendment, "
            "colourable legislation, delegated legislation, parliamentary sovereignty, "
            "directive principles, fundamental duties, concurrent list"
        ),
        "comparison_pairs": (
            "Lok Sabha vs Rajya Sabha | Centre vs State legislative powers | "
            "Fundamental Rights vs DPSP | Ordinary Bill vs Money Bill vs Constitutional Amendment Bill | "
            "Judicial Review vs Judicial Activism | Original jurisdiction vs Appellate jurisdiction"
        ),
        "data_types": (
            "Article numbers, Schedule numbers (1-12), Amendment numbers and years, "
            "seats in Lok Sabha (543) and Rajya Sabha (245), quorum requirements, "
            "voting majority thresholds, tenure periods"
        ),
        "section_renames": {
            "framework": "Constitutional & Legal Framework",
            "core_content": "Composition, Powers & Functional Mechanics",
            "evolution": "Constitutional Evolution & Key Amendments",
            "significance": "Structural Debates, Judicial Interpretation & Reform Proposals",
        },
    },

    "Governance & Social Justice": {
        "tone": (
            "policy-implementation focused, reform-critical, evidence-driven — "
            "always interrogate the gap between legislative intent and ground reality"
        ),
        "emphasis": (
            "specific scheme names with year of launch and implementing ministry, "
            "DPSP provisions as policy mandates, RTI and transparency mechanisms, "
            "decentralization (73rd/74th Amendment framework), CAG audit findings, "
            "social audit processes, e-governance platforms"
        ),
        "structure": (
            "policy objective and constitutional/legal mandate → institutional delivery mechanism → "
            "data on reach and outcomes → identified gaps (CAG/committee findings) → "
            "reform proposals and current trajectory"
        ),
        "avoid": (
            "listing schemes without analyzing effectiveness, treating government press releases "
            "as objective assessment, ignoring federalism tensions in centrally sponsored schemes, "
            "vague recommendations like 'more awareness needed'"
        ),
        "example_voice": (
            "MGNREGS (2005), guaranteed 100 days of unskilled wage employment by law, "
            "reached 7.55 crore households in FY23 — yet CAG 2023 flagged ₹1.07 lakh crore "
            "in unspent funds and found 30% of job cards linked to inactive or deceased persons, "
            "exposing a structural disconnect between allocation and delivery."
        ),
        "key_sources": (
            "CAG performance audit reports, NITI Aayog SDG India Index, Economic Survey, "
            "2nd Administrative Reforms Commission (ARC) reports, Parliamentary Standing "
            "Committee reports, Ministry annual reports, PIB scheme data, "
            "World Bank Governance Indicators"
        ),
        "critical_vocab": (
            "decentralization, 73rd/74th Amendment, gram sabha, social audit, RTI Act 2005, "
            "whistleblower protection, e-governance, DBT (Direct Benefit Transfer), "
            "JAM trinity (Jan Dhan-Aadhaar-Mobile), Centrally Sponsored Scheme (CSS), "
            "devolution, concurrent jurisdiction, DPSP Article 36-51"
        ),
        "comparison_pairs": (
            "73rd vs 74th Amendment provisions | RTI vs Official Secrets Act 1923 | "
            "DPSP vs Fundamental Rights | Centre vs State governance responsibility | "
            "CSS vs Central Sector Scheme financing"
        ),
        "data_types": (
            "scheme budget allocations (₹ crore), beneficiary counts, CAG audit observations, "
            "India's rank in Ease of Doing Business / Governance indices, "
            "devolution % of taxes to states (Finance Commission awards), GFD targets"
        ),
        "section_renames": {
            "framework": "Constitutional Mandate & Policy Framework",
            "core_content": "Institutional Architecture & Implementation Machinery",
            "evolution": "Reform Trajectory & Key Policy Milestones",
            "significance": "Implementation Gaps, CAG Findings & Reform Agenda",
        },
    },

    "International Relations": {
        "tone": (
            "diplomatic-strategic, analytically balanced, India-centric — "
            "present India's formal positions accurately, then interrogate the strategic "
            "calculus behind them without editorializing"
        ),
        "emphasis": (
            "bilateral frameworks and treaty bases, multilateral forum positions and India's "
            "voting record, India's neighborhood policy specifics, strategic partnerships vs "
            "alliances distinction, historical context of current tensions"
        ),
        "structure": (
            "historical/structural foundation of the relationship or issue → India's current "
            "formal position and strategic doctrine → key bilateral/multilateral instruments → "
            "areas of cooperation vs friction → recent developments and trajectory"
        ),
        "avoid": (
            "one-sided geopolitical analysis, excessive detail on non-India bilateral relations, "
            "treating India's foreign policy as static, confusing bilateral and multilateral forums, "
            "ignoring domestic policy linkages (trade policy ↔ foreign policy)"
        ),
        "example_voice": (
            "India's abstention at the UNSC and UNGA on Russia-Ukraine resolutions reflects "
            "the 'strategic autonomy' doctrine — preserving the Russia relationship (S-400, "
            "energy, fertilizers) while not formally endorsing territorial aggression, a "
            "position that drew criticism from the US and EU but remained India's consistent stance."
        ),
        "key_sources": (
            "MEA (Ministry of External Affairs) annual reports and official statements, "
            "PIB press releases on bilateral summits, Joint communiqués and treaty texts, "
            "IDSA (Institute for Defence Studies and Analyses) working papers, "
            "IISS Military Balance, World Trade Organization India profile"
        ),
        "critical_vocab": (
            "strategic autonomy, Neighbourhood First policy, Act East policy, Look East policy, "
            "Panchamrit, non-alignment, multi-alignment, Vasudhaiva Kutumbakam, QUAD, SCO, BRICS, "
            "G20, SAARC, BIMSTEC, Line of Actual Control (LAC), Line of Control (LoC), "
            "maritime security, blue economy, soft power"
        ),
        "comparison_pairs": (
            "SAARC vs BIMSTEC (effectiveness) | bilateral vs multilateral diplomacy | "
            "India-China vs India-US strategic partnership | QUAD vs SCO membership | "
            "hard power vs soft power instruments"
        ),
        "data_types": (
            "bilateral trade volumes (USD billion), FDI inflows by country, defense import % from Russia/US, "
            "treaty signing years, summit declaration dates, UN Security Council vote records, "
            "India's contribution to UN peacekeeping (troops deployed)"
        ),
        "section_renames": {
            "framework": "Structural Foundations & Governing Doctrines",
            "core_content": "Key Instruments, Forums & Strategic Dimensions",
            "evolution": "Historical Trajectory & Policy Shifts",
            "significance": "Strategic Significance, Current Tensions & Future Trajectory",
        },
    },

    "Indian Economy": {
        "tone": (
            "analytical, data-aware, policy-critical — treat economic concepts as "
            "tools for analyzing India's specific developmental challenges; "
            "always anchor theory in Indian data and policy reality"
        ),
        "emphasis": (
            "India-specific data (GDP, inflation, FD, CAD, unemployment), Budget provisions "
            "with year and allocation, RBI monetary policy stance, sector-wise performance, "
            "scheme effectiveness data, structural weaknesses vs stated policy goals"
        ),
        "structure": (
            "economic concept and its formal definition → India's institutional/regulatory "
            "framework → key data trends (3-5 years) → sectoral or regional breakdown → "
            "policy challenges and structural constraints → recent reforms and current trajectory"
        ),
        "avoid": (
            "abstract theory without Indian application, outdated statistics (always use latest "
            "available), treating Budget announcements as achieved outcomes, "
            "confusing monetary and fiscal policy instruments"
        ),
        "example_voice": (
            "India's Gross Fiscal Deficit stood at 5.8% of GDP in FY24 against the FRBM target "
            "of 3% — the deviation, sustained since COVID, reflects deliberate counter-cyclical "
            "spending, though the RBI has flagged that elevated government borrowing competes "
            "with private investment, contributing to the 'crowding out' observed in FY22-23."
        ),
        "key_sources": (
            "Economic Survey (Finance Ministry, annual), Union Budget documents, "
            "RBI Annual Report and Monetary Policy Reports, MOSPI (National Statistical Office) data, "
            "NITI Aayog strategy papers, World Bank India Development Update, "
            "IMF World Economic Outlook India chapter"
        ),
        "critical_vocab": (
            "GDP, GVA, GNI, fiscal deficit, revenue deficit, primary deficit, FRBM Act, "
            "CPI, WPI, repo rate, reverse repo, CRR, SLR, monetary transmission, "
            "current account deficit (CAD), capital account, FDI vs FPI, GST, "
            "direct vs indirect tax, PMLA, NPA (non-performing assets), SARFAESI Act"
        ),
        "comparison_pairs": (
            "fiscal vs monetary policy | public vs private investment (crowding-in vs crowding-out) | "
            "direct vs indirect taxes | FDI vs FPI | demand-side vs supply-side economics | "
            "formal vs informal sector | Keynesian vs monetarist approach to Indian context"
        ),
        "data_types": (
            "GDP growth % (RBI/CSO estimates), inflation rates (CPI/WPI), fiscal deficit as % GDP, "
            "FDI inflows (USD billion by year), unemployment rate (PLFS data), "
            "export-import figures, forex reserves, credit growth %, HDI rank"
        ),
        "section_renames": {
            "framework": "Policy & Regulatory Framework",
            "core_content": "Sectoral Analysis, Key Indicators & Structural Dynamics",
            "evolution": "Policy Evolution & Reform Trajectory",
            "significance": "Structural Challenges, Reform Gaps & Future Outlook",
        },
    },

    # ── GS PAPER III ──────────────────────────────────────────────────────────

    "Science & Technology": {
        "tone": (
            "explanatory, current-affairs-anchored, application-focused — explain the "
            "science clearly but always pivot to India's strategic, developmental, or "
            "governance implications; avoid pure science-textbook mode"
        ),
        "emphasis": (
            "India's institutional ecosystem (ISRO, DRDO, CSIR, DST, DBT, DAE), "
            "recent Indian achievements with specific mission/project names and dates, "
            "dual-use technology dimensions (civilian and defence), policy and regulation "
            "(biosafety, data protection, nuclear liability), global technology governance"
        ),
        "structure": (
            "what the technology/concept is (plain language) → how it works (essential mechanism only) → "
            "India's current status, institutions, and key achievements → "
            "policy/regulatory framework governing it → "
            "strategic implications and recent global developments relevant to India"
        ),
        "avoid": (
            "overly technical jargon without explanation, ignoring India-specific context "
            "entirely, treating every technology as benign (note dual-use concerns), "
            "listing organizations without explaining what they actually do"
        ),
        "example_voice": (
            "Chandrayaan-3's Vikram lander achieved a soft landing at 69.37°S on 23 August 2023 — "
            "making India the fourth country to land on the Moon and the first to reach the "
            "south pole region, validating ISRO's cost-optimized mission architecture "
            "(₹615 crore, roughly the budget of a Hollywood film)."
        ),
        "key_sources": (
            "DST (Department of Science & Technology) Annual Report, ISRO mission documentation, "
            "DRDO technology node reports, PIB S&T releases, Technology Vision 2035 (TIFAC), "
            "India Innovation Index (NITI Aayog), Global Innovation Index (WIPO) India chapter"
        ),
        "critical_vocab": (
            "CRISPR-Cas9, quantum entanglement, 5G/6G, semiconductor fab, AI/ML, deep learning, "
            "mRNA vaccine platform, biosafety level (BSL), cybersecurity, encryption, "
            "dual-use technology, MTCR, Wassenaar Arrangement, space debris, LEO/MEO/GEO orbits, "
            "nuclear reactor types (PWR, PHWR, FBR), thorium fuel cycle"
        ),
        "comparison_pairs": (
            "ISRO vs ESA/NASA (cost efficiency) | nuclear vs renewable energy policy | "
            "indigenous vs imported defence technology | LEO vs GEO satellites | "
            "public R&D vs private sector innovation | AI regulation: India vs EU vs US"
        ),
        "data_types": (
            "mission dates and costs, patent filings (India rank globally), R&D spend as % GDP "
            "(India ~0.65% vs global avg ~1.8%), GERD (Gross Expenditure on R&D), "
            "broadband penetration %, semiconductor import value, space economy size"
        ),
        "section_renames": {
            "framework": "India's Institutional & Policy Framework",
            "core_content": "Technical Architecture, Applications & India's Status",
            "evolution": "Technological Evolution & Key Indian Milestones",
            "significance": "Strategic Implications, Regulatory Challenges & Future Directions",
        },
    },

    "Environment & Ecology": {
        "tone": (
            "scientifically precise, conservation-focused, development-critical — "
            "present the ecology accurately, then critically examine the tension between "
            "conservation mandates and developmental pressures"
        ),
        "emphasis": (
            "India's specific biodiversity assets (hotspots, endemic species counts, "
            "Ramsar sites, Tiger Reserves, Biosphere Reserves), climate commitments "
            "(NDCs, net-zero targets), pollution data (CPCB/WHO), international conventions "
            "India has ratified, legal framework (WPA 1972, FCA 1980, EPA 1986, FRA 2006)"
        ),
        "structure": (
            "ecological concept or threat definition → India-specific context with data → "
            "legal and institutional framework → international convention linkages → "
            "implementation reality and enforcement gaps → development vs conservation tension → "
            "current status and way forward"
        ),
        "avoid": (
            "vague 'save the environment' rhetoric without policy substance, ignoring the "
            "development vs conservation tension (tribal rights vs forest conservation), "
            "listing protected areas without explaining their legal differences, "
            "treating EIA as automatically effective"
        ),
        "example_voice": (
            "India's 18 Biosphere Reserves — of which 12 are recognized in UNESCO's World "
            "Network — differ from National Parks in a critical legal respect: human habitation "
            "and resource use are permitted in the transition and buffer zones, making them "
            "instruments of co-existence rather than exclusion."
        ),
        "key_sources": (
            "MoEFCC (Ministry of Environment, Forest and Climate Change) annual reports, "
            "Wildlife Protection Act 1972, Forest Conservation Act 1980 (and 2023 amendment), "
            "Forest Rights Act 2006, CPCB (Central Pollution Control Board) data, "
            "IPCC Assessment Reports (India chapter), CBD (Convention on Biological Diversity), "
            "India's NDC submitted to UNFCCC, FSI (Forest Survey of India) biennial reports"
        ),
        "critical_vocab": (
            "endemic species, IUCN Red List categories, Ramsar Convention, CITES, CBD, "
            "biosphere reserve zones (core/buffer/transition), EIA (Environmental Impact Assessment), "
            "CRZ (Coastal Regulation Zone), carbon sequestration, NDC, net zero, LiFE mission, "
            "PM2.5, AQI, bioaccumulation, biomagnification, eutrophication, coral bleaching"
        ),
        "comparison_pairs": (
            "Wildlife Sanctuary vs National Park vs Biosphere Reserve (legal differences) | "
            "Paris Agreement vs Kyoto Protocol obligations | CITES vs CBD scope | "
            "Forest Conservation Act 1980 vs Forest Rights Act 2006 | "
            "mitigation vs adaptation strategies"
        ),
        "data_types": (
            "forest cover % (FSI 2021: 21.71%), tiger population (NTCA census), "
            "number of Ramsar sites (75 as of 2023), PM2.5 levels (CPCB city data), "
            "India's per capita emissions vs global average, renewable energy installed capacity (GW)"
        ),
        "section_renames": {
            "framework": "Legal Framework & International Conventions",
            "core_content": "Ecological Profile, Threats & Conservation Architecture",
            "evolution": "Policy Evolution & Key Legislative Milestones",
            "significance": "Development vs Conservation Tension & India's Climate Commitments",
        },
    },

    "Internal Security": {
        "tone": (
            "factual, neutral, legally precise, threat-analytical — "
            "describe threats and responses using legal and institutional language; "
            "avoid sensationalism; distinguish between operational and structural responses"
        ),
        "emphasis": (
            "exact legal provisions (UAPA, AFSPA, NIA Act, NDPS Act), institutional mandates "
            "(NIA, IB, RAW, NSG, CRPF, Border guarding forces), threat classification and "
            "geography, Left Wing Extremism data, border management framework, cyber threats"
        ),
        "structure": (
            "threat type definition and classification → geographic/operational profile in India → "
            "legal framework governing response → institutional machinery → "
            "inter-agency coordination mechanisms → challenges and structural weaknesses → "
            "recent developments"
        ),
        "avoid": (
            "sensationalism or inflammatory language about any group, politically charged "
            "characterization of conflicts, specific operational details that could assist bad "
            "actors, conflating terrorism with communalism without legal precision"
        ),
        "example_voice": (
            "The UAPA (Amendment) Act 2019 empowered the Government to designate individuals "
            "— not just organizations — as terrorists, a provision upheld by the Supreme Court "
            "in Sajal Awasthi v. Union of India (2023) despite civil liberties concerns about "
            "procedural safeguards for de-designation."
        ),
        "key_sources": (
            "MHA (Ministry of Home Affairs) Annual Report, NCRB Crime in India report, "
            "Parliamentary Standing Committee on Home Affairs reports, "
            "UAPA bare text, AFSPA bare text, NIA Act 2008, "
            "Institute for Conflict Management (South Asia Terrorism Portal data)"
        ),
        "critical_vocab": (
            "UAPA, AFSPA, NIA, NSA (National Security Act), FICN (Fake Indian Currency Notes), "
            "hybrid warfare, radicalization, insurgency, Left Wing Extremism (LWE), "
            "cyber terrorism, critical information infrastructure (CII), "
            "ISI (Pakistan), cross-border infiltration, LoC, LAC, IED, HUMINT, SIGINT"
        ),
        "comparison_pairs": (
            "IB vs RAW (domestic vs external intelligence) | CRPF vs BSF vs ITBP vs SSB "
            "(border and internal roles) | UAPA vs NSA vs AFSPA (scope and safeguards) | "
            "insurgency vs terrorism (legal and operational distinction) | "
            "LWE-affected districts pre vs post 2019 (reduction trend)"
        ),
        "data_types": (
            "LWE-affected district count (MHA data: reduced from 90 to 45 by 2023), "
            "terrorist incident statistics (SATP/NCRB), cyber crime cases (NCRB IT crime data), "
            "FICN seizure volumes, border infiltration attempt numbers, "
            "NDPS Act drug seizure data"
        ),
        "section_renames": {
            "framework": "Legal Mandate & Statutory Framework",
            "core_content": "Threat Profile, Institutional Architecture & Response Mechanisms",
            "evolution": "Threat Evolution & Policy Response Timeline",
            "significance": "Structural Challenges, Coordination Gaps & Reform Imperatives",
        },
    },

    "Disaster Management": {
        "tone": (
            "procedural, preparedness-focused, institutionally precise — "
            "treat disaster management as a governance and institutional challenge; "
            "always link to the DM Act 2005 framework and Sendai Framework obligations"
        ),
        "emphasis": (
            "DM Act 2005 three-tier hierarchy (NDMA-SDMA-DDMA), NDRF deployment protocols, "
            "Sendai Framework 2015-2030 four priorities, India's disaster risk profile "
            "(hazard-specific vulnerability data), early warning systems, "
            "community-based DRR, climate change × disaster risk nexus"
        ),
        "structure": (
            "disaster type definition and classification → India's vulnerability profile with data → "
            "DM Act 2005 legal framework → institutional hierarchy and mandates → "
            "pre-disaster preparedness → response protocol → recovery and reconstruction → "
            "Sendai Framework alignment and gaps"
        ),
        "avoid": (
            "vague 'raise awareness' prescriptions, ignoring the vulnerability and resilience "
            "framework, treating disaster response as purely a military/NDRF function "
            "(community resilience is central), omitting climate change as a risk multiplier"
        ),
        "example_voice": (
            "The National Disaster Management Act 2005 (DM Act) established NDMA under the "
            "Chairmanship of the Prime Minister — a deliberate elevation above the existing "
            "Crisis Management Group under the Cabinet Secretary — signalling that disaster "
            "management is a national security-level governance function, not a welfare measure."
        ),
        "key_sources": (
            "Disaster Management Act 2005 (bare text), NDMA National Guidelines (hazard-specific), "
            "Sendai Framework for DRR 2015-2030 (UNDRR), National Policy on Disaster Management 2009, "
            "NDRF Operations Manual, BIS codes for earthquake-resistant construction, "
            "EM-DAT (Emergency Events Database) India disaster statistics"
        ),
        "critical_vocab": (
            "DM Act 2005, NDMA, SDMA, DDMA, NDRF, SDRF, Sendai Framework, CBDRR "
            "(Community-Based Disaster Risk Reduction), EWS (Early Warning System), "
            "hazard, vulnerability, exposure, resilience, DRR (Disaster Risk Reduction), "
            "mitigation, preparedness, response, recovery — the four-phase cycle, "
            "seismic zone (I–V), IMD cyclone naming, APDM, IDRN"
        ),
        "comparison_pairs": (
            "NDRF vs SDRF (funding and deployment rules) | mitigation vs preparedness vs response | "
            "natural vs man-made (CBRN) disasters | "
            "Sendai Framework vs Hyogo Framework (2005-2015) priorities | "
            "community-based vs institution-led DRR approaches"
        ),
        "data_types": (
            "NDRF battalion count and deployment locations, disaster mortality statistics "
            "(EM-DAT India data), economic loss figures from major disasters, "
            "seismic zone classification of Indian cities, cyclone frequency data (IMD), "
            "flood-prone area (40 million hectares), SDRF allocation by Finance Commission"
        ),
        "section_renames": {
            "framework": "DM Act 2005 & Sendai Framework Architecture",
            "core_content": "Institutional Hierarchy, Roles & Response Protocols",
            "evolution": "Policy Evolution: Pre-DM Act to Sendai Alignment",
            "significance": "Vulnerability Profile, Climate Risk Nexus & Systemic Gaps",
        },
    },

    # ── GS PAPER IV ───────────────────────────────────────────────────────────

    "Ethics, Integrity & Aptitude": {
        "tone": (
            "reflective, philosophical, normatively engaged, case-study grounded — "
            "ethics is not purely descriptive; take reasoned positions; "
            "always bridge abstract moral philosophy to civil service practice"
        ),
        "emphasis": (
            "major ethical frameworks (consequentialism, deontology, virtue ethics) with "
            "their Indian counterparts (Gandhian ethics, Nishkama Karma, Dharma), "
            "thinker positions with dates, ethical dilemmas in public administration, "
            "ARC and Santhanam Committee recommendations on probity, emotional intelligence"
        ),
        "structure": (
            "concept definition and its core philosophical tension → major theoretical frameworks "
            "and thinkers (Western and Indian) → public administration application → "
            "case study or dilemma analysis → institutional mechanisms for ethical governance → "
            "current reform directions"
        ),
        "avoid": (
            "purely factual recitation without normative engagement, legalistic tone that reduces "
            "ethics to rule compliance, simplistic moralizing, treating all ethical frameworks as "
            "equally valid without critical comparison, ignoring Indian philosophical traditions"
        ),
        "example_voice": (
            "A civil servant ordered to implement a policy she believes will harm vulnerable "
            "communities faces the deontological duty to follow lawful orders against the "
            "consequentialist imperative to prevent harm — Gandhian ethics would counsel "
            "satyagraha through legitimate institutional channels rather than passive compliance "
            "or reckless insubordination."
        ),
        "key_sources": (
            "2nd Administrative Reforms Commission (ARC) Reports (especially Report 4: Ethics in "
            "Governance), Santhanam Committee on Prevention of Corruption, "
            "Nolan Committee Seven Principles of Public Life (UK — cited in UPSC syllabus), "
            "IAS (Conduct) Rules 1964, Lokpal and Lokayuktas Act 2013, "
            "RTI Act 2005 as transparency mechanism"
        ),
        "critical_vocab": (
            "consequentialism, deontology, virtue ethics, Kantian categorical imperative, "
            "utilitarianism (Bentham vs Mill), Gandhian Sarvodaya, Nishkama Karma, "
            "emotional intelligence (EI), moral courage, probity, integrity, "
            "conflict of interest, double effect, whistleblower, civil service neutrality, "
            "compassion, tolerance, universal human values"
        ),
        "comparison_pairs": (
            "consequentialist vs deontological approach to a public policy dilemma | "
            "Gandhi vs Kautilya on statecraft ethics | public ethics vs private ethics | "
            "rules-based vs principle-based ethical governance | "
            "Nolan principles vs Indian service conduct rules"
        ),
        "data_types": (
            "Transparency International CPI rank (India), RTI applications filed annually, "
            "Lokpal cases registered, conviction rates under Prevention of Corruption Act, "
            "survey data on public trust in civil services, whistle-blower complaint counts"
        ),
        "section_renames": {
            "framework": "Theoretical & Philosophical Framework",
            "core_content": "Conceptual Dimensions, Thinkers & Applied Analysis",
            "evolution": "Historical Development of the Concept & Institutional Response",
            "significance": "Public Administration Implications & Reform Imperatives",
        },
    },
}


# ── MAIN GENERATION FUNCTION ──────────────────────────────────────────────────


def generate_quality_article(
    subtopic: str,
    parent_topic: str,
    ncert_section: str,
    wiki_content: str,
    previously_covered: str = "",
    subject: str = "",
) -> tuple[str, float]:
    """
    LAYER 2 MAIN FUNCTION.
    Generates a high-quality article using section-by-section approach
    with self-critique pass, then formatting pass.

    Returns:
        (article_markdown: str, quality_score: float)
    """
    logger.info("quality_engine_start", subtopic=subtopic, subject=subject)

    # Step 1: Generate section by section
    sections = _generate_sections(
        subtopic, parent_topic, ncert_section, wiki_content, previously_covered, subject
    )
    article_draft = _assemble_article(subtopic, sections)

    # Step 2: Self-critique pass
    logger.info("quality_engine_critique_start", subtopic=subtopic)
    critique_result = _run_critique(subtopic, article_draft)
    quality_score = critique_result.get("score", 0.0)

    # Step 3: If quality < 65, run targeted refinement on weak sections
    if quality_score < 65.0:
        logger.info(
            "quality_engine_refinement_start",
            subtopic=subtopic,
            score=quality_score,
        )
        article_draft = _refine_weak_sections(
            subtopic,
            article_draft,
            critique_result.get("weak_sections", []),
            ncert_section,
            wiki_content,
        )
        # Re-score after refinement
        critique_result = _run_critique(subtopic, article_draft)
        quality_score = critique_result.get("score", 0.0)

    # Step 4: Phase 4.5B — Formatting pass (tables, callouts, infographic markers)
    article_draft = _run_formatting_pass(subtopic, article_draft)

    logger.info(
        "quality_engine_done",
        subtopic=subtopic,
        quality_score=quality_score,
        word_count=len(article_draft.split()),
    )

    return article_draft, quality_score


# ── SECTION-BY-SECTION GENERATOR ─────────────────────────────────────────────


def _generate_sections(
    subtopic: str,
    parent_topic: str,
    ncert_section: str,
    wiki_content: str,
    previously_covered: str,
    subject: str = "",
) -> dict:
    """
    Generates each section independently for deeper content.
    The LLM chooses its own ### heading per section (dynamic headings).
    used_headings is passed to every subsequent section to prevent duplication.
    """
    sections = {}
    article_so_far = ""
    used_headings: list[str] = []

    for section_def in SECTION_PLAN:
        section_id = section_def["id"]
        heading_directive = section_def["heading_directive"].format(subtopic=subtopic)
        instruction = section_def["instruction"].format(subtopic=subtopic)

        prompt = _build_section_prompt(
            subtopic=subtopic,
            parent_topic=parent_topic,
            ncert_section=ncert_section,
            wiki_content=wiki_content,
            previously_covered=previously_covered,
            heading_directive=heading_directive,
            section_instruction=instruction,
            article_so_far=article_so_far,
            used_headings=used_headings,
            subject=subject,
        )

        section_content = llm_call(prompt, mode="writer")

        if section_content and len(section_content.strip()) > 50:
            content = section_content.strip()

            # Extract the ### heading the LLM chose and track it
            heading_match = re.match(r"^###\s+(.+)", content)
            if heading_match:
                used_headings.append(heading_match.group(1).strip())
            else:
                # LLM skipped the ### — prepend a safe fallback and track it
                fallback_heading = f"{subtopic} — {section_id.replace('_', ' ').title()}"
                content = f"### {fallback_heading}\n\n{content}"
                used_headings.append(fallback_heading)
                logger.warning(
                    "quality_engine_heading_missing",
                    section_id=section_id,
                    subtopic=subtopic,
                    fallback=fallback_heading,
                )

            sections[section_id] = content
            article_so_far += f"\n\n{content}"
        else:
            fallback_heading = f"{subtopic} — {section_id.replace('_', ' ').title()}"
            logger.warning(
                "quality_engine_section_failed",
                section_id=section_id,
                subtopic=subtopic,
            )
            sections[section_id] = f"### {fallback_heading}\n\n*Content pending.*"
            used_headings.append(fallback_heading)

    return sections


def _build_section_prompt(
    subtopic: str,
    parent_topic: str,
    ncert_section: str,
    wiki_content: str,
    previously_covered: str,
    heading_directive: str,
    section_instruction: str,
    article_so_far: str,
    used_headings: list[str],
    subject: str = "",
) -> str:
    """
    Builds the full prompt for one section.
    The LLM picks its own ### heading guided by heading_directive.
    used_headings enforces no duplication across sections.
    """

    # ── Source material ───────────────────────────────────────────────────────
    sources_block = ""
    if ncert_section and ncert_section.strip():
        sources_block += f"""
PRIMARY SOURCE — NCERT (use as your factual spine):
{ncert_section[:3000]}
"""
    if wiki_content and wiki_content.strip():
        sources_block += f"""
ENRICHMENT SOURCE — Wikipedia (depth, history, recent developments):
{wiki_content[:3000]}
"""
    if not sources_block:
        sources_block = "(No source material available — draw on expert knowledge.)"

    # ── Prior context ─────────────────────────────────────────────────────────
    context_block = f"\n{previously_covered}\n" if previously_covered else ""

    continuity_block = ""
    if article_so_far.strip():
        continuity_block = f"""
ARTICLE SO FAR (maintain continuity — do NOT repeat any of this):
...{article_so_far[-600:]}
"""

    # ── Anti-duplication fence ────────────────────────────────────────────────
    if used_headings:
        forbidden_list = "\n".join(f"  ✗ {h}" for h in used_headings)
        duplicate_fence = f"""
HEADINGS ALREADY USED — your new heading MUST NOT repeat or closely echo any of these:
{forbidden_list}
"""
    else:
        duplicate_fence = ""

    # ── Subject persona ───────────────────────────────────────────────────────
    subject_persona_block = ""
    if subject and subject in SUBJECT_PROFILES:
        profile = SUBJECT_PROFILES[subject]
        lines = [
            f"\nSUBJECT PERSONA — {subject}:",
            f"  Tone:            {profile['tone']}",
            f"  Emphasis:        {profile['emphasis']}",
            f"  Narrative arc:   {profile['structure']}",
            f"  Avoid:           {profile['avoid']}",
            f'  Voice example:   "{profile["example_voice"]}"',
        ]
        if profile.get("key_sources"):
            lines.append(f"  Authoritative sources to cite: {profile['key_sources']}")
        if profile.get("critical_vocab"):
            lines.append(f"  Domain vocabulary to use:      {profile['critical_vocab']}")
        if profile.get("comparison_pairs"):
            lines.append(f"  Comparison pairs (use where relevant): {profile['comparison_pairs']}")
        if profile.get("data_types"):
            lines.append(f"  Data to weave in when available:       {profile['data_types']}")
        subject_persona_block = "\n".join(lines) + "\n"

    return f"""You are a senior author writing "{subtopic}" — one chapter in a
comprehensive UPSC study book on "{parent_topic}".

{MASTER_STYLE_ANCHOR}
{subject_persona_block}
{sources_block}
{context_block}
{continuity_block}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR TASK — Write ONE section now. Follow ALL rules below exactly.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 1 — CHOOSE YOUR HEADING
{heading_directive}
{duplicate_fence}
OUTPUT FORMAT FOR HEADING: Start your response with exactly:
### [Your chosen heading here]
(one blank line, then the section content)

STEP 2 — WRITE THE SECTION
{section_instruction}

HARD RULES:
  • Begin your output with "### " followed immediately by your chosen heading.
  • Do NOT write a preamble like "Here is the section..." or "Sure, here's..."
  • Do NOT write any other section — only this one.
  • Do NOT repeat content already present in the article so far.
  • The heading you choose becomes the permanent heading — choose carefully."""


def _assemble_article(subtopic: str, sections: dict) -> str:
    """Assembles all sections into the final article."""
    header = f"## {subtopic}\n"
    body = "\n\n".join(sections.values())
    return f"{header}\n{body}"


# ── SELF-CRITIQUE PASS ────────────────────────────────────────────────────────


def _run_critique(subtopic: str, article: str) -> dict:
    """
    Runs a self-critique on the generated article.
    Returns critique dict with score and weak sections.
    """
    prompt = f"""You are a strict UPSC content quality reviewer.
Review this article on "{subtopic}" and score it.

ARTICLE TO REVIEW:
{article[:4000]}

Rate on these criteria (0-20 each, total 100):
1. SPECIFICITY: Are Articles, Acts, case names, years all cited precisely?
2. DEPTH: Does it go beyond surface-level explanation?
3. UPSC RELEVANCE: Is exam angle clearly addressed?
4. NO VAGUENESS: Zero hedging phrases, zero filler sentences?
5. ACCURACY: Is constitutional information factually correct?

Return ONLY valid JSON:
{{
  "scores": {{
    "specificity": 0-20,
    "depth": 0-20,
    "upsc_relevance": 0-20,
    "no_vagueness": 0-20,
    "accuracy": 0-20
  }},
  "total_score": 0-100,
  "weak_sections": ["section heading that needs improvement"],
  "specific_gaps": ["specific missing fact or concept"],
  "verdict": "one sentence summary"
}}"""

    response = llm_call(prompt, mode="standard")
    result = _parse_critique_json(response)
    return result


def _refine_weak_sections(
    subtopic: str,
    article: str,
    weak_sections: list,
    ncert_section: str,
    wiki_content: str,
) -> str:
    """Rewrites identified weak sections with targeted prompts."""
    if not weak_sections:
        return article

    for section_heading in weak_sections[:2]:  # Max 2 refinements to save API calls
        prompt = f"""This section of a UPSC article on "{subtopic}" is weak.
Rewrite it to be more specific, precise, and exam-relevant.

{MASTER_STYLE_ANCHOR}

SECTION TO IMPROVE:
{section_heading}

SOURCE MATERIAL:
NCERT: {ncert_section[:2000] if ncert_section else "Not available"}
Wikipedia: {wiki_content[:2000] if wiki_content else "Not available"}

Rewrite ONLY this section. Begin directly with improved content:"""

        improved = llm_call(prompt, mode="writer")
        if improved and len(improved.strip()) > 100:
            # Replace the weak section in the article
            if section_heading in article:
                # Find and replace just this section
                idx = article.find(section_heading)
                next_heading_idx = article.find("\n###", idx + 1)
                if next_heading_idx == -1:
                    next_heading_idx = len(article)
                article = (
                    article[:idx]
                    + section_heading
                    + "\n\n"
                    + improved.strip()
                    + "\n\n"
                    + article[next_heading_idx:]
                )

    return article


# ── PHASE 4.5B: FORMATTING PASS ───────────────────────────────────────────────


def _run_formatting_pass(subtopic: str, article_md: str) -> str:
    """
    Phase 4.5B: Post-critique formatting pass.
    Runs SECTION BY SECTION — mirrors the SECTION_PLAN loop in _generate_sections()
    to keep each LLM call within API payload limits.

    Per-section calls (Criteria 2 & 3):
      Each call receives only that one section (capped at 2500 chars).
      CRITERION 2 — Comparison Potential: inline comparison table if ≥2 entities compared.
      CRITERION 3 — Logical Grouping: inline classification table if content groups cleanly.
      Infographic placeholders and UPSC callout boxes also injected per section.

    Final single call (Criterion 1):
      CRITERION 1 — Factual Density: generates ONLY the summary table from the
      first 4000 chars of the assembled article, then appends it ourselves.
      This mirrors _run_critique()'s article[:4000] cap.

    IF NO CRITERIA MET → section returned unchanged. No tables added.
    DATA SAFETY: Every table cell must trace to a sentence in the source section.
    """
    # Split article into header (## line) + individual ### sections
    parts = re.split(r"(?=\n### )", article_md)
    header = parts[0]
    section_parts = parts[1:]

    if not section_parts:
        # No ### sections found — fall back gracefully, skip formatting
        logger.info(
            "formatting_pass_skipped", subtopic=subtopic, reason="no_sections_found"
        )
        return article_md

    # ── Pass 1: per-section (Criteria 2 & 3 + infographics + callouts) ──────
    enhanced_sections = []
    for section_text in section_parts:
        enhanced = _format_single_section(subtopic, section_text.strip())
        enhanced_sections.append(enhanced)

    assembled = header + "\n" + "\n\n".join(enhanced_sections)

    # ── Pass 2: summary table (Criterion 1) — capped single call ────────────
    assembled = _add_summary_table(subtopic, assembled)

    if assembled and len(assembled.strip()) > len(article_md) * 0.5:
        logger.info("formatting_pass_done", subtopic=subtopic, enhanced=True)
        return assembled.strip()

    logger.info("formatting_pass_skipped", subtopic=subtopic, reason="output_too_short")
    return article_md


def _format_single_section(subtopic: str, section_text: str) -> str:
    """
    Checks a single ### section for Criterion 2 (comparison tables),
    Criterion 3 (classification tables), infographic placeholders, and
    UPSC callout boxes. Each call is bounded to section_text[:2500] —
    same bounding philosophy as ncert[:3000] / wiki[:3000] in _build_section_prompt().
    Returns the enhanced section, or original if no criteria met.
    """
    prompt = f"""You are a UPSC study material formatter.
Analyze the single section below from an article on "{subtopic}" and enhance it WHERE JUSTIFIED.

SECTION:
{section_text[:2500]}

EVALUATE THESE 2 CRITERIA FOR THIS SECTION ONLY:

CRITERION 2 — Comparison Potential:
  Does this section discuss ≥2 distinct entities on the same attributes
  (e.g., Lok Sabha vs Rajya Sabha, Fundamental Rights vs DPSP)?
  → If YES: Add a comparison table INLINE after both entities are discussed.
  Format:
  ### ⚖️ Comparative Analysis: [Entity A] vs [Entity B]
  | Feature | [Entity A] | [Entity B] |
  |---------|-----------|-----------|
  (Fill ONLY with facts present in the section above — no hallucination)

CRITERION 3 — Logical Grouping:
  Can this section's content be better presented as a classification table
  (e.g., types of emergencies, categories of bills, types of amendments)?
  → If YES: Add a categorization table INLINE within this section.
  Format:
  ### 📋 Classification: [Category Name]
  | Category | Description |
  |----------|-------------|
  (Fill ONLY with facts present in the section above — no hallucination)

ALSO — detect Visual Moments in this section and inject infographic placeholders:
  Use this syntax inline where a diagram/map/timeline would genuinely help:
  >[!infographic: "Description of what the image should show"]<

ALSO — inject UPSC callout boxes for critical exam-facing facts:
  > **💡 UPSC High-Yield Focus:** [Critical exam takeaway in 1-2 sentences]

RULES:
  - If NEITHER criterion is met → return the section UNCHANGED.
  - Do NOT add tables for the sake of adding them.
  - Every table cell must trace to a sentence in the section above.
  - Do NOT add any new facts, names, or data not present in the section.

Return the complete enhanced section (or unchanged section if no criteria met):"""

    result = llm_call(prompt, mode="writer")
    if result and len(result.strip()) > len(section_text) * 0.4:
        return result.strip()
    return section_text


def _add_summary_table(subtopic: str, article_md: str) -> str:
    """
    Criterion 1: Factual Density check.
    Asks the LLM to generate ONLY the summary table (or reply NO_TABLE).
    Uses article[:4000] as input — same cap as _run_critique().
    The table is appended to the full article by this function, not by the LLM,
    so the LLM never needs to echo back a large payload.
    """
    prompt = f"""You are a UPSC study material formatter.
Analyze the article excerpt below on "{subtopic}".

ARTICLE EXCERPT:
{article_md[:4000]}

TASK — Criterion 1: Does this article contain ≥5 dates, names, or specific powers/provisions?

→ If YES: Generate ONLY the summary revision table (nothing else, no preamble):
### 📊 Quick Revision: {subtopic}
| Aspect | Detail |
|--------|--------|
(8–12 rows of key facts ONLY from the excerpt above — no hallucination, no new data)

→ If NO: Reply with exactly the word: NO_TABLE

Rules: Every row must trace to a fact in the excerpt. Zero hallucination."""

    result = llm_call(prompt, mode="standard")

    if result and result.strip() and result.strip() != "NO_TABLE" and "|" in result:
        return article_md.rstrip() + "\n\n" + result.strip()

    return article_md


# ── JSON PARSER ───────────────────────────────────────────────────────────────


def _parse_critique_json(text: str) -> dict:
    """Parses critique JSON from LLM response."""
    for attempt in [
        text,
        text[text.find("{") : text.rfind("}") + 1] if "{" in text else "",
    ]:
        try:
            result = json.loads(attempt)
            if isinstance(result, dict):
                # Normalize score
                score = result.get("total_score", 0)
                if not score and "scores" in result:
                    score = sum(result["scores"].values())
                result["score"] = float(score)
                return result
        except Exception:
            pass
    return {"score": 60.0, "weak_sections": [], "specific_gaps": []}
