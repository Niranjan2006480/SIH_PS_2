import pytest
from app.ai.rag_retriever import RAGRetriever


@pytest.mark.asyncio
async def test_rag_retriever_query_points_compatibility():
    """
    Verify that RAGRetriever.retrieve() executes query_points() against Qdrant
    without raising AttributeError or deprecated search() errors.
    """
    retriever = RAGRetriever()
    query = "government financial support for a small rural entrepreneur"
    
    # Execute retrieval
    context = await retriever.retrieve(
        query=query,
        business_category="financial_schemes",
        state_code="27",
        top_k=4,
    )
    
    # Verify non-empty context returned
    assert context is not None
    assert len(context) > 0
    # Verify real Qdrant indexed knowledge is present in context
    assert "NBCFDC" in context or "PMFME" in context or "PMFME & Sub-Mission" in context
