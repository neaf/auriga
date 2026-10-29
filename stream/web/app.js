"use strict";

const canvas = document.getElementById("screen");
const ctx = canvas.getContext("2d", { alpha: false });
const statusEl = document.getElementById("status");
const statsEl = document.getElementById("stats");
const muteBtn = document.getElementById("mute");

const WS_PORT = 8081;
const REPLACED_CODE = 4001;      // close code: another tab took the stream
const GAP_US = 250000;           // a jump this large means frames were dropped
const MAX_QUEUE = 2400;          // hard cap on chunks pending in the decoder

let ws = null;
let decoder = null;
let configured = false;
let needKey = true;              // drop deltas until the next keyframe
let keyframePending = false;
let replaced = false;
let audioCtx = null;
let muted = true;
let firstAudioTs = null;
let audioBaseTime = 0;
let lastVideoTs = null;
let dragging = false;
let moved = false;
let dragStart = null;
let lastPoint = null;
let lastMoveSent = 0;
let videoFrames = 0;
let droppedFrames = 0;
let lastStats = 0;

function setStatus(text) {
  statusEl.textContent = text;
}

function connect() {
  if (replaced) return;
  closeSocket();
  const host = location.hostname || "localhost";
  const socket = new WebSocket(`ws://${host}:${WS_PORT}`);
  ws = socket;
  socket.binaryType = "arraybuffer";

  socket.onopen = () => setStatus("connected, waiting for stream…");
  socket.onclose = (event) => {
    configured = false;
    keyframePending = false;
    teardownDecoder();
    if (event.code === REPLACED_CODE) {
      replaced = true;
      setStatus("another tab took over this stream");
      return;
    }
    setStatus("disconnected, retrying…");
    setTimeout(connect, 2000);
  };
  socket.onerror = () => setStatus("websocket error");
  socket.onmessage = (event) => {
    if (typeof event.data === "string") {
      let message;
      try { message = JSON.parse(event.data); } catch { return; }
      handleJson(message);
    } else {
      handleBinary(event.data);
    }
  };
}

// The server keeps one viewer; a second socket for this page would take the
// stream from itself, so an old socket is always closed first.
function closeSocket() {
  if (!ws) return;
  const old = ws;
  ws = null;
  old.onclose = null;
  old.onmessage = null;
  try { old.close(); } catch {}
}

function handleJson(message) {
  if (message.type === "hello") {
    configureVideo(message);
    setStatus(`stream ${message.width}x${message.height} @ ${message.fps} fps`);
  } else if (message.type === "reset") {
    keyframePending = false;
    needKey = true;
    lastVideoTs = null;
    teardownDecoder();
    firstAudioTs = null;
    videoFrames = 0;
    droppedFrames = 0;
    setStatus("AA session reset, waiting for stream…");
  } else if (message.type === "status") {
    setStatus(message.text);
  }
}

function applyGeometry(width, height) {
  const w = Math.round(Number(width)) || canvas.width || 1280;
  const h = Math.round(Number(height)) || canvas.height || 720;
  if (canvas.width !== w) canvas.width = w;
  if (canvas.height !== h) canvas.height = h;
  canvas.style.aspectRatio = `${w} / ${h}`;
}

function teardownDecoder() {
  configured = false;
  if (!decoder) return;
  try { decoder.close(); } catch {}
  decoder = null;
}

function configureVideo(message) {
  teardownDecoder();
  keyframePending = false;
  needKey = true;
  lastVideoTs = null;
  if (!message.description) {
    setStatus("no avcC description from server");
    return;
  }

  applyGeometry(message.width, message.height);
  const description = Uint8Array.from(atob(message.description), (c) => c.charCodeAt(0));
  try {
    decoder = new VideoDecoder({
      output: (frame) => {
        draw(frame);
      },
      error: (error) => {
        setStatus(`video decoder error: ${error.message || error}`);
        requestKeyframe();
      },
    });
    decoder.configure({
      codec: message.codec,
      description,
      codedWidth: canvas.width,
      codedHeight: canvas.height,
      optimizeForLatency: true,
    });
    configured = true;
  } catch (error) {
    setStatus(`VideoDecoder configure failed: ${error.message || error}`);
  }
}

function draw(frame) {
  // The decoded frame is authoritative: the manifest geometry can lag the SPS.
  if (frame.displayWidth && frame.displayHeight &&
      (canvas.width !== frame.displayWidth || canvas.height !== frame.displayHeight)) {
    applyGeometry(frame.displayWidth, frame.displayHeight);
  }
  ctx.drawImage(frame, 0, 0, canvas.width, canvas.height);
  frame.close();
  videoFrames++;
}

// The server replays its cached GOP from the last keyframe, so this is cheap
// and always decodable (`docs/Stream protocol.md`, keyframe request).
function requestKeyframe() {
  if (replaced || keyframePending) return;
  teardownDecoder();
  needKey = true;
  lastVideoTs = null;
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  keyframePending = true;
  try { ws.send(JSON.stringify({ type: "keyframe" })); } catch {}
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
    if (key) {
      needKey = false;
    } else if (needKey) {
      return;
    } else if (lastVideoTs !== null && timestamp - lastVideoTs > GAP_US) {
      droppedFrames++;
      requestKeyframe();
      return;
    }
    if (decoder.decodeQueueSize > MAX_QUEUE) {
      needKey = true;
      return;
    }
    lastVideoTs = timestamp;
    try {
      decoder.decode(new EncodedVideoChunk({
        type: key ? "key" : "delta",
        timestamp,
        data: payload,
      }));
    } catch (error) {
      setStatus(`decode failed: ${error.message || error}`);
      requestKeyframe();
    }
  } else if (type === 2) {
    playAudio(timestamp, payload);
  }

  const now = performance.now();
  if (now - lastStats > 1000) {
    lastStats = now;
    statsEl.textContent = `frames ${videoFrames} · dropped ${droppedFrames}` +
      ` · audio ${audioCtx ? "on" : "off"}`;
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

  // A backward jump means a new server run or a new content clock: re-anchor
  // instead of dropping every chunk as "too late" (`docs/Stream protocol.md`).
  if (firstAudioTs === null || timestamp < firstAudioTs) {
    firstAudioTs = timestamp;
    audioBaseTime = audioCtx.currentTime + 0.15;
  }

  let when = audioBaseTime + (timestamp - firstAudioTs) / 1_000_000;
  if (when < audioCtx.currentTime - 0.2) return; // too late, drop
  if (when > audioCtx.currentTime + 1.0) {
    // Backlog ahead of the clock: re-anchor and recompute `when`, otherwise
    // this chunk plays at the old future time over the following audio.
    firstAudioTs = timestamp;
    audioBaseTime = audioCtx.currentTime + 0.15;
    when = audioBaseTime;
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
  lastPoint = dragStart;
  moved = false;
  dragging = true;
  lastMoveSent = 0;
});

canvas.addEventListener("pointermove", (event) => {
  if (!dragging || !dragStart) return;
  const point = pointFromEvent(event);
  lastPoint = point;
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
  lastPoint = null;
});

canvas.addEventListener("pointercancel", () => {
  if (!dragging) return;
  dragging = false;
  if (moved) sendInput("up", lastPoint || dragStart);
  dragStart = null;
  lastPoint = null;
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
