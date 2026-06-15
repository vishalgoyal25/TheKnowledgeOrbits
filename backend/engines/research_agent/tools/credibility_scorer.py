"""
engines/research_agent/tools/credibility_scorer.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CredibilityScorer — scores source URLs by domain authority.

Rule-based, no API call. Scores 0.0–1.0:
  0.9–1.0 → official government, UN, RBI, PIB, known authorities
  0.7–0.89 → established news, academia, reputed think tanks
  0.5–0.69 → general reference (Wikipedia, encyclopedias)
  0.3–0.49 → blogs, unknown domains
  0.1–0.29 → social media, forums, aggregators

Used by Research Agent to:
  - Sort sources before passing to LLM (highest credibility first)
  - Filter out sources below threshold (default 0.3)
  - Add credibility_score to each source dict for report citations
"""

from __future__ import annotations

import re
import structlog

logger = structlog.get_logger(__name__)

DEFAULT_SCORE = 0.4  # unknown domain
THRESHOLD_MINIMUM = 0.3  # sources below this are dropped

# ── Tier 1: Official government + authoritative bodies (0.95) ─────────────
_TIER_1: set[str] = {
    # Indian government
    "gov.in",
    "nic.in",
    "pib.gov.in",
    "mygov.in",
    "india.gov.in",
    "rbi.org.in",
    "sebi.gov.in",
    "irdai.gov.in",
    "trai.gov.in",
    "mea.gov.in",
    "pmindia.gov.in",
    "president.gov.in",
    "rajyasabha.nic.in",
    "loksabha.nic.in",
    "sansad.nic.in",
    "supremecourt.gov.in",
    "ncert.nic.in",
    "upsc.gov.in",
    "mospi.gov.in",
    "indiabudget.gov.in",
    "finmin.gov.in",
    # International authorities
    "un.org",
    "who.int",
    "worldbank.org",
    "imf.org",
    "oecd.org",
    "wto.org",
    "unicef.org",
    "undp.org",
    "fao.org",
    "isro.gov.in",
    "drdo.gov.in",
    "csir.res.in",
}

# ── Tier 2: Established news + academia + think tanks (0.80) ─────────────
_TIER_2: set[str] = {
    # Indian news
    "thehindu.com",
    "indianexpress.com",
    "hindustantimes.com",
    "livemint.com",
    "economictimes.indiatimes.com",
    "businessstandard.com",
    "timesofindia.indiatimes.com",
    "ndtv.com",
    "pib.nic.in",
    "downtoearth.org.in",
    "scroll.in",
    "thewire.in",
    # International news
    "reuters.com",
    "bbc.com",
    "bbc.co.uk",
    "apnews.com",
    "theguardian.com",
    "nytimes.com",
    "ft.com",
    "bloomberg.com",
    # Academia
    "jstor.org",
    "scholar.google.com",
    "researchgate.net",
    "academia.edu",
    "nature.com",
    "sciencedirect.com",
    "pubmed.ncbi.nlm.nih.gov",
    # Think tanks
    "orfonline.org",
    "idsa.in",
    "cprindia.org",
    "prsindia.org",
    "brookings.edu",
    "cfr.org",
    "carnegieendowment.org",
}

# ── Tier 3: General reference (0.55) ─────────────────────────────────────
_TIER_3: set[str] = {
    "wikipedia.org",
    "britannica.com",
    "encyclopedia.com",
    "merriam-webster.com",
    "oxfordreference.com",
}

# ── Tier 4: Social media / forums / aggregators (0.15) ───────────────────
_TIER_4_PATTERNS: list[str] = [
    "twitter.com",
    "x.com",
    "facebook.com",
    "instagram.com",
    "reddit.com",
    "quora.com",
    "medium.com",
    "substack.com",
    "blogspot.com",
    "wordpress.com",
    "tumblr.com",
    "youtube.com",
    "youtu.be",
]


class CredibilityScorer:
    """
    Scores source URLs by domain authority.
    No API call — pure rule-based lookup against known domain tiers.
    """

    def score(self, url: str) -> float:
        """
        Score a single URL.

        Args:
            url: Full URL string e.g. "https://rbi.org.in/Scripts/..."

        Returns:
            Float 0.0–1.0. Higher = more credible.
        """
        if not url:
            return DEFAULT_SCORE

        domain = self._extract_domain(url)

        # Exact Tier 1 match (or subdomain of Tier 1)
        for t1 in _TIER_1:
            if domain == t1 or domain.endswith(f".{t1}"):
                return 0.95

        # Exact Tier 2 match
        for t2 in _TIER_2:
            if domain == t2 or domain.endswith(f".{t2}"):
                return 0.80

        # Exact Tier 3 match
        for t3 in _TIER_3:
            if domain == t3 or domain.endswith(f".{t3}"):
                return 0.55

        # Tier 4 pattern match (social/blogs)
        for pattern in _TIER_4_PATTERNS:
            if pattern in domain:
                return 0.15

        # .gov or .edu TLD anywhere → treat as authoritative
        if domain.endswith(".gov") or domain.endswith(".edu"):
            return 0.90

        # .ac.in or .edu.in → Indian academic institutions
        if domain.endswith(".ac.in") or domain.endswith(".edu.in"):
            return 0.82

        return DEFAULT_SCORE

    def score_sources(self, sources: list[dict]) -> list[dict]:
        """
        Adds 'credibility_score' field to each source dict,
        filters out sources below THRESHOLD_MINIMUM,
        and returns list sorted highest score first.

        Called by Research Agent before passing sources to LLM —
        ensures LLM sees best sources first within its context window.

        Args:
            sources: List of {url, title, content, score, source} dicts

        Returns:
            Filtered + sorted list with added credibility_score field.
        """
        scored = []
        for source in sources:
            url = source.get("url", "")
            credibility = self.score(url)
            enriched = dict(source)
            enriched["credibility_score"] = credibility

            if credibility >= THRESHOLD_MINIMUM:
                scored.append(enriched)
            else:
                logger.debug(
                    "research_agent.credibility.source_filtered",
                    url=url,
                    score=credibility,
                )

        scored.sort(key=lambda s: s["credibility_score"], reverse=True)

        logger.info(
            "research_agent.credibility.scoring_complete",
            total_in=len(sources),
            total_out=len(scored),
            filtered=len(sources) - len(scored),
        )

        return scored

    def _extract_domain(self, url: str) -> str:
        """Extract bare domain from URL, strip www. prefix."""
        url = url.lower().strip()
        # Strip scheme
        url = re.sub(r"^https?://", "", url)
        # Strip www.
        url = re.sub(r"^www\.", "", url)
        # Keep only domain part (before first /)
        domain = url.split("/")[0].split("?")[0].split("#")[0]
        return domain
