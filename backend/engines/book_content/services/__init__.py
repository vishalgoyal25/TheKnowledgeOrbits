"""
engines/book_content/services/__init__.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Intentionally lightweight — this package's __init__ does NOT eagerly import the
service submodules.

It used to do `from . import ingestor_service / llm_service / ...`, which meant
importing ANY submodule (e.g. retrieval_service for the RAG gateway) transitively
loaded llm_service → the cerebras SDK. That coupling crashed the zero-LLM
current_affairs scraper at Django startup (it boots in a lean env WITHOUT cerebras)
the moment the RAG rewiring made URL-reachable views import `retrieve_grounding`.

Import submodules explicitly where you need them, e.g.:
    from engines.book_content.services.retrieval_service import retrieve_grounding
    from engines.book_content.services.llm_service import llm_call

Each submodule now loads on demand — retrieval (RAG) no longer drags in
generation (LLM/cerebras).
"""
