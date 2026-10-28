"use strict";

const canvas = document.getElementById("screen");
const ctx = canvas.getContext("2d", { alpha: false });
const statusEl = document.getElementById("status");
const statsEl = document.getElementById("stats");
const muteBtn = document.getElementById("mute");

let ws = null;
let decoder = null;
let configured = false;
let audioCtx = null;
let muted = true;
let firstAudioTs = null;
let audioBaseTime = 0;
let dragging = false;
let moved = false;
let dragStart = null;
let lastMoveSent = 0;
let videoFrames = 0;
let lastStats = 0;

function setStatus(text) {
  statusEl.textContent = text;
}

function connect() {
  const host = location.hostname || "localhost";
  ws = new WebSocket(`ws://${host}:8081`);
  ws.binaryType = "arraybuffer";

  ws.onopen = () => setStatus("connected, waiting for stream…");
  ws.onclose = () => {
    configured = false;
    setStatus("disconnected, retrying…");
    setTimeout(connect, 2000);
  };
  ws.onerror = () => setStatus("websocket error");
  ws.onmessage = (event) => {
    if (typeof event.data === "string") {
      let message;
      try { message = JSON.parse(event.data); } catch { return; }
      handleJson(message);
    } else {
      handleBinary(event.data);
    }
  };
}

function handleJson(message) {
  if (message.type === "hello") {
    configureVideo(message);
    setStatus(`stream ${message.width}x${message.height} @ ${message.fps} fps`);
  } else if (message.type === "reset") {
    configured = false;
    if (decoder) {
      try { decoder.close(); } catch {}
      decoder = null;
    }
    firstAudioTs = null;
    setStatus("AA session reset, waiting for stream…");
  }
}

function configureVideo(message) {
  configured = false;
  if (decoder) {
    try { decoder.close(); } catch {}
    decoder = null;
  }
  if (!message.description) {
    setStatus("no avcC description from server");
    return;
  }

  const description = Uint8Array.from(atob(message.description), (c) => c.charCodeAt(0));
  try {
    decoder = new VideoDecoder({
      output: (frame) => {
        ctx.drawImage(frame, 0, 0, canvas.width, canvas.height);
        frame.close();
        videoFrames++;
      },
      error: (error) => setStatus(`video decoder error: ${error.message || error}`),
    });
    decoder.configure({
      codec: message.codec,
      description,
      codedWidth: message.width,
      codedHeight: message.height,
      optimizeForLatency: true,
    });
    configured = true;
  } catch (error) {
    setStatus(`VideoDecoder configure failed: ${error.message || error}`);
  }
}

function handleBinary(buffer) {
  const view = new DataView(buffer);
  if (view.byteLength < 9) return;
  const type = view.getUint8(0);
  const timestamp = Number(view.getBigUint64(1, false));
  const payload = new Uint8Array(buffer, 9);

  if (type === 1 || type === 3) {
    if (!configured || !decoder) return;
    const key = type === 1;
    if (!key && decoder.decodeQueueSize > 12) return;
    try {
      decoder.decode(new EncodedVideoChunk({
        type: key ? "key" : "delta",
        timestamp,
        data: payload,
      }));
    } catch (error) {
      setStatus(`decode failed: ${error.message || error}`);
    }
  } else if (type === 2) {
    playAudio(timestamp, payload);
  }

  const now = performance.now();
  if (now - lastStats > 1000) {
    lastStats = now;
    statsEl.textContent = `frames ${videoFrames} · audio ${audioCtx ? "on" : "off"}`;
  }
}

function ensureAudio() {
  if (audioCtx) return audioCtx;
  try {
    audioCtx = new AudioContext({ sampleRate: 48000, latencyHint: "interactive" });
    audioCtx.resume();
  } catch (error) {
    setStatus(`AudioContext failed: ${error.message || error}`);
    audioCtx = null;
  }
  return audioCtx;
}

function playAudio(timestamp, payload) {
  if (muted || !audioCtx) return;
  if (audioCtx.state === "suspended") audioCtx.resume();

  const samples = Math.floor(payload.byteLength / 4);
  if (samples <= 0) return;

  if (firstAudioTs === null) {
    firstAudioTs = timestamp;
    audioBaseTime = audioCtx.currentTime + 0.15;
  }

  const when = audioBaseTime + (timestamp - firstAudioTs) / 1_000_000;
  if (when < audioCtx.currentTime - 0.2) return; // too late, drop
  if (when > audioCtx.currentTime + 2.0) {
    // Re-anchor if the stream jumped.
    firstAudioTs = timestamp;
    audioBaseTime = audioCtx.currentTime + 0.15;
  }

  const buffer = audioCtx.createBuffer(2, samples, 48000);
  const left = buffer.getChannelData(0);
  const right = buffer.getChannelData(1);
  const view = new DataView(payload.buffer, payload.byteOffset, payload.byteLength);
  for (let i = 0; i < samples; i++) {
    left[i] = view.getInt16(i * 4, true) / 32768;
    right[i] = view.getInt16(i * 4 + 2, true) / 32768;
  }

  const source = audioCtx.createBufferSource();
  source.buffer = buffer;
  source.connect(audioCtx.destination);
  source.start(Math.max(when, audioCtx.currentTime + 0.01));
}

function pointFromEvent(event) {
  const rect = canvas.getBoundingClientRect();
  const x = Math.round(((event.clientX - rect.left) / rect.width) * canvas.width);
  const y = Math.round(((event.clientY - rect.top) / rect.height) * canvas.height);
  return {
    x: Math.max(0, Math.min(canvas.width - 1, x)),
    y: Math.max(0, Math.min(canvas.height - 1, y)),
  };
}

function sendInput(type, point) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ type, x: point.x, y: point.y }));
}

canvas.addEventListener("pointerdown", (event) => {
  canvas.setPointerCapture(event.pointerId);
  dragStart = pointFromEvent(event);
  moved = false;
  dragging = true;
  lastMoveSent = 0;
});

canvas.addEventListener("pointermove", (event) => {
  if (!dragging || !dragStart) return;
  const point = pointFromEvent(event);
  const dx = point.x - dragStart.x;
  const dy = point.y - dragStart.y;
  if (!moved && Math.hypot(dx, dy) > 8) {
    moved = true;
    sendInput("down", dragStart);
  }
  if (moved) {
    const now = performance.now();
    if (now - lastMoveSent > 50) {
      lastMoveSent = now;
      sendInput("move", point);
    }
  }
});

canvas.addEventListener("pointerup", (event) => {
  if (!dragging) return;
  const point = pointFromEvent(event);
  dragging = false;
  if (moved) {
    sendInput("up", point);
  } else {
    sendInput("tap", point);
  }
  dragStart = null;
});

canvas.addEventListener("pointercancel", () => {
  if (!dragging) return;
  dragging = false;
  if (moved && dragStart) sendInput("up", dragStart);
  dragStart = null;
});

function setMuted(value) {
  muted = value;
  muteBtn.textContent = muted ? "🔇" : "🔊";
  muteBtn.title = muted ? "Audio muted" : "Audio on";
  muteBtn.setAttribute("aria-label", muted ? "Audio muted" : "Audio on");

  if (muted) {
    if (audioCtx) audioCtx.suspend();
  } else {
    ensureAudio();
    if (audioCtx) {
      audioCtx.resume();
      firstAudioTs = null;
      audioBaseTime = audioCtx.currentTime + 0.15;
    }
  }
}

muteBtn.addEventListener("click", () => setMuted(!muted));
setMuted(true);

connect();
