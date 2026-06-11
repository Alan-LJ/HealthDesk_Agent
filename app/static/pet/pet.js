const workspace = document.querySelector("#workspace");
const scene = document.querySelector(".scene");
const pet = document.querySelector("#pet");
const petCanvas = document.querySelector("#petCanvas");
const petSpeech = document.querySelector("#petSpeech");
const heartLayer = document.querySelector("#heartLayer");
const scenario = document.querySelector("#scenario");
const tickButton = document.querySelector("#tick");
const messageForm = document.querySelector("#messageForm");
const messageInput = document.querySelector("#messageInput");
const sendButton = document.querySelector("#sendMessage");
const refreshStateButton = document.querySelector("#refreshState");
const taskPreview = document.querySelector("#taskPreview");
const statusLine = document.querySelector("#statusLine");
const stateMetrics = document.querySelector("#stateMetrics");
const summary = document.querySelector("#summary");
const confidence = document.querySelector("#confidence");
const recommendations = document.querySelector("#recommendations");
const traceId = document.querySelector("#traceId");
const traceList = document.querySelector("#traceList");

const petClasses = ["idle", "stretch", "drink_water", "adjust_environment", "check_device", "concerned", "calm", "high", "medium", "low"];
const defaultTask = "\u5206\u6790\u6211\u5f53\u524d\u529e\u516c\u5065\u5eb7\u72b6\u6001\uff0c\u5e76\u751f\u6210\u684c\u5ba0\u63d0\u9192";
const heartColors = ["#ff4d6d", "#ff6b8a", "#ff85a1", "#ff3366", "#ff80ab", "#f06292", "#e91e63"];
const petSpriteSize = 220;
const petSprites = {
  normal: null,
  excited: null,
};

let dragging = null;
let reactionTimer = null;
let lastReactionAt = 0;
let petSpriteReady = false;
let activePetState = "normal";

initPetPosition();
initPetSprite();
loadState();

tickButton.addEventListener("click", async () => {
  await createTick();
});

messageForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await runAgent();
});

refreshStateButton.addEventListener("click", async () => {
  await loadState();
});

pet.addEventListener("pointerdown", startDrag);
pet.addEventListener("click", () => {
  triggerPetReaction();
});
window.addEventListener("resize", clampPetPosition);

async function createTick() {
  setBusy("生成模拟状态...");
  try {
    await postJson(`/simulation/scenario/${encodeURIComponent(scenario.value)}`, {});
    const tick = await postJson("/simulation/tick", {});
    renderState(tick.state);
    setReady(`状态已更新: ${tick.scenario}`);
    petSpeech.textContent = "状态已刷新，可以运行真实 Agent。";
  } catch (error) {
    setError(error.message);
  }
}

async function runAgent() {
  const userTask = messageInput.value.trim() || defaultTask;
  messageInput.value = userTask;
  taskPreview.textContent = userTask;
  setBusy("真实 Agent 运行中...");
  setPetClass({ animation: "idle", emotion: "calm", priority: "low" });
  try {
    const result = await postJson("/agent/run", {
      task: userTask,
      user_id: "default",
    });
    renderAgentResult(result);
    if (result.trace_id) {
      await loadTrace(result.trace_id);
    }
    setReady(`完成: ${result.stop_reason || "ok"}`);
  } catch (error) {
    setError(error.message);
    petSpeech.textContent = "真实 Agent 没有完成，请检查 DeepSeek 配置或服务日志。";
  }
}

async function loadState() {
  try {
    const state = await getJson("/state/current");
    renderState(state);
  } catch (_error) {
    renderEmptyState();
  }
}

async function loadTrace(id) {
  try {
    const trace = await getJson(`/traces/${encodeURIComponent(id)}`);
    renderTrace(trace);
  } catch (error) {
    traceList.innerHTML = `<div class="trace-item"><span class="trace-index">!</span><div class="trace-body"><strong>Trace</strong><span>${escapeHtml(error.message)}</span></div></div>`;
  }
}

function renderAgentResult(result) {
  const output = result.final_output || {};
  const petAction = output.pet_action || {};
  summary.textContent = output.health_summary || result.message || "Agent 已返回结构化结果。";
  confidence.textContent = typeof output.confidence === "number" ? `confidence ${output.confidence.toFixed(2)}` : "-";
  traceId.textContent = result.trace_id || output.trace_id || "-";
  petSpeech.textContent = petAction.message || compactSpeech(output.health_summary) || "真实 Agent 已完成。";
  setPetClass(petAction);
  renderRecommendations(output.recommendations || []);
}

function renderRecommendations(items) {
  if (!items.length) {
    recommendations.innerHTML = "";
    return;
  }
  recommendations.innerHTML = items
    .map((item) => {
      const level = item.risk_level || "low";
      return `
        <div class="recommendation ${escapeHtml(level)}">
          <strong>${escapeHtml(item.category || "recommendation")} · ${escapeHtml(level)}</strong>
          <p>${escapeHtml(item.suggested_action || item.reason || "")}</p>
        </div>
      `;
    })
    .join("");
}

function renderState(state) {
  stateMetrics.innerHTML = `
    <div><span>久坐</span><strong>${escapeHtml(String(state.sedentary_minutes ?? "-"))} min</strong></div>
    <div><span>饮水</span><strong>${escapeHtml(String(state.drink_today_ml ?? "-"))} ml</strong></div>
    <div><span>温度</span><strong>${escapeHtml(String(state.temperature_c ?? "-"))} °C</strong></div>
    <div><span>设备</span><strong>${formatConfidence(state.device_confidence)}</strong></div>
  `;
}

function renderEmptyState() {
  stateMetrics.innerHTML = `
    <div><span>久坐</span><strong>-</strong></div>
    <div><span>饮水</span><strong>-</strong></div>
    <div><span>温度</span><strong>-</strong></div>
    <div><span>设备</span><strong>-</strong></div>
  `;
}

function renderTrace(trace) {
  traceId.textContent = trace.trace_id || "-";
  const steps = trace.steps || [];
  if (!steps.length) {
    traceList.innerHTML = "";
    return;
  }
  traceList.innerHTML = steps
    .map((step, index) => {
      const title = [step.node_name, step.action_type, step.tool_name].filter(Boolean).join(" · ");
      const detail = step.observation_summary || step.stop_reason || "";
      return `
        <div class="trace-item">
          <span class="trace-index">${index + 1}</span>
          <div class="trace-body">
            <strong>${escapeHtml(title)}</strong>
            <span>${escapeHtml(detail)}</span>
          </div>
        </div>
      `;
    })
    .join("");
}

function setPetClass(action) {
  petClasses.forEach((name) => pet.classList.remove(name));
  pet.classList.add(action.animation || "idle");
  pet.classList.add(action.emotion || "calm");
  pet.classList.add(action.priority || "low");
  setPetSpriteState(action.animation === "drink_water" || action.emotion === "excited" ? "excited" : "normal");
}

function setBusy(text) {
  tickButton.disabled = true;
  sendButton.disabled = true;
  messageInput.disabled = true;
  refreshStateButton.disabled = true;
  statusLine.className = "status-line busy";
  statusLine.textContent = text;
}

function setReady(text) {
  tickButton.disabled = false;
  sendButton.disabled = false;
  messageInput.disabled = false;
  refreshStateButton.disabled = false;
  statusLine.className = "status-line";
  statusLine.textContent = text;
}

function setError(text) {
  tickButton.disabled = false;
  sendButton.disabled = false;
  messageInput.disabled = false;
  refreshStateButton.disabled = false;
  statusLine.className = "status-line error";
  statusLine.textContent = text;
}

async function getJson(url) {
  const response = await fetch(url);
  return readJsonResponse(response);
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJsonResponse(response);
}

async function readJsonResponse(response) {
  const text = await response.text();
  let data = {};
  if (text) {
    try {
      data = JSON.parse(text);
    } catch (_error) {
      data = { detail: text };
    }
  }
  if (!response.ok) {
    throw new Error(data.detail || `HTTP ${response.status}`);
  }
  return data;
}

function startDrag(event) {
  const rect = pet.getBoundingClientRect();
  dragging = {
    offsetX: event.clientX - rect.left,
    offsetY: event.clientY - rect.top,
    startX: event.clientX,
    startY: event.clientY,
    moved: false,
  };
  pet.classList.add("dragging");
  pet.setPointerCapture(event.pointerId);
  pet.addEventListener("pointermove", moveDrag);
  pet.addEventListener("pointerup", stopDrag, { once: true });
  pet.addEventListener("pointercancel", stopDrag, { once: true });
}

function moveDrag(event) {
  if (!dragging) {
    return;
  }
  const bounds = scene.getBoundingClientRect();
  const width = pet.offsetWidth;
  const height = pet.offsetHeight;
  const nextLeft = event.clientX - bounds.left - dragging.offsetX;
  const nextTop = event.clientY - bounds.top - dragging.offsetY;
  if (Math.hypot(event.clientX - dragging.startX, event.clientY - dragging.startY) > 3) {
    dragging.moved = true;
  }
  setPetPosition(clamp(nextLeft, 8, bounds.width - width - 8), clamp(nextTop, 8, bounds.height - height - 8));
}

function stopDrag(event) {
  const wasClick = dragging && !dragging.moved && event.type !== "pointercancel";
  dragging = null;
  pet.classList.remove("dragging");
  pet.removeEventListener("pointermove", moveDrag);
  localStorage.setItem("healthdesk.pet.position", JSON.stringify({ left: pet.style.left, top: pet.style.top }));
  if (wasClick) {
    triggerPetReaction();
  }
}

function initPetPosition() {
  const saved = localStorage.getItem("healthdesk.pet.position");
  if (!saved) {
    return;
  }
  try {
    const position = JSON.parse(saved);
    if (position.left && position.top) {
      pet.style.left = position.left;
      pet.style.top = position.top;
    }
  } catch (_error) {
    localStorage.removeItem("healthdesk.pet.position");
  }
  requestAnimationFrame(clampPetPosition);
}

function clampPetPosition() {
  const bounds = scene.getBoundingClientRect();
  const left = parseFloat(pet.style.left || `${pet.offsetLeft}`);
  const top = parseFloat(pet.style.top || `${pet.offsetTop}`);
  setPetPosition(clamp(left, 8, bounds.width - pet.offsetWidth - 8), clamp(top, 8, bounds.height - pet.offsetHeight - 8));
}

function setPetPosition(left, top) {
  pet.style.left = `${Math.round(left)}px`;
  pet.style.top = `${Math.round(top)}px`;
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(value, Math.max(min, max)));
}

function formatConfidence(value) {
  if (typeof value !== "number") {
    return "-";
  }
  return value.toFixed(2);
}

function triggerPetReaction() {
  const now = Date.now();
  if (now - lastReactionAt < 260) {
    return;
  }
  lastReactionAt = now;
  pet.classList.add("ears-up", "excited", "clicked");
  setPetSpriteState("excited");
  spawnHearts();
  window.setTimeout(() => pet.classList.remove("clicked"), 620);
  if (reactionTimer) {
    window.clearTimeout(reactionTimer);
  }
  reactionTimer = window.setTimeout(() => {
    pet.classList.remove("ears-up", "excited");
    setPetSpriteState("normal");
    reactionTimer = null;
  }, 2000);
}

async function initPetSprite() {
  if (!petCanvas) {
    return;
  }
  try {
    const [normal, excited] = await Promise.all([
      loadAndKeyPetSprite(petCanvas.dataset.normalSrc || "/pet/assets/corgi_normal.png"),
      loadAndKeyPetSprite(petCanvas.dataset.excitedSrc || "/pet/assets/corgi_ears_up.png"),
    ]);
    petSprites.normal = normal;
    petSprites.excited = excited;
    petSpriteReady = true;
    drawPetSprite();
  } catch (error) {
    console.warn("Failed to load pet sprites", error);
  }
}

function loadAndKeyPetSprite(src) {
  return loadImage(src).then((image) => {
    const canvas = document.createElement("canvas");
    canvas.width = petSpriteSize;
    canvas.height = petSpriteSize;
    const context = canvas.getContext("2d", { willReadFrequently: true });
    context.clearRect(0, 0, petSpriteSize, petSpriteSize);
    context.drawImage(image, 0, 0, petSpriteSize, petSpriteSize);
    chromaKeyGreen(context, petSpriteSize, petSpriteSize);
    return canvas;
  });
}

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error(`Failed to load ${src}`));
    image.src = src;
  });
}

function chromaKeyGreen(context, width, height) {
  const imageData = context.getImageData(0, 0, width, height);
  const pixels = imageData.data;
  for (let index = 0; index < pixels.length; index += 4) {
    const red = pixels[index];
    const green = pixels[index + 1];
    const blue = pixels[index + 2];
    const alpha = pixels[index + 3];
    const diff = green - Math.max(red, blue);
    if (green > 120 && diff > 95) {
      pixels[index + 3] = 0;
    } else if (green > 95 && diff > 42) {
      const ratio = Math.min(1, Math.max(0, diff / 110));
      pixels[index + 1] = Math.min(green, Math.round((red + blue) / 2 + 12));
      pixels[index + 3] = Math.max(0, Math.min(255, Math.round(alpha * (1 - ratio))));
    }
  }
  context.putImageData(imageData, 0, 0);
}

function setPetSpriteState(state) {
  activePetState = state === "excited" ? "excited" : "normal";
  if (petSpriteReady) {
    drawPetSprite();
  }
}

function drawPetSprite() {
  const context = petCanvas.getContext("2d");
  const sprite = petSprites[activePetState] || petSprites.normal;
  context.clearRect(0, 0, petCanvas.width, petCanvas.height);
  if (sprite) {
    context.drawImage(sprite, 0, 0, petCanvas.width, petCanvas.height);
  }
}

function spawnHearts() {
  if (!heartLayer) {
    return;
  }
  for (let index = 0; index < 8; index += 1) {
    window.setTimeout(createHeart, index * 80);
  }
}

function createHeart() {
  const heart = document.createElement("span");
  heart.className = "heart-particle";
  heart.textContent = "\u2665";
  const startX = randomBetween(-42, 42);
  const startY = randomBetween(10, 48);
  const endX = startX + randomBetween(-58, 58);
  const endY = startY - randomBetween(96, 148);
  heart.style.setProperty("--heart-color", heartColors[Math.floor(Math.random() * heartColors.length)]);
  heart.style.setProperty("--heart-size", `${Math.round(randomBetween(14, 24))}px`);
  heart.style.setProperty("--heart-duration", `${Math.round(randomBetween(980, 1420))}ms`);
  heart.style.setProperty("--heart-x", `${Math.round(startX)}px`);
  heart.style.setProperty("--heart-y", `${Math.round(startY)}px`);
  heart.style.setProperty("--heart-end-x", `${Math.round(endX)}px`);
  heart.style.setProperty("--heart-end-y", `${Math.round(endY)}px`);
  heart.style.setProperty("--heart-rotate", `${Math.round(randomBetween(-24, 24))}deg`);
  heart.addEventListener("animationend", () => heart.remove(), { once: true });
  heartLayer.appendChild(heart);
}

function randomBetween(min, max) {
  return min + Math.random() * (max - min);
}

function compactSpeech(value) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (!text) {
    return "";
  }
  return text.length > 90 ? `${text.slice(0, 88)}...` : text;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
