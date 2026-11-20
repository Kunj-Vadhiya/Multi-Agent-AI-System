"""
Local Vector Store module for RAG (Version 7).

Stores:
- Document chunk text
- Embedding vectors
- Citation metadata (document_id, filename, chunk_id, page)

Persists locally to SQLite database for zero-dependency, crash-resilient storage across restarts.
Computes cosine similarity ranking for top-k semantic retrieval.
"""

import contextlib
import json
import logging
import math
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Calculate cosine similarity between two floating point vectors."""
    if len(vec_a) != len(vec_b) or not vec_a:
        return 0.0
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a, b in zip(vec_a, vec_a)))
    norm_b = math.sqrt(sum(b * b for a, b in zip(vec_b, vec_b)))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot_product / (norm_a * norm_b)


class VectorStore:
    """
    Lightweight, persistent local vector database backed by SQLite.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        """
        Initialize vector store at specified path or default settings path.
        """
        raw_path = db_path or settings.VECTOR_DB_PATH
        # If file ends with .json, change to .db for SQLite storage
        if raw_path.endswith(".json"):
            raw_path = raw_path[:-5] + ".db"
        self.db_path = raw_path
        self._lock = threading.Lock()
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextlib.contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Create vector chunks table if not exists."""
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS document_chunks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        document_id TEXT NOT NULL,
                        filename TEXT NOT NULL,
                        chunk_id INTEGER NOT NULL,
                        page INTEGER NOT NULL,
                        text TEXT NOT NULL,
                        metadata TEXT NOT NULL,
                        embedding TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_doc_id ON document_chunks (document_id)"
                )
                conn.commit()

    def add_documents(
        self,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]],
    ) -> int:
        """
        Store document chunks and their corresponding embedding vectors.

        Args:
            chunks (List[Dict[str, Any]]): Chunk records with text and metadata.
            embeddings (List[List[float]]): Computed embedding vectors.

        Returns:
            int: Number of chunks successfully stored.
        """
        if len(chunks) != len(embeddings):
            raise ValueError("Number of chunks and embeddings must match.")

        rows_to_insert = []
        for chunk, emb in zip(chunks, embeddings):
            metadata_dict = {
                "document_id": chunk.get("document_id", ""),
                "filename": chunk.get("filename", ""),
                "chunk_id": chunk.get("chunk_id", 0),
                "page": chunk.get("page", 1),
            }
            rows_to_insert.append(
                (
                    metadata_dict["document_id"],
                    metadata_dict["filename"],
                    metadata_dict["chunk_id"],
                    metadata_dict["page"],
                    chunk.get("text", ""),
                    json.dumps(metadata_dict),
                    json.dumps(emb),
                )
            )

        with self._lock:
            with self._get_connection() as conn:
                conn.executemany(
                    """
                    INSERT INTO document_chunks (
                        document_id, filename, chunk_id, page, text, metadata, embedding
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows_to_insert,
                )
                conn.commit()

        logger.info("Persisted %d chunks into VectorStore at '%s'", len(rows_to_insert), self.db_path)
        return len(rows_to_insert)

    def similarity_search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search using cosine similarity ranking against stored chunks.

        Args:
            query_embedding (List[float]): Query vector.
            top_k (int): Maximum number of results to return.

        Returns:
            List[Dict[str, Any]]: Top relevant chunks ordered by descending similarity score.
        """
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT document_id, filename, chunk_id, page, text, metadata, embedding FROM document_chunks"
                )
                rows = cursor.fetchall()

        if not rows:
            logger.info("VectorStore is currently empty. Returning 0 search results.")
            return []

        scored_results: List[Dict[str, Any]] = []
        for r in rows:
            try:
                emb = json.loads(r["embedding"])
                score = cosine_similarity(query_embedding, emb)
                meta = json.loads(r["metadata"])
                scored_results.append(
                    {
                        "text": r["text"],
                        "similarity_score": round(score, 4),
                        "metadata": meta,
                    }
                )
            except Exception as err:
                logger.warning("Error computing similarity for row %s: %s", r["id"], err)
                continue

        # Sort descending by score
        scored_results.sort(key=lambda x: x["similarity_score"], reverse=True)
        top_results = scored_results[:top_k]

        logger.info(
            "Semantic retrieval matched %d candidate chunks, returning top %d (best score: %.4f)",
            len(scored_results),
            len(top_results),
            top_results[0]["similarity_score"] if top_results else 0.0,
        )
        return top_results

    def count(self) -> int:
        """Return total number of chunks stored."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM document_chunks")
                return int(cursor.fetchone()[0])

    def list_documents(self) -> List[Dict[str, Any]]:
        """Return distinct documents and total chunks."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT document_id, filename, COUNT(*) as chunk_count
                    FROM document_chunks
                    GROUP BY document_id, filename
                    """
                )
                return [
                    {
                        "document_id": r["document_id"],
                        "filename": r["filename"],
                        "chunk_count": r["chunk_count"],
                    }
                    for r in cursor.fetchall()
                ]

    def delete_document(self, document_id: str) -> int:
        """Delete all chunks for a document_id from the vector store."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM document_chunks WHERE document_id = ?",
                    (document_id,),
                )
                conn.commit()
                deleted_count = cursor.rowcount
        logger.info("Deleted document '%s' (%d chunks removed).", document_id, deleted_count)
        return deleted_count

    def clear(self) -> None:
        """Clear all stored documents from vector database."""
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM document_chunks")
                conn.commit()
        logger.info("Cleared all records from VectorStore.")



# Global singleton instance
_vector_store_instance: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Get or initialize singleton VectorStore."""
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = VectorStore()
    return _vector_store_instance
