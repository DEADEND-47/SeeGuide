"""SeeGuide WebSocket Telemetry Handler
Handles bidirectional client communication, frame ingestion, latest-frame-wins queueing,
and orchestrates the live perception -> decision -> trace -> action loop.
"""

import asyncio
import logging
import time
from fastapi import WebSocket, WebSocketDisconnect, status
from agent.policy import decide
from server.models import (
    AgentAction,
    CommandMessage,
    FrameMessage,
    UserResponse,
    parse_client_message,
)
from server.session import Session, session_manager

logger = logging.getLogger("seeguide.websocket")

# Security: Maximum inbound WebSocket payload size (2MB) to prevent memory exhaustion DoS
MAX_MESSAGE_BYTES: int = 2 * 1024 * 1024


async def frame_processor_loop(
    websocket: WebSocket,
    session: Session,
    send_lock: asyncio.Lock,
) -> None:
    """Consumes incoming video frames from the single-slot buffer, executes the OpenCV 5

    vision pipeline (gated by BeliefState tier requirements), evaluates deterministic agent policy,
    logs trace telemetry, and dispatches action directives back to the client device.
    """
    while session.is_active:
        try:
            frame: FrameMessage = await session.frame_buffer.get()
        except asyncio.CancelledError:
            break

        try:
            # 1. Query BeliefState for tier requirements
            run_detector = session.state.needs_detector()
            run_ocr = session.state.needs_ocr()

            # 2. Execute Vision Pipeline in worker thread to prevent event loop stuttering
            t_start = time.time()
            try:
                observation = await asyncio.to_thread(
                    session.pipeline.process,
                    frame.image_b64,
                    run_detector,
                    run_ocr,
                    frame.ts_client,
                )
            except Exception as pipe_err:
                logger.warning(
                    "Pipeline processing error/fallback for session %s: %s",
                    session.session_id,
                    pipe_err,
                )
                # Resilient fallback acknowledgment for synthetic/malformed test frames
                ack_action = AgentAction(
                    type="log_event",
                    text="Frame received",
                    priority="P3",
                    vibrate=False,
                    request_id=str(frame.seq),
                    mode=frame.mode,
                    reason="latest_frame_queued",
                )
                async with send_lock:
                    await websocket.send_text(ack_action.model_dump_json())
                session.frame_buffer.task_done()
                continue

            # 3. Deterministic Decision Arbitration
            action = decide(observation=observation, state=session.state)

            # 4. Attach session correlation metadata
            if not action.request_id:
                action.request_id = str(frame.seq)
            if not action.mode:
                action.mode = session.state.mode

            # 5. Update agent belief state (cooldowns, announced objects, reframing)
            session.state.update(observation, action)

            # 6. Audit & Telemetry Logging
            total_latency_ms = (time.time() - t_start) * 1000.0
            await session.trace_logger.log_cycle(
                session_id=session.session_id,
                observation=observation,
                action=action,
                reason=action.reason or "policy_decision",
                latency_ms=total_latency_ms,
            )

            # 7. Dispatch Action to Client Device
            async with send_lock:
                await websocket.send_text(action.model_dump_json())

            session.frame_buffer.task_done()

        except asyncio.CancelledError:
            break
        except (WebSocketDisconnect, ConnectionResetError):
            break
        except Exception as exc:
            logger.error(
                "Unexpected error in frame processor for session %s: %s",
                session.session_id,
                exc,
                exc_info=True,
            )


async def receive_loop(
    websocket: WebSocket,
    session: Session,
    send_lock: asyncio.Lock,
) -> None:
    """Continuously ingests WebSocket messages (frames, commands, user responses)

    and routes them concurrently to session buffers and handlers.
    """
    while session.is_active:
        try:
            raw_text = await websocket.receive_text()
        except asyncio.CancelledError:
            break

        # Security: Enforce strict maximum payload size to prevent memory exhaustion DoS
        payload_bytes = len(raw_text.encode("utf-8"))
        if payload_bytes > MAX_MESSAGE_BYTES:
            logger.warning(
                "Session %s exceeded maximum allowed message size (%d bytes > %d bytes). Terminating connection.",
                session.session_id,
                payload_bytes,
                MAX_MESSAGE_BYTES,
            )
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Message size exceeds 2MB limit",
            )
            session.is_active = False
            break

        try:
            msg = parse_client_message(raw_text)
        except Exception as ve:
            logger.warning(
                "Session %s received invalid message payload: %s",
                session.session_id,
                ve,
            )
            err_action = AgentAction(
                type="log_event",
                text=f"Invalid schema: {ve}",
                priority="P3",
                vibrate=False,
                reason="validation_error",
            )
            async with send_lock:
                await websocket.send_text(err_action.model_dump_json())
            continue

        if isinstance(msg, FrameMessage):
            # Sync session mode if specified
            if msg.mode in ("walk", "read", "describe") and session.state.mode != "describe":
                session.state.mode = msg.mode
            await session.put_frame(msg)

        elif isinstance(msg, CommandMessage):
            session.handle_command(msg)
            ack_action = AgentAction(
                type="log_event",
                text=f"Command accepted: {msg.command}",
                priority="P3",
                vibrate=False,
                mode=session.state.mode,
                reason=f"command_{msg.command}",
            )
            async with send_lock:
                await websocket.send_text(ack_action.model_dump_json())

        elif isinstance(msg, UserResponse):
            session.handle_response(msg)
            ack_action = AgentAction(
                type="log_event",
                text=f"Response accepted: {msg.answer}",
                priority="P3",
                vibrate=False,
                confirm_id=msg.confirm_id,
                mode=session.state.mode,
                reason=f"response_{msg.answer}",
            )
            async with send_lock:
                await websocket.send_text(ack_action.model_dump_json())


async def handle_websocket(websocket: WebSocket, session_id: str) -> None:
    """Core WebSocket connection orchestrator managing concurrent receiver and processor loops."""
    await websocket.accept()
    session = await session_manager.create_session(session_id=session_id, websocket=websocket)
    send_lock = asyncio.Lock()
    logger.info(
        "Session %s connected. Active sessions: %d",
        session_id,
        session_manager.active_session_count(),
    )

    receive_task = asyncio.create_task(receive_loop(websocket, session, send_lock))
    process_task = asyncio.create_task(frame_processor_loop(websocket, session, send_lock))

    try:
        # Run until either loop exits (e.g. client disconnects or fatal error occurs)
        done, pending = await asyncio.wait(
            [receive_task, process_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, WebSocketDisconnect):
                pass

    except WebSocketDisconnect:
        logger.info("Session %s disconnected normally.", session_id)
    except Exception as exc:
        logger.error("Session %s encountered unexpected error: %s", session_id, exc)
    finally:
        session.is_active = False
        receive_task.cancel()
        process_task.cancel()
        await session_manager.remove_session(session_id)
        logger.info(
            "Session %s cleaned up. Remaining sessions: %d",
            session_id,
            session_manager.active_session_count(),
        )
