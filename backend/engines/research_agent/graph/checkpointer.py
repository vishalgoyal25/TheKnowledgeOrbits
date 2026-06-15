"""
engines/research_agent/graph/checkpointer.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LangGraph checkpointer setup — with graceful backend fallback.

What is checkpointing?
  LangGraph saves the full ResearchState after EVERY node completes. If the
  worker crashes mid-workflow, the next run can resume from the last checkpoint
  instead of starting over. thread_id = session_id (one thread per session).

TWO BACKENDS, automatic selection:
  1. PostgreSQL (PREFERRED, production) — survives worker/process restarts, so a
     crashed Celery task can resume. Requires the optional pip package
     `langgraph-checkpoint-postgres` (+ psycopg). Its OWN tables
     (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`,
     `checkpoint_migrations`) are auto-created by .setup() — separate from our
     Django `ra_*` tables and unrelated to `ra_state_snapshot`.
  2. In-memory (FALLBACK, local/dev) — ships with core `langgraph`. Works fine
     for a single synchronous run, but does NOT survive a process restart.

If the Postgres package isn't installed (or the connection fails), we log a
warning and fall back to in-memory so the pipeline still runs. To get true
crash-recovery in production, add `langgraph-checkpoint-postgres` to
requirements (deployment concern, Phase 13).
"""

from __future__ import annotations

import structlog
from django.conf import settings

logger = structlog.get_logger(__name__)

# Module-level singleton — one checkpointer instance per process.
_checkpointer = None


def get_checkpointer():
    """
    Returns the checkpointer singleton. Built once on first call.

    Tries the PostgreSQL backend first; on any failure (package missing,
    connection error) falls back to the in-memory saver so testing and local
    dev are never blocked.

    Called by: graph.py _build_graph()
    """
    global _checkpointer

    if _checkpointer is not None:
        return _checkpointer

    try:
        _checkpointer = _build_postgres_checkpointer()
        logger.info("research_agent.checkpointer.ready", backend="postgres")
    except Exception as exc:
        # langgraph-checkpoint-postgres not installed, or connection failed.
        from langgraph.checkpoint.memory import MemorySaver

        _checkpointer = MemorySaver()
        logger.warning(
            "research_agent.checkpointer.fallback_memory",
            reason=str(exc),
            note="No crash-recovery across restarts; install "
            "langgraph-checkpoint-postgres for production.",
        )

    return _checkpointer


def _build_postgres_checkpointer():
    """
    Build the PostgreSQL checkpointer using Django's DB settings.

    We deliberately create a PERSISTENT psycopg Connection and hand it to
    PostgresSaver directly — NOT PostgresSaver.from_conn_string().

    Why not from_conn_string()? It's a generator-based context manager meant for
    short `with` blocks: it opens the connection on enter and CLOSES it on exit.
    For a process-lifetime singleton, the context manager gets garbage-collected
    after this function returns, which closes the connection out from under us
    (→ "the connection is closed" at invoke time).

    Connection kwargs that PostgresSaver requires / benefits from:
      - autocommit=True        : PostgresSaver manages its own transactions
      - row_factory=dict_row   : it reads rows as dicts
      - prepare_threshold=None : DISABLE server-side prepared statements. This is
                                 mandatory for Supabase's transaction pooler
                                 (port 6543 / pgBouncer / Supavisor): the pooler
                                 hands each transaction a DIFFERENT physical
                                 backend, so a statement prepared on one backend
                                 won't exist on the next → "prepared statement
                                 _pg3_N does not exist". With None, psycopg3 never
                                 creates named prepared statements, so it's
                                 pooler-safe.
                                 (NOTE: psycopg3 `0` means "prepare EAGERLY on
                                 first use" — the opposite of disabling — which
                                 was the original bug.)
    """
    from psycopg import Connection
    from psycopg.rows import dict_row
    from langgraph.checkpoint.postgres import PostgresSaver

    db = settings.DATABASES["default"]
    conn_str = (
        f"postgresql://{db['USER']}:{db['PASSWORD']}"
        f"@{db['HOST']}:{db['PORT']}/{db['NAME']}"
    )

    logger.info("research_agent.checkpointer.initializing", backend="postgres")

    # Persistent connection — held by the checkpointer (a module singleton),
    # so it stays open for the lifetime of the process/worker.
    conn = Connection.connect(
        conn_str,
        autocommit=True,
        prepare_threshold=None,  # disable prepared statements → Supabase pooler-safe
        row_factory=dict_row,
    )
    saver = PostgresSaver(conn)

    # Creates the checkpoint tables if absent (idempotent — safe to call again).
    saver.setup()

    return saver
