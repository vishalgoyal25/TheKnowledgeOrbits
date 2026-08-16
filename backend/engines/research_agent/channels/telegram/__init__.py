# engines/research_agent/channels/telegram/__init__.py
# ─────────────────────────────────────────────────────────────────────────────
# Telegram adapter — the first platform to plug into channels/core/.
#
# TWO FILES, deliberately:
#   config.py    credentials, endpoints, declared Capabilities
#   adapter.py   verify · parse · send_text · send_document · send_prompt
#
# No models, no webhook, no urls, no state machine, no retry logic — all of
# that is core's, shared with every other platform. If a third file starts to
# feel necessary here, the logic almost certainly belongs in core.
#
# WHY TELEGRAM IS EASY
#   No business tier, no message templates, no 24-hour service window, no
#   approval queue, no verification, no message allowance. `sendMessage` and
#   `sendDocument` are plain async REST, callable at any time — which is exactly
#   what a workflow that finishes 40-90s after the webhook closes requires.
#   (Twilio's trial tier refused precisely this; see FEATURE_WHATSAPP.md §11.)
#
# Nothing is imported here on purpose — the registry imports `adapter` lazily,
# so `migrate` and other management commands never pull in `requests`.
# ─────────────────────────────────────────────────────────────────────────────
