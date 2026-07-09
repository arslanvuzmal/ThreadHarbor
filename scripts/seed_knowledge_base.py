import asyncio
import os
import sys

# Ensure project root is in python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.intelligence.llm_client import LLMClient
from src.intelligence.rag import RAGPipeline
from src.utils.config import get_settings


DUMMY_FAQ = [
    {
        "id": "faq_1",
        "text": (
            "How do I check my order status? To track your order, send 'check order' along with your order ID "
            "(e.g. check order status 12345). Alternatively, our system will lookup order updates dynamically in the "
            "system status tracker."
        ),
        "metadata": {"category": "orders"},
    },
    {
        "id": "faq_2",
        "text": (
            "What is your refund policy? We offer full refunds within 30 days of purchase. Refunds are processed "
            "automatically but any item over $500 requires manual approval. To request, mention 'refund' to our "
            "support bot."
        ),
        "metadata": {"category": "billing"},
    },
    {
        "id": "faq_3",
        "text": (
            "How do I connect to a human agent? If you want to speak with a human support agent, simply type 'agent', "
            "'human', or 'representative' and the bot will immediately escalate the ticket to manual support handoff."
        ),
        "metadata": {"category": "escalations"},
    },
    {
        "id": "faq_4",
        "text": (
            "What are your shipping times? Standard domestic shipping takes 3-5 business days. International deliveries "
            "can take 7-14 business days depending on customs and shipping options selected at checkout."
        ),
        "metadata": {"category": "shipping"},
    },
    {
        "id": "faq_5",
        "text": (
            "Can I cancel my order? Orders can be cancelled within 1 hour of placing them. Go to your orders dashboard "
            "or ask the support bot to initiate standard cancellations."
        ),
        "metadata": {"category": "orders"},
    },
]


async def seed() -> None:
    """Seeds the Qdrant local Vector DB with test FAQ documents."""
    settings = get_settings()
    # Check if OPENAI_API_KEY is dummy/missing to warn
    if settings.OPENAI_API_KEY == "dummy" or not settings.OPENAI_API_KEY:
        print("Warning: OPENAI_API_KEY is not set or is 'dummy'. Embbeddings call may fail if real server isn't mocked.")

    print(f"Connecting to Qdrant at {settings.QDRANT_URL}...")
    llm_client = LLMClient(api_key=settings.OPENAI_API_KEY, embedding_model=settings.LLM_EMBEDDING_MODEL)
    rag = RAGPipeline(llm_client=llm_client, qdrant_url=settings.QDRANT_URL)

    print("Ingesting dummy documents into support_knowledge collection...")
    try:
        await rag.ingest_documents(DUMMY_FAQ)
        print("Success! Seeding completed successfully.")
    except Exception as e:
        print(f"Error during seeding: {e}")


if __name__ == "__main__":
    # Ensure OPENAI_API_KEY is present for execution
    if "OPENAI_API_KEY" not in os.environ:
        os.environ["OPENAI_API_KEY"] = "dummy_key_seeding"
    asyncio.run(seed())
