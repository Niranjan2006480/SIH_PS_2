"""
RAG Document Indexer
Extracts knowledge from HCES PDF, scheme documents, and category guides,
and indexes embedded chunks into Qdrant for semantic search.
"""

import logging
import uuid
from app.ai.rag_retriever import RAGRetriever

logger = logging.getLogger(__name__)

DOMAIN_KNOWLEDGE_DOCS = [
    {
        "category": "dairy",
        "title": "Rural Dairy Feasibility Guide",
        "source": "NABARD Dairy Sector Guide",
        "text": (
            "Dairy processing and milk collection centers in rural Maharashtra benefit from high "
            "milk density and cooperative collection routes (Mahanand, Amul, Chitale). "
            "A mini dairy unit handling 200-500 liters/day requires chilling infrastructure and milk fat testers. "
            "Value addition into paneer, curd, and ghee yields 30-45% higher gross profit margins than raw milk."
        ),
    },
    {
        "category": "agriculture",
        "title": "Agri-Processing & Custom Hiring Centers",
        "source": "PMFME & Sub-Mission on Agricultural Mechanization",
        "text": (
            "Custom Hiring Centers (CHC) for farm equipment and village-level grading/packing units "
            "serve small and marginal farmers. Direct linkage to district APMC mandis and weekly village "
            "haats ensures steady cash flow. Subsidy under AIF (Agriculture Infrastructure Fund) provides "
            "3% interest subvention for loans up to ₹2 Crore."
        ),
    },
    {
        "category": "food_processing",
        "title": "Micro Food Processing Enterprises",
        "source": "PM Formalisation of Micro food processing Enterprises (PMFME)",
        "text": (
            "Local grain milling, spice grinding, and pulse processing units have strong daily rural demand. "
            "Under PMFME, individual micro-enterprises receive 35% credit-linked capital subsidy up to ₹10 Lakhs. "
            "Basic FSSAI registration and hygienic packaging allow selling at 15-20% price premium."
        ),
    },
    {
        "category": "retail",
        "title": "Rural Retail & Kirana Modernization",
        "source": "CAIT Rural Commerce Study",
        "text": (
            "Rural general stores and grocery outlets thrive on fast-moving consumer goods (FMCG) and farm inputs. "
            "Average inventory turnover in rural belts is 18-25 days. Offering digital UPI payments and monthly "
            "credit accounts to known farming families drives customer loyalty."
        ),
    },
    {
        "category": "financial_schemes",
        "title": "NBCFDC Concessional Credit Schemes",
        "source": "NBCFDC Scheme Guidelines 2024",
        "text": (
            "NBCFDC provides term loans and working capital assistance through State Channelising Agencies (SCAs). "
            "General Term Loan covers up to 90% of project cost up to ₹15 Lakhs at 6% annual interest for beneficiaries. "
            "Micro Finance scheme offers loans up to ₹1,00,000 per beneficiary at 5% interest with minimal paperwork."
        ),
    },
]


async def index_domain_knowledge() -> int:
    """Indexes pre-curated rural domain knowledge into Qdrant."""
    retriever = RAGRetriever()
    await retriever.ensure_collection()

    count = 0
    for doc in DOMAIN_KNOWLEDGE_DOCS:
        doc_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"udyamai_{doc['title']}"))
        success = await retriever.index_document(
            text=doc["text"],
            metadata={
                "category": doc["category"],
                "title": doc["title"],
                "source": doc["source"],
            },
            doc_id=doc_id,
        )
        if success:
            count += 1

    logger.info("Indexed %d knowledge documents into Qdrant", count)
    return count
