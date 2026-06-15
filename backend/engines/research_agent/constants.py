"""
engines/research_agent/constants.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Centralized constants for Research Agent engine.
All magic numbers / strings live here — never inline.
"""

# ── Rate Limits ────────────────────────────────────────────────────────────────
PUBLIC_DAILY_LIMIT = 3  # anonymous users: 3 queries/day
GROQ_REQUESTS_PER_MINUTE = 30  # global Groq RPM cap (Redis-backed, not per-user)
CEREBRAS_REQUESTS_PER_MINUTE = 60

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
