"""
engines/research_agent/channels/telegram/adapter.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Telegram Bot API adapter.

Everything Telegram-specific lives here and nowhere else: the secret-token
header, the update envelope, `chat_id` as identity, inline keyboards, and the
`{"ok": true, "result": {...}}` response shape.

Everything else — dedupe, contact upsert, rate limiting, session creation, the
workflow, the state machine, delivery, retry, ordering, PII hashing — is core's,
shared with every other platform.

The registry discovers this class by scanning `channels/`; nothing imports it
by name.
"""

from __future__ import annotations

import hmac
import json

import structlog

from engines.research_agent.channels.core import constants as k
from engines.research_agent.channels.core import http
from engines.research_agent.channels.core.adapter import (
    ChannelAdapter,
    InboundMessage,
)
from engines.research_agent.channels.telegram import config
from engines.research_agent.constants import SessionChannel

logger = structlog.get_logger(__name__)

# Telegram's header carrying the secret we registered via setWebhook.
_SECRET_HEADER = "HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN"


class TelegramAdapter(ChannelAdapter):
    """Telegram Bot API. Free, unmetered, no templates, no service window."""

    name = SessionChannel.TELEGRAM
    capabilities = config.CAPABILITIES

    # ── Availability ─────────────────────────────────────────────────────────
    def is_operational(self) -> bool:
        return config.is_operational()

    # ── Inbound ──────────────────────────────────────────────────────────────
    def verify(self, request) -> bool:
        """
        Constant-time comparison of the secret token header.

        This is the webhook's ONLY authentication. It fails CLOSED: a missing
        secret in config means nothing is accepted, rather than everything.
        Telegram sends the header on every update once setWebhook was given a
        `secret_token`.
        """
        expected = config.WEBHOOK_SECRET
        if not expected:
            logger.error("telegram.verify.no_secret_configured")
            return False

        received = request.META.get(_SECRET_HEADER, "")
        # compare_digest, not ==, so a wrong secret cannot be recovered by
        # timing how long the rejection took.
        return hmac.compare_digest(received, expected)

    def parse(self, request) -> InboundMessage | None:
        """
        Normalise a Telegram update.

        Returns None for anything core should acknowledge and ignore — edits,
        channel posts, membership changes, delivery receipts. None means 200,
        because a non-2xx makes Telegram retry the same update forever.
        """
        try:
            update = json.loads(request.body or b"{}")
        except (ValueError, TypeError) as exc:
            logger.warning("telegram.parse.bad_json", error=str(exc))
            return None

        update_id = update.get("update_id")
        if update_id is None:
            return None

        # Namespaced because provider_message_id is unique across ALL channels;
        # a bare integer could collide with another platform's id.
        provider_message_id = f"{self.name}:{update_id}"

        if "callback_query" in update:
            return self._parse_callback(update["callback_query"], provider_message_id)
        if "message" in update:
            return self._parse_message(update["message"], provider_message_id)

        logger.debug("telegram.parse.ignored", keys=sorted(update.keys()))
        return None

    def _parse_message(self, message: dict, provider_message_id: str):
        chat = message.get("chat") or {}
        sender = message.get("from") or {}
        chat_id = chat.get("id")
        if chat_id is None:
            return None

        text = message.get("text")

        return InboundMessage(
            external_id=str(chat_id),
            provider_message_id=provider_message_id,
            kind=k.MessageType.TEXT if text else k.MessageType.UNSUPPORTED,
            text=text,
            display_name=self._display_name(sender),
            metadata={
                "username": sender.get("username"),
                "language_code": sender.get("language_code"),
                "chat_type": chat.get("type"),
                "message_id": message.get("message_id"),
            },
        )

    def _parse_callback(self, callback: dict, provider_message_id: str):
        """A tapped inline button. `data` carries the action id core sent."""
        message = callback.get("message") or {}
        chat = message.get("chat") or {}
        sender = callback.get("from") or {}
        chat_id = chat.get("id")
        if chat_id is None:
            return None

        return InboundMessage(
            external_id=str(chat_id),
            provider_message_id=provider_message_id,
            kind=k.MessageType.CALLBACK,
            action_id=callback.get("data"),
            display_name=self._display_name(sender),
            metadata={
                "username": sender.get("username"),
                "chat_type": chat.get("type"),
                # Needed by answerCallbackQuery to dismiss the button's spinner.
                # Wired up in T6, when a button actually exists — done from the
                # worker, not here, so the webhook keeps returning in ms.
                "callback_query_id": callback.get("id"),
            },
        )

    @staticmethod
    def _display_name(sender: dict) -> str | None:
        parts = [sender.get("first_name"), sender.get("last_name")]
        full = " ".join(p for p in parts if p).strip()
        return full or sender.get("username") or None

    # ── Outbound ─────────────────────────────────────────────────────────────
    def send_text(self, external_id: str, text: str) -> str | None:
        return self._send(
            "sendMessage",
            {"chat_id": external_id, "text": text},
            external_id=external_id,
            kind=k.MessageType.TEXT,
        )

    def send_document(
        self,
        external_id: str,
        url: str,
        filename: str,
        caption: str | None = None,
    ) -> str | None:
        """
        Fetch the export ourselves, then UPLOAD the bytes to Telegram.

        Telegram can fetch a URL, and that was the original design — but it
        refuses content types it does not recognise. A Markdown export came back
        as `wrong type of the web page content`, and `ExportView`'s content type
        is frozen, so we cannot change what it serves.

        Uploading sidesteps all of it: Telegram never touches our host, we
        declare the filename and MIME type it sees, and the same code path works
        for `.md` locally and `.pdf` in production.

        Cost: one extra round trip for a file measured in kilobytes.
        """
        content = http.fetch_bytes(url)
        extension = filename.rsplit(".", 1)[-1].lower()
        mime = k.MIME_TYPES.get(extension, "application/octet-stream")

        data = {"chat_id": external_id}
        if caption:
            data["caption"] = caption

        def perform() -> str | None:
            response = http.post_multipart(
                config.api_url("sendDocument"),
                data=data,
                files={"document": (filename, content, mime)},
            )
            http.raise_for_status(response)
            body = response.json()
            if not body.get("ok"):
                raise http.ChannelSendError(f"telegram: {body.get('description')}")
            return str((body.get("result") or {}).get("message_id") or "")

        return http.guarded_send(
            channel=self.name,
            kind=k.MessageType.DOCUMENT,
            external_id=external_id,
            perform=perform,
            budget=self.capabilities.outbound_budget,
        )

    def send_prompt(self, external_id: str, text: str, action_id: str) -> str | None:
        """
        A tappable inline button, because `supports_buttons` is True.

        Core sends the same `action_id` on every platform; a platform without
        buttons appends a keyword instruction instead. Core never learns which
        happened — that difference stops here.
        """
        payload = {
            "chat_id": external_id,
            "text": text,
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "📧 Email report", "callback_data": action_id}]
                ]
            },
        }
        return self._send(
            "sendMessage",
            payload,
            external_id=external_id,
            kind=k.MessageType.PROMPT,
        )

    # ── One send path ────────────────────────────────────────────────────────
    def _send(self, method: str, payload: dict, *, external_id: str, kind: str):
        """
        Hand the request to core, which owns budget, ordering, retry and
        PII-safe logging. This adapter only builds the payload and reads the id.
        """

        def perform() -> str | None:
            response = http.post_json(config.api_url(method), payload)
            # Classifies 429/5xx as transient, 403 as blocked, other 4xx as
            # permanent — so a doomed request is never retried.
            http.raise_for_status(response)
            body = response.json()
            if not body.get("ok"):
                # HTTP 200 with ok:false is rare but real; treat as permanent.
                raise http.ChannelSendError(f"telegram: {body.get('description')}")
            return str((body.get("result") or {}).get("message_id") or "")

        return http.guarded_send(
            channel=self.name,
            kind=kind,
            external_id=external_id,
            perform=perform,
            budget=self.capabilities.outbound_budget,
        )

    # ── Optional hooks ───────────────────────────────────────────────────────
    def acknowledge(self, inbound: InboundMessage) -> None:
        """
        Stop the tapped button spinning.

        Telegram shows a loading state on an inline button until
        `answerCallbackQuery` arrives. Best-effort: a failure here is cosmetic,
        and must never derail the work the tap actually requested.
        """
        callback_id = (inbound.metadata or {}).get("callback_query_id")
        if not callback_id:
            return
        try:
            http.post_json(
                config.api_url("answerCallbackQuery"),
                {"callback_query_id": callback_id},
            )
        except Exception as exc:
            logger.debug("telegram.acknowledge_failed", error=str(exc))

    # ── Webhook registration (operational helper, not part of the contract) ──
    def set_webhook(self) -> dict:
        """
        Point Telegram at this backend. Run once per environment, and again
        whenever BACKEND_PUBLIC_URL changes.

        `drop_pending_updates` clears anything queued while the webhook was
        unset — otherwise switching it on replays every message sent meanwhile.
        """
        response = http.post_json(
            config.api_url("setWebhook"),
            {
                "url": k.webhook_url(self.name),
                "secret_token": config.WEBHOOK_SECRET,
                "allowed_updates": ["message", "callback_query"],
                "drop_pending_updates": True,
            },
        )
        http.raise_for_status(response)
        return response.json()

    def webhook_info(self) -> dict:
        """What Telegram currently believes about our webhook. Diagnostics only."""
        response = http.post_json(config.api_url("getWebhookInfo"), {})
        http.raise_for_status(response)
        return response.json()
