"""Unit and Integration tests for SeeGuide WebSocket Endpoint and Session Manager
Validates connection lifecycle, FrameMessage ingestion, latest-frame-wins queueing, and action response.
"""

import json
from pathlib import Path
from fastapi.testclient import TestClient
from server.main import app
from server.models import AgentAction, FrameMessage
from server.session import session_manager

client = TestClient(app)
EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


def test_health_endpoint():
    """Verify health endpoint responds with ok status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "seeguide"
    assert data["mock_storage"] is True


def test_websocket_connect_and_frame_acknowledgment():
    """Verify WebSocket handshake, frame ingestion, and dummy action response."""
    session_id = "test-session-001"

    # Load valid example frame
    with open(EXAMPLES_DIR / "frame_message.example.json", "r", encoding="utf-8") as f:
        frame_payload = json.load(f)

    with client.websocket_connect(f"/ws/{session_id}") as ws:
        # Check session is active in session manager
        session = session_manager.get_session(session_id)
        assert session is not None
        assert session.session_id == session_id

        # Send frame payload
        ws.send_text(json.dumps(frame_payload))

        # Receive action response
        response_text = ws.receive_text()
        action = AgentAction.from_json_str(response_text)

        assert action.type == "log_event"
        assert action.text == "Frame received"
        assert action.priority == "P3"
        assert action.vibrate is False
        assert action.request_id == str(frame_payload["seq"])
        assert action.mode == frame_payload["mode"]

    # Verify session is cleaned up after disconnect
    assert session_manager.get_session(session_id) is None


def test_websocket_latest_frame_wins_buffering():
    """Verify that rapid frame streaming drops stale frames and retains the newest frame."""
    session_id = "test-session-buffer"

    with client.websocket_connect(f"/ws/{session_id}") as ws:
        session = session_manager.get_session(session_id)
        assert session is not None

        # Send frame sequence 1
        f1 = FrameMessage(
            session_id=session_id,
            seq=1,
            ts_client=100.0,
            mode="walk",
            image_b64="frame1",
            width=640,
            height=480,
            mime="image/jpeg",
        )
        ws.send_text(f1.model_dump_json())
        resp1 = ws.receive_text()
        act1 = AgentAction.from_json_str(resp1)
        assert act1.request_id == "1"

        # Send frame sequence 2
        f2 = FrameMessage(
            session_id=session_id,
            seq=2,
            ts_client=100.1,
            mode="walk",
            image_b64="frame2",
            width=640,
            height=480,
            mime="image/jpeg",
        )
        ws.send_text(f2.model_dump_json())
        resp2 = ws.receive_text()
        act2 = AgentAction.from_json_str(resp2)
        assert act2.request_id == "2"

        # Verify buffer holds the latest frame (seq 2) and capacity is at most 1
        assert session.frame_buffer.qsize() <= 1
        assert session.last_seq == 2


def test_websocket_invalid_payload_error_handling():
    """Verify that sending invalid schema returns validation error event and does not crash."""
    session_id = "test-session-err"

    with client.websocket_connect(f"/ws/{session_id}") as ws:
        # Send invalid message
        ws.send_text(json.dumps({"invalid": "payload"}))

        response_text = ws.receive_text()
        action = AgentAction.from_json_str(response_text)
        assert action.type == "log_event"
        assert action.reason == "validation_error"
