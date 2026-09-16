"""
engines.tags.services — deliberately EMPTY package init.

Python executes this file before any `engines.tags.services.<module>` import.
Until 2026-09-16 it re-exported `ConceptPageResolver` and `TagService`, and both
of those modules import `engines.book_content.services.llm_service`, which loads
the Cerebras and OpenAI SDKs at module level. Those SDKs are not in
`requirements/scraper.txt`, the standalone install the GitHub Actions
"Current Affairs Ghost Worker" uses.

So the moment `tags/views.py` imported the pure-regex `concept_seo_service`
(PR #25), every `manage.py` command in that workflow died at URL-conf load with
`ModuleNotFoundError: No module named 'cerebras'` — run #410, twelve hours of
scraping lost before it was noticed.

The contract: importing this package must never import an LLM SDK. Callers
import the module they need:

    from engines.tags.services.concept_resolver import ConceptPageResolver
    from engines.tags.services.tag_service import TagService

Guarded by `engines/tags/tests/test_import_contract.py`.
"""
