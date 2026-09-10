"""
RAG Retriever Service
Embeds queries using Ollama bge-m3 and retrieves relevant chunks from Qdrant.
Used to enrich AI prompts with government scheme docs, HCES data, and business guides.
"""

import logging

import httpx
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class RAGRetriever:
    """
    Retrieves relevant knowledge chunks from Qdrant for prompt context enrichment.
    Uses Ollama bge-m3 for embeddings (running locally).
    """

    def __init__(self) -> None:
        self._client: AsyncQdrantClient | None = None

    @property
    def client(self) -> AsyncQdrantClient:
        if self._client is None:
            self._client = AsyncQdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
            )
        return self._client

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding using Ollama bge-m3."""
        async with httpx.AsyncClient(timeout=60.0) as http:
            response = await http.post(
                f"{settings.ollama_base_url}/api/embeddings",
                json={"model": settings.ollama_embed_model, "prompt": text},
            )
            response.raise_for_status()
            data = response.json()
            return data["embedding"]

    async def ensure_collection(self) -> None:
        """Create Qdrant collection if it doesn't exist."""
        try:
            collections = await self.client.get_collections()
            existing = [c.name for c in collections.collections]
            if settings.qdrant_collection_name not in existing:
                # bge-m3 produces 1024-dim embeddings
                await self.client.create_collection(
                    collection_name=settings.qdrant_collection_name,
                    vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
                )
                logger.info(f"Created Qdrant collection: {settings.qdrant_collection_name}")
        except Exception as e:
            logger.warning(f"Qdrant collection check failed: {e}")

    async def retrieve(
        self,
        query: str,
        business_category: str,
        state_code: str,
        top_k: int = 4,
    ) -> str:
        """
        Retrieve relevant context chunks for a query.
        Returns formatted text ready to inject into AI prompt.
        """
        try:
            query_vector = await self.embed_text(query)

            # Build filter: prefer documents matching the category or state
            results = await self.client.search(
                collection_name=settings.qdrant_collection_name,
                query_vector=query_vector,
                limit=top_k,
                with_payload=True,
            )

            if not results:
                return self._fallback_context(business_category)

            chunks = []
            for hit in results:
                if hit.score > 0.35:  # Relevance threshold
                    payload = hit.payload or {}
                    source = payload.get("source", "Knowledge Base")
                    text = payload.get("text", "")
                    if text:
                        chunks.append(f"[{source}]\n{text}")

            if chunks:
                return "\n\n".join(chunks)
            return self._fallback_context(business_category)

        except Exception as e:
            logger.warning(f"RAG retrieval failed: {e}. Using fallback context.")
            return self._fallback_context(business_category)

    def _fallback_context(self, business_category: str) -> str:
        """Minimal fallback context when Qdrant is unavailable."""
        fallbacks = {
            "dairy": "Dairy business in rural India requires access to milk collection infrastructure. Maharashtra has cooperative dairy networks (Mahanand) that provide market linkage. Seasonal variation is common with peak in winter months.",
            "agriculture": "Agriculture-based businesses benefit from proximity to mandis. AGMARKNET data shows commodity price trends. Kisan Credit Card and PMFBY schemes support agricultural enterprises.",
            "food_processing": "Food processing units require FSSAI registration. Cold chain infrastructure is critical. Local value addition increases margins by 30-60% over raw commodity prices.",
            "retail": "Rural retail faces competition from weekly haats and urban supply chains. Digital payment adoption (UPI) is growing in rural Maharashtra. Credit-based selling is common.",
            "textiles": "Maharashtra's textile sector is supported by PowerTex India scheme. Handloom clusters have access to cooperative marketing. Raw cotton sourcing is key cost driver.",
        }
        return fallbacks.get(
            business_category.lower(),
            "Rural micro-enterprises in India benefit from local market knowledge, government scheme support, and community trust. NBCFDC provides concessional credit for first-generation entrepreneurs from marginalized communities.",
        )

    async def index_document(
        self,
        text: str,
        metadata: dict,
        doc_id: str,
    ) -> bool:
        """Index a document chunk into Qdrant."""
        try:
            await self.ensure_collection()
            vector = await self.embed_text(text)
            await self.client.upsert(
                collection_name=settings.qdrant_collection_name,
                points=[
                    {
                        "id": doc_id,
                        "vector": vector,
                        "payload": {"text": text, **metadata},
                    }
                ],
            )
            return True
        except Exception as e:
            logger.error(f"Failed to index document {doc_id}: {e}")
            return False
