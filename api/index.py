"""
FastAPI entry point.

Local dev:  uvicorn api.index:app --reload
Vercel:     The `app` object is auto-detected as an ASGI app.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import init_db
from .middleware import ActivityLoggingMiddleware
from .routes import orders, upload, logs

logging.basicConfig(level=logging.INFO)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description=(
        "REST API for managing medical orders. "
        "Supports CRUD operations, PDF patient data extraction, and activity logging."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ActivityLoggingMiddleware)

app.include_router(orders.router)
app.include_router(upload.router)
app.include_router(logs.router)


@app.get("/v1/health", tags=["Health"])
async def health():
    return {"status": "healthy", "version": settings.VERSION, "service": settings.APP_NAME}


# Vercel also supports a top-level `handler` name for some runtimes
handler = app
