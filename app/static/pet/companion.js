const desktop = document.querySelector("#companionDesktop");
const petWidget = document.querySelector("#petWidget");
const petDialog = document.querySelector("#petDialog");
const chatForm = document.querySelector("#chatForm");
const chatInput = document.querySelector("#chatInput");
const sendChat = document.querySelector("#sendChat");
const closeDialog = document.querySelector("#closeDialog");
const dialogStatus = document.querySelector("#dialogStatus");
const replyBox = document.querySelector("#replyBox");
const heartLayer = document.querySelector("#heartLayer");
const petCanvas = document.querySelector("#petCanvas");
const sizeButtons = Array.from(document.querySelectorAll("[data-size-preset]"));

const positionKey = "healthdesk.companion.position";
const sizeKey = "healthdesk.companion.size";
const heartColors = ["#ff4d6d", "#ff6b8a", "#ff85a1", "#ff3366", "#ff80ab", "#f06292", "#e91e63"];
const petSpriteSize = 220;
const sizePresetOrder = ["small", "medium", "large"];
const sizePresets = {
  small: { label: "小", scale: 0.85 },
  medium: { label: "中", scale: 1 },
  large: { label: "大", scale: 1.25 },
};
const petSprites = {
  normal: null,
  excited: null,
};

let dragging = null;
let isBusy = false;
let activePetState = "normal";
let activeSizePreset = loadSizePreset();
let petSpriteReady = false;
let reactionTimer = null;
let hideReplyTimer = null;
let lastWakeAt = 0;

applySizePreset(activeSizePreset, { persist: false, clamp: false });
initWidgetPosition();
initPetSprite();

petWidget.addEventListener("pointerdown", startDrag);
petWidget.addEventListener("contextmenu", cycleSizeFromContextMenu);
petDialog.addEventListener("pointerdown", stopDialogEvent);
petDialog.addEventListener("click", stopDialogEvent);
window.addEventListener("resize", clampWidgetPosition);

closeDialog.addEventListener("click", () => {
  hideDialog();
});

sizeButtons.forEach((button) => {
  button.addEventListener("click", () => {
    setSizePresetFromControl(button.dataset.sizePreset);
  });
});

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await sendMessage();
});

chatInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    chatForm.requestSubmit();
  }
});

function loadSizePreset() {
  const saved = localStorage.getItem(sizeKey);
  return sizePresets[saved] ? saved : "medium";
}

function applySizePreset(preset, options = {}) {
  const nextPreset = sizePresets[preset] ? preset : "medium";
  const scale = sizePresets[nextPreset].scale;
  const px = (value) => `${Math.round(value * scale)}px`;

  activeSizePreset = nextPreset;
  petWidget.dataset.size = nextPreset;
  syncSizeButtons();
  petWidget.style.setProperty("--pet-widget-width", px(220));
  petWidget.style.setProperty("--pet-widget-height", px(300));
  petWidget.style.setProperty("--pet-visual-size", px(220));
  petWidget.style.setProperty("--pet-visual-bottom", px(28));
  petWidget.style.setProperty("--pet-dialog-bottom", px(250));
  petWidget.style.setProperty("--pet-dialog-width", px(340));
  petWidget.style.setProperty("--pet-name-font-size", px(13));
  petWidget.style.setProperty("--pet-heart-inset", `${px(-72)} ${px(-34)} 0`);

  if (options.persist) {
    localStorage.setItem(sizeKey, nextPreset);
  }
  if (options.clamp) {
    window.requestAnimationFrame(() => {
      clampWidgetPosition();
      saveWidgetPosition();
    });
  }
}

function syncSizeButtons() {
  sizeButtons.forEach((button) => {
    const isActive = button.dataset.sizePreset === activeSizePreset;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-pressed", String(isActive));
  });
}

function setSizePresetFromControl(preset) {
  if (!sizePresets[preset]) {
    return;
  }
  applySizePreset(preset, { persist: true, clamp: true });
  triggerPetReaction();
  dialogStatus.textContent = `大小：${sizePresets[preset].label}`;
}

function cycleSizeFromContextMenu(event) {
  if (petDialog.contains(event.target)) {
    return;
  }
  event.preventDefault();
  const currentIndex = sizePresetOrder.indexOf(activeSizePreset);
  const nextPreset = sizePresetOrder[(currentIndex + 1) % sizePresetOrder.length];
  applySizePreset(nextPreset, { persist: true, clamp: true });
  triggerPetReaction();
  if (!petDialog.classList.contains("hidden")) {
    dialogStatus.textContent = `大小：${sizePresets[nextPreset].label}`;
  }
}

function currentPetScale() {
  return sizePresets[activeSizePreset]?.scale || 1;
}

function stopDialogEvent(event) {
  event.stopPropagation();
}

function wakeDialog() {
  const now = Date.now();
  if (now - lastWakeAt < 220) {
    return;
  }
  lastWakeAt = now;
  triggerPetReaction();
  clearHideReplyTimer();
  petDialog.classList.remove("hidden");
  if (!isBusy) {
    chatForm.classList.remove("hidden");
    replyBox.classList.add("hidden");
    dialogStatus.textContent = "Ready";
    window.setTimeout(() => chatInput.focus(), 30);
  }
}

async function sendMessage() {
  const text = chatInput.value.trim();
  if (!text || isBusy) {
    chatInput.focus();
    return;
  }
  setBusy(true);
  dialogStatus.textContent = "\u601d\u8003\u4e2d...";
  replyBox.classList.add("hidden");
  try {
    const result = await postJson("/agent/run", {
      task: text,
      user_id: "default",
    });
    const output = result.final_output || {};
    const petAction = output.pet_action || {};
    if (petAction.animation === "drink_water" || petAction.emotion === "excited") {
      setPetSpriteState("excited");
    }
    showReply(formatAgentReply(result));
  } catch (error) {
    showReply(`\u5c0f\u7075\u6ca1\u6709\u5b8c\u6210\u8fd9\u6b21\u5bf9\u8bdd\uff1a${error.message}`);
  } finally {
    setBusy(false);
  }
}

function showReply(text) {
  petDialog.classList.remove("hidden");
  chatForm.classList.add("hidden");
  replyBox.textContent = text;
  replyBox.classList.remove("hidden");
  triggerPetReaction();
  clearHideReplyTimer();
  hideReplyTimer = window.setTimeout(() => {
    hideDialog();
  }, 10000);
}

function hideDialog() {
  clearHideReplyTimer();
  petDialog.classList.add("hidden");
  replyBox.classList.add("hidden");
  chatForm.classList.remove("hidden");
}

function clearHideReplyTimer() {
  if (hideReplyTimer) {
    window.clearTimeout(hideReplyTimer);
    hideReplyTimer = null;
  }
}

function setBusy(value) {
  isBusy = value;
  chatInput.disabled = value;
  sendChat.disabled = value;
}

function formatAgentReply(result) {
  const output = result.final_output || {};
  const petAction = output.pet_action || {};
  const lines = [];
  const summary = output.health_summary || output.answer || output.message || result.message || petAction.message;
  if (summary) {
    lines.push(String(summary));
  }
  const recommendations = Array.isArray(output.recommendations) ? output.recommendations : [];
  if (recommendations.length) {
    const details = recommendations
      .slice(0, 3)
      .map((item) => {
        const category = item.category || "\u5efa\u8bae";
        const action = item.suggested_action || item.reason || "";
        return `${category}: ${action}`;
      })
      .filter(Boolean)
      .join("\n");
    if (details) {
      lines.push(details);
    }
  }
  if (!lines.length && petAction.message) {
    lines.push(String(petAction.message));
  }
  return lines.join("\n\n") || "\u5c0f\u7075\u5df2\u7ecf\u6536\u5230\u4e86\u3002";
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
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
  if (event.button !== 0) {
    return;
  }
  if (petDialog.contains(event.target)) {
    return;
  }
  const rect = petWidget.getBoundingClientRect();
  dragging = {
    offsetX: event.clientX - rect.left,
    offsetY: event.clientY - rect.top,
    startX: event.clientX,
    startY: event.clientY,
    moved: false,
  };
  petWidget.classList.add("dragging");
  petWidget.setPointerCapture(event.pointerId);
  petWidget.addEventListener("pointermove", moveDrag);
  petWidget.addEventListener("pointerup", stopDrag, { once: true });
  petWidget.addEventListener("pointercancel", stopDrag, { once: true });
}

function moveDrag(event) {
  if (!dragging) {
    return;
  }
  if (Math.hypot(event.clientX - dragging.startX, event.clientY - dragging.startY) > 3) {
    dragging.moved = true;
  }
  setWidgetPosition(event.clientX - dragging.offsetX, event.clientY - dragging.offsetY);
}

function stopDrag(event) {
  const wasClick = dragging && !dragging.moved && event.type !== "pointercancel";
  dragging = null;
  petWidget.classList.remove("dragging");
  petWidget.removeEventListener("pointermove", moveDrag);
  saveWidgetPosition();
  if (wasClick) {
    wakeDialog();
  }
}

function initWidgetPosition() {
  const saved = localStorage.getItem(positionKey);
  if (saved) {
    try {
      const position = JSON.parse(saved);
      if (typeof position.left === "number" && typeof position.top === "number") {
        setWidgetPosition(position.left, position.top);
        return;
      }
    } catch (_error) {
      localStorage.removeItem(positionKey);
    }
  }
  requestAnimationFrame(() => {
    const left = Math.max(24, window.innerWidth - petWidget.offsetWidth - 72);
    const top = Math.max(40, window.innerHeight - petWidget.offsetHeight - 72);
    setWidgetPosition(left, top);
  });
}

function clampWidgetPosition() {
  const rect = petWidget.getBoundingClientRect();
  setWidgetPosition(rect.left, rect.top);
  saveWidgetPosition();
}

function setWidgetPosition(left, top) {
  const maxLeft = Math.max(8, window.innerWidth - petWidget.offsetWidth - 8);
  const maxTop = Math.max(8, window.innerHeight - petWidget.offsetHeight - 8);
  const nextLeft = clamp(left, 8, maxLeft);
  const nextTop = clamp(top, 8, maxTop);
  petWidget.style.left = `${Math.round(nextLeft)}px`;
  petWidget.style.top = `${Math.round(nextTop)}px`;
  petWidget.classList.toggle("near-left", nextLeft < 170);
  petWidget.classList.toggle("near-right", nextLeft + petWidget.offsetWidth > window.innerWidth - 170);
}

function saveWidgetPosition() {
  const rect = petWidget.getBoundingClientRect();
  localStorage.setItem(positionKey, JSON.stringify({ left: Math.round(rect.left), top: Math.round(rect.top) }));
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(value, Math.max(min, max)));
}

function triggerPetReaction() {
  petWidget.classList.add("clicked");
  setPetSpriteState("excited");
  spawnHearts();
  window.setTimeout(() => petWidget.classList.remove("clicked"), 620);
  if (reactionTimer) {
    window.clearTimeout(reactionTimer);
  }
  reactionTimer = window.setTimeout(() => {
    setPetSpriteState("normal");
    reactionTimer = null;
  }, 2000);
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
  const scale = currentPetScale();
  const startX = randomBetween(-42, 42) * scale;
  const startY = randomBetween(10, 48) * scale;
  const endX = startX + randomBetween(-58, 58) * scale;
  const endY = startY - randomBetween(96, 148) * scale;
  heart.style.setProperty("--heart-color", heartColors[Math.floor(Math.random() * heartColors.length)]);
  heart.style.setProperty("--heart-size", `${Math.round(randomBetween(14, 24) * scale)}px`);
  heart.style.setProperty("--heart-duration", `${Math.round(randomBetween(980, 1420))}ms`);
  heart.style.setProperty("--heart-x", `${Math.round(startX)}px`);
  heart.style.setProperty("--heart-y", `${Math.round(startY)}px`);
  heart.style.setProperty("--heart-end-x", `${Math.round(endX)}px`);
  heart.style.setProperty("--heart-end-y", `${Math.round(endY)}px`);
  heart.style.setProperty("--heart-rotate", `${Math.round(randomBetween(-24, 24))}deg`);
  heart.addEventListener("animationend", () => heart.remove(), { once: true });
  heartLayer.appendChild(heart);
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

function randomBetween(min, max) {
  return min + Math.random() * (max - min);
}
