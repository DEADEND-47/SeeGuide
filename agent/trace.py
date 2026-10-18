"""SeeGuide Trace Logger
Records structured cycle telemetry (observation, agent decision, policy rationale, and latency)
using the abstract TraceRepository for auditing, evaluation, and O&M review.
"""

import logging
from typing import Any, Dict
from server.models import AgentAction, VisionObservation
from server.storage import TraceRepository

logger = logging.getLogger("seeguide.agent.trace")


class TraceLogger:
    """Records perception-decision cycles to the trace repository."""

    def __init__(self, repo: TraceRepository):
        self.repo: TraceRepository = repo

    async def log_cycle(
        self,
        session_id: str,
        observation: VisionObservation,
        action: AgentAction,
        reason: str,
        latency_ms: float,
    ) -> None:
        """Persists a complete perception-decision cycle trace record."""
        trace_data: Dict[str, Any] = {
            "timestamp": observation.t,
            "session_id": session_id,
            "observation": observation.model_dump(),
            "action": action.model_dump(),
            "reason": reason,
            "latency_ms": round(latency_ms, 2),
        }

        try:
            await self.repo.save_trace(session_id=session_id, trace_data=trace_data)
        except Exception as e:
            logger.error("Failed to log trace cycle for session %s: %s", session_id, e)
