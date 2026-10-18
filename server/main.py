"""FastAPI application entry point: API routing, lifespan management, health endpoints, and WebSocket telemetry."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from server.config import get_settings
from server.websocket_handler import handle_websocket

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("seeguide.server")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager initializing storage directories and system resources."""
    logger.info("Initializing SeeGuide backend in environment: %s", settings.ENVIRONMENT)
    # Ensure local storage directories exist
    Path("data/traces").mkdir(parents=True, exist_ok=True)
    Path("data/objects").mkdir(parents=True, exist_ok=True)
    logger.info("Local storage directories initialized at data/traces and data/objects.")
    yield
    logger.info("SeeGuide backend shutting down.")


app = FastAPI(
    title="SeeGuide Assistant API",
    description="Privacy-first phone-camera assistant for blind and low-vision users (OpenCV AI Competition 2026)",
    version="0.6.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    """Health check endpoint confirming service status and environment mode."""
    return {
        "status": "ok",
        "service": "seeguide",
        "environment": settings.ENVIRONMENT,
        "mock_storage": settings.USE_MOCK_STORAGE,
    }


@app.websocket("/ws/{session_id}")
async def websocket_telemetry_endpoint(websocket: WebSocket, session_id: str):
    """Bidirectional WebSocket endpoint for video telemetry and agent action directives."""
    await handle_websocket(websocket=websocket, session_id=session_id)


# Mount frontend PWA static files (after API routes so endpoints take precedence)
app.mount("/", StaticFiles(directory="web", html=True), name="web")
