"""SeeGuide Pydantic v2 Models
Strictly implements the data contracts defined in Stage 1:
- FrameMessage (client-to-server video frame telemetry)
- VisionObservation (vision pipeline observation sent to deterministic agent)
- AgentAction (agent directive sent to client device)
"""

import json
from typing import List, Literal, Optional, Tuple, Union
from pydantic import BaseModel, ConfigDict, Field


class StrictBaseModel(BaseModel):
    """Base model enforcing strict schema conformance and prohibiting extra fields."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )


# ====================================================================
# 1. Client-to-Server Frame Message
# ====================================================================

class FrameMessage(StrictBaseModel):
    """Client-to-server frame telemetry message received via WebSocket."""

    type: Literal["frame"] = "frame"
    session_id: str = Field(..., description="Unique session UUID for the client connection")
    seq: int = Field(..., ge=0, description="Monotonically increasing sequence number")
    ts_client: float = Field(..., description="Client epoch timestamp in seconds")
    mode: Literal["walk", "read", "describe"] = Field(..., description="Operating mode")
    image_b64: str = Field(..., description="Base64-encoded JPEG image string")
    width: int = Field(..., ge=1, description="Frame width in pixels")
    height: int = Field(..., ge=1, description="Frame height in pixels")
    mime: Literal["image/jpeg"] = "image/jpeg"

    @classmethod
    def from_json_str(cls, raw: Union[str, bytes]) -> "FrameMessage":
        """Deserialize and validate raw JSON string or bytes into a FrameMessage."""
        return cls.model_validate_json(raw)


# ====================================================================
# 2. Vision-to-Agent Observation
# ====================================================================

class QualityMetrics(StrictBaseModel):
    """Fast-tier visual quality assessment."""

    blur: float = Field(..., description="Laplacian variance blur metric")
    brightness: float = Field(..., description="Mean luma intensity (0-255)")
    stable: bool = Field(..., description="True if camera is stable for high-confidence inference")


class MotionMetrics(StrictBaseModel):
    """Optical flow and ego-motion metrics."""

    corridor_divergence: float = Field(..., description="Flow divergence into corridor")
    ego_motion: float = Field(..., description="Magnitude of estimated camera movement")


class CorridorMetrics(StrictBaseModel):
    """Dynamic walking corridor analysis."""

    edge_density: float = Field(..., description="Edge density in navigation path (0.0 - 1.0)")
    blocked_score: float = Field(..., description="Corridor obstruction probability (0.0 - 1.0)")


class DetectedObject(StrictBaseModel):
    """Detected pedestrian or obstacle candidate."""

    cls: str = Field(..., description="Detected class label (e.g. person, chair)")
    conf: float = Field(..., ge=0.0, le=1.0, description="Detector confidence score")
    bbox: List[float] = Field(..., min_length=4, max_length=4, description="[x1, y1, x2, y2] coordinates")
    growth: float = Field(..., description="Bounding box area expansion ratio relative to prior frame")
    zone: Literal["left", "center", "right"] = Field(..., description="Horizontal corridor zone")


class TimingMetrics(StrictBaseModel):
    """Inference execution latency breakdown in milliseconds."""

    fast: float = Field(..., ge=0.0, description="Fast-tier execution duration in ms")
    detect: Optional[float] = Field(None, description="Detector tier duration in ms or null if skipped")
    ocr: Optional[float] = Field(None, description="OCR tier duration in ms or null if skipped")


class VisionObservation(StrictBaseModel):
    """Complete perception observation produced by OpenCV 5 pipeline for deterministic agent."""

    t: float = Field(..., description="Observation server epoch timestamp in seconds")
    quality: QualityMetrics
    motion: MotionMetrics
    corridor: CorridorMetrics
    objects: List[DetectedObject] = Field(default_factory=list, description="List of detected objects")
    text: Optional[str] = Field(None, description="Extracted OCR text or null")
    text_confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Mean OCR confidence score")
    text_clipped: Optional[bool] = Field(None, description="True if text touches image frame boundary")
    timing_ms: TimingMetrics
    status: Literal["ok", "degraded", "error"] = Field("ok", description="Pipeline execution health status")

    @classmethod
    def from_json_str(cls, raw: Union[str, bytes]) -> "VisionObservation":
        """Deserialize and validate raw JSON into a VisionObservation."""
        return cls.model_validate_json(raw)


# ====================================================================
# 3. Agent-to-Client Action Message
# ====================================================================

class AgentAction(StrictBaseModel):
    """Action directive emitted by deterministic agent policy to the client device."""

    type: Literal["speak", "request_reframe", "ask_confirmation", "stay_silent", "log_event"] = Field(
        ..., description="Action category discriminator"
    )
    text: str = Field(..., description="Utterance text or empty string when silent")
    priority: Literal["P0", "P1", "P2", "P3"] = Field(..., description="Urgency priority level")
    vibrate: bool = Field(..., description="Whether to trigger device vibration")
    direction: Optional[Literal["up", "down", "left", "right", "center", "none"]] = Field(
        None, description="Reframing direction"
    )
    request_id: Optional[str] = Field(None, description="Correlated request/frame ID")
    mode: Optional[Literal["walk", "read", "describe"]] = Field(None, description="Mode context")
    confirm_id: Optional[str] = Field(None, description="Confirmation correlation ID")
    reason: Optional[str] = Field(None, description="Deterministic rule rationale")

    @classmethod
    def from_json_str(cls, raw: Union[str, bytes]) -> "AgentAction":
        """Deserialize and validate raw JSON into an AgentAction."""
        return cls.model_validate_json(raw)


# ====================================================================
# 4. Client-to-Server Control and Response Messages
# ====================================================================

class CommandMessage(StrictBaseModel):
    """Client command to change operating mode or request an action."""

    type: Literal["command"] = "command"
    command: Literal["walk", "read", "describe", "stop"] = Field(
        ..., description="Operating mode change or immediate action request"
    )


class UserResponse(StrictBaseModel):
    """Client response message to active perception confirmation dialogs."""

    type: Literal["response"] = "response"
    confirm_id: str = Field(..., description="Correlation ID matching the confirmation prompt")
    answer: Literal["yes", "no"] = Field(..., description="User binary confirmation answer")


ClientMessage = Union[FrameMessage, CommandMessage, UserResponse]


def parse_client_message(raw: Union[str, bytes]) -> ClientMessage:
    """Parses and validates raw client WebSocket JSON into the appropriate client message model."""
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Client message payload must be a JSON object")

    msg_type = data.get("type", "frame")
    if msg_type == "frame":
        return FrameMessage.model_validate(data)
    elif msg_type == "command":
        return CommandMessage.model_validate(data)
    elif msg_type == "response":
        return UserResponse.model_validate(data)
    else:
        raise ValueError(f"Unknown client message type: {msg_type}")
