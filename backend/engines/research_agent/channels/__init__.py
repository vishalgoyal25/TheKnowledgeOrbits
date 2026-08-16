# engines/research_agent/channels/__init__.py
# Delivery channels for the research agent.
#
# A "channel" is a transport that carries an existing research query in and the
# existing report out. Channels NEVER modify the pipeline — graph/, agents/,
# tools/, export_service.py, sse_service.py, evaluation/ and llmops/ are frozen.
#
# Every channel MUST create a normal ResearchSession so all 5 ops tables,
# Langfuse and DeepEval populate identically to the web experience.
#
# Channels:
#   whatsapp/  — Meta WhatsApp Cloud API bot (see FEATURE_WHATSAPP.md)
