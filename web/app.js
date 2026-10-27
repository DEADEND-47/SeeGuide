/**
 * SeeGuide Client Application (OpenCV AI Competition 2026)
 * Strict implementation of Plan & SRS:
 * - FR-1: 640x480 JPEG frame capture streamed over WebSockets (latest-frame-wins)
 * - FR-10: Human approval confirmation dialog
 * - FR-11: Priority client-side speech queue (P0 interrupts speech) + haptics
 * - FR-13: Web trace viewer reading session timeline
 * - FR-14: Voice commands ("read", "walk", "stop", "what's around me") via Web Speech API
 * - FR-15: Export session trace as JSON
 * - Section 12: First-launch safety notice and "delete my session" endpoint
 */

class SessionManager {
  constructor() {
    this.storageKey = "seeguide_session_id";
    this.sessionId = this.getOrCreateSessionId();
    this.currentMode = "walk"; // "walk", "read", "describe"
    this.seq = 0;
  }

  getOrCreateSessionId() {
    let id = sessionStorage.getItem(this.storageKey);
    if (!id) {
      id = "sess_" + crypto.randomUUID();
      sessionStorage.setItem(this.storageKey, id);
    }
    return id;
  }

  nextSeq() {
    return this.seq++;
  }

  setMode(mode) {
    if (["walk", "read", "describe"].includes(mode)) {
      this.currentMode = mode;
    }
  }
}

class AudioManager {
  constructor() {
    this.synth = window.speechSynthesis;
    this.queue = [];
    this.isSpeaking = false;
    this.lastSpokenText = "";
    this.lastSpokenTime = 0;
  }

  speak(text, priority = "P2") {
    if (!text || text.trim() === "") return;
    const clean = text.trim();

    // Deduplication check: suppress identical speech within 3.0 seconds unless it is P0
    const now = Date.now();
    if (priority !== "P0" && clean === this.lastSpokenText && now - this.lastSpokenTime < 3000) {
      return;
    }

    // CRITICAL: P0 Hazard immediately cancels all current and queued speech (FR-11)
    if (priority === "P0") {
      if (this.synth) {
        this.synth.cancel();
      }
      this.queue = [];
      this.isSpeaking = false;
      this.playEarcon();
      this.enqueue(clean, "P0");
      this.processQueue();
      return;
    }

    this.enqueue(clean, priority);
    this.processQueue();
  }

  playEarcon() {
    // Short audible alert tone for hazards using Web Audio API
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(880, ctx.currentTime); // A5 tone
      osc.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.12);
      gain.gain.setValueAtTime(0.3, ctx.currentTime);
      gain.gain.linearRampToValueAtTime(0.01, ctx.currentTime + 0.12);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.12);
    } catch (e) {
      // AudioContext unavailable or blocked
    }
  }

  enqueue(text, priority) {
    const priorityWeight = { P0: 0, P1: 1, P2: 2, P3: 3 };
    const item = {
      text,
      priority,
      weight: priorityWeight[priority] ?? 2,
      timestamp: Date.now(),
    };

    if (priority === "P0") {
      this.queue.unshift(item);
    } else {
      this.queue.push(item);
      this.queue.sort((a, b) => a.weight - b.weight);
    }
  }

  processQueue() {
    if (this.isSpeaking || this.queue.length === 0 || !this.synth) return;

    const item = this.queue.shift();
    const utterance = new SpeechSynthesisUtterance(item.text);
    utterance.rate = 1.05;
    utterance.pitch = 1.0;

    utterance.onend = () => {
      this.isSpeaking = false;
      this.lastSpokenText = item.text;
      this.lastSpokenTime = Date.now();
      setTimeout(() => this.processQueue(), 80);
    };

    utterance.onerror = (e) => {
      console.warn("Speech synthesis error:", e);
      this.isSpeaking = false;
      this.processQueue();
    };

    this.isSpeaking = true;
    this.synth.speak(utterance);
  }
}

class HapticManager {
  vibrate(priority) {
    if (!("vibrate" in navigator)) return;

    if (priority === "P0") {
      // Urgent double-pulse pattern (FR-11)
      navigator.vibrate([200, 100, 200, 100, 300]);
    } else if (priority === "P1") {
      navigator.vibrate([150]);
    }
  }
}

class CameraManager {
  constructor(videoElement, canvasElement, onFrameReady) {
    this.video = videoElement;
    this.canvas = canvasElement;
    this.ctx = canvasElement.getContext("2d");
    this.onFrameReady = onFrameReady;
    this.captureInterval = null;
    this.isDemoMode = false;
  }

  async startCamera() {
    try {
      const constraints = {
        video: {
          facingMode: { ideal: "environment" },
          width: { ideal: 640 },
          height: { ideal: 480 },
        },
        audio: false,
      };
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      this.video.srcObject = stream;
      await this.video.play();
      this.startCaptureLoop();
      return true;
    } catch (err) {
      console.warn("Camera acquisition failed or restricted:", err);
      return false;
    }
  }

  loadDemoVideo(file) {
    this.stopCaptureLoop();
    if (this.video.srcObject) {
      this.video.srcObject.getTracks().forEach((t) => t.stop());
      this.video.srcObject = null;
    }
    this.video.src = URL.createObjectURL(file);
    this.video.loop = true;
    this.video.muted = true;
    this.video.play().then(() => {
      this.startCaptureLoop();
    });
  }

  startCaptureLoop() {
    this.stopCaptureLoop();
    // FR-1: capture approx 5 fps (200ms)
    this.captureInterval = setInterval(() => {
      if (this.video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
        this.ctx.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);
        const dataUrl = this.canvas.toDataURL("image/jpeg", 0.7);
        const b64 = dataUrl.split(",")[1];
        if (b64 && this.onFrameReady) {
          this.onFrameReady(b64, this.canvas.width, this.canvas.height);
        }
      }
    }, 200);
  }

  stopCaptureLoop() {
    if (this.captureInterval) {
      clearInterval(this.captureInterval);
      this.captureInterval = null;
    }
  }

  stopCamera() {
    this.stopCaptureLoop();
    if (this.video.srcObject) {
      this.video.srcObject.getTracks().forEach((track) => track.stop());
      this.video.srcObject = null;
    }
    this.video.pause();
    this.video.src = "";
  }
}

class WebSocketClient {
  constructor(sessionId, onActionReceived, onStatusChange) {
    this.sessionId = sessionId;
    this.onActionReceived = onActionReceived;
    this.onStatusChange = onStatusChange;
    this.ws = null;
    this.reconnectTimer = null;
    this.connect();
  }

  connect() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host || "127.0.0.1:8000";
    const url = `${protocol}//${host}/ws/${this.sessionId}`;

    if (this.onStatusChange) this.onStatusChange("connecting");

    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      console.log("WebSocket connected to", url);
      if (this.onStatusChange) this.onStatusChange("connected");
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer);
        this.reconnectTimer = null;
      }
    };

    this.ws.onmessage = (event) => {
      try {
        const action = JSON.parse(event.data);
        if (this.onActionReceived) {
          this.onActionReceived(action);
        }
      } catch (err) {
        console.error("Failed to parse incoming action payload:", err);
      }
    };

    this.ws.onclose = () => {
      if (this.onStatusChange) this.onStatusChange("disconnected");
      this.scheduleReconnect();
    };

    this.ws.onerror = (err) => {
      console.warn("WebSocket error:", err);
      this.ws.close();
    };
  }

  scheduleReconnect() {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, 2000);
  }

  sendFrame(frameMessage) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(frameMessage));
    }
  }

  sendMessage(messageObj) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(messageObj));
    }
  }
}

class VoiceCommandManager {
  constructor(onCommand) {
    this.onCommand = onCommand;
    this.recognition = null;
    this.isListening = false;
    this.init();
  }

  init() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      console.log("Web Speech API not supported in this browser. Button fallback active.");
      return;
    }

    this.recognition = new SpeechRecognition();
    this.recognition.continuous = true;
    this.recognition.interimResults = false;
    this.recognition.lang = "en-US";

    this.recognition.onresult = (event) => {
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          const transcript = event.results[i][0].transcript.trim().toLowerCase();
          console.log("Voice command heard:", transcript);
          this.handleTranscript(transcript);
        }
      }
    };

    this.recognition.onerror = (e) => {
      if (e.error !== "no-speech") {
        console.warn("Voice recognition error:", e.error);
      }
    };

    this.recognition.onend = () => {
      if (this.isListening) {
        try {
          this.recognition.start();
        } catch (e) {
          // Restart loop
        }
      }
    };
  }

  handleTranscript(text) {
    // FR-14 voice commands: "read", "walk", "stop", "what's around me"
    if (text.includes("read")) {
      this.onCommand("read");
    } else if (text.includes("walk")) {
      this.onCommand("walk");
    } else if (text.includes("stop")) {
      this.onCommand("stop");
    } else if (text.includes("around") || text.includes("describe") || text.includes("what")) {
      this.onCommand("describe");
    } else if (text.includes("yes") || text.includes("confirm")) {
      this.onCommand("confirm_yes");
    } else if (text.includes("no") || text.includes("cancel") || text.includes("dismiss")) {
      this.onCommand("confirm_no");
    }
  }

  start() {
    if (this.recognition && !this.isListening) {
      this.isListening = true;
      try {
        this.recognition.start();
      } catch (e) {}
    }
  }

  stop() {
    if (this.recognition && this.isListening) {
      this.isListening = false;
      try {
        this.recognition.stop();
      } catch (e) {}
    }
  }
}

class App {
  constructor() {
    this.session = new SessionManager();
    this.audio = new AudioManager();
    this.haptics = new HapticManager();
    this.wakeLock = null;

    // DOM Elements
    this.statusText = document.getElementById("status-text");
    this.connectionStatus = document.getElementById("connection-status");
    this.feedbackPanel = document.getElementById("feedback-panel");
    this.actionPriorityTag = document.getElementById("action-priority-tag");

    this.btnWalk = document.getElementById("btn-mode-walk");
    this.btnRead = document.getElementById("btn-mode-read");
    this.btnDescribe = document.getElementById("btn-mode-describe");

    this.confirmDialog = document.getElementById("confirmation-dialog");
    this.confirmPrompt = document.getElementById("confirm-prompt");
    this.btnConfirmYes = document.getElementById("btn-confirm-yes");
    this.btnConfirmNo = document.getElementById("btn-confirm-no");

    this.btnCameraToggle = document.getElementById("btn-camera-toggle");
    this.btnVoiceToggle = document.getElementById("btn-voice-toggle");
    this.voiceBtnLabel = document.getElementById("voice-btn-label");

    this.safetyModal = document.getElementById("safety-modal");
    this.btnSafetyDismiss = document.getElementById("btn-safety-dismiss");

    this.demoSwitch = document.getElementById("demo-switch");
    this.demoUploadWrapper = document.getElementById("demo-upload-wrapper");
    this.videoFileInput = document.getElementById("video-file-input");
    this.btnSelectVideo = document.getElementById("btn-select-video");

    this.videoEl = document.getElementById("camera-feed");
    this.canvasEl = document.getElementById("capture-canvas");

    this.traceListEl = document.getElementById("trace-list");
    this.traceCountPill = document.getElementById("trace-count-pill");
    this.btnRefreshTraces = document.getElementById("btn-refresh-traces");
    this.btnExportTraces = document.getElementById("btn-export-traces");
    this.btnDeleteSession = document.getElementById("btn-delete-session");

    this.totalEventCount = 0;
    this.activeConfirmId = null;
    this.isCameraRunning = true;
    this.previousFocusedElement = null;

    this.init();
  }

  async init() {
    this.checkSafetyNotice();
    this.bindEvents();
    this.requestWakeLock();

    // Initialize Voice Commands (FR-14)
    this.voice = new VoiceCommandManager((cmd) => this.handleVoiceCommand(cmd));
    this.voice.start();

    // Initialize WebSocket
    this.wsClient = new WebSocketClient(
      this.session.sessionId,
      (action) => this.handleAgentAction(action),
      (status) => this.handleConnectionStatus(status)
    );

    // Initialize Camera (FR-1)
    this.camera = new CameraManager(
      this.videoEl,
      this.canvasEl,
      (b64, width, height) => this.dispatchFrame(b64, width, height)
    );

    const cameraStarted = await this.camera.startCamera();
    if (!cameraStarted) {
      this.isCameraRunning = false;
      if (this.btnCameraToggle) {
        this.btnCameraToggle.textContent = "Start Camera";
      }
      this.updateStatus("Camera unavailable. Toggle Demo Mode to test video.", "P2");
    }
  }

  checkSafetyNotice() {
    // Section 12: Safety notice shown on first launch
    const agreed = localStorage.getItem("seeguide_safety_agreed");
    if (!agreed && this.safetyModal) {
      this.safetyModal.style.display = "flex";
      if (this.btnSafetyDismiss) this.btnSafetyDismiss.focus();
    } else if (this.safetyModal) {
      this.safetyModal.style.display = "none";
    }
  }

  bindEvents() {
    if (this.btnSafetyDismiss) {
      this.btnSafetyDismiss.addEventListener("click", () => {
        localStorage.setItem("seeguide_safety_agreed", "true");
        this.safetyModal.style.display = "none";
      });
    }

    this.btnWalk.addEventListener("click", () => this.switchMode("walk"));
    this.btnRead.addEventListener("click", () => this.switchMode("read"));
    this.btnDescribe.addEventListener("click", () => this.triggerDescribe());

    if (this.btnCameraToggle) {
      this.btnCameraToggle.addEventListener("click", () => this.toggleCamera());
    }

    if (this.btnVoiceToggle) {
      this.btnVoiceToggle.addEventListener("click", () => {
        if (this.voice.isListening) {
          this.voice.stop();
          this.voiceBtnLabel.textContent = "Off";
        } else {
          this.voice.start();
          this.voiceBtnLabel.textContent = "Listening";
        }
      });
    }

    if (this.btnRefreshTraces) {
      this.btnRefreshTraces.addEventListener("click", () => this.fetchTraces());
    }
    if (this.btnExportTraces) {
      this.btnExportTraces.addEventListener("click", () => this.exportTraces());
    }
    if (this.btnDeleteSession) {
      this.btnDeleteSession.addEventListener("click", () => this.deleteSession());
    }

    this.btnConfirmYes.addEventListener("click", () => this.respondConfirmation(true));
    this.btnConfirmNo.addEventListener("click", () => this.respondConfirmation(false));

    // Handle Tab key trapping inside confirmation dialog
    this.confirmDialog.addEventListener("keydown", (e) => {
      if (e.key === "Tab") {
        if (e.shiftKey) {
          if (document.activeElement === this.btnConfirmYes) {
            this.btnConfirmNo.focus();
            e.preventDefault();
          }
        } else {
          if (document.activeElement === this.btnConfirmNo) {
            this.btnConfirmYes.focus();
            e.preventDefault();
          }
        }
      } else if (e.key === "Escape") {
        this.respondConfirmation(false);
      }
    });

    this.demoSwitch.addEventListener("change", (e) => {
      if (e.target.checked) {
        this.demoUploadWrapper.style.display = "block";
        this.updateStatus("Demo mode enabled. Select an evaluation video.", "P2");
      } else {
        this.demoUploadWrapper.style.display = "none";
        this.camera.startCamera();
        this.updateStatus("Resuming live camera stream.", "P2");
      }
    });

    this.btnSelectVideo.addEventListener("click", () => this.videoFileInput.click());
    this.videoFileInput.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (file) {
        this.camera.loadDemoVideo(file);
        this.updateStatus(`Loaded evaluation video: ${file.name}`, "P2");
        this.audio.speak("Evaluation video loaded and streaming.", "P2");
      }
    });

    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") {
        this.requestWakeLock();
      }
    });
  }

  handleVoiceCommand(cmd) {
    if (cmd === "walk" || cmd === "read") {
      this.switchMode(cmd);
    } else if (cmd === "describe") {
      this.triggerDescribe();
    } else if (cmd === "stop") {
      this.wsClient.sendMessage({ type: "command", command: "stop" });
      this.audio.speak("Stopped. Resuming nominal monitoring.", "P2");
    } else if (cmd === "confirm_yes") {
      if (this.confirmDialog.style.display !== "none") {
        this.respondConfirmation(true);
      }
    } else if (cmd === "confirm_no") {
      if (this.confirmDialog.style.display !== "none") {
        this.respondConfirmation(false);
      }
    }
  }

  async toggleCamera() {
    if (this.isCameraRunning) {
      this.camera.stopCamera();
      this.isCameraRunning = false;
      this.btnCameraToggle.textContent = "Resume Camera";
      this.updateStatus("Camera paused. Tap Resume to restart.", "P2");
      this.audio.speak("Camera paused.", "P2");
    } else {
      const started = await this.camera.startCamera();
      if (started) {
        this.isCameraRunning = true;
        this.btnCameraToggle.textContent = "Pause Camera";
        this.updateStatus("Camera active. Monitoring walking corridor.", "P2");
        this.audio.speak("Camera resumed.", "P2");
      } else {
        this.updateStatus("Failed to restart camera.", "P2");
      }
    }
  }

  async requestWakeLock() {
    if ("wakeLock" in navigator) {
      try {
        this.wakeLock = await navigator.wakeLock.request("screen");
      } catch (err) {}
    }
  }

  switchMode(mode) {
    this.session.setMode(mode);
    this.wsClient.sendMessage({
      type: "command",
      command: mode,
    });
    if (mode === "walk") {
      this.btnWalk.classList.add("active");
      this.btnWalk.setAttribute("aria-pressed", "true");
      this.btnRead.classList.remove("active");
      this.btnRead.setAttribute("aria-pressed", "false");
      this.updateStatus("Switched to Walk Mode. Monitoring for obstacles.", "P2");
      this.audio.speak("Walk mode.", "P2");
    } else if (mode === "read") {
      this.btnRead.classList.add("active");
      this.btnRead.setAttribute("aria-pressed", "true");
      this.btnWalk.classList.remove("active");
      this.btnWalk.setAttribute("aria-pressed", "false");
      this.updateStatus("Switched to Read Mode. Point camera at signage.", "P2");
      this.audio.speak("Read mode.", "P2");
    }
  }

  triggerDescribe() {
    this.updateStatus("Requesting scene description...", "P2");
    this.audio.speak("Analyzing scene.", "P2");
    this.wsClient.sendMessage({
      type: "command",
      command: "describe",
    });
    const priorMode = this.session.currentMode;
    this.session.setMode("describe");
    setTimeout(() => {
      this.session.setMode(priorMode);
    }, 1500);
  }

  dispatchFrame(b64, width, height) {
    const frameMessage = {
      type: "frame",
      session_id: this.session.sessionId,
      seq: this.session.nextSeq(),
      ts_client: Date.now() / 1000.0,
      mode: this.session.currentMode,
      image_b64: b64,
      width: width,
      height: height,
      mime: "image/jpeg",
    };
    this.wsClient.sendFrame(frameMessage);
  }

  handleAgentAction(action) {
    if (!action) return;

    if (this.actionPriorityTag && action.priority) {
      const p = action.priority.toUpperCase();
      this.actionPriorityTag.textContent = `${p} ${action.type || "Action"}`;
      this.actionPriorityTag.className = `priority-label ${p.toLowerCase()}`;
    }

    this.appendLiveTrace(action);

    // 1. Auditory Feedback (ignore silent and internal log events)
    if (action.text && action.type !== "stay_silent" && action.type !== "log_event") {
      this.audio.speak(action.text, action.priority);
    }

    // 2. Haptic Feedback
    if (action.vibrate || action.priority === "P0" || action.priority === "P1") {
      this.haptics.vibrate(action.priority);
    }

    // 3. Visual Alert Region
    const hazardEl = document.getElementById("hazard-alert");
    if (action.priority === "P0") {
      this.feedbackPanel.classList.add("hazard");
      if (hazardEl) {
        hazardEl.textContent = action.text || "Warning: Hazard ahead!";
      }
    } else {
      this.feedbackPanel.classList.remove("hazard");
      if (hazardEl) {
        hazardEl.textContent = "";
      }
    }

    // 4. Human-in-the-Loop Approval (FR-10)
    if (action.type === "ask_confirmation") {
      this.showConfirmation(action.text, action.confirm_id);
    } else if (action.text && action.type !== "stay_silent" && action.type !== "log_event") {
      this.updateStatus(action.text, action.priority);
    }
  }

  showConfirmation(prompt, confirmId) {
    this.previousFocusedElement = document.activeElement;
    this.activeConfirmId = confirmId;
    this.confirmPrompt.textContent = prompt || "Read the sign aloud?";
    this.confirmDialog.style.display = "flex";
    this.btnConfirmYes.focus();
  }

  respondConfirmation(approved) {
    this.confirmDialog.style.display = "none";
    const answer = approved ? "yes" : "no";
    this.wsClient.sendMessage({
      type: "response",
      confirm_id: this.activeConfirmId || "confirm_read",
      answer: answer,
    });
    this.audio.speak(`Confirmed ${approved ? "Yes" : "No"}.`, "P2");
    this.activeConfirmId = null;
    if (this.previousFocusedElement && typeof this.previousFocusedElement.focus === "function") {
      this.previousFocusedElement.focus();
    }
  }

  updateStatus(message, priority) {
    this.statusText.textContent = message;
  }

  appendLiveTrace(action) {
    if (!this.traceListEl) return;
    const placeholder = this.traceListEl.querySelector(".trace-empty");
    if (placeholder) {
      placeholder.remove();
    }
    this.totalEventCount++;
    if (this.traceCountPill) {
      this.traceCountPill.textContent = `${this.totalEventCount} records`;
    }

    const row = document.createElement("div");
    const pClass = (action.priority || "").toLowerCase();
    row.className = `trace-row ${pClass}`;
    const timeStr = new Date().toLocaleTimeString();
    const actionDesc = action.type === "stay_silent" ? `stay_silent (${action.reason || "nominal"})` : `${action.type}: "${action.text || ""}"`;
    row.innerHTML = `<span style="color: #aeaeb2; font-size: 0.75rem;">${timeStr} | ${action.priority || "P3"} | ${action.mode || "walk"}</span><strong>${actionDesc}</strong>`;
    this.traceListEl.prepend(row);
    while (this.traceListEl.children.length > 25) {
      this.traceListEl.removeChild(this.traceListEl.lastChild);
    }
  }

  async fetchTraces() {
    try {
      const res = await fetch(`/traces/${this.session.sessionId}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (!this.traceListEl) return;
      this.traceListEl.innerHTML = "";
      if (!data.traces || data.traces.length === 0) {
        this.traceListEl.innerHTML = '<div class="trace-empty">No stored traces found for this session.</div>';
        return;
      }
      data.traces.forEach((t) => {
        const row = document.createElement("div");
        const act = t.action || {};
        const pClass = (act.priority || "").toLowerCase();
        row.className = `trace-row ${pClass}`;
        const timeStr = new Date(t.timestamp || Date.now()).toLocaleTimeString();
        row.innerHTML = `<span style="color: #aeaeb2; font-size: 0.75rem;">${timeStr} | ${act.priority || "P3"}</span><strong>${act.type || "action"}: ${act.text || act.reason || ""}</strong>`;
        this.traceListEl.appendChild(row);
      });
      this.updateStatus(`Loaded ${data.traces.length} trace records.`, "P2");
    } catch (err) {
      console.warn("Failed to fetch traces:", err);
      this.updateStatus("Failed to fetch session traces from server.", "P2");
    }
  }

  async exportTraces() {
    try {
      const res = await fetch(`/traces/${this.session.sessionId}`);
      const data = await res.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `seeguide_trace_${this.session.sessionId}.json`;
      a.click();
      URL.revokeObjectURL(url);
      this.updateStatus("Exported session trace JSON.", "P2");
    } catch (err) {
      console.warn("Failed to export traces:", err);
    }
  }

  async deleteSession() {
    if (!confirm("Permanently delete all stored traces for this session?")) {
      return;
    }
    try {
      const res = await fetch(`/session/${this.session.sessionId}`, { method: "DELETE" });
      if (res.ok) {
        if (this.traceListEl) {
          this.traceListEl.innerHTML = '<div class="trace-empty">Session data purged from server.</div>';
        }
        this.updateStatus("Session data permanently deleted from server.", "P2");
        this.audio.speak("Session data deleted.", "P2");
      }
    } catch (err) {
      console.warn("Failed to delete session:", err);
    }
  }

  handleConnectionStatus(status) {
    if (status === "connected") {
      this.connectionStatus.querySelector(".status-text").textContent = "Connected";
      this.connectionStatus.className = "status-indicator connected";
    } else if (status === "connecting") {
      this.connectionStatus.querySelector(".status-text").textContent = "Connecting";
      this.connectionStatus.className = "status-indicator";
    } else {
      this.connectionStatus.querySelector(".status-text").textContent = "Offline";
      this.connectionStatus.className = "status-indicator";
    }
  }
}

window.addEventListener("DOMContentLoaded", () => {
  window.seeGuideApp = new App();
});
