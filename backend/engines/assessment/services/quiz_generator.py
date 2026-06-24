import sentry_sdk

"""
Quiz Generator Service

RAG-based quiz generation combining static textbooks and current affairs.
Reuses patterns from ArticleGenerationService for consistency.

Key Features:
- Dual-source chunk retrieval (static + CA)
- UPSC-authentic question formats (multi-statement, assertion-reasoning)
- Detailed explanations with source citations
- Groq LLM integration for generation
"""

import json
from datetime import timedelta
from typing import Any, Dict, List, Optional

import structlog
from django.db import transaction
from django.utils import timezone

from engines.assessment.models import Question, Quiz
from engines.book_content.services.retrieval_service import retrieve_grounding
from engines.content.models import Chunk
from engines.current_affairs.models import CAChunk
from engines.knowledge.models import ChunkTopicMap, Topic

logger = structlog.get_logger(__name__)


class QuizGeneratorService:
    """
    Service for generating UPSC-style quizzes from chunks using RAG.
    """

    # Constants
    MAX_STATIC_CHUNKS = 10
    MAX_CA_CHUNKS = 5
    CA_RELEVANCE_DAYS = 60

    def __init__(self) -> Any:  # type: ignore
        """Initialize quiz generator — LLM calls routed via shared llm_service pool."""
        pass

    def generate_quiz(
        self,
        topic_id: str,
        difficulty: str = "medium",
        include_ca: bool = False,
        question_count: int = 10,
        user_id: Optional[Any] = None,
    ) -> Quiz:
        """
        Generate a complete quiz for a topic.

        Args:
            topic_id: UUID of target topic
            difficulty: 'easy', 'medium', or 'hard'
            include_ca: Whether to include Current Affairs (Hybrid Mode)
            question_count: Number of questions to generate (1-20)
            user_id: User requesting generation (for logging)

        Returns:
            Generated Quiz instance with all questions

        Raises:
            ValueError: If topic not found or no chunks available
            Exception: If Groq generation fails
        """
        logger.info(
            "quiz_generation_requested",
            topic_id=topic_id,
            difficulty=difficulty,
            include_ca=include_ca,
            question_count=question_count,
            user_id=user_id,
        )

        try:
            # Step 1: Get topic
            topic = Topic.objects.get(id=topic_id)
            logger.info("topic_found", topic_name=topic.name, topic_id=topic_id)

            # Step 2: Fetch chunks
            static_chunks = self._fetch_static_chunks(topic)
            ca_chunks = self._fetch_ca_chunks(topic) if include_ca else []

            # Phase 5 — RAG grounding from the book corpus (publish-agnostic, semantic
            # + cross-subject) replaces reliance on the dead NCERT content.Chunk path.
            # k_ca=0 — CA handled above via the hybrid _fetch_ca_chunks. Appended to
            # context; provenance stored on the quiz post-save.
            grounding = retrieve_grounding(
                seed_topic_id=topic.id, query=topic.name, k_ca=0
            )

            if not static_chunks and not ca_chunks and not grounding.get("book_chunks"):
                raise ValueError(f"No chunks available for topic: {topic.name}")

            logger.info(
                "chunks_retrieved",
                static_count=len(static_chunks),
                ca_count=len(ca_chunks),
                rag_book_chunks=len(grounding.get("book_chunks", [])),
                topic_id=topic_id,
            )

            # Step 3: Build RAG context (chunks + retrieved knowledge-base theory)
            context = self._build_context(static_chunks, ca_chunks, include_ca)
            if grounding.get("context_text"):
                context = (context + "\n\n" + grounding["context_text"]).strip()

            # Step 4: Generate questions via Groq
            questions_data = self._generate_questions_with_groq(
                context=context,
                topic_name=topic.name,
                difficulty=difficulty,
                question_count=question_count,
                include_ca=include_ca,
            )

            # Step 5: Create quiz and questions in database
            quiz = self._create_quiz_in_db(
                topic=topic,
                questions_data=questions_data,
                static_chunks=static_chunks,
                ca_chunks=ca_chunks,
                difficulty=difficulty,
                include_ca=include_ca,
            )

            # Phase 5 — record RAG grounding provenance. book_chunk can't go in the
            # content.Chunk-typed source_static_chunks M2M, so it lives in metadata.
            if grounding.get("book_chunks"):
                quiz.generation_metadata["rag_grounding"] = grounding.get("stats", {})
                quiz.generation_metadata["rag_provenance"] = grounding.get(
                    "provenance", []
                )
                quiz.save(update_fields=["generation_metadata"])

            logger.info(
                "quiz_generation_successful",
                quiz_id=str(quiz.id),
                question_count=len(questions_data),
                topic_id=topic_id,
            )

            return quiz

        except Topic.DoesNotExist:
            logger.error("topic_not_found", topic_id=topic_id)
            raise ValueError(f"Topic with ID {topic_id} not found")

        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(
                "quiz_generation_failed",
                error=str(e),
                topic_id=topic_id,
                exc_info=True,
            )
            raise

    def _fetch_static_chunks(self, topic: Topic) -> List[Chunk]:
        """
        Fetch static (textbook) chunks mapped to topic.

        Args:
            topic: Target Topic instance

        Returns:
            List of Chunk instances ordered by relevance
        """
        # Get chunk IDs via ChunkTopicMap (Knowledge Engine)
        chunk_ids = (
            ChunkTopicMap.objects.filter(topic=topic)
            .order_by("-relevance_score")[: self.MAX_STATIC_CHUNKS]
            .values_list("chunk_id", flat=True)
        )

        # Fetch actual chunks
        chunks = (
            Chunk.objects.filter(
                id__in=chunk_ids,
                source_type="static",
                quality_flag__in=["high", "medium"],
            )
            .select_related("document")
            .order_by("chunk_index")
        )

        return list(chunks)

    def _fetch_ca_chunks(self, topic: Topic) -> List[CAChunk]:
        """
        Fetch recent Current Affairs chunks linked to topic using Hybrid Strategy.
        1. DB Links (Primary): High precision, manual/system tags
        2. Vector Search (Secondary): Discovery of untagged but relevant content

        Args:
            topic: Target Topic instance

        Returns:
            List of CAChunk instances from last 60 days
        """
        # Calculate cutoff date
        cutoff_date = timezone.now() - timedelta(days=self.CA_RELEVANCE_DAYS)

        # --- STRATEGY 1: Strict Database Links (Existing) ---
        linked_ca_chunks = list(
            CAChunk.objects.filter(
                topic_links__topic=topic,
                published_at__gte=cutoff_date,
                is_expired=False,
                quality_flag__in=["high", "medium"],
            )
            .select_related("ca_article__source")
            .order_by("-topic_links__relevance_score")[: self.MAX_CA_CHUNKS]
        )

        # If we have enough chunks, return them
        if len(linked_ca_chunks) >= self.MAX_CA_CHUNKS:
            return linked_ca_chunks

        # --- STRATEGY 2: Semantic Vector Search (Fill the gap) ---
        try:
            from pgvector.django import CosineDistance

            from engines.content.models import Embedding
            from engines.content.services.embedding_service import EmbeddingService

            # Generate topic embedding
            query_vector = EmbeddingService.generate_embedding(topic.name)

            # Find similar CA chunks
            # Filter by date and distance < 0.65 (slightly looser than strict search to find related news)
            sem_embeddings = (
                Embedding.objects.annotate(
                    distance=CosineDistance("vector", query_vector)
                )
                .filter(content_type="ca_chunk", distance__lt=0.65)
                .order_by("distance")[:10]
            )  # Get a few candidates

            # Get candidate IDs
            candidate_ids = [emb.content_id for emb in sem_embeddings]

            # Filter candidates by date and exclude already found
            existing_ids = {c.id for c in linked_ca_chunks}

            semantic_chunks = (
                CAChunk.objects.filter(
                    id__in=candidate_ids,
                    published_at__gte=cutoff_date,
                    is_expired=False,
                )
                .exclude(id__in=existing_ids)
                .select_related("ca_article__source")
            )

            # Add semantic chunks to fill quota
            needed = self.MAX_CA_CHUNKS - len(linked_ca_chunks)
            linked_ca_chunks.extend(list(semantic_chunks)[:needed])

        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.warning(
                "semantic_ca_fetch_failed",
                topic_name=topic.name,
                error=str(e),
                exc_info=True,
            )
            # Fallback: just return what we have from links

        # Final sort by date for context flow
        linked_ca_chunks.sort(key=lambda x: x.published_at, reverse=True)

        return linked_ca_chunks

    def _build_context(
        self, static_chunks: List[Chunk], ca_chunks: List[CAChunk], include_ca: bool
    ) -> str:
        """
        Build RAG context from chunks.

        Mimics ArticleGenerationService._assemble_context for consistency.

        Args:
            static_chunks: List of static Chunk instances
            ca_chunks: List of CAChunk instances
            include_ca: Whether CA chunks are included

        Returns:
            Formatted context string with sections
        """
        context_parts = []

        # Section 1: Theoretical Foundation (Static Chunks)
        if static_chunks:
            context_parts.append(
                "=== THEORETICAL FOUNDATION (TEXTBOOK KNOWLEDGE) ===\n"
            )

            for idx, chunk in enumerate(static_chunks, 1):
                source_info = f"[Source: {chunk.document.title}"
                if chunk.page_number:
                    source_info += f", Page {chunk.page_number}"
                if chunk.chapter_name:
                    source_info += f", Chapter: {chunk.chapter_name}"
                source_info += "]"

                context_parts.append(f"\n[Chunk {idx}] {source_info}")
                context_parts.append(chunk.chunk_text)
                context_parts.append("---")

        # Section 2: Current Developments (CA Chunks)
        if include_ca and ca_chunks:
            context_parts.append("\n=== CURRENT DEVELOPMENTS (RECENT NEWS) ===\n")

            for idx, ca_chunk in enumerate(ca_chunks, 1):
                source_info = f"[Source: {ca_chunk.ca_article.source.name}"
                source_info += f" - '{ca_chunk.ca_article.title}'"
                source_info += (
                    f", Published: {ca_chunk.published_at.strftime('%d %b %Y')}]"
                )

                context_parts.append(f"\n[CA Chunk {idx}] {source_info}")
                context_parts.append(ca_chunk.chunk_text)
                context_parts.append("---")

        return "\n".join(context_parts)

    def _generate_questions_with_groq(
        self,
        context: str,
        topic_name: str,
        difficulty: str,
        question_count: int,
        include_ca: bool,
    ) -> List[Dict[str, Any]]:
        """
        Generate questions using Groq LLM with batching to avoid token limits.

        Args:
            context: RAG context assembled from chunks
            topic_name: Name of topic for contextual prompting
            difficulty: 'easy', 'medium', or 'hard'
            question_count: Total questions to generate
            include_ca: Whether CA is included

        Returns:
            List of question dictionaries
        """
        all_questions = []
        BATCH_SIZE = 5
        generated_count = 0

        logger.info(
            "batched_generation_started",
            total_questions=question_count,
            batch_size=BATCH_SIZE,
            topic=topic_name,
        )

        # Loop until we have enough questions
        while generated_count < question_count:
            # Determine size of current batch
            remaining = question_count - generated_count
            current_batch_size = min(BATCH_SIZE, remaining)

            logger.info(
                "generating_question_batch",
                current_batch_size=current_batch_size,
                progress=f"{generated_count}/{question_count}",
            )

            try:
                # Build specialized prompt for this batch
                prompt = self._build_groq_prompt(
                    context=context,
                    topic_name=topic_name,
                    difficulty=difficulty,
                    question_count=current_batch_size,
                    include_ca=include_ca,
                )

                # Call shared LLM pool (round-robin, all providers)
                from engines.book_content.services.llm_service import llm_call_json

                response_text = llm_call_json(
                    prompt=prompt,
                    system_prompt="You are an expert UPSC question creator. Generate response in valid JSON format only.",
                    mode="quiz",
                )

                # Clean response (remove markdown if present)
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.startswith("```"):
                    response_text = response_text[3:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                response_text = response_text.strip()

                # Parse JSON
                data = json.loads(response_text)
                batch_questions = data.get("questions", [])

                if not batch_questions:
                    logger.warning("No questions found in batch response")
                    # If we fail to get questions, avoid infinite loop
                    if current_batch_size == 1:
                        break  # Give up if even 1 question fails
                    continue  # Retry or proceed? proceed might result in partial quiz

                all_questions.extend(batch_questions)
                generated_count += len(batch_questions)

                logger.info(
                    "batch_generation_successful",
                    batch_questions_count=len(batch_questions),
                    total_so_far=len(all_questions),
                )

            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing failed for batch: {str(e)}")
                # If a batch fails, we might return partial results or fail completely
                # For now, let's stop and return what we have to avoid crashing?
                # Or better, log and try to continue if we haven't hit limit?
                # Actually, raising error is safer than creating broken quiz
                if not all_questions:
                    raise ValueError(f"Invalid JSON from Groq: {str(e)}")
                break

            except Exception as e:
                sentry_sdk.capture_exception(e)
                logger.error(
                    "groq_api_call_failed",
                    error=str(e),
                    exc_info=True,
                    questions_generated=len(all_questions),
                )
                if not all_questions:
                    raise
                break

        if not all_questions:
            raise ValueError("Failed to generate any questions")

        return all_questions[:question_count]

    def _build_groq_prompt(
        self,
        context: str,
        topic_name: str,
        difficulty: str,
        question_count: int,
        include_ca: bool,
    ) -> str:
        """
        Build specialized Groq prompt for UPSC question generation.

        Args:
            context: RAG context assembled from chunks
            topic_name: Topic name
            difficulty: 'easy', 'medium', or 'hard'
            question_count: Number of questions to generate
            include_ca: Whether CA chunks are included

        Returns:
            Complete prompt string
        """
        mode_label = (
            "HYBRID (Textbook Theory + Current Affairs)"
            if include_ca
            else "STATIC (Textbook Theory Only)"
        )

        difficulty_guide = {
            "easy": (
                "Easy: Direct factual recall from a single chunk. "
                "Test basic definitions, names, or provisions. "
                "Use single_mcq or a straightforward 3-statement multi_statement."
            ),
            "medium": (
                "Medium: Require understanding of relationships between 2–3 concepts. "
                "Test application of principles, not just recall. "
                "Mix single_mcq, multi_statement (3–4 stmts), and assertion_reasoning."
            ),
            "hard": (
                "Hard: Require synthesis across multiple chunks. "
                "Use multi-statement (4–5 statements) or nuanced assertion-reason pairs. "
                "Distractors must be highly plausible. Correct answer non-obvious."
            ),
        }
        difficulty_instruction = difficulty_guide.get(
            difficulty, difficulty_guide["medium"]
        )

        if include_ca:
            strategy = (
                "HYBRID MODE: Each question should force the student to connect "
                "textbook theory with the current affairs context in the source. "
                "The best questions make the news event the 'hook' and the theoretical "
                "concept the 'depth' — a student who read the news but doesn't know the "
                "theory (or vice versa) should struggle. Vary the question type across "
                "the batch: do not make all questions the same format."
            )
        else:
            strategy = (
                "STATIC MODE: Questions test conceptual understanding from textbook "
                "material only. Focus on definitions, mechanisms, provisions, and "
                "relationships between concepts. Avoid any reference to recent events. "
                "Vary the question type across the batch for richness."
            )

        prompt = f"""You are a senior question setter for India's most competitive examinations.
Generate {question_count} original, challenging questions about "{topic_name}".

=== SOURCE MATERIAL ===
{context}

=== PARAMETERS ===
Topic      : {topic_name}
Difficulty : {difficulty}
Mode       : {mode_label}
Count      : {question_count}

=== STRATEGY ===
{strategy}

=== DIFFICULTY CALIBRATION ===
{difficulty_instruction}

=== QUESTION TYPES — use a diverse mix across the {question_count} questions ===

TYPE 1 — MULTI-STATEMENT (3 to 5 statements)
  "Consider the following statements regarding [subject]:
  1. [Statement]  2. [Statement]  3. [Statement]  [4. optional]  [5. optional]
  Which of the above statements is/are correct?"
  OR: "How many of the above statements are correct?"

  Options for combination-style:
    Use UPSC-authentic combinations: "1 only", "2 and 3 only", "1 and 3 only",
    "2, 3 and 4 only", "All of the above", "None of the above", etc.
  Options for count-style ("How many"):
    A: Only one   B: Only two   C: Only three   D: All four / All five

  — Number of correct statements is YOUR choice each time. Vary it freely:
    sometimes only 1 is correct, sometimes all are, sometimes 2 of 5.
  — "All of the above" and "None of the above" are valid correct answers.
  — Exactly ONE option must be unambiguously correct.

TYPE 2 — ASSERTION-REASON
  "Assertion (A): [precise factual or causal claim]
   Reason    (R): [claim intended to explain A]"

  Options (always these four for this type):
    A: Both A and R are true, and R is the correct explanation of A
    B: Both A and R are true, but R is NOT the correct explanation of A
    C: A is true but R is false
    D: A is false but R is true

TYPE 3 — SINGLE BEST ANSWER
  A direct question with one clearly correct answer and three plausible distractors.
  Best when the source material has one specific verifiable fact to test.
  Distractors must be factually close — not obviously wrong.

=== EXPLANATION FORMAT (shown to users after submission) ===

For MULTI-STATEMENT:
  Statement 1: CORRECT/INCORRECT — [one sentence with the exact fact and source]
  Statement 2: CORRECT/INCORRECT — [one sentence with the exact fact and source]
  ... (repeat for each statement)
  Therefore, correct answer is [X]: [option text].

For ASSERTION-REASON:
  Assertion: CORRECT/INCORRECT — [brief factual justification]
  Reason: CORRECT/INCORRECT — [brief factual justification]
  Relationship: [one sentence on whether R explains A]
  Therefore, correct answer is [X].

For SINGLE BEST ANSWER:
  Option A: correct/incorrect — [one line why]
  Option B: correct/incorrect — [one line why]
  Option C: correct/incorrect — [one line why]
  Option D: correct/incorrect — [one line why]
  Therefore, correct answer is [X].

Rules: 80–160 words. Every wrong statement/option gets a one-line factual rebuttal
with the correct fact stated explicitly. No exam-language, no "this tests...".

=== ABSOLUTE RULES ===
1. Generate EXACTLY {question_count} questions — no more, no less.
2. Use ONLY facts present in the source material above. No fabrication.
3. Each question must use a different question type where possible.
4. Correct answer must not be predictable from the question format.
5. correct_answer must be exactly one of: "A", "B", "C", "D".
6. For multi_statement questions, "statements" array must match the numbered
   statements in question_text (one entry per statement, no numbering in the string).
7. For assertion_reasoning, "statements" must be exactly two entries:
   ["Assertion: ...", "Reason: ..."].
8. For single_mcq, "statements" must be an empty list [].

=== OUTPUT FORMAT — valid JSON only, no markdown, no preamble ===

{{
  "questions": [
    {{
      "question_text": "[full question text including numbered statements if multi_statement]",
      "question_type": "multi_statement" | "assertion_reasoning" | "single_mcq",
      "statements": ["[stmt 1]", "[stmt 2]", "[stmt 3 optional]", "[stmt 4 optional]", "[stmt 5 optional]"],
      "options": {{
        "A": "[option A]",
        "B": "[option B]",
        "C": "[option C]",
        "D": "[option D]"
      }},
      "correct_answer": "A" | "B" | "C" | "D",
      "explanation": "[structured explanation per format above]",
      "difficulty": "{difficulty}",
      "source_chunk_indices": [0, 1, 2]
    }}
  ]
}}

Generate the {question_count} questions now:"""

        return prompt

    @transaction.atomic
    def _create_quiz_in_db(
        self,
        topic: Topic,
        questions_data: List[Dict[str, Any]],
        static_chunks: List[Chunk],
        ca_chunks: List[CAChunk],
        difficulty: str,
        include_ca: bool,
    ) -> Quiz:
        """
        Create quiz and questions in database with source attribution.

        Args:
            topic: Topic instance
            questions_data: List of question dictionaries from Groq
            static_chunks: Source static chunks
            ca_chunks: Source CA chunks
            difficulty: Difficulty level
            include_ca: CA inclusion flag

        Returns:
            Created Quiz instance with all questions
        """
        # Generate quiz title
        ca_marker = " with Current Affairs" if include_ca else ""
        title = f"Quiz: {topic.name}{ca_marker}"

        # Calculate time limit (2 minutes per question)
        time_limit = len(questions_data) * 120

        # Create quiz
        quiz = Quiz.objects.create(
            title=title,
            topic=topic,
            difficulty_level=difficulty,
            include_ca=include_ca,
            question_count=len(questions_data),
            time_limit=time_limit,
            generation_metadata={
                "static_chunk_count": len(static_chunks),
                "ca_chunk_count": len(ca_chunks),
                "generated_at": timezone.now().isoformat(),
                "model": "llama-3.3-70b-versatile",
            },
        )

        logger.info("quiz_record_created", quiz_id=str(quiz.id), topic=topic.name)

        # Create questions
        for idx, q_data in enumerate(questions_data):
            # Create question
            question = Question.objects.create(
                quiz=quiz,
                question_text=q_data.get("question_text", ""),
                question_type=q_data.get("question_type", "single_mcq"),
                statements=q_data.get("statements", []),
                options=q_data.get("options", {}),
                correct_answer=q_data.get("correct_answer", "A"),
                explanation=q_data.get("explanation", ""),
                difficulty_level=q_data.get("difficulty", difficulty),
                order_index=idx,
            )

            # Link source chunks
            # Use source_chunk_indices if provided, otherwise link all chunks
            source_indices = q_data.get("source_chunk_indices", [])

            if source_indices:
                # Link specific chunks
                for chunk_idx_raw in source_indices:
                    try:
                        chunk_idx = int(chunk_idx_raw)
                        if chunk_idx < len(static_chunks):
                            question.source_static_chunks.add(static_chunks[chunk_idx])
                        elif chunk_idx - len(static_chunks) < len(ca_chunks):
                            ca_idx = chunk_idx - len(static_chunks)
                            question.source_ca_chunks.add(ca_chunks[ca_idx])
                    except (ValueError, TypeError):
                        logger.warning(
                            "invalid_source_chunk_index", index=chunk_idx_raw
                        )
            else:
                # Link all chunks (fallback)
                question.source_static_chunks.set(static_chunks)
                if include_ca:
                    question.source_ca_chunks.set(ca_chunks)

        logger.info(
            "quiz_questions_created",
            count=len(questions_data),
            quiz_id=str(quiz.id),
        )

        return quiz


# Global singleton instance
_quiz_generator = None


def get_quiz_generator() -> QuizGeneratorService:
    """Get or create global quiz generator instance."""
    global _quiz_generator
    if _quiz_generator is None:
        _quiz_generator = QuizGeneratorService()
    return _quiz_generator
