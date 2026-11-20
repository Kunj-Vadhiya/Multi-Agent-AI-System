"""
Tests for Semantic Retrieval, Top-K Matching, and Source Metadata Preservation (Version 7).

Verifies:
- Test 12: Top-K semantic retrieval returns relevant document chunks.
- Test 13: RAG context integration with formatted citations.
- Test 14: Source metadata integrity (document_id, filename, chunk_id, page).
"""

import tempfile
from pathlib import Path

import pytest

from app.rag.embeddings import EmbeddingService
from app.rag.pipeline import RAGPipeline
from app.rag.retriever import Retriever
from app.rag.vector_store import VectorStore


def test_semantic_retrieval_ranking():
    """
    Test 12: Query retrieves top-K relevant chunks ranked by cosine similarity.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "retrieval_test.db")
        vs = VectorStore(db_path=db_path)
        emb_service = EmbeddingService()

        pipeline = RAGPipeline(vector_store=vs, embeddings=emb_service)

        doc1 = Path(tmpdir) / "transformers.txt"
        doc1.write_text(
            "The Transformer model uses self-attention mechanisms to process sequence data in parallel. "
            "It consists of an encoder stack and a decoder stack, each containing multi-head attention and feedforward layers.",
            encoding="utf-8",
        )
        pipeline.ingest_file(doc1, filename="transformers.txt")

        doc2 = Path(tmpdir) / "cnn.txt"
        doc2.write_text(
            "Convolutional Neural Networks (CNNs) utilize spatial convolutions and pooling layers "
            "designed specifically for computer vision tasks and image classification.",
            encoding="utf-8",
        )
        pipeline.ingest_file(doc2, filename="cnn.txt")

        retriever = Retriever(vector_store=vs, embedding_service=emb_service)

        # Query specifically about self-attention
        results = retriever.retrieve("How does the transformer self-attention mechanism work?", top_k=2)

        assert len(results) > 0
        top_match = results[0]
        # Transformers document should rank higher than CNN document for this query
        assert top_match["metadata"]["filename"] == "transformers.txt"
        assert top_match["similarity_score"] > 0.0
        assert "self-attention" in top_match["text"].lower()


def test_source_metadata_preservation():
    """
    Test 14: Every retrieved chunk retains accurate document, page, and chunk_id metadata.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "meta_test.db")
        vs = VectorStore(db_path=db_path)
        emb_service = EmbeddingService()
        pipeline = RAGPipeline(vector_store=vs, embeddings=emb_service)

        test_file = Path(tmpdir) / "transformer_notes.txt"
        test_file.write_text(
            "Attention Is All You Need is the seminal paper published by Vaswani et al. in 2017 introducing the Transformer.",
            encoding="utf-8",
        )
        ingest_res = pipeline.ingest_file(test_file, filename="transformer_notes.pdf")

        retriever = Retriever(vector_store=vs, embedding_service=emb_service)
        results = retriever.retrieve("Vaswani Attention Is All You Need 2017", top_k=1)

        assert len(results) == 1
        meta = results[0]["metadata"]
        assert meta["filename"] == "transformer_notes.pdf"
        assert meta["document_id"] == ingest_res["document_id"]
        assert "page" in meta
        assert "chunk_id" in meta


def test_rag_context_formatting():
    """
    Test 13: Retriever.format_context formats retrieved chunks with explicit citation labels.
    """
    retriever = Retriever()

    chunks = [
        {
            "text": "Retrieval-Augmented Generation combines an information retrieval system with a generative model.",
            "similarity_score": 0.88,
            "metadata": {"filename": "rag_paper.pdf", "page": 3, "chunk_id": 12},
        },
        {
            "text": "Dense passage retrieval uses bi-encoder architectures to index passages efficiently.",
            "similarity_score": 0.75,
            "metadata": {"filename": "dpr_paper.pdf", "page": 1, "chunk_id": 4},
        },
    ]

    context = retriever.format_context(chunks)

    assert "[Source 1: rag_paper.pdf | Page 3 | Chunk 12 | Relevance: 0.88]" in context
    assert "[Source 2: dpr_paper.pdf | Page 1 | Chunk 4 | Relevance: 0.75]" in context
    assert "Dense passage retrieval" in context
