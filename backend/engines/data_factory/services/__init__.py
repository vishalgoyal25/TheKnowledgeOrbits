"""Service layer for the Data Factory engine.

🔴 INTENTIONALLY EMPTY. This package's ``__init__`` does NOT import its
submodules, and must never start doing so.

Why -- there is already a production incident for this
-----------------------------------------------------
``engines/book_content/services/__init__.py`` used to do
``from . import llm_service / ingestor_service / ...``. That meant importing
ANY submodule -- even the pure-retrieval RAG gateway -- transitively loaded
``llm_service``, which imports the Cerebras SDK. When the RAG rewiring made a
URL-reachable view import ``retrieve_grounding``, the zero-LLM current_affairs
scraper crashed at Django startup, because GitHub Actions installs
``requirements/scraper.txt`` and that environment has no Cerebras SDK. See that
file's docstring for the full account.

This package will hold modules on BOTH sides of that line:

    span_checker.py   pure arithmetic, no network, safe anywhere
    (later) adapters, the verifier caller, extraction  -- these WILL reach an
    LLM SDK or boto3

So a single eager re-export here would taint the whole package, and every
caller of the pure span checker would start dragging an SDK behind it. Guarded
by ``engines/tags/tests/test_import_contract.py``.

Import submodules explicitly, always:

    from engines.data_factory.services.span_checker import check_span

⚠️ ``daily_ca/services/__init__.py`` and ``shared/services/__init__.py`` DO
re-export eagerly. That is safe there and unsafe here -- do not copy them into
this engine (CLAUDE.md 4.6a: follow the nearest pattern, but say when a
different one applies).
"""
