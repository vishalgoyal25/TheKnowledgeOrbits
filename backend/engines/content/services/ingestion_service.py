import sentry_sdk

"""
Ingestion Service

Orchestrates the full ingestion pipeline:
1. Accept file upload
2. Extract text (PDF/web)
3. Chunk text
4. Generate embeddings
5. Store in database
"""

from typing import Any, Dict, List, Optional

from django.core.files.uploadedfile import UploadedFile
from django.utils import timezone

import structlog

from engines.content.models import Chunk, Document, IngestionJob

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
        source_edition: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Orchestrates the full ingestion pipeline from file upload to embedding storage.

        This method handles:
        1. Tracking the job via IngestionJob.
        2. Permanent storage of the file.
        3. Document metadata creation.
        4. Page-by-page text extraction for positional accuracy.
        5. Batch embedding generation.

        Args:
            file (UploadedFile): The uploaded PDF or text file.
            title (str): Human-readable title for the document.
            source_type (str): Category (e.g., 'static', 'standard_book').
            source_edition (str, optional): Edition or version string.
            metadata (dict, optional): Additional key-value pairs for categorization.

        Returns:
            Dict[str, Any]: Summary of the ingestion results including IDs and counts.
        """
        job = None
        document = None

        try:
            # Step 1: Create ingestion job
            job = IngestionJob.objects.create(status="pending")

            logger.info(
                "ingestion_started",
                job_id=str(job.id),
                file_name=file.name,
                title=title,
                source_type=source_type,
            )

            # Step 2: Save file
            file_path = cls._save_file(file)

            # Step 3: Create document
            document = Document.objects.create(
                title=title,
                file_path=file_path,
                source_type=source_type,
                source_edition=source_edition or "",
                metadata=metadata or {},
            )

            # Step 4: Link job to document
            job.document = document
            job.status = "processing"
            job.save()

            # Step 5: Extract text BY PAGE
            pages_data = cls._extract_text_by_pages(file)

            # Update total pages
            job.total_pages = len(pages_data)
            job.save()

            # Step 6: Process each page
            all_chunks = []
            global_chunk_index = 0

            for page_data in pages_data:
                page_num = page_data["page_number"]
                page_text = page_data["text"]
                chapter = page_data.get("chapter", "Unknown Chapter")

                # Chunk this page
                page_chunks = ChunkingService.chunk_text(
                    text=page_text,
                    document_id=str(document.id),
                    page_number=page_num,  # PASS PAGE NUMBER
                    chapter_name=chapter,
                )

                # Update chunk index to be globally unique for this document
                for chunk in page_chunks:
                    chunk["chunk_index"] = global_chunk_index
                    global_chunk_index += 1

                all_chunks.extend(page_chunks)

                # Update progress
                job.processed_pages = page_num
                job.save()

            # Step 7: Store all chunks in database
            chunk_objects = []
            for chunk_data in all_chunks:
                chunk_objects.append(Chunk(**chunk_data))

            Chunk.objects.bulk_create(chunk_objects)

            # Update chunks_created
            job.chunks_created = len(chunk_objects)
            job.save()

            logger.info(
                "chunks_created",
                document_id=str(document.id),
                total_chunks=len(chunk_objects),
                total_pages=job.total_pages,
            )

            # Step 8: Generate embeddings
            cls._generate_embeddings_for_chunks(chunk_objects)

            # Step 9: Mark job complete
            job.status = "completed"
            job.completed_at = timezone.now()
            job.save()

            logger.info(
                "ingestion_completed",
                document_id=str(document.id),
                chunks_created=len(chunk_objects),
            )

            return {
                "document_id": str(document.id),
                "job_id": str(job.id),
                "status": "completed",
                "chunks_created": len(chunk_objects),
                "pages_processed": job.total_pages,
            }

        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(
                "ingestion_failed", error=str(e), job_id=str(job.id) if job else None
            )

            if job:
                job.status = "failed"
                job.error_log = str(e)
                job.save()

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
        """
        if not file or not file.name:
            raise ValueError("Invalid file object: Name is missing")
        file_name = file.name.lower()

        try:
            # TEXT FILE
            if file_name.endswith(".txt"):
                logger.info("extracting_text_file", file_name=file.name)

                content = file.read()

                # Decode bytes to string
                if isinstance(content, bytes):
                    text = content.decode("utf-8")
                else:
                    text = str(content)

                logger.info(
                    "text_extracted", file_name=file.name, text_length=len(text)
                )

                return text

            # PDF FILE
            elif file_name.endswith(".pdf"):
                logger.info("extracting_pdf_file", file_name=file.name)

                try:
                    from io import BytesIO

                    import pdfplumber
                except ImportError:
                    logger.error("pdfplumber_not_installed")
                    raise ValueError(
                        "pdfplumber not installed. Run: pip install pdfplumber"
                    )

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
                                    length=len(page_text),
                                )
                            else:
                                logger.warning("empty_page", page=page_num)

                        except Exception as page_error:
                            sentry_sdk.capture_exception(page_error)
                            logger.error(
                                "page_extraction_failed",
                                page=page_num,
                                error=str(page_error),
                            )
                            # Continue with next page
                            continue

                # Join all pages
                full_text = "\n\n".join(text_pages)

                logger.info(
                    "pdf_text_extracted",
                    file_name=file.name,
                    total_pages=total_pages,
                    extracted_pages=len(text_pages),
                    text_length=len(full_text),
                )

                if not full_text.strip():
                    raise ValueError(
                        "No text extracted from PDF. File may be scanned/image-based."
                    )

                return full_text

            # UNSUPPORTED FILE TYPE
            else:
                logger.error("unsupported_file_type", file_name=file.name)
                raise ValueError(
                    f"Unsupported file type: {file_name}. Supported formats: .txt, .pdf"
                )

        except ValueError:
            # Re-raise ValueError (expected errors)
            raise

        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(
                "text_extraction_failed",
                file_name=file.name,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise ValueError(f"Could not extract text from file: {str(e)}")

    @classmethod
    def _extract_text_by_pages(cls, file: UploadedFile) -> List[Dict[str, Any]]:
        """
        Extract text from a file while maintaining page-level isolation.

        This is critical for allowing users to jump directly to specific pages
        referenced in generated articles or search results.

        Args:
            file (UploadedFile): The file to process.

        Returns:
            List[Dict[str, Any]]: A list containing text and metadata for each page.
        """
        if not file or not file.name:
            raise ValueError("Invalid file object: Name is missing")
        file_name = file.name.lower()
        pages_data = []

        try:
            # TEXT FILE (single page)
            if file_name.endswith(".txt"):
                logger.info("extracting_text_file", file_name=file.name)

                content = file.read()
                if isinstance(content, bytes):
                    text = content.decode("utf-8")
                else:
                    text = str(content)

                pages_data.append(
                    {"page_number": 1, "text": text, "chapter": "Unknown Chapter"}
                )

            # PDF FILE (multi-page)
            elif file_name.endswith(".pdf"):
                logger.info("extracting_pdf_file", file_name=file.name)

                from io import BytesIO

                import pdfplumber

                pdf_bytes = BytesIO(file.read())
                current_chapter = "Unknown Chapter"

                with pdfplumber.open(pdf_bytes) as pdf:
                    total_pages = len(pdf.pages)
                    logger.info("pdf_opened", pages=total_pages)

                    for page_num, page in enumerate(pdf.pages, 1):
                        try:
                            page_text = page.extract_text()

                            if page_text:
                                # Try to detect new chapter on this page
                                detected = cls._detect_chapter_from_page(page_text)
                                if detected != "Unknown Chapter":
                                    current_chapter = detected

                                pages_data.append(
                                    {
                                        "page_number": page_num,
                                        "text": page_text,
                                        "chapter": current_chapter,
                                    }
                                )

                                logger.debug(
                                    "page_extracted",
                                    page=page_num,
                                    chapter=current_chapter,
                                    length=len(page_text),
                                )
                            else:
                                logger.warning("empty_page", page=page_num)

                        except Exception as page_error:
                            sentry_sdk.capture_exception(page_error)
                            logger.error(
                                "page_extraction_failed",
                                page=page_num,
                                error=str(page_error),
                            )
                            continue

                logger.info(
                    "pdf_extraction_complete",
                    total_pages=total_pages,
                    extracted_pages=len(pages_data),
                )

            else:
                raise ValueError(f"Unsupported file type: {file_name}")

            return pages_data

        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error("text_extraction_failed", file_name=file.name, error=str(e))
            raise

    @classmethod
    def _detect_chapter_from_page(cls, text: str) -> str:
        """Detect chapter from page text (first 200 chars)."""
        from engines.content.services.chunking_service import ChunkingService

        return ChunkingService._detect_chapter(text)

    @classmethod
    def _generate_embeddings_for_chunks(cls, chunks: List["Chunk"]) -> None:
        """
        Generate semantic embeddings for a list of document chunks.

        This batches the embedding process and stores results in the vector database.

        Args:
            chunks (List[Chunk]): The pre-created chunk instances needing embeddings.
        """
        from engines.content.models import Embedding

        logger.info("generating_embeddings", chunk_count=len(chunks))

        for chunk in chunks:
            try:
                embedding_data = EmbeddingService.create_embedding_record(
                    content_type="chunk",
                    content_id=str(chunk.id),
                    text=chunk.chunk_text,
                )

                # CREATE THE RECORD IN DATABASE
                Embedding.objects.create(
                    content_type=embedding_data["content_type"],
                    content_id=embedding_data["content_id"],
                    vector=embedding_data["vector"],
                    model_name=embedding_data["model_name"],
                )

                logger.info("embedding_created", chunk_id=str(chunk.id))

            except Exception as e:
                sentry_sdk.capture_exception(e)
                logger.error(
                    "embedding_generation_failed", chunk_id=str(chunk.id), error=str(e)
                )
