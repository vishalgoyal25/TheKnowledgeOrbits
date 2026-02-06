"""
Chunking Service

Responsible for splitting text into semantic chunks (~1200 characters).
Preserves context with chapter/page metadata.
"""
import re
from typing import List, Dict, Any
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
        page_number: int = None,
        chapter_name: str = None
    ) -> List[Dict[str, Any]]:
        """
        Split text into chunks with metadata.
        
        Args:
            text: Full text to chunk
            document_id: Parent document UUID
            page_number: Source page number
            chapter_name: Chapter/section name
            
        Returns:
            List of chunk dictionaries with text and metadata
        """
        if not text or len(text.strip()) == 0:
            logger.warning("empty_text_provided", document_id=document_id)
            return []
        
        # Clean text
        cleaned_text = cls._clean_text(text)
        
        # Split into chunks
        chunks = cls._split_into_chunks(cleaned_text)
        
        # Add metadata to each chunk
        chunk_dicts = []
        for idx, chunk_text in enumerate(chunks):
            chunk_dict = {
                'chunk_text': chunk_text,
                'chunk_index': idx,
                'page_number': page_number,
                'chapter_name': chapter_name or cls._detect_chapter(chunk_text),
                'document_id': document_id,
                'source_type': 'static',
                'quality_flag': cls._assess_quality(chunk_text),
                'confidence_score': 1.0,
            }
            chunk_dicts.append(chunk_dict)
        
        logger.info(
            "text_chunked",
            document_id=document_id,
            total_chunks=len(chunk_dicts),
            avg_chunk_size=sum(len(c['chunk_text']) for c in chunk_dicts) // len(chunk_dicts) if chunk_dicts else 0
        )
        
        return chunk_dicts
    
    @classmethod
    def _clean_text(cls, text: str) -> str:
        """
        Clean and normalize text.
        
        - Remove extra whitespace
        - Normalize line breaks
        - Remove special characters (preserve punctuation)
        """
        # Replace multiple spaces with single space
        text = re.sub(r'\s+', ' ', text)
        
        # Normalize line breaks
        text = re.sub(r'\n+', '\n', text)
        
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
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        chunks = []
        current_chunk = []
        current_length = 0
        
        for sentence in sentences:
            sentence_length = len(sentence)
            
            # If adding this sentence exceeds chunk size
            if current_length + sentence_length > cls.CHUNK_SIZE and current_chunk:
                # Save current chunk
                chunk_text = ' '.join(current_chunk)
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
            chunk_text = ' '.join(current_chunk)
            if len(chunk_text) >= cls.MIN_CHUNK_SIZE:
                chunks.append(chunk_text)
        
        return chunks
    
    @classmethod
    def _detect_chapter(cls, text: str) -> str:
        """
        Simple chapter detection from text.
        
        Looks for patterns like "Chapter 1", "CHAPTER I", etc.
        """
        # Check first 100 characters for chapter markers
        first_100 = text[:100]
        
        patterns = [
            r'Chapter\s+\d+',
            r'CHAPTER\s+[IVX]+',
            r'Section\s+\d+',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, first_100, re.IGNORECASE)
            if match:
                return match.group()
        
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
            return 'low'
        
        # Count special characters (OCR errors indicator)
        special_char_count = len(re.findall(r'[^a-zA-Z0-9\s.,!?;:\-\']', text))
        special_char_ratio = special_char_count / text_length if text_length > 0 else 0
        
        if special_char_ratio > 0.1:
            return 'needs_review'
        
        # Check if ends with sentence terminator
        if not text.strip().endswith(('.', '!', '?')):
            return 'medium'
        
        return 'high'
        