"""
Retriever module for RAG (Version 7).

Accepts a natural language query, generates its query embedding via EmbeddingService,
and retrieves the top-K semantically closest chunks from VectorStore with exact source metadata.
Formats citation context blocks for consumption by the Research Agent.
"""

import logging
from typing import Any, Dict, List, Optional

from app.config import settings
from app.rag.embeddings import EmbeddingService, get_embedding_service
from app.rag.vector_store import VectorStore, get_vector_store

logger = logging.getLogger(__name__)


class Retriever:
    """
    Semantic search retriever linking EmbeddingService and VectorStore.
    """

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        embedding_service: Optional[EmbeddingService] = None,
    ) -> None:
        self.vector_store = vector_store or get_vector_store()
        self.embedding_service = embedding_service or get_embedding_service()

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve top-K relevant chunks for a user question.

        Args:
            query (str): User question or topic.
            top_k (Optional[int]): Number of chunks to retrieve (defaults to settings.TOP_K).

        Returns:
            List[Dict[str, Any]]: Items containing 'text', 'similarity_score', and 'metadata'.
        """
        k = top_k if top_k is not None else settings.TOP_K
        query_text = query.strip()
        if not query_text:
            return []

        logger.info("Executing RAG retrieval for query: '%s' (top_k=%d)", query_text, k)
        query_embedding = self.embedding_service.embed_query(query_text)
        results = self.vector_store.similarity_search(query_embedding=query_embedding, top_k=k)
        return results

    def format_context(self, retrieved_chunks: List[Dict[str, Any]]) -> str:
        """
        Format retrieved chunks into a structured markdown context string with explicit citations.

        Args:
            retrieved_chunks (List[Dict[str, Any]]): Retrieved chunk list.

        Returns:
            str: Markdown formatted context string for LLM prompts.
        """
        if not retrieved_chunks:
            return "No matching documents found in knowledge base."

        context_blocks = []
        for i, chunk in enumerate(retrieved_chunks, start=1):
            meta = chunk.get("metadata", {})
            filename = meta.get("filename", "unknown_source")
            page = meta.get("page", 1)
            chunk_id = meta.get("chunk_id", i)
            score = chunk.get("similarity_score", 0.0)
            text = chunk.get("text", "").strip()

            header = f"[Source {i}: {filename} | Page {page} | Chunk {chunk_id} | Relevance: {score:.2f}]"
            context_blocks.append(f"{header}\n{text}")

        return "\n\n".join(context_blocks)


_retriever_instance: Optional[Retriever] = None


def get_retriever() -> Retriever:
    """Get or initialize singleton Retriever."""
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = Retriever()
    return _retriever_instance
