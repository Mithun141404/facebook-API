from typing import List, Optional, Dict, Any
"""
Facebook CRM API — FastAPI application entry point.

Starts the server, initialises the DB, mounts all routers, and registers
global exception handlers.
"""
import logging
from contextlib import asynccontextmanager

import traceback
from fastapi import FastAPI, Request, status, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.router import router as v1_router
from config import settings
from db.base import init_db, get_db
from services.email import alert_admin_error

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
    
    error_trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    bg_tasks = BackgroundTasks()
    bg_tasks.add_task(alert_admin_error, f"Global Exception on {request.method} {request.url}\n\n{error_trace}")

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False, 
            "message": "Our system is currently facing an issue. We have notified the authority and will get back to you shortly."
        },
        background=bg_tasks
    )


# ─── Routers ──────────────────────────────────────────────────────────────────

app.include_router(v1_router)


# ─── Health check ─────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
async def health(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "healthy", "env": settings.app_env, "version": "1.0.0"}
    except Exception as e:
        _logger.error("Health check DB failure: %s", e)
        error_trace = "".join(traceback.format_exception(type(e), e, e.__traceback__))
        bg_tasks = BackgroundTasks()
        bg_tasks.add_task(alert_admin_error, f"Health Check Database Failure:\n\n{error_trace}")
        
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "success": False, 
                "message": "Our system is currently facing an issue. We have notified the authority and will get back to you shortly."
            },
            background=bg_tasks
        )


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
