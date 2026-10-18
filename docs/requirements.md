# SeeGuide: System Requirements Specification

## 1. Executive Summary & Purpose

**SeeGuide** is an assistive vision system built for the **OpenCV AI Competition 2026** (targeting the **Agentic Vision Award**). The primary objective is to empower blind and low-vision pedestrians with real-time, proactive spatial awareness along familiar indoor and outdoor corridors. 

Rather than functioning as a passive image captioner, SeeGuide implements a closed **Perception → Decision → Action** loop where an intelligent, deterministic agent evaluates perceptual telemetry and executes discrete, prioritized actions including hazard alerts, reframing suggestions, text confirmation prompts, and deliberate silence.

---

## 2. Core Constraints & Standards

### 2.1. OpenCV 5 Mandatory Framework
- **Requirement:** The vision backend must run exclusively on **OpenCV 5** (specifically `opencv-python-headless==5.0.0.93`).
- **Models:** Model zoo integrations must utilize official OpenCV Zoo ONNX models executing via the OpenCV `cv2.dnn` backend or lightweight ONNX runtimes.
- **Algorithms:** Image quality assessment (Laplacian variance), motion/divergence analysis (Farneback optical flow / frame diffs), and corridor edge analysis must utilize optimized native OpenCV 5 primitives.

### 2.2. Zero-Dollar ($0.00) Budget Constraint
- **Hosting:** Must execute within AWS Free Tier limits (single EC2 t4g/t3/t2 instance, DynamoDB 25GB free tier, S3 5GB standard free tier).
- **DNS & SSL:** DuckDNS free dynamic DNS with automatic Let's Encrypt TLS certificate provisioning via Caddy web server.
- **AI Models:** Strictly no paid LLM/VLM cloud APIs (e.g., OpenAI, Anthropic, Google Cloud Vision, Azure Cognitive Services) in the critical perception-action loop. All processing runs locally on the host CPU.

### 2.3. Safety Disclaimer & Boundaries
- SeeGuide is strictly an **assistive navigation aid** and does **NOT replace white canes, guide dogs, orientation-and-mobility (O&M) specialists, or human caution**.

---

## 3. Functional Requirements (FR-1 through FR-16)

| ID | Title | Description | MoSCoW |
| :--- | :--- | :--- | :--- |
| **FR-1** | **Client Camera Capture** | The browser PWA captures continuous rear camera video at 640x480 resolution (15-30 fps) with automatic exposure and focus controls. | Must Have |
| **FR-2** | **Secure Frame Telemetry** | Transmit captured frames over secure WebSockets (`wss://`) packaged with client metadata (session ID, sequence number, timestamp, user mode). | Must Have |
| **FR-3** | **Fast-Tier Quality & Motion** | OpenCV 5 pipeline computes per-frame Laplacian blur, mean brightness/luma, and frame-to-frame motion/corridor divergence in <30ms. | Must Have |
| **FR-4** | **Corridor Obstacle Density** | Segment the central walking corridor into zones (left, center, right); calculate edge density and path obstruction score. | Must Have |
| **FR-5** | **Object Detection & Looming** | Run an OpenCV Zoo object detector (e.g., YOLOX-nano) to detect pedestrians, obstacles, and compute bounding box area growth rate (`growth > 1.2` indicates approaching hazard). | Must Have |
| **FR-6** | **Text Detection & OCR** | Detect and recognize text on doors, signs, and labels using OpenCV text detection / OCR pipeline when in Read mode or when requested. | Should Have |
| **FR-7** | **Deterministic Agent Policy** | A rule-based agent loop consumes observations every cycle, cross-referencing motion, obstacle trajectory, and visual stability without non-deterministic hallucinations. | Must Have |
| **FR-8** | **Priority-Based Action Dispatch** | Actions are classified and dispatched by priority: `P0` (immediate hazard alert), `P1` (reframing advice), `P2` (read text / info), `P3` (silent event). | Must Have |
| **FR-9** | **Silence as a First-Class Action** | The agent intentionally outputs `stay_silent` when conditions are stable and no hazards exist, preventing cognitive overload and preserving environmental acoustic hearing. | Must Have |
| **FR-10** | **Active Perception & Reframing** | If the camera is tilted too far down, obscured, or blurred during transit, the agent prompts directional reframing (e.g., "Tilt camera up slightly"). | Must Have |
| **FR-11** | **Human-in-the-Loop Confirmation** | Before reading detected text longer than a threshold (e.g. >12 words), the agent requests verbal or haptic confirmation ("Found sign with 25 words. Read aloud?"). | Should Have |
| **FR-12** | **Multi-Modal Operating Modes** | Support three discrete user modes: `walk` (hazard avoidance focus), `read` (signage and document focus), and `describe` (on-demand scene summary). | Must Have |
| **FR-13** | **Auditory & Haptic Feedback** | Client browser executes high-priority alerts via Web Speech API speech synthesis accompanied by distinct vibration patterns (Vibration API). | Must Have |
| **FR-14** | **Trace Telemetry Logging** | Persist structured JSON observation and action traces with microsecond timestamps to DynamoDB / local mock for evaluation and judging. | Must Have |
| **FR-15** | **Privacy Face Blurring** | Detect human faces and apply irreversible Gaussian blur before any frame image artifact is persisted to storage. | Must Have |
| **FR-16** | **Storage Abstraction & Local Mocking**| Provide pluggable storage adapters allowing complete offline testing and validation without live AWS credentials. | Must Have |

---

## 4. Non-Functional Requirements (NFR-1 through NFR-8)

| ID | Title | Specification | MoSCoW |
| :--- | :--- | :--- | :--- |
| **NFR-1** | **Latency Budget** | Fast-tier perception (blur, motion, corridor check) must complete in $\le 30\text{ ms}$; full detector cycle $\le 100\text{ ms}$; glass-to-ear latency $\le 250\text{ ms}$ for P0 warnings. | Must Have |
| **NFR-2** | **Zero-Dollar Budget** | Total infrastructure deployment and running cost must equal strictly \$0.00 using AWS Free Tier and open-source tools. | Must Have |
| **NFR-3** | **OpenCV 5 Strict Compliance**| All computer vision algorithms must execute on OpenCV 5.0 headless releases without deprecated legacy dependencies. | Must Have |
| **NFR-4** | **Latest-Frame-Wins Strategy** | The server drops stale incoming frames when processing takes longer than frame arrival rate; queue depth is strictly 1 to eliminate lag. | Must Have |
| **NFR-5** | **Privacy by Design** | Raw video frames are processed in-memory and discarded immediately; no raw pedestrian images are stored without explicit privacy redaction. | Must Have |
| **NFR-6** | **Accessibility Standards** | Mobile PWA complies with WCAG 2.1 AA: large touch targets (min $48\times 48\text{ px}$), screen-reader labels (ARIA), high-contrast UI, and Wake Lock API. | Must Have |
| **NFR-7** | **Deterministic Explainability**| Every agent decision includes a machine-readable `reason` string allowing 100% auditable replay and debugging for O&M trainers. | Must Have |
| **NFR-8** | **Zero Hardcoded Secrets** | Codebase contains no embedded credentials; cloud deployment utilizes AWS IAM Instance Roles and environment configuration. | Must Have |

---

## 5. Explicit Out-of-Scope Items

To ensure real-time performance and prevent life-threatening safety failures, the following domains are **strictly out of scope**:
1. **Drop-offs, Curbs, and Staircases:** Phone camera depth and single-monocular geometry cannot reliably guarantee ground-level negative obstacle detection. White canes remain the primary ground detection tool.
2. **Traffic Signals & Street Crossings:** Autonomous pedestrian crossing decisions require ultra-high safety certifiability and are excluded.
3. **Turn-by-Turn GPS Navigation:** Outdoor route guidance is handled by specialized GPS navigation applications; SeeGuide focuses strictly on the local walking corridor.
4. **Replacement of Canes or Guide Dogs:** SeeGuide is explicitly a supplement, never a substitute.
5. **High-Power Cloud GPU Inference:** Cloud-hosted GPU servers violate the zero-dollar free-tier constraint.
6. **Paid Commercial LLMs / Vision APIs:** Commercial APIs introduce unacceptable operational costs and non-deterministic response times.

---

## 6. MoSCoW Requirements Categorization

### Must Have
- Complete OpenCV 5 fast-tier + detector pipeline running on CPU.
- Deterministic agent decision policy with `P0`–`P3` priority actions.
- Silence as a first-class action (`stay_silent`).
- Active perception reframing directives (`request_reframe`).
- Zero-dollar AWS Free Tier deployment topology (Caddy, FastAPI, DynamoDB).
- Privacy face blurring before image persistence.
- Complete contract validation and evaluation trace logging.

### Should Have
- Text detection & OCR reading mode with user confirmation flow.
- Directional spatial audio cues or variable haptic vibration cadences.
- Orientation-and-mobility (O&M) trainer trace review playback viewer.

### Could Have
- Light on-device WebAssembly fallback for offline basic blur/light detection.
- Customizable voice pitch/rate settings in PWA.

### Won't Have (Out of Scope for 2026 Competition)
- Depth-camera/LiDAR hardware integration.
- Outdoor road crossing autonomous signaling.
- Paid cloud LLM / GenAI inference pipelines.
