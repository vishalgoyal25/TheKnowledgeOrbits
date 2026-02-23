"""
Chunking Service

Responsible for splitting text into semantic chunks (~1200 characters).
Preserves context with chapter/page metadata.
"""

import re
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


class ChunkingService:
    """
    Service for chunking text content into semantic pieces.

    Principles:
    - Fixed size: ~1200 characters
    - Respect sentence boundaries
    - Track source context (chapter, page)
    - Quality scoring
    """

    CHUNK_SIZE = 1200
    CHUNK_OVERLAP = 200
    MIN_CHUNK_SIZE = 300

    @classmethod
    def chunk_text(
        cls,
        text: str,
        document_id: str,
        page_number: int,
        chapter_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Split text into semantic chunks with metadata.

        Args:
            text: Text content to chunk
            document_id: UUID of parent document
            page_number: Page number in document
            chapter_name: Chapter/section name

        Returns:
            List of chunk dictionaries ready for Chunk.objects.create()
        """

        if not text or len(text.strip()) == 0:
            logger.warning("empty_text_provided", document_id=document_id)
            return []

        # Clean text
        cleaned_text = cls._clean_text(text)

        # Detect chapter if not provided
        if not chapter_name:
            chapter_name = cls._detect_chapter(text)

        # Split into chunks
        chunk_texts = cls._split_into_chunks(cleaned_text)

        # Create chunk data
        chunks = []
        for idx, chunk_text in enumerate(chunk_texts):
            quality = cls._assess_quality(chunk_text)

            chunks.append(
                {
                    "chunk_text": chunk_text,
                    "chunk_index": idx,
                    "page_number": page_number,
                    "source_type": "static",
                    "document_id": document_id,
                    "chapter_name": chapter_name,
                    "quality_flag": quality,
                    "confidence_score": 1.0 if quality == "high" else 0.7,
                }
            )

        logger.info(
            "text_chunked",
            document_id=document_id,
            page_number=page_number,
            total_chunks=len(chunks),
            avg_chunk_size=(
                sum(len(str(c["chunk_text"])) for c in chunks) // len(chunks)
                if chunks
                else 0
            ),
        )

        return chunks

    @classmethod
    def _clean_text(cls, text: str) -> str:
        """
        Clean and normalize text.

        - Remove extra whitespace
        - Normalize line breaks
        - Remove special characters (preserve punctuation)
        """
        # Replace multiple spaces with single space
        text = re.sub(r"\s+", " ", text)

        # Normalize line breaks
        text = re.sub(r"\n+", "\n", text)

        # Remove leading/trailing whitespace
        text = text.strip()

        return text

    @classmethod
    def _split_into_chunks(cls, text: str) -> List[str]:
        """
        Split text into chunks respecting sentence boundaries.

        Strategy:
        1. Split by sentences
        2. Group sentences into ~1200 char chunks
        3. Add overlap for context continuity
        """
        # Split into sentences (simple approach)
        sentences = re.split(r"(?<=[.!?])\s+", text)

        chunks: List[str] = []
        current_chunk: List[str] = []
        current_length = 0

        for sentence in sentences:
            sentence_length = len(sentence)

            # If adding this sentence exceeds chunk size
            if current_length + sentence_length > cls.CHUNK_SIZE and current_chunk:
                # Save current chunk
                chunk_text = " ".join(current_chunk)
                if len(chunk_text) >= cls.MIN_CHUNK_SIZE:
                    chunks.append(chunk_text)

                # Start new chunk with overlap (last sentence)
                current_chunk = [current_chunk[-1]] if current_chunk else []
                current_length = len(current_chunk[0]) if current_chunk else 0

            # Add sentence to current chunk
            current_chunk.append(sentence)
            current_length += sentence_length

        # Add final chunk
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            if len(chunk_text) >= cls.MIN_CHUNK_SIZE:
                chunks.append(chunk_text)

        return chunks

    @classmethod
    def _detect_chapter(cls, text: str) -> str:
        """
        Detect chapter name from text using pattern matching.

        Patterns detected:
        - Chapter 1, Chapter I, CHAPTER 1
        - Unit 1, UNIT I
        - Part A, PART 1
        - Section 1.1

        Args:
            text: Text to analyze (first 200 chars)

        Returns:
            Chapter name or "Unknown Chapter"
        """
        # Check first 200 characters
        header = text[:200].strip()

        # Patterns to match
        patterns = [
            (r"Chapter\s+(\d+)", "Chapter {}"),
            (r"CHAPTER\s+(\d+)", "Chapter {}"),
            (r"Chapter\s+([IVX]+)", "Chapter {}"),
            (r"CHAPTER\s+([IVX]+)", "Chapter {}"),
            (r"Unit\s+(\d+)", "Unit {}"),
            (r"UNIT\s+(\d+)", "Unit {}"),
            (r"Unit\s+([IVX]+)", "Unit {}"),
            (r"Part\s+([A-Z\d]+)", "Part {}"),
            (r"PART\s+([A-Z\d]+)", "Part {}"),
            (r"Section\s+(\d+\.?\d*)", "Section {}"),
        ]

        for pattern, template in patterns:
            match = re.search(pattern, header, re.IGNORECASE)
            if match:
                chapter_id = match.group(1)
                return template.format(chapter_id)

        return "Unknown Chapter"

    @classmethod
    def _assess_quality(cls, text: str) -> str:
        """
        Assess chunk quality based on heuristics.

        Criteria:
        - Length (too short = low quality)
        - Special characters (too many = OCR errors)
        - Sentence structure (incomplete = low quality)
        """
        text_length = len(text)

        # Too short
        if text_length < cls.MIN_CHUNK_SIZE:
            return "low"

        # Count special characters (OCR errors indicator)
        special_char_count = len(re.findall(r"[^a-zA-Z0-9\s.,!?;:\-\']", text))
        special_char_ratio = special_char_count / text_length if text_length > 0 else 0

        if special_char_ratio > 0.1:
            return "needs_review"

        # Check if ends with sentence terminator
        if not text.strip().endswith((".", "!", "?")):
            return "medium"

        return "high"
