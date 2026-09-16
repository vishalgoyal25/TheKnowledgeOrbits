"""
engines/tags/tests/test_import_contract.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The URL conf must import WITHOUT the LLM SDKs.

WHY
  The GitHub Actions "Current Affairs Ghost Worker" runs `manage.py scrape_ca`
  on `requirements/scraper.txt`, a standalone install with no Cerebras, OpenAI
  or Mistral SDK. Every management command runs Django's system checks first,
  and the URL check imports `core.urls`, which imports every engine's views.
  One eager `from … import` on that path that reaches
  `book_content.services.llm_service` therefore kills the scraper — which is
  exactly what happened on 2026-09-16 (run #410): `tags/views.py` imported a
  pure-regex helper from `engines.tags.services`, whose `__init__` re-exported
  two LLM-backed services.

HOW
  A subprocess blocks the three SDK packages (`sys.modules[name] = None` makes
  `import name` raise ModuleNotFoundError), runs `django.setup()` and imports
  `core.urls`. Any import chain that reaches an SDK fails the test with the
  offending traceback. A subprocess, not `importlib.reload`, so the test cannot
  poison this interpreter's module state for the rest of the suite.
"""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[3]

# Not installed by requirements/scraper.txt. `groq` IS installed there and is
# deliberately not blocked.
LLM_SDKS = ("cerebras", "cerebras.cloud", "cerebras.cloud.sdk", "openai", "mistralai")

PROBE = textwrap.dedent(
    """
    import sys
    for name in {sdks!r}:
        sys.modules[name] = None
    import django
    django.setup()
    import core.urls
    assert core.urls.urlpatterns
    """
).format(sdks=LLM_SDKS)


def test_url_conf_imports_without_llm_sdks():
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": os.environ.get(
            "DJANGO_SETTINGS_MODULE", "core.settings.dev"
        ),
    }
    result = subprocess.run(
        [sys.executable, "-c", PROBE],
        cwd=str(BACKEND_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, (
        "core.urls pulled in an LLM SDK at import time — the scraper workflow "
        "(requirements/scraper.txt) would die at URL-conf load:\n"
        + result.stderr[-4000:]
    )
