"""Model package for the Data Factory engine.

A package rather than a flat ``models.py``, which diverges from the 16 shipped
engines on purpose: this engine reaches ~24 models by Act II, and splitting a
single file at that point means touching imports across services and tests.
``book_content`` already carries 8 models in one file and is hard to navigate.
Grouping is by layer, matching 06_DESIGN.md:

    sources.py   acquisition  -- DfSource, DfArtifact
    atoms.py     evidence     -- DfChunk, DfAtom

Act II adds ``graph.py`` (knowledge objects, entities) and ``control.py`` (runs,
cost, budget, checkpoints, the two memory ledgers).

Django finds models through this module, so every model class MUST be re-exported
here or its table will never be created.

Import discipline -- this file is load-bearing
----------------------------------------------
``engines/tags/tests/test_import_contract.py`` runs ``django.setup()`` with
``cerebras``, ``openai`` and ``mistralai`` blocked, then imports ``core.urls``.
``django.setup()`` loads every installed app's models, so THIS module is inside
that probe's import path. It may import models and nothing else -- never
``services/``, never an adapter, never anything that reaches an LLM SDK. The
same chain runs on every ``manage.py`` command and in the GitHub Actions
scraper, which installs ``requirements/scraper.txt`` without those SDKs.

(``groq`` is deliberately NOT blocked by that test -- it ships in scraper.txt.
That is not licence to import it here.)
"""

from .atoms import DfAtom, DfChunk
from .sources import DfArtifact, DfSource

# Re-export surface. Ruff's F401 honours __all__, so these imports survive
# `ruff check --fix` rather than being stripped as unused (CLAUDE.md 4.1).
__all__ = [
    "DfArtifact",
    "DfAtom",
    "DfChunk",
    "DfSource",
]
