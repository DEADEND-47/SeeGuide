# SeeGuide

> **CRITICAL SAFETY WARNING:**  
> **SeeGuide is an assistive experimental prototype designed to supplement, NEVER replace, a white cane, guide dog, orientation-and-mobility training, or human judgment.** Users must never rely on SeeGuide as a primary navigation aid or for safety-critical life-and-limb decisions.

---

## Project Overview

**SeeGuide** is a free-tier, privacy-first, real-time phone-camera assistant built for blind and low-vision pedestrians navigating indoor corridors and outdoor sidewalks. Developed for the **OpenCV AI Competition 2026** (specifically targeting the *Agentic Vision Award* and overall technical excellence), SeeGuide moves beyond passive image captioning by implementing an active **perception → decision → action loop**. Powered by **OpenCV 5** vision pipelines and a transparent, deterministic agent policy, SeeGuide evaluates camera telemetry every cycle to proactively warn users of oncoming corridor hazards, request camera reframing when visibility is obstructed or unstable, solicit confirmation before reading lengthy text, or deliberately choose **silence** as a first-class action to preserve acoustic situational awareness.

---

## Development Status

- **Current Stage:** **Stage 8 of 10** — *Advanced Reliability, Evaluation, Profiling, and Failure Handling*
- **Stage Goal:** Implement robust failure handling and containment (FR-16 safe "I'm not sure" fallback upon timeouts or degraded perception), full offline evaluation replay harness (`eval/run_eval.py`) comparing against naive (B0) and ablation (B1) baselines to generate `eval/results/metrics.csv`, and latency profiler (`benchmarks/run_profile.py`) generating `benchmarks/results/profile.csv` with p50/p95 latencies across all vision and agent stages.
- **Stages 1–7 Status:** Complete. Contracts, schemas, examples, documentation, environment verification, WebSocket handling, latest-frame-wins buffer, mock storage, OpenCV 5 vision pipeline, deterministic agent engine, accessible frontend PWA, and end-to-end integration loop are preserved and fully tested.

---

## Repository Structure

```text
SeeGuide/
├── .gitignore                                      # Excludes virtual environments, models, caches, and secrets
├── Makefile                                        # Automation targets: setup, check, test, validate, run, clean
├── pytest.ini                                      # Pytest configuration with asyncio_mode=auto and testpaths
├── README.md                                       # Project overview, safety disclaimers, and quickstart
├── requirements.txt                                # Strictly pinned dependencies (OpenCV 5.0.0.93, FastAPI, etc.)
├── agent/                                          # Agent runtime and policy engine package
│   ├── __init__.py
│   ├── policy.py                                   # Deterministic arbitration rules (P0-P3 priorities)
│   ├── state.py                                    # State tracker, operating modes, and history
│   ├── tools.py                                    # Agent vision tools invocation interfaces
│   └── trace.py                                    # Telemetry trace logging
├── benchmarks/                                     # Benchmarking and profiling
│   ├── results/                                    # Profiling output artifacts (.gitkeep)
│   └── run_profile.py                              # Latency profiler
├── contracts/                                      # Formal JSON Schemas for inter-component communication
│   ├── agent_to_client_action.schema.json         # Agent action directives dispatched to user device
│   ├── client_to_server_frame.schema.json         # Telemetry contract for phone camera frames to backend
│   └── vision_to_agent_observation.schema.json    # Vision pipeline observations sent to deterministic agent
├── docs/                                           # Project architecture and development specifications
│   ├── architecture.md                             # System design, dataflow diagrams, and privacy/security rules
│   ├── assumptions.md                              # System assumptions and operating constraints
│   ├── contracts.md                                # Detailed documentation of communication protocols
│   ├── decisions.md                                # Architectural Decision Records (ADRs)
│   ├── requirements.md                             # Comprehensive functional and non-functional requirements
│   ├── roadmap.md                                  # 10-stage execution plan, milestones, and exit criteria
│   └── stage-reports/
│       ├── stage-1-report.md                       # Stage 1 execution report and verification audit
│       └── stage-2-report.md                       # Stage 2 environment & repository structure report
├── eval/                                           # Evaluation pipeline for competition judging
│   ├── clips/                                      # Evaluation video clips (.gitkeep)
│   ├── labels.csv                                  # Ground truth annotation manifest
│   ├── results/                                    # Evaluation metrics and outputs (.gitkeep)
│   └── run_eval.py                                 # Evaluation execution script
├── examples/                                       # Verified JSON contract examples
│   ├── action.example.json                         # Sample high-priority hazard warning action
│   ├── frame_message.example.json                 # Sample client frame payload
│   └── observation.example.json                    # Sample vision pipeline output observation
├── infra/                                          # Zero-dollar AWS Free Tier deployment assets
│   ├── Caddyfile                                   # Reverse proxy with automatic Let's Encrypt TLS
│   ├── deploy.sh                                   # EC2 deployment automation script
│   ├── dynamodb_setup.py                           # DynamoDB trace table provisioner
│   └── iam_policy.json                             # Least-privilege IAM policy for EC2 role
├── scripts/                                        # Operational and validation scripts
│   ├── check_environment.py                       # Validates Python 3.11+, OpenCV 5.x, FastAPI, etc.
│   ├── run_server.ps1                              # Server launch script (Windows PowerShell)
│   ├── run_server.sh                               # Server launch script (Linux/macOS)
│   ├── setup.ps1                                   # Environment setup script (Windows PowerShell)
│   ├── setup.sh                                    # Environment setup script (Linux/macOS)
│   └── validate_contracts.py                       # Zero-dependency Python standard library validator
├── server/                                         # FastAPI WebSocket backend package
│   ├── __init__.py
│   ├── main.py                                     # FastAPI application entry point & health check
│   ├── session.py                                  # Session management and client state
│   └── websocket_handler.py                        # WebSocket telemetry handler & single-frame buffer
├── tests/                                          # Test suite
│   ├── __init__.py
│   ├── test_contracts.py                           # Contract schema verification tests
│   ├── test_hazard.py                              # Hazard evaluation test skeleton
│   └── test_policy.py                              # Deterministic policy test skeleton
├── vision/                                         # OpenCV 5 Computer Vision pipeline package
│   ├── __init__.py
│   ├── detector.py                                 # Object detection (OpenCV Zoo ONNX YOLOX-nano)
│   ├── fast_tier.py                                # Fast-tier Laplacian blur, luma, and flow divergence
│   ├── hazard.py                                   # Corridor edge density and looming collision scoring
│   ├── ocr.py                                      # Text detection & OCR for door signs and labels
│   ├── privacy.py                                  # Irreversible face Gaussian blur redaction
│   └── tracker.py                                  # Obstacle bounding box tracker & growth rate
└── web/                                            # Lightweight browser PWA frontend (.gitkeep)
```

---

## Quickstart & Verification

### 1. Verify Runtime Environment
```bash
python scripts/check_environment.py
```

Expected output:
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
====================================================================
All core environment requirements VERIFIED successfully!
====================================================================
```

### 2. Run Test Suite
```bash
pytest tests/
```

### 3. Run Contract Validation Suite
```bash
python scripts/validate_contracts.py
```

### 4. Makefile Automation (Linux / macOS / WSL)
```bash
make check      # Run environment verification
make test       # Run pytest test suite
make validate   # Run contract validation
make run        # Start FastAPI backend via uvicorn
```

---

## Competition Target

- **Competition:** OpenCV AI Competition 2026
- **Primary Category:** Agentic Vision Award
- **Core Vision Framework:** OpenCV 5 (`opencv-python-headless==5.0.0.93`, verified `cv2.__version__ == "5.0.0"`)
- **Hosting Strategy:** AWS Free Tier eligible (EC2, DynamoDB, S3) with $0 operating budget constraint.
