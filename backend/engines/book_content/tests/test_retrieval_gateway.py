"""
engines/book_content/tests/test_retrieval_gateway.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 6 — Unit tests for the RAG grounding gateway (retrieve_grounding + helpers).

Covers the NEW logic from P1/P5 WITHOUT touching the DB or the HF embedding API:
  • pure helpers: _build_seed_query, _rrf_merge, _format_grounding_context
  • slot adapters: as_static_facts, as_wiki_enrichment
  • retrieve_grounding guard / graceful-failure branches (embedding mocked)

The happy-path retrieval (real data + embeddings) is covered by the
`inspect_retrieval` management command + manual shell verification — those need
a live corpus and the HF model, so they are intentionally out of scope here.

All tests use SimpleTestCase (no DB) and run fast in CI.
"""

from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from engines.book_content.services import retrieval_service as rs


class BuildSeedQueryTests(SimpleTestCase):
    def test_explicit_query_only(self):
        self.assertEqual(rs._build_seed_query(None, "Union Budget"), "Union Budget")

    def test_seed_topic_fields_combined(self):
        topic = SimpleNamespace(
            name="Fiscal Federalism",
            description="Centre-State finance",
            keywords=["taxes", "devolution"],
        )
        q = rs._build_seed_query(topic, None)
        self.assertIn("Fiscal Federalism", q)
        self.assertIn("Centre-State finance", q)
        self.assertIn("taxes", q)

    def test_empty_inputs_return_empty_string(self):
        self.assertEqual(rs._build_seed_query(None, None), "")
        self.assertEqual(rs._build_seed_query(None, "   "), "")


class RrfMergeTests(SimpleTestCase):
    @staticmethod
    def _chunk(cid, ctype="book_chunk"):
        return {
            "content_type": ctype,
            "id": cid,
            "text": f"t{cid}",
            "topic": "",
            "subject": "",
            "score": 0.5,
        }

    def test_dedup_and_cap(self):
        lane_a = [self._chunk("1"), self._chunk("2"), self._chunk("3")]
        lane_b = [self._chunk("2"), self._chunk("4")]  # "2" appears in both lanes
        merged = rs._rrf_merge([lane_a, lane_b], cap=3)
        ids = [c["id"] for c in merged]
        self.assertEqual(len(ids), 3)
        self.assertEqual(len(set(ids)), 3)  # no duplicates
        self.assertEqual(ids[0], "2")  # in both lanes → fuses to the top

    def test_empty_lanes(self):
        self.assertEqual(rs._rrf_merge([[], []], cap=4), [])


class AdapterTests(SimpleTestCase):
    @staticmethod
    def _grounding():
        return {
            "query": "Fundamental Rights",
            "book_chunks": [
                {
                    "content_type": "book_chunk",
                    "id": "a",
                    "text": "Article 21 guarantees right to life. It allocates ₹500 crore and covers 35% of cases.",
                    "topic": "Fundamental Rights",
                    "subject": "Indian Polity & Constitution",
                    "score": 0.7,
                },
                {
                    "content_type": "book_chunk",
                    "id": "b",
                    "text": "Section 66A was struck down. The provision affected 20 percent of users.",
                    "topic": "IT Act",
                    "subject": "Indian Polity & Constitution",
                    "score": 0.6,
                },
            ],
            "ca_chunks": [],
        }

    def test_as_static_facts_shape_and_extraction(self):
        facts = rs.as_static_facts(self._grounding(), title="Fundamental Rights")
        self.assertEqual(facts["title"], "Fundamental Rights")
        self.assertGreaterEqual(len(facts["key_facts"]), 1)
        # Article/Section sentences are pulled into key_provisions
        self.assertTrue(any("Article 21" in p for p in facts["key_provisions"]))
        # Figures / percentages are pulled into statistics
        self.assertTrue(
            any(("%" in s) or ("percent" in s) or ("crore" in s) for s in facts["statistics"])
        )

    def test_as_static_facts_empty_grounding(self):
        facts = rs.as_static_facts({"book_chunks": []}, title="X")
        self.assertEqual(facts["key_facts"], [])
        self.assertEqual(facts["key_provisions"], [])
        self.assertEqual(facts["statistics"], [])

    def test_as_wiki_enrichment_shape(self):
        w = rs.as_wiki_enrichment(self._grounding())
        self.assertTrue(w["intro"])  # first book chunk → intro
        self.assertIsInstance(w["key_facts"], list)
        self.assertIn("Fundamental Rights", w["related_terms"])
        self.assertEqual(w["wiki_url"], "")  # RAG grounding carries no wiki URL

    def test_as_wiki_enrichment_falls_back_to_ca(self):
        g = {
            "book_chunks": [],
            "ca_chunks": [
                {
                    "content_type": "ca_chunk",
                    "id": "c",
                    "text": "Recent news text about the topic.",
                    "topic": "News",
                    "subject": "The Hindu",
                    "score": 0.6,
                }
            ],
        }
        w = rs.as_wiki_enrichment(g)
        self.assertTrue(w["intro"])  # intro falls back to CA when no book chunks


class FormatContextTests(SimpleTestCase):
    def test_includes_section_labels_and_text(self):
        book = [
            {
                "content_type": "book_chunk",
                "id": "a",
                "text": "Theory body.",
                "topic": "Topic A",
                "subject": "Polity",
                "score": 0.7,
            }
        ]
        ca = [
            {
                "content_type": "ca_chunk",
                "id": "c",
                "text": "News body.",
                "topic": "Headline",
                "subject": "The Hindu",
                "date": "2026-06-01",
                "score": 0.6,
            }
        ]
        out = rs._format_grounding_context(book, ca)
        self.assertIn("Knowledge Base", out)
        self.assertIn("Topic A", out)
        self.assertIn("Current Affairs", out)
        self.assertIn("Theory body.", out)

    def test_empty(self):
        self.assertEqual(rs._format_grounding_context([], []), "")


class RetrieveGroundingGuardTests(SimpleTestCase):
    def test_no_query_no_seed_returns_empty(self):
        result = rs.retrieve_grounding(query=None, seed_topic_id=None)
        self.assertEqual(result["stats"]["returned"], 0)
        self.assertEqual(result["chunks"], [])

    @mock.patch.object(rs, "_grounding_query_embedding", return_value=None)
    def test_embedding_unavailable_returns_empty(self, _mock_embed):
        result = rs.retrieve_grounding(query="anything", seed_topic_id=None)
        self.assertEqual(result["chunks"], [])
        self.assertEqual(result["query"], "anything")

    @mock.patch.object(
        rs, "_grounding_query_embedding", side_effect=RuntimeError("boom")
    )
    def test_unexpected_error_never_raises(self, _mock_embed):
        # The gateway must always degrade gracefully → empty result, never raise.
        result = rs.retrieve_grounding(query="anything", seed_topic_id=None)
        self.assertEqual(result["stats"]["returned"], 0)
        self.assertEqual(result["chunks"], [])
