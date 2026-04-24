import sentry_sdk

"""
Article Generation Service

RAG-based article generation using GROQ with integrated Contextual Analysis.
"""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

import structlog
from django.db import transaction
from django.utils import timezone

from engines.content.models import Chunk
from engines.current_affairs.models import CAChunk, CATopicLink
from engines.knowledge.models import ChunkTopicMap, Topic

from ..models import Article, ArticleSourceMap

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)


# Article specs
TARGET_WORD_COUNT = 1000
MIN_WORD_COUNT = 500
MAX_WORD_COUNT = 1500


class ArticleGenerationService:
    """Service for generating articles from chunks using RAG."""

    @staticmethod
    def generate_article(
        topic_id: str, include_ca: bool = False, user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Orchestrate the RAG pipeline to generate a comprehensive UPSC-style article.

        This process includes:
        1. Retrieving high-relevance chunks from static sources.
        2. Optionally fetching and merging recent current affairs context.
        3. Formulating a context-rich prompt for the Groq LLM.
        4. Validating the generated article for quality and length.
        5. Persisting the result with full source attribution.

        Args:
            topic_id (str): UUID of the Knowledge Topic to generate for.
            include_ca (bool): Flag to trigger Current Affairs (CA) integration.
            user_id (int, optional): The ID of the user triggering the generation.

        Returns:
            Dict[str, Any]: Article metadata and success status.
        """
        logger.info(
            "article_generation_started", topic_id=topic_id, include_ca=include_ca
        )

        try:
            # Get topic
            topic = Topic.objects.get(id=topic_id)

            # Fetch static chunks (Textbooks/NCERT)
            static_chunks = ArticleGenerationService._fetch_chunks(topic)

            # Fetch CA chunks if requested
            ca_chunks: List[CAChunk] = []
            if include_ca:
                # Increased window to 180 days to ensure recent news is captured
                ca_chunks = ArticleGenerationService._fetch_ca_chunks(topic, days=180)
                logger.info("ca_chunks_fetched", count=len(ca_chunks))

            # Validate that we have at least SOME source material (Static OR CA)
            if not static_chunks and not ca_chunks:
                logger.warning("no_source_material_found", topic_id=topic_id)
                raise ValueError(
                    f"No source material (Static or Current Affairs) found for topic: {topic.name}. "
                    "Please ingest relevant material first."
                )

            # Assemble RAG context
            context = ArticleGenerationService._assemble_context(
                static_chunks, include_ca, ca_chunks
            )

            # Generate article content
            article_data = ArticleGenerationService._generate_with_groq(
                topic=topic, context=context, include_ca=include_ca
            )

            # Validate quality
            quality_score = ArticleGenerationService._validate_quality(article_data)
            article_data["quality_score"] = quality_score

            # Store article + source map
            article = ArticleGenerationService._store_article(
                topic=topic,
                article_data=article_data,
                static_chunks=static_chunks,
                ca_chunks=ca_chunks,
                include_ca=include_ca,
                user_id=user_id,
            )

            logger.info(
                "article_generated_successfully",
                topic_id=topic_id,
                article_id=str(article.id),
                word_count=article.word_count,
                quality_score=quality_score,
            )

            return {
                "success": True,
                "article_id": str(article.id),
                "title": article.title,
                "word_count": article.word_count,
                "quality_score": quality_score,
                "source_chunks": len(static_chunks),
                "ca_chunks": len(ca_chunks) if include_ca else 0,
            }

        except Topic.DoesNotExist:
            logger.error("topic_not_found", topic_id=topic_id)
            raise

        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error("article_generation_failed", topic_id=topic_id, error=str(e))
            raise

    @staticmethod
    def _fetch_chunks(topic: Topic) -> List[Chunk]:
        """
        Retrieve theoretical foundation chunks mapped to the target topic.

        Args:
            topic (Topic): The topic instance.

        Returns:
            List[Chunk]: Chunks ordered by their relevance to the topic.
        """
        # Get mapping objects
        mappings = (
            ChunkTopicMap.objects.filter(topic=topic)
            .select_related("chunk", "chunk__document")
            .order_by("-relevance_score")
        )

        # Filter for static source type and extract chunks
        chunks: List[Chunk] = []
        for mapping in mappings:
            chunk = mapping.chunk
            if chunk.source_type == "static":  # Explicitly check for static type
                chunks.append(chunk)

        return chunks

    @staticmethod
    def _fetch_ca_chunks(topic: Topic, days: int = 30) -> List[CAChunk]:
        """
        Retrieve recent Current Affairs (dynamic) chunks linked to the topic.

        Args:
            topic (Topic): The topic instance.
            days (int): Temporal window for CA relevance (default: 30 days).

        Returns:
            List[CAChunk]: Recent news chunks relevant to the topic.
        """
        from datetime import timedelta

        cutoff_date = timezone.now() - timedelta(days=days)

        # Get CA chunks linked to this topic via CATopicLink
        # We need to filter by the specific topic and recent dates
        ca_links = (
            CATopicLink.objects.filter(
                topic=topic,
                ca_chunk__published_at__gte=cutoff_date,
                ca_chunk__is_expired=False,
            )
            .select_related("ca_chunk", "ca_chunk__ca_article")
            .order_by("-relevance_score", "-ca_chunk__published_at")[:5]
        )  # Top 5 most relevant/recent

        return [link.ca_chunk for link in ca_links]

    @staticmethod
    def _assemble_context(
        static_chunks: List[Chunk],
        include_ca: bool,
        ca_chunks: Optional[List[CAChunk]] = None,
    ) -> str:
        """
        Assemble RAG context from static and optional CA chunks.
        """
        context_parts = []

        # 1. Theoretical Foundation (Static Chunks)
        if static_chunks:
            context_parts.append("=== THEORETICAL FOUNDATION (NCERT/Textbooks) ===\n")
            for idx, chunk in enumerate(static_chunks, 1):
                doc_title = chunk.document.title if chunk.document else "Textbook"
                page_info = f", Page {chunk.page_number}" if chunk.page_number else ""
                chapter_info = (
                    f", Chapter: {chunk.chapter_name}" if chunk.chapter_name else ""
                )

                context_parts.append(
                    f"[Source {idx}: {doc_title}{page_info}{chapter_info}]"
                )
                context_parts.append(chunk.chunk_text)
                context_parts.append("---\n")

        # 2. Current Context (CA Chunks)
        if include_ca and ca_chunks:
            context_parts.append("\n=== CURRENT CONTEXT (Recent Developments) ===\n")
            for ca_idx, ca_chunk in enumerate(ca_chunks, 1):
                article_title = (
                    ca_chunk.ca_article.title if ca_chunk.ca_article else "News Article"
                )
                date_str = ca_chunk.published_at.strftime("%Y-%m-%d")

                context_parts.append(
                    f"[CA Source {ca_idx}: {article_title}, {date_str}]"
                )
                context_parts.append(ca_chunk.chunk_text)
                context_parts.append("---\n")

        return "\n".join(context_parts)

    @staticmethod
    def _generate_with_groq(
        topic: Topic, context: str, include_ca: bool
    ) -> Dict[str, Any]:
        """
        Generate article using the shared LLM pool (round-robin, all providers).
        """
        from engines.book_content.services.llm_service import llm_call

        # Build prompt
        prompt = ArticleGenerationService._build_prompt(topic, context, include_ca)

        logger.info(
            "calling_llm_pool",
            topic_id=str(topic.id),
            context_length=len(context),
        )

        content = llm_call(prompt, mode="article")
        if not content:
            raise ValueError("Empty response received from LLM pool")

        # Parse output
        article_data = ArticleGenerationService._parse_groq_output(content)

        # Calculate details
        article_data["word_count"] = len(article_data["content"].split())

        return article_data

    @staticmethod
    def _build_prompt(topic: Topic, context: str, include_ca: bool) -> str:
        """Build GROQ prompt based on generation mode."""

        base_role = "You are an expert UPSC educator writing for IAS aspirants."

        if include_ca:
            return f"""{base_role}

Generate a comprehensive article integrating THEORY and CURRENT AFFAIRS on: {topic.name}

Topic Description: {topic.description}

Source Material:
{context}

Requirements:
1. Structure:
   - Introduction (100-150 words) - Set context
   - Theoretical Framework (400-500 words) - Core concepts from textbooks
   - Current Developments (200-300 words) - Recent news/events analysis
   - Analysis & Exam Relevance (200-250 words) - Connect theory to practice
   - Conclusion (100-150 words) - UPSC perspective

2. Integration: Explicitly link current affairs to theoretical concepts.
3. UPSC Angle: Highlight prelims facts + mains discussion points.
4. Examples: Use specific examples from both theory and current events.
5. Format: Proper paragraphs (no bullet points in body unless listing facts).

Target Length: {TARGET_WORD_COUNT} words

Generate the integrated article now:"""

        else:
            return f"""{base_role}

Generate a comprehensive article on: {topic.name}

Topic Description: {topic.description}

Source Material:
{context}

Requirements:
1. Structure: Introduction (100-150 words), Body (600-700 words), Conclusion (100-150 words)
2. UPSC Focus: Connect theory to exam patterns (Prelims + Mains)
3. Examples: Use concrete examples from source material
4. Clarity: Clear explanations suitable for UPSC preparation
5. Depth: Cover all important aspects mentioned in sources
6. Format: Uses proper paragraphs.

Target Length: {TARGET_WORD_COUNT} words

Generate the article now:"""

    @staticmethod
    def _parse_groq_output(content: str) -> Dict[str, Any]:
        """Parse GROQ output to extract title, content, summary."""
        lines = content.strip().split("\n")
        title = None
        content_start = 0

        # Try to detect title
        if lines:
            first_line = lines[0].strip()
            # Heuristic: Short line, no period, possibly hashed
            if len(first_line) < 100 and not first_line.endswith("."):
                title = first_line.replace("#", "").strip()
                content_start = 1

        article_content = "\n".join(lines[content_start:]).strip()

        # Generate summary from first paragraph
        summary = ""
        paragraphs = article_content.split("\n\n")
        if paragraphs:
            summary = " ".join(paragraphs[0].split()[:30]) + "..."

        return {
            "title": title,
            "content": article_content,
            "summary": summary,
        }

    @staticmethod
    def _validate_quality(article_data: Dict[str, Any]) -> float:
        """Validate article quality via heuristics."""
        checks = {}
        content = article_data.get("content", "")
        word_count = article_data.get("word_count", 0)

        checks["word_count"] = MIN_WORD_COUNT <= word_count <= MAX_WORD_COUNT
        checks["has_content"] = len(content) > 100
        checks["has_summary"] = len(article_data.get("summary", "")) > 20
        checks["proper_structure"] = content.count("\n\n") >= 3

        words = content.split()
        if words:
            unique_ratio = len(set(words)) / len(words)
            checks["not_repetitive"] = unique_ratio > 0.4
        else:
            checks["not_repetitive"] = False

        score = (sum(checks.values()) / len(checks)) * 100
        return round(score, 2)  # type: ignore

    @staticmethod
    @transaction.atomic
    def _store_article(
        topic: Topic,
        article_data: Dict[str, Any],
        static_chunks: List[Chunk],
        ca_chunks: List[CAChunk],
        include_ca: bool,
        user_id: Optional[int] = None,
    ) -> Article:
        """
        Persist the generated article and create formal source mapping for provenance.

        Args:
            topic (Topic): The associated knowledge topic.
            article_data (Dict): Content and metadata returned from LLM.
            static_chunks (List[Chunk]): Foundation materials used.
            ca_chunks (List[CAChunk]): Dynamic news materials used.
            include_ca (bool): Mode used for relative metadata tracking.
            user_id (int, optional): Owning user ID.

        Returns:
            Article: The saved Article instance.
        """

        # Fallback title
        title = article_data.get("title") or f"{topic.name}: Comprehensive Guide"

        # Create Article Record
        article = Article.objects.create(
            title=title,
            content=article_data["content"],
            summary=article_data.get("summary", ""),
            topic=topic,
            word_count=article_data["word_count"],
            generation_type="ai_generated",
            quality_score=article_data["quality_score"],
            review_status=(
                "pending" if article_data["quality_score"] < 70 else "approved"
            ),
            is_published=article_data["quality_score"] >= 70,
            published_at=(
                timezone.now() if article_data["quality_score"] >= 70 else None
            ),
            generation_metadata={
                "static_chunks_used": len(static_chunks),
                "ca_chunks_used": len(ca_chunks) if include_ca else 0,
                "model": "llm_pool",
                "include_ca": include_ca,
            },
        )

        # Map Static Chunks
        for idx, chunk in enumerate(static_chunks, 1):
            # Get relevance from ChunkTopicMap if available
            mapping = ChunkTopicMap.objects.filter(chunk=chunk, topic=topic).first()
            relevance = mapping.relevance_score if mapping else 1.0

            ArticleSourceMap.objects.create(
                article=article,
                chunk=chunk,
                relevance_weight=relevance,
                sequence_order=idx,
                chunk_contribution="static",
            )

        # Map CA Chunks
        # Note: Since ArticleSourceMap links to 'content.Chunk', we cannot directly link 'current_affairs.CAChunk'
        # UNLESS they share a base ID or we have a generic foreign key.
        # Based on the provided instruction, we'll assume we need to handle this.
        # However, looking at the previous file content, ArticleSourceMap.chunk is a ForeignKey to content.Chunk.
        # CAChunk is a separate model.
        #
        # OPTION A: If CAChunk IS NOT a content.Chunk, we can't store it in ArticleSourceMap without schema change.
        # OPTION B: Maybe CAChunk inherits or there is a mechanism I missed?
        #
        # Checking models... CAChunk is independent.
        #
        # WORKAROUND: For now, I will NOT try to insert CA chunks into ArticleSourceMap to avoid Foreign Key Constraint errors,
        # unless I can verify they are compatible. The user request has a placeholder 'pass' for this.
        # I will leave a TODO or log it, as blindly inserting CAChunk ID into Chunk FK will fail.

        if include_ca and ca_chunks:
            # Ideally, we would have a unified Chunk model or a GenericForeignKey.
            # For this task, we will store the CA attribution in the article metadata
            # effectively until the schema supports it.
            ca_sources_meta = []
            for idx, ca_chunk in enumerate(ca_chunks, 1):
                ca_sources_meta.append(
                    {
                        "title": ca_chunk.ca_article.title,
                        "date": ca_chunk.published_at.isoformat(),
                        "chunk_id": str(ca_chunk.id),
                    }
                )

            # update metadata with explicit source list
            article.generation_metadata["ca_sources"] = ca_sources_meta
            article.save()

        # Generate Embedding for Semantic Search in background
        try:
            from engines.content.tasks import generate_content_embedding

            # Combine title, summary, and first part of content for rich context
            embedding_text = (
                f"{article.title}\n{article.summary}\n{article.content[:1000]}"
            )

            # Queue background task
            generate_content_embedding(
                content_type="article", content_id=str(article.id), text=embedding_text
            )
            logger.info("article_embedding_queued", article_id=str(article.id))
        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error("article_embedding_queue_failed", error=str(e))

        return article
