"""Unit tests for SeeGuide Pydantic v2 Contract Models
Tests schema conformance against Stage 1 example payloads and checks validation constraints.
"""

import json
from pathlib import Path
import pytest
from pydantic import ValidationError
from server.models import AgentAction, FrameMessage, VisionObservation

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


def test_frame_message_from_example():
    """Verify FrameMessage correctly parses examples/frame_message.example.json."""
    example_path = EXAMPLES_DIR / "frame_message.example.json"
    with open(example_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    frame = FrameMessage.model_validate(data)
    assert frame.type == "frame"
    assert frame.session_id == "sess_8f3a91c2-d38a-40a5-b043-98fe04b50c18"
    assert frame.seq == 104
    assert frame.mode == "walk"
    assert frame.width == 640
    assert frame.height == 480
    assert frame.mime == "image/jpeg"

    # Test round-trip JSON serialization
    json_str = frame.model_dump_json()
    reparsed = FrameMessage.from_json_str(json_str)
    assert reparsed == frame


def test_vision_observation_from_example():
    """Verify VisionObservation correctly parses examples/observation.example.json."""
    example_path = EXAMPLES_DIR / "observation.example.json"
    with open(example_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    obs = VisionObservation.model_validate(data)
    assert obs.t == 1729180000.12
    assert obs.quality.blur == 38.2
    assert obs.quality.brightness == 71
    assert obs.quality.stable is False
    assert obs.motion.corridor_divergence == 0.62
    assert obs.motion.ego_motion == 0.4
    assert obs.corridor.edge_density == 0.31
    assert obs.corridor.blocked_score == 0.7
    assert len(obs.objects) == 1
    assert obs.objects[0].cls == "person"
    assert obs.objects[0].conf == 0.88
    assert obs.objects[0].bbox == [220, 140, 380, 470]
    assert obs.objects[0].growth == 1.35
    assert obs.objects[0].zone == "center"
    assert obs.text is None
    assert obs.timing_ms.fast == 21
    assert obs.timing_ms.detect == 74
    assert obs.timing_ms.ocr is None


def test_agent_action_from_example():
    """Verify AgentAction correctly parses examples/action.example.json."""
    example_path = EXAMPLES_DIR / "action.example.json"
    with open(example_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    action = AgentAction.model_validate(data)
    assert action.type == "speak"
    assert action.text == "Stop. Person ahead, close."
    assert action.priority == "P0"
    assert action.vibrate is True
    assert action.reason == "approaching_object_in_corridor"


def test_frame_message_validation_errors():
    """Verify validation fails on invalid sequence number or forbidden extra fields."""
    with pytest.raises(ValidationError):
        FrameMessage(
            session_id="test-1",
            seq=-5,  # Invalid: ge=0 required
            ts_client=100.0,
            mode="walk",
            image_b64="data",
            width=640,
            height=480,
        )

    # Test forbidden extra field
    with pytest.raises(ValidationError):
        FrameMessage.model_validate({
            "type": "frame",
            "session_id": "test-1",
            "seq": 1,
            "ts_client": 100.0,
            "mode": "walk",
            "image_b64": "data",
            "width": 640,
            "height": 480,
            "mime": "image/jpeg",
            "unexpected_field": "disallowed",
        })


def test_agent_action_invalid_priority():
    """Verify validation fails when priority is not one of P0-P3."""
    with pytest.raises(ValidationError):
        AgentAction(
            type="speak",
            text="Warning",
            priority="P99",  # Invalid
            vibrate=True,
        )
