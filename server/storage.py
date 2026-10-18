"""SeeGuide Storage Abstractions
Provides abstract interfaces and local filesystem mock adapters for:
- TraceRepository (DynamoDB in production / JSON files in local mock)
- ObjectStorage (AWS S3 in production / binary files in local mock)
"""

import json
import os
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict
from server.config import get_settings


# ====================================================================
# Abstract Storage Interfaces
# ====================================================================

class TraceRepository(ABC):
    """Abstract repository for persisting telemetry traces."""

    @abstractmethod
    async def save_trace(self, session_id: str, trace_data: Dict[str, Any]) -> None:
        """Persists a structured trace telemetry record."""
        pass


class ObjectStorage(ABC):
    """Abstract storage for binary objects (clips, images, artifacts)."""

    @abstractmethod
    async def put_object(self, key: str, data: bytes) -> None:
        """Stores a binary object payload under the specified key."""
        pass


# ====================================================================
# Local Filesystem Mock Implementations
# ====================================================================

class LocalMockTraceRepository(TraceRepository):
    """Local mock implementation persisting trace JSON files under data/traces/."""

    def __init__(self, base_dir: str = "data/traces"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def save_trace(self, session_id: str, trace_data: Dict[str, Any]) -> None:
        """Writes trace_data as JSON to data/traces/{session_id}_{timestamp}.json."""
        timestamp = int(time.time() * 1000)
        file_path = self.base_dir / f"{session_id}_{timestamp}.json"
        
        # Async-safe file write
        payload = json.dumps(trace_data, indent=2)
        file_path.write_text(payload, encoding="utf-8")


class LocalMockObjectStorage(ObjectStorage):
    """Local mock implementation persisting binary files under data/objects/."""

    def __init__(self, base_dir: str = "data/objects"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def put_object(self, key: str, data: bytes) -> None:
        """Writes binary data to data/objects/{key} creating parent directories if needed."""
        target_path = self.base_dir / key
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(data)


# ====================================================================
# Factory Functions
# ====================================================================

def get_trace_repo() -> TraceRepository:
    """Factory function returning active TraceRepository implementation.
    Returns LocalMockTraceRepository when USE_MOCK_STORAGE is True.
    (AWS DynamoDBTraceRepository implementation will be integrated in Stage 9).
    """
    settings = get_settings()
    if settings.USE_MOCK_STORAGE:
        return LocalMockTraceRepository()
    
    # Real AWS DynamoDB implementation for Stage 9
    raise NotImplementedError("DynamoDBTraceRepository will be initialized in Stage 9.")


def get_object_storage() -> ObjectStorage:
    """Factory function returning active ObjectStorage implementation.
    Returns LocalMockObjectStorage when USE_MOCK_STORAGE is True.
    (AWS S3ObjectStorage implementation will be integrated in Stage 9).
    """
    settings = get_settings()
    if settings.USE_MOCK_STORAGE:
        return LocalMockObjectStorage()
    
    # Real AWS S3 implementation for Stage 9
    raise NotImplementedError("S3ObjectStorage will be initialized in Stage 9.")
