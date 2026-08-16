# engines/research_agent/channels/__init__.py
# ─────────────────────────────────────────────────────────────────────────────
# Delivery channels for the research agent — CORE + ADAPTERS.
#
# A "channel" is a transport that carries an existing research query in and the
# existing report out. Channels NEVER modify the pipeline — graph/, agents/,
# tools/, export_service.py, sse_service.py, evaluation/ and llmops/ are frozen.
#
# Every channel MUST create a normal ResearchSession, so all 5 ops tables,
# Langfuse and DeepEval populate identically to the web experience.
#
#   core/       platform-agnostic engine — models, state machine, delivery,
#               retry, registry, webhook. Read core/__init__.py first; it holds
#               the architecture contract.
#
#   telegram/   adapter — ACTIVE
#   whatsapp/   adapter — ON HOLD (provider access; see FEATURE_WHATSAPP.md §11).
#               Retained intact, not reverted. Its ra_wa_* tables are superseded
#               by core's generic tables but kept, empty and unused.
#
# An adapter is TWO files: config.py + adapter.py. If a third seems necessary,
# that logic almost certainly belongs in core/.
#
# Adapters MUST NEVER import each other. Shared logic moves UP into core/,
# never sideways.
# ─────────────────────────────────────────────────────────────────────────────
