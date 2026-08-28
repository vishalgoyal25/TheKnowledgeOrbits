"""
engines/research_agent/constants.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Centralized constants for Research Agent engine.
All magic numbers / strings live here — never inline.
"""

# ── Rate Limits ────────────────────────────────────────────────────────────────
PUBLIC_DAILY_LIMIT = 3  # anonymous users: 3 queries/day
# Global per-provider RPM caps (Redis-backed, pool-wide — NOT per user, NOT per key).
# These are pre-emptive: hitting the cap makes the pool fail over to the next
# provider instead of earning an upstream 429.
GROQ_REQUESTS_PER_MINUTE = 30
MISTRAL_REQUESTS_PER_MINUTE = 4  # free tier ≈ 2 RPM per key; deliberately conservative
OPENROUTER_REQUESTS_PER_MINUTE = 15  # free tier ≈ 20 RPM, but only ~50 req/day/account
CEREBRAS_REQUESTS_PER_MINUTE = 60  # retained — provider disabled since 2026-08-19 (402)

# ── LangGraph ─────────────────────────────────────────────────────────────────
MAX_SEARCH_QUERIES = 3  # Planner generates max 3 sub-queries
MAX_VERIFICATION_RETRIES = 1  # max 1 retry loop (saves ~30% API calls)
MAX_REFLECTION_PASSES = 1  # Reflection agent iterates max once

# ── LLM Token Budgets (Opt #3) ────────────────────────────────────────────────
MAX_TOKENS_SUPERVISOR = 512
MAX_TOKENS_PLANNER = 1024
MAX_TOKENS_RESEARCH = 1500  # richer synthesis from deeper sources
MAX_TOKENS_VERIFICATION = 1024
MAX_TOKENS_REPORT_GENERATOR = 2048  # longer, more complete reports (~800-1000 words)
MAX_TOKENS_REFLECTION = 512
MAX_TOKENS_SUMMARY = 600  # executive summary (Opt #2)

# Force valid JSON output for structured-output agents (planner/research/
# verification/reflection). Both Groq and Cerebras support it — this is what
# eliminates the bad-JSON parse failures on gpt-oss-120b.
JSON_RESPONSE_FORMAT = {"type": "json_object"}

# ── SSE ────────────────────────────────────────────────────────────────────────
SSE_HEARTBEAT_INTERVAL = 15  # seconds — prevents Render proxy timeout (Risk #6)
SSE_STREAM_RETRY_MS = 3000  # client reconnect delay in ms

# ── Cache ─────────────────────────────────────────────────────────────────────
QUERY_CACHE_TTL = 86400  # 24 hours (in seconds)
SESSION_CACHE_PREFIX = "ra:session:"
QUERY_HASH_PREFIX = "ra:query:"


# ── Session States ─────────────────────────────────────────────────────────────
class SessionStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ── Session Channels ──────────────────────────────────────────────────────────
# Which transport a session arrived through. WEB is the default for every
# existing row and every browser query — the field exists so non-web traffic is
# attributable in the ops tables and in Langfuse (FEATURE_WHATSAPP.md §5.2).
#
# THE SINGLE SOURCE OF TRUTH for channel names. Adding a platform means one
# entry here, which cascades to:
#   · ResearchSession.channel choices + the ra_session_channel_valid constraint
#   · channels/core/constants.py → DeliveryChannel (derived, minus WEB)
#     → the ra_delivery_channel_valid constraint
#   · the registry, which refuses an adapter whose name is not listed here
#
# Each addition needs one small migration to widen those two CHECK constraints
# — the documented exception in FEATURE_TELEGRAM.md §12.7. Nothing else changes.
#
# WEB is special: it is an attribution label, NOT an adapter. Browser queries
# keep their existing QueryView → orchestrator → SSE path and never route
# through channels/.
class SessionChannel:
    WEB = "web"
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    ALL = (WEB, WHATSAPP, TELEGRAM)


# ── Agent Names ────────────────────────────────────────────────────────────────
class AgentName:
    SUPERVISOR = "supervisor"
    PLANNER = "planner"
    SEARCH = "search"
    RESEARCH = "research"
    VERIFICATION = "verification"
    REPORT_GENERATOR = "report_generator"
    REFLECTION = "reflection"
    SUMMARY_GENERATOR = "summary_generator"


# ── SSE Event Types ───────────────────────────────────────────────────────────
class SSEEvent:
    WORKFLOW_STARTED = "workflow_started"
    NODE_STARTED = "node_started"
    NODE_COMPLETED = "node_completed"
    REPORT_TOKEN = "report_token"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    WORKFLOW_CANCELLED = "workflow_cancelled"
    HEARTBEAT = "heartbeat"


# ── Export Formats ────────────────────────────────────────────────────────────
class ExportFormat:
    PDF = "pdf"
    MARKDOWN = "md"
