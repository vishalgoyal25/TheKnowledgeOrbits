"""
engines/research_agent/tools/domain_classifier.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DomainClassifier — maps a research query to one of 6 fixed UPSC domains.

Domains (hardcoded constants — never change at runtime):
  polity         → constitution, parliament, judiciary, governance, rights
  economy        → GDP, budget, fiscal, inflation, trade, RBI, banking
  geography      → rivers, climate, states, mountains, monsoon, soil
  science        → physics, chemistry, biology, space, technology, ISRO
  current_affairs → recent events, news, 2024, 2025, latest, recently
  general        → fallback when no domain matches clearly

Why keyword-based (not LLM)?
  - Zero latency — runs in microseconds
  - Zero API cost — no Groq/Cerebras call
  - Deterministic — same query → same domain every time
  - Sufficient for routing — Planner only needs a broad signal

The domain label is stored in ResearchState.domain and used by:
  - Search Agent: to weight Tavily query parameters
  - Report Generator: to pick the right report template/structure
"""

from __future__ import annotations

import re
import structlog

logger = structlog.get_logger(__name__)

# Valid domain constants — matches what ResearchState.domain accepts
DOMAIN_POLITY = "polity"
DOMAIN_ECONOMY = "economy"
DOMAIN_GEOGRAPHY = "geography"
DOMAIN_SCIENCE = "science"
DOMAIN_CURRENT_AFFAIRS = "current_affairs"
DOMAIN_GENERAL = "general"

ALL_DOMAINS = [
    DOMAIN_POLITY,
    DOMAIN_ECONOMY,
    DOMAIN_GEOGRAPHY,
    DOMAIN_SCIENCE,
    DOMAIN_CURRENT_AFFAIRS,
    DOMAIN_GENERAL,
]

# Keyword sets per domain — order matters (checked top to bottom, first match wins)
# More specific domains listed before broader ones
_DOMAIN_KEYWORDS: list[tuple[str, list[str]]] = [
    (
        DOMAIN_CURRENT_AFFAIRS,
        [
            "2024",
            "2025",
            "2026",
            "recent",
            "recently",
            "latest",
            "current",
            "today",
            "this year",
            "last year",
            "this month",
            "news",
            "update",
            "new policy",
            "new scheme",
            "new law",
            "amendment",
            "budget 2",
            "election",
            "appointed",
            "inaugurated",
            "launched",
        ],
    ),
    (
        DOMAIN_ECONOMY,
        [
            "gdp",
            "economy",
            "economic",
            "fiscal",
            "inflation",
            "deflation",
            "budget",
            "tax",
            "gst",
            "rbi",
            "bank",
            "banking",
            "finance",
            "trade",
            "export",
            "import",
            "fdi",
            "revenue",
            "deficit",
            "debt",
            "monetary",
            "repo rate",
            "sebi",
            "stock",
            "market",
            "poverty",
            "unemployment",
            "per capita",
            "growth rate",
            "oecd",
            "imf",
            "world bank",
        ],
    ),
    (
        DOMAIN_POLITY,
        [
            "constitution",
            "constitutional",
            "article",
            "amendment",
            "parliament",
            "lok sabha",
            "rajya sabha",
            "president",
            "prime minister",
            "governor",
            "judiciary",
            "supreme court",
            "high court",
            "fundamental rights",
            "directive principles",
            "election commission",
            "federalism",
            "panchayat",
            "municipality",
            "bill",
            "act",
            "legislation",
            "ordinance",
            "tribunal",
            "upsc",
            "ias",
            "governance",
            "policy",
            "scheme",
            "ministry",
        ],
    ),
    (
        DOMAIN_GEOGRAPHY,
        [
            "geography",
            "river",
            "mountain",
            "plateau",
            "plain",
            "delta",
            "climate",
            "monsoon",
            "rainfall",
            "soil",
            "forest",
            "biodiversity",
            "state",
            "district",
            "capital",
            "border",
            "ocean",
            "sea",
            "lake",
            "island",
            "peninsula",
            "latitude",
            "longitude",
            "national park",
            "wildlife",
            "sanctuary",
            "dam",
            "irrigation",
            "mineral",
            "rock",
        ],
    ),
    (
        DOMAIN_SCIENCE,
        [
            "science",
            "physics",
            "chemistry",
            "biology",
            "technology",
            "space",
            "isro",
            "nasa",
            "satellite",
            "rocket",
            "missile",
            "nuclear",
            "atomic",
            "dna",
            "gene",
            "cell",
            "virus",
            "bacteria",
            "disease",
            "vaccine",
            "medicine",
            "invention",
            "discovery",
            "ai",
            "artificial intelligence",
            "computer",
            "internet",
            "quantum",
            "energy",
            "solar",
            "wind",
            "electric",
            "environment",
            "pollution",
            "climate change",
            "global warming",
        ],
    ),
]


class DomainClassifier:
    """
    Keyword-based domain classifier. Runs in microseconds.
    Returns one of the 6 fixed domain constants above.
    """

    def classify(self, query: str) -> str:
        """
        Classify a research query into a UPSC domain.

        Args:
            query: The raw research question from the user.

        Returns:
            One of: polity, economy, geography, science, current_affairs, general
        """
        normalized = self._normalize(query)

        for domain, keywords in _DOMAIN_KEYWORDS:
            for keyword in keywords:
                if keyword in normalized:
                    logger.debug(
                        "research_agent.domain_classifier.matched",
                        domain=domain,
                        keyword=keyword,
                        query=query[:80],
                    )
                    return domain

        logger.debug(
            "research_agent.domain_classifier.fallback",
            domain=DOMAIN_GENERAL,
            query=query[:80],
        )
        return DOMAIN_GENERAL

    def _normalize(self, text: str) -> str:
        """Lowercase + collapse whitespace for reliable keyword matching."""
        text = text.lower()
        text = re.sub(r"\s+", " ", text).strip()
        return text
