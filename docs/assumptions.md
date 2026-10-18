# SeeGuide: System Assumptions & Operating Constraints

This document formalizes the baseline assumptions regarding user behavior, device capabilities, network connectivity, and deployment environments.

---

## 1. User & Operational Assumptions

1. **User Role & Competence:**
   - The primary user is an adult or supervised youth pedestrian with visual impairment.
   - The user possesses basic orientation and mobility (O&M) travel skills and utilizes a primary navigation tool (white cane or guide dog).
   - SeeGuide is understood to be an advisory auxiliary aid, not an autonomous mobility system.

2. **Phone Mounting / Handling:**
   - The phone is held in a chest harness, lanyard pouch, or handheld forward-facing orientation.
   - The rear camera has an unobstructed field of view pointing horizontally along the walking corridor.
   - If the camera tilts excessively downward (pointing at shoes) or upward (pointing at ceiling), the active perception engine will request reframing.

3. **Operating Environments:**
   - Primary: Familiar indoor hallways, office corridors, transit concourses, and outdoor sidewalks.
   - Nominal lighting conditions ($\ge 30\text{ lux}$). Under extreme low light or pitch darkness, the system issues a warning or suggests torch activation.

---

## 2. Hardware & Client Device Assumptions

1. **Mobile Platform:**
   - Modern smartphone (iOS Safari 15+ or Android Chrome 100+) supporting standard Web APIs:
     - `MediaDevices.getUserMedia` (video stream acquisition)
     - `WebSocket` (full duplex bidirectional communication)
     - `window.speechSynthesis` (text-to-speech)
     - `navigator.vibrate` (haptic pulses, where supported by OS/browser)
     - `navigator.wakeLock` (preventing display sleep)

2. **Camera Specification:**
   - Capable of providing $640\times 480$ video at $15\text{ to }30\text{ fps}$.

---

## 3. Network & Infrastructure Assumptions

1. **Network Connectivity:**
   - Standard 4G LTE, 5G, or Wi-Fi connectivity with roundtrip latency $\le 80\text{ ms}$.
   - WebSocket protocol support without aggressive corporate proxy interference.

2. **Server Infrastructure:**
   - Single AWS Free Tier instance (e.g. `t4g.micro` / `t4g.small` or `t3.micro` / `t2.micro`).
   - Ubuntu 22.04 LTS or 24.04 LTS host environment.
   - CPU-only execution without discrete GPU accelerators.
