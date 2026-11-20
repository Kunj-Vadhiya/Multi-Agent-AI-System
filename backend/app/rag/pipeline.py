"""
RAG Pipeline module (Version 7).

Orchestrates the complete document ingestion, chunking, embedding, storage,
and retrieval workflow:
Document -> Loader -> Chunker -> Embeddings -> VectorStore -> Retriever
"""

import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.rag.chunker import DocumentChunker
from app.rag.embeddings import EmbeddingService, get_embedding_service
from app.rag.loader import DocumentLoader
from app.rag.retriever import Retriever, get_retriever
from app.rag.vector_store import VectorStore, get_vector_store

logger = logging.getLogger(__name__)


class RAGPipeline:
    """
    Unified coordinator for document ingestion and retrieval.
    """

    def __init__(
        self,
        loader: Optional[DocumentLoader] = None,
        chunker: Optional[DocumentChunker] = None,
        embeddings: Optional[EmbeddingService] = None,
        vector_store: Optional[VectorStore] = None,
        retriever: Optional[Retriever] = None,
    ) -> None:
        self.loader = loader or DocumentLoader()
        self.chunker = chunker or DocumentChunker()
        self.embeddings = embeddings or get_embedding_service()
        self.vector_store = vector_store or get_vector_store()
        self.retriever = retriever or get_retriever()

    def ingest_file(
        self,
        file_path: Path,
        filename: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute end-to-end document ingestion:
        1. Extract text via DocumentLoader
        2. Chunk text via DocumentChunker with metadata
        3. Generate vector embeddings via EmbeddingService
        4. Store chunks and embeddings into VectorStore

        Args:
            file_path (Path): Path to document on disk.
            filename (Optional[str]): Original filename (defaults to file_path.name).
            document_id (Optional[str]): Assigned ID or auto-generated.

        Returns:
            Dict[str, Any]: Ingestion status summary including document_id and chunks_created.
        """
        actual_filename = filename or file_path.name
        doc_id = document_id or f"doc_{uuid.uuid4().hex[:8]}"

        logger.info("Starting ingestion of '%s' (ID: %s)...", actual_filename, doc_id)

        # 1. Parse document pages
        pages_data = self.loader.load(file_path)
        if not pages_data:
            logger.warning("No extractable content found in '%s'", actual_filename)
            return {
                "document_id": doc_id,
                "filename": actual_filename,
                "chunks_created": 0,
                "status": "empty_document",
            }

        # 2. Chunk text
        chunks = self.chunker.chunk_pages(
            pages_data=pages_data,
            document_id=doc_id,
            filename=actual_filename,
        )
        if not chunks:
            return {
                "document_id": doc_id,
                "filename": actual_filename,
                "chunks_created": 0,
                "status": "no_chunks_generated",
            }

        # 3. Generate embeddings
        chunk_texts = [c["text"] for c in chunks]
        logger.info("Generating embeddings for %d chunks of '%s'...", len(chunks), actual_filename)
        embeddings = self.embeddings.embed_documents(chunk_texts)

        # 4. Store in vector database
        stored_count = self.vector_store.add_documents(chunks, embeddings)

        logger.info(
            "Ingestion completed for '%s'. Successfully stored %d chunks.",
            actual_filename,
            stored_count,
        )

        return {
            "document_id": doc_id,
            "filename": actual_filename,
            "chunks_created": stored_count,
            "status": "success",
        }

    def retrieve(self, query: str, top_k: Optional[int] = None) -> Dict[str, Any]:
        """
        Retrieve relevant knowledge base chunks and format as context.

        Args:
            query (str): Search query or user question.
            top_k (Optional[int]): Number of chunks to retrieve.

        Returns:
            Dict[str, Any]: Contains 'chunks' (List[Dict]) and 'context' (str).
        """
        chunks = self.retriever.retrieve(query=query, top_k=top_k)
        context = self.retriever.format_context(chunks) if chunks else ""
        return {
            "chunks": chunks,
            "context": context,
        }


_pipeline_instance: Optional[RAGPipeline] = None


def get_rag_pipeline() -> RAGPipeline:
    """Get or initialize singleton RAGPipeline."""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = RAGPipeline()
    return _pipeline_instance
