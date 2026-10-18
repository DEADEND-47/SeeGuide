"""Unit tests for SeeGuide Agent Belief State and Trace Logger
Validates state transitions, cooldown pruning, announced object tracking, and trace logging.
"""

from pathlib import Path
import pytest
from agent.state import BeliefState
from agent.tools import ask_confirmation, request_reframe, speak, stay_silent
from agent.trace import TraceLogger
from server.models import (
    CorridorMetrics,
    DetectedObject,
    MotionMetrics,
    QualityMetrics,
    TimingMetrics,
    VisionObservation,
)
from server.storage import LocalMockTraceRepository


def make_sample_obs(t: float = 100.0, stable: bool = True) -> VisionObservation:
    """Helper to generate minimal valid VisionObservation."""
    return VisionObservation(
        t=t,
        quality=QualityMetrics(blur=60.0, brightness=110.0, stable=stable),
        motion=MotionMetrics(corridor_divergence=0.0, ego_motion=0.1),
        corridor=CorridorMetrics(edge_density=0.1, blocked_score=0.1),
        objects=[
            DetectedObject(cls="person", conf=0.9, bbox=[200, 100, 300, 300], growth=1.0, zone="center")
        ],
        text=None,
        timing_ms=TimingMetrics(fast=10.0, detect=None, ocr=None),
    )


def test_belief_state_defaults():
    """Verify initial default properties of BeliefState."""
    state = BeliefState()
    assert state.mode == "walk"
    assert state.last_description_time == 0.0
    assert state.active_reframe is None
    assert state.pending_confirmation is None
    assert len(state.hazard_cooldowns) == 0
    assert len(state.announced_objects) == 0


def test_belief_state_cooldown_tracking():
    """Verify setting and checking hazard cooldowns."""
    state = BeliefState()
    assert not state.is_hazard_in_cooldown("hazard_person", 100.0)

    state.set_hazard_cooldown("hazard_person", 103.0)
    assert state.is_hazard_in_cooldown("hazard_person", 101.5)
    assert not state.is_hazard_in_cooldown("hazard_person", 103.5)


def test_belief_state_update_on_p0_action():
    """Verify updating state with P0 hazard creates cooldown and increments cycle."""
    state = BeliefState()
    obs = make_sample_obs(t=50.0)
    action = speak("Stop", priority="P0", vibrate=True, reason="hazard_person")

    state.update(obs, action)
    assert state.cycle_count == 1
    assert state.is_hazard_in_cooldown("hazard_person", 51.0)
    assert not state.is_hazard_in_cooldown("hazard_person", 54.0)


def test_belief_state_reframe_and_clearing():
    """Verify reframe state tracking and automatic clearing when quality stabilizes."""
    state = BeliefState()
    obs1 = make_sample_obs(t=10.0, stable=False)
    act_reframe = request_reframe("tilt up", reason="obscured")

    state.update(obs1, act_reframe)
    assert state.active_reframe is not None
    assert state.active_reframe["reason"] == "obscured"

    # Next cycle stabilizes with silent action
    obs2 = make_sample_obs(t=11.0, stable=True)
    act_silent = stay_silent()

    state.update(obs2, act_silent)
    assert state.active_reframe is None


def test_belief_state_confirmation_tracking():
    """Verify pending confirmation tracking."""
    state = BeliefState()
    obs = make_sample_obs(t=20.0)
    act_conf = ask_confirmation("Read sign?", context="room_sign")

    state.update(obs, act_conf)
    assert state.pending_confirmation is not None
    assert state.pending_confirmation["prompt"] == "Read sign?"


@pytest.mark.asyncio
async def test_trace_logger_persists_cycle(tmp_path: Path):
    """Verify TraceLogger writes complete cycle telemetry to storage repository."""
    mock_repo = LocalMockTraceRepository(base_dir=str(tmp_path / "traces"))
    logger = TraceLogger(repo=mock_repo)

    obs = make_sample_obs(t=12345.67)
    act = speak("Stop. Obstacle ahead.", priority="P0", vibrate=True)

    await logger.log_cycle(
        session_id="sess_test_cycle",
        observation=obs,
        action=act,
        reason="approaching_obstacle",
        latency_ms=18.5,
    )

    created_files = list((tmp_path / "traces").glob("sess_test_cycle_*.json"))
    assert len(created_files) == 1
    content = created_files[0].read_text(encoding="utf-8")

    assert "sess_test_cycle" in content
    assert "Stop. Obstacle ahead." in content
    assert "18.5" in content
