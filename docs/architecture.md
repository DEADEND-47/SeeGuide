# SeeGuide: System Architecture

## 1. High-Level System Architecture

SeeGuide utilizes a hybrid edge-to-cloud topology designed for strict low-latency execution and zero operational expenditure. The system connects a lightweight mobile Progressive Web App (PWA) client to an AWS EC2 instance running a Caddy reverse proxy, FastAPI WebSocket server, an OpenCV 5 tiered vision pipeline, and a deterministic agent policy engine.

```mermaid
flowchart TD
    subgraph Client["Mobile Device (Browser PWA)"]
        Cam["Phone Camera (640x480 @ 15fps)"]
        AudioHaptic["Web Speech Synthesis & Vibration API"]
        PWA["PWA Controller & WebSocket Client"]
        Cam --> PWA
        PWA --> AudioHaptic
    end

    subgraph EdgeProxy["Reverse Proxy & Security Boundary"]
        Caddy["Caddy Server (DuckDNS / Auto TLS Let's Encrypt)"]
    end

    subgraph Backend["FastAPI Server (AWS EC2 Free Tier / Local Dev)"]
        WS["FastAPI WebSocket Telemetry Hub"]
        Queue["Buffer (Latest-Frame-Wins: Capacity=1)"]
        
        subgraph VisionEngine["OpenCV 5 Vision Pipeline"]
            FastTier["Fast-Tier: Laplacian Blur, Luma, Motion/Flow"]
            Corridor["Corridor Analyzer: Edge Density & Zone Obstruction"]
            Detector["OpenCV Zoo ONNX Detector (YOLOX-Nano / Person & Obstacle)"]
            OCR["OCR Tier: Text Detection & Recognition (Read Mode)"]
        end
        
        subgraph AgentPolicy["Deterministic Agent Policy Engine"]
            Policy["Rule-Based Arbiter (State, Urgency, Looming)"]
            ActionDispatch["Action Dispatcher (P0..P3 Prioritization)"]
            PrivacyFilter["Privacy Face Redaction (Gaussian Blur)"]
        end
        
        WS --> Queue
        Queue --> FastTier
        FastTier --> Corridor
        Corridor --> Detector
        Detector --> Policy
        OCR -.-> Policy
        Policy --> ActionDispatch
        ActionDispatch --> WS
        ActionDispatch --> PrivacyFilter
    end

    subgraph Storage["Storage Layer (AWS Free Tier / Local File Mock)"]
        DDB["DynamoDB (Structured Trace Telemetry)"]
        S3["AWS S3 / Local (Eval Clips & Benchmarks)"]
        PrivacyFilter --> DDB
        PrivacyFilter --> S3
    end

    PWA <-->|WSS (HTTPS / TLS 1.3)| Caddy
    Caddy <-->|Internal WS / Loopback| WS
```

---

## 2. Component Responsibilities

### 2.1. Phone PWA (Mobile Browser Client)
- **Camera Acquisition:** Requests rear-facing wide-angle camera using `navigator.mediaDevices.getUserMedia` at $640\times 480$ resolution.
- **Frame Telemetry:** Encodes frames as compressed JPEGs and streams them over a persistent WebSocket connection with sequence and client timestamp tags.
- **Action Execution:**
  - Auditory announcements using browser `window.speechSynthesis`.
  - Haptic feedback using `navigator.vibrate` with priority-coded vibration patterns.
  - Directional reframing prompts (speech + audio tone).
- **Session & Accessibility Management:**
  - Prevents screen lock during operation using the Screen Wake Lock API.
  - Implements high-contrast, large touch targets ($\ge 48\times 48\text{ px}$) and screen-reader accessible semantic labels.
  - Supports quick one-touch mode switching between `walk`, `read`, and `describe`.

### 2.2. Caddy Reverse Proxy & Security Layer
- **Automatic HTTPS/TLS:** Provisions and auto-renews free Let's Encrypt SSL/TLS certificates using DuckDNS dynamic DNS integration.
- **Secure Termination:** Terminates client TLS (HTTPS and WSS), enforcing modern TLS 1.3 ciphers.
- **Internal Proxying:** Forwards unencrypted WebSocket traffic to the local FastAPI service on `127.0.0.1:8000`.

### 2.3. FastAPI WebSocket Hub
- **Connection Management:** Maintains bidirectional client session lifecycles, connection heartbeats, and client disconnect handling.
- **Latest-Frame-Wins Buffer:** Implements a strict single-element queue buffer (`maxsize=1`). When a new frame arrives while the previous frame is still undergoing computer vision inference, the stale frame is dropped immediately, eliminating latency buildup.
- **Payload Validation & Parsing:** Deserializes and validates frame envelopes against the `ClientToServerFrame` contract.

### 2.4. OpenCV 5 Vision Pipeline
- **Tier 1: Fast-Tier Quality & Motion ($\le 25\text{ ms}$)**
  - Calculates Laplacian variance to detect optical blur.
  - Measures mean luma/brightness to flag underexposed or overexposed environments.
  - Computes inter-frame motion or dense optical flow divergence to evaluate whether the user is moving forward or turning.
- **Tier 2: Dynamic Corridor Analysis ($\le 30\text{ ms}$)**
  - Partitions visual field into left, center, and right corridor zones.
  - Computes edge density and structural convergence lines to assess central path clearance.
- **Tier 3: Object Detection & Looming Analysis ($\le 80\text{ ms}$)**
  - Executes quantized OpenCV Zoo ONNX model (e.g. YOLOX-nano) via `cv2.dnn`.
  - Tracks candidate obstacle bounding boxes across frames; calculates bounding box growth rate ($\text{growth} = \text{Area}_t / \text{Area}_{t-1}$). Bounding box growth $> 1.2$ in the center zone flags a looming collision hazard.
- **Tier 4: Text Detection & OCR (On-Demand / Read Mode)**
  - Activated conditionally when in `read` mode or when high edge contrast indicates signage.

### 2.5. Deterministic Agent Policy Engine
- **Perception-Decision Loop:** Consumes the unified `VisionToAgentObservation` object on every inference cycle.
- **Deterministic Action Selection:**
  - **P0 (Immediate Hazard):** Collision looming in center zone ($\text{growth} > 1.25$ or $\text{blocked\_score} > 0.8$) $\rightarrow$ `speak("Stop. Obstacle ahead.")`, `vibrate=True`.
  - **P1 (Reframing Directive):** Excessive downward pitch or extreme blur $\rightarrow$ `request_reframe(direction="up")`.
  - **P2 (Information / Confirmation):** Detected door sign or room text $\rightarrow$ `ask_confirmation` or `speak`.
  - **P3 (Deliberate Silence):** Path clear, corridor open, camera stable $\rightarrow$ `stay_silent()`. Silence prevents cognitive fatigue and protects natural hearing.

### 2.6. DynamoDB & S3 Storage Abstraction
- **DynamoDB (Traces):** Stores structured telemetry JSON records (timestamp, session ID, observation metrics, agent decisions, execution latencies).
- **S3 / Local Storage (Evaluation Media):** Stores anonymized frame snapshots for competition evaluation and regression testing.
- **Local Dev Abstraction:** In local development or offline mode, storage operations seamlessly switch to in-memory mocks or local append-only files without requiring AWS credentials.

---

## 3. Core Architectural Principles & Rules

### 3.1. The "Latest-Frame-Wins" Latency Rule
Queued video frames in assistive navigation are perishable. An inference completed on a 500ms-old frame can cause a pedestrian to miss a hazard. 
- The backend uses an asynchronous worker pattern where incoming WebSocket messages overwrite the pending buffer if the worker is busy.
- Stale frames are discarded without processing, guaranteeing that every inference reflects the most recent view.

### 3.2. Privacy-by-Design Rule
- **Ephemeral Processing:** Raw camera frames exist only in volatile RAM buffers during active inference and are overwritten each cycle.
- **Irreversible Anonymization:** If an image is selected for evaluation storage or trace recording, an automated face detector isolates facial bounding boxes and applies a $25\times 25$ Gaussian blur kernel *prior* to serialization or persistence.
- No personally identifiable biometric data is ever stored unblurred.

### 3.3. Security & Cloud Configuration Rule
- **Zero Static Credentials:** The repository and deployment artifacts contain zero AWS access keys, secret keys, or passwords.
- **IAM Instance Profile:** Production EC2 deployment authenticates against DynamoDB and S3 exclusively via temporary STS credentials provided by an attached AWS IAM Role.
- **Encrypted In-Transit:** All client-server communication requires HTTPS/WSS with TLS 1.3. Plain HTTP/WS connections are rejected.
- **Local Mocking Compatibility:** All cloud integrations implement an abstract interface (`StorageRepository`) with both `DynamoDBStorage` and `LocalMockStorage` implementations, ensuring that Stage 1 through Stage 8 can be developed and verified completely offline.
