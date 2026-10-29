
import logging
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG_DIR / "background_tasks.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def notify_document_uploaded(
    document_id: int,
    filename: str,
    username: str,
) -> None:
    """Record a notification after a document upload."""
    logger.info(
        "Document upload notification: document_id=%s filename=%s username=%s time=%s",
        document_id,
        filename,
        username,
        datetime.now(timezone.utc).isoformat(),
    )
