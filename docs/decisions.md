# SeeGuide: Architecture Decision Records (ADRs)

This document tracks key architectural, algorithmic, and engineering trade-off decisions made for the SeeGuide project.

---

## ADR-001: Selection of OpenCV 5 as Mandatory Vision Framework
- **Status:** Accepted
- **Context:** The project is competing for the **OpenCV AI Competition 2026** (specifically the *Agentic Vision Award*).
- **Decision:** Utilize `opencv-python-headless==5.0.0.93` and OpenCV Zoo ONNX models via `cv2.dnn`.
- **Consequences:** 
  - Guarantees strict compliance with competition eligibility criteria.
  - Native C++ optimized CPU inference for fast Laplacian blur, optical flow, and edge filtering without heavy framework dependencies.

---

## ADR-002: Deterministic Rule-Based Agent vs. Generative LLM Planner
- **Status:** Accepted
- **Context:** Real-time pedestrian obstacle avoidance requires sub-200ms glass-to-ear latency, 100% predictable decision boundaries, zero hallucinations, and zero operating cost ($0.00).
- **Decision:** Implement a deterministic, rule-based arbitration policy instead of a generative LLM/VLM planner.
- **Consequences:**
  - Zero cloud API inference costs (satisfies $0 AWS Free Tier constraint).
  - Deterministic explainability for orientation-and-mobility trainers.
  - Instantaneous (<1ms) policy execution without network roundtrips to proprietary LLM endpoints.

---

## ADR-003: Latest-Frame-Wins Queue Policy (Depth = 1)
- **Status:** Accepted
- **Context:** Over a cellular/WiFi connection, network jitter or computer vision computation spikes can cause frame accumulation. In blind navigation, processing an outdated frame is dangerous.
- **Decision:** Implement a single-slot buffer (`Queue(maxsize=1)`) where new incoming frames overwrite unread frames.
- **Consequences:**
  - Prevents queue buildup and eliminates frame lag.
  - System operates in continuous real-time lockstep with the pedestrian's physical present.

---

## ADR-004: Deliberate Silence as a First-Class Action
- **Status:** Accepted
- **Context:** Blind pedestrians rely heavily on acoustic environmental cues (traffic sounds, footfalls, echo reflection). Constant chatter from an AI assistant leads to cognitive overload and auditory masking of real-world hazards.
- **Decision:** Design `stay_silent` as an explicit, high-priority decision category (`P3`) returned whenever corridors are clear and nominal.
- **Consequences:**
  - Reduces auditory fatigue.
  - Elevates user trust: when the system speaks, the pedestrian knows it is actionable and urgent.

---

## ADR-005: In-Memory Ephemeral Video Frames with Pre-Persistence Privacy Blurring
- **Status:** Accepted
- **Context:** Pedestrian camera streams routinely capture bystanders' faces in public and private hallways, posing major privacy and legal compliance concerns.
- **Decision:** Process all camera frames strictly in ephemeral RAM buffers. If a frame is designated for trace logging or competition evaluation, an automated face detector applies an irreversible Gaussian blur before disk/cloud persistence.
- **Consequences:**
  - Enforces privacy-by-design.
  - Eliminates accidental persistence of unredacted bystander biometric data.

---

## ADR-006: Local Mock Storage Adapters Alongside Cloud Integrations
- **Status:** Accepted
- **Context:** Developers and judges need to test, run, and evaluate SeeGuide locally without requiring live AWS accounts, billing setup, or static credentials.
- **Decision:** Define an abstract `StorageRepository` interface implemented by both `LocalFileStorage` (offline default) and `DynamoDBStorage` (cloud deployment).
- **Consequences:**
  - Stage 1 through Stage 8 can be developed and completely validated offline with zero cloud credentials.
  - Zero-risk of accidental AWS billing charges.
