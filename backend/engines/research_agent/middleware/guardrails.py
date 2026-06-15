"""
engines/research_agent/middleware/guardrails.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Input + output guardrails (Risk #39 / #55).

INPUT  (before LangGraph runs): reject prompt-injection / jailbreak attempts and
       Unicode-normalize the query. This is the comprehensive screen the
       Supervisor's cheap inline check defers to.
OUTPUT (before persisting / sending): strip dangerous HTML (e.g. <script>) from
       LLM-generated markdown as a defense-in-depth layer behind the frontend's
       rehype-sanitize, and Unicode-normalize.

Pure, deterministic, no LLM call — fast and free.
"""

from __future__ import annotations

import re
import unicodedata

import structlog

logger = structlog.get_logger(__name__)

# Comprehensive prompt-injection / jailbreak signatures (superset of the
# Supervisor's cheap inline list). Lowercased substring match.
_INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all previous",
    "ignore the above",
    "disregard the above",
    "disregard previous",
    "disregard all previous",
    "forget your instructions",
    "forget all previous",
    "you are now",
    "act as if",
    "pretend to be",
    "pretend you are",
    "roleplay as",
    "system prompt",
    "reveal your prompt",
    "reveal your instructions",
    "print your instructions",
    "show me your prompt",
    "repeat the words above",
    "developer mode",
    "do anything now",
    "jailbreak",
    "dan mode",
    "bypass your",
    "without any restrictions",
]

# Dangerous HTML stripped from output (defense-in-depth; frontend also sanitizes).
_SCRIPT_RE = re.compile(
    r"<\s*script[^>]*>.*?<\s*/\s*script\s*>", re.IGNORECASE | re.DOTALL
)
_EVENT_HANDLER_RE = re.compile(
    r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", re.IGNORECASE
)
_JS_URI_RE = re.compile(r"javascript:", re.IGNORECASE)


class Guardrails:
    """Module-level singleton. Stateless, deterministic."""

    # ── INPUT ─────────────────────────────────────────────────────────────────
    def check_input(self, query: str) -> tuple[bool, str | None]:
        """
        Returns (allowed, reason). reason is None when allowed.
        Detects prompt-injection patterns after Unicode normalization.
        """
        normalized = self.sanitize_input(query)
        lowered = normalized.lower()
        for pattern in _INJECTION_PATTERNS:
            if pattern in lowered:
                logger.warning(
                    "research_agent.guardrails.input_blocked", pattern=pattern
                )
                return False, f"prompt_injection:{pattern}"
        return True, None

    def sanitize_input(self, text: str) -> str:
        """NFC-normalize + trim — handles Hindi/Arabic/emoji safely (Risk #47)."""
        if not text:
            return ""
        return unicodedata.normalize("NFC", text).strip()

    # ── OUTPUT ────────────────────────────────────────────────────────────────
    def sanitize_output(self, text: str) -> str:
        """
        Strip dangerous HTML from LLM-generated markdown before it's stored/sent.
        Defense-in-depth behind the frontend's rehype-sanitize (Risk #55).
        """
        if not text:
            return ""
        text = unicodedata.normalize("NFC", text)
        text = _SCRIPT_RE.sub("", text)
        text = _EVENT_HANDLER_RE.sub("", text)
        text = _JS_URI_RE.sub("", text)
        return text

    def check_output(self, text: str) -> tuple[bool, str | None]:
        """
        Light output validation: flag empty output or obvious system-prompt
        leakage. Returns (ok, reason). Non-blocking by default — the caller
        decides what to do with a flagged report.
        """
        if not text or not text.strip():
            return False, "empty_output"
        lowered = text.lower()
        if "you are an expert research" in lowered and "system prompt" in lowered:
            return False, "possible_prompt_leak"
        return True, None


# Module-level singleton.
guardrails = Guardrails()
