"""SeeGuide Session Management
Maintains active client WebSocket sessions and their dedicated single-frame buffers.
"""

import asyncio
from typing import Dict, Optional
from fastapi import WebSocket
from agent.state import BeliefState
from agent.trace import TraceLogger
from server.config import get_settings
from server.models import CommandMessage, FrameMessage, UserResponse
from server.storage import get_trace_repo
from vision.pipeline import VisionPipeline


class Session:
    """Represents an active client connection session with audit telemetry."""

    def __init__(self, session_id: str, websocket: WebSocket):
        self.session_id: str = session_id
        self.websocket: WebSocket = websocket
        # Single-slot queue enforcing latest-frame-wins latency policy
        self.frame_buffer: asyncio.Queue[FrameMessage] = asyncio.Queue(maxsize=1)
        self.last_seq: int = -1
        self.is_active: bool = True
        
        # Configure model paths from centralized settings
        settings = get_settings()
        self.pipeline: VisionPipeline = VisionPipeline(
            detector_model_path=settings.DETECTOR_MODEL_PATH,
            ocr_det_path=settings.OCR_DET_PATH,
            ocr_rec_path=settings.OCR_REC_PATH,
            yunet_model_path=settings.YUNET_MODEL_PATH,
            vocabulary_path=settings.VOCABULARY_PATH,
            timeout_ms=settings.PIPELINE_TIMEOUT_MS,
        )
        self.state: BeliefState = BeliefState(mode="walk")
        self.trace_logger: TraceLogger = TraceLogger(get_trace_repo())
        
        # Failure and degradation counters for trace auditing
        self.failure_counters: Dict[str, int] = {
            "timeouts": 0,
            "degraded_cycles": 0,
            "error_cycles": 0,
            "dropped_frames": 0,
        }

    async def put_frame(self, frame: FrameMessage) -> None:
        """Enforces latest-frame-wins: drops stale frame if queue is full, then puts new frame."""
        if self.frame_buffer.full():
            try:
                self.frame_buffer.get_nowait()
            except asyncio.QueueEmpty:
                pass
        await self.frame_buffer.put(frame)
        self.last_seq = frame.seq

    def handle_command(self, cmd: CommandMessage) -> None:
        """Processes client control command."""
        if cmd.command in ("walk", "read", "describe"):
            self.state.mode = cmd.command
            if cmd.command == "describe":
                self.state.force_detector = True
        elif cmd.command == "stop":
            self.state.mode = "walk"
            self.state.active_reframe = None
            self.state.pending_confirmation = None

    def handle_response(self, resp: UserResponse) -> None:
        """Processes client active perception user confirmation response."""
        if resp.answer == "yes":
            self.state.approved_read = True
            self.state.pending_confirmation = None
        else:
            self.state.approved_read = False
            self.state.pending_confirmation = None


class SessionManager:
    """Tracks and manages all active client sessions across the server."""

    def __init__(self):
        self._sessions: Dict[str, Session] = {}
        self._lock = asyncio.Lock()

    async def create_session(self, session_id: str, websocket: WebSocket) -> Session:
        """Registers a new active session."""
        async with self._lock:
            session = Session(session_id=session_id, websocket=websocket)
            self._sessions[session_id] = session
            return session

    async def remove_session(self, session_id: str) -> Optional[Session]:
        """Removes a session upon client disconnection."""
        async with self._lock:
            session = self._sessions.pop(session_id, None)
            if session:
                session.is_active = False
            return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Retrieves an active session by session_id."""
        return self._sessions.get(session_id)

    def active_session_count(self) -> int:
        """Returns the number of active sessions."""
        return len(self._sessions)


# Global singleton session manager
session_manager = SessionManager()
