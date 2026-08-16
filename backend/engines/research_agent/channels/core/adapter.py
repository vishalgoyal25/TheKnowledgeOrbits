"""
engines/research_agent/channels/core/adapter.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The contract between core and a platform.

An adapter is the ONLY place a platform's peculiarities may live. It answers
six questions and declares what it can do; core does everything else.

    Is the channel usable right now?        is_operational()
    Did this request really come from you?  verify(request)
    What does this payload actually say?    parse(request)   -> InboundMessage
    Send words.                             send_text()
    Send a file.                            send_document()
    Ask a question with an action.          send_prompt()

Everything downstream of `parse()` is identical for every platform: dedupe,
contact upsert, rate limiting, session creation, the workflow, the state
machine, delivery, email.

WHY CAPABILITIES EXIST
    Platforms differ in ways core must respect — 1600 vs 4096 character limits,
    tappable buttons vs typed keywords, media by public URL vs upload, metered
    trial quotas vs none.

    Core handles those by reading the `Capabilities` an adapter DECLARES. It
    must never ask *which* platform it is talking to. That is the whole reason
    adding platform #11 costs a folder instead of a refactor — and why an
    `if channel == "..."` inside core/ is a review-blocking defect.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

from engines.research_agent.channels.core import constants as k


class MediaMode:
    """How a platform wants documents handed to it."""

    URL = "url"  # we pass a public link; the provider fetches it
    UPLOAD = "upload"  # we post the bytes ourselves
    ALL = (URL, UPLOAD)


@dataclass(frozen=True)
class Capabilities:
    """
    What a platform can do, declared as data.

    Every field here exists because some platform differs from another. If a
    new difference appears, it becomes a field — never a branch in core.
    """

    # Hard cap on one outbound text message. Core truncates against this.
    max_text_chars: int

    # True  → send_prompt() renders a tappable button, and taps arrive as
    #         MessageType.CALLBACK carrying an action_id.
    # False → send_prompt() appends a keyword instruction, and the reply
    #         arrives as ordinary text. Core does not care which.
    supports_buttons: bool

    media_mode: str = MediaMode.URL
    max_media_bytes: int = 20 * 1024 * 1024

    # Lifetime ceiling on outbound messages for metered providers.
    # None = unlimited (the normal case). A trial account that charges for
    # every accepted request sets a real number, and core stops there.
    outbound_budget: int | None = None

    def __post_init__(self) -> None:
        if self.media_mode not in MediaMode.ALL:
            raise ValueError(f"media_mode must be one of {MediaMode.ALL}")
        if self.max_text_chars < 1:
            raise ValueError("max_text_chars must be positive")


@dataclass(frozen=True)
class InboundMessage:
    """
    A platform payload, normalised. Core never sees the raw request again.

    `external_id` is the raw identity (chat_id, phone, user id) as a string.
    It is hashed before it reaches ResearchSession, Langfuse or Sentry — the
    raw value lives only in ra_channel_contact.
    """

    external_id: str
    provider_message_id: str  # idempotency key; providers re-deliver
    kind: str  # MessageType.TEXT | CALLBACK | UNSUPPORTED

    text: str | None = None
    action_id: str | None = None  # set when kind == CALLBACK
    display_name: str | None = None
    metadata: dict = field(default_factory=dict)  # platform extras, stored as JSON

    @property
    def is_text(self) -> bool:
        return self.kind == k.MessageType.TEXT and bool((self.text or "").strip())

    @property
    def is_callback(self) -> bool:
        return self.kind == k.MessageType.CALLBACK and bool(self.action_id)


class ChannelAdapter(ABC):
    """
    Base class for every platform adapter.

    An ABC rather than a Protocol on purpose: a missing or misspelled method
    fails loudly at instantiation, during startup discovery, instead of at
    3 a.m. when a user taps a button.

    Adapters MAY import core. Core MUST NOT import adapters, and adapters MUST
    NOT import each other — shared logic moves up into core, never sideways.
    """

    #: Must match a SessionChannel value. The registry keys on this.
    name: ClassVar[str]

    #: Declared once, read by core wherever platforms differ.
    capabilities: ClassVar[Capabilities]

    # ── Availability ─────────────────────────────────────────────────────────
    @abstractmethod
    def is_operational(self) -> bool:
        """
        True only when the kill switch is on AND every credential is present.

        Core checks this before attempting anything. A disabled or
        half-configured channel must go quiet, never raise — it may not break
        the worker or the web app.
        """

    # ── Inbound ──────────────────────────────────────────────────────────────
    @abstractmethod
    def verify(self, request: Any) -> bool:
        """
        Prove the request came from the provider — signature, HMAC or shared
        secret. This is the webhook's ONLY authentication (the documented
        exemption to the RBAC-decorator rule), so it must fail closed.
        """

    @abstractmethod
    def parse(self, request: Any) -> InboundMessage | None:
        """
        Normalise a verified payload.

        Returns None for anything core should silently acknowledge and ignore —
        delivery receipts, read receipts, edits, bot-joined events. Returning
        None is a 200, not an error: providers retry non-2xx responses.
        """

    # ── Outbound ─────────────────────────────────────────────────────────────
    @abstractmethod
    def send_text(self, external_id: str, text: str) -> str | None:
        """Send plain text. Returns the provider's message id, or None if skipped."""

    @abstractmethod
    def send_document(
        self,
        external_id: str,
        url: str,
        filename: str,
        caption: str | None = None,
    ) -> str | None:
        """
        Send a document.

        `url` must be publicly reachable when `media_mode == URL` — the
        provider fetches it. A localhost URL fails on the provider's side, not
        ours, which is a miserable thing to debug.
        """

    @abstractmethod
    def send_prompt(self, external_id: str, text: str, action_id: str) -> str | None:
        """
        Ask something the user can act on.

        With `supports_buttons=True` this is a tappable button whose tap
        returns `action_id` as a CALLBACK. Otherwise the adapter appends a
        keyword instruction and the answer arrives as ordinary text.

        Core sends the same action either way and never learns which happened.
        """

    # ── Optional hooks ───────────────────────────────────────────────────────
    def acknowledge(self, inbound: InboundMessage) -> None:
        """
        Dismiss a platform's "processing" indicator after an interaction.

        Telegram spins a tapped button until `answerCallbackQuery` arrives.
        Platforms without that concept inherit this no-op, so core can call it
        unconditionally rather than asking who it is talking to.

        Called from the WORKER, never the webhook — acknowledgement must stay
        in milliseconds.
        """
        return None

    # ── Diagnostics ──────────────────────────────────────────────────────────
    def describe(self) -> dict:
        """Non-sensitive snapshot for health checks and logs. Never credentials."""
        c = self.capabilities
        return {
            "channel": self.name,
            "operational": self.is_operational(),
            "max_text_chars": c.max_text_chars,
            "supports_buttons": c.supports_buttons,
            "media_mode": c.media_mode,
            "outbound_budget": c.outbound_budget,
        }

    def __str__(self) -> str:
        return f"<ChannelAdapter {self.name}>"
