"""
Tests for RAG Ingestion, Chunking, Embeddings, and Vector Storage (Version 7).

Verifies:
- Test 8: Document Ingestion (TXT, Markdown, and PDF).
- Test 9: Chunking produces structured chunks with preserved metadata.
- Test 10: Embedding generation produces normalized vectors.
- Test 11: Vector database stores chunks and embeddings with SQLite persistence.
"""

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.rag.chunker import DocumentChunker
from app.rag.embeddings import EmbeddingService, FastEmbedEmbeddingProvider, DeterministicHashEmbeddingProvider
from app.rag.loader import DocumentLoader
from app.rag.pipeline import RAGPipeline
from app.rag.vector_store import VectorStore


@pytest.fixture
def client():
    return TestClient(app)


def test_document_loader_txt_and_md():
    """
    Test 8a: Verify DocumentLoader correctly parses TXT and Markdown files.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        txt_path = Path(tmpdir) / "sample.txt"
        txt_path.write_text("This is a plain text document about transformers and attention.", encoding="utf-8")

        md_path = Path(tmpdir) / "notes.md"
        md_path.write_text("# Transformer Architecture\n\nSelf-attention allows global receptive fields.", encoding="utf-8")

        txt_pages = DocumentLoader.load(txt_path)
        assert len(txt_pages) == 1
        assert "transformers" in txt_pages[0]["text"]
        assert txt_pages[0]["page"] == 1
        assert txt_pages[0]["filename"] == "sample.txt"

        md_pages = DocumentLoader.load(md_path)
        assert len(md_pages) == 1
        assert "Self-attention" in md_pages[0]["text"]
        assert md_pages[0]["filename"] == "notes.md"


def test_document_chunker_metadata_preservation():
    """
    Test 9: Verify DocumentChunker chunks text and preserves metadata (document_id, filename, chunk_id, page).
    """
    chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)

    pages = [
        {"text": "Paragraph 1: Transformers revolutionized natural language processing by replacing recurrent units with multi-head self-attention mechanisms. This allowed parallel computation across sequence lengths.", "page": 1, "filename": "nlp.txt"},
        {"text": "Paragraph 2: RAG enhances language models by retrieving external knowledge from vector stores, reducing hallucinations and providing verifiable source citations.", "page": 2, "filename": "nlp.txt"},
    ]

    chunks = chunker.chunk_pages(pages, document_id="doc_test_001", filename="nlp.txt")

    assert len(chunks) >= 2
    for i, chunk in enumerate(chunks):
        assert chunk["document_id"] == "doc_test_001"
        assert chunk["filename"] == "nlp.txt"
        assert chunk["chunk_id"] == i
        assert chunk["page"] in (1, 2)
        assert len(chunk["text"]) > 0


def test_embedding_generation():
    """
    Test 10: Verify EmbeddingService creates embedding vectors of expected dimensions.
    """
    embedding_service = EmbeddingService()
    query = "What is Retrieval-Augmented Generation?"
    vector = embedding_service.embed_query(query)

    assert isinstance(vector, list)
    assert len(vector) > 0
    assert all(isinstance(val, float) for val in vector)

    docs = ["Doc 1 text", "Doc 2 text"]
    doc_vectors = embedding_service.embed_documents(docs)
    assert len(doc_vectors) == 2
    assert len(doc_vectors[0]) == len(vector)


def test_vector_store_persistence_and_count():
    """
    Test 11: Verify VectorStore adds chunks, persists to SQLite, and updates document counts.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_vector_store.db")
        vs = VectorStore(db_path=db_path)

        chunks = [
            {"document_id": "doc_1", "filename": "rag.pdf", "chunk_id": 0, "page": 1, "text": "RAG concept"},
            {"document_id": "doc_1", "filename": "rag.pdf", "chunk_id": 1, "page": 1, "text": "RAG evaluation"},
            {"document_id": "doc_2", "filename": "ann.pdf", "chunk_id": 0, "page": 1, "text": "ANN search"},
        ]
        # 3-dim mock vectors for testing store operations
        embeddings = [[0.1, 0.2, 0.3], [0.1, 0.2, 0.4], [0.8, 0.1, 0.1]]

        added = vs.add_documents(chunks, embeddings)
        assert added == 3
        assert vs.count() == 3

        docs = vs.list_documents()
        assert len(docs) == 2  # doc_1 and doc_2

        # Reopen with fresh instance to confirm SQLite file persistence
        vs_reopened = VectorStore(db_path=db_path)
        assert vs_reopened.count() == 3


def test_upload_document_endpoint(client):
    """
    Test 8b: Test POST /documents/upload FastAPI endpoint.
    """
    file_content = b"This is a test document uploaded via the REST API for knowledge base ingestion."
    response = client.post(
        "/documents/upload",
        files={"file": ("test_ingest.txt", file_content, "text/plain")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["filename"] == "test_ingest.txt"
    assert data["chunks_created"] >= 1
    assert "document_id" in data
