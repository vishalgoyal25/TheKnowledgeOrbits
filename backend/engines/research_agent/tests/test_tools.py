"""
engines/research_agent/tests/test_tools.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tests for the tool layer (all deterministic, no network):

  - CalculatorTool   — safe arithmetic, rejects unsafe/oversized expressions
  - DomainClassifier — keyword → UPSC domain, general fallback
  - CredibilityScorer — domain-tier scoring, filter + sort
  - TavilyTool._parse_results — content cap, url drop, source tag (pure parse)
  - ToolRegistry     — get() / get_search_chain() / KeyError on unknown
"""

from __future__ import annotations

import pytest

from engines.research_agent.tools.calculator_tool import CalculatorError, CalculatorTool
from engines.research_agent.tools.credibility_scorer import CredibilityScorer
from engines.research_agent.tools.domain_classifier import (
    DOMAIN_CURRENT_AFFAIRS,
    DOMAIN_ECONOMY,
    DOMAIN_GENERAL,
    DOMAIN_GEOGRAPHY,
    DOMAIN_POLITY,
    DOMAIN_SCIENCE,
    DomainClassifier,
)
from engines.research_agent.tools.registry import ToolRegistry
from engines.research_agent.tools.tavily_tool import MAX_CONTENT_CHARS, TavilyTool


# ── CalculatorTool ───────────────────────────────────────────────────────────


class TestCalculatorTool:
    def setup_method(self):
        self.calc = CalculatorTool()

    def test_basic_arithmetic(self):
        assert self.calc.calculate("2 + 3 * 4") == "14"

    def test_percentage_style(self):
        assert self.calc.calculate("3.5e12 * 0.15") == "525000000000"

    def test_integer_result_has_no_decimal(self):
        assert self.calc.calculate("10 / 2") == "5"

    def test_division_by_zero_raises(self):
        with pytest.raises(CalculatorError):
            self.calc.calculate("1 / 0")

    def test_empty_expression_raises(self):
        with pytest.raises(CalculatorError):
            self.calc.calculate("   ")

    def test_unsafe_expression_rejected(self):
        # Names / calls are not in the AST whitelist.
        with pytest.raises(CalculatorError):
            self.calc.calculate("__import__('os').system('ls')")

    def test_too_long_expression_rejected(self):
        with pytest.raises(CalculatorError):
            self.calc.calculate("1+" * 200 + "1")


# ── DomainClassifier ─────────────────────────────────────────────────────────


class TestDomainClassifier:
    def setup_method(self):
        self.clf = DomainClassifier()

    @pytest.mark.parametrize(
        "query,expected",
        [
            ("Powers of the President under the Constitution", DOMAIN_POLITY),
            ("Impact of inflation on GDP and fiscal deficit", DOMAIN_ECONOMY),
            ("Monsoon rainfall over the Western Ghats rivers", DOMAIN_GEOGRAPHY),
            ("ISRO satellite launch and quantum physics", DOMAIN_SCIENCE),
            ("Latest 2025 budget news update", DOMAIN_CURRENT_AFFAIRS),
        ],
    )
    def test_keyword_domains(self, query, expected):
        assert self.clf.classify(query) == expected

    def test_general_fallback(self):
        assert self.clf.classify("Tell me an interesting story") == DOMAIN_GENERAL

    def test_case_insensitive(self):
        assert self.clf.classify("CONSTITUTION of india") == DOMAIN_POLITY


# ── CredibilityScorer ────────────────────────────────────────────────────────


class TestCredibilityScorer:
    def setup_method(self):
        self.scorer = CredibilityScorer()

    def test_tier1_government(self):
        assert self.scorer.score("https://rbi.org.in/page") == 0.95

    def test_tier2_news(self):
        assert self.scorer.score("https://www.thehindu.com/article") == 0.80

    def test_tier3_reference(self):
        assert self.scorer.score("https://en.wikipedia.org/wiki/India") == 0.55

    def test_tier4_social_is_low(self):
        assert self.scorer.score("https://twitter.com/someone/status/1") == 0.15

    def test_unknown_domain_default(self):
        assert self.scorer.score("https://some-random-blog.xyz/post") == 0.4

    def test_edu_tld_authoritative(self):
        assert self.scorer.score("https://mit.edu/research") == 0.90

    def test_empty_url_returns_default(self):
        assert self.scorer.score("") == 0.4

    def test_score_sources_filters_and_sorts(self):
        sources = [
            {"url": "https://twitter.com/x", "title": "tweet"},  # 0.15 → filtered
            {"url": "https://rbi.org.in/a", "title": "rbi"},  # 0.95
            {"url": "https://en.wikipedia.org/x", "title": "wiki"},  # 0.55
        ]
        out = self.scorer.score_sources(sources)
        # Low-credibility social source dropped.
        assert all("twitter.com" not in s["url"] for s in out)
        # Sorted highest-first; each enriched with credibility_score.
        assert out[0]["credibility_score"] == 0.95
        assert out[-1]["credibility_score"] == 0.55


# ── TavilyTool._parse_results (pure parse, no network) ───────────────────────


class TestTavilyParse:
    def setup_method(self):
        self.tool = TavilyTool()

    def test_content_truncated_and_tagged(self):
        response = {
            "results": [
                {
                    "url": "https://x.com/a",
                    "title": "T",
                    "content": "z" * 5000,
                    "score": 0.5,
                },
            ]
        }
        parsed = self.tool._parse_results(response)
        assert len(parsed) == 1
        assert len(parsed[0]["content"]) == MAX_CONTENT_CHARS
        assert parsed[0]["source"] == "tavily"

    def test_result_without_url_dropped(self):
        response = {"results": [{"title": "no url", "content": "x"}]}
        assert self.tool._parse_results(response) == []

    def test_caps_to_three_results(self):
        response = {
            "results": [{"url": f"https://x/{i}", "title": str(i)} for i in range(10)]
        }
        assert len(self.tool._parse_results(response)) == 3


# ── ToolRegistry ─────────────────────────────────────────────────────────────


class TestToolRegistry:
    def test_get_known_tool(self):
        registry = ToolRegistry()
        assert isinstance(registry.get("domain"), DomainClassifier)

    def test_get_unknown_raises_keyerror(self):
        registry = ToolRegistry()
        with pytest.raises(KeyError):
            registry.get("does_not_exist")

    def test_search_chain_is_three_tools(self):
        registry = ToolRegistry()
        chain = registry.get_search_chain()
        assert len(chain) == 3

    def test_get_all_has_six_tools(self):
        registry = ToolRegistry()
        assert set(registry.get_all().keys()) == {
            "tavily",
            "exa",
            "wikipedia",
            "calculator",
            "domain",
            "credibility",
        }
