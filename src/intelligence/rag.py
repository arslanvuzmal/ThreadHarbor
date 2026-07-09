from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams

from src.intelligence.llm_client import LLMClient
from src.utils.logger import get_logger

logger = get_logger(__name__)


class RAGPipeline:
    """Manages the knowledge base collection, processing documents, and generating context via Qdrant and LLM Client."""

    def __init__(
        self,
        llm_client: LLMClient,
        qdrant_url: str = "http://localhost:6333",
        api_key: str | None = None,
        collection_name: str = "support_knowledge",
    ) -> None:
        """Initialize AsyncQdrantClient and save metadata targets."""
        self.llm_client = llm_client
        self.client = AsyncQdrantClient(url=qdrant_url, api_key=api_key)
        self.collection_name = collection_name

    async def _ensure_collection_exists(self, vector_size: int) -> None:
        """Ensure collection exists in Qdrant; creates it if not."""
        collections_response = await self.client.get_collections()
        collection_names = [col.name for col in collections_response.collections]
        if self.collection_name not in collection_names:
            logger.info("Creating Qdrant collection", collection=self.collection_name, size=vector_size)
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )

    def _chunk_text(self, text: str, max_length: int = 500) -> list[str]:
        """Splits the text into smaller chunks if it exceeds the maximum character threshold."""
        if len(text) <= max_length:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + max_length
            # Try to slide back to find a space or period, to avoid splitting mid-word
            if end < len(text):
                last_space = text.rfind(" ", start, end)
                if last_space != -1 and last_space > start + (max_length // 2):
                    end = last_space + 1
            chunks.append(text[start:end].strip())
            start = end
        return chunks

    async def ingest_documents(self, documents: list[dict[str, Any]]) -> None:
        """Processes incoming documents, chunks large texts, embeds, and uploads into Qdrant collection."""
        if not documents:
            return

        points = []
        # Get first embedding size to ensure the collection exists
        sample_embed = await self.llm_client.get_embedding("sample")
        vector_size = len(sample_embed)
        await self._ensure_collection_exists(vector_size)

        point_idx = 0
        for doc in documents:
            doc_id = doc.get("id", "")
            raw_text = doc.get("text", "")
            meta = doc.get("metadata", {})

            # Chunk text
            chunks = self._chunk_text(raw_text, max_length=500)

            for chunk_idx, chunk in enumerate(chunks):
                # Embed each chunk
                vector = await self.llm_client.get_embedding(chunk)

                # Merge chunk data with payload metadata
                payload = {
                    "doc_id": doc_id,
                    "text": chunk,
                    "chunk_idx": chunk_idx,
                    **meta,
                }

                # Construct points using unique IDs (use sequential hash or compound ID)
                unique_point_id = f"{doc_id}_{chunk_idx}_{point_idx}"
                points.append(
                    PointStruct(
                        id=point_idx + hash(unique_point_id) % 100000000,
                        vector=vector,
                        payload=payload,
                    )
                )
                point_idx += 1

        if points:
            await self.client.upsert(
                collection_name=self.collection_name,
                points=points,
            )
            logger.info(
                "Ingested documents to vector DB",
                document_count=len(documents),
                point_count=len(points),
            )

    async def retrieve_context(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        """Query Qdrant for semantic neighbors of the search query and extract matching contexts."""
        # Embed query
        query_vector = await self.llm_client.get_embedding(query)

        # Check if collection exists
        collections_response = await self.client.get_collections()
        collection_names = [col.name for col in collections_response.collections]
        if self.collection_name not in collection_names:
            logger.warning(
                "Search triggered but collection does not exist in Qdrant yet.",
                collection=self.collection_name,
            )
            return []

        search_result = await self.client.search(  # type: ignore[attr-defined]
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=top_k,
        )

        results = []
        for hit in search_result:
            if hit.payload:
                results.append(hit.payload)

        return results
