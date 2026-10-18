"""Unit tests for SeeGuide Deterministic Agent Policy
Verifies all 6 priority decision rules using mock VisionObservation inputs:
1. P0 Hazard (looming obstacle in center corridor)
2. P1 Path Blocked (corridor blockage guidance)
3. Quality Gate (blur / dark reframing)
4. Read Mode Active Perception (reframing, confirmation, reading)
5. P3 Ambient Scene Description (unannounced objects)
6. Nominal Silence (scene unchanged)
"""

import pytest
from agent.policy import decide
from agent.state import BeliefState
from agent.tools import ask_confirmation, read_text, request_reframe, run_detector, speak, stay_silent
from server.models import (
    CorridorMetrics,
    DetectedObject,
    MotionMetrics,
    QualityMetrics,
    TimingMetrics,
    VisionObservation,
)


def make_mock_observation(
    t: float = 100.0,
    blur: float = 85.0,
    brightness: float = 120.0,
    stable: bool = True,
    corridor_divergence: float = 0.1,
    ego_motion: float = 0.2,
    edge_density: float = 0.15,
    blocked_score: float = 0.1,
    objects: list = None,
    text: str = None,
    text_clipped: bool = False,
    text_confidence: float = 0.9,
    status: str = "ok",
) -> VisionObservation:
    """Helper to instantiate valid VisionObservation Pydantic models for deterministic policy tests."""
    return VisionObservation(
        t=t,
        quality=QualityMetrics(blur=blur, brightness=brightness, stable=stable),
        motion=MotionMetrics(corridor_divergence=corridor_divergence, ego_motion=ego_motion),
        corridor=CorridorMetrics(edge_density=edge_density, blocked_score=blocked_score),
        objects=objects or [],
        text=text,
        text_confidence=text_confidence if text is not None else None,
        text_clipped=text_clipped,
        timing_ms=TimingMetrics(fast=12.0, detect=45.0, ocr=None),
        status=status,
    )


# ====================================================================
# Rule 1: P0 Hazard Tests
# ====================================================================

def test_p0_hazard_looming():
    """Object in center zone with growth 1.35 triggers P0 warning."""
    state = BeliefState(mode="walk")
    obj = DetectedObject(cls="person", conf=0.9, bbox=[200, 150, 400, 450], growth=1.35, zone="center")
    obs = make_mock_observation(objects=[obj])

    action = decide(obs, state)
    assert action.type == "speak"
    assert action.priority == "P0"
    assert action.vibrate is True
    assert "Stop" in action.text
    assert action.reason == "approaching_object_in_corridor"


def test_p0_hazard_cooldown():
    """Active cooldown suppresses repetitive P0 warning and yields silence if path otherwise clear."""
    state = BeliefState(mode="walk")
    obj = DetectedObject(cls="person", conf=0.9, bbox=[200, 150, 400, 450], growth=1.35, zone="center")
    obs = make_mock_observation(t=100.0, objects=[obj])

    # First cycle triggers P0
    action1 = decide(obs, state)
    assert action1.priority == "P0"
    state.update(obs, action1)

    # Next cycle within cooldown window (101.0s < 103.0s) suppresses P0
    obs2 = make_mock_observation(t=101.0, objects=[obj])
    action2 = decide(obs2, state)
    assert action2.priority != "P0"
    assert action2.type == "stay_silent"


def test_p0_cooldown_expiration_fires_again():
    """After cooldown window expires (t + 3.1s >= 3.0s), P0 warning can fire again."""
    state = BeliefState(mode="walk")
    obj = DetectedObject(cls="person", conf=0.9, bbox=[200, 150, 400, 450], growth=1.35, zone="center")
    obs1 = make_mock_observation(t=100.0, objects=[obj])

    action1 = decide(obs1, state)
    assert action1.priority == "P0"
    state.update(obs1, action1)

    # After cooldown expires (103.5s > 100.0 + 3.0s)
    obs_later = make_mock_observation(t=103.5, objects=[obj])
    action_later = decide(obs_later, state)
    assert action_later.priority == "P0"
    assert action_later.reason == "approaching_object_in_corridor"


def test_p1_path_blocked_cooldown():
    """P1 path blocked guidance respects cooldown and avoids spamming advice."""
    state = BeliefState(mode="walk")
    obj1 = DetectedObject(cls="chair", conf=0.85, bbox=[50, 100, 150, 250], growth=1.0, zone="left")
    obj2 = DetectedObject(cls="box", conf=0.80, bbox=[80, 260, 180, 400], growth=1.0, zone="left")
    obs1 = make_mock_observation(t=200.0, blocked_score=0.85, objects=[obj1, obj2])

    action1 = decide(obs1, state)
    assert action1.priority == "P1"
    state.update(obs1, action1)

    # Next cycle within 4.0s cooldown window suppresses repetitive speech
    obs2 = make_mock_observation(t=201.5, blocked_score=0.85, objects=[obj1, obj2])
    action2 = decide(obs2, state)
    assert action2.type == "stay_silent"


# ====================================================================
# Rule 2: P1 Path Blocked Tests
# ====================================================================

def test_p1_path_blocked():
    """Blocked score > 0.7 with multiple objects triggers P1 directional advice."""
    state = BeliefState(mode="walk")
    # Objects placed on left
    obj1 = DetectedObject(cls="chair", conf=0.85, bbox=[50, 100, 150, 250], growth=1.0, zone="left")
    obj2 = DetectedObject(cls="box", conf=0.80, bbox=[80, 260, 180, 400], growth=1.0, zone="left")
    obs = make_mock_observation(blocked_score=0.85, objects=[obj1, obj2])

    action = decide(obs, state)
    assert action.type == "speak"
    assert action.priority == "P1"
    assert "Clear on your right" in action.text
    assert action.reason == "corridor_blocked_guidance"


# ====================================================================
# Rule 3: Quality Gate Tests
# ====================================================================

def test_quality_gate_blurry():
    """Blur score below threshold triggers hold steady reframe."""
    state = BeliefState(mode="walk")
    obs = make_mock_observation(blur=20.0, brightness=100.0)

    action = decide(obs, state)
    assert action.type == "request_reframe"
    assert action.priority == "P1"
    assert action.reason == "poor_quality"
    assert "Hold steady" in action.text


def test_quality_gate_dark():
    """Very low illumination triggers reframing directive."""
    state = BeliefState(mode="walk")
    obs = make_mock_observation(blur=80.0, brightness=15.0)

    action = decide(obs, state)
    assert action.type == "request_reframe"
    assert action.priority == "P1"
    assert action.reason == "poor_quality"


# ====================================================================
# Rule 4: Read Mode Tests
# ====================================================================

def test_read_mode_reframe_on_clipped():
    """In read mode, clipped text prompts moving closer/reframing."""
    state = BeliefState(mode="read")
    obs = make_mock_observation(text="[CLIPPED] Conference Room 4...", text_clipped=True)

    action = decide(obs, state)
    assert action.type == "request_reframe"
    assert action.reason == "low_confidence"
    assert "move closer" in action.text.lower()


def test_read_mode_reframe_on_low_confidence():
    """In read mode, low OCR confidence prompts moving closer."""
    state = BeliefState(mode="read")
    obs = make_mock_observation(text="Room 402", text_confidence=0.4)

    action = decide(obs, state)
    assert action.type == "request_reframe"
    assert action.reason == "low_confidence"


def test_read_mode_confirmation_for_long_text():
    """In read mode, lengthy high-confidence text prompts user confirmation."""
    state = BeliefState(mode="read")
    long_text = "Emergency exit route. In case of fire do not use elevators. Use stairwell B."
    obs = make_mock_observation(text=long_text, text_confidence=0.95)

    action = decide(obs, state)
    assert action.type == "ask_confirmation"
    assert action.priority == "P2"
    assert "Read the text aloud?" in action.text


def test_read_mode_reads_short_text_directly():
    """In read mode, concise high-confidence text is spoken directly without asking."""
    state = BeliefState(mode="read")
    obs = make_mock_observation(text="Exit 4", text_confidence=0.95)

    action = decide(obs, state)
    assert action.type == "speak"
    assert action.priority == "P2"
    assert "Exit 4" in action.text


# ====================================================================
# Rule 5: P3 Ambient Scene Description Tests
# ====================================================================

def test_p3_ambient_scene_change():
    """Unannounced objects in clear corridor trigger low-priority P3 scene description."""
    state = BeliefState(mode="walk")
    obj = DetectedObject(cls="bench", conf=0.88, bbox=[450, 200, 600, 400], growth=1.0, zone="right")
    obs = make_mock_observation(t=100.0, objects=[obj])

    action = decide(obs, state)
    assert action.type == "speak"
    assert action.priority == "P3"
    assert "bench" in action.text
    assert action.reason == "ambient_scene_update"


# ====================================================================
# Rule 6: Nominal Silence Tests
# ====================================================================

def test_stay_silent_unchanged():
    """Clear corridor with no new objects or hazards returns deliberate silence."""
    state = BeliefState(mode="walk")
    obs = make_mock_observation(objects=[])

    action = decide(obs, state)
    assert action.type == "stay_silent"
    assert action.priority == "P3"
    assert action.text == ""
    assert action.reason == "scene_unchanged"


# ====================================================================
# Tool Registry Factory Tests
# ====================================================================

def test_tools_factory_functions():
    """Verify tool functions return valid AgentAction models."""
    a1 = speak("Alert", priority="P0", vibrate=True)
    assert a1.type == "speak"
    assert a1.vibrate is True

    a2 = request_reframe("tilt up", reason="obscured")
    assert a2.type == "request_reframe"

    a3 = ask_confirmation("Proceed?")
    assert a3.type == "ask_confirmation"

    a4 = stay_silent()
    assert a4.type == "stay_silent"

    a5 = run_detector()
    assert a5.type == "log_event"

    a6 = read_text()
    assert a6.type == "log_event"
