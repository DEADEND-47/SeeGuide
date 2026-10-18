"""SeeGuide WebSocket Telemetry Handler
Handles bidirectional client communication, frame ingestion, latest-frame-wins queueing,
and agent action dispatch over WebSockets.
"""

import asyncio
import logging
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from server.models import AgentAction, FrameMessage
from server.session import session_manager

logger = logging.getLogger("seeguide.websocket")


async def handle_websocket(websocket: WebSocket, session_id: str) -> None:
    """Core WebSocket handler for client video telemetry streaming."""
    await websocket.accept()
    session = await session_manager.create_session(session_id=session_id, websocket=websocket)
    logger.info("Session %s connected. Active sessions: %d", session_id, session_manager.active_session_count())

    try:
        while True:
            # 1. Receive incoming message
            raw_text = await websocket.receive_text()

            # 2. Parse and validate FrameMessage
            try:
                frame = FrameMessage.from_json_str(raw_text)
            except ValidationError as ve:
                logger.warning("Session %s received invalid frame payload: %s", session_id, ve)
                # Send warning event
                err_action = AgentAction(
                    type="log_event",
                    text=f"Invalid frame schema: {ve.errors()[0]['msg']}",
                    priority="P3",
                    vibrate=False,
                    reason="validation_error",
                )
                await websocket.send_text(err_action.model_dump_json())
                continue

            # 3. Enforce Latest-Frame-Wins Buffer
            await session.put_frame(frame)

            # 4. Stage 3 Verification Response (Dummy AgentAction acknowledgment)
            # In Stage 4/5, this will be replaced by the OpenCV vision pipeline + deterministic agent policy
            ack_action = AgentAction(
                type="log_event",
                text="Frame received",
                priority="P3",
                vibrate=False,
                request_id=str(frame.seq),
                mode=frame.mode,
                reason="latest_frame_queued",
            )
            await websocket.send_text(ack_action.model_dump_json())

    except WebSocketDisconnect:
        logger.info("Session %s disconnected normally.", session_id)
    except Exception as exc:
        logger.error("Session %s encountered unexpected error: %s", session_id, exc)
    finally:
        await session_manager.remove_session(session_id)
        logger.info("Session %s cleaned up. Remaining sessions: %d", session_id, session_manager.active_session_count())
