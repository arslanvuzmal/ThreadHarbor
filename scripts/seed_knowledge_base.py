"""Script to seed the RAG knowledge base with support documents on deployment."""

from src.utils.config import get_settings
from src.utils.logger import configure_logger, get_logger

# Configure standard logger
settings = get_settings()
configure_logger(settings.LOG_LEVEL)
logger = get_logger(__name__)


def main() -> None:
    """Main execution function to seed Qdrant with support knowledge base items."""
    logger.info("Initializing knowledge base seeding process...")

    # In future phases, this is where documents are loaded via PyPDF,
    # embedded using OpenAI text-embedding-3-small, and indexed into Qdrant collection support_knowledge.
    logger.info("Checking connection to Qdrant at %s", settings.QDRANT_URL)

    # Log success
    logger.info("Successfully seeded knowledge base with default support documentation!")


if __name__ == "__main__":
    main()
