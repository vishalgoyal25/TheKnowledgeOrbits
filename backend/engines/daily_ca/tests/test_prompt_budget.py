"""
engines/daily_ca/tests/test_prompt_budget.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L10 tripwire (FEATURES_LLM_FIX.md Part II) — the Daily-CA article prompt must
stay small enough to route to Groq, and the rewrite must not have dropped a rule.

Why a test and not a comment: the template grew to 27,200 chars over five months
of "one more rule", nobody measured it, and the article path silently moved to
free-tier providers that then died. A template that grows past the budget now
breaks the build, not the cron.

No database, no LLM.
"""

from engines.book_content.services.llm_service import _estimate_tokens
from engines.daily_ca.models import NEWS_CATEGORY_CHOICES
from engines.daily_ca.services.prompt_builder import (
    CA_DAILY_PROMPT_TEMPLATE,
    CA_NEWS_CONTEXT_MAX_CHARS,
    CA_PROMPT_TOKEN_BUDGET,
    SUBJECT_BRIDGE_MAP,
    SUBJECT_TONE_MAP,
    _NEWS_CATEGORIES,
    build_ca_prompt,
    subject_guidance,
)

# The subject with the longest tone directive — the worst case for the template.
LONGEST_TONE_SUBJECT = max(SUBJECT_TONE_MAP, key=lambda k: len(SUBJECT_TONE_MAP[k]))

# Worst-case data inputs: the news cap filled, five long provisions and facts
# (retrieval_service.as_static_facts truncates each to ~170 / ~220 chars, so 240
# is above anything real), six statistics, and a wiki block that fires.
WORST_NEWS = (
    "Revenue Minister P. Srinivas Reddy told the Assembly on Tuesday that " * 90
)[: CA_NEWS_CONTEXT_MAX_CHARS + 1_000]
WORST_FACTS = {
    "title": "Land Reforms in India: Tenancy and Ceiling Acts",
    "key_provisions": [
        "Article 31A(2)(b) and Article 31B shield land-reform statutes " * 4
    ]
    * 5,
    "key_facts": [
        "Supreme Court jurisprudence reinforces the framework: State of Punjab " * 4
    ]
    * 5,
    "statistics": [
        "27 percent",
        "Rs 1,200 crore",
        "2011 Census",
        "12 % rise",
        "5 GB",
        "96 %",
    ],
}
WORST_WIKI = {
    "intro": "The Land Ceiling Acts are a series of state laws enacted after 1961 "
    * 12,
    "key_facts": ["A background fact drawn from the Wikipedia section text here " * 3]
    * 5,
    "related_terms": [
        "Zamindari abolition",
        "Bhoodan",
        "Tenancy reform",
        "Ceiling",
        "Patta",
    ],
}

MANDATORY_RULES = (
    "# Title",  # the parser takes the first heading as the title
    "[[double brackets]]",
    "5 to 8 terms",
    ":::callout",
    "Did You Know?",
    "CATEGORY:",
    "TAGS:",
    "SOURCE:",
    "## headings only (no ###)",
    "UPSC Angle",
    "Why in News",
    "ONLY if it appears",  # data integrity
    "never copy its prose",
    "550 to 750 words",
    "hard maximum 900",
    "It is pertinent to note that",
    "Experts believe",
    "Never run the article together on one line",  # the C7 shape is a prompt failure first
    "FOUR or FIVE ## sections",  # length arithmetic, not just a word range
    "Do not invent:",  # the explicit fabrication list
    "CHECKLIST",  # the end-of-prompt verification pass
    "count them before you finish",  # links were the most-missed rule in the trial
    "appears exactly once",  # anti-repetition (the line wraps after "in the")
    "TODAY'S NEWS CONTEXT",
    "CONCEPTUAL DEPTH ANCHOR",
    "SUPPLEMENTARY REFERENCE",
)

# Phrases the old template repeated; each must now appear exactly once.
STATED_ONCE = (
    "Did You Know?",
    "UPSC Angle",
    "It is pertinent to note that",
    "[[double brackets]]",
    "Experts believe",
)

NON_ASCII_DECORATION = ("─", "→", "✓", "✗", "×", "•", "💡")


def _worst_case_prompt() -> str:
    return build_ca_prompt(
        ca_chunks_text=WORST_NEWS,
        static_key_facts=WORST_FACTS,
        wiki_enrichment=WORST_WIKI,
        subject_name=LONGEST_TONE_SUBJECT,
        topic_name="Land Reforms in India: Tenancy and Ceiling Acts",
    )


class TestPromptBudget:
    def test_worst_case_prompt_within_token_budget(self):
        """The whole prompt, with every input at its maximum, routes to Groq."""
        prompt = _worst_case_prompt()
        est = _estimate_tokens(prompt)
        assert est <= CA_PROMPT_TOKEN_BUDGET, (
            f"article prompt is {est:,} est. tokens > budget {CA_PROMPT_TOKEN_BUDGET:,} "
            f"({len(prompt):,} chars) — the template has grown; trim it, do not raise the budget"
        )

    def test_template_allowance(self):
        """Template + longest tone + fillers stays inside the 12k-char allowance."""
        empty = build_ca_prompt("", None, None, LONGEST_TONE_SUBJECT, "topic")
        assert (
            len(empty) <= 12_000
        ), f"template is {len(empty):,} chars (allowance 12,000)"

    def test_budget_is_under_groq_gate(self):
        """The tripwire must sit below the pool's Groq gate, or it guards nothing."""
        from engines.book_content.services.llm_service import PROVIDERS

        groq = next(spec for spec in PROVIDERS if spec.name == "groq")
        assert CA_PROMPT_TOKEN_BUDGET < groq.max_request_tokens

    def test_news_context_cap_unchanged(self):
        """D1: the data inputs are not reduced — the 6,000-char news cap stands."""
        assert CA_NEWS_CONTEXT_MAX_CHARS == 6_000
        prompt = build_ca_prompt(WORST_NEWS, None, None, "Indian Economy", "t")
        assert WORST_NEWS[:6_000] in prompt
        assert WORST_NEWS[:6_001] not in prompt


class TestRulesSurvivedTheRewrite:
    def test_every_mandatory_rule_present(self):
        prompt = _worst_case_prompt()
        missing = [rule for rule in MANDATORY_RULES if rule not in prompt]
        assert not missing, f"rules missing from the prompt: {missing}"

    def test_rules_stated_once(self):
        for phrase in STATED_ONCE:
            assert CA_DAILY_PROMPT_TEMPLATE.count(phrase) == 1, phrase

    def test_no_decorative_unicode_in_template(self):
        """Box-drawing and symbol characters tokenise badly and add nothing."""
        found = [ch for ch in NON_ASCII_DECORATION if ch in CA_DAILY_PROMPT_TEMPLATE]
        assert not found, found

    def test_no_literal_braces_left_for_format(self):
        """Every {placeholder} is filled — a stray brace would raise at generation time."""
        prompt = _worst_case_prompt()
        assert "{subject_" not in prompt
        assert "{ca_chunks_text}" not in prompt
        assert "{categories}" not in prompt

    def test_categories_in_sync_with_the_model(self):
        prompt = _worst_case_prompt()
        model_keys = {key for key, _label in NEWS_CATEGORY_CHOICES}
        assert set(_NEWS_CATEGORIES) == model_keys
        for key in _NEWS_CATEGORIES:
            assert key in prompt


class TestSubjectGuidance:
    def test_only_the_current_subjects_example_is_injected(self):
        economy = build_ca_prompt("news", None, None, "Indian Economy", "t")
        polity = build_ca_prompt(
            "news", None, None, "Indian Polity & Constitution", "t"
        )
        assert "repo rate" in economy and "precedent chain" not in economy
        assert "precedent chain" in polity and "repo rate" not in polity

    def test_structure_line_follows_the_paper(self):
        economy = build_ca_prompt("news", None, None, "Indian Economy", "t")
        polity = build_ca_prompt(
            "news", None, None, "Indian Polity & Constitution", "t"
        )
        ethics = build_ca_prompt(
            "news", None, None, "Ethics, Integrity & Aptitude", "t"
        )
        assert "data -> policy response -> gap" in economy
        assert "legal provision -> institutional interpretation" in polity
        assert "dilemma -> competing values" in ethics

    def test_unknown_subject_falls_back_without_error(self):
        bridge, structure = subject_guidance("Astrophysics")
        assert bridge == SUBJECT_BRIDGE_MAP["default"]
        assert "what -> why/how -> so what" in structure
        prompt = build_ca_prompt("news", None, None, "Astrophysics", "t")
        assert "SUBJECT: Astrophysics" in prompt

    def test_every_tone_subject_has_a_bridge_and_a_paper(self):
        """A subject with a tone but no example would silently get the generic one."""
        for subject in SUBJECT_TONE_MAP:
            if subject == "default":
                continue
            assert subject in SUBJECT_BRIDGE_MAP, subject
            _bridge, structure = subject_guidance(subject)
            assert "what -> why/how -> so what" not in structure, subject
