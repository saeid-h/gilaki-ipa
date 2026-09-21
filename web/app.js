import { applyMap } from "./rewriter.js";
import { STRINGS } from "./i18n.js";

const DEFAULT_BASE = "https://1404kingstreet.com/gilaki-api";
const DEFAULT_PRESET = "varg-perso-arabic";
const CUSTOM_ID = "custom";
const KEYS = {
  base: "gilaki.apiBase",
  lang: "gilaki.uiLang",
  custom: "gilaki.customMap",
  applyServer: "gilaki.applyOnServer",
  lastIpa: "gilaki.lastIpa",
  maps: "gilaki.presetMaps",
};

const DEFAULT_CUSTOM = {
  id: "my-map",
  name: "My map",
  script: "Latn",
  direction: "ltr",
  lossy: false,
  rules: [
    { ipa: "ə", out: "e" },
    { ipa: "ʃ", out: "sh" },
  ],
};

const $ = (id) => document.getElementById(id);

const state = {
  view: "record",
  lang: localStorage.getItem(KEYS.lang) === "fa" ? "fa" : "en",
  base: localStorage.getItem(KEYS.base) || DEFAULT_BASE,
  maps: {},
  activeId: DEFAULT_PRESET,
  ipa: localStorage.getItem(KEYS.lastIpa) || "",
  showIpa: false,
  status: "ready",
  error: "",
  applyOnServer: localStorage.getItem(KEYS.applyServer) === "1",
  recorder: null,
  chunks: [],
};

function t(key) {
  return STRINGS[state.lang][key] || STRINGS.en[key] || key;
}

function customMap() {
  try {
    return JSON.parse($("customJson").value);
  } catch {
    return null;
  }
}

function activeMap() {
  if (state.activeId === CUSTOM_ID) return customMap();
  return state.maps[state.activeId] || null;
}

function mappedText() {
  if (!state.ipa) return "";
  const map = activeMap();
  if (!map) return "";
  return applyMap(state.ipa, map);
}

function setStatus(kind, extra = "") {
  state.status = kind;
  state.error = extra;
  const el = $("status");
  el.textContent = extra || t(kind === "error" ? "error" : kind);
  el.dataset.kind = kind;
}

function applyChrome() {
  const uiRtl = state.lang === "fa";
  document.documentElement.lang = state.lang === "fa" ? "fa" : "en";
  document.documentElement.dir = uiRtl ? "rtl" : "ltr";
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  $("showIpa").textContent = state.showIpa ? t("hideSounds") : t("showSounds");
  $("recordBtn").textContent = state.status === "recording" ? t("stop") : t("record");
  $("apiBase").value = state.base;
  $("langEn").checked = state.lang === "en";
  $("langFa").checked = state.lang === "fa";
  $("applyServer").checked = state.applyOnServer;
  if (state.status !== "error") $("status").textContent = t(state.status);
}

function showView(name) {
  const overlay = name === "maps" || name === "settings";
  state.view = overlay ? name : "main";
  document.querySelectorAll("[data-screen]").forEach((node) => {
    const screen = node.dataset.screen;
    if (screen === "record") {
      node.hidden = overlay;
    } else if (screen === "result") {
      node.hidden = overlay || !state.ipa;
    } else {
      node.hidden = screen !== name;
    }
  });
}

function renderChips() {
  const row = $("chips");
  row.innerHTML = "";
  const items = [...Object.values(state.maps)];
  const custom = customMap();
  if (custom) items.push({ ...custom, id: CUSTOM_ID, name: custom.name || "Custom" });
  for (const item of items) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chip";
    btn.dataset.mapId = item.id;
    btn.dataset.testid = `chip-${item.id}`;
    if (item.id === state.activeId) btn.classList.add("selected");
    btn.textContent = item.name || item.id;
    if (item.lossy) {
      const dot = document.createElement("span");
      dot.className = "lossy-dot";
      dot.title = t("lossy");
      btn.appendChild(dot);
    }
    btn.addEventListener("click", () => {
      state.activeId = item.id;
      renderChips();
      renderResult();
    });
    row.appendChild(btn);
  }
}

function renderResult() {
  const map = activeMap() || {};
  const rtl = map.direction === "rtl";
  const text = mappedText();
  const card = $("transcript");
  card.dir = rtl ? "rtl" : "ltr";
  card.classList.toggle("arab", map.script === "Arab");
  card.classList.toggle("latn", map.script !== "Arab");
  $("mapped").textContent = text || t("noResult");
  $("ipa").textContent = state.ipa;
  $("ipa").hidden = !state.showIpa;
  $("showIpa").textContent = state.showIpa ? t("hideSounds") : t("showSounds");
  $("lossy").hidden = !map.lossy;
  showView("main");
}

async function api(path, options = {}) {
  const base = state.base.replace(/\/$/, "");
  const res = await fetch(base + path, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const code = data?.error?.code || data?.detail?.error?.code || res.status;
    throw new Error(String(code));
  }
  return data;
}

async function loadPresets() {
  const cached = localStorage.getItem(KEYS.maps);
  if (cached) {
    try {
      state.maps = JSON.parse(cached);
    } catch {
      state.maps = {};
    }
  }
  const list = await api("/v1/presets");
    const maps = {};
    for (const row of list.presets || []) {
      const detail = await api(`/v1/presets/${row.id}`);
      maps[row.id] = detail.preset;
    }
  state.maps = maps;
  localStorage.setItem(KEYS.maps, JSON.stringify(maps));
  if (!state.maps[state.activeId] && state.activeId !== CUSTOM_ID) {
    state.activeId = DEFAULT_PRESET;
  }
  renderChips();
}

async function recognize(blob, filename) {
  setStatus("uploading");
  const body = new FormData();
  body.append("audio", blob, filename || "clip.webm");
  const custom = customMap();
  if (state.applyOnServer && custom && state.activeId === CUSTOM_ID) {
    body.append("map_json", JSON.stringify(custom));
  }
  const data = await api("/v1/recognize", { method: "POST", body });
  state.ipa = data.ipa || "";
  localStorage.setItem(KEYS.lastIpa, state.ipa);
  setStatus("ready");
  if (data.backend) {
    $("status").textContent = `${t("ready")} · ${data.backend}`;
  }
  renderChips();
  renderResult();
}

async function onFile(file) {
  if (!file) return;
  try {
    await recognize(file, file.name);
  } catch (err) {
    setStatus("error", String(err.message || err));
  } finally {
    $("file").value = "";
  }
}

async function toggleRecord() {
  if (state.recorder) {
    state.recorder.stop();
    return;
  }
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const mime = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"].find((type) =>
    MediaRecorder.isTypeSupported(type),
  );
  const recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
  state.chunks = [];
  recorder.ondataavailable = (event) => {
    if (event.data.size) state.chunks.push(event.data);
  };
  recorder.onstop = async () => {
    stream.getTracks().forEach((track) => track.stop());
    state.recorder = null;
    $("recordBtn").classList.remove("recording");
    const blob = new Blob(state.chunks, { type: recorder.mimeType || "audio/webm" });
    try {
      await recognize(blob, "mic.webm");
    } catch (err) {
      setStatus("error", String(err.message || err));
    }
    applyChrome();
  };
  state.recorder = recorder;
  recorder.start();
  $("recordBtn").classList.add("recording");
  setStatus("recording");
  applyChrome();
}

function bind() {
  $("recordBtn").addEventListener("click", () => {
    toggleRecord().catch((err) => setStatus("error", String(err.message || err)));
  });
  $("file").addEventListener("change", (event) => {
    const file = event.target.files && event.target.files[0];
    onFile(file);
  });
  $("showIpa").addEventListener("click", () => {
    state.showIpa = !state.showIpa;
    renderResult();
  });
  $("openMaps").addEventListener("click", () => showView("maps"));
  $("openSettings").addEventListener("click", () => showView("settings"));
  document.querySelectorAll("[data-back]").forEach((btn) => {
    btn.addEventListener("click", () => showView("main"));
  });
  $("saveMap").addEventListener("click", () => {
    JSON.parse($("customJson").value);
    localStorage.setItem(KEYS.custom, $("customJson").value);
    renderChips();
    if (state.activeId === CUSTOM_ID) renderResult();
  });
  $("applyServer").addEventListener("change", () => {
    state.applyOnServer = $("applyServer").checked;
    localStorage.setItem(KEYS.applyServer, state.applyOnServer ? "1" : "0");
  });
  $("saveSettings").addEventListener("click", async () => {
    state.base = $("apiBase").value.trim() || DEFAULT_BASE;
    localStorage.setItem(KEYS.base, state.base);
    try {
      await loadPresets();
      setStatus("ready");
      showView("main");
    } catch (err) {
      setStatus("error", String(err.message || err));
    }
  });
  $("langEn").addEventListener("change", () => {
    if ($("langEn").checked) {
      state.lang = "en";
      localStorage.setItem(KEYS.lang, "en");
      applyChrome();
      renderResult();
    }
  });
  $("langFa").addEventListener("change", () => {
    if ($("langFa").checked) {
      state.lang = "fa";
      localStorage.setItem(KEYS.lang, "fa");
      applyChrome();
      renderResult();
    }
  });
}

function boot() {
  $("customJson").value =
    localStorage.getItem(KEYS.custom) || JSON.stringify(DEFAULT_CUSTOM, null, 2);
  $("apiBase").value = state.base;
  bind();
  applyChrome();
  showView("main");
  loadPresets()
    .then(() => {
      setStatus("ready");
      renderChips();
      if (state.ipa) renderResult();
      else showView("main");
    })
    .catch((err) => setStatus("error", String(err.message || err)));
}

boot();
