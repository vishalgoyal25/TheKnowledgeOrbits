"""
Data Factory Engine — the product-agnostic evidence core.

Acquires source material, stores it immutably, and reduces it to Fact Atoms:
one verifiable claim, one exact character span, one source. Everything the
platform publishes is traceable back to a row in this engine.

Tables are prefixed ``df_`` (house style: ``current_affairs`` -> ``ca_``,
``research_agent`` -> ``ra_``). Design: FEATURES/DATA_FACTORY/06_DESIGN.md.

Two rules that this engine exists to enforce
--------------------------------------------
1. Nothing publishes that cannot be traced to its evidence.
2. This engine is PRODUCT-AGNOSTIC. It must never contain the words "test
   series" -- not in a column, an index, a docstring or a prompt. Products
   point at ``df_atom`` through their own join tables; this engine never
   points back. Delete every product table and the Factory still runs.

Import discipline
-----------------
This module stays import-free. ``manage.py`` runs the URL system check before
every command, so anything reachable from the URL conf must not pull in an LLM
SDK. Guarded by ``engines/tags/tests/test_import_contract.py``.

``default_app_config`` is deliberately absent: it was removed in Django 4.1 and
this project runs Django 5.2, so the older engines' copies of it are inert.
Django discovers ``apps.DataFactoryConfig`` on its own.
"""
