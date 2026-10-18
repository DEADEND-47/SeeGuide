# SeeGuide Stage 7 Completion Report
## Stage 7: End-to-End Integration and Live Active Perception Loop

**Generated At:** 2026-10-18T15:07:00+05:30  
**Project:** SeeGuide — Privacy-First Phone-Camera Assistant for Blind & Low-Vision Pedestrians  
**Target:** OpenCV AI Competition 2026 (Agentic Vision Award & Technical Quality)  
**Author:** Senior Software Architect, Full-Stack Engineer, AI/ML Engineer, DevOps Engineer, Security Engineer  

---

### 1. Executive Summary

Stage 7 ("End-to-End Integration and Live Active Perception Loop") establishes the complete bidirectional perception-decision-action cycle of SeeGuide. Prior to Stage 7, the OpenCV 5 vision pipeline, deterministic agent policy, and frontend PWA operated in isolation or via mock echo handlers. In this stage, all tiers were wired together through an asynchronous WebSocket orchestrator running dual non-blocking worker loops.

The client device streams camera frames, mode commands (`walk`, `read`, `describe`, `stop`), and active-perception user responses (`yes`, `no`) over WebSocket. The server's `Session` coordinates OpenCV 5 tiered vision processing (gated dynamically by `BeliefState`), evaluates deterministic priority rules, updates internal cooldowns, records auditable traces, and returns prioritized `AgentAction` directives (speech, haptics, reframing, confirmations, or silence).

All 43 existing unit tests from Stages 1–6 continue to pass, and 4 new comprehensive end-to-end integration tests were added in `tests/test_integration.py`, bringing the verified test suite to **47 passing tests** in 2.38 seconds.

---

### 2. Summary of Completed Work

1. **Protocol & Contract Extension (`server/models.py`):**
   - Implemented `CommandMessage` strictly conforming to Pydantic v2 `extra="forbid"` models (`type: Literal["command"]`, `command: Literal["walk", "read", "describe", "stop"]`).
   - Implemented `UserResponse` model (`type: Literal["response"]`, `confirm_id: str`, `answer: Literal["yes", "no"]`).
   - Implemented `parse_client_message(raw)` discriminator function safely routing `FrameMessage`, `CommandMessage`, and `UserResponse`.

2. **BeliefState-Driven Active Vision Gating (`agent/state.py` & `agent/policy.py`):**
   - Added `needs_detector()` to `BeliefState`: throttles heavy object detection to cycle 0 and every 5th cycle during `walk` mode, but executes immediately upon `describe` mode command.
   - Added `needs_ocr()` to `BeliefState`: activates scene text OCR exclusively when in `read` mode, conserving server CPU.
   - Integrated `approved_read` state flag and reset logic for Human-in-the-Loop active perception: Rule 4 in `agent/policy.py` bypasses `ask_confirmation` when the user approves reading lengthy text.

3. **Session Per-Connection Context (`server/session.py`):**
   - Equipped `Session` with an independent `VisionPipeline`, `BeliefState`, and `TraceLogger`.
   - Added `handle_command(cmd)` to immediately toggle operating modes and set detection triggers.
   - Added `handle_response(resp)` to resolve pending confirmations and set `approved_read = True/False`.

4. **Async Dual-Loop WebSocket Handler (`server/websocket_handler.py`):**
   - Replaced dummy Stage 3 verification echo with a concurrent architecture running `receive_loop` and `frame_processor_loop` via `asyncio.wait(return_when=FIRST_COMPLETED)`.
   - Ingested frames are queued into the single-slot buffer (`latest-frame-wins`).
   - Image decoding and OpenCV 5 inference are dispatched to a worker thread via `asyncio.to_thread` to prevent event loop blocking.
   - Outgoing messages are serialized with an `asyncio.Lock()` to prevent ASGI channel interleaving.
   - Full telemetry trace is written for each cycle using `TraceLogger`.

5. **PWA Client Communication (`web/app.js`):**
   - Added `sendMessage(message)` to `WebSocketClient` for sending control payloads.
   - Wired `switchMode(mode)` and `triggerDescribe()` to send `CommandMessage` over WebSocket.
   - Wired `respondConfirmation(approved)` to send `UserResponse` with `confirm_id` and binary answer.
   - Filtered `log_event` messages from speech synthesis so internal acknowledgments do not clutter spoken audio.

6. **End-to-End Integration Test Suite (`tests/test_integration.py`):**
   - Created comprehensive tests validating walk mode perception loop, command mode switching, active perception confirmation flow, and trace repository JSON persistence.

---

### 3. Files Created, Modified, or Deleted

| File | Status | Description |
| :--- | :--- | :--- |
| `server/models.py` | Modified | Added `CommandMessage`, `UserResponse`, `ClientMessage`, and `parse_client_message`. |
| `agent/state.py` | Modified | Added `approved_read`, `force_detector`, `needs_detector()`, and `needs_ocr()`. |
| `agent/policy.py` | Modified | Updated Rule 4 to respect `state.approved_read` after human confirmation. |
| `server/session.py` | Modified | Added `pipeline`, `state`, `trace_logger`, `handle_command()`, and `handle_response()`. |
| `server/websocket_handler.py` | Modified | Implemented dual-loop perception orchestrator with thread offloading and send locking. |
| `web/app.js` | Modified | Added WebSocket command and confirmation transmission; filtered log events from speech. |
| `tests/test_integration.py` | Created | Added 4 comprehensive end-to-end integration tests using `TestClient`. |
| `README.md` | Modified | Updated status and stage objectives to reflect Stage 7 completion. |
| `docs/stage-reports/stage-7-report.md` | Created | This Stage 7 completion and architecture report. |

---

### 4. Important Architectural Decisions

```mermaid
sequenceDiagram
    autonumber
    actor User as Blind Pedestrian
    participant PWA as PWA Frontend (web/app.js)
    participant WS as WebSocket Handler (server)
    participant Pipe as OpenCV 5 Vision Pipeline
    participant Agent as Deterministic Agent Policy
    participant State as BeliefState
    participant Trace as Trace Repository

    User->>PWA: Points phone camera at scene
    PWA->>WS: FrameMessage (JPEG b64, mode="walk", seq=1)
    WS->>State: Check needs_detector(), needs_ocr()
    WS->>Pipe: process(b64, run_detector, run_ocr) [asyncio.to_thread]
    Pipe-->>WS: VisionObservation (quality, motion, corridor, objects)
    WS->>Agent: decide(observation, state)
    Agent-->>WS: AgentAction (stay_silent or speak or reframe)
    WS->>State: update(observation, action)
    WS->>Trace: log_cycle(session_id, obs, action, latency_ms)
    WS-->>PWA: AgentAction JSON
    PWA->>User: Speech synthesis / Haptic pulse

    Note over User, PWA: Active Perception Confirmation Flow
    User->>PWA: Switches to Read Mode ("read")
    PWA->>WS: CommandMessage (command="read")
    WS->>State: state.mode = "read"
    PWA->>WS: FrameMessage (Signage with long text)
    WS->>Pipe: process(b64, run_ocr=True)
    Pipe-->>WS: VisionObservation (text="Emergency exit...")
    WS->>Agent: decide() -> Rule 4 (> 6 words)
    Agent-->>WS: ask_confirmation ("Read text aloud?")
    WS-->>PWA: ask_confirmation (confirm_id="confirm_read_mode")
    PWA->>User: Spoken prompt & shows Yes/No modal
    User->>PWA: Taps "YES"
    PWA->>WS: UserResponse (confirm_id, answer="yes")
    WS->>State: state.approved_read = True
    PWA->>WS: FrameMessage (subsequent frame)
    WS->>Agent: decide() -> approved_read is True -> speak text directly
    WS-->>PWA: speak ("Text reads: Emergency exit...")
    PWA->>User: Speaks full signage text
```

#### Dual Non-Blocking Asynchronous Loops
In `server/websocket_handler.py`, the incoming message ingestion and frame perception execution are split into two concurrent tasks:
- `receive_loop`: Never blocks on computer vision inference. It immediately parses JSON messages, updates mode states, flags confirmations, and enqueues frames into the single-slot buffer.
- `frame_processor_loop`: Dequeues the freshest frame, offloads image decoding and OpenCV 5 inference to a worker thread via `asyncio.to_thread`, evaluates deterministic arbitration, logs trace telemetry, and returns the action directive.

#### State-Driven Active Perception & Vision Gating
To run reliably on constrained compute (such as AWS t4g.micro or local CPU), computer vision tiers are selectively executed:
- **Fast Tier (Quality, Motion, Corridor ROI):** Runs on every frame (~3–8ms).
- **Detector Tier (YOLOX-nano / Tracker):** Runs on cycle 0 and every 5th cycle in walk mode, or immediately when in `describe` mode.
- **OCR Tier (Text Recognition):** Runs exclusively in `read` mode.

---

### 5. Dependencies Added or Changed

**Zero new runtime dependencies were added.** All implementations strictly leverage the confirmed technical stack:
- Python 3.13.7
- OpenCV Headless 5.0.0 (`opencv-python-headless==5.0.0.93`)
- FastAPI 0.136.1 & Starlette
- Pydantic v2.13.3
- WebSockets 16.1.1
- Vanilla ES6 JavaScript (No npm/node runtime dependencies)

---

### 6. Verification and Test Results

#### A. Contract Validation
Command: `python scripts/validate_contracts.py`
```text
====================================================================
SeeGuide Stage 1 Contract Validation Suite
====================================================================

[Contract] Client-to-Server Frame Message
  Schema:  contracts\client_to_server_frame.schema.json
  Example: examples\frame_message.example.json
  [PASS] All required fields, types, and constraints verified successfully.

[Contract] Vision-to-Agent Observation
  Schema:  contracts\vision_to_agent_observation.schema.json
  Example: examples\observation.example.json
  [PASS] All required fields, types, and constraints verified successfully.

[Contract] Agent-to-Client Action Message
  Schema:  contracts\agent_to_client_action.schema.json
  Example: examples\action.example.json
  [PASS] All required fields, types, and constraints verified successfully.

====================================================================
Summary: 3 passed, 0 failed.
====================================================================
```

#### B. Environment Verification
Command: `python scripts/check_environment.py`
```text
====================================================================
SeeGuide Stage 2 Environment Verification
====================================================================
[*] Checking Python runtime: detected 3.13.7
    [PASS] Python version 3.13.7 satisfies requirement (>= 3.11).
[*] Checking OpenCV installation...
    Detected cv2.__version__ = 5.0.0
    [PASS] OpenCV 5.x verified (5.0.0).
[*] Checking FastAPI installation...
    [PASS] FastAPI verified (0.136.1).
[*] Checking Pydantic installation...
    [PASS] Pydantic verified (2.13.3).
[*] Checking WebSockets installation...
    [PASS] WebSockets verified (16.1.1).
    [INFO] uvicorn: 0.46.0
    [INFO] boto3: 1.43.114
    [INFO] pytest: 9.1.1
    [INFO] dotenv: installed
    [INFO] pydantic_settings: 2.14.2
====================================================================
All core environment requirements VERIFIED successfully!
====================================================================
```

#### C. Full Pytest Suite Execution
Command: `pytest tests/ -v`
```text
============================= test session starts =============================
platform win32 -- Python 3.13.7, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\Acer\AppData\Local\Programs\Python\Python313\python.exe
cachedir: .pytest_cache
rootdir: E:\SeeGuide
configfile: pytest.ini
plugins: anyio-4.15.1, langsmith-0.14.11, asyncio-1.4.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 47 items

tests/test_agent_state.py::test_belief_state_defaults PASSED             [  2%]
tests/test_agent_state.py::test_belief_state_cooldown_tracking PASSED    [  4%]
tests/test_agent_state.py::test_belief_state_update_on_p0_action PASSED  [  6%]
tests/test_agent_state.py::test_belief_state_reframe_and_clearing PASSED [  8%]
tests/test_agent_state.py::test_belief_state_confirmation_tracking PASSED [ 10%]
tests/test_agent_state.py::test_trace_logger_persists_cycle PASSED       [ 12%]
tests/test_contracts.py::test_contracts_valid PASSED                     [ 14%]
tests/test_hazard.py::test_hazard_clear_path PASSED                      [ 17%]
tests/test_hazard.py::test_hazard_high_edge_density PASSED               [ 19%]
tests/test_hazard.py::test_hazard_lateral_non_threatening PASSED         [ 21%]
tests/test_integration.py::test_e2e_walk_mode_perception_action_loop PASSED [ 23%]
tests/test_integration.py::test_e2e_command_mode_switch PASSED           [ 25%]
tests/test_integration.py::test_e2e_active_perception_human_confirmation_flow PASSED [ 27%]
tests/test_integration.py::test_e2e_trace_repository_persistence PASSED  [ 29%]
tests/test_models.py::test_frame_message_from_example PASSED             [ 31%]
tests/test_models.py::test_vision_observation_from_example PASSED        [ 34%]
tests/test_models.py::test_agent_action_from_example PASSED              [ 36%]
tests/test_models.py::test_frame_message_validation_errors PASSED        [ 38%]
tests/test_models.py::test_agent_action_invalid_priority PASSED          [ 40%]
tests/test_policy.py::test_p0_hazard_looming PASSED                      [ 42%]
tests/test_policy.py::test_p0_hazard_cooldown PASSED                     [ 44%]
tests/test_policy.py::test_p1_path_blocked PASSED                        [ 46%]
tests/test_policy.py::test_quality_gate_blurry PASSED                    [ 48%]
tests/test_policy.py::test_quality_gate_dark PASSED                      [ 51%]
tests/test_policy.py::test_read_mode_reframe_on_clipped PASSED           [ 53%]
tests/test_policy.py::test_read_mode_reframe_on_low_confidence PASSED    [ 55%]
tests/test_policy.py::test_read_mode_confirmation_for_long_text PASSED   [ 57%]
tests/test_policy.py::test_read_mode_reads_short_text_directly PASSED    [ 59%]
tests/test_policy.py::test_p3_ambient_scene_change PASSED                [ 61%]
tests/test_policy.py::test_stay_silent_unchanged PASSED                  [ 63%]
tests/test_policy.py::test_tools_factory_functions PASSED                [ 65%]
tests/test_storage.py::test_settings_defaults PASSED                     [ 68%]
tests/test_storage.py::test_local_mock_trace_repository PASSED           [ 70%]
tests/test_storage.py::test_local_mock_object_storage PASSED             [ 72%]
tests/test_storage.py::test_storage_factories PASSED                     [ 74%]
tests/test_vision.py::test_fast_tier_single_frame PASSED                 [ 76%]
tests/test_vision.py::test_fast_tier_optical_flow PASSED                 [ 78%]
tests/test_vision.py::test_tracker_growth_calculation PASSED             [ 80%]
tests/test_vision.py::test_tracker_zone_classification PASSED            [ 82%]
tests/test_vision.py::test_compute_iou PASSED                            [ 85%]
tests/test_vision.py::test_hazard_estimation_looming PASSED              [ 87%]
tests/test_vision.py::test_privacy_blur_pass_through PASSED              [ 89%]
tests/test_vision.py::test_vision_pipeline_orchestration PASSED          [ 91%]
tests/test_websocket.py::test_health_endpoint PASSED                     [ 93%]
tests/test_websocket.py::test_websocket_connect_and_frame_acknowledgment PASSED [ 95%]
tests/test_websocket.py::test_websocket_latest_frame_wins_buffering PASSED [ 97%]
tests/test_websocket.py::test_websocket_invalid_payload_error_handling PASSED [100%]

============================= 47 passed in 2.38s ==============================
```

#### D. FastAPI Application Import
Command: `python -c "from server.main import app; print('FastAPI app with full integration imported successfully')"`
```text
FastAPI app with full integration imported successfully
```

#### E. Frontend JavaScript Syntax Verification
Command: `node --check web/app.js`
```text
(Clean exit with code 0; 0 syntax errors)
```

---

### 7. Known Issues and Unresolved Blockers

**No known issues or unresolved blockers exist.**
- Event loop deadlocks are eliminated by running separate producer/consumer tasks.
- Network congestion is mitigated by single-slot latest-frame-wins queueing.
- Audio spamming is suppressed by the deterministic 6-rule policy engine and first-class deliberate silence.

---

### 8. Required Environment Variables & Configuration

The local development configuration runs out-of-the-box with zero mandatory environment variables or AWS credentials:
- `USE_MOCK_STORAGE=True` (Default: traces saved to `data/traces/`)
- `ENVIRONMENT=development` (Default)
- `HOST=0.0.0.0`
- `PORT=8000`

---

### 9. Current Repository Status

The repository is clean, operational, and in full working order:
- All 10 directories are populated and functional.
- Static assets (`web/`) are served directly by FastAPI at `/` and accessible to mobile browsers.
- WebSocket endpoint `/ws/{session_id}` handles bidirectional live streaming.
- Mock trace repository logs complete JSON cycle records.

---

### 10. Functional Features & Incomplete Features

#### Functional Features in Stage 7:
1. Continuous perception-decision-action loop with OpenCV 5 and deterministic policy engine.
2. Bidirectional WebSocket streaming with latest-frame-wins queueing.
3. State-driven computer vision tier execution (`needs_detector`, `needs_ocr`).
4. Human-in-the-Loop active perception confirmation dialogs.
5. Mode switching (`walk`, `read`, `describe`, `stop`) triggered from frontend.
6. Real-time audit trace logging with cycle latencies.
7. Mobile PWA with camera stream, video demo evaluation mode, priority audio queue, and haptics.

#### Features Remaining for Future Stages:
- **Stage 8:** Profiling & Benchmark Suite (latency benchmarks, edge case regression suite, competition evaluation metrics).
- **Stage 9:** Zero-Dollar AWS Free Tier Cloud Deployment (EC2 t4g.micro ARM64, Caddy TLS reverse proxy, DynamoDB, S3).
- **Stage 10:** Final Competition Submission Handover (documentation polish, submission video guide, judging walkthrough).

---

### 11. Instructions for Manual Verification

1. **Launch the Server:**
   ```powershell
   python -m uvicorn server.main:app --host 0.0.0.0 --port 8000
   ```
2. **Access the PWA:**
   Open Chrome, Edge, or Safari on your phone or desktop and navigate to `http://localhost:8000/`.
3. **Verify Active Perception Dialogue:**
   - Tap **"Read Text"** mode button. The app sends `{"type": "command", "command": "read"}` to the backend.
   - Either point camera at text or enable **"Demo Mode"** and upload a video clip.
   - When text with > 6 words is detected, the agent issues `ask_confirmation`.
   - The accessible modal dialog appears and speech synthesis prompts: *"Read the text aloud?"*
   - Tap **"Yes"**. The client sends `{"type": "response", "confirm_id": "...", "answer": "yes"}`.
   - On the subsequent cycle, the agent reads the approved text aloud.
4. **Inspect Generated Traces:**
   View files in `data/traces/*.json` to examine timestamp, observation, action, and latency metrics.

---

### 12. Stage 7 Acceptance Declaration

> **DECLARATION:**  
> **Stage 7 acceptance criteria have been completely and unconditionally SATISFIED.**
> - Stages 1–6 artifacts have been fully preserved without regressions.
> - Client sends commands and user responses via WebSocket.
> - WebSocket handler successfully orchestrates the full live perception → decision → action → trace loop.
> - Vision pipeline execution is gated dynamically by the agent's `BeliefState`.
> - All 47 tests pass in `pytest tests/ -v`.
> - Frontend JavaScript syntax is verified clean with `node --check web/app.js`.
