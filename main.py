"""
Facebook CRM API — FastAPI application entry point.

Starts the server, initialises the DB, mounts all routers, and registers
global exception handlers.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.v1.router import router as v1_router
from config import settings
from db.base import init_db

# ─── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
_logger = logging.getLogger(__name__)


# ─── Lifespan (startup / shutdown) ───────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    _logger.info("Starting Facebook CRM API (env=%s)", settings.app_env)
    await init_db()
    _logger.info("Database initialised.")
    yield
    _logger.info("Shutting down Facebook CRM API.")


# ─── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Facebook CRM API",
    description=(
        "Standalone Python REST API for Facebook Graph API integration. "
        "Handles page configs, post fetching, comment fetching, campaign management, "
        "and publishing. Consumed by the Laravel CRM backend."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
# Adjust origins as needed when deploying

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Global exception handlers ────────────────────────────────────────────────

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"success": False, "message": str(exc)},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    _logger.exception("Unhandled exception on %s %s", request.method, request.url)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"success": False, "message": "An internal server error occurred."},
    )


# ─── Routers ──────────────────────────────────────────────────────────────────

app.include_router(v1_router)


# ─── Health check ─────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "env": settings.app_env, "version": "1.0.0"}


@app.get("/api/v1/info", tags=["Health"])
async def info():
    return {
        "name": "Facebook CRM API",
        "version": "1.0.0",
        "fb_graph_version": settings.fb_graph_api_version,
        "debug": settings.debug,
    }


# ─── Dev entrypoint ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
