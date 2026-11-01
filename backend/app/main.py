from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router
from app.jobs.routes import router as jobs_router
from app.records.routes import router as records_router
from app.intake.routes import imports_router, uploads_router
from app.core.config import APP_DESCRIPTION, APP_NAME, APP_VERSION, CORS_ORIGINS
from app.core.db import migrate_database
from app.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup initiated")
    migrate_database()
    logger.info("Database tables ensured")
    yield
    logger.info("Application shutdown complete")


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(uploads_router)
app.include_router(imports_router)
app.include_router(records_router)
app.include_router(jobs_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["root"])
def root() -> dict[str, str]:
    return {"message": f"{APP_NAME} is running"}
