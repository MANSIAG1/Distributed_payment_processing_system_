import os
import logging
from datetime import datetime
import pytz
from dotenv import load_dotenv

# Load .env file if available
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("system.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def get_config(key: str, default=None):
    """
    Fetch configuration values from environment variables or use default.
    """
    return os.getenv(key, default)


def get_current_time(timezone: str = "UTC") -> str:
    """
    Returns current timestamp in given timezone.
    """
    tz = pytz.timezone(timezone)
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")


def log_event(event: str):
    """
    Helper to log system events in a consistent way.
    """
    logger.info(event)
