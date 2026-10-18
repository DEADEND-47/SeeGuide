# SeeGuide

> **CRITICAL SAFETY WARNING:**  
> **SeeGuide is an assistive experimental prototype designed to supplement, NEVER replace, a white cane, guide dog, orientation-and-mobility training, or human judgment.** Users must never rely on SeeGuide as a primary navigation aid or for safety-critical life-and-limb decisions.

---

## Project Overview

**SeeGuide** is a free-tier, privacy-first, real-time phone-camera assistant built for blind and low-vision pedestrians navigating indoor corridors and outdoor sidewalks. Developed for the **OpenCV AI Competition 2026** (specifically targeting the *Agentic Vision Award* and overall technical excellence), SeeGuide moves beyond passive image captioning by implementing an active **perception → decision → action loop**. Powered by **OpenCV 5** vision pipelines and a transparent, deterministic agent policy, SeeGuide evaluates camera telemetry every cycle to proactively warn users of oncoming corridor hazards, request camera reframing when visibility is obstructed or unstable, solicit confirmation before reading lengthy text, or deliberately choose **silence** as a first-class action to preserve acoustic situational awareness.

---

## Development Status

- **Current Stage:** **Stage 1 of 10** — *Requirements Analysis, Repository Inspection, Architecture, Contracts, and Development Plan*
- **Stage Goal:** Establish architectural specifications, functional/non-functional requirements, API telemetry contracts (JSON schemas and example payloads), and validation tooling without introducing premature heavyweight dependencies.
- **Prerequisites Note:** Stage 1 requires **zero cloud credentials, zero external paid API keys, and no ONNX model downloads**. Only a standard Python 3.11+ environment with standard library modules is needed.

---

## Repository Structure

```text
SeeGuide/
├── .gitignore                                      # Excludes virtual environments, models, caches, and secrets
├── README.md                                       # Project overview, safety disclaimers, and quickstart
├── contracts/                                      # Formal JSON Schemas for inter-component communication
│   ├── client_to_server_frame.schema.json         # Telemetry contract for phone camera frames to backend
│   ├── vision_to_agent_observation.schema.json    # Vision pipeline observations sent to deterministic agent
│   └── agent_to_client_action.schema.json         # Agent action directives dispatched to user device
├── docs/                                           # Project architecture and development specifications
│   ├── requirements.md                             # Comprehensive functional and non-functional requirements (FR-1..16, NFR-1..8)
│   ├── architecture.md                             # System design, dataflow diagrams, and privacy/security rules
│   ├── roadmap.md                                  # 10-stage execution plan, milestones, and exit criteria
│   ├── contracts.md                                # Detailed documentation of communication protocols
│   ├── decisions.md                                # Architectural Decision Records (ADRs)
│   ├── assumptions.md                              # System assumptions and operating constraints
│   └── stage-reports/
│       └── stage-1-report.md                       # Stage 1 execution report and verification audit
├── examples/                                       # Verified JSON contract examples
│   ├── frame_message.example.json                 # Sample client frame payload
│   ├── observation.example.json                    # Sample vision pipeline output observation
│   └── action.example.json                         # Sample high-priority hazard warning action
└── scripts/                                        # Operational and validation scripts
    └── validate_contracts.py                       # Zero-dependency Python standard library validator
```

---

## Quickstart: Validating Stage 1

Stage 1 verification uses only Python standard library utilities:

```bash
# Run contract validation suite
python scripts/validate_contracts.py
```

Expected output:
```text
====================================================================
SeeGuide Stage 1 Contract Validation Suite
====================================================================

[Contract] Client-to-Server Frame Message
  Schema:  contracts/client_to_server_frame.schema.json
  Example: examples/frame_message.example.json
  [PASS] All required fields, types, and constraints verified successfully.

[Contract] Vision-to-Agent Observation
  Schema:  contracts/vision_to_agent_observation.schema.json
  Example: examples/observation.example.json
  [PASS] All required fields, types, and constraints verified successfully.

[Contract] Agent-to-Client Action Message
  Schema:  contracts/agent_to_client_action.schema.json
  Example: examples/action.example.json
  [PASS] All required fields, types, and constraints verified successfully.

====================================================================
Summary: 3 passed, 0 failed.
====================================================================
```

You can also syntax-validate all JSON schemas and payload examples directly:
```bash
python -m json.tool contracts/client_to_server_frame.schema.json
python -m json.tool contracts/vision_to_agent_observation.schema.json
python -m json.tool contracts/agent_to_client_action.schema.json
python -m json.tool examples/frame_message.example.json
python -m json.tool examples/observation.example.json
python -m json.tool examples/action.example.json
```

---

## Competition Target

- **Competition:** OpenCV AI Competition 2026
- **Primary Category:** Agentic Vision Award
- **Core Vision Framework:** OpenCV 5 (`opencv-python-headless==5.0.0.93`)
- **Hosting Strategy:** AWS Free Tier eligible (EC2 t4g/t3/t2, DynamoDB, S3) with $0 operating budget constraint.
