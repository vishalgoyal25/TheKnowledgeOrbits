"""
engines/research_agent/services/sse_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SSEService — the live event bus between the Celery worker and the browser.

THE PROBLEM IT SOLVES:
  The workflow runs in a Celery WORKER process. The browser's SSE connection is
  held open by a DIFFERENT Django process (the stream view). They cannot call
  each other directly. They bridge through REDIS PUB/SUB:

      worker  ──emit()──►  redis channel "research:sse:{id}"  ──►  stream() ──► browser

API:
  emit(session_id, event_type, data)  → worker side: publish one event
  stream(session_id)                  → view side: generator of SSE strings
                                        (subscribes to the channel, heartbeats
                                        every 15s, ends on the __close__ sentinel)
  close(session_id)                   → worker side: publish __close__ so the
                                        browser stream terminates cleanly
  set_cancelled / is_cancelled        → Redis flag the browser sets on disconnect;
                                        every agent checks it (Risk #36)

GRACEFUL DEGRADATION:
  If Redis is unavailable (e.g. local dev with no REDIS_URL), emit/close/cancel
  become safe no-ops and stream() yields a single error event then ends. The
  workflow itself still runs (the terminal/management command needs no SSE).
"""

from __future__ import annotations

import json
import structlog

from engines.research_agent.constants import (
    SSE_HEARTBEAT_INTERVAL,
    SSE_STREAM_RETRY_MS,
)

logger = structlog.get_logger(__name__)

# Redis key namespaces.
_CHANNEL = "research:sse:{session_id}"
_CANCEL_KEY = "research:cancel:{session_id}"
_CANCEL_TTL = 3600  # cancel flags self-expire after 1h (cleanup safety)

# Internal sentinel event that tells stream() to stop.
_CLOSE_EVENT = "__close__"


class SSEService:
    """Module-level singleton. All members are stateless w.r.t. instance data."""

    # ──────────────────────────────────────────────────────────────────────────
    # WORKER SIDE — publish events
    # ──────────────────────────────────────────────────────────────────────────
    def emit(self, session_id: str, event_type: str, data: dict) -> None:
        """Publish one event to the session's Redis channel. Never raises."""
        conn = self._redis()
        if conn is None:
            return
        try:
            payload = json.dumps({"event": event_type, "data": data})
            conn.publish(_CHANNEL.format(session_id=session_id), payload)
        except Exception as exc:
            logger.warning(
                "research_agent.sse.emit_failed", session_id=session_id, error=str(exc)
            )

    def close(self, session_id: str) -> None:
        """Publish the close sentinel so the browser's stream() loop terminates."""
        self.emit(session_id, _CLOSE_EVENT, {})

    def terminal_stream(self, status: str):
        """
        One-shot SSE stream for a session that ALREADY finished. Emits the final
        event and ends — WITHOUT subscribing to Redis. This avoids the infinite
        heartbeat that happens when the browser connects AFTER the session
        completed (Redis pub/sub is fire-and-forget; a late subscriber misses the
        events that already fired, including __close__).
        """
        from engines.research_agent.constants import SSEEvent

        yield f"retry: {SSE_STREAM_RETRY_MS}\n\n"
        event = {
            "completed": SSEEvent.WORKFLOW_COMPLETED,
            "cancelled": SSEEvent.WORKFLOW_CANCELLED,
            "failed": SSEEvent.WORKFLOW_FAILED,
        }.get(status, SSEEvent.WORKFLOW_COMPLETED)
        yield self._format(
            event, {"status": status, "note": "session already finished"}
        )

    # ──────────────────────────────────────────────────────────────────────────
    # VIEW SIDE — stream to the browser
    # ──────────────────────────────────────────────────────────────────────────
    def stream(self, session_id: str):
        """
        Generator of SSE-formatted strings, consumed by StreamingHttpResponse.

        Subscribes to the session channel and:
          - forwards each published event as `event: <type>\\ndata: <json>\\n\\n`
          - emits a `: heartbeat` comment every SSE_HEARTBEAT_INTERVAL seconds of
            silence (keeps Render/Vercel proxies from closing the connection)
          - stops on the __close__ sentinel or on client disconnect (GeneratorExit)
        """
        conn = self._redis()
        if conn is None:
            yield self._format("workflow_failed", {"error": "sse_unavailable"})
            return

        # Tell the browser how long to wait before auto-reconnecting.
        yield f"retry: {SSE_STREAM_RETRY_MS}\n\n"

        pubsub = None
        try:
            pubsub = conn.pubsub()
            channel = _CHANNEL.format(session_id=session_id)
            pubsub.subscribe(channel)

            while True:
                message = pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=SSE_HEARTBEAT_INTERVAL,
                )
                if message is None:
                    # Silence window elapsed → heartbeat comment.
                    yield ": heartbeat\n\n"
                    continue

                payload = self._decode(message.get("data"))
                if payload is None:
                    continue

                event_type = payload.get("event", "")
                if event_type == _CLOSE_EVENT:
                    break

                yield self._format(event_type, payload.get("data", {}))
        except GeneratorExit:
            # Browser disconnected → flag cancellation so agents stop wasting budget.
            self.set_cancelled(session_id)
            raise
        except Exception as exc:
            # ANY Redis/pubsub error → clean SSE error frame, never a 500.
            logger.warning(
                "research_agent.sse.stream_error", session_id=session_id, error=str(exc)
            )
            yield self._format("workflow_failed", {"error": "stream_error"})
        finally:
            if pubsub is not None:
                try:
                    pubsub.close()
                except Exception:
                    pass

    # ──────────────────────────────────────────────────────────────────────────
    # CANCELLATION FLAG
    # ──────────────────────────────────────────────────────────────────────────
    def set_cancelled(self, session_id: str) -> None:
        """Set the Redis cancel flag (browser disconnect or explicit cancel)."""
        conn = self._redis()
        if conn is None:
            return
        try:
            conn.set(_CANCEL_KEY.format(session_id=session_id), "1", ex=_CANCEL_TTL)
            logger.info("research_agent.sse.cancelled_set", session_id=session_id)
        except Exception as exc:
            logger.warning(
                "research_agent.sse.cancel_set_failed",
                session_id=session_id,
                error=str(exc),
            )

    def is_cancelled(self, session_id: str) -> bool:
        """Check the Redis cancel flag. Returns False if Redis is unavailable."""
        conn = self._redis()
        if conn is None:
            return False
        try:
            return conn.exists(_CANCEL_KEY.format(session_id=session_id)) == 1
        except Exception:
            return False

    # ──────────────────────────────────────────────────────────────────────────
    # PRIVATE
    # ──────────────────────────────────────────────────────────────────────────
    def _redis(self):
        """
        Lazily fetch the shared django-redis connection. Returns None (so callers
        degrade gracefully) if Redis isn't configured/available.
        """
        try:
            from django_redis import get_redis_connection

            return get_redis_connection("default")
        except Exception:
            return None

    @staticmethod
    def _format(event_type: str, data: dict) -> str:
        """Render one SSE event frame."""
        return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

    @staticmethod
    def _decode(raw):
        """Decode a published Redis message (bytes/str) into a dict."""
        if raw is None:
            return None
        try:
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            return json.loads(raw)
        except Exception:
            return None


# Module-level singleton — imported by orchestrator, agents, views.
sse_service = SSEService()
