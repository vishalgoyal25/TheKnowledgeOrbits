# TheKnowledgeOrbits — AgenticAI Research Agent
# Full Architectural Roadmap

---

## 1. PYDANTIC RESEARCH STATE SCHEMA

```python
from typing import TypedDict, Annotated, Literal
from pydantic import BaseModel, Field
from uuid import UUID
import operator

# Sub-models for structured fields
class ResearchPlan(BaseModel):
    intent: str                          # what the user actually wants
    domain: str                          # science / politics / history / economics / general
    sub_queries: list[str]               # 3-5 focused search queries
    clarification_needed: bool = False   # triggers HITL interrupt if True
    clarification_question: str = ""     # question to ask user if above is True

class SearchResult(BaseModel):
    query: str
    source: str                          # tavily / exa / wikipedia
    url: str
    title: str
    content: str
    score: float = 0.0                   # credibility score 0.0-1.0
    cache_hit: bool = False

class Evidence(BaseModel):
    key_facts: list[str]                 # deduplicated bullet facts
    contradictions: list[str]            # conflicting claims detected
    gaps: list[str]                      # missing information identified
    sources_used: list[str]              # URLs

class VerificationResult(BaseModel):
    passed: bool
    confidence: float                    # 0.0-1.0
    weak_areas: list[str]
    retry_reason: str = ""

class ReflectionResult(BaseModel):
    approved: bool
    issues_found: list[str]
    suggested_improvements: list[str]

class ReportSection(BaseModel):
    heading: str
    content: str

class FinalReport(BaseModel):
    title: str
    summary: str                         # 2-3 line executive summary
    sections: list[ReportSection]
    key_takeaways: list[str]
    sources: list[dict]                  # [{title, url, credibility_score}]
    confidence_score: float              # 0.0-1.0 (derived from DeepEval)
    word_count: int
    domain: str

class ExecutionMetadata(BaseModel):
    session_id: str
    langfuse_trace_id: str = ""
    total_tokens: int = 0
    total_llm_calls: int = 0
    groq_calls: int = 0
    cerebras_calls: int = 0
    tavily_calls: int = 0
    cache_hits: int = 0
    total_duration_ms: int = 0
    models_used: list[str] = []

# Main LangGraph State
class ResearchState(TypedDict):
    # --- Input ---
    session_id: str
    query: str
    user_id: str | None                  # None = guest
    user_clarification: str              # filled if HITL interrupt occurred

    # --- Planning ---
    research_plan: ResearchPlan | None

    # --- Search ---
    search_results: Annotated[list[SearchResult], operator.add]  # parallel merge
    search_cache_hit: bool

    # --- Research ---
    evidence: Evidence | None

    # --- Verification ---
    verification: VerificationResult | None
    retry_count: int                     # max 1

    # --- Report ---
    report: FinalReport | None
    report_md: str                       # final markdown string

    # --- Reflection ---
    reflection: ReflectionResult | None

    # --- Output Safety ---
    output_approved: bool

    # --- Observability ---
    execution_metadata: ExecutionMetadata
    node_history: Annotated[list[str], operator.add]  # ordered list of completed nodes
    deepeval_scores: dict                # hallucination, faithfulness, relevance, completeness
```

---

## 2. LANGGRAPH NODE NETWORK + ROUTING LOGIC

### Graph Definition (workflow.py)

```
StateGraph nodes:
  supervisor          → always runs first
  planner             → always runs after supervisor
  hitl_interrupt      → conditional: only if research_plan.clarification_needed=True
  search              → parallel fanout via Send() API (one Send per sub_query)
  research            → runs after all parallel searches complete
  verification        → runs after research
  report_generator    → runs after verification passes (or retry exhausted)
  reflection          → runs after report_generator
  output_guardrail    → always runs last before END
  END

Edges:
  supervisor          → planner (always)
  planner             → hitl_interrupt (if clarification_needed) OR search (direct)
  hitl_interrupt      → search (after user responds)
  search              → research (after all parallel branches complete)
  research            → verification (always)
  verification        → report_generator (if passed OR retry_count >= 1)
                     → search (if not passed AND retry_count < 1) [RETRY LOOP]
  report_generator    → reflection (always)
  reflection          → output_guardrail (if approved)
                     → research (if not approved AND retry_count < 1) [REFLECTION RETRY]
  output_guardrail    → END (always)
```

### Conditional Edge Functions (edges.py)

```python
def route_after_planner(state: ResearchState) -> str:
    if state["research_plan"].clarification_needed:
        return "hitl_interrupt"
    return "search"

def route_after_verification(state: ResearchState) -> str:
    v = state["verification"]
    if v.passed:
        return "report_generator"
    if state["retry_count"] >= 1:
        return "report_generator"   # exhausted retries — proceed anyway
    return "search"                 # retry: back to search

def route_after_reflection(state: ResearchState) -> str:
    r = state["reflection"]
    if r.approved:
        return "output_guardrail"
    if state["retry_count"] >= 1:
        return "output_guardrail"   # exhausted — proceed with warning
    return "research"               # send back for re-synthesis

# Parallel search via Send API:
def fanout_search(state: ResearchState) -> list[Send]:
    return [
        Send("search_node", {"query": q, "session_id": state["session_id"]})
        for q in state["research_plan"].sub_queries
    ]
```

---

## 3. MODEL ROUTING (model_router_service.py)

```python
MODEL_ASSIGNMENTS = {
    "supervisor":         {"provider": "cerebras", "model": "llama-3.3-70b"},   # fast, simple
    "planner":            {"provider": "groq",     "model": "llama-3.3-70b-versatile"},
    "research":           {"provider": "groq",     "model": "llama-3.3-70b-versatile"},
    "verification":       {"provider": "groq",     "model": "llama-3.3-70b-versatile"},
    "report_generator":   {"provider": "groq",     "model": "llama-3.3-70b-versatile"},
    "reflection":         {"provider": "cerebras", "model": "llama-3.3-70b"},   # fast self-check
    "concept_generation": {"provider": "groq",     "model": "llama-3.3-70b-versatile"},
}
```

---

## 4. GLOBAL RETRY / BACKOFF WRAPPER

```python
# services/groq_client.py — wraps ALL LLM calls in research_agent
import time, structlog
from functools import wraps

log = structlog.get_logger()

GROQ_RPM_LIMIT = 30          # Groq free: 30 req/min
CEREBRAS_RPM_LIMIT = 60      # Cerebras free: 60 req/min
RETRY_DELAYS = [5, 15, 30]   # seconds — exponential-ish backoff

def llm_call_with_retry(provider: str, model: str, messages: list, **kwargs):
    """
    Global wrapper for all LLM calls in research_agent.
    - Enforces per-provider RPM via token bucket
    - Retries on 429 (rate limit) and 503 (unavailable)
    - Falls back provider on repeated failure: groq → cerebras → groq
    - Instruments Langfuse span automatically
    """
    for attempt, delay in enumerate(RETRY_DELAYS):
        try:
            _acquire_token(provider)                     # token bucket gate
            response = _call_provider(provider, model, messages, **kwargs)
            _record_langfuse_span(provider, model, response)
            return response
        except RateLimitError:
            log.warning("llm_rate_limited", provider=provider, attempt=attempt, retry_in=delay)
            time.sleep(delay)
        except ProviderUnavailableError:
            provider = _fallback_provider(provider)      # switch to other provider
            log.warning("llm_provider_switched", new_provider=provider)
    raise LLMExhaustedError("All LLM retry attempts failed")
```

### Token Bucket (rate_limiter_service.py)

```python
class TokenBucket:
    """
    Custom token bucket per LLM provider.
    Prevents hitting free-tier RPM limits across parallel agent calls.
    """
    def __init__(self, rpm: int):
        self.capacity = rpm
        self.tokens = rpm
        self.refill_rate = rpm / 60.0    # tokens per second
        self.last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, timeout: float = 30.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                self._refill()
                if self.tokens >= 1:
                    self.tokens -= 1
                    return True
            time.sleep(0.5)
        return False

BUCKETS = {
    "groq":     TokenBucket(rpm=GROQ_RPM_LIMIT),
    "cerebras": TokenBucket(rpm=CEREBRAS_RPM_LIMIT),
}
```

---

## 5. LANGFUSE TRACE HOOKS (langfuse_service.py)

```python
# Pattern: every agent node wraps its LLM calls in a Langfuse span

from langfuse import Langfuse
langfuse = Langfuse()   # reads LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST from env

class LangfuseService:

    @staticmethod
    def start_trace(session_id: str, query: str, user_id: str | None) -> str:
        trace = langfuse.trace(
            name="research_agent_workflow",
            session_id=session_id,
            input={"query": query},
            metadata={"user_id": user_id or "guest"},
        )
        return trace.id

    @staticmethod
    def agent_span(trace_id: str, agent_name: str, model: str, prompt: str, response: str, tokens: dict):
        langfuse.span(
            trace_id=trace_id,
            name=agent_name,
            input={"prompt": prompt},
            output={"response": response},
            metadata={"model": model, "tokens": tokens},
        )

    @staticmethod
    def end_trace(trace_id: str, report_confidence: float, total_tokens: int, duration_ms: int):
        langfuse.score(
            trace_id=trace_id,
            name="confidence_score",
            value=report_confidence,
        )
        langfuse.trace(
            id=trace_id,
            output={"confidence": report_confidence, "total_tokens": total_tokens},
            metadata={"duration_ms": duration_ms},
        )

    @staticmethod
    def get_prompt(prompt_name: str, version: int | None = None) -> str:
        """Fetch versioned prompt from Langfuse. Falls back to local if unavailable."""
        try:
            p = langfuse.get_prompt(prompt_name, version=version)
            return p.compile()
        except Exception:
            return _LOCAL_PROMPT_FALLBACKS[prompt_name]
```

---

## 6. DEEPEVAL AUTOMATION HOOKS (evaluation_service.py)

```python
from deepeval import evaluate
from deepeval.metrics import (
    HallucinationMetric,
    FaithfulnessMetric,
    AnswerRelevancyMetric,
    ContextualRecallMetric,
)
from deepeval.test_case import LLMTestCase

class EvaluationService:

    @staticmethod
    def evaluate_report(query: str, report_md: str, search_results: list) -> dict:
        """
        Runs DeepEval locally after every report generation.
        Returns scores dict saved to evaluation_result table.
        """
        context = [r.content for r in search_results[:5]]
        test_case = LLMTestCase(
            input=query,
            actual_output=report_md,
            retrieval_context=context,
        )

        metrics = [
            HallucinationMetric(threshold=0.3),
            FaithfulnessMetric(threshold=0.7),
            AnswerRelevancyMetric(threshold=0.7),
            ContextualRecallMetric(threshold=0.6),
        ]

        results = evaluate([test_case], metrics)

        scores = {
            "hallucination": results[0].metrics_data[0].score,
            "faithfulness":  results[0].metrics_data[1].score,
            "relevance":     results[0].metrics_data[2].score,
            "completeness":  results[0].metrics_data[3].score,
        }
        scores["overall"] = sum(scores.values()) / 4
        return scores

    @staticmethod
    def compute_confidence_pct(scores: dict) -> float:
        """Derives user-facing confidence % from raw DeepEval scores."""
        weights = {"faithfulness": 0.4, "relevance": 0.3, "completeness": 0.2, "hallucination_inv": 0.1}
        hallucination_inv = 1.0 - scores.get("hallucination", 0.5)
        confidence = (
            scores["faithfulness"]  * weights["faithfulness"] +
            scores["relevance"]     * weights["relevance"] +
            scores["completeness"]  * weights["completeness"] +
            hallucination_inv       * weights["hallucination_inv"]
        )
        return round(confidence * 100, 1)   # e.g. 82.4
```

---

## 7. SSE EVENT SCHEMA

```python
# All events emitted by sse_service.py during graph execution

SSE_EVENTS = {
    "workflow_started":    {"session_id", "query", "timestamp"},
    "node_started":        {"node", "session_id", "timestamp"},
    "node_completed":      {"node", "session_id", "summary", "duration_ms", "timestamp"},
    "node_failed":         {"node", "session_id", "error", "timestamp"},
    "retry_started":       {"node", "session_id", "retry_count", "reason", "timestamp"},
    "hitl_interrupt":      {"session_id", "question", "timestamp"},          # Planner needs clarification
    "search_progress":     {"session_id", "query", "source", "result_count", "cache_hit"},
    "workflow_completed":  {"session_id", "report_id", "confidence_pct", "duration_ms"},
    "workflow_failed":     {"session_id", "error", "timestamp"},
}

# SSE format:
# data: {"event": "node_started", "node": "planner", "session_id": "abc123", "timestamp": "..."}
```

---

## 8. CIRCUIT BREAKER — SEARCH FALLBACK (circuit_breaker_service.py)

```python
class CircuitBreaker:
    CHAIN = ["tavily", "exa", "wikipedia"]

    @classmethod
    def search(cls, query: str) -> list[dict]:
        for source in cls.CHAIN:
            try:
                result = cls._call(source, query)
                if result:
                    log.info("search_success", source=source, query=query)
                    return result, source
            except Exception as e:
                log.warning("search_source_failed", source=source, error=str(e))
                continue
        log.error("all_search_sources_failed", query=query)
        return [], "none"
```

---

## 9. REDIS CACHE STRATEGY

```python
# Namespace: research:cache:*
# Key construction:
import hashlib

def make_cache_key(query: str) -> str:
    normalized = query.lower().strip()
    return f"research:cache:report:{hashlib.sha256(normalized.encode()).hexdigest()[:16]}"

def make_search_cache_key(query: str) -> str:
    normalized = query.lower().strip()
    return f"research:cache:search:{hashlib.sha256(normalized.encode()).hexdigest()[:16]}"

# TTLs:
SEARCH_CACHE_TTL  = 6 * 3600    # 6 hours — news changes
REPORT_CACHE_TTL  = 24 * 3600   # 24 hours — stable research
MEMORY_TTL        = 7 * 24 * 3600  # 7 days — user preference memory

# Guest users: cache keyed to session cookie (no user_id)
# Logged-in: cache keyed to normalized query only (shared across users for same query)
```

---

## 10. RATE LIMITING STRATEGY (per-user, per-day)

```python
# Key: research:ratelimit:{user_ip_or_user_id}:{date}
# Guest: 3 queries/day by IP
# Logged-in: unlimited

def check_rate_limit(user_id: str | None, ip: str) -> bool:
    if user_id:
        return True   # logged-in: unlimited
    key = f"research:ratelimit:{ip}:{date.today().isoformat()}"
    count = redis.incr(key)
    if count == 1:
        redis.expire(key, 86400)   # reset at midnight
    return count <= 3

# Returns 429 with: {"error": "Guest limit reached", "limit": 3, "reset": "midnight UTC", "hint": "Login for unlimited access"}
```

---

## 11. COMPLETE FILE MAP

### Backend: engines/research_agent/
```
__init__.py
apps.py
admin.py
urls.py
models.py
serializers.py
views.py
permissions.py
exceptions.py
health.py

agents/
  __init__.py
  base_agent.py
  supervisor_agent.py
  planner_agent.py
  search_agent.py
  research_agent.py
  verification_agent.py
  report_generator_agent.py
  reflection_agent.py

graph/
  __init__.py
  state.py
  workflow.py
  edges.py
  checkpointer.py

tools/
  __init__.py
  tool_registry.py
  search_tool.py
  exa_tool.py
  wiki_tool.py
  calculator_tool.py
  domain_classifier.py
  credibility_scorer.py

services/
  __init__.py
  orchestrator_service.py
  sse_service.py
  cache_service.py
  langfuse_service.py
  evaluation_service.py
  report_service.py
  export_service.py
  model_router_service.py
  guardrails_service.py
  memory_service.py
  prompt_service.py
  circuit_breaker_service.py
  rate_limiter_service.py
  groq_client.py

prompts/
  __init__.py
  system_prompts.py
  planner_prompts.py
  research_prompts.py
  verification_prompts.py
  report_prompts.py
  reflection_prompts.py
  guardrails_prompts.py

management/
  __init__.py
  commands/
    __init__.py
    test_research_agent.py
    run_evaluation_suite.py
    warm_agent_cache.py
    export_langfuse_metrics.py

migrations/
  __init__.py
  0001_initial.py

tests/
  __init__.py
  test_agents.py
  test_graph.py
  test_tools.py
  test_services.py
  test_views.py
  test_evaluation.py
  test_sse.py
  test_guardrails.py
  test_cache.py
```

### Frontend: frontend/src/
```
app/research_agent/
  page.tsx
  layout.tsx
  [session_id]/
    page.tsx

app/research-history/
  page.tsx

components/research_agent/
  research-input.tsx
  voice-input.tsx
  workflow-graph.tsx
  agent-node.tsx
  agent-edge.tsx
  parallel-search-indicator.tsx
  retry-indicator.tsx
  hitl-dialog.tsx
  research-status-panel.tsx
  thinking-stream.tsx
  report-viewer.tsx
  source-citations.tsx
  confidence-badge.tsx
  eval-scores-panel.tsx
  model-info-tooltip.tsx
  memory-panel.tsx
  domain-badge.tsx
  export-button.tsx
  share-button.tsx
  session-card.tsx
  session-history.tsx
  homepage-widget.tsx

lib/api/research.ts
lib/hooks/use-research-sse.ts
lib/hooks/use-workflow-state.ts
lib/hooks/use-voice-input.ts
lib/types/research.ts
lib/utils/research-helpers.ts
```

### DevOps:
```
Dockerfile.research-agent
backend/requirements/research-agent-additions.txt   (notes which lines go into which .txt)
```

---

## 12. DEPLOYMENT ARCHITECTURE

```
Render (backend):
  - research_agent engine runs inside existing Django app
  - No separate service needed — single Render web service
  - Environment vars: add TAVILY_API_KEY, LANGFUSE_* to Render dashboard
  - Redis: existing Redis add-on on Render used (new key namespace)
  - Docker: Dockerfile.research-agent used by Render build

Vercel (frontend):
  - /research route auto-deployed with Next.js
  - SSE: works with Vercel — no special config (standard fetch streaming)
  - Environment vars: add NEXT_PUBLIC_API_URL (already exists)

Supabase:
  - 5 new tables added via Django migrate --database=supabase
  - No structural changes to existing tables

Langfuse:
  - cloud.langfuse.com (free tier: 50k observations/month)
  - Traces from both local dev and production point to same dashboard
  - Separate projects: "TKO-Dev" and "TKO-Prod"

DeepEval:
  - Runs locally inside Django (same process)
  - No external API — completely free
  - Uses Groq as judge model (already have key)
```

---

## 13. LEARNING REFERENCE (What each component teaches)

| Component | Concept learned |
|---|---|
| ResearchState TypedDict | LangGraph stateful graph design |
| graph/workflow.py | Multi-agent orchestration, node composition |
| graph/edges.py | Conditional routing, retry loops |
| graph/checkpointer.py | State persistence, resumable workflows |
| tools/search_tool.py | Tool calling in agentic systems |
| services/circuit_breaker_service.py | Production reliability, graceful degradation |
| services/groq_client.py | LLM API management, rate limits, retries |
| services/rate_limiter_service.py | Token bucket algorithm, concurrent access |
| services/langfuse_service.py | LLMOps: tracing, prompt versioning, cost tracking |
| services/evaluation_service.py | AI evaluation: hallucination detection, faithfulness |
| services/sse_service.py | Real-time server-to-client streaming |
| services/model_router_service.py | Multi-LLM routing, cost optimization |
| services/guardrails_service.py | AI safety, prompt injection defense |
| services/memory_service.py | Agent memory: short-term + long-term |
| graph/state.py (Annotated + operator.add) | Parallel agent output merging |
| workflow.py (Send API) | Parallel agent execution in LangGraph |
| agents/reflection_agent.py | Self-correcting agents, self-critique pattern |
| agents/verification_agent.py | Quality gates in agentic pipelines |
| React Flow + SSE hook | Live agentic workflow visualization |
| Dockerfile.research-agent | AI system containerization |
