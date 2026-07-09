from unittest.mock import AsyncMock, MagicMock

import pytest

from src.intelligence.rag import RAGPipeline


@pytest.mark.asyncio
async def test_rag_ingest_documents() -> None:
    """Test document chunking, embedding generation, and Qdrant collections ingestion."""
    # Mock LLM Client
    mock_llm = MagicMock()
    mock_llm.get_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])

    # Instantiate pipeline with mock elements
    pipeline = RAGPipeline(llm_client=mock_llm, qdrant_url="http://localhost:6333")

    # Mock AsyncQdrantClient internals
    mock_qdrant_client = AsyncMock()
    # Mock get_collections returning empty
    mock_collections_res = MagicMock()
    mock_collections_res.collections = []
    mock_qdrant_client.get_collections.return_value = mock_collections_res
    pipeline.client = mock_qdrant_client

    documents = [
        {
            "id": "doc_1",
            "text": "Short FAQ entry context.",
            "metadata": {"source": "faq"},
        },
        {
            "id": "doc_2",
            "text": "A" * 600,  # exceeds 500 chars -> should trigger chunking into 2 parts
            "metadata": {"source": "manual"},
        },
    ]

    await pipeline.ingest_documents(documents)

    # 1. Assert get_embedding was called for sample and chunks
    # One for 'sample' to verify vector_size, one for 'doc_1', two for the chunked 'doc_2' (total: 4)
    assert mock_llm.get_embedding.call_count == 4

    # 2. Assert collection creation was triggered because it wasn't found
    mock_qdrant_client.create_collection.assert_called_once()

    # 3. Assert upsert points to qdrant
    mock_qdrant_client.upsert.assert_called_once()
    called_points = mock_qdrant_client.upsert.call_args[1]["points"]
    # doc_1 (1 point) + doc_2 (chunked into 2 points) = 3 total points
    assert len(called_points) == 3


@pytest.mark.asyncio
async def test_rag_retrieve_context() -> None:
    """Test retrieving semantic matching context from Qdrant."""
    mock_llm = MagicMock()
    mock_llm.get_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])

    pipeline = RAGPipeline(llm_client=mock_llm, qdrant_url="http://localhost:6333")

    mock_qdrant_client = AsyncMock()
    # Mock get_collections returning our collection name
    mock_col = MagicMock()
    mock_col.name = "support_knowledge"
    mock_collections_res = MagicMock()
    mock_collections_res.collections = [mock_col]
    mock_qdrant_client.get_collections.return_value = mock_collections_res

    # Mock search result
    hit1 = MagicMock()
    hit1.payload = {"text": "Context paragraph matching text sequence."}
    mock_qdrant_client.search.return_value = [hit1]

    pipeline.client = mock_qdrant_client

    results = await pipeline.retrieve_context("how do I get a refund?", top_k=2)

    assert len(results) == 1
    assert results[0]["text"] == "Context paragraph matching text sequence."
    mock_qdrant_client.search.assert_called_once()
