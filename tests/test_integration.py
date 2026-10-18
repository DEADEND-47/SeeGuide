"""End-to-End Integration Tests for SeeGuide
Tests the full live perception-decision-action loop over WebSockets:
- WebSocket connection and session lifecycle
- Client CommandMessage mode switching ("walk", "read", "describe")
- Live FrameMessage processing through OpenCV 5 vision pipeline and deterministic agent policy
- Active perception Human-in-the-Loop confirmation dialogue flow (ask_confirmation -> yes -> speak text)
- Trace repository persistence and audit logging
"""

import base64
import json
import time
from pathlib import Path
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from server.main import app
from server.models import AgentAction, CommandMessage, FrameMessage, UserResponse
from server.session import session_manager
from server.storage import get_trace_repo

client = TestClient(app)


def create_test_jpeg_b64(width: int = 640, height: int = 480, draw_text: str = None) -> str:
    """Generates a valid synthetic BGR frame encoded as base64 JPEG."""
    # Create gradient background
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:, :] = (120, 120, 120)  # Neutral grey for good illumination
    # Add high-contrast geometric shapes to pass blur/quality check
    cv2.rectangle(img, (100, 100), (300, 300), (255, 255, 255), -1)
    cv2.circle(img, (450, 240), 80, (50, 50, 50), -1)

    if draw_text:
        cv2.putText(
            img,
            draw_text,
            (50, 200),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (0, 0, 0),
            2,
            cv2.LINE_AA,
        )

    _, buffer = cv2.imencode(".jpg", img)
    return base64.b64encode(buffer).decode("utf-8")


def test_e2e_walk_mode_perception_action_loop():
    """Verifies complete perception-decision cycle in walk mode with trace persistence."""
    session_id = "sess_e2e_walk_001"
    b64_frame = create_test_jpeg_b64()

    with client.websocket_connect(f"/ws/{session_id}") as ws:
        session = session_manager.get_session(session_id)
        assert session is not None
        assert session.state.mode == "walk"

        # 1. Send Frame in Walk Mode
        frame_msg = FrameMessage(
            session_id=session_id,
            seq=1,
            ts_client=time.time(),
            mode="walk",
            image_b64=b64_frame,
            width=640,
            height=480,
            mime="image/jpeg",
        )
        ws.send_text(frame_msg.model_dump_json())

        # 2. Receive AgentAction emitted by deterministic policy
        resp = ws.receive_text()
        action = AgentAction.from_json_str(resp)

        assert action.type in ("stay_silent", "speak", "request_reframe", "ask_confirmation")
        assert action.request_id == "1"
        assert action.mode == "walk"
        assert session.state.cycle_count >= 1

    # Verify session cleanup
    assert session_manager.get_session(session_id) is None


def test_e2e_command_mode_switch():
    """Verifies that sending CommandMessage changes session mode and acknowledges via WebSocket."""
    session_id = "sess_e2e_cmd_002"

    with client.websocket_connect(f"/ws/{session_id}") as ws:
        session = session_manager.get_session(session_id)
        assert session.state.mode == "walk"

        # Switch to read mode
        cmd = CommandMessage(command="read")
        ws.send_text(cmd.model_dump_json())

        resp = ws.receive_text()
        ack = AgentAction.from_json_str(resp)
        assert ack.type == "log_event"
        assert "Command accepted: read" in ack.text
        assert session.state.mode == "read"

        # Switch to describe mode
        cmd_desc = CommandMessage(command="describe")
        ws.send_text(cmd_desc.model_dump_json())

        resp2 = ws.receive_text()
        ack2 = AgentAction.from_json_str(resp2)
        assert ack2.type == "log_event"
        assert "Command accepted: describe" in ack2.text
        assert session.state.mode == "describe"
        assert session.state.force_detector is True


def test_e2e_active_perception_human_confirmation_flow():
    """Verifies Human-in-the-Loop active perception flow:

    1. Client switches to Read mode
    2. Server detects lengthy text and issues ask_confirmation
    3. Client responds with UserResponse(answer="yes")
    4. Server accepts confirmation and speaks text on subsequent cycle
    """
    session_id = "sess_e2e_confirm_003"
    b64_frame = create_test_jpeg_b64()

    with client.websocket_connect(f"/ws/{session_id}") as ws:
        session = session_manager.get_session(session_id)

        # 1. Switch to read mode
        ws.send_text(CommandMessage(command="read").model_dump_json())
        ws.receive_text()  # command ack
        assert session.state.mode == "read"

        # 2. Mock OCR detection for long text requiring confirmation
        session.pipeline.ocr.read = lambda frame: {
            "text": "Emergency exit staircase B. In case of fire do not use elevators.",
            "confidence": 0.95,
            "clipped": False,
        }

        # Send frame
        frame_msg = FrameMessage(
            session_id=session_id,
            seq=10,
            ts_client=time.time(),
            mode="read",
            image_b64=b64_frame,
            width=640,
            height=480,
            mime="image/jpeg",
        )
        ws.send_text(frame_msg.model_dump_json())

        # Receive ask_confirmation action
        resp = ws.receive_text()
        action = AgentAction.from_json_str(resp)
        assert action.type == "ask_confirmation"
        assert action.confirm_id == "confirm_read_mode"
        assert "Read the text aloud?" in action.text
        assert session.state.pending_confirmation is not None

        # 3. Client responds with UserResponse "yes"
        user_resp = UserResponse(confirm_id="confirm_read_mode", answer="yes")
        ws.send_text(user_resp.model_dump_json())

        ack_resp = ws.receive_text()
        ack_action = AgentAction.from_json_str(ack_resp)
        assert ack_action.type == "log_event"
        assert "Response accepted: yes" in ack_action.text
        assert session.state.approved_read is True

        # 4. Subsequent frame now speaks the approved text
        frame_msg_2 = FrameMessage(
            session_id=session_id,
            seq=11,
            ts_client=time.time(),
            mode="read",
            image_b64=b64_frame,
            width=640,
            height=480,
            mime="image/jpeg",
        )
        ws.send_text(frame_msg_2.model_dump_json())

        resp2 = ws.receive_text()
        action2 = AgentAction.from_json_str(resp2)
        assert action2.type == "speak"
        assert action2.priority == "P2"
        assert "Emergency exit staircase B" in action2.text
        # Verification that approved_read resets after speaking
        assert session.state.approved_read is False


def test_e2e_trace_repository_persistence():
    """Verifies that perception-decision cycles are properly saved to the TraceRepository."""
    session_id = "sess_e2e_trace_004"
    b64_frame = create_test_jpeg_b64()

    with client.websocket_connect(f"/ws/{session_id}") as ws:
        frame_msg = FrameMessage(
            session_id=session_id,
            seq=42,
            ts_client=time.time(),
            mode="walk",
            image_b64=b64_frame,
            width=640,
            height=480,
            mime="image/jpeg",
        )
        ws.send_text(frame_msg.model_dump_json())
        ws.receive_text()

    # Check local mock traces directory
    traces_dir = Path("data/traces")
    matching_traces = list(traces_dir.glob(f"{session_id}_*.json"))
    assert len(matching_traces) >= 1, f"Expected trace file for {session_id} in {traces_dir}"

    trace_file = matching_traces[0]
    with open(trace_file, "r", encoding="utf-8") as f:
        trace_data = json.load(f)

    assert trace_data["session_id"] == session_id
    assert "observation" in trace_data
    assert "action" in trace_data
    assert "latency_ms" in trace_data
    assert trace_data["action"]["request_id"] == "42"
