"""SeeGuide Deterministic Agent Policy Engine
Executes rule-based arbitration mapping perception observations to prioritized actions:
Rule 1: P0 Hazard (looming collision in center corridor)
Rule 2: P1 Path Blocked (corridor obstruction guidance)
Rule 3: Quality Gate (low blur or extreme lighting reframing)
Rule 4: Read Mode Active Perception (reframing, confirmation, or reading)
Rule 5: P3 Ambient Scene Description (unannounced obstacles)
Rule 6: Nominal Silence (preserves acoustic environmental hearing)
"""

from typing import List, Optional
from agent.state import BeliefState
from agent.tools import ask_confirmation, request_reframe, speak, stay_silent
from server.models import AgentAction, VisionObservation


def decide(observation: VisionObservation, state: BeliefState) -> AgentAction:
    """Evaluates perception observation against deterministic priority rules.

    Args:
        observation: Validated VisionObservation from OpenCV 5 pipeline.
        state: Current BeliefState tracking cooldowns and active perception.

    Returns:
        Deterministic AgentAction to dispatch to client device.
    """
    t = observation.t

    # ====================================================================
    # Rule 1: P0 Hazard (Looming Obstacle in Center Corridor)
    # ====================================================================
    for obj in observation.objects:
        if obj.zone == "center" and obj.growth >= 1.25:
            hazard_key = f"hazard_{obj.cls}_center"
            if not state.is_hazard_in_cooldown(hazard_key, t) and not state.is_hazard_in_cooldown("approaching_object_in_corridor", t):
                return speak(
                    text="Stop. Object ahead, close.",
                    priority="P0",
                    vibrate=True,
                    reason="approaching_object_in_corridor",
                )

    # Extreme flow divergence indicating rapid approach into an obstacle
    if observation.motion.corridor_divergence > 1.2:
        if not state.is_hazard_in_cooldown("hazard_high_divergence", t):
            return speak(
                text="Stop. Object ahead, close.",
                priority="P0",
                vibrate=True,
                reason="high_flow_divergence_hazard",
            )

    # ====================================================================
    # Rule 2: P1 Path Blocked Guidance
    # ====================================================================
    if observation.corridor.blocked_score > 0.7 and len(observation.objects) >= 2:
        # Determine clearer side
        left_count = sum(1 for o in observation.objects if o.zone == "left")
        right_count = sum(1 for o in observation.objects if o.zone == "right")
        clear_side = "right" if left_count >= right_count else "left"

        blocked_key = f"path_blocked_{clear_side}"
        if not state.is_hazard_in_cooldown(blocked_key, t):
            return speak(
                text=f"Path blocked. Clear on your {clear_side}.",
                priority="P1",
                vibrate=False,
                reason="corridor_blocked_guidance",
            )

    # ====================================================================
    # Rule 3: Quality Gate (Blur / Illumination Check)
    # ====================================================================
    if observation.quality.blur < 50.0 or observation.quality.brightness < 30.0:
        return request_reframe(
            direction="hold steady",
            reason="poor_quality",
            text="Hold steady. Image is blurry or low light.",
        )

    # ====================================================================
    # Rule 4: Read Mode (Active Perception & Human-in-the-Loop)
    # ====================================================================
    if state.mode == "read" and observation.text and len(observation.text.strip()) > 0:
        raw_text = observation.text.strip()
        
        # Check for clipped flag or low confidence attribute if attached to observation
        is_clipped = getattr(observation, "text_clipped", False) or "[CLIPPED]" in raw_text or raw_text.endswith("...")
        confidence = getattr(observation, "text_confidence", 0.85)

        if is_clipped or confidence < 0.6:
            return request_reframe(
                direction="move closer",
                reason="low_confidence",
                text="Please move closer to the text.",
            )

        # High confidence text reading: check length for human approval
        clean_text = raw_text.replace("[CLIPPED]", "").strip()
        word_count = len(clean_text.split())
        if (word_count > 6 or len(clean_text) > 30) and not getattr(state, "approved_read", False):
            return ask_confirmation(
                prompt="Read the text aloud?",
                context="read_mode",
            )
        else:
            return speak(
                text=f"Text reads: {clean_text}",
                priority="P2",
                vibrate=False,
                reason="read_text",
            )

    # ====================================================================
    # Rule 5: P3 Ambient Scene Description (Unannounced Objects)
    # ====================================================================
    unannounced_objects = [
        obj for obj in observation.objects
        if not state.is_object_announced(f"{obj.cls}_{obj.zone}", t)
    ]

    if unannounced_objects and (t - state.last_description_time >= 5.0 or state.last_description_time == 0.0):
        classes = sorted(list(set(o.cls for o in unannounced_objects)))
        return speak(
            text=f"Notice: {', '.join(classes)} in corridor.",
            priority="P3",
            vibrate=False,
            reason="ambient_scene_update",
        )

    # ====================================================================
    # Rule 6: Nominal Silence (Preserves Acoustic Awareness)
    # ====================================================================
    return stay_silent(reason="scene_unchanged")
