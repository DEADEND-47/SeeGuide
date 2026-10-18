/**
 * SeeGuide Mobile PWA Application
 * Privacy-first phone-camera assistant for blind and low-vision pedestrians.
 * Implements camera streaming, frame telemetry, priority speech synthesis,
 * haptics, and active perception confirmation handling.
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
  }

  speak(text, priority = "P2") {
    if (!text || text.trim() === "") return;

    // CRITICAL: P0 Hazard immediately cancels all current and queued speech
    if (priority === "P0") {
      if (this.synth) {
        this.synth.cancel();
      }
      this.queue = [];
      this.isSpeaking = false;

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.15; // Slightly faster for emergency hazard
      utterance.pitch = 1.1;
      utterance.volume = 1.0;

      if (this.synth) {
        this.synth.speak(utterance);
      }
      return;
    }

    // Lower priority speech (P1, P2, P3) queued normally
    this.queue.push({ text, priority });
    this.processQueue();
  }

  processQueue() {
    if (this.isSpeaking || this.queue.length === 0 || !this.synth) return;

    const item = this.queue.shift();
    const utterance = new SpeechSynthesisUtterance(item.text);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;

    utterance.onend = () => {
      this.isSpeaking = false;
      this.processQueue();
    };

    utterance.onerror = () => {
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
      // Urgent double-pulse pattern
      navigator.vibrate([200, 100, 200, 100, 300]);
    } else if (priority === "P1") {
      // Single attention pulse
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
    this.video.play();
    this.isDemoMode = true;
    this.startCaptureLoop();
  }

  startCaptureLoop() {
    this.stopCaptureLoop();
    // Throttle capture to ~5 fps (200ms per frame) to prevent client/network congestion
    this.captureInterval = setInterval(() => {
      if (this.video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
        this.ctx.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);
        const dataUrl = this.canvas.toDataURL("image/jpeg", 0.7);
        // Strip data:image/jpeg;base64, prefix
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
    if (!this.reconnectTimer) {
      this.reconnectTimer = setTimeout(() => {
        this.reconnectTimer = null;
        this.connect();
      }, 2000);
    }
  }

  sendFrame(frameMessage) {
    // Latest-frame-wins client rule: drop if socket buffer is backlogged
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      if (this.ws.bufferedAmount === 0) {
        this.ws.send(JSON.stringify(frameMessage));
      }
    }
  }

  sendMessage(message) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
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
    this.btnWalk = document.getElementById("btn-mode-walk");
    this.btnRead = document.getElementById("btn-mode-read");
    this.btnDescribe = document.getElementById("btn-mode-describe");
    this.confirmDialog = document.getElementById("confirmation-dialog");
    this.confirmPrompt = document.getElementById("confirm-prompt");
    this.btnConfirmYes = document.getElementById("btn-confirm-yes");
    this.btnConfirmNo = document.getElementById("btn-confirm-no");
    this.demoSwitch = document.getElementById("demo-switch");
    this.demoUploadWrapper = document.getElementById("demo-upload-wrapper");
    this.videoFileInput = document.getElementById("video-file-input");
    this.btnSelectVideo = document.getElementById("btn-select-video");

    this.videoEl = document.getElementById("camera-feed");
    this.canvasEl = document.getElementById("capture-canvas");

    this.activeConfirmId = null;

    this.init();
  }

  async init() {
    this.bindEvents();
    this.requestWakeLock();

    // Initialize WebSocket
    this.wsClient = new WebSocketClient(
      this.session.sessionId,
      (action) => this.handleAgentAction(action),
      (status) => this.handleConnectionStatus(status)
    );

    // Initialize Camera
    this.camera = new CameraManager(
      this.videoEl,
      this.canvasEl,
      (b64, width, height) => this.dispatchFrame(b64, width, height)
    );

    const cameraStarted = await this.camera.startCamera();
    if (!cameraStarted) {
      this.updateStatus("Camera unavailable. Toggle Demo Mode to test video.", "P2");
    }
  }

  bindEvents() {
    this.btnWalk.addEventListener("click", () => this.switchMode("walk"));
    this.btnRead.addEventListener("click", () => this.switchMode("read"));
    this.btnDescribe.addEventListener("click", () => this.triggerDescribe());

    this.btnConfirmYes.addEventListener("click", () => this.respondConfirmation(true));
    this.btnConfirmNo.addEventListener("click", () => this.respondConfirmation(false));

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

    // Re-acquire wake lock on visibility change
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") {
        this.requestWakeLock();
      }
    });
  }

  async requestWakeLock() {
    if ("wakeLock" in navigator) {
      try {
        this.wakeLock = await navigator.wakeLock.request("screen");
      } catch (err) {
        console.warn("Screen Wake Lock request failed:", err);
      }
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
      this.updateStatus("Switched to Read Mode. Point camera at signage or text.", "P2");
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
    // Send immediate describe trigger frame with describe mode
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

    // 1. Auditory Feedback (ignore silent and internal log events)
    if (action.text && action.type !== "stay_silent" && action.type !== "log_event") {
      this.audio.speak(action.text, action.priority);
    }

    // 2. Haptic Feedback
    if (action.vibrate || action.priority === "P0" || action.priority === "P1") {
      this.haptics.vibrate(action.priority);
    }

    // 3. Visual UI Updates
    if (action.priority === "P0") {
      this.feedbackPanel.classList.add("hazard");
    } else {
      this.feedbackPanel.classList.remove("hazard");
    }

    if (action.type === "ask_confirmation") {
      this.showConfirmation(action.text, action.confirm_id);
    } else if (action.text && action.type !== "stay_silent" && action.type !== "log_event") {
      this.updateStatus(action.text, action.priority);
    }
  }

  showConfirmation(prompt, confirmId) {
    this.activeConfirmId = confirmId;
    this.confirmPrompt.textContent = prompt;
    this.confirmDialog.style.display = "block";
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
  }

  updateStatus(message, priority) {
    this.statusText.textContent = message;
  }

  handleConnectionStatus(status) {
    if (status === "connected") {
      this.connectionStatus.textContent = "Connected to SeeGuide Backend";
      this.connectionStatus.className = "status-badge connected";
    } else if (status === "connecting") {
      this.connectionStatus.textContent = "Connecting to server...";
      this.connectionStatus.className = "status-badge disconnected";
    } else {
      this.connectionStatus.textContent = "Disconnected (Reconnecting...)";
      this.connectionStatus.className = "status-badge disconnected";
    }
  }
}

// Instantiate application on DOMContentLoaded
window.addEventListener("DOMContentLoaded", () => {
  window.seeGuideApp = new App();
});
