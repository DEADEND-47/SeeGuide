# SeeGuide: 10-Stage Implementation Roadmap

This roadmap defines the structured, incremental engineering plan for SeeGuide, built for the OpenCV AI Competition 2026 (Agentic Vision Award). Each stage builds systematically on previous stages with clear deliverables and verified exit criteria.

---

## Stage 1: Requirements Baseline, Repository Inspection, Architecture, Contracts, and Development Plan
- **Status:** **CURRENT STAGE**
- **Objective:** Establish the comprehensive requirements baseline, verify repository state, document end-to-end architecture, define API communication contracts, provide validation tooling, and lay out the execution roadmap.
- **Expected Deliverables:**
  - `README.md` with safety disclaimer, system overview, and validation commands.
  - `docs/requirements.md` (FR-1..16, NFR-1..8, OpenCV 5 requirements, $0 constraint, safety bounds).
  - `docs/architecture.md` (System dataflow diagram, component roles, latest-frame-wins rule, privacy/security rules).
  - `docs/roadmap.md` (10-stage execution plan).
  - `docs/contracts.md` (Contract documentation and protocol mechanics).
  - Contract schemas: `contracts/client_to_server_frame.schema.json`, `contracts/vision_to_agent_observation.schema.json`, `contracts/agent_to_client_action.schema.json`.
  - Contract examples: `examples/frame_message.example.json`, `examples/observation.example.json`, `examples/action.example.json`.
  - Python standard library validator: `scripts/validate_contracts.py`.
  - `.gitignore` (excludes secrets, venvs, cache, models, and eval media).
  - `docs/stage-reports/stage-1-report.md`.
- **Exit Criteria:**
  - `scripts/validate_contracts.py` passes all 3 contracts with zero errors using Python standard library.
  - JSON schemas and payload examples are fully valid JSON.
  - No third-party packages, AWS credentials, or model downloads required.

---

## Stage 2: Project Foundation, Environment Configuration, Dependencies, and Core Repository Structure
- **Objective:** Establish reproducible environment configuration (Python 3.11/3.12/3.13 virtual environment, `pyproject.toml` / `requirements.txt`), pinned OpenCV 5 headless packages, configuration management, and baseline testing framework.
- **Expected Deliverables:**
  - `pyproject.toml` and/or `requirements.txt` with `opencv-python-headless==5.0.0.93`, `fastapi`, `uvicorn`, `websockets`, `pydantic`.
  - Application package layout under `src/seeguide/` (`core/`, `vision/`, `agent/`, `api/`, `storage/`).
  - Configuration loader (`src/seeguide/core/config.py`) reading environment variables with sensible defaults.
  - Initial test scaffolding with `pytest`.
  - `docs/stage-reports/stage-2-report.md`.
- **Exit Criteria:**
  - Clean virtual environment setup without dependency conflicts.
  - Baseline test suite (`pytest`) runs and passes.
  - OpenCV 5 imports and reports version `5.x`.

---

## Stage 3: Contracts, Configuration, Backend Foundations, and Storage Abstractions
- **Objective:** Implement Pydantic data models for the contracts, build the core FastAPI WebSocket server foundation, implement the "Latest-Frame-Wins" worker queue, and provide pluggable storage adapters.
- **Expected Deliverables:**
  - Pydantic models for Frame, Observation, and Action matching Stage 1 schemas.
  - Storage abstraction interface (`StorageRepository`) with `LocalFileStorage` and `DynamoDBStorage` implementations.
  - FastAPI WebSocket endpoint (`/ws/telemetry`) accepting frame messages and replying with heartbeat/acknowledgments.
  - Single-slot buffer (`asyncio.Queue(maxsize=1)`) with drop-stale semantics.
  - Unit tests for contracts, serialization, and storage adapters.
- **Exit Criteria:**
  - WebSocket connection test successfully exchanges frame and mock response.
  - Stale frames are verified dropped when processing latency exceeds arrival interval.
  - Unit tests pass with 100% test pass rate.

---

## Stage 4: Core Vision Pipeline
- **Objective:** Implement the tiered OpenCV 5 computer vision processing pipeline on incoming frames.
- **Expected Deliverables:**
  - `FastTierAnalyzer`: Computes Laplacian variance blur, mean brightness, and inter-frame motion.
  - `CorridorAnalyzer`: Detects horizontal corridor zones, edge density, and path obstruction score.
  - `ObjectDetectorTier`: Integrates OpenCV Zoo ONNX model via `cv2.dnn` (YOLOX-nano) for pedestrian/obstacle detection and computes bounding box growth rate.
  - `FaceBlurFilter`: Applies irreversible Gaussian blur to detected faces before frame persistence.
  - Benchmarking script to verify $\le 30\text{ ms}$ fast-tier and $\le 100\text{ ms}$ full pipeline latency on CPU.
- **Exit Criteria:**
  - Vision pipeline consumes raw base64/JPEG frames and returns fully populated `VisionToAgentObservation`.
  - Benchmarks confirm execution within CPU latency budgets.

---

## Stage 5: Agent Runtime and Policy Engine
- **Objective:** Implement the deterministic, rule-based agent policy that maps perception observations to prioritized actions.
- **Expected Deliverables:**
  - `AgentPolicyEngine`: Evaluates observation metrics (stability, motion, corridor blockage, obstacle growth).
  - Priority arbiter:
    - `P0`: Looming hazard in center zone $\rightarrow$ "Stop. Obstacle ahead."
    - `P1`: Low quality / severe tilt $\rightarrow$ "Tilt camera up."
    - `P2`: OCR text reading with confirmation handling.
    - `P3`: Clear path $\rightarrow$ `stay_silent()`.
  - Unit test suite exercising all deterministic branches and edge cases.
- **Exit Criteria:**
  - All policy rules covered by deterministic test fixtures.
  - Silence is verified selected in nominal walking conditions.

---

## Stage 6: Frontend PWA and User Experience
- **Objective:** Develop the accessible mobile web client (PWA) with camera streaming, Web Speech synthesis, and vibration feedback.
- **Expected Deliverables:**
  - Progressive Web App (`static/` or lightweight client) with `manifest.json` and service worker.
  - Video capture loop streaming compressed JPEG frames over WebSocket.
  - Web Speech API integration for auditory speech output.
  - Vibration API integration for haptic priority pulses.
  - Screen Wake Lock integration to keep screen active.
  - Screen-reader accessible UI (high contrast, ARIA landmarks, large tap buttons for mode switching).
- **Exit Criteria:**
  - PWA loads on mobile browser, connects over WebSocket, captures camera, and plays synthesized speech and vibrations.

---

## Stage 7: End-to-End Integration
- **Objective:** Connect the PWA client, FastAPI WebSocket server, OpenCV 5 vision pipeline, agent policy engine, and storage layer into a unified live loop.
- **Expected Deliverables:**
  - Complete end-to-end telemetry pipeline: Camera $\rightarrow$ WebSocket $\rightarrow$ Vision $\rightarrow$ Agent $\rightarrow$ Speech/Haptic $\rightarrow$ Trace Log.
  - Active perception reframing demonstrated in live loop.
  - Confirmation loop verified for long text.
  - Local trace logging verified with replay capability.
- **Exit Criteria:**
  - Full perception-decision-action cycle operates continuously under live camera input with $<250\text{ ms}$ response.

---

## Stage 8: Advanced Reliability, Evaluation, Profiling, and Failure Handling
- **Objective:** Harden system reliability against network jitter, dropped connections, corrupted frames, and perform quantitative evaluation on benchmark clips.
- **Expected Deliverables:**
  - WebSocket auto-reconnect and graceful degradation handlers.
  - Benchmark evaluation suite running on recorded corridor clips (measuring hazard detection precision/recall, false alarm rate, latency distribution).
  - Evaluation report generator creating competition judging metrics.
  - Error handling for invalid frames, extreme darkness, and camera disconnects.
- **Exit Criteria:**
  - System recovers gracefully from disconnections without manual restart.
  - Benchmark evaluation suite outputs quantitative metrics for competition submission.

---

## Stage 9: Security, Accessibility, Performance, AWS Deployment Preparation
- **Objective:** Finalize security hardening, audit accessibility, optimize CPU performance, and prepare zero-dollar AWS deployment automation.
- **Expected Deliverables:**
  - Caddy configuration (`Caddyfile`) with DuckDNS dynamic DNS and automated Let's Encrypt TLS.
  - Systemd service definition and deployment instructions for EC2 free-tier instances.
  - AWS IAM Instance Role least-privilege policy definitions (DynamoDB/S3).
  - Accessibility audit report (WCAG 2.1 AA compliance validation).
  - Performance profiling confirming zero memory leaks and stable CPU usage.
- **Exit Criteria:**
  - Zero hardcoded secrets verified by static analysis.
  - Deployment configuration verified against AWS Free Tier resource limits ($0.00 billable footprint).

---

## Stage 10: Final Verification, Production Configuration, Documentation, Deployment, and Handover
- **Objective:** Perform end-to-end production verification, complete judging and submission documentation, package competition artifacts, and finalize project handover.
- **Expected Deliverables:**
  - Production deployment verification and smoke test logs.
  - Complete competition submission dossier (architecture narrative, benchmark results, agentic vision highlights, video demo script).
  - Comprehensive user and developer manuals.
  - Final Stage 10 handover report.
- **Exit Criteria:**
  - System is fully operational and reproducible.
  - All competition requirements for the Agentic Vision Award are met and documented.
