"""
Document Chunker module for RAG ingestion (Version 7).

Splits parsed document pages into overlapping text chunks with preserved source metadata:
- document_id
- filename
- chunk_id
- page
- text
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)


class DocumentChunker:
    """
    Splits document pages into text chunks with configurable size and overlap.
    """

    def __init__(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> None:
        """
        Initialize chunker with configurable chunk parameters.

        Args:
            chunk_size (Optional[int]): Max characters per chunk (default from settings).
            chunk_overlap (Optional[int]): Overlapping characters between consecutive chunks.
        """
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP

        if self.chunk_overlap >= self.chunk_size:
            logger.warning(
                "Chunk overlap (%d) >= chunk size (%d). Clamping overlap to %d",
                self.chunk_overlap,
                self.chunk_size,
                max(0, self.chunk_size // 4),
            )
            self.chunk_overlap = max(0, self.chunk_size // 4)

    def _split_text(self, text: str) -> List[str]:
        """
        Split a block of text using recursive boundary preferences:
        double newlines -> single newlines -> periods -> spaces -> hard slice.
        """
        text = text.strip()
        if not text:
            return []

        if len(text) <= self.chunk_size:
            return [text]

        chunks: List[str] = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + self.chunk_size, text_len)

            if end < text_len:
                # Search backwards for a natural break point (paragraph, sentence, or word boundary)
                segment = text[start:end]
                best_break = -1
                for sep in ["\n\n", "\n", ". ", "? ", "! ", " "]:
                    idx = segment.rfind(sep)
                    if idx != -1 and idx >= len(segment) // 3:
                        best_break = idx + len(sep)
                        break

                if best_break != -1:
                    end = start + best_break

            chunk_str = text[start:end].strip()
            if chunk_str:
                chunks.append(chunk_str)

            # Advance by step size (chunk_size - overlap)
            step = max(1, (end - start) - self.chunk_overlap)
            start += step

        return chunks

    def chunk_pages(
        self,
        pages_data: List[Dict[str, Any]],
        document_id: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Process parsed pages into structured chunks with complete citation metadata.

        Args:
            pages_data (List[Dict[str, Any]]): List of dicts with 'text', 'page', 'filename'.
            document_id (Optional[str]): Assigned document ID or auto-generated.
            filename (Optional[str]): Document file name.

        Returns:
            List[Dict[str, Any]]: List of chunk dicts ready for embedding and storage.
        """
        doc_id = document_id or f"doc_{uuid.uuid4().hex[:12]}"
        chunks: List[Dict[str, Any]] = []
        global_chunk_idx = 0

        for page_item in pages_data:
            page_text = page_item.get("text", "")
            page_num = page_item.get("page", 1)
            file_name = filename or page_item.get("filename", "unknown_document")

            text_splits = self._split_text(page_text)
            for split_text in text_splits:
                chunks.append(
                    {
                        "chunk_id": global_chunk_idx,
                        "document_id": doc_id,
                        "filename": file_name,
                        "page": page_num,
                        "text": split_text,
                    }
                )
                global_chunk_idx += 1

        logger.info(
            "Chunked document '%s' (ID: %s) into %d chunks (chunk_size=%d, overlap=%d).",
            filename,
            doc_id,
            len(chunks),
            self.chunk_size,
            self.chunk_overlap,
        )
        return chunks
