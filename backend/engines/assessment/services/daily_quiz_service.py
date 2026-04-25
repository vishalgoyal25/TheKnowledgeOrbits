"""
engines/assessment/services/daily_quiz_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Daily Public Quiz generator service.

Generates one public Quiz (10 questions) per day from today's approved
CaDailyProposal records — the same proposals used by DailyCaGeneratorService
to generate articles.  No NCERT/static chunks are involved here.

Source pipeline per question:
  1. Enriched CA context  — CAChunk text + parent CAArticle full content
                            (reused from daily_ca generator_service)
  2. Wikipedia background — WikiEnrichmentService (thin-source enrichment)
                            (reused from daily_ca wiki_enrichment_service)
  3. Source URLs          — CaDailyProposal.source_urls (from RSS scrape)
                            Appended to explanation programmatically after
                            parsing (not left to LLM — same pattern as
                            daily_ca _parse_response SOURCE: footer).

Quiz record:
  • is_public = True       — no auth required to attempt
  • created_by = None      — system-generated
  • topic = first proposal's topic (highest relevance — required FK, not nullable)
  • title = "Daily Current Affairs Quiz — DD Month YYYY"
  • include_ca = True
  • time_limit = 600 s (10 min for 10 questions)
  • generation_metadata stores pub_date + per-question proposal mapping

Idempotent: if a daily public quiz already exists for the target date,
generation is skipped and the existing quiz_id is returned.

Rate-limit: llm_call_json() already applies INTER_CALL_SLEEP (12 s).
Session cap: MAX_GROQ_CALLS = 15 (safety; 10 questions × 1 call each + retries).
"""

import json
import re
from datetime import date

import sentry_sdk
import structlog
from django.db import transaction
from django.utils import timezone

from engines.assessment.models import Question, Quiz
from engines.assessment.services.daily_quiz_prompt_builder import build_quiz_prompt

logger = structlog.get_logger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────
MAX_QUESTIONS = 10          # questions per daily quiz
MAX_GROQ_CALLS = 15         # session safety cap (10 questions + 5 retries)
QUIZ_TIME_LIMIT = 600       # 10 minutes in seconds
QUIZ_DIFFICULTY = "medium"  # daily quiz is always mixed medium


# ── Helpers ──────────────────────────────────────────────────────────────────


def _fetch_enriched_ca_context(
    ca_chunk_ids: list, db_alias: str = "default"
) -> tuple[str, int]:
    """
    Thin import-wrapper so we can mock this in tests without touching daily_ca.
    Delegates to the same function used by DailyCaGeneratorService.
    Returns (enriched_text, chunk_word_count).

    db_alias MUST match the alias used to fetch proposals — CA chunks live in
    the same database as the proposals (supabase in production).
    """
    from engines.daily_ca.services.generator_service import (
        _fetch_enriched_ca_context as _inner,
    )
    return _inner(ca_chunk_ids, db_alias=db_alias)


def _get_wiki_enrichment(topic_name: str) -> dict:
    """
    Thin import-wrapper around WikiEnrichmentService.
    Returns {} on any failure (never raises).
    """
    try:
        from engines.daily_ca.services.wiki_enrichment_service import (
            WikiEnrichmentService,
        )
        return WikiEnrichmentService.get_enrichment(topic_name)
    except Exception as exc:
        logger.warning("wiki_enrichment_failed", topic=topic_name, error=str(exc))
        return {}


def _strip_llm_source_lines(explanation: str) -> str:
    """
    Remove any 'Source:' line the LLM may have written in the explanation.
    We append the real URLs ourselves below.
    """
    return re.sub(r"\n?\s*Source\s*:\s*.+", "", explanation, flags=re.IGNORECASE).strip()


def _append_sources(explanation: str, source_urls: list) -> str:
    """
    Deterministically append verified source URLs to the explanation,
    same pattern as daily_ca _parse_response SOURCE: extraction.

    source_urls may be:
      - list of strings  (plain URLs)
      - list of dicts    {source_name, url, title}  ← CaDailyProposal format
    """
    if not source_urls:
        return explanation
    clean = _strip_llm_source_lines(explanation)
    urls = []
    for item in source_urls[:3]:
        if isinstance(item, dict):
            u = item.get("url", "")
        else:
            u = str(item)
        if u:
            urls.append(u)
    if not urls:
        return clean
    url_block = "\n".join(urls)
    return f"{clean}\n\nSource: {url_block}"


def _parse_question_json(raw: str, source_urls: list[str]) -> dict | None:
    """
    Parse and validate the LLM JSON response for a single question.

    Returns a clean question dict on success, None on validation failure.
    Programmatically appends source URLs to the explanation.
    """
    # Strip markdown fences if LLM added them
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).rstrip("`").strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("question_json_decode_failed", error=str(exc), raw=raw[:200])
        return None

    # Required fields
    question_text = (data.get("question_text") or "").strip()
    question_type = (data.get("question_type") or "single_mcq").strip()
    options = data.get("options") or {}
    correct_answer = (data.get("correct_answer") or "").strip().upper()
    explanation = (data.get("explanation") or "").strip()
    statements = data.get("statements") or []

    # Basic sanity checks
    if not question_text:
        logger.warning("question_missing_text")
        return None

    if question_type not in ("multi_statement", "assertion_reasoning", "single_mcq"):
        question_type = "single_mcq"

    if set(options.keys()) != {"A", "B", "C", "D"}:
        logger.warning("question_bad_options", keys=list(options.keys()))
        return None

    if correct_answer not in ("A", "B", "C", "D"):
        logger.warning("question_bad_correct_answer", value=correct_answer)
        return None

    if not explanation:
        explanation = "See source material for details."

    # Deterministic source URL injection
    explanation = _append_sources(explanation, source_urls)

    return {
        "question_text": question_text,
        "question_type": question_type,
        "statements": statements if isinstance(statements, list) else [],
        "options": options,
        "correct_answer": correct_answer,
        "explanation": explanation,
        "difficulty_level": QUIZ_DIFFICULTY,
    }


# ── Core service ──────────────────────────────────────────────────────────────


class DailyQuizGeneratorService:
    """
    Generates the Daily Public Quiz from today's approved CA proposals.

    Entry point: generate_daily_quiz(proposals, pub_date, db_alias)
    """

    @staticmethod
    def generate_daily_quiz(
        proposals: list,
        pub_date: date,  # datetime.date
        db_alias: str = "default",
    ) -> dict:
        """
        Main entry point.  Reads approved CaDailyProposal records and produces
        one public Quiz with up to MAX_QUESTIONS questions.

        Args:
            proposals:  Ordered list of CaDailyProposal instances
                        (status='approved' or 'generated', sorted by relevance DESC).
            pub_date:   Date for the quiz (usually today).
            db_alias:   'default' (local) or 'supabase' (production).

        Returns:
            {
              "quiz_id":   str | None,
              "generated": int,      # questions successfully created
              "failed":    int,      # proposals skipped due to LLM/parse errors
              "skipped":   bool,     # True if quiz for this date already existed
            }
        """
        date_label = pub_date.strftime("%d %B %Y")
        quiz_title = f"Daily Current Affairs Quiz — {date_label}"

        # ── Idempotency check ──────────────────────────────────────────────
        existing = Quiz.objects.using(db_alias).filter(
            title=quiz_title,
            is_public=True,
            created_by=None,
        ).first()

        if existing:
            logger.info(
                "daily_quiz_already_exists",
                quiz_id=str(existing.id),
                date=str(pub_date),
            )
            return {
                "quiz_id": str(existing.id),
                "generated": existing.question_count,
                "failed": 0,
                "skipped": True,
            }

        if not proposals:
            logger.warning("daily_quiz_no_proposals", date=str(pub_date))
            return {"quiz_id": None, "generated": 0, "failed": 0, "skipped": False}

        # ── Generate questions ─────────────────────────────────────────────
        questions_data: list[dict] = []
        failed = 0
        groq_calls_used = 0

        # Work through proposals until we have MAX_QUESTIONS or exhaust the list
        for proposal in proposals[:MAX_QUESTIONS]:
            if groq_calls_used >= MAX_GROQ_CALLS:
                logger.warning(
                    "daily_quiz_groq_cap_reached",
                    cap=MAX_GROQ_CALLS,
                    generated=len(questions_data),
                )
                break

            q_data = DailyQuizGeneratorService._generate_single_question(
                proposal, db_alias=db_alias
            )
            groq_calls_used += 1

            if q_data is None:
                failed += 1
                logger.warning(
                    "daily_quiz_question_failed",
                    proposal_id=str(proposal.id),
                    topic=getattr(proposal, "title", ""),
                )
                continue

            questions_data.append(q_data)
            logger.info(
                "daily_quiz_question_ok",
                order=len(questions_data),
                topic=getattr(proposal, "title", ""),
                q_type=q_data["question_type"],
            )

        if not questions_data:
            logger.error("daily_quiz_no_questions_generated", date=str(pub_date))
            sentry_sdk.capture_message(
                f"Daily quiz generation produced 0 questions for {pub_date}.",
                level="error",
            )
            return {"quiz_id": None, "generated": 0, "failed": failed, "skipped": False}

        # ── Persist ────────────────────────────────────────────────────────
        quiz = DailyQuizGeneratorService._save_quiz(
            questions_data=questions_data,
            proposals=proposals,
            quiz_title=quiz_title,
            pub_date=pub_date,
            db_alias=db_alias,
        )

        logger.info(
            "daily_quiz_generation_complete",
            quiz_id=str(quiz.id),
            date=str(pub_date),
            generated=len(questions_data),
            failed=failed,
        )

        return {
            "quiz_id": str(quiz.id),
            "generated": len(questions_data),
            "failed": failed,
            "skipped": False,
        }

    # ── Single-question generation ─────────────────────────────────────────

    @staticmethod
    def _generate_single_question(
        proposal, db_alias: str = "default"
    ) -> dict | None:
        """
        Generate one question from one CaDailyProposal.

        Steps:
          1. Fetch enriched CA context (reused from daily_ca generator_service)
          2. Fetch Wikipedia enrichment (reused from daily_ca wiki_enrichment_service)
          3. Build prompt
          4. Call LLM (llm_call_json, mode="quiz")
          5. Parse + validate JSON
          6. Attach source URLs deterministically

        db_alias must match where the proposals and CA chunks live.

        Returns cleaned question dict, or None on any failure.
        """
        from engines.book_content.services.llm_service import llm_call_json

        proposal_id = str(proposal.id)
        topic_name = getattr(proposal, "title", "")
        subject_name = getattr(proposal, "subject_name", "")
        ca_chunk_ids = getattr(proposal, "ca_chunk_ids", None) or []
        source_urls = getattr(proposal, "source_urls", None) or []

        # Resolve topic name: prefer the linked Topic.name if available
        try:
            if proposal.topic:
                topic_name = proposal.topic.name
        except Exception:
            pass  # keep proposal.title as fallback

        logger.info(
            "daily_quiz_generating_question",
            proposal_id=proposal_id,
            topic=topic_name,
            subject=subject_name,
        )

        # STEP 1: Enriched CA context — MUST use same db_alias as proposals
        try:
            ca_text, chunk_word_count = _fetch_enriched_ca_context(
                ca_chunk_ids, db_alias=db_alias
            )
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.error(
                "daily_quiz_ca_fetch_failed",
                proposal_id=proposal_id,
                error=str(exc),
            )
            return None

        if not ca_text:
            logger.warning("daily_quiz_empty_ca_context", proposal_id=proposal_id)
            return None

        # STEP 2: Wikipedia enrichment
        # Always fetch wiki — it provides the conceptual background layer
        # that replaces NCERT chunks in this pipeline.
        wiki_data = _get_wiki_enrichment(topic_name)

        # STEP 3: Build prompt
        prompt = build_quiz_prompt(
            ca_chunks_text=ca_text,
            wiki_enrichment=wiki_data,
            topic_name=topic_name,
            subject_name=subject_name,
            source_urls=source_urls if source_urls else None,
        )

        # STEP 4: LLM call
        try:
            raw_response = llm_call_json(
                prompt=prompt,
                system_prompt=(
                    "You are a senior competitive examination question setter. "
                    "Respond with valid JSON only — no markdown, no extra text."
                ),
                mode="quiz",
            )
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.error(
                "daily_quiz_llm_call_failed",
                proposal_id=proposal_id,
                error=str(exc),
            )
            return None

        if not raw_response:
            logger.warning("daily_quiz_empty_llm_response", proposal_id=proposal_id)
            return None

        # STEP 5: Parse, validate, attach source URLs
        q_data = _parse_question_json(raw_response, source_urls)
        if q_data is None:
            logger.warning(
                "daily_quiz_parse_failed",
                proposal_id=proposal_id,
                raw=raw_response[:300],
            )
            return None

        # Store the proposal id for DB linking later
        q_data["_proposal_id"] = proposal_id
        q_data["_ca_chunk_ids"] = ca_chunk_ids

        return q_data

    # ── DB persistence ─────────────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def _save_quiz(
        questions_data: list[dict],
        proposals: list,
        quiz_title: str,
        pub_date: date,
        db_alias: str,
    ) -> Quiz:
        """
        Atomically create Quiz + Question records.

        Quiz.topic is a required (non-nullable) FK.
        We use the first (highest-relevance) proposal's topic as the
        representative topic — the quiz title makes the cross-topic nature clear.

        Questions are linked to their source CAChunks via source_ca_chunks M2M.
        """
        from engines.current_affairs.models import CAChunk

        # Determine representative topic (required FK — not nullable)
        representative_topic = None
        for p in proposals:
            try:
                if p.topic:
                    representative_topic = p.topic
                    break
            except Exception:
                continue

        if representative_topic is None:
            raise ValueError(
                "No valid topic found among proposals — cannot create Quiz record."
            )

        quiz = Quiz.objects.using(db_alias).create(
            title=quiz_title,
            topic=representative_topic,
            difficulty_level=QUIZ_DIFFICULTY,
            include_ca=True,
            is_public=True,
            created_by=None,
            question_count=len(questions_data),
            time_limit=QUIZ_TIME_LIMIT,
            generation_metadata={
                "pub_date": str(pub_date),
                "source": "daily_ca_proposals",
                "model": "llm_pool",
                "generated_at": timezone.now().isoformat(),
                "proposal_count": len(proposals),
                "questions_generated": len(questions_data),
            },
        )

        logger.info("daily_quiz_record_created", quiz_id=str(quiz.id))

        for idx, q_data in enumerate(questions_data):
            q_data.pop("_proposal_id", None)   # internal tracking key — not a DB field
            ca_chunk_ids = q_data.pop("_ca_chunk_ids", [])

            question = Question.objects.using(db_alias).create(
                quiz=quiz,
                question_text=q_data["question_text"],
                question_type=q_data["question_type"],
                statements=q_data["statements"],
                options=q_data["options"],
                correct_answer=q_data["correct_answer"],
                explanation=q_data["explanation"],
                difficulty_level=q_data["difficulty_level"],
                order_index=idx,
            )

            # Link source CA chunks for attribution
            if ca_chunk_ids:
                try:
                    ca_chunks = CAChunk.objects.using(db_alias).filter(
                        id__in=ca_chunk_ids
                    )
                    question.source_ca_chunks.set(ca_chunks)
                except Exception as exc:
                    # Attribution failure must never abort quiz creation
                    sentry_sdk.capture_exception(exc)
                    logger.warning(
                        "daily_quiz_ca_chunk_link_failed",
                        question_id=str(question.id),
                        error=str(exc),
                    )

        logger.info(
            "daily_quiz_questions_created",
            count=len(questions_data),
            quiz_id=str(quiz.id),
        )

        return quiz
