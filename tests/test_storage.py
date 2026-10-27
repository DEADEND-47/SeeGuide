"""Unit tests for SeeGuide Configuration and Storage Abstractions
Tests settings loading and LocalMock storage implementations for traces and objects.
"""

from pathlib import Path
import pytest
from server.config import get_settings
from server.storage import (
    LocalMockObjectStorage,
    LocalMockTraceRepository,
    get_object_storage,
    get_trace_repo,
)


def test_settings_defaults():
    """Verify default configuration settings."""
    settings = get_settings()
    assert settings.ENVIRONMENT in ["local", "test", "production"]
    assert settings.USE_MOCK_STORAGE is True
    assert settings.AWS_REGION == "us-east-1"
    assert settings.DYNAMODB_TRACE_TABLE == "seeguide-traces"
    assert settings.S3_BUCKET_NAME == "seeguide-assets"


@pytest.mark.asyncio
async def test_local_mock_trace_repository(tmp_path: Path):
    """Verify LocalMockTraceRepository saves JSON trace to local filesystem."""
    repo = LocalMockTraceRepository(base_dir=str(tmp_path / "traces"))
    trace_sample = {
        "session_id": "test-trace-sess",
        "action": "speak",
        "priority": "P0",
    }
    await repo.save_trace("test-trace-sess", trace_sample)

    created_files = list((tmp_path / "traces").glob("test-trace-sess_*.json"))
    assert len(created_files) == 1
    content = created_files[0].read_text(encoding="utf-8")
    assert "test-trace-sess" in content
    assert "P0" in content


@pytest.mark.asyncio
async def test_local_mock_object_storage(tmp_path: Path):
    """Verify LocalMockObjectStorage saves binary data to local filesystem."""
    storage = LocalMockObjectStorage(base_dir=str(tmp_path / "objects"))
    test_bytes = b"\x00\x01\x02\x03\x04test_frame_data"
    await storage.put_object("frames/clip_01.jpg", test_bytes)

    target_file = tmp_path / "objects" / "frames" / "clip_01.jpg"
    assert target_file.exists()
    assert target_file.read_bytes() == test_bytes


def test_storage_factories():
    """Verify factory functions return mock adapters when USE_MOCK_STORAGE is True."""
    trace_repo = get_trace_repo()
    assert isinstance(trace_repo, LocalMockTraceRepository)

    object_storage = get_object_storage()
    assert isinstance(object_storage, LocalMockObjectStorage)


@pytest.mark.asyncio
async def test_trace_query_and_delete_session(tmp_path: Path):
    """Verify TraceRepository get_session_traces and delete_session methods (FR-13 & NFR-6)."""
    repo = LocalMockTraceRepository(base_dir=str(tmp_path / "traces"))
    session_id = "test-query-sess"

    # Save multiple traces
    await repo.save_trace(session_id, {"session_id": session_id, "step": 1, "action": {"type": "speak", "text": "hello"}})
    await repo.save_trace(session_id, {"session_id": session_id, "step": 2, "action": {"type": "stay_silent"}})

    traces = await repo.get_session_traces(session_id)
    assert len(traces) == 2
    assert traces[0]["step"] == 1
    assert traces[1]["step"] == 2

    # Delete session
    await repo.delete_session(session_id)
    remaining_traces = await repo.get_session_traces(session_id)
    assert len(remaining_traces) == 0
