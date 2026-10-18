"""SeeGuide Agent Tool Registry
Factory functions emitting validated AgentAction models for the policy engine:
- speak: Auditory speech synthesis with priority interrupt
- request_reframe: Active perception camera adjustment
- ask_confirmation: User approval before reading verbose content
- stay_silent: First-class deliberate silence to preserve acoustic awareness
- run_detector / read_text: Internal telemetry directives
"""

from typing import Literal, Optional
from server.models import AgentAction

VALID_DIRECTIONS = {"up", "down", "left", "right", "center", "none"}


def speak(
    text: str,
    priority: Literal["P0", "P1", "P2", "P3"] = "P2",
    vibrate: bool = False,
    reason: Optional[str] = None,
) -> AgentAction:
    """Emits an auditory speech action."""
    return AgentAction(
        type="speak",
        text=text,
        priority=priority,
        vibrate=vibrate,
        reason=reason,
    )


def request_reframe(
    direction: str = "none",
    reason: str = "poor_visibility",
    text: Optional[str] = None,
) -> AgentAction:
    """Emits an active perception camera reframing directive."""
    # Map directional string to valid schema enum, preserving instruction in speech text
    valid_dir = direction if direction in VALID_DIRECTIONS else "none"
    spoken_text = text if text is not None else f"Please {direction}."

    return AgentAction(
        type="request_reframe",
        text=spoken_text,
        priority="P1",
        vibrate=False,
        direction=valid_dir,
        reason=reason,
    )


def ask_confirmation(
    prompt: str,
    context: str = "read_mode",
    confirm_id: Optional[str] = None,
) -> AgentAction:
    """Emits a human-in-the-loop confirmation prompt before executing high-bandwidth speech."""
    cid = confirm_id or f"confirm_{context}"
    return AgentAction(
        type="ask_confirmation",
        text=prompt,
        priority="P2",
        vibrate=False,
        confirm_id=cid,
        reason="human_confirmation_required",
    )


def stay_silent(reason: str = "scene_unchanged") -> AgentAction:
    """Emits deliberate silence as a first-class action to prevent auditory fatigue."""
    return AgentAction(
        type="stay_silent",
        text="",
        priority="P3",
        vibrate=False,
        reason=reason,
    )


def run_detector(reason: str = "periodic_scan") -> AgentAction:
    """Internal tool action triggering object detection tier on the next frame."""
    return AgentAction(
        type="log_event",
        text="Invoke detector tier",
        priority="P3",
        vibrate=False,
        reason=reason,
    )


def read_text(reason: str = "read_mode_ocr") -> AgentAction:
    """Internal tool action triggering scene text OCR tier on the next frame."""
    return AgentAction(
        type="log_event",
        text="Invoke OCR tier",
        priority="P3",
        vibrate=False,
        reason=reason,
    )
