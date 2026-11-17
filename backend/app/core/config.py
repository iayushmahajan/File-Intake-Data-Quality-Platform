import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data"))).resolve()
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"
DB_PATH = BASE_DIR / "file_processing.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))

APP_NAME = "Reconcile Workbench"
APP_VERSION = "0.2.0"
APP_DESCRIPTION = (
    "AI-Assisted Data Reconciliation & Quality Workbench: immutable Flights observations, evidence-bounded investigation, explicit human review and traceable exports. Legacy transaction intake remains available."
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# GitHub Models / Azure compatible endpoint
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://models.inference.ai.azure.com")

# Use whatever model is available (you can change later)
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,https://file-intake-processing-service.vercel.app",
    ).split(",")
    if origin.strip()
]

# A database outbox is the source of truth; Redis only transports work.
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_QUEUE = os.getenv("CELERY_QUEUE", "csv-processing")
JOB_TIME_LIMIT_SECONDS = int(os.getenv("JOB_TIME_LIMIT_SECONDS", "120"))
JOB_LEASE_SECONDS = int(os.getenv("JOB_LEASE_SECONDS", "150"))
JOB_MAX_ATTEMPTS = int(os.getenv("JOB_MAX_ATTEMPTS", "3"))
DISPATCH_INTERVAL_SECONDS = float(os.getenv("DISPATCH_INTERVAL_SECONDS", "2"))
JOB_REDISPATCH_SECONDS = int(os.getenv("JOB_REDISPATCH_SECONDS", "30"))
JOB_QUEUE_TIMEOUT_SECONDS = int(os.getenv("JOB_QUEUE_TIMEOUT_SECONDS", "600"))
PUBLISH_MAX_FAILURES = int(os.getenv("PUBLISH_MAX_FAILURES", "8"))
if JOB_TIME_LIMIT_SECONDS < 5 or JOB_LEASE_SECONDS < JOB_TIME_LIMIT_SECONDS + 5:
    raise ValueError(
        "JOB_LEASE_SECONDS must exceed JOB_TIME_LIMIT_SECONDS by at least 5 seconds."
    )
if (
    min(
        JOB_MAX_ATTEMPTS,
        JOB_REDISPATCH_SECONDS,
        JOB_QUEUE_TIMEOUT_SECONDS,
        PUBLISH_MAX_FAILURES,
        DISPATCH_INTERVAL_SECONDS,
    )
    <= 0
):
    raise ValueError("Queue timing and retry settings must be positive.")
