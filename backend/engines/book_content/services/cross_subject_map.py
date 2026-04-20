"""
engines/book_content/services/cross_subject_map.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The Complete UPSC Cross-Subject Topic Registry.

Every entry defines:
  - primary_subject: WHERE the topic primarily lives in the hierarchy
  - module:          The specific module within that subject
  - secondary_subjects: Other subjects this topic SPANS (for Phase 11 cross-linking)
  - aliases:         Alternative names/search terms for this topic

WHY THIS EXISTS:
  UPSC topics don't fit neatly into one box.
  "Budget" is Economy + Polity + Governance.
  "Climate Change" is Environment + Geography + Economy + IR.
  This map tells the classifier exactly where to place them
  WITHOUT an LLM call (faster, more reliable, zero hallucination).

  Phase 11 will use secondary_subjects to create
  'related_to' edges across subject boundaries in the graph.
Ported from: upsc-agent-lab/src/cross_subject_map.py
Changes: logging (structlog), imports.
Preserved exactly: SUBJECTS dict, CROSS_SUBJECT_MAP dict, all lookup helpers.
"""

import structlog

logger = structlog.get_logger(__name__)

# ── UPSC Subject Registry (canonical names — must match classifier.py) ─────────
SUBJECTS = {
    "POLITY": "Indian Polity & Constitution",
    "HISTORY": "Indian History & Culture",
    "GEOGRAPHY": "Geography of India & World",
    "ECONOMY": "Indian Economy & Agriculture",
    "ENVIRONMENT": "Environment & Ecology",
    "SCIENCE": "Science & Technology",
    "IR": "International Relations",
    "GOVERNANCE": "Governance & Social Justice",
    "SECURITY": "Internal Security & Disaster Management",
}
P = SUBJECTS  # shorthand for use below


# ══════════════════════════════════════════════════════════════════════════════
# THE MASTER REGISTRY
# Format: "Canonical Topic Name": { ...details }
# ══════════════════════════════════════════════════════════════════════════════

CROSS_SUBJECT_MAP = {
    # ── POLITY CORE ──────────────────────────────────────────────────────────
    "Parliament of India": {
        "primary_subject": P["POLITY"],
        "module": "Union Legislature",
        "secondary_subjects": [P["GOVERNANCE"]],
        "aliases": ["Parliament", "Indian Parliament", "Lok Sabha and Rajya Sabha"],
    },
    "President of India": {
        "primary_subject": P["POLITY"],
        "module": "Union Executive",
        "secondary_subjects": [P["GOVERNANCE"]],
        "aliases": ["President", "Rashtrapati"],
    },
    "Prime Minister of India": {
        "primary_subject": P["POLITY"],
        "module": "Union Executive",
        "secondary_subjects": [P["GOVERNANCE"]],
        "aliases": ["Prime Minister", "PM of India", "Council of Ministers"],
    },
    "Cabinet Committees": {
        "primary_subject": P["POLITY"],
        "module": "Union Executive",
        "secondary_subjects": [P["GOVERNANCE"]],
        "aliases": ["Cabinet", "Union Cabinet", "Cabinet System India"],
    },
    "Fundamental Rights": {
        "primary_subject": P["POLITY"],
        "module": "Constitutional Framework",
        "secondary_subjects": [P["GOVERNANCE"], P["HISTORY"]],
        "aliases": ["Part III Constitution", "Fundamental Rights India"],
    },
    "Directive Principles of State Policy": {
        "primary_subject": P["POLITY"],
        "module": "Constitutional Framework",
        "secondary_subjects": [P["GOVERNANCE"], P["ECONOMY"]],
        "aliases": ["DPSP", "Directive Principles", "Part IV Constitution"],
    },
    "Preamble of Indian Constitution": {
        "primary_subject": P["POLITY"],
        "module": "Constitutional Framework",
        "secondary_subjects": [P["HISTORY"]],
        "aliases": ["Preamble", "Preamble India"],
    },
    "Judicial Review & Judicial Activism": {
        "primary_subject": P["POLITY"],
        "module": "Judiciary",
        "secondary_subjects": [P["GOVERNANCE"], P["GOVERNANCE"]],
        "aliases": [
            "Judicial Review",
            "Judicial Activism",
            "Supreme Court India",
            "PIL",
            "Public Interest Litigation",
        ],
    },
    "Election Process & Electoral Reforms": {
        "primary_subject": P["POLITY"],
        "module": "Electoral System",
        "secondary_subjects": [P["GOVERNANCE"]],
        "aliases": [
            "Electoral Reforms",
            "FPTP",
            "Election Commission India",
            "EVM",
            "Electoral Bonds",
        ],
    },
    "Federalism & Centre-State Relations": {
        "primary_subject": P["POLITY"],
        "module": "Federal Structure",
        "secondary_subjects": [P["GOVERNANCE"], P["ECONOMY"]],
        "aliases": [
            "Federalism India",
            "Centre-State Relations",
            "7th Schedule",
            "Union-State Relations",
        ],
    },
    "Federalism & Local Governance": {
        "primary_subject": P["POLITY"],
        "module": "Federal Structure",
        "secondary_subjects": [P["GOVERNANCE"], P["ECONOMY"]],
        "aliases": [
            "Local Self Government",
            "Panchayati Raj",
            "73rd Amendment",
            "74th Amendment",
            "ULBs",
        ],
    },
    "Social Justice (SC/ST/OBC)": {
        "primary_subject": P["GOVERNANCE"],
        "module": "Social Justice",
        "secondary_subjects": [P["POLITY"], P["HISTORY"]],
        "aliases": [
            "Reservation Policy",
            "Scheduled Castes",
            "Scheduled Tribes",
            "OBC Reservation",
            "Affirmative Action India",
        ],
    },
    "Women Empowerment": {
        "primary_subject": P["GOVERNANCE"],
        "module": "Social Justice",
        "secondary_subjects": [P["POLITY"], P["ECONOMY"]],
        "aliases": [
            "Gender Equality India",
            "Women Rights India",
            "Women Reservation Bill",
            "SHGs",
        ],
    },
    "NGOs & Civil Society": {
        "primary_subject": P["GOVERNANCE"],
        "module": "Civil Society & Democracy",
        "secondary_subjects": [P["POLITY"]],
        "aliases": ["Civil Society India", "FCRA", "NGO Regulation India"],
    },
    # ── ECONOMY CORE ─────────────────────────────────────────────────────────
    "Budget & Fiscal Policy": {
        "primary_subject": P["ECONOMY"],
        "module": "Fiscal Policy",
        "secondary_subjects": [P["POLITY"], P["GOVERNANCE"]],
        "aliases": [
            "Union Budget",
            "Fiscal Policy India",
            "Budget Session",
            "Fiscal Deficit",
            "FRBM Act",
            "Finance Bill",
        ],
    },
    "Economic Development & Growth": {
        "primary_subject": P["ECONOMY"],
        "module": "Macroeconomics",
        "secondary_subjects": [P["IR"], P["GOVERNANCE"]],
        "aliases": [
            "GDP India",
            "Economic Growth",
            "Inflation India",
            "Monetary Policy",
            "RBI",
            "Indian Economy",
        ],
    },
    "Poverty & Inequality": {
        "primary_subject": P["ECONOMY"],
        "module": "Development Economics",
        "secondary_subjects": [P["GOVERNANCE"], P["GEOGRAPHY"]],
        "aliases": [
            "Poverty India",
            "Income Inequality",
            "HDI India",
            "Multidimensional Poverty Index",
            "BPL",
        ],
    },
    "Agricultural Reforms": {
        "primary_subject": P["ECONOMY"],
        "module": "Agricultural Economy",
        "secondary_subjects": [P["GEOGRAPHY"], P["GOVERNANCE"], P["ENVIRONMENT"]],
        "aliases": [
            "Farm Laws India",
            "Agrarian Reforms",
            "Land Reforms",
            "Green Revolution",
            "MSP",
            "Agricultural Policy India",
        ],
    },
    "Food Security": {
        "primary_subject": P["ECONOMY"],
        "module": "Food & Nutrition Security",
        "secondary_subjects": [P["GEOGRAPHY"], P["GOVERNANCE"], P["ENVIRONMENT"]],
        "aliases": [
            "National Food Security Act",
            "PDS India",
            "NFSA",
            "Food Security India",
            "Zero Hunger",
            "SDG 2",
        ],
    },
    "Infrastructure Development": {
        "primary_subject": P["ECONOMY"],
        "module": "Infrastructure",
        "secondary_subjects": [P["GEOGRAPHY"], P["GOVERNANCE"]],
        "aliases": [
            "National Infrastructure Pipeline",
            "Smart Cities",
            "Highways India",
            "Railways India",
            "Port Development",
        ],
    },
    "Industrial Policy": {
        "primary_subject": P["ECONOMY"],
        "module": "Industrial Economy",
        "secondary_subjects": [P["POLITY"], P["GEOGRAPHY"]],
        "aliases": [
            "Make in India",
            "PLI Scheme",
            "MSME India",
            "Ease of Doing Business",
            "FDI India",
            "Industrial Corridors",
        ],
    },
    "Trade & WTO": {
        "primary_subject": P["ECONOMY"],
        "module": "International Trade",
        "secondary_subjects": [P["IR"], P["POLITY"]],
        "aliases": [
            "WTO India",
            "India Trade Policy",
            "Current Account Deficit",
            "Export Import Policy",
            "Trade Agreements India",
        ],
    },
    "Globalization & Its Impact": {
        "primary_subject": P["ECONOMY"],
        "module": "Globalization",
        "secondary_subjects": [P["IR"], P["GOVERNANCE"]],
        "aliases": [
            "Globalization India",
            "LPG Reforms 1991",
            "Liberalization Privatization Globalization",
        ],
    },
    "Startup Ecosystem & Innovation": {
        "primary_subject": P["ECONOMY"],
        "module": "Entrepreneurship & Innovation",
        "secondary_subjects": [P["SCIENCE"], P["GOVERNANCE"]],
        "aliases": [
            "Startup India",
            "Innovation India",
            "DPIIT",
            "Unicorns India",
            "Venture Capital India",
        ],
    },
    "Land Reforms": {
        "primary_subject": P["ECONOMY"],
        "module": "Agrarian Economy",
        "secondary_subjects": [P["HISTORY"], P["POLITY"]],
        "aliases": [
            "Land Reforms India",
            "Zamindari Abolition",
            "Tenancy Reforms",
            "Ceiling on Land Holdings",
        ],
    },
    "Health Sector in India": {
        "primary_subject": P["GOVERNANCE"],
        "module": "Health Policy",
        "secondary_subjects": [P["ECONOMY"], P["SCIENCE"]],
        "aliases": [
            "Healthcare India",
            "Ayushman Bharat",
            "NHM",
            "Universal Health Coverage",
            "Public Health India",
        ],
    },
    "Education System in India": {
        "primary_subject": P["GOVERNANCE"],
        "module": "Education Policy",
        "secondary_subjects": [P["ECONOMY"], P["GOVERNANCE"]],
        "aliases": [
            "NEP 2020",
            "National Education Policy",
            "RTE Act",
            "Higher Education India",
            "Skill Development India",
        ],
    },
    # ── ENVIRONMENT & GEOGRAPHY ──────────────────────────────────────────────
    "Climate Change": {
        "primary_subject": P["ENVIRONMENT"],
        "module": "Climate & Global Warming",
        "secondary_subjects": [P["GEOGRAPHY"], P["ECONOMY"], P["IR"]],
        "aliases": [
            "Global Warming",
            "Paris Agreement India",
            "COP",
            "IPCC",
            "Net Zero India",
            "Climate Justice",
        ],
    },
    "Environment & Agriculture Linkage": {
        "primary_subject": P["ENVIRONMENT"],
        "module": "Environmental Sustainability",
        "secondary_subjects": [P["GEOGRAPHY"], P["ECONOMY"]],
        "aliases": [
            "Sustainable Agriculture",
            "Organic Farming India",
            "Agro-ecology",
            "Soil Degradation India",
        ],
    },
    "Water Resource Management": {
        "primary_subject": P["GEOGRAPHY"],
        "module": "Water Resources",
        "secondary_subjects": [P["ENVIRONMENT"], P["POLITY"], P["ECONOMY"]],
        "aliases": [
            "Interlinking of Rivers",
            "Watershed Management",
            "Groundwater Depletion India",
            "Jal Jeevan Mission",
            "Interstate Water Disputes",
        ],
    },
    "Disaster Management": {
        "primary_subject": P["SECURITY"],
        "module": "Disaster Risk Reduction",
        "secondary_subjects": [P["GEOGRAPHY"], P["ENVIRONMENT"], P["GOVERNANCE"]],
        "aliases": [
            "NDMA",
            "Disaster Risk Reduction",
            "Sendai Framework",
            "NDRF",
            "Flood Management India",
        ],
    },
    "Urbanization": {
        "primary_subject": P["GEOGRAPHY"],
        "module": "Human Geography",
        "secondary_subjects": [P["ECONOMY"], P["ENVIRONMENT"], P["GOVERNANCE"]],
        "aliases": [
            "Urban India",
            "Smart Cities Mission",
            "AMRUT",
            "Urban Poverty",
            "Slum Development India",
        ],
    },
    "Population & Demographics": {
        "primary_subject": P["GEOGRAPHY"],
        "module": "Human Geography",
        "secondary_subjects": [P["ECONOMY"], P["GOVERNANCE"]],
        "aliases": [
            "India Population",
            "Demographic Dividend",
            "Census India",
            "Ageing Population India",
            "Population Policy India",
        ],
    },
    "Migration (Internal & International)": {
        "primary_subject": P["GEOGRAPHY"],
        "module": "Human Geography",
        "secondary_subjects": [P["ECONOMY"], P["IR"], P["GOVERNANCE"]],
        "aliases": [
            "Internal Migration India",
            "Indian Diaspora",
            "NRI",
            "Brain Drain India",
            "Refugee Policy India",
        ],
    },
    # ── SCIENCE & TECHNOLOGY ─────────────────────────────────────────────────
    "Science & Technology in Governance": {
        "primary_subject": P["SCIENCE"],
        "module": "Digital Governance & Emerging Tech",
        "secondary_subjects": [P["POLITY"], P["GOVERNANCE"]],
        "aliases": [
            "AI Governance",
            "Digital India",
            "E-Governance India",
            "Blockchain India",
            "Data Protection Bill",
        ],
    },
    "Cyber Security": {
        "primary_subject": P["SCIENCE"],
        "module": "Cyber Security",
        "secondary_subjects": [P["SECURITY"], P["POLITY"]],
        "aliases": [
            "Cyber Warfare",
            "Critical Information Infrastructure",
            "IT Act India",
            "CERT-In",
            "Cyber Crime India",
        ],
    },
    "Space Technology": {
        "primary_subject": P["SCIENCE"],
        "module": "Space Technology",
        "secondary_subjects": [P["IR"], P["SECURITY"]],
        "aliases": [
            "ISRO",
            "Chandrayaan",
            "Gaganyaan",
            "Aditya-L1",
            "Outer Space Treaty",
            "Space Economy India",
        ],
    },
    "Biotechnology": {
        "primary_subject": P["SCIENCE"],
        "module": "Biotechnology",
        "secondary_subjects": [P["ENVIRONMENT"]],
        "aliases": [
            "GMO India",
            "Gene Editing",
            "CRISPR India",
            "Biosafety India",
            "DBT India",
            "Bioeconomy",
        ],
    },
    "Energy Security": {
        "primary_subject": P["ECONOMY"],
        "module": "Energy Policy",
        "secondary_subjects": [P["GEOGRAPHY"], P["ENVIRONMENT"], P["IR"]],
        "aliases": [
            "Renewable Energy India",
            "Solar Energy India",
            "Nuclear Energy India",
            "Energy Transition India",
            "National Solar Mission",
            "Energy Mix India",
            "Oil & Gas India",
        ],
    },
    # ── INTERNATIONAL RELATIONS ──────────────────────────────────────────────
    "India's Foreign Policy": {
        "primary_subject": P["IR"],
        "module": "Indian Foreign Policy",
        "secondary_subjects": [P["HISTORY"], P["GEOGRAPHY"], P["ECONOMY"]],
        "aliases": [
            "India Foreign Relations",
            "Neighbourhood First Policy",
            "Act East Policy",
            "Panchsheel",
            "NAM India",
            "India UN Relations",
            "India US Relations",
            "India China Relations",
            "India Russia Relations",
        ],
    },
    "Border Issues & Disputes": {
        "primary_subject": P["IR"],
        "module": "Borders & Territorial Disputes",
        "secondary_subjects": [P["GEOGRAPHY"], P["SECURITY"], P["HISTORY"]],
        "aliases": [
            "India China Border",
            "India Pakistan Border",
            "LAC",
            "LOC",
            "McMahon Line",
            "Durand Line",
            "India Bangladesh Border",
        ],
    },
    "Regional Organizations (SAARC, ASEAN, SCO)": {
        "primary_subject": P["IR"],
        "module": "Multilateral Organizations",
        "secondary_subjects": [P["ECONOMY"], P["GEOGRAPHY"]],
        "aliases": [
            "SAARC",
            "ASEAN India",
            "SCO India",
            "BRICS India",
            "G20 India",
            "QUAD",
            "I2U2",
            "BIMSTEC",
        ],
    },
    # ── INTERNAL SECURITY ────────────────────────────────────────────────────
    "Internal Security (Terrorism & Naxalism)": {
        "primary_subject": P["SECURITY"],
        "module": "Internal Security Threats",
        "secondary_subjects": [P["GEOGRAPHY"], P["POLITY"], P["GOVERNANCE"]],
        "aliases": [
            "Terrorism India",
            "Left Wing Extremism",
            "Naxalism",
            "UAPA",
            "NIA",
            "Counter-Terrorism India",
        ],
    },
    # ── HISTORY-POLITY BRIDGE ────────────────────────────────────────────────
    "Indian Constitution & Freedom Struggle Legacy": {
        "primary_subject": P["POLITY"],
        "module": "Constitutional History",
        "secondary_subjects": [P["HISTORY"]],
        "aliases": [
            "Constitutional History India",
            "Government of India Acts",
            "Act of 1935",
            "Independence Act 1947",
            "Constituent Assembly India",
        ],
    },
    # ── SUPER NODES (Core integrating concepts) ──────────────────────────────
    "Indian Constitution & Governance": {
        "primary_subject": P["POLITY"],
        "module": "Constitutional Framework",
        "secondary_subjects": [P["HISTORY"], P["GOVERNANCE"]],
        "aliases": ["Indian Constitution", "Constitutional Democracy India"],
    },
    "Ethics, Integrity & Aptitude": {
        "primary_subject": P["GOVERNANCE"],
        "module": "Ethics & Integrity",
        "secondary_subjects": [],
        "aliases": [
            "Ethics GS4",
            "Integrity India",
            "Ethical Governance",
            "Probity in Public Life",
            "Code of Conduct",
        ],
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# LOOKUP HELPERS (used by classifier.py)
# ══════════════════════════════════════════════════════════════════════════════


def lookup_topic(topic_name: str) -> dict | None:
    """
    Direct lookup by canonical name.
    Returns the registry entry or None if not found.
    """
    return CROSS_SUBJECT_MAP.get(topic_name)


def fuzzy_lookup(topic_name: str) -> dict | None:
    """
    Fuzzy lookup: checks both canonical names AND aliases.
    Useful when the user provides a slightly different name.
    Returns the registry entry or None if not found.
    """
    topic_lower = topic_name.lower().strip()

    # Exact match first
    if topic_name in CROSS_SUBJECT_MAP:
        return CROSS_SUBJECT_MAP[topic_name]

    # Alias match
    for canonical, data in CROSS_SUBJECT_MAP.items():
        if topic_lower == canonical.lower():
            return data
        for alias in data.get("aliases", []):
            if topic_lower == alias.lower():
                return data

    # Partial match — topic_name is a substring of a canonical name or alias
    for canonical, data in CROSS_SUBJECT_MAP.items():
        if topic_lower in canonical.lower() or canonical.lower() in topic_lower:
            return data
        for alias in data.get("aliases", []):
            if topic_lower in alias.lower() or alias.lower() in topic_lower:
                return data

    return None


def get_all_canonical_topics() -> list:
    """Returns list of all canonical topic names — for use in run_lab.py."""
    return list(CROSS_SUBJECT_MAP.keys())


def get_secondary_subjects(topic_name: str) -> list:
    """Returns list of secondary subject names for cross-linking (Phase 11)."""
    entry = fuzzy_lookup(topic_name)
    if entry:
        return entry.get("secondary_subjects", [])
    return []
