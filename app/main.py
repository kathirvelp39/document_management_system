
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import models
from app.database import Base, engine
from app.routes.auth import router as auth_router
from app.routes.documents import router as documents_router
from app.routes.sharing import router as sharing_router

# Create the logs directory and configure a dedicated file logger.
LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("document_management")
logger.setLevel(logging.INFO)
logger.propagate = False

if not any(
    isinstance(handler, logging.FileHandler)
    and Path(handler.baseFilename).resolve()
    == (LOG_DIR / "api.log").resolve()
    for handler in logger.handlers
):
    file_handler = logging.FileHandler(
        LOG_DIR / "api.log",
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"
        )
    )
    logger.addHandler(file_handler)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    logger.info("Document Management API started")
    yield
    logger.info("Document Management API stopped")


app = FastAPI(
    title="Document Management & Secure File Sharing System",
    lifespan=lifespan,
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    start_time = time.perf_counter()

    try:
        response = await call_next(request)
        elapsed = time.perf_counter() - start_time

        logger.info(
            "%s %s status=%s duration=%.3fs",
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
        )
        return response

    except Exception:
        logger.exception(
            "Unhandled error on %s %s",
            request.method,
            request.url.path,
        )
        raise


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def general_exception_handler(
    request: Request,
    exc: Exception,
):
    logger.exception(
        "Unhandled application exception on %s %s",
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


app.include_router(auth_router)
app.include_router(sharing_router)
app.include_router(documents_router)


@app.get("/")
def home():
    return {
        "message": "Document Management System API is running"
    }


@app.get("/db-check")
def check_database():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    return {"message": "MySQL connection successful"}
