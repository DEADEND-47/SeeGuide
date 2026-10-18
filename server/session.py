"""SeeGuide Session Management
Maintains active client WebSocket sessions and their dedicated single-frame buffers.
"""

import asyncio
from typing import Dict, Optional
from fastapi import WebSocket
from server.models import FrameMessage


class Session:
    """Represents an active client connection session."""

    def __init__(self, session_id: str, websocket: WebSocket):
        self.session_id: str = session_id
        self.websocket: WebSocket = websocket
        # Single-slot queue enforcing latest-frame-wins latency policy
        self.frame_buffer: asyncio.Queue[FrameMessage] = asyncio.Queue(maxsize=1)
        self.last_seq: int = -1
        self.is_active: bool = True

    async def put_frame(self, frame: FrameMessage) -> None:
        """Enforces latest-frame-wins: drops stale frame if queue is full, then puts new frame."""
        if self.frame_buffer.full():
            try:
                self.frame_buffer.get_nowait()
            except asyncio.QueueEmpty:
                pass
        await self.frame_buffer.put(frame)
        self.last_seq = frame.seq


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
