"""
Ingestion Service

Orchestrates the full ingestion pipeline:
1. Accept file upload
2. Extract text (PDF/web)
3. Chunk text
4. Generate embeddings
5. Store in database
"""
from typing import Dict, Any, Optional
from django.core.files.uploadedfile import UploadedFile
import structlog

from engines.content.models import Document, Chunk, Embedding, IngestionJob
from .chunking_service import ChunkingService
from .embedding_service import EmbeddingService

logger = structlog.get_logger(__name__)


class IngestionService:
    """
    Service for orchestrating content ingestion.
    
    Flow: Upload → Extract → Chunk → Embed → Store
    """
    
    @classmethod
    def ingest_document(
        cls,
        file: UploadedFile,
        title: str,
        source_type: str,
        source_edition: str = None,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Main ingestion entry point.
        
        Args:
            file: Uploaded file
            title: Document title
            source_type: 'static' or 'dynamic'
            source_edition: Edition identifier
            metadata: Additional metadata
            
        Returns:
            Dictionary with document_id, job_id, status
        """
        logger.info(
            "ingestion_started",
            title=title,
            source_type=source_type,
            file_name=file.name
        )
        
        # Create ingestion job
        job = IngestionJob.objects.create(status='pending')
        
        try:
            # Create document record
            document = Document.objects.create(
                title=title,
                file_path=cls._save_file(file),
                source_type=source_type,
                source_edition=source_edition or '',
                metadata=metadata or {}
            )
            
            # Link job to document
            job.document = document
            job.status = 'processing'
            job.save()
            
            # Extract text from file
            text = cls._extract_text(file)
            
            # Chunk text
            chunks_data = ChunkingService.chunk_text(
                text=text,
                document_id=str(document.id)
            )
            
            job.total_pages = 1  # Simplified for Phase 1
            job.save()
            
            # Create chunk records
            chunks = []
            for chunk_data in chunks_data:
                chunk = Chunk.objects.create(
                    document=document,
                    **chunk_data
                )
                chunks.append(chunk)
            
            job.chunks_created = len(chunks)
            job.processed_pages = 1
            job.save()
            
            # Generate embeddings (async in production)
            cls._generate_embeddings_for_chunks(chunks)
            
            # Mark job complete
            job.status = 'completed'
            job.save()
            
            logger.info(
                "ingestion_completed",
                document_id=str(document.id),
                chunks_created=len(chunks)
            )
            
            return {
                'document_id': str(document.id),
                'job_id': str(job.id),
                'status': 'completed',
                'chunks_created': len(chunks),
            }
            
        except Exception as e:
            # Mark job as failed
            job.status = 'failed'
            job.error_log = str(e)
            job.save()
            
            logger.error(
                "ingestion_failed",
                error=str(e),
                job_id=str(job.id)
            )
            
            raise
    
    @classmethod
    def _save_file(cls, file: UploadedFile) -> str:
        """
        Save uploaded file to storage.
        
        For Phase 1: Simple file system storage.
        Future: S3/Cloudinary.
        """
        # Simplified: Return file name
        # In production, save to media folder or cloud storage
        return f"/media/documents/{file.name}"
    
    @classmethod
    def _extract_text(cls, file: UploadedFile) -> str:
        """
        Extract text from uploaded file.
        Supports: .txt, .pdf
        
        Args:
            file: Uploaded file object
            
        Returns:
            Extracted text content
            
        Raises:
            ValueError: If file type unsupported or extraction fails
        """
        file_name = file.name.lower()
        
        try:
            # TEXT FILE
            if file_name.endswith('.txt'):
                logger.info("extracting_text_file", file_name=file.name)
                
                content = file.read()
                
                # Decode bytes to string
                if isinstance(content, bytes):
                    text = content.decode('utf-8')
                else:
                    text = str(content)
                
                logger.info(
                    "text_extracted",
                    file_name=file.name,
                    text_length=len(text)
                )
                
                return text
            
            # PDF FILE
            elif file_name.endswith('.pdf'):
                logger.info("extracting_pdf_file", file_name=file.name)
                
                try:
                    import pdfplumber
                    from io import BytesIO
                except ImportError:
                    logger.error("pdfplumber_not_installed")
                    raise ValueError("pdfplumber not installed. Run: pip install pdfplumber")
                
                text_pages = []
                
                # Read PDF
                pdf_bytes = BytesIO(file.read())
                
                with pdfplumber.open(pdf_bytes) as pdf:
                    total_pages = len(pdf.pages)
                    logger.info("pdf_opened", pages=total_pages)
                    
                    for page_num, page in enumerate(pdf.pages, 1):
                        try:
                            page_text = page.extract_text()
                            
                            if page_text:
                                text_pages.append(page_text)
                                logger.debug(
                                    "page_extracted",
                                    page=page_num,
                                    length=len(page_text)
                                )
                            else:
                                logger.warning(
                                    "empty_page",
                                    page=page_num
                                )
                        
                        except Exception as page_error:
                            logger.error(
                                "page_extraction_failed",
                                page=page_num,
                                error=str(page_error)
                            )
                            # Continue with next page
                            continue
                
                # Join all pages
                full_text = '\n\n'.join(text_pages)
                
                logger.info(
                    "pdf_text_extracted",
                    file_name=file.name,
                    total_pages=total_pages,
                    extracted_pages=len(text_pages),
                    text_length=len(full_text)
                )
                
                if not full_text.strip():
                    raise ValueError("No text extracted from PDF. File may be scanned/image-based.")
                
                return full_text
            
            # UNSUPPORTED FILE TYPE
            else:
                logger.error(
                    "unsupported_file_type",
                    file_name=file.name
                )
                raise ValueError(
                    f"Unsupported file type: {file_name}. "
                    f"Supported formats: .txt, .pdf"
                )
        
        except ValueError:
            # Re-raise ValueError (expected errors)
            raise
        
        except Exception as e:
            logger.error(
                "text_extraction_failed",
                file_name=file.name,
                error=str(e),
                error_type=type(e).__name__
            )
            raise ValueError(f"Could not extract text from file: {str(e)}")


    @classmethod
    def _generate_embeddings_for_chunks(cls, chunks: list) -> None:
        """
        Generate and store embeddings for all chunks.
        
        Args:
            chunks: List of Chunk instances
        """
        from engines.content.models import Embedding
        
        logger.info("generating_embeddings", chunk_count=len(chunks))
        
        for chunk in chunks:
            try:
                embedding_data = EmbeddingService.create_embedding_record(
                    content_type='chunk',
                    content_id=str(chunk.id),
                    text=chunk.chunk_text
                )
                
                # CREATE THE RECORD IN DATABASE
                Embedding.objects.create(
                    content_type=embedding_data['content_type'],
                    content_id=embedding_data['content_id'],
                    vector=embedding_data['vector'],
                    model_name=embedding_data['model_name']
                )
                
                logger.info(
                    "embedding_created",
                    chunk_id=str(chunk.id)
                )
                
            except Exception as e:
                logger.error(
                    "embedding_generation_failed",
                    chunk_id=str(chunk.id),
                    error=str(e)
                )
                