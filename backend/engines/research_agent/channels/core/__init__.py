# engines/research_agent/channels/core/__init__.py
# ─────────────────────────────────────────────────────────────────────────────
# The platform-agnostic core of the channel layer.
#
# One engine, many doors. A question asked from Telegram, WhatsApp or any future
# platform runs through EXACTLY the same code from this point inward — same
# session, same 8-node workflow, same ops tables, same Langfuse trace, same
# DeepEval score. Platforms differ only in how bytes arrive and leave.
#
# THE RULE
#   Dependencies point INWARD. This package MUST NEVER import an adapter
#   (channels/telegram/, channels/whatsapp/, …) and MUST NEVER branch on a
#   channel name. The only permitted lookup is registry.get(name).
#
#   An `if channel == "telegram"` in this package is a review-blocking defect,
#   because it means the next platform has to edit core.
#
# CAPABILITY, NOT PLATFORM
#   Platforms genuinely differ — 1600 vs 4096 character limits, tappable
#   buttons vs typed keywords, media by URL vs upload. Core branches on the
#   Capabilities an adapter DECLARES, never on who declared them. That is what
#   keeps this package stable while platforms come and go.
#
# WHAT LIVES HERE (policy — identical everywhere)
#   constants.py      shared enums + policy values (TTL, retries, masking)
#   adapter.py        Capabilities · InboundMessage · ChannelAdapter interface
#   models.py         ChannelContact · ChannelMessage · ReportDelivery
#   http.py           retry/backoff · send ordering · outbound budget
#   registry.py       auto-discovers adapters by scanning channels/
#   webhook.py        ONE parameterised route for every channel
#   service.py        inbound → dedupe → contact → rate limit → session → enqueue
#   state.py          the email state machine (TTL, retries, NULL clearing)
#   delivery.py       summary → document → prompt, in order
#   filename.py       query → safe, readable filename
#   progress.py       graph node events → human-readable pings
#   email_service.py  report delivery by email, with the PDF attached
#
# WHAT DOES NOT LIVE HERE (transport — varies per platform)
#   credentials · payload shape · auth scheme · identity extraction ·
#   provider message ids · the actual HTTP call. All of that is an adapter's
#   `config.py` + `adapter.py`, and nothing else.
#
# THE WEB PATH IS NOT A CHANNEL
#   `channel="web"` is an attribution label only. Browser queries keep their
#   existing QueryView → orchestrator → SSE → export path and MUST NEVER route
#   through this package. The web experience is the incumbent and has priority.
#
# Full spec: FEATURE_TELEGRAM.md §2 · rules: CLAUDE.md
# ─────────────────────────────────────────────────────────────────────────────
#
# Nothing is imported here on purpose. Django loads this package at startup, and
# eager imports would pull `requests` and env reads into every management
# command, including `migrate`.
