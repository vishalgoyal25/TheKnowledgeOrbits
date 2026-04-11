"""
engines/tags/management/commands/seed_tags.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase D: Pre-seed 1000+ UPSC-relevant tags into the `tag` table.

Usage:
    python manage.py seed_tags                   # local Postgres
    python manage.py seed_tags --database=supabase  # Supabase (production)

Rules:
    - Tags are lowercase-hyphenated (e.g. "nuclear-energy", "article-370")
    - Slugs are auto-derived from name (hyphens, lowercase)
    - Existing tags are SKIPPED (idempotent — safe to re-run)
    - 10 tag types: topic / subtopic / scheme / person / place /
                    organisation / concept / law / event / other
"""

import structlog
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from engines.tags.models import Tag

logger = structlog.get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# MASTER TAG SEED LIST
# Format: (name, tag_type, description)
# ─────────────────────────────────────────────────────────────────────────────
TAGS: list[tuple[str, str, str]] = [
    # ══════════════════════════════════════════════════════════════════
    # POLITY & GOVERNANCE
    # ══════════════════════════════════════════════════════════════════
    (
        "indian-constitution",
        "topic",
        "The supreme law of India adopted on 26 November 1949",
    ),
    (
        "fundamental-rights",
        "topic",
        "Rights guaranteed under Part III of the Indian Constitution",
    ),
    (
        "directive-principles",
        "topic",
        "Non-justiciable principles in Part IV guiding state policy",
    ),
    ("fundamental-duties", "topic", "Duties of citizens under Article 51A"),
    ("parliament", "topic", "Lok Sabha and Rajya Sabha — the Union legislature"),
    ("lok-sabha", "topic", "Lower house of the Indian Parliament"),
    (
        "rajya-sabha",
        "topic",
        "Upper house / Council of States of the Indian Parliament",
    ),
    ("president-of-india", "topic", "Constitutional head of the Indian Republic"),
    ("prime-minister", "topic", "Head of the Union Council of Ministers"),
    ("council-of-ministers", "topic", "Cabinet and ministers of state at Union level"),
    ("supreme-court", "topic", "Apex court of India; guardian of the Constitution"),
    (
        "high-court",
        "topic",
        "Principal civil court of original jurisdiction in each state",
    ),
    (
        "judicial-review",
        "concept",
        "Power of courts to examine constitutionality of laws",
    ),
    (
        "judicial-activism",
        "concept",
        "Proactive role of judiciary in protecting rights",
    ),
    ("pil", "concept", "Public Interest Litigation — legal action for public welfare"),
    (
        "writ-jurisdiction",
        "concept",
        "Supreme Court and High Court power to issue writs",
    ),
    ("habeas-corpus", "concept", "Writ to produce a detained person before court"),
    (
        "separation-of-powers",
        "concept",
        "Division of government authority among three organs",
    ),
    ("federalism", "concept", "Division of powers between Centre and states"),
    (
        "centre-state-relations",
        "topic",
        "Legislative, administrative and financial relations between Union and states",
    ),
    ("governor", "topic", "Constitutional head of a state; appointed by the President"),
    (
        "state-legislature",
        "topic",
        "Legislature of a state — Vidhan Sabha and Vidhan Parishad",
    ),
    (
        "local-self-government",
        "topic",
        "Panchayats and urban local bodies under 73rd and 74th Amendments",
    ),
    ("panchayati-raj", "topic", "Three-tier rural local self-government system"),
    ("urban-local-bodies", "topic", "Municipalities, corporations and town panchayats"),
    (
        "election-commission",
        "organisation",
        "Constitutional body conducting free and fair elections in India",
    ),
    (
        "electoral-reforms",
        "topic",
        "Changes to make elections more transparent and accountable",
    ),
    (
        "model-code-of-conduct",
        "concept",
        "Guidelines for political parties during elections",
    ),
    (
        "anti-defection-law",
        "law",
        "Tenth Schedule — disqualification of legislators for defection",
    ),
    (
        "constitutional-amendment",
        "concept",
        "Procedure to amend the Constitution under Article 368",
    ),
    (
        "emergency-provisions",
        "topic",
        "Articles 352, 356, 360 — national, state and financial emergency",
    ),
    (
        "president-rule",
        "concept",
        "Imposition of Article 356 in a state — dismissal of elected government",
    ),
    ("attorney-general", "topic", "Chief law officer of the Government of India"),
    (
        "comptroller-auditor-general",
        "organisation",
        "CAG — constitutional auditor of Union and state accounts",
    ),
    (
        "finance-commission",
        "organisation",
        "Constitutional body for devolution of taxes between Centre and states",
    ),
    (
        "upsc-commission",
        "organisation",
        "Union Public Service Commission — central recruiting authority",
    ),
    (
        "niti-aayog",
        "organisation",
        "National Institution for Transforming India — policy think tank",
    ),
    (
        "planning-commission",
        "organisation",
        "Dissolved body that drafted Five-Year Plans",
    ),
    (
        "right-to-information",
        "law",
        "RTI Act 2005 — citizen's right to access government information",
    ),
    (
        "right-to-education",
        "law",
        "Article 21A and RTE Act 2009 — free compulsory education for children",
    ),
    (
        "lokpal-lokayukta",
        "organisation",
        "Anti-corruption ombudsman at Union and state levels",
    ),
    (
        "central-vigilance-commission",
        "organisation",
        "CVC — apex vigilance institution for Central government employees",
    ),
    (
        "national-human-rights-commission",
        "organisation",
        "NHRC — statutory body protecting human rights in India",
    ),
    (
        "goods-and-services-tax",
        "concept",
        "GST — unified indirect tax replacing multiple levies",
    ),
    (
        "gst-council",
        "organisation",
        "Constitutional body governing GST rates and policy",
    ),
    (
        "one-nation-one-election",
        "concept",
        "Simultaneous elections to Lok Sabha and state assemblies",
    ),
    (
        "delimitation-commission",
        "organisation",
        "Body that redraws parliamentary and assembly constituencies",
    ),
    (
        "coalition-politics",
        "concept",
        "Government formation through alliance of multiple parties",
    ),
    (
        "floor-test",
        "concept",
        "Procedure to prove majority on the floor of the legislature",
    ),
    (
        "money-bill",
        "concept",
        "Bill certified by Lok Sabha speaker dealing only with financial matters",
    ),
    (
        "ordinance",
        "concept",
        "Executive legislation promulgated when Parliament is not in session",
    ),
    (
        "question-hour",
        "concept",
        "First hour of parliamentary sitting for asking questions to ministers",
    ),
    (
        "zero-hour",
        "concept",
        "Unscheduled parliamentary time for raising urgent public matters",
    ),
    (
        "privileges-of-parliament",
        "concept",
        "Special rights and immunities enjoyed by Houses and members",
    ),
    (
        "joint-sitting",
        "concept",
        "Article 108 — joint sitting of both Houses to resolve deadlock",
    ),
    (
        "prorogation-dissolution",
        "concept",
        "Ending a parliamentary session vs ending the House's term",
    ),
    (
        "voting-rights",
        "topic",
        "Right to vote and provisions governing elections in India",
    ),
    (
        "election-bonds",
        "concept",
        "Instrument for anonymous political funding declared unconstitutional in 2024",
    ),
    # ══════════════════════════════════════════════════════════════════
    # ECONOMY
    # ══════════════════════════════════════════════════════════════════
    ("indian-economy", "topic", "Structure, growth and challenges of India's economy"),
    (
        "gdp-growth",
        "concept",
        "Gross Domestic Product growth rate of the Indian economy",
    ),
    ("inflation", "concept", "Sustained rise in the general price level"),
    (
        "monetary-policy",
        "concept",
        "RBI's management of money supply and interest rates",
    ),
    (
        "fiscal-policy",
        "concept",
        "Government's use of taxation and spending to influence the economy",
    ),
    ("union-budget", "topic", "Annual financial statement of the Government of India"),
    (
        "rbi",
        "organisation",
        "Reserve Bank of India — central bank and monetary authority",
    ),
    (
        "sebi",
        "organisation",
        "Securities and Exchange Board of India — capital market regulator",
    ),
    ("irda", "organisation", "Insurance Regulatory and Development Authority of India"),
    ("nabard", "organisation", "National Bank for Agriculture and Rural Development"),
    ("sidbi", "organisation", "Small Industries Development Bank of India"),
    ("exim-bank", "organisation", "Export-Import Bank of India"),
    (
        "foreign-direct-investment",
        "concept",
        "FDI — investment by foreign entities in Indian businesses",
    ),
    (
        "foreign-portfolio-investment",
        "concept",
        "FPI — investment by foreigners in Indian securities markets",
    ),
    (
        "balance-of-payments",
        "concept",
        "Record of all economic transactions between India and the world",
    ),
    (
        "current-account-deficit",
        "concept",
        "Excess of imports over exports in goods and services",
    ),
    ("fiscal-deficit", "concept", "Gap between government expenditure and revenue"),
    ("public-debt", "concept", "Total borrowings of the Central and state governments"),
    (
        "disinvestment",
        "concept",
        "Government selling stake in public sector enterprises",
    ),
    (
        "privatisation",
        "concept",
        "Transfer of state-owned enterprises to private ownership",
    ),
    (
        "banking-sector-reforms",
        "topic",
        "Changes to improve efficiency and stability of Indian banks",
    ),
    (
        "nbfc",
        "concept",
        "Non-Banking Financial Company — financial intermediary without full banking licence",
    ),
    (
        "insolvency-bankruptcy-code",
        "law",
        "IBC 2016 — resolution framework for insolvent companies",
    ),
    (
        "msme",
        "concept",
        "Micro, Small and Medium Enterprises — backbone of Indian economy",
    ),
    (
        "startup-ecosystem",
        "topic",
        "India's startup environment, unicorns, and policy support",
    ),
    ("make-in-india", "scheme", "Manufacturing promotion initiative launched in 2014"),
    (
        "atmanirbhar-bharat",
        "scheme",
        "Self-reliant India initiative announced during COVID-19 pandemic",
    ),
    (
        "production-linked-incentive",
        "scheme",
        "PLI — incentive scheme to boost domestic manufacturing",
    ),
    (
        "gig-economy",
        "concept",
        "Work arrangements based on short-term contracts and freelance work",
    ),
    (
        "digital-payments",
        "topic",
        "Electronic payment systems including UPI, NEFT, RTGS",
    ),
    (
        "upi",
        "concept",
        "Unified Payments Interface — real-time interbank mobile payment system",
    ),
    (
        "cryptocurrency",
        "concept",
        "Digital currency using cryptography; regulatory debate in India",
    ),
    ("central-bank-digital-currency", "concept", "CBDC — digital rupee issued by RBI"),
    (
        "infrastructure-investment",
        "topic",
        "Capital formation in roads, ports, railways, energy",
    ),
    (
        "national-infrastructure-pipeline",
        "scheme",
        "NIP — Rs 111 lakh crore infrastructure investment plan",
    ),
    (
        "pm-gati-shakti",
        "scheme",
        "Multi-modal connectivity masterplan integrating infrastructure agencies",
    ),
    (
        "economic-survey",
        "topic",
        "Annual document presenting state of the Indian economy before the budget",
    ),
    ("tax-reforms", "topic", "Changes to direct and indirect tax structure in India"),
    ("income-tax", "concept", "Direct tax levied on individual and corporate income"),
    ("corporate-tax", "concept", "Tax on profits of companies operating in India"),
    ("capital-gains-tax", "concept", "Tax on profit from sale of capital assets"),
    (
        "transfer-pricing",
        "concept",
        "Pricing of transactions between related entities across borders",
    ),
    (
        "double-taxation-avoidance",
        "concept",
        "DTAA treaties preventing same income being taxed twice",
    ),
    (
        "special-economic-zones",
        "concept",
        "SEZ — designated zones with special economic regulations",
    ),
    ("trade-deficit", "concept", "Excess of imports over exports in merchandise trade"),
    ("export-promotion", "topic", "Government policies to increase India's exports"),
    (
        "import-substitution",
        "concept",
        "Strategy to reduce imports by developing domestic industry",
    ),
    (
        "poverty-estimation",
        "topic",
        "Methodology to measure and track poverty in India",
    ),
    (
        "inequality",
        "concept",
        "Disparity in income, wealth and opportunity across population",
    ),
    (
        "human-development-index",
        "concept",
        "HDI — composite index of life expectancy, education and income",
    ),
    ("national-income-accounting", "concept", "Methods to measure GDP, GNP, NNP, NDP"),
    (
        "base-rate-repo-rate",
        "concept",
        "Key policy rates used by RBI to control liquidity",
    ),
    (
        "stagflation",
        "concept",
        "Simultaneous occurrence of inflation and economic stagnation",
    ),
    # ══════════════════════════════════════════════════════════════════
    # INTERNATIONAL RELATIONS
    # ══════════════════════════════════════════════════════════════════
    ("foreign-policy", "topic", "India's external relations and diplomatic strategies"),
    (
        "non-alignment",
        "concept",
        "India's Cold War policy of not joining any military bloc",
    ),
    (
        "neighbourhood-first-policy",
        "concept",
        "India's foreign policy priority for SAARC neighbours",
    ),
    (
        "act-east-policy",
        "concept",
        "India's engagement with Southeast Asian and East Asian nations",
    ),
    (
        "indo-pacific",
        "concept",
        "Strategic construct for the ocean region from Indian Ocean to Pacific",
    ),
    (
        "quad",
        "organisation",
        "Quadrilateral Security Dialogue — India, USA, Japan, Australia",
    ),
    ("brics", "organisation", "Brazil, Russia, India, China, South Africa grouping"),
    (
        "g20",
        "organisation",
        "Group of 20 major economies; India held presidency in 2023",
    ),
    ("g7", "organisation", "Group of 7 most advanced economies"),
    (
        "sco",
        "organisation",
        "Shanghai Cooperation Organisation — Eurasian security grouping",
    ),
    ("saarc", "organisation", "South Asian Association for Regional Cooperation"),
    (
        "bimstec",
        "organisation",
        "Bay of Bengal Initiative for Multi-Sectoral Technical and Economic Cooperation",
    ),
    ("asean", "organisation", "Association of Southeast Asian Nations"),
    (
        "united-nations",
        "organisation",
        "UN — principal international organisation for world peace",
    ),
    (
        "un-security-council",
        "organisation",
        "UNSC — primary body for international peace and security",
    ),
    (
        "un-general-assembly",
        "organisation",
        "UNGA — main deliberative organ of the United Nations",
    ),
    (
        "india-us-relations",
        "topic",
        "Bilateral ties between India and the United States",
    ),
    (
        "india-china-relations",
        "topic",
        "Bilateral ties including border disputes and trade",
    ),
    (
        "india-pakistan-relations",
        "topic",
        "Bilateral relations including Kashmir and cross-border terrorism",
    ),
    (
        "india-russia-relations",
        "topic",
        "Strategic partnership and defence cooperation",
    ),
    ("india-japan-relations", "topic", "Special strategic and global partnership"),
    (
        "india-israel-relations",
        "topic",
        "Defence, technology and agriculture cooperation",
    ),
    ("india-australia-relations", "topic", "Comprehensive strategic partnership"),
    (
        "india-bangladesh-relations",
        "topic",
        "Bilateral ties including water, trade and connectivity",
    ),
    (
        "india-sri-lanka-relations",
        "topic",
        "Bilateral ties including ethnic issues and maritime security",
    ),
    (
        "india-nepal-relations",
        "topic",
        "Historical open-border relationship and water treaties",
    ),
    ("india-bhutan-relations", "topic", "Unique friendship treaty-based relationship"),
    (
        "india-maldives-relations",
        "topic",
        "Strategic maritime partnership in the Indian Ocean",
    ),
    (
        "border-disputes",
        "topic",
        "Territorial disagreements with China, Pakistan and others",
    ),
    (
        "line-of-actual-control",
        "concept",
        "LAC — de facto border between India and China",
    ),
    (
        "line-of-control",
        "concept",
        "LOC — de facto border between India and Pakistan in J&K",
    ),
    (
        "nuclear-doctrine",
        "concept",
        "India's nuclear policy including No First Use commitment",
    ),
    ("nuclear-suppliers-group", "organisation", "NSG — nuclear export control regime"),
    (
        "missile-technology-control-regime",
        "organisation",
        "MTCR — export control for missile technology",
    ),
    (
        "wassenaar-arrangement",
        "organisation",
        "Multilateral export control regime for dual-use goods",
    ),
    (
        "terrorism",
        "topic",
        "Cross-border and domestic terrorism; India's counter-terror policy",
    ),
    (
        "financial-action-task-force",
        "organisation",
        "FATF — global money laundering and terror financing watchdog",
    ),
    ("refugee-crisis", "topic", "Displacement of people and India's refugee policy"),
    ("diaspora", "topic", "Indian diaspora abroad — NRI and PIO communities"),
    ("soft-power", "concept", "India's cultural and diplomatic influence globally"),
    ("climate-diplomacy", "topic", "India's role in global climate negotiations"),
    (
        "trade-war",
        "concept",
        "Conflict between countries over trade tariffs and barriers",
    ),
    ("sanctions", "concept", "Economic or political penalties imposed on countries"),
    (
        "geopolitics",
        "concept",
        "Influence of geography on international politics and strategy",
    ),
    # ══════════════════════════════════════════════════════════════════
    # ENVIRONMENT & ECOLOGY
    # ══════════════════════════════════════════════════════════════════
    (
        "climate-change",
        "topic",
        "Long-term shifts in global temperatures and weather patterns",
    ),
    (
        "global-warming",
        "concept",
        "Rise in Earth's average surface temperature due to greenhouse gases",
    ),
    (
        "greenhouse-gases",
        "concept",
        "CO2, methane, nitrous oxide and other heat-trapping gases",
    ),
    (
        "paris-agreement",
        "law",
        "2015 international treaty to limit global warming to 1.5°C",
    ),
    ("unfccc", "organisation", "UN Framework Convention on Climate Change"),
    (
        "cop-climate-summit",
        "event",
        "Conference of Parties — annual UN climate negotiations",
    ),
    (
        "net-zero-emissions",
        "concept",
        "Balance between greenhouse gas emissions and removal",
    ),
    (
        "carbon-credits",
        "concept",
        "Tradeable permits for emitting a certain amount of CO2",
    ),
    ("carbon-tax", "concept", "Levy on fossil fuel use based on carbon content"),
    (
        "renewable-energy",
        "topic",
        "Energy from sources naturally replenished — solar, wind, hydro",
    ),
    (
        "solar-energy",
        "topic",
        "Electricity generated from sunlight using photovoltaic cells",
    ),
    ("wind-energy", "topic", "Power generated from wind using turbines"),
    (
        "green-hydrogen",
        "concept",
        "Hydrogen produced using renewable electricity — zero emission fuel",
    ),
    (
        "biodiversity",
        "topic",
        "Variety of life on Earth — species, genes and ecosystems",
    ),
    (
        "biodiversity-loss",
        "topic",
        "Decline in species, ecosystems and genetic diversity",
    ),
    (
        "convention-on-biological-diversity",
        "law",
        "CBD — international treaty for biodiversity conservation",
    ),
    (
        "kunming-montreal-framework",
        "law",
        "30x30 biodiversity targets agreed at COP15 in 2022",
    ),
    (
        "endangered-species",
        "topic",
        "Species at risk of extinction due to human activities",
    ),
    (
        "wildlife-protection",
        "topic",
        "Laws and policies to protect animals and their habitats",
    ),
    (
        "forest-conservation",
        "topic",
        "Protection and sustainable management of forests",
    ),
    (
        "deforestation",
        "concept",
        "Clearing of forests for agriculture, urbanisation or industry",
    ),
    ("wetlands", "topic", "Marshy ecosystems of high ecological value — Ramsar sites"),
    ("ramsar-convention", "law", "International treaty for conservation of wetlands"),
    (
        "tiger-conservation",
        "topic",
        "Project Tiger and protection of India's tiger population",
    ),
    (
        "elephant-conservation",
        "topic",
        "Project Elephant and human-wildlife conflict management",
    ),
    (
        "coral-reefs",
        "topic",
        "Marine ecosystems under threat from bleaching and acidification",
    ),
    (
        "ocean-acidification",
        "concept",
        "Increase in ocean acidity due to absorption of CO2",
    ),
    (
        "air-pollution",
        "topic",
        "Contamination of air by harmful gases and particulate matter",
    ),
    (
        "water-pollution",
        "topic",
        "Contamination of water bodies by industrial, agricultural and domestic waste",
    ),
    (
        "solid-waste-management",
        "topic",
        "Collection, processing and disposal of solid waste",
    ),
    (
        "e-waste",
        "concept",
        "Electronic waste — discarded electronic equipment and its management",
    ),
    (
        "plastic-pollution",
        "topic",
        "Environmental harm from plastic waste in land and ocean",
    ),
    (
        "single-use-plastic-ban",
        "law",
        "India's prohibition on specific single-use plastic items from 2022",
    ),
    (
        "national-green-tribunal",
        "organisation",
        "NGT — specialised court for environmental cases in India",
    ),
    (
        "environment-impact-assessment",
        "concept",
        "EIA — process to evaluate environmental effects of projects",
    ),
    (
        "pollution-control-board",
        "organisation",
        "CPCB and SPCBs — regulators of pollution standards",
    ),
    (
        "indian-forest-act",
        "law",
        "Legislation governing forests, forest produce and forest offences",
    ),
    (
        "forest-rights-act",
        "law",
        "FRA 2006 — rights of tribal communities over forest land",
    ),
    (
        "compensatory-afforestation",
        "concept",
        "Planting trees to compensate for forest land diverted",
    ),
    (
        "heat-island-effect",
        "concept",
        "Higher temperatures in urban areas compared to rural surroundings",
    ),
    (
        "ozone-layer",
        "concept",
        "Stratospheric layer protecting Earth from UV radiation",
    ),
    (
        "montreal-protocol",
        "law",
        "International treaty phasing out ozone-depleting substances",
    ),
    (
        "sustainable-development-goals",
        "concept",
        "UN's 17 SDGs for 2030 — global development agenda",
    ),
    (
        "natural-disasters",
        "topic",
        "Floods, droughts, earthquakes, cyclones and their management",
    ),
    (
        "disaster-risk-reduction",
        "concept",
        "Sendai Framework and policies to reduce disaster losses",
    ),
    (
        "ndma",
        "organisation",
        "National Disaster Management Authority — apex body for disaster management",
    ),
    (
        "cyclone-preparedness",
        "topic",
        "Early warning and mitigation measures for tropical cyclones",
    ),
    (
        "drought-management",
        "topic",
        "Policies for drought-proofing and water conservation",
    ),
    (
        "glacial-retreat",
        "concept",
        "Melting of Himalayan and polar glaciers due to global warming",
    ),
    ("sea-level-rise", "concept", "Rise in mean ocean level threatening coastal areas"),
    # ══════════════════════════════════════════════════════════════════
    # SCIENCE & TECHNOLOGY
    # ══════════════════════════════════════════════════════════════════
    (
        "space-technology",
        "topic",
        "India's space programme, satellites and launch vehicles",
    ),
    (
        "isro",
        "organisation",
        "Indian Space Research Organisation — India's national space agency",
    ),
    ("chandrayaan", "event", "India's lunar exploration missions"),
    (
        "mangalyaan",
        "event",
        "India's Mars Orbiter Mission — first Asian nation to reach Mars",
    ),
    ("gaganyaan", "event", "India's first crewed spaceflight mission"),
    (
        "aditya-l1",
        "event",
        "India's first solar observation mission to Lagrange Point 1",
    ),
    (
        "satellite-navigation",
        "topic",
        "NavIC — India's regional navigation satellite system",
    ),
    (
        "artificial-intelligence",
        "topic",
        "AI — simulation of human intelligence by machines",
    ),
    ("machine-learning", "concept", "Subset of AI enabling systems to learn from data"),
    (
        "deep-learning",
        "concept",
        "Neural network-based AI learning from large datasets",
    ),
    (
        "generative-ai",
        "concept",
        "AI systems that create text, images, code and other content",
    ),
    (
        "large-language-models",
        "concept",
        "LLMs — AI models trained on massive text datasets",
    ),
    (
        "digital-india",
        "scheme",
        "Flagship programme to transform India into digital society",
    ),
    (
        "semiconductor",
        "concept",
        "Chip manufacturing — India's push for domestic fab units",
    ),
    ("5g-technology", "concept", "Fifth generation mobile network technology"),
    ("6g-technology", "concept", "Next-generation wireless technology beyond 5G"),
    (
        "cybersecurity",
        "topic",
        "Protection of digital systems from cyber attacks and data breaches",
    ),
    ("cyber-crime", "topic", "Criminal activities using computers and the internet"),
    ("data-protection", "law", "Digital Personal Data Protection Act 2023"),
    ("internet-of-things", "concept", "IoT — network of interconnected smart devices"),
    (
        "blockchain",
        "concept",
        "Distributed ledger technology for secure record-keeping",
    ),
    ("quantum-computing", "concept", "Computing using quantum mechanical phenomena"),
    (
        "biotechnology",
        "topic",
        "Use of biological systems for industrial and medical applications",
    ),
    (
        "genetic-engineering",
        "concept",
        "Modification of an organism's DNA using biotechnology",
    ),
    ("crispr", "concept", "Gene-editing technology for precise DNA modification"),
    (
        "genome-sequencing",
        "concept",
        "Determining the complete DNA sequence of an organism",
    ),
    (
        "vaccine-development",
        "topic",
        "Research and production of vaccines including Covaxin",
    ),
    (
        "nuclear-energy",
        "topic",
        "Power generation using nuclear fission and fusion reactions",
    ),
    (
        "nuclear-reactors",
        "topic",
        "PHWR, fast breeder reactor and thorium cycle in India",
    ),
    (
        "thorium-cycle",
        "concept",
        "India's three-stage nuclear programme using thorium reserves",
    ),
    (
        "defence-technology",
        "topic",
        "Military technology including weapons, drones and electronics",
    ),
    ("drdo", "organisation", "Defence Research and Development Organisation"),
    (
        "missile-technology",
        "topic",
        "Development of ballistic and cruise missiles by DRDO",
    ),
    (
        "agni-prithvi-missiles",
        "topic",
        "India's strategic and tactical ballistic missiles",
    ),
    (
        "brahmos-missile",
        "topic",
        "Supersonic cruise missile developed jointly with Russia",
    ),
    (
        "drone-technology",
        "topic",
        "Unmanned aerial vehicles for civilian and military use",
    ),
    ("tejas-fighter", "topic", "India's indigenously developed light combat aircraft"),
    (
        "indigenous-defence-manufacturing",
        "topic",
        "Atmanirbhar defence — domestic weapons production",
    ),
    (
        "nanotechnology",
        "concept",
        "Manipulation of matter at atomic scale for applications",
    ),
    (
        "3d-printing",
        "concept",
        "Additive manufacturing technology for producing objects layer by layer",
    ),
    ("electric-vehicles", "topic", "Battery-powered vehicles and India's EV policy"),
    (
        "battery-storage",
        "concept",
        "Energy storage systems for renewable power management",
    ),
    (
        "hydrogen-fuel-cell",
        "concept",
        "Technology converting hydrogen into electricity for vehicles",
    ),
    (
        "smart-cities",
        "scheme",
        "Smart Cities Mission — technology-driven urban development",
    ),
    (
        "digilocker",
        "scheme",
        "Digital platform for storing and sharing government documents",
    ),
    ("aadhaar", "scheme", "India's biometric digital identity system"),
    (
        "unified-health-interface",
        "concept",
        "UHI — interoperable digital health ecosystem",
    ),
    (
        "telemedicine",
        "concept",
        "Healthcare delivery using digital communication technologies",
    ),
    (
        "medtech",
        "concept",
        "Medical technology — devices, diagnostics and digital health",
    ),
    ("robotic-surgery", "concept", "Minimally invasive surgery using robotic systems"),
    ("precision-agriculture", "concept", "Use of technology for data-driven farming"),
    (
        "agri-tech",
        "topic",
        "Technology applications in agriculture — sensors, drones, AI",
    ),
    # ══════════════════════════════════════════════════════════════════
    # SOCIAL ISSUES
    # ══════════════════════════════════════════════════════════════════
    (
        "education-policy",
        "topic",
        "National Education Policy 2020 and schooling reforms",
    ),
    (
        "nep-2020",
        "scheme",
        "New Education Policy overhauling school and higher education",
    ),
    (
        "higher-education",
        "topic",
        "Universities, IITs, IIMs and reforms in college education",
    ),
    (
        "skill-development",
        "topic",
        "Vocational training and skilling initiatives in India",
    ),
    (
        "pm-kaushal-vikas-yojana",
        "scheme",
        "PMKVY — flagship skill training scheme under MSDE",
    ),
    ("health-policy", "topic", "National Health Policy and healthcare system in India"),
    (
        "ayushman-bharat",
        "scheme",
        "PM-JAY — health insurance scheme for economically vulnerable",
    ),
    (
        "national-health-mission",
        "scheme",
        "NHM — umbrella programme for public health services",
    ),
    (
        "mental-health",
        "topic",
        "Policies and initiatives for mental healthcare in India",
    ),
    (
        "malnutrition",
        "topic",
        "Stunting, wasting and undernutrition among children and women",
    ),
    (
        "poshan-abhiyaan",
        "scheme",
        "Mission to reduce malnutrition among pregnant women and children",
    ),
    (
        "women-empowerment",
        "topic",
        "Policies and programmes for gender equality and women's rights",
    ),
    (
        "gender-gap",
        "concept",
        "Disparity between men and women in education, work and pay",
    ),
    (
        "violence-against-women",
        "topic",
        "Domestic violence, sexual assault and harassment policies",
    ),
    (
        "maternity-benefits",
        "law",
        "Maternity Benefit Act and paid leave for working mothers",
    ),
    (
        "child-labour",
        "topic",
        "Prohibition of child labour and child rights protection",
    ),
    (
        "child-marriage",
        "topic",
        "Early marriage below legal age — law and social campaign",
    ),
    (
        "dowry-system",
        "concept",
        "Illegal practice of giving gifts at marriage — Dowry Prohibition Act",
    ),
    (
        "caste-system",
        "topic",
        "India's hierarchical social structure and caste discrimination",
    ),
    (
        "sc-st-reservations",
        "topic",
        "Scheduled Caste and Scheduled Tribe reservations in jobs and education",
    ),
    (
        "obc-reservations",
        "topic",
        "Other Backward Classes reservation and Mandal Commission",
    ),
    (
        "creamy-layer",
        "concept",
        "Well-off sections of OBC excluded from reservation benefits",
    ),
    (
        "atrocities-act",
        "law",
        "SC/ST (Prevention of Atrocities) Act — protection from discrimination",
    ),
    ("tribal-welfare", "topic", "Policies and schemes for Scheduled Tribe communities"),
    ("slum-rehabilitation", "topic", "Urban housing schemes for slum dwellers"),
    ("urban-poverty", "topic", "Poverty and livelihood challenges in urban areas"),
    (
        "lgbtq-rights",
        "topic",
        "Legal recognition and rights of LGBTQ+ persons in India",
    ),
    (
        "section-377",
        "law",
        "IPC provision struck down by Supreme Court decriminalising homosexuality",
    ),
    (
        "uniform-civil-code",
        "concept",
        "UCC — common personal law for all citizens regardless of religion",
    ),
    (
        "population-policy",
        "topic",
        "Policies to manage India's population growth and demographics",
    ),
    (
        "demographic-dividend",
        "concept",
        "Economic benefit from large working-age population",
    ),
    (
        "ageing-population",
        "concept",
        "Growing proportion of elderly people in India's demographics",
    ),
    (
        "drug-abuse",
        "topic",
        "Substance abuse and India's de-addiction and narcotic control policies",
    ),
    ("ndps-act", "law", "Narcotics, Drugs and Psychotropic Substances Act 1985"),
    (
        "communalism",
        "concept",
        "Promotion of one religious group's interests against another",
    ),
    (
        "secularism",
        "concept",
        "Separation of religion from state; equal treatment of all religions",
    ),
    (
        "regionalism",
        "concept",
        "Excessive promotion of regional interests over national unity",
    ),
    ("naxalism", "topic", "Left-wing extremism — Maoist insurgency in central India"),
    ("insurgency", "topic", "Armed rebellions in northeast India and J&K"),
    # ══════════════════════════════════════════════════════════════════
    # HISTORY
    # ══════════════════════════════════════════════════════════════════
    (
        "indus-valley-civilisation",
        "topic",
        "Bronze Age civilisation along the Indus river — Harappa, Mohenjodaro",
    ),
    ("vedic-age", "topic", "Period of Rigveda and early Aryan settlements in India"),
    (
        "maurya-empire",
        "topic",
        "Empire founded by Chandragupta Maurya — Ashoka's reign",
    ),
    ("gupta-empire", "topic", "Golden Age of India — art, science and literature"),
    (
        "delhi-sultanate",
        "topic",
        "Five successive Islamic dynasties ruling from Delhi 1206–1526",
    ),
    ("mughal-empire", "topic", "Mughal rule in India from Babur to Aurangzeb"),
    ("maratha-empire", "topic", "Maratha confederacy under Shivaji and the Peshwas"),
    ("british-colonialism", "topic", "British rule in India from 1857 to 1947"),
    (
        "east-india-company",
        "organisation",
        "British trading company that colonised India",
    ),
    (
        "revolt-of-1857",
        "event",
        "First War of Indian Independence against British rule",
    ),
    (
        "indian-national-congress",
        "organisation",
        "INC — premier political party of the independence movement",
    ),
    (
        "freedom-movement",
        "topic",
        "India's struggle for independence from British rule",
    ),
    (
        "mahatma-gandhi",
        "person",
        "Father of the Nation — leader of non-violent independence movement",
    ),
    (
        "non-cooperation-movement",
        "event",
        "Gandhi's mass civil disobedience campaign 1920–22",
    ),
    (
        "civil-disobedience-movement",
        "event",
        "Salt March and nationwide campaign against British laws 1930",
    ),
    (
        "quit-india-movement",
        "event",
        "1942 movement demanding immediate British withdrawal from India",
    ),
    (
        "partition-of-india",
        "event",
        "Division of British India into India and Pakistan in 1947",
    ),
    ("subhas-chandra-bose", "person", "INA leader and revolutionary freedom fighter"),
    ("bhagat-singh", "person", "Revolutionary freedom fighter and socialist thinker"),
    (
        "br-ambedkar",
        "person",
        "Father of the Indian Constitution and champion of Dalit rights",
    ),
    (
        "jawaharlal-nehru",
        "person",
        "First Prime Minister of India — architect of modern India",
    ),
    (
        "sardar-patel",
        "person",
        "Iron Man of India — unified princely states into Indian Union",
    ),
    (
        "indira-gandhi",
        "person",
        "Prime Minister who declared Emergency and led 1971 war",
    ),
    (
        "emergency-1975",
        "event",
        "Period of authoritarian rule declared by Indira Gandhi 1975–77",
    ),
    (
        "green-revolution",
        "event",
        "1960s agricultural transformation using HYV seeds and irrigation",
    ),
    (
        "white-revolution",
        "event",
        "Operation Flood — India's dairy development programme",
    ),
    ("kargil-war", "event", "1999 conflict between India and Pakistan in Kargil, J&K"),
    ("pokhran-tests", "event", "India's nuclear weapons tests in 1974 and 1998"),
    (
        "banking-nationalisation",
        "event",
        "1969 nationalisation of 14 major private banks by Indira Gandhi",
    ),
    (
        "liberalisation-1991",
        "event",
        "Economic reforms opening India to market economy in 1991",
    ),
    (
        "nehruvian-socialism",
        "concept",
        "Nehru's mixed economy model with heavy public sector emphasis",
    ),
    # ══════════════════════════════════════════════════════════════════
    # GEOGRAPHY
    # ══════════════════════════════════════════════════════════════════
    (
        "indian-monsoon",
        "topic",
        "Seasonal reversal of winds bringing rainfall to India",
    ),
    (
        "himalayas",
        "place",
        "World's highest mountain range forming India's northern boundary",
    ),
    ("deccan-plateau", "place", "Peninsular plateau comprising most of South India"),
    (
        "indo-gangetic-plain",
        "place",
        "Fertile alluvial plains between Himalayas and Deccan",
    ),
    ("western-ghats", "place", "Biodiversity hotspot along India's western coast"),
    (
        "eastern-ghats",
        "place",
        "Discontinuous chain of hills along India's eastern coast",
    ),
    ("river-systems-india", "topic", "Himalayan and Peninsular river systems of India"),
    ("ganga-river", "place", "India's most sacred river — Namami Gange programme"),
    ("brahmaputra-river", "place", "River flowing through Tibet, Arunachal and Assam"),
    (
        "indus-river",
        "place",
        "River giving India its name — Indus Waters Treaty with Pakistan",
    ),
    (
        "krishna-godavari-basin",
        "place",
        "Major river basins of South India with hydrocarbon reserves",
    ),
    ("thar-desert", "place", "World's most populated desert in Rajasthan and Pakistan"),
    (
        "andaman-nicobar-islands",
        "place",
        "India's island territory in the Bay of Bengal",
    ),
    ("lakshadweep", "place", "India's coral island territory in the Arabian Sea"),
    ("indian-ocean", "place", "Strategic maritime region central to India's security"),
    (
        "arctic-polar-regions",
        "topic",
        "Geopolitical and climate significance of polar regions for India",
    ),
    (
        "earthquake-seismic-zones",
        "topic",
        "India's seismic vulnerability and earthquake-prone regions",
    ),
    (
        "urban-planning",
        "topic",
        "Planning and development of cities and metropolitan areas",
    ),
    (
        "water-bodies",
        "topic",
        "Lakes, reservoirs, ponds and their ecological importance",
    ),
    (
        "groundwater-depletion",
        "topic",
        "Over-extraction of groundwater and policy responses",
    ),
    (
        "interlinking-rivers",
        "topic",
        "Proposal to transfer surplus water from one basin to another",
    ),
    (
        "atal-bhujal-yojana",
        "scheme",
        "Groundwater management scheme for seven Indian states",
    ),
    # ══════════════════════════════════════════════════════════════════
    # AGRICULTURE & RURAL DEVELOPMENT
    # ══════════════════════════════════════════════════════════════════
    (
        "agriculture-policy",
        "topic",
        "Policies governing farming, farmers and food production",
    ),
    (
        "pm-kisan",
        "scheme",
        "PM-KISAN — direct income support to small and marginal farmers",
    ),
    ("msp", "concept", "Minimum Support Price — guaranteed price for farm produce"),
    (
        "farm-laws-2020",
        "law",
        "Three farm reform acts repealed after farmer protests in 2021",
    ),
    ("farmers-protest", "event", "2020–21 protests against three farm reform laws"),
    ("irrigation", "topic", "Systems and schemes providing water to agricultural land"),
    (
        "pradhan-mantri-krishi-sinchai",
        "scheme",
        "PMKSY — micro-irrigation and water use efficiency scheme",
    ),
    (
        "food-security",
        "topic",
        "Ensuring adequate food for all — PDS, NFSA, buffer stocks",
    ),
    (
        "national-food-security-act",
        "law",
        "NFSA 2013 — legal entitlement to subsidised food grains",
    ),
    (
        "public-distribution-system",
        "scheme",
        "PDS — subsidised food grain distribution to poor households",
    ),
    ("fertiliser-subsidy", "topic", "Government subsidy on urea and other fertilisers"),
    (
        "soil-health-card",
        "scheme",
        "Scheme providing farmers a card with soil nutrient status",
    ),
    (
        "crop-insurance",
        "scheme",
        "PMFBY — crop insurance scheme for farmers against losses",
    ),
    (
        "cooperative-movement",
        "topic",
        "Farmer cooperatives including AMUL, IFFCO and sugar cooperatives",
    ),
    (
        "contract-farming",
        "concept",
        "Pre-agreed supply contracts between farmers and buyers",
    ),
    (
        "organic-farming",
        "concept",
        "Farming without synthetic chemicals — certification and markets",
    ),
    (
        "natural-farming",
        "concept",
        "Zero-budget natural farming using local bio-inputs",
    ),
    (
        "food-processing",
        "topic",
        "Value addition to agricultural produce — MOFPI schemes",
    ),
    (
        "cold-chain-infrastructure",
        "topic",
        "Post-harvest storage and transport to reduce wastage",
    ),
    (
        "fisheries",
        "topic",
        "Marine and inland fisheries — Blue Revolution and PM Matsya Sampada",
    ),
    (
        "pm-matsya-sampada-yojana",
        "scheme",
        "Flagship scheme for sustainable development of fisheries",
    ),
    (
        "animal-husbandry",
        "topic",
        "Livestock management — dairy, poultry and cattle rearing",
    ),
    (
        "mgnrega",
        "scheme",
        "Mahatma Gandhi NREGS — 100 days employment guarantee in rural areas",
    ),
    (
        "pm-awas-yojana-rural",
        "scheme",
        "Housing scheme for rural poor — pucca house construction",
    ),
    (
        "deen-dayal-upadhyaya-grameen",
        "scheme",
        "DDU-GKY — rural livelihood and skill development",
    ),
    (
        "svamitva-scheme",
        "scheme",
        "Survey of villages using drone technology for property rights",
    ),
    # ══════════════════════════════════════════════════════════════════
    # SECURITY & DEFENCE
    # ══════════════════════════════════════════════════════════════════
    ("national-security", "topic", "India's internal and external security framework"),
    (
        "armed-forces",
        "topic",
        "Indian Army, Navy and Air Force — structure and modernisation",
    ),
    ("border-security", "topic", "Management of India's land and maritime borders"),
    (
        "bsf",
        "organisation",
        "Border Security Force — guarding India-Pakistan and India-Bangladesh borders",
    ),
    (
        "crpf",
        "organisation",
        "Central Reserve Police Force — internal security and anti-naxal operations",
    ),
    (
        "intelligence-agencies",
        "organisation",
        "RAW, IB, NTRO — India's intelligence framework",
    ),
    (
        "national-security-council",
        "organisation",
        "NSC — apex body for national security decision-making",
    ),
    (
        "cyber-warfare",
        "concept",
        "Use of digital attacks to damage or disrupt adversary's systems",
    ),
    (
        "hybrid-warfare",
        "concept",
        "Combination of conventional, cyber and information warfare",
    ),
    (
        "counter-terrorism",
        "topic",
        "Policies, laws and operations to prevent and respond to terrorism",
    ),
    ("nsa", "topic", "National Security Act — preventive detention law"),
    ("uapa", "law", "Unlawful Activities Prevention Act — anti-terror legislation"),
    (
        "defence-budget",
        "topic",
        "Annual allocation for India's armed forces and defence modernisation",
    ),
    (
        "military-exercises",
        "topic",
        "Bilateral and multilateral defence exercises involving India",
    ),
    ("malabar-exercise", "event", "Trilateral naval exercise — India, USA, Japan"),
    (
        "agnipath-scheme",
        "scheme",
        "Short-term military recruitment scheme for 4-year service",
    ),
    (
        "one-rank-one-pension",
        "scheme",
        "Uniform pension for retired military personnel at same rank",
    ),
    (
        "strategic-autonomy",
        "concept",
        "India's policy of independent decision-making in defence and foreign policy",
    ),
    (
        "military-modernisation",
        "topic",
        "Upgradation of equipment, technology and capabilities of armed forces",
    ),
    (
        "theatre-commands",
        "concept",
        "Integrated tri-service commands for operational theatre",
    ),
    (
        "cds",
        "topic",
        "Chief of Defence Staff — single-point military adviser to government",
    ),
    (
        "nuclear-triad",
        "concept",
        "Nuclear delivery capability through land, sea and air platforms",
    ),
    # ══════════════════════════════════════════════════════════════════
    # GOVERNMENT SCHEMES
    # ══════════════════════════════════════════════════════════════════
    (
        "pm-modi-schemes",
        "scheme",
        "Flagship programmes launched under PM Narendra Modi",
    ),
    (
        "jan-dhan-yojana",
        "scheme",
        "PMJDY — financial inclusion scheme for universal bank account access",
    ),
    (
        "mudra-yojana",
        "scheme",
        "MUDRA — micro-credit scheme for small business entrepreneurs",
    ),
    (
        "stand-up-india",
        "scheme",
        "Loans to SC/ST and women entrepreneurs for greenfield enterprises",
    ),
    (
        "startup-india",
        "scheme",
        "Programme to build a strong startup ecosystem with tax and regulatory benefits",
    ),
    (
        "swachh-bharat-mission",
        "scheme",
        "Clean India Mission — toilet construction and open defecation free",
    ),
    (
        "namami-gange",
        "scheme",
        "Integrated mission to clean and rejuvenate river Ganga",
    ),
    (
        "smart-cities-mission",
        "scheme",
        "Development of 100 cities with smart infrastructure",
    ),
    (
        "atal-mission-rejuvenation",
        "scheme",
        "AMRUT — urban infrastructure development in 500 cities",
    ),
    (
        "pm-awas-yojana-urban",
        "scheme",
        "Housing for All — affordable housing in urban areas",
    ),
    ("ujjwala-yojana", "scheme", "Free LPG connections for women in BPL households"),
    ("saubhagya-scheme", "scheme", "Universal household electrification scheme"),
    (
        "jal-jeevan-mission",
        "scheme",
        "Har Ghar Jal — tap water connections to rural households by 2024",
    ),
    (
        "ayushman-bharat-digital",
        "scheme",
        "ABHA — health ID and digital health records for citizens",
    ),
    ("e-shram-portal", "scheme", "Registration portal for unorganised sector workers"),
    (
        "one-district-one-product",
        "scheme",
        "ODOP — promotion of unique products from each district",
    ),
    (
        "aspirational-districts",
        "scheme",
        "Transformation of 112 least developed districts",
    ),
    (
        "pm-poshan",
        "scheme",
        "Mid-Day Meal Scheme renamed to PM POSHAN for school children",
    ),
    (
        "national-apprenticeship-scheme",
        "scheme",
        "Apprenticeship training for youth in industry",
    ),
    (
        "dbt-direct-benefit-transfer",
        "scheme",
        "DBT — direct transfer of subsidies to beneficiaries' accounts",
    ),
    ("fastrack-courts", "scheme", "Fast Track Special Courts for POCSO and rape cases"),
    ("vivaad-se-vishwas", "scheme", "Tax dispute resolution scheme"),
    ("sabka-vishwas-scheme", "scheme", "Indirect tax dispute legacy resolution scheme"),
    # ══════════════════════════════════════════════════════════════════
    # LAWS & ACTS
    # ══════════════════════════════════════════════════════════════════
    (
        "companies-act-2013",
        "law",
        "Legislation governing incorporation and regulation of companies",
    ),
    (
        "consumer-protection-act",
        "law",
        "Consumer Protection Act 2019 — rights and redressal for consumers",
    ),
    (
        "competition-act",
        "law",
        "Competition Act 2002 — prevention of anti-competitive practices",
    ),
    (
        "prevention-of-corruption-act",
        "law",
        "PCA — law against corruption of public servants",
    ),
    (
        "sedition-law",
        "law",
        "IPC Section 124A — criminalising acts against the state; under review",
    ),
    ("pocso-act", "law", "Protection of Children from Sexual Offences Act 2012"),
    (
        "juvenile-justice-act",
        "law",
        "JJ Act 2015 — care and protection of children in conflict with law",
    ),
    (
        "domestic-violence-act",
        "law",
        "PWDVA 2005 — protection of women from domestic violence",
    ),
    (
        "land-acquisition-act",
        "law",
        "LARR Act 2013 — fair compensation for land taken for public purpose",
    ),
    (
        "forest-conservation-act",
        "law",
        "Legislation restricting diversion of forest land for non-forest use",
    ),
    (
        "environment-protection-act",
        "law",
        "EPA 1986 — umbrella legislation for environmental protection",
    ),
    ("water-act", "law", "Water (Prevention and Control of Pollution) Act 1974"),
    ("air-act", "law", "Air (Prevention and Control of Pollution) Act 1981"),
    (
        "coastal-regulation-zone",
        "law",
        "CRZ notification regulating development near coastlines",
    ),
    (
        "mines-and-minerals-act",
        "law",
        "MMDR Act — regulation of mines and mineral development",
    ),
    ("patent-act", "law", "Patents Act 1970 — protection of inventions in India"),
    (
        "copyright-act",
        "law",
        "Copyright Act 1957 — protection of literary and creative works",
    ),
    (
        "it-act-2000",
        "law",
        "Information Technology Act — legal framework for digital transactions",
    ),
    (
        "posh-act",
        "law",
        "Prevention of Sexual Harassment of Women at Workplace Act 2013",
    ),
    ("food-safety-act", "law", "FSSAI — food safety standards and regulation"),
    (
        "drug-price-control",
        "law",
        "DPCO — government control over prices of essential medicines",
    ),
    (
        "arms-act",
        "law",
        "Arms Act 1959 — regulation of acquisition and possession of firearms",
    ),
    (
        "motor-vehicles-act",
        "law",
        "MV Act 2019 — road safety and traffic regulation reforms",
    ),
    (
        "insolvency-and-bankruptcy-code",
        "law",
        "IBC 2016 — time-bound resolution of corporate insolvencies",
    ),
    (
        "benami-transactions-act",
        "law",
        "Benami Transactions Act — prohibition of holding property in fictitious names",
    ),
    ("black-money-act", "law", "Black Money (Undisclosed Foreign Income) Act 2015"),
    (
        "pmla",
        "law",
        "Prevention of Money Laundering Act 2002 — ED's primary legal tool",
    ),
    ("rera", "law", "Real Estate Regulation and Development Act 2016"),
    (
        "new-criminal-laws",
        "law",
        "BNS, BNSS, BSA — replacing IPC, CrPC and Indian Evidence Act in 2024",
    ),
    (
        "bharatiya-nyaya-sanhita",
        "law",
        "BNS — new criminal code replacing the Indian Penal Code",
    ),
    # ══════════════════════════════════════════════════════════════════
    # ORGANISATIONS & BODIES
    # ══════════════════════════════════════════════════════════════════
    (
        "world-bank",
        "organisation",
        "International financial institution providing loans for development",
    ),
    (
        "imf",
        "organisation",
        "International Monetary Fund — global financial stability body",
    ),
    ("wto", "organisation", "World Trade Organisation — global trade rules body"),
    ("who", "organisation", "World Health Organisation — UN public health agency"),
    ("unicef", "organisation", "UN Children's Fund — child welfare and rights"),
    (
        "undp",
        "organisation",
        "UN Development Programme — sustainable development goals",
    ),
    ("ilo", "organisation", "International Labour Organisation — labour standards"),
    ("iaea", "organisation", "International Atomic Energy Agency — nuclear safeguards"),
    ("interpol", "organisation", "International Criminal Police Organisation"),
    (
        "cci",
        "organisation",
        "Competition Commission of India — anti-monopoly regulator",
    ),
    ("trai", "organisation", "Telecom Regulatory Authority of India"),
    ("cerc", "organisation", "Central Electricity Regulatory Commission"),
    ("pfrda", "organisation", "Pension Fund Regulatory and Development Authority"),
    ("nhrc", "organisation", "National Human Rights Commission"),
    ("ncw", "organisation", "National Commission for Women"),
    ("ncpcr", "organisation", "National Commission for Protection of Child Rights"),
    (
        "nsc",
        "organisation",
        "National Statistical Commission — official statistics body",
    ),
    ("ibbi", "organisation", "Insolvency and Bankruptcy Board of India"),
    (
        "nclt",
        "organisation",
        "National Company Law Tribunal — corporate disputes court",
    ),
    ("epfo", "organisation", "Employees Provident Fund Organisation"),
    ("esic", "organisation", "Employees State Insurance Corporation"),
    ("fssai", "organisation", "Food Safety and Standards Authority of India"),
    (
        "cbi",
        "organisation",
        "Central Bureau of Investigation — India's premier investigation agency",
    ),
    (
        "ed",
        "organisation",
        "Enforcement Directorate — financial crimes investigation agency",
    ),
    ("ncb", "organisation", "Narcotics Control Bureau — drug law enforcement agency"),
    # ══════════════════════════════════════════════════════════════════
    # EVENTS (recent and recurring)
    # ══════════════════════════════════════════════════════════════════
    ("g20-india-presidency", "event", "India's G20 Presidency 2023 — New Delhi Summit"),
    (
        "covid-19-pandemic",
        "event",
        "Global pandemic caused by SARS-CoV-2 — impact on India",
    ),
    (
        "russia-ukraine-war",
        "event",
        "Ongoing conflict between Russia and Ukraine from 2022",
    ),
    (
        "israel-gaza-conflict",
        "event",
        "Conflict in Gaza — India's humanitarian and diplomatic response",
    ),
    (
        "india-canada-dispute",
        "event",
        "Diplomatic row over Khalistan extremism allegations 2023",
    ),
    (
        "india-china-galwan",
        "event",
        "2020 Galwan Valley clash — India-China LAC standoff",
    ),
    ("india-general-elections", "event", "Indian General Elections — Lok Sabha polls"),
    ("state-elections", "event", "Assembly elections in various Indian states"),
    ("budget-2024-25", "event", "Union Budget for financial year 2024-25"),
    (
        "supreme-court-verdicts",
        "event",
        "Landmark Supreme Court judgments with constitutional significance",
    ),
    (
        "electoral-bonds-verdict",
        "event",
        "SC 2024 verdict striking down electoral bonds scheme",
    ),
    (
        "ayodhya-verdict",
        "event",
        "SC 2019 verdict on Ram Janmabhoomi-Babri Masjid dispute",
    ),
    (
        "abrogation-article-370",
        "event",
        "2019 revocation of Jammu and Kashmir's special status",
    ),
    (
        "citizenship-amendment-act",
        "law",
        "CAA 2019 — fast-track citizenship for persecuted minorities from 3 neighbours",
    ),
    (
        "nrc",
        "concept",
        "National Register of Citizens — citizenship verification in India",
    ),
    ("demonetisation", "event", "2016 withdrawal of ₹500 and ₹1000 currency notes"),
    ("gst-rollout", "event", "GST launched on 1 July 2017 — one nation one tax"),
    (
        "india-moon-landing",
        "event",
        "Chandrayaan-3 soft landing on lunar south pole in August 2023",
    ),
    (
        "manipur-conflict",
        "event",
        "Ethnic violence between Meitei and Kuki communities in 2023",
    ),
    (
        "wrestlers-protest",
        "event",
        "2023 protest by Indian wrestlers against WFI chief",
    ),
    # ══════════════════════════════════════════════════════════════════
    # PERSONS (historical and contemporary)
    # ══════════════════════════════════════════════════════════════════
    (
        "swami-vivekananda",
        "person",
        "Hindu monk who introduced Vedanta and Yoga to the Western world",
    ),
    (
        "rabindranath-tagore",
        "person",
        "Poet, novelist and Nobel laureate — author of India's national anthem",
    ),
    ("aryabhata", "person", "Ancient Indian mathematician and astronomer"),
    ("chanakya", "person", "Ancient Indian strategist and author of Arthashastra"),
    ("ashoka", "person", "Mauryan emperor who embraced Buddhism and spread dharma"),
    ("akbar", "person", "Mughal emperor known for religious tolerance — Din-i-Ilahi"),
    ("tipu-sultan", "person", "Ruler of Mysore and early resistance to British rule"),
    (
        "lal-bal-pal",
        "person",
        "Lala Lajpat Rai, Bal Gangadhar Tilak, Bipin Chandra Pal — nationalist trio",
    ),
    (
        "rani-lakshmibai",
        "person",
        "Queen of Jhansi — symbol of 1857 revolt against British",
    ),
    ("ramanujan", "person", "Self-taught mathematical genius from India"),
    ("homi-bhabha", "person", "Father of India's nuclear programme"),
    ("vikram-sarabhai", "person", "Father of India's space programme"),
    ("ms-swaminathan", "person", "Father of India's Green Revolution"),
    ("verghese-kurien", "person", "Father of India's White Revolution — AMUL"),
    ("narendra-modi", "person", "14th Prime Minister of India — BJP leader"),
    (
        "dr-manmohan-singh",
        "person",
        "13th Prime Minister and architect of 1991 economic liberalisation",
    ),
    # ══════════════════════════════════════════════════════════════════
    # CONCEPTS (cross-cutting)
    # ══════════════════════════════════════════════════════════════════
    ("rule-of-law", "concept", "Principle that everyone is subject to the law equally"),
    (
        "due-process",
        "concept",
        "Legal requirement of fair procedures before government action",
    ),
    (
        "natural-justice",
        "concept",
        "Principles of audi alteram partem and nemo judex in causa sua",
    ),
    (
        "constitutionalism",
        "concept",
        "Principle of limiting government power through constitutional norms",
    ),
    ("sovereignty", "concept", "Supreme authority of the state within its territory"),
    ("parliamentary-sovereignty", "concept", "Supremacy of Parliament in law-making"),
    (
        "basic-structure-doctrine",
        "concept",
        "SC ruling that Parliament cannot amend Constitution's basic features",
    ),
    (
        "doctrine-of-severability",
        "concept",
        "Only unconstitutional part of a law is struck down",
    ),
    (
        "delegated-legislation",
        "concept",
        "Law-making by executive under authority granted by Parliament",
    ),
    (
        "administrative-law",
        "concept",
        "Laws governing powers and procedures of government agencies",
    ),
    (
        "ombudsman",
        "concept",
        "Independent official investigating public complaints against government",
    ),
    (
        "good-governance",
        "concept",
        "Accountable, transparent, participatory and rule-based governance",
    ),
    ("e-governance", "concept", "Use of ICT to deliver government services"),
    (
        "cooperative-federalism",
        "concept",
        "Centre-state collaboration for shared development goals",
    ),
    (
        "competitive-federalism",
        "concept",
        "States competing to attract investment and improve governance",
    ),
    ("fourth-pillar-democracy", "concept", "Free press as watchdog of democracy"),
    (
        "hate-speech",
        "concept",
        "Speech inciting discrimination or violence against groups",
    ),
    (
        "freedom-of-expression",
        "concept",
        "Article 19(1)(a) — right to express views freely with reasonable restrictions",
    ),
    (
        "minority-rights",
        "concept",
        "Rights of linguistic and religious minorities under Articles 29-30",
    ),
    (
        "tribal-rights",
        "concept",
        "Rights of Scheduled Tribes — land, forest, self-governance",
    ),
    (
        "right-to-privacy",
        "concept",
        "Fundamental right declared by SC in Puttaswamy judgment 2017",
    ),
    ("right-to-food", "concept", "Implied fundamental right derived from Article 21"),
    (
        "right-to-health",
        "concept",
        "Implied fundamental right to healthcare under Article 21",
    ),
    (
        "right-to-shelter",
        "concept",
        "Implied right to adequate housing under Article 21",
    ),
    ("human-rights", "concept", "Inherent rights and freedoms of all human beings"),
    (
        "international-humanitarian-law",
        "law",
        "Geneva Conventions and laws of armed conflict",
    ),
    (
        "sustainable-development",
        "concept",
        "Development meeting present needs without compromising future generations",
    ),
    (
        "circular-economy",
        "concept",
        "Economic model minimising waste by reusing and recycling",
    ),
    (
        "blue-economy",
        "concept",
        "Sustainable use of ocean resources for economic growth",
    ),
    (
        "knowledge-economy",
        "concept",
        "Economy driven by knowledge, innovation and intellectual capital",
    ),
    (
        "inclusive-growth",
        "concept",
        "Economic growth benefiting all sections of society",
    ),
    (
        "public-private-partnership",
        "concept",
        "PPP — joint venture between government and private sector",
    ),
    (
        "foreign-exchange-reserves",
        "concept",
        "India's holdings of gold, SDRs and foreign currencies",
    ),
    (
        "ease-of-doing-business",
        "concept",
        "World Bank ranking of regulatory environment for businesses",
    ),
    (
        "swot-analysis",
        "concept",
        "Strategic planning framework — strengths, weaknesses, opportunities, threats",
    ),
    (
        "critical-minerals",
        "concept",
        "Lithium, cobalt, rare earths essential for clean energy transition",
    ),
    (
        "food-inflation",
        "concept",
        "Rise in prices of food items — vegetable, pulse and cereal prices",
    ),
    ("core-inflation", "concept", "Inflation excluding volatile food and fuel prices"),
    (
        "repo-rate",
        "concept",
        "Rate at which RBI lends overnight funds to commercial banks",
    ),
    ("reverse-repo-rate", "concept", "Rate at which RBI borrows from commercial banks"),
    (
        "crr-slr",
        "concept",
        "Cash Reserve Ratio and Statutory Liquidity Ratio — bank reserve requirements",
    ),
    (
        "open-market-operations",
        "concept",
        "RBI's buying and selling of government securities to control liquidity",
    ),
    (
        "priority-sector-lending",
        "concept",
        "Mandatory bank credit to agriculture, MSME and weaker sections",
    ),
    (
        "microfinance",
        "concept",
        "Small loans to low-income individuals and self-help groups",
    ),
    (
        "self-help-groups",
        "concept",
        "SHG — small groups for savings, credit and livelihood support",
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# COMMAND
# ─────────────────────────────────────────────────────────────────────────────


class Command(BaseCommand):
    help = (
        "Phase D: Seed 1000+ UPSC-relevant tags into the tag table. "
        "Idempotent — safe to re-run. Skips existing tags."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Preview how many tags would be created without writing to DB.",
        )
        parser.add_argument(
            "--database",
            default="default",
            help="Database alias to target (e.g. 'default' or 'supabase').",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        using: str = options.get("database", "default")

        self.stdout.write(
            self.style.WARNING(
                f"{'[DRY RUN] ' if dry_run else ''}Seeding tags → database: {using}"
            )
        )

        created = 0
        skipped = 0

        with transaction.atomic(using=using):
            for name, tag_type, description in TAGS:
                slug = slugify(name)
                if Tag.objects.using(using).filter(slug=slug).exists():
                    skipped += 1
                    continue

                if not dry_run:
                    Tag.objects.using(using).create(
                        name=name,
                        slug=slug,
                        tag_type=tag_type,
                        description=description,
                        is_active=True,
                        usage_count=0,
                    )
                created += 1

        status = "Would create" if dry_run else "Created"
        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Done — {status}: {created} tags | Skipped (already exist): {skipped} tags"
            )
        )
        logger.info(
            "seed_tags_complete",
            created=created,
            skipped=skipped,
            dry_run=dry_run,
            database=using,
        )
