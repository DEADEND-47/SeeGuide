"""SeeGuide Agent Belief State
Maintains persistent agent belief state across perception-action cycles:
- Operating modes (walk, read, describe)
- Active hazard and speech cooldowns
- Announced object tracking to prevent repetitive chatter
- Pending active perception states (reframing directives and confirmation dialogues)
"""

from typing import Any, Dict, List, Literal, Optional
from server.models import AgentAction, VisionObservation


class BeliefState:
    """Tracks temporal state, cooldowns, and active perception across cycles."""

    def __init__(self, mode: Literal["walk", "read", "describe"] = "walk"):
        self.mode: Literal["walk", "read", "describe"] = mode
        self.last_description_time: float = 0.0
        self.last_description_hash: str = ""
        self.announced_objects: Dict[str, float] = {}
        self.hazard_cooldowns: Dict[str, float] = {}
        self.active_reframe: Optional[Dict[str, Any]] = None
        self.pending_confirmation: Optional[Dict[str, Any]] = None
        self.cycle_count: int = 0

    def is_hazard_in_cooldown(self, hazard_key: str, current_time: float) -> bool:
        """Checks if a hazard key is currently suppressed by an active cooldown."""
        expiry = self.hazard_cooldowns.get(hazard_key, 0.0)
        return current_time < expiry

    def set_hazard_cooldown(self, hazard_key: str, expiry_time: float) -> None:
        """Sets a cooldown expiry timestamp for a specific hazard key."""
        self.hazard_cooldowns[hazard_key] = expiry_time

    def is_object_announced(self, obj_key: str, current_time: float, suppression_window: float = 8.0) -> bool:
        """Checks if an object was announced within the suppression window."""
        last_time = self.announced_objects.get(obj_key, 0.0)
        return (current_time - last_time) < suppression_window

    def update(self, observation: VisionObservation, action: AgentAction) -> None:
        """Updates internal belief state based on the current observation and chosen action."""
        self.cycle_count += 1
        t = observation.t

        # 1. Prune expired hazard cooldowns
        self.hazard_cooldowns = {
            k: exp for k, exp in self.hazard_cooldowns.items() if exp > t
        }

        # 2. Prune old announced objects (older than 30s)
        self.announced_objects = {
            k: ts for k, ts in self.announced_objects.items() if (t - ts) < 30.0
        }

        # 3. Handle action-specific state transitions
        if action.type == "speak":
            self.last_description_time = t
            for obj in observation.objects:
                obj_key = f"{obj.cls}_{obj.zone}"
                self.announced_objects[obj_key] = t

            if action.priority == "P0":
                # Set hazard cooldown for 3 seconds to avoid auditory spamming
                hazard_key = action.reason or "looming_hazard"
                self.set_hazard_cooldown(hazard_key, t + 3.0)
                for obj in observation.objects:
                    if obj.zone == "center" and obj.growth >= 1.25:
                        self.set_hazard_cooldown(f"hazard_{obj.cls}_center", t + 3.0)

        elif action.type == "request_reframe":
            self.active_reframe = {
                "direction": action.direction or "none",
                "reason": action.reason or "poor_visibility",
                "time": t,
            }

        elif action.type == "ask_confirmation":
            self.pending_confirmation = {
                "prompt": action.text,
                "confirm_id": action.confirm_id or "confirm_read",
                "time": t,
            }

        # Clear reframe if quality is now stable and action was not a reframe
        if observation.quality.stable and action.type != "request_reframe":
            self.active_reframe = None

        # Update scene hash
        obj_signatures = sorted([f"{o.cls}_{o.zone}" for o in observation.objects])
        self.last_description_hash = ":".join(obj_signatures)
