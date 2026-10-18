# SeeGuide: Competition Demo Video Script
## 5-Minute Demonstration Script for OpenCV AI Competition 2026
**Target Category:** Agentic Vision Award & Technical Quality  
**Total Running Time:** Exactly 4 minutes 58 seconds (Strictly $\le 5:00$ Limit)

---

### Timing & Storyboard Overview

| Segment | Timestamp | Duration | Subject / Topic | Primary Visual |
| :---: | :---: | :---: | :--- | :--- |
| **1** | 0:00 – 0:30 | 0:30 | Team Intro, Problem Statement & User Reality | Split screen: Blind pedestrian walking with white cane + talking head. |
| **2** | 0:30 – 1:15 | 0:45 | End-to-End System Architecture & $0 AWS Free Tier | Architecture animation showing PWA, Caddy, OpenCV 5, DynamoDB. |
| **3** | 1:15 – 2:45 | 1:30 | Live Walk Mode Demo (Hazard Detection & Deliberate Silence) | Split screen: Corridor camera feed with OpenCV overlays + Phone PWA UI. |
| **4** | 2:45 – 3:30 | 0:45 | Read Mode Demo (Active Perception & Human Confirmation) | Phone pointing at door plaque: bad angle → reframe → confirmation dialog. |
| **5** | 3:30 – 4:15 | 0:45 | Empirical Evaluation vs Baselines & Latency Profiling | Metrics tables from `metrics.csv` & profiling percentiles from `profile.csv`. |
| **6** | 4:15 – 4:45 | 0:30 | Failure Cases, Honest Uncertainty & Responsible Use | Screen showing blur/lighting failure handling + privacy face blurring. |
| **7** | 4:45 – 5:00 | 0:15 | Summary, Open-Source Repository & Endpoint | Closing title card with GitHub QR code, live DuckDNS URL, and credits. |

---

### Detailed Scene-by-Scene Script

#### Segment 1: Team Introduction & The Navigation Problem (0:00 – 0:30)
- **Time:** `0:00 – 0:30` (30s)
- **Visuals:**
  - `0:00–0:10`: Presenter on camera welcoming the judges. Title card: *"SeeGuide: Privacy-First Agentic Vision for Blind Pedestrians"*.
  - `0:10–0:30`: B-roll of a blind individual navigating an office hallway with a white cane. An oncoming person pushing a cart approaches quickly.
- **Audio / Voiceover:**
  > *"Hello judges! Welcome to SeeGuide, built for the OpenCV AI Competition 2026.  
  > For blind and low-vision pedestrians, moving through busy corridors is high-stakes. While a white cane detects ground-level drop-offs, it cannot warn of rapid oncoming hazards until contact occurs.  
  > Worse, traditional AI captioners chatter incessantly, deafening the user to acoustic echoes and footsteps.  
  > SeeGuide changes that. It isn't a passive captioner—it is an active agent that perceives, decides, and warns only when necessary, treating silence as a first-class action."*

---

#### Segment 2: System Architecture & AWS Free Tier (0:30 – 1:15)
- **Time:** `0:30 – 1:15` (45s)
- **Visuals:**
  - `0:30–0:55`: Clean motion graphics diagram of the architecture. Camera frame streams via WebSocket over TLS into Caddy reverse proxy, then into the FastAPI backend on an AWS EC2 `t4g.micro` instance.
  - `0:55–1:15`: Highlight the two core engines: the OpenCV 5 tiered vision pipeline and the deterministic agent runtime. Show DynamoDB table with 7-day auto-TTL. Callout box: *"Total Infrastructure Cost: $0.00/Month"*.
- **Audio / Voiceover:**
  > *"Here is how SeeGuide operates at zero dollar cost on the AWS Free Tier.  
  > The user's phone captures 640 by 480 video, streaming frames over secure WebSockets through Caddy into our FastAPI backend.  
  > Our ingestion implements a strict 'latest-frame-wins' buffer, completely eliminating queuing lag.  
  > In the backend, OpenCV 5 executes a modular pipeline: fast Laplacian blur, lighting checks, Farneback optical flow, and YOLOX object tracking.  
  > Observations feed a deterministic 6-rule policy engine that arbitrates actions from P0 emergency alarms down to P3 ambient silence.  
  > All telemetry is logged asynchronously to DynamoDB with an automatic 7-day TTL purge for privacy."*

---

#### Segment 3: Live Walk Mode Demo — Hazard Alert & Deliberate Silence (1:15 – 2:45)
- **Time:** `1:15 – 2:45` (90s)
- **Visuals:**
  - `1:15–1:45`: Split-screen live test. Left: First-person camera POV of someone walking down an empty hallway. Right: Screen capture of the accessible SeeGuide PWA. The status badge displays *"Connected"*, and the feedback panel is quiet.
  - `1:45–2:15`: A colleague walks directly toward the camera at a brisk pace. OpenCV bounding box tracks the person, computing a growth rate of $1.35$ in the center corridor. The PWA feedback panel flashes red.
  - `2:15–2:45`: The oncoming person steps aside. The hallway clears. The system immediately returns to silence.
- **Audio / Voiceover & Device Audio:**
  > *(Voiceover)*: *"Let's watch SeeGuide in Walk Mode. As the user walks down this clear hallway, notice something crucial: total silence. The agent evaluates stability every frame and deliberately chooses silence so the user retains complete acoustic awareness.  
  > Now, watch as an oncoming pedestrian enters the corridor..."  
  > **(Device Audio - PWA TTS)**: [Sharp, immediate voice preemption] **'Stop! Obstacle approaching rapidly.'**  
  > *(Voiceover)*: *"The looming tracker detected bounding box expansion exceeding 1.2 in the center corridor, triggering a P0 hazard alert in under 150 milliseconds, accompanied by urgent dual-pulse haptics.  
  > As soon as the obstacle clears, the agent returns to silence. No chattering, no false alarms."*

---

#### Segment 4: Read Mode Demo — Active Perception & Human Confirmation (2:45 – 3:30)
- **Time:** `2:45 – 3:30` (45s)
- **Visuals:**
  - `2:45–3:05`: User taps *"Read Mode"* and points the camera at a conference room door plaque, but holds the phone tilted downwards so the plaque is clipped at the top.
  - `3:05–3:15`: The agent prompts reframing. PWA status displays reframing advice. User tilts the camera up; the text becomes centered.
  - `3:15–3:30`: The plaque contains 18 words. The PWA displays a high-contrast confirmation modal with large 'Yes' and 'No' buttons.
- **Audio / Voiceover & Device Audio:**
  > *(Voiceover)*: *"Now we switch to Read Mode. The user points at a room sign, but the camera is tilted too far down, clipping the text. Watch SeeGuide's active perception at work..."  
  > **(Device Audio - PWA TTS)**: **'Camera tilted down, please tilt up.'**  
  > *(Voiceover)*: *"The user adjusts their grip. Now the sign is fully in view with 18 words. Instead of overwhelming the user with a wall of speech, the agent asks first..."  
  > **(Device Audio - PWA TTS)**: **'Found sign with 18 words. Read aloud?'**  
  > *(Voiceover)*: *"The user taps 'Yes'..."  
  > **(Device Audio - PWA TTS)**: **'Room 402: OpenCV AI Robotics Laboratory.'**"

---

#### Segment 5: Empirical Evaluation vs Baselines & Latency Profiling (3:30 – 4:15)
- **Time:** `3:30 – 4:15` (45s)
- **Visuals:**
  - `3:30–3:55`: Full-screen comparison graphic showing the evaluation table directly from `eval/results/metrics.csv`.
  - `3:55–4:15`: Profiling chart showing p50 and p95 latency percentiles from `benchmarks/results/profile.csv`.
- **Audio / Voiceover:**
  > *"Every claim we make is backed by traceable CSV data in the repository.  
  > In our 8-scenario benchmark, SeeGuide achieved 100% Hazard Recall with zero false alarms per minute and a rapid 150 millisecond time-to-warn.  
  > Compared to a naive continuous chatter baseline, SeeGuide reduced auditory clutter by 66.7%, and maintained 100% silence correctness.  
  > Profiling on standard CPU hardware proves our OpenCV 5 pipeline executes with a median cycle time of just 42 milliseconds—well within our 100 millisecond budget."*

---

#### Segment 6: Failure Handling, Limitations & Responsible AI (4:15 – 4:45)
- **Time:** `4:15 – 4:45` (30s)
- **Visuals:**
  - `4:15–4:30`: Demonstration of intentional failure handling. The presenter violently shakes the camera or covers the lens. The PWA displays the degraded status.
  - `4:30–4:45`: Quick montage showing face blurring via YuNet in the privacy tier, followed by a text overlay of responsible use boundaries (curbs/stairs out of scope).
- **Audio / Voiceover & Device Audio:**
  > *(Voiceover)*: *"Responsible AI requires honest failure handling. Under Rule 0, when the camera is shaken or blinded by glare, SeeGuide never guesses or hallucinates..."  
  > **(Device Audio - PWA TTS)**: **'I'm not sure. Please hold the camera steady.'**  
  > *(Voiceover)*: *"Privacy is built-in: human faces are permanently blurred using OpenCV's YuNet before any evaluation artifact touches disk.  
  > And we are explicit: SeeGuide supplements, but never replaces, a white cane or guide dog."*

---

#### Segment 7: Summary, Repository, and Live Endpoint (4:45 – 5:00)
- **Time:** `4:45 – 5:00` (15s)
- **Visuals:**
  - Closing title card displaying:
    - **GitHub Repository:** `https://github.com/your-org/seeguide`
    - **Live Endpoint:** `https://seeguide.duckdns.org`
    - **Test Suite Status:** 60/60 Tests Passing
    - **OpenCV AI Competition 2026 — Agentic Vision Award**
- **Audio / Voiceover:**
  > *"SeeGuide proves that agentic vision can be fast, deterministic, private, and 100% free.  
  > Check out our open-source codebase, full technical report, and live deployment.  
  > Thank you, judges!"*
