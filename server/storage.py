"""SeeGuide Storage Abstractions
Provides abstract interfaces, AWS production adapters (DynamoDB / S3), and local filesystem mock adapters for:
- TraceRepository (DynamoDB in production / JSON files in local mock)
- ObjectStorage (AWS S3 in production / binary files in local mock)
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import json
import logging
import os
from pathlib import Path
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import boto3
from botocore.exceptions import ClientError

from server.config import get_settings

logger = logging.getLogger("seeguide.server.storage")
_executor = ThreadPoolExecutor(max_workers=4)


def _convert_floats_to_decimals(obj: Any) -> Any:
    """Recursively converts float values to Decimal for DynamoDB serialization."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: _convert_floats_to_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_floats_to_decimals(v) for v in obj]
    return obj


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
# AWS Production Storage Implementations
# ====================================================================

class AWSDynamoDBTraceRepository(TraceRepository):
    """AWS DynamoDB production implementation for persisting telemetry traces.
    
    Persists structured telemetry with session_id (PK), timestamp (SK),
    and an automatic 7-day TTL expiration timestamp (expires_at).
    """

    def __init__(self, table_name: Optional[str] = None, region_name: Optional[str] = None):
        settings = get_settings()
        self.table_name = table_name or settings.DYNAMODB_TRACE_TABLE
        self.region_name = region_name or settings.AWS_REGION
        self.dynamodb = boto3.resource("dynamodb", region_name=self.region_name)
        self.table = self.dynamodb.Table(self.table_name)

    async def save_trace(self, session_id: str, trace_data: Dict[str, Any]) -> None:
        """Asynchronously writes a telemetry trace item to DynamoDB."""
        now = time.time()
        timestamp_ms = int(now * 1000)
        # NFR-6: 7-day TTL in epoch seconds
        expires_at = int(now + (7 * 24 * 3600))

        item = {
            "session_id": session_id,
            "timestamp": timestamp_ms,
            "expires_at": expires_at,
            "trace_data": _convert_floats_to_decimals(trace_data),
        }

        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(
                _executor,
                lambda: self.table.put_item(Item=item)
            )
        except Exception as e:
            logger.error("Failed to write trace to DynamoDB table %s: %s", self.table_name, e)


class AWSS3ObjectStorage(ObjectStorage):
    """AWS S3 production object storage with strict key path sanitization."""

    def __init__(self, bucket_name: Optional[str] = None, region_name: Optional[str] = None):
        settings = get_settings()
        self.bucket_name = bucket_name or settings.S3_BUCKET_NAME
        self.region_name = region_name or settings.AWS_REGION
        self.s3_client = boto3.client("s3", region_name=self.region_name)

    async def put_object(self, key: str, data: bytes) -> None:
        """Stores binary object in S3 with strict path sanitization."""
        # Sanitize key to prevent path traversal
        clean_key = key.replace("\\", "/").strip("/")
        if ".." in clean_key.split("/"):
            raise ValueError(f"Directory traversal detected in S3 key: {key}")

        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(
                _executor,
                lambda: self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=clean_key,
                    Body=data,
                )
            )
        except Exception as e:
            logger.error("Failed to upload object %s to S3 bucket %s: %s", clean_key, self.bucket_name, e)


# ====================================================================
# Local Filesystem Mock Implementations
# ====================================================================

class LocalMockTraceRepository(TraceRepository):
    """Local mock implementation persisting trace JSON files under data/traces/."""

    def __init__(self, base_dir: str = "data/traces"):
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def save_trace(self, session_id: str, trace_data: Dict[str, Any]) -> None:
        """Non-blocking asynchronous file write for trace data."""
        timestamp = int(time.time() * 1000)
        file_path = self.base_dir / f"{session_id}_{timestamp}.json"
        payload = json.dumps(trace_data, indent=2)

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            _executor,
            lambda: file_path.write_text(payload, encoding="utf-8")
        )


class LocalMockObjectStorage(ObjectStorage):
    """Local mock implementation persisting binary files under data/objects/ with path containment."""

    def __init__(self, base_dir: str = "data/objects"):
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def put_object(self, key: str, data: bytes) -> None:
        """Writes binary data to local mock ensuring path containment."""
        clean_key = key.replace("\\", "/").strip("/")
        if ".." in clean_key.split("/"):
            raise ValueError(f"Directory traversal detected in key: {key}")

        target_path = (self.base_dir / clean_key).resolve()
        if not str(target_path).startswith(str(self.base_dir)):
            raise ValueError(f"Path traversal detected: {key} escapes {self.base_dir}")

        target_path.parent.mkdir(parents=True, exist_ok=True)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            _executor,
            lambda: target_path.write_bytes(data)
        )


# ====================================================================
# Factory Functions
# ====================================================================

def get_trace_repo() -> TraceRepository:
    """Factory function returning active TraceRepository implementation."""
    settings = get_settings()
    if settings.USE_MOCK_STORAGE:
        return LocalMockTraceRepository()
    return AWSDynamoDBTraceRepository()


def get_object_storage() -> ObjectStorage:
    """Factory function returning active ObjectStorage implementation."""
    settings = get_settings()
    if settings.USE_MOCK_STORAGE:
        return LocalMockObjectStorage()
    return AWSS3ObjectStorage()
