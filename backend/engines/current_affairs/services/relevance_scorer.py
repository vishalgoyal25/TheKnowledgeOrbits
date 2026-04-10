"""
engines/current_affairs/services/relevance_scorer.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase A — A3: UPSC Relevance Scorer

Scores a CAArticle 0.0–10.0 for UPSC relevance.
Used by generate_ca_proposals to filter raw articles before proposal creation.

Scoring rules:
  +3.0  title contains a known UPSC keyword (UPSC_KEYWORDS list, 200+ terms)
  +3.0  article is semantically mappable to a knowledge_topic (embedding similarity > 0.7)
  +1.0  published_at is within the last 12 hours (recency bonus)
  -5.0  title matches BLOCKED_NOISE patterns (pure noise, zero UPSC mapping)

Threshold: score >= 5.0 → keep for proposals
           score <  5.0 → discard (logged at DEBUG level)

Notes on noise blocking:
  - "monsoon", "cyclone", "flood", "drought" → NOT blocked (Environment/Disaster)
  - "strike", "protest", "agitation"         → NOT blocked (Governance/Labour)
  - Only titles with ZERO possible UPSC mapping get -5.0
"""

import re
from datetime import timedelta
from typing import Optional

import numpy as np
import sentry_sdk
import structlog
from django.utils import timezone

from ..models import CAArticle, CATopicLink

logger = structlog.get_logger(__name__)

# ── Lazy-loaded embedding model (same as topic_linker.py) ────────────────────
_embedding_model = None


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        logger.info("relevance_scorer_loading_model")
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model


# ── UPSC Keyword list (200+ terms) ───────────────────────────────────────────
# Covers all 14 GS subjects. Presence in title → +3.0

UPSC_KEYWORDS = {
    # Indian Polity & Constitution
    "constitution", "parliament", "lok sabha", "rajya sabha", "supreme court",
    "high court", "fundamental rights", "directive principles", "preamble",
    "amendment", "president", "governor", "cabinet", "council of ministers",
    "election commission", "federalism", "judiciary", "ordinance", "bill",
    "speaker", "writ", "habeas corpus", "article 370", "article 356",
    "anti-defection", "delimitation", "panchayati raj", "municipal corporation",
    "gram sabha", "decentralization", "rti", "right to information",
    "lokpal", "lokayukta", "cag", "comptroller",

    # Governance & Social Justice
    "governance", "e-governance", "transparency", "accountability",
    "social justice", "reservation", "obc", "sc", "st", "dalit", "adivasi",
    "women empowerment", "gender equality", "disability", "minority",
    "scheme", "yojana", "mission", "programme", "policy", "welfare",
    "mgnregs", "pm-kisan", "ayushman", "pmjay", "jan dhan", "dbt",
    "aadhaar", "jam trinity", "direct benefit transfer",

    # Indian Economy
    "gdp", "inflation", "fiscal deficit", "monetary policy", "rbi",
    "budget", "tax", "gst", "fdi", "fpi", "trade", "export", "import",
    "current account", "forex", "rupee", "sebi", "npa", "bank",
    "disinvestment", "privatization", "msme", "startup", "make in india",
    "infrastructure", "investment", "capital", "economic growth",
    "unemployment", "poverty", "inequality", "frbm", "economic survey",
    "finance commission", "niti aayog", "five year plan",

    # Indian & World Geography
    "monsoon", "cyclone", "flood", "drought", "earthquake", "tsunami",
    "himalaya", "western ghats", "eastern ghats", "river", "dam",
    "glacier", "groundwater", "aquifer", "soil", "mineral",
    "agriculture", "crop", "irrigation", "watershed", "delta",
    "coastline", "island", "eez", "continental shelf",

    # Environment & Ecology
    "climate change", "global warming", "carbon", "emission", "net zero",
    "biodiversity", "wildlife", "tiger", "elephant", "wetland", "ramsar",
    "forest", "deforestation", "afforestation", "pollution", "air quality",
    "pm2.5", "ozone", "plastic", "waste", "solar", "renewable energy",
    "paris agreement", "unfccc", "cop", "ndc", "biosphere reserve",
    "national park", "wildlife sanctuary", "endangered species",
    "coral reef", "mangrove", "eia", "environmental clearance",

    # Science & Technology
    "isro", "drdo", "nasa", "space", "satellite", "rocket", "missile",
    "nuclear", "ai", "artificial intelligence", "machine learning",
    "5g", "semiconductor", "quantum", "biotechnology", "genome",
    "vaccine", "drug", "pharma", "cyber", "cybersecurity", "data",
    "internet", "digital india", "technology", "innovation", "patent",
    "research", "chandrayaan", "gaganyaan", "aditya",

    # Internal Security
    "terrorism", "naxal", "lwe", "insurgency", "border", "infiltration",
    "uapa", "afspa", "nia", "crpf", "bsf", "security forces",
    "ceasefire", "militant", "radicalization", "cyber attack",
    "fake currency", "ficn", "narcotics", "drug trafficking",

    # Disaster Management
    "disaster", "ndma", "ndrf", "sdrf", "relief", "rescue",
    "landslide", "avalanche", "fire", "chemical disaster", "sendai",
    "drr", "disaster risk reduction", "early warning",

    # International Relations
    "bilateral", "multilateral", "summit", "treaty", "agreement",
    "un", "united nations", "g20", "brics", "sco", "quad", "saarc",
    "bimstec", "asean", "wto", "imf", "world bank", "nato",
    "sanctions", "diplomacy", "foreign policy", "india-china",
    "india-pakistan", "india-us", "india-russia", "neighbourhood",

    # Modern History & Culture
    "independence", "partition", "gandhi", "nehru", "ambedkar",
    "colonial", "british", "mughal", "revolt", "freedom struggle",
    "heritage", "unesco", "monument", "archaeological", "excavation",
    "festival", "art", "culture", "classical", "folk",

    # Ethics & Social
    "corruption", "whistleblower", "probity", "integrity",
    "human rights", "civil liberties", "mob lynching", "caste violence",
    "communal", "secularism", "religious freedom",

    # Indian Society
    "population", "census", "literacy", "education", "health",
    "nutrition", "malnutrition", "infant mortality", "maternal",
    "migration", "urbanization", "slum", "housing", "sanitation",
    "swachh bharat", "open defecation", "tribal", "schedule tribe",
}

# ── Blocked noise patterns ────────────────────────────────────────────────────
# Only for titles with ZERO possible UPSC topic mapping.
# Each pattern is a compiled regex checked against the lowercased title.

BLOCKED_NOISE_PATTERNS = [
    # Cricket / sports scores
    re.compile(r"\b(ipl|cricket|match score|wicket|century|test match|odi|t20i)\b"),
    # Bollywood / celebrity
    re.compile(r"\b(bollywood|box office|film release|actor|actress|celebrity|gossip"
               r"|bigg boss|karan johar|salman|shahrukh|deepika)\b"),
    # Crime / accident (pure local, no policy angle)
    re.compile(r"\b(robbery|burglary|murder case|rape case|kidnap|car accident"
               r"|road accident|hit and run|drunk driving crash)\b"),
    # Purely personal/tabloid
    re.compile(r"\b(wedding|divorce|breakup|affair|dating|pregnancy|baby shower)\b"),
]

# Terms that CANCEL noise blocking — if present, article is never blocked
# (e.g. "cricket diplomacy", "actor turned politician", "accident compensation policy")
NOISE_CANCEL_TERMS = {
    "policy", "law", "court", "government", "ministry", "bill", "act",
    "parliament", "scheme", "rights", "compensation", "reform", "tribunal",
}


# ── Topic embeddings cache ────────────────────────────────────────────────────
# Loaded once per process — same lazy pattern as TopicLinkerService.

_topic_embeddings_cache: Optional[dict] = None


def _get_topic_embeddings() -> dict:
    """
    Returns {topic_name: np.ndarray} for all active knowledge topics.
    Cached in-process. Same approach as TopicLinkerService._get_topic_embeddings().
    """
    global _topic_embeddings_cache
    if _topic_embeddings_cache is not None:
        return _topic_embeddings_cache

    try:
        from engines.knowledge.models import Topic
        from engines.content.models import Embedding

        topics = Topic.objects.filter(is_active=True).select_related("module")
        embeddings: dict = {}

        for topic in topics:
            # Topics may have embeddings stored, or we encode the name on the fly
            try:
                emb_record = Embedding.objects.filter(
                    content_type="topic", object_id=str(topic.id)
                ).first()
                if emb_record and emb_record.vector:
                    embeddings[topic.name] = np.array(emb_record.vector)
            except Exception:
                pass

        if not embeddings:
            # Fallback: encode topic names directly
            model = _get_embedding_model()
            topic_names = [t.name for t in topics]
            if topic_names:
                vectors = model.encode(topic_names, convert_to_numpy=True)
                for name, vec in zip(topic_names, vectors):
                    embeddings[name] = vec

        _topic_embeddings_cache = embeddings
        logger.info("relevance_scorer_topic_cache_loaded", count=len(embeddings))
        return embeddings

    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        logger.error("relevance_scorer_topic_cache_failed", error=str(exc))
        return {}


# ── Scoring functions ─────────────────────────────────────────────────────────

def _score_keyword(title: str) -> float:
    """
    +3.0 if any UPSC keyword appears in the lowercased title.
    Multi-word keywords are checked as substrings.
    """
    title_lower = title.lower()
    for keyword in UPSC_KEYWORDS:
        if keyword in title_lower:
            return 3.0
    return 0.0


def _score_topic_similarity(title: str, content: str) -> float:
    """
    +3.0 if article text embeds close to any knowledge_topic (cosine > 0.7).
    Uses title + first 500 chars of content for the article vector.
    Returns 0.0 if embedding model unavailable or no topics loaded.
    """
    try:
        topic_embeddings = _get_topic_embeddings()
        if not topic_embeddings:
            return 0.0

        model = _get_embedding_model()
        text = f"{title}. {content[:500]}"
        article_vec = model.encode([text], convert_to_numpy=True)[0]
        article_norm = article_vec / (np.linalg.norm(article_vec) + 1e-10)

        best_similarity = 0.0
        for topic_vec in topic_embeddings.values():
            topic_norm = topic_vec / (np.linalg.norm(topic_vec) + 1e-10)
            similarity = float(np.dot(article_norm, topic_norm))
            if similarity > best_similarity:
                best_similarity = similarity

        return 3.0 if best_similarity >= 0.7 else 0.0

    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        logger.warning("relevance_scorer_similarity_failed", error=str(exc))
        return 0.0


def _score_recency(published_at) -> float:
    """
    +1.0 if published within last 12 hours.
    """
    if published_at and timezone.now() - published_at <= timedelta(hours=12):
        return 1.0
    return 0.0


def _score_noise_penalty(title: str) -> float:
    """
    -5.0 if title matches a BLOCKED_NOISE pattern AND contains no cancel terms.
    """
    title_lower = title.lower()

    # Check cancel terms first — if present, never penalise
    for cancel in NOISE_CANCEL_TERMS:
        if cancel in title_lower:
            return 0.0

    for pattern in BLOCKED_NOISE_PATTERNS:
        if pattern.search(title_lower):
            return -5.0

    return 0.0


# ── Public API ────────────────────────────────────────────────────────────────

class RelevanceScorerService:
    """
    Scores a CAArticle for UPSC relevance.
    Call score_article() — returns float 0.0–10.0 (clamped).
    Threshold: >= 5.0 → relevant; < 5.0 → discard.
    """

    THRESHOLD = 5.0

    @staticmethod
    def score_article(article: CAArticle) -> float:
        """
        Score a single CAArticle. Returns clamped float 0.0–10.0.
        All component scores are logged for observability.
        """
        try:
            title = article.title or ""
            content = article.content or ""

            keyword_score = _score_keyword(title)

            # Primary: use pre-computed CATopicLink records (created by scraper's
            # topic linker — faster and more reliable than re-computing embeddings).
            # Fallback to embedding similarity only when no topic links exist yet.
            # Use article._state.db to respect --database=supabase routing.
            db = article._state.db or "default"
            has_topic_links = CATopicLink.objects.using(db).filter(
                ca_chunk__ca_article=article
            ).exists()
            similarity_score = (
                3.0 if has_topic_links
                else _score_topic_similarity(title, content)
            )

            recency_score = _score_recency(article.published_at)
            noise_penalty = _score_noise_penalty(title)

            raw = keyword_score + similarity_score + recency_score + noise_penalty
            final = max(0.0, min(10.0, raw))

            logger.debug(
                "relevance_score_computed",
                article_id=str(article.id),
                title=title[:80],
                keyword=keyword_score,
                similarity=similarity_score,
                recency=recency_score,
                noise_penalty=noise_penalty,
                final=final,
                above_threshold=final >= RelevanceScorerService.THRESHOLD,
            )

            return final

        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.error(
                "relevance_scorer_error",
                article_id=str(article.id),
                error=str(exc),
            )
            return 0.0

    @staticmethod
    def is_relevant(article: CAArticle) -> bool:
        """Convenience wrapper — returns True if score >= THRESHOLD."""
        return RelevanceScorerService.score_article(article) >= RelevanceScorerService.THRESHOLD

    @staticmethod
    def filter_relevant(articles) -> list:
        """
        Filter a queryset or list of CAArticles to relevant ones only.
        Returns list of (article, score) tuples sorted by score descending.
        """
        scored = []
        for article in articles:
            score = RelevanceScorerService.score_article(article)
            if score >= RelevanceScorerService.THRESHOLD:
                scored.append((article, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        logger.info(
            "relevance_filter_complete",
            total=len(list(articles)) if hasattr(articles, '__len__') else "N/A",
            passed=len(scored),
        )
        return scored
