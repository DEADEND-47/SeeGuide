"""FastAPI application entry point: API routing, lifespan management, health endpoints, and static asset serving."""
from fastapi import FastAPI

app = FastAPI(
    title="SeeGuide Assistant API",
    description="Privacy-first phone-camera assistant for blind and low-vision users (OpenCV AI Competition 2026)",
    version="0.1.0",
)


@app.get("/health")
async def health_check():
    """Health check endpoint confirming service status."""
    return {"status": "ok", "service": "seeguide"}
