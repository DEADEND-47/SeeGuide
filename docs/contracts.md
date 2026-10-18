# SeeGuide: Interface Contracts Specification

This document details the three core communication contracts governing data exchange in SeeGuide:
1. **Client-to-Server Frame Message** (Phone PWA $\rightarrow$ FastAPI Backend)
2. **Vision-to-Agent Observation** (OpenCV 5 Vision Pipeline $\rightarrow$ Deterministic Agent Policy)
3. **Agent-to-Client Action Message** (Deterministic Agent Policy $\rightarrow$ Phone PWA)

Each contract is formally specified with a corresponding JSON Schema in the `contracts/` directory and concrete example payloads in the `examples/` directory.

---

## 1. Client-to-Server Frame Message

### 1.1. Description
Transmitted from the mobile browser PWA over a persistent WebSocket connection (`/ws/telemetry`) to stream captured camera video frames alongside client-side operational telemetry.

> **Note on Optimization:**  
> In Stage 1, this contract is formatted as a structured JSON message containing a Base64-encoded JPEG string for transparency, schema verifiability, and rapid debugging. In later stages (Stages 6–8), this may be augmented with a binary frame protocol (e.g., a binary header followed by raw JPEG bytes) to reduce serialization overhead while maintaining backward compatibility with the JSON envelope.

### 1.2. Schema Location
`contracts/client_to_server_frame.schema.json`

### 1.3. Field Specifications

| Field | Type | Required | Description | Constraints |
| :--- | :--- | :--- | :--- | :--- |
| `type` | string | Yes | Message type discriminator | Must be `"frame"` |
| `session_id` | string | Yes | Unique UUID for client connection session | Non-empty string |
| `seq` | integer | Yes | Monotonically increasing sequence number | $\ge 0$ |
| `ts_client` | number | Yes | Client timestamp in epoch seconds | Microsecond precision |
| `mode` | string | Yes | Current operating mode | `"walk"`, `"read"`, or `"describe"` |
| `image_b64` | string | Yes | Base64-encoded JPEG frame | Valid Base64 string |
| `width` | integer | Yes | Frame pixel width | e.g. 640 |
| `height` | integer | Yes | Frame pixel height | e.g. 480 |
| `mime` | string | Yes | Media MIME type | Must be `"image/jpeg"` |

### 1.4. Example Payload (`examples/frame_message.example.json`)
```json
{
  "type": "frame",
  "session_id": "sess_8f3a91c2-d38a-40a5-b043-98fe04b50c18",
  "seq": 104,
  "ts_client": 1729180000.05,
  "mode": "walk",
  "image_b64": "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA=",
  "width": 640,
  "height": 480,
  "mime": "image/jpeg"
}
```

---

## 2. Vision-to-Agent Observation

### 2.1. Description
Generated internally on the server by the OpenCV 5 computer vision pipeline upon processing a video frame. The observation synthesizes visual quality, inter-frame motion, corridor clearance, detected obstacles with looming calculations, and extracted text. This contract feeds directly into the deterministic agent policy engine.

### 2.2. Schema Location
`contracts/vision_to_agent_observation.schema.json`

### 2.3. Field Specifications

| Field | Type | Required | Description | Constraints |
| :--- | :--- | :--- | :--- | :--- |
| `t` | number | Yes | Server observation epoch timestamp | Float seconds |
| `quality` | object | Yes | Image quality metrics | Requires `blur`, `brightness`, `stable` |
| `quality.blur` | number | Yes | Laplacian variance score | Higher indicates sharper image |
| `quality.brightness` | number | Yes | Mean grayscale pixel intensity | $0.0$ to $255.0$ |
| `quality.stable` | boolean| Yes | Camera stability flag | True if motion/blur is within bounds |
| `motion` | object | Yes | Inter-frame motion and flow | Requires `corridor_divergence`, `ego_motion` |
| `motion.corridor_divergence` | number | Yes | Optical flow divergence into corridor | $> 0$ indicates forward progress |
| `motion.ego_motion` | number | Yes | Magnitude of camera movement | Heuristic motion energy |
| `corridor` | object | Yes | Navigational corridor analysis | Requires `edge_density`, `blocked_score` |
| `corridor.edge_density` | number | Yes | Fraction of high-contrast edges in central path | $0.0$ to $1.0$ |
| `corridor.blocked_score` | number | Yes | Estimated corridor obstruction probability | $0.0$ (clear) to $1.0$ (blocked) |
| `objects` | array | Yes | Array of detected objects | Can be empty `[]` |
| `objects[].cls` | string | Yes | Detected object class | e.g. `"person"`, `"chair"`, `"door"` |
| `objects[].conf` | number | Yes | Detection model confidence | $0.0$ to $1.0$ |
| `objects[].bbox` | array | Yes | Bounding box coordinates $[x_1, y_1, x_2, y_2]$ | Exactly 4 numbers |
| `objects[].growth` | number | Yes | Bounding box area growth ratio | $\text{Area}_t / \text{Area}_{t-1}$; $>1.0$ approaching |
| `objects[].zone` | string | Yes | Corridor lateral placement | `"left"`, `"center"`, or `"right"` |
| `text` | string/null | Yes | Extracted OCR text if in read mode, else `null` | String or `null` |
| `timing_ms` | object | Yes | Pipeline latency breakdown | Requires `fast`, `detect`, `ocr` |
| `timing_ms.fast` | number | Yes | Execution time of fast tier in ms | Non-negative number |
| `timing_ms.detect` | number/null | Yes | Execution time of detector in ms | Number or `null` if skipped |
| `timing_ms.ocr` | number/null | Yes | Execution time of OCR in ms | Number or `null` if skipped |

### 2.4. Example Payload (`examples/observation.example.json`)
```json
{
  "t": 1729180000.12,
  "quality": {
    "blur": 38.2,
    "brightness": 71,
    "stable": false
  },
  "motion": {
    "corridor_divergence": 0.62,
    "ego_motion": 0.4
  },
  "corridor": {
    "edge_density": 0.31,
    "blocked_score": 0.7
  },
  "objects": [
    {
      "cls": "person",
      "conf": 0.88,
      "bbox": [220, 140, 380, 470],
      "growth": 1.35,
      "zone": "center"
    }
  ],
  "text": null,
  "timing_ms": {
    "fast": 21,
    "detect": 74,
    "ocr": null
  }
}
```

---

## 3. Agent-to-Client Action Message

### 3.1. Description
Transmitted from the FastAPI backend to the mobile PWA client over the WebSocket connection. The deterministic agent policy dictates which sensory feedback (speech synthesis, haptic vibration, reframing prompt, confirmation request, or deliberate silence) the client must execute.

### 3.2. Schema Location
`contracts/agent_to_client_action.schema.json`

### 3.3. Field Specifications

| Field | Type | Required | Description | Constraints |
| :--- | :--- | :--- | :--- | :--- |
| `type` | string | Yes | Action category discriminator | `"speak"`, `"request_reframe"`, `"ask_confirmation"`, `"stay_silent"`, `"log_event"` |
| `text` | string | Yes | Speech synthesis utterance or empty string | String |
| `priority` | string | Yes | Action urgency level | `"P0"`, `"P1"`, `"P2"`, or `"P3"` |
| `vibrate` | boolean| Yes | Whether to pulse device haptic actuator | `true` or `false` |
| `direction` | string | No | Suggested camera adjustment direction | `"up"`, `"down"`, `"left"`, `"right"`, `"center"`, `"none"` |
| `request_id`| string | No | Correlation ID linking action to request/frame | String |
| `mode` | string | No | Mode context for the action | `"walk"`, `"read"`, or `"describe"` |
| `confirm_id`| string | No | Unique ID to correlate user approval response | String |
| `reason` | string | No | Machine-readable deterministic rule rationale | For auditing and debugging |

### 3.4. Priority Semantics
- **`P0` (Immediate Hazard):** Immediate auditory warning interrupt and strong haptic pulse. Takes precedence over all current speech synthesis.
- **`P1` (Reframing Directive):** Non-blocking active perception directive (e.g. "Tilt camera up slightly").
- **`P2` (Information / OCR):** Spoken sign readout, confirmation dialogue, or scene description.
- **`P3` (Deliberate Silence / Log):** No audio or haptic output. Telemetry is logged quietly to preserve the pedestrian's auditory awareness.

### 3.5. Example Payload (`examples/action.example.json`)
```json
{
  "type": "speak",
  "text": "Stop. Person ahead, close.",
  "priority": "P0",
  "vibrate": true,
  "reason": "approaching_object_in_corridor"
}
```
