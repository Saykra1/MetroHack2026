/* Tram load forecast dashboard — vanilla JS, Leaflet + ECharts. */
(() => {
  "use strict";
  const API = "/api/v1";
  const $ = (id) => document.getElementById(id);
  const nf = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 });
  const fmt = (v) => (v === null || v === undefined || Number.isNaN(v) ? "—" : nf.format(v));
  const MONTHS = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"];
  const MONTHS_GEN = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"];
  const WD = ["вс", "пн", "вт", "ср", "чт", "пт", "сб"];
  const pad = (n) => String(n).padStart(2, "0");
  const iso = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const parse = (s) => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };
  const human = (s) => { const d = parse(s); return `${d.getDate()} ${MONTHS_GEN[d.getMonth()]} ${d.getFullYear()}, ${WD[d.getDay()]}`; };
  const short = (s) => { const d = parse(s); return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}`; };
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();

  const S = {
    route: "all", horizon: "day", date: "2025-11-11", month: "2025-11", growth: 0,
    hourFrom: 0, hourTo: 23, hour: 8, stop: null, stopName: "",
    routes: [], coverage: null, explainAvailable: false, map: null, playing: null, band: 10,
    adj: { level: 1, scope: "all", special: 1, precip: -1.1, cold: -3.4, floor: 0.9, scn: [], events: [], traffic: [], tActual: false, wTraffic: 0.7 },
    lastFit: null,
    model: "v08", planP90: false, ml: {}, anomKind: "",
  };
  const ADJ_DEFAULT = JSON.stringify({ level: 1, scope: "all", special: 1, precip: -1.1, cold: -3.4, floor: 0.9, scn: [], events: [], traffic: [], tActual: false, wTraffic: 0.7 });
  const num = (v) => Math.round(v * 10000) / 10000;
  function adjParams() {
    const a = S.adj, out = {};
    if (a.level !== 1) out.k_level = a.scope === "all" || S.route === "all" ? `${a.level}` : `${S.route}:${a.level}`;
    if (a.special !== 1) out.k_special = a.special;
    if (a.precip !== -1.1) out.w_precip = num(a.precip / 100);
    if (a.cold !== -3.4) out.w_cold = num(a.cold / 100);
    if (a.floor !== 0.9) out.w_floor = a.floor;
    if (a.scn.length) out.w_scenario = a.scn.map((x) => `${x.date}:${x.mm}${x.t !== null && x.t !== "" ? ":" + x.t : ""}`).join(";");
    if (a.tActual || a.traffic.length) out.k_traffic = [...(a.tActual ? ["actual"] : []), ...a.traffic.map((x) => `${x.date}:${x.score}`)].join(";");
    if (out.k_traffic && a.wTraffic !== 0.7) out.w_traffic = num(a.wTraffic / 100);
    if (a.events.length) out.k_event = a.events.map((e) => `${e.route}:${e.from}:${e.to}:${e.k}${e.h0 !== 0 || e.h1 !== 23 ? `:${e.h0}-${e.h1}` : ""}`).join(";");
    return out;
  }
  const adjActive = () => Object.keys(adjParams()).length > 0;
  const ADJ_PATHS = new Set(["/series", "/forecast", "/forecast/stop", "/kpi", "/map", "/fleet", "/scenario/year", "/weather", "/assistant", "/assistant/query", "/traffic"]);
  const modelParams = () => (S.model === "hybrid" ? { model: "hybrid" } : {});

  // ---------------- API ----------------
  const cache = new Map();
  async function api(path, params = {}) {
    if (ADJ_PATHS.has(path)) params = { ...params, ...adjParams(), ...modelParams() };
    const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== ""));
    const url = `${API}${path}?${q}`;
    if (cache.has(url)) return cache.get(url);
    const p = fetch(url).then(async (r) => {
      const body = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(body?.error?.message || `Ошибка ${r.status}`);
      return body;
    });
    cache.set(url, p);
    p.catch(() => cache.delete(url));
    return p;
  }
  // toasts: top-right, close button, auto-close after 6 s (errors stay readable, never block the page)
  let toastTimer = null;
  function toast(msg) {
    const t = $("toast");
    clearTimeout(toastTimer);
    if (!msg) { t.classList.add("hidden"); return; }
    t.innerHTML = `<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16v.5"/></svg><span></span><button class="toast-x" aria-label="Закрыть уведомление">✕</button>`;
    t.querySelector("span").textContent = msg;
    t.querySelector(".toast-x").onclick = () => t.classList.add("hidden");
    t.classList.remove("hidden");
    toastTimer = setTimeout(() => t.classList.add("hidden"), 6000);
  }

  // ---------------- period helpers ----------------
  const histEnd = () => S.coverage.history.to;
  const fcStart = () => S.coverage.forecast.from;
  const srcFor = (dateStr) => (dateStr <= histEnd() ? "history" : "forecast");
  function monthRange(ym) {
    const [y, m] = ym.split("-").map(Number);
    return [`${ym}-01`, iso(new Date(y, m, 0))];
  }
  function period() {
    if (S.horizon === "day") return { from: S.date, to: S.date, source: srcFor(S.date) };
    if (S.horizon === "month") { const [a, b] = monthRange(S.month); return { from: a, to: b, source: srcFor(a) }; }
    return { from: S.coverage.combined.from, to: S.coverage.combined.to, source: "combined" };
  }
  const hours = () => ({ hour_from: S.hourFrom, hour_to: S.hourTo });
  const routeHasData = (r) => r === "all" || S.routes.find((x) => x.route === r)?.has_data;
  const routeHasHistory = (r) => r === "all" || S.routes.find((x) => x.route === r)?.has_history;
  const launchOf = (r) => S.routes.find((x) => x.route === r)?.launch_date || null;

  // ---------------- init ----------------
  async function init() {
    applyTheme(localStorageGet("theme"));
    const meta = await api("/routes");
    S.routes = meta.routes; S.coverage = meta.coverage; S.explainAvailable = meta.explain_available;
    const sel = $("route");
    sel.innerHTML = `<option value="all">Все маршруты (сумма)</option>` + S.routes.map((r) =>
      `<option value="${r.route}">№ ${r.route}${r.name ? " · " + r.name : ""}${!r.has_data ? " — нет данных" : r.launch_date ? ` — новый, с ${short(r.launch_date)}` : ""}</option>`).join("");
    const ms = $("month");
    ms.innerHTML = MONTHS.map((m, i) => {
      const ym = `2025-${pad(i + 1)}`;
      return `<option value="${ym}">${m[0].toUpperCase() + m.slice(1)} 2025 · ${ym <= histEnd().slice(0, 7) ? "факт" : "прогноз"}</option>`;
    }).join("");
    ms.value = S.month;
    for (const id of ["hourFrom", "hourTo"]) $(id).innerHTML = [...Array(24).keys()].map((h) => `<option value="${h}">${pad(h)}:00</option>`).join("");
    $("hourFrom").value = 0; $("hourTo").value = 23;
    $("date").value = S.date; $("date").min = S.coverage.combined.from; $("date").max = S.coverage.combined.to;
    $("hour").value = S.hour;
    const h = await api("/health");
    $("footInfo").textContent = `Прогноз: ${h.forecast_file === "forecast.csv" && h.data_bundle?.forecast_source ? h.data_bundle.forecast_source : h.forecast_file}${h.explain_loaded ? " (с декомпозицией)" : ""}.`;
    S.ml = h.ml || {};
    loadDataQuality();
    initAdjControls();
    initAi();
    bind();
    initShell();
    initMap();
    await refresh();
  }

  function bind() {
    $("route").onchange = (e) => { S.route = e.target.value; S.stop = null; refresh(); };
    $("horizon").onclick = (e) => {
      const b = e.target.closest("button"); if (!b) return;
      S.horizon = b.dataset.h;
      [...$("horizon").children].forEach((x) => x.classList.toggle("on", x === b));
      if (S.horizon === "month") S.month = S.date.slice(0, 7), $("month").value = S.month;
      $("lineChart").classList.add("fade");  // smooth day ↔ month ↔ year switch (cleared when the new chart is drawn)
      refresh();
    };
    $("date").onchange = (e) => {
      const v = e.target.value;
      if (!v || v < S.coverage.combined.from || v > S.coverage.combined.to) {
        toast(`Дата должна быть в диапазоне ${S.coverage.combined.from} — ${S.coverage.combined.to}`); e.target.value = S.date; return;
      }
      S.date = v; refresh();
    };
    $("month").onchange = (e) => { S.month = e.target.value; const [a] = monthRange(S.month); S.date = a; $("date").value = a; refresh(); };
    $("growth").onchange = (e) => { S.growth = Math.max(-50, Math.min(50, Number(e.target.value) || 0)); e.target.value = S.growth; refresh(); };
    $("band").onchange = (e) => { S.band = Math.max(0, Math.min(50, Number(e.target.value) || 0)); e.target.value = S.band; refresh(); };
    $("hourFrom").onchange = $("hourTo").onchange = () => {
      let a = +$("hourFrom").value, b = +$("hourTo").value;
      if (b < a) { toast("Час окончания не может быть раньше часа начала"); $("hourTo").value = S.hourTo; $("hourFrom").value = S.hourFrom; return; }
      S.hourFrom = a; S.hourTo = b; refresh();
    };
    $("hour").oninput = (e) => { S.hour = +e.target.value; paintHour(); loadExplain(); };
    $("play").onclick = togglePlay;
    $("expCsv").onclick = () => doExport("csv");
    $("expXlsx").onclick = () => doExport("xlsx");
    $("stopChip").onclick = () => { S.stop = null; refresh(); };
    $("themeBtn").onclick = () => {
      const dark = isDark();
      const t = dark ? "light" : "dark";
      const root = document.documentElement;  // 300 ms colour transition only while the theme switches
      root.classList.add("theme-switching");
      localStorageSet("theme", t); applyTheme(t); rerenderCharts();
      setTimeout(() => root.classList.remove("theme-switching"), 350);
    };
    window.addEventListener("resize", () => Object.values(charts).forEach((c) => c && c.resize()));
    matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", () => { applyTheme(localStorageGet("theme")); rerenderCharts(); });
  }

  function localStorageGet(k) { try { return localStorage.getItem(k); } catch { return null; } }
  function localStorageSet(k, v) { try { localStorage.setItem(k, v); } catch { /* ignore */ } }
  function isDark() {
    const t = document.documentElement.dataset.theme;
    return t ? t === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  }
  function applyTheme(t) {
    if (t === "light" || t === "dark") document.documentElement.dataset.theme = t;
    document.documentElement.classList.toggle("is-dark", isDark());  // drives the sun/moon toggle and map tiles
    // CartoDB basemaps follow the theme: Dark Matter in dark, Positron in light (no CSS filter hacks)
    if (S.tiles) S.tiles.setUrl(tileUrl());
  }

  // ---------------- refresh ----------------
  let seq = 0;
  async function refresh() {
    const my = ++seq;
    toast(null);
    $("dateBox").classList.toggle("hidden", S.horizon !== "day");
    $("monthBox").classList.toggle("hidden", S.horizon !== "month");
    $("growthBox").classList.toggle("hidden", S.horizon !== "year");
    $("bandBox").classList.toggle("hidden", S.horizon !== "year");
    renderAdjInfo();
    $("stopChip").classList.toggle("hidden", !S.stop);
    if (S.stop) $("stopChip").textContent = `Остановка: ${S.stopName} ✕`;
    const jobs = [track("map", loadMap()), loadKpis(), track("lineChart", loadLine()), track("heatChart", loadHeat()), loadTable(), loadExplain(),
      track("fleetChart", loadFleet()), loadWeatherInfo(), loadAnomalies(), loadTrafficInfo()];
    const res = await Promise.allSettled(jobs);
    if (my !== seq) return;
    const err = res.find((r) => r.status === "rejected");
    if (err) toast(err.reason.message);
  }

  // ---------------- loading / empty states (cat mascot) ----------------
  const CAT_LYING = "/static/img/cat_lying.png";
  function overlayFor(id) {
    const el = $(id);
    let host = el.parentElement;
    if (id !== "map" && !host.classList.contains("chart-wrap")) {
      const w = document.createElement("div");
      w.className = "chart-wrap";
      el.replaceWith(w); w.appendChild(el); host = w;
    }
    let ov = host.querySelector(":scope > .loader");
    if (!ov) {
      ov = document.createElement("div");
      ov.className = "loader hidden";
      ov.innerHTML = `<div class="skel"></div><div class="loader-cat"><img src="${CAT_LYING}" alt="" width="84" height="94"><span></span></div>`;
      host.appendChild(ov);
    }
    return ov;
  }
  /** Skeleton + lying cat «Считаю прогноз…» while a block loads (only if it takes > 250 ms, so fast answers don't flicker). */
  function track(id, promise) {
    const ov = overlayFor(id);
    const t = setTimeout(() => {
      ov.querySelector("span").textContent = "Считаю прогноз…";
      ov.classList.remove("hidden", "empty"); ov.classList.add("busy");
    }, 250);
    const done = () => { clearTimeout(t); ov.classList.remove("busy"); $(id).classList.remove("fade"); if (!ov.classList.contains("empty")) ov.classList.add("hidden"); };
    promise.then(done, done);
    return promise;
  }
  /** Empty state: the same cat with a message instead of a blank chart. */
  function setEmpty(id, text) {
    const ov = overlayFor(id);
    if (!text) { ov.classList.remove("empty"); ov.classList.add("hidden"); return; }
    ov.querySelector("span").textContent = text;
    ov.classList.remove("hidden", "busy"); ov.classList.add("empty");
  }

  // ---------------- KPIs ----------------
  async function loadKpis() {
    const p = period();
    const lbl = S.horizon === "day" ? `Пассажиров за сутки (${p.source === "history" ? "факт" : "прогноз"})`
      : S.horizon === "month" ? `Пассажиров за месяц (${p.source === "history" ? "факт" : "прогноз"})` : "Пассажиров за 2025 (факт + прогноз)";
    $("kTotalLabel").textContent = lbl;
    if (!routeHasData(S.route)) { ["kPeak", "kMax", "kTotal", "kChange"].forEach((k) => ($(k).textContent = "—")); $("kTotalSub").textContent = "нет данных о пассажиропотоке"; return; }
    if (p.source === "history" && !routeHasHistory(S.route)) {
      ["kPeak", "kMax", "kTotal", "kChange"].forEach((k) => ($(k).textContent = "—"));
      ["kPeakSub", "kMaxSub", "kChangeSub"].forEach((k) => ($(k).textContent = ""));
      $("kTotalSub").textContent = `нет факта: маршрут запущен ${human(launchOf(S.route))}`; return;
    }
    const k = await api("/kpi", { route: S.route, date_from: p.from, date_to: p.to, source: p.source, ...hours() });
    renderAdjDelta(k);
    $("kPeak").textContent = k.peak_hour === null ? "—" : `${pad(k.peak_hour)}:00–${pad((k.peak_hour + 1) % 24)}:00`;
    $("kPeakSub").textContent = k.peak_hour_avg ? `в среднем ${fmt(k.peak_hour_avg)} пасс./час` : "";
    $("kMax").textContent = fmt(k.max_hourly);
    $("kMaxSub").textContent = k.max_at ? `${human(k.max_at.slice(0, 10))}, ${k.max_at.slice(11)}` : "";
    $("kTotal").textContent = fmt(k.total);
    $("kTotalSub").textContent = S.horizon === "day" ? human(p.from) : `в среднем ${fmt(k.avg_per_day)} в сутки`;
    if (k.adjusted) $("kTotalSub").textContent = `было ${fmt(k.delta.total_before)} → стало ${fmt(k.delta.total_after)} (${sign(k.delta.pct)} %)`;
    if (S.horizon === "year") {
      const y = await api("/scenario/year", { route: S.route, growth: S.growth, band: S.band });
      $("kTotalLabel").textContent = `Пассажиров за ${y.scenario_year} (сценарный прогноз)`;
      $("kTotal").textContent = fmt(y.total);
      $("kTotalSub").textContent = `коридор ${fmt(y.total_low)} – ${fmt(y.total_high)} (±${String(y.band_pct).replace(".", ",")} %)`;
    }
    const c = k.change_vs_prev_month;
    if (c && c.pct !== null && S.horizon !== "year") {
      const s = c.pct > 0 ? "+" : "";
      $("kChange").innerHTML = `<span>${s}${c.pct.toLocaleString("ru-RU")}%</span>`;
      $("kChangeSub").textContent = c.basis === "same_weekday"
        ? `к среднему «${WD[parse(p.from).getDay()]}» за ${c.prev_month}: ${fmt(c.prev_avg_per_day)}`
        : `ср. сутки к ${c.prev_month}: ${fmt(c.prev_avg_per_day)}`;
    } else {
      $("kChange").textContent = "—";
      $("kChangeSub").textContent = S.horizon === "year" ? "не применимо для года" : "нет данных за прошлый месяц";
    }
  }

  const sign = (v) => (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toLocaleString("ru-RU", { maximumFractionDigits: 2 });

  // ---------------- corrections panel ----------------
  let adjTimer = null;
  function adjChanged(immediate = false) {
    clearTimeout(adjTimer);
    renderAdjInfo();
    adjTimer = setTimeout(refresh, immediate ? 0 : 250);
  }
  function initAdjControls() {
    const a = S.adj;
    const hopts = [...Array(24).keys()].map((h) => `<option value="${h}">${pad(h)}:00</option>`).join("");
    $("eH0").innerHTML = hopts; $("eH1").innerHTML = hopts; $("eH1").value = 23;
    $("eRoute").innerHTML = `<option value="all">все маршруты</option>` + S.routes.filter((r) => r.has_data).map((r) => `<option value="${r.route}">№ ${r.route}</option>`).join("");
    const fc0 = S.coverage.forecast.from, fc1 = S.coverage.forecast.to;
    for (const id of ["wDate", "eFrom", "eTo"]) { $(id).min = fc0; $(id).max = fc1; }
    $("wDate").value = S.date >= fc0 ? S.date : fc0; $("eFrom").value = $("wDate").value; $("eTo").value = $("wDate").value;
    $("kLevel").oninput = (e) => { a.level = +e.target.value; $("oLevel").textContent = `×${a.level.toFixed(2).replace(".", ",")}`; adjChanged(); };
    $("kLevelScope").onchange = (e) => { a.scope = e.target.value; adjChanged(); };
    $("kSpecial").oninput = (e) => { a.special = +e.target.value; $("oSpecial").textContent = `×${a.special.toFixed(2).replace(".", ",")}`; adjChanged(); };
    $("wPrecip").onchange = (e) => { a.precip = clampIn(e.target, -20, 20, -1.1); adjChanged(true); };
    $("wCold").onchange = (e) => { a.cold = clampIn(e.target, -50, 50, -3.4); adjChanged(true); };
    $("wFloor").onchange = (e) => { a.floor = clampIn(e.target, 0.3, 1, 0.9); adjChanged(true); };
    $("wAdd").onclick = () => {
      const d = $("wDate").value;
      if (!d || d < fc0 || d > fc1) { toast(`Сценарий погоды задаётся на даты прогноза: ${fc0} — ${fc1}`); return; }
      const mm = Number($("wMm").value) || 0, t = $("wT").value === "" ? null : Number($("wT").value);
      a.scn = a.scn.filter((x) => x.date !== d).concat([{ date: d, mm, t }]);
      adjChanged(true);
    };
    document.querySelectorAll(".ghost-btn[data-k]").forEach((b) => (b.onclick = () => { $("eK").value = b.dataset.k; paintAdjControls(); }));
    $("eK").addEventListener("input", paintAdjControls);
    document.querySelectorAll("#adjCard input[type=range]").forEach((r) => r.addEventListener("input", paintAdjControls));
    $("eAdd").onclick = () => {
      const from = $("eFrom").value, to = $("eTo").value, k = Number($("eK").value), h0 = +$("eH0").value, h1 = +$("eH1").value;
      if (!from || !to || to < from) { toast("Событие: дата окончания раньше даты начала"); return; }
      if (h1 < h0) { toast("Событие: час окончания раньше часа начала"); return; }
      if (!(k >= 0 && k <= 5)) { toast("Событие: множитель от 0 до 5"); return; }
      a.events.push({ route: $("eRoute").value, from, to, k, h0, h1 });
      adjChanged(true);
    };
    $("tDate").min = fc0; $("tDate").max = fc1; $("tDate").value = $("wDate").value;
    $("tScore").oninput = (e) => { $("oTraffic").textContent = e.target.value; };
    $("tDate").onchange = () => { $("tDate").dataset.user = "1"; loadTrafficInfo(); };
    $("tAdd").onclick = () => {
      const d = $("tDate").value;
      if (!d || d < fc0 || d > fc1) { toast(`Сценарий пробок задаётся на даты прогноза: ${fc0} — ${fc1}`); return; }
      a.traffic = a.traffic.filter((x) => x.date !== d).concat([{ date: d, score: +$("tScore").value }]);
      adjChanged(true);
    };
    $("tActual").onclick = () => { a.tActual = !a.tActual; adjChanged(true); };
    $("tEffect").onchange = (e) => { a.wTraffic = clampIn(e.target, 0, 5, 0.7); if (a.tActual || a.traffic.length) adjChanged(true); };
    $("adjReset").onclick = () => {
      Object.assign(a, JSON.parse(ADJ_DEFAULT));
      $("tEffect").value = 0.7;
      $("kLevel").value = 1; $("kSpecial").value = 1; $("wPrecip").value = -1.1; $("wCold").value = -3.4; $("wFloor").value = 0.9; $("kLevelScope").value = "all";
      $("oLevel").textContent = "×1,00"; $("oSpecial").textContent = "×1,00";
      adjChanged(true);
    };
    const syncInputs = () => {
      $("kLevel").value = a.level; $("kSpecial").value = a.special; $("wPrecip").value = a.precip; $("wCold").value = a.cold;
      $("wFloor").value = a.floor; $("kLevelScope").value = a.scope; $("tEffect").value = a.wTraffic;
      $("oLevel").textContent = `×${a.level.toFixed(2).replace(".", ",")}`; $("oSpecial").textContent = `×${a.special.toFixed(2).replace(".", ",")}`;
    };
    document.querySelectorAll(".grp-reset").forEach((b) => (b.onclick = (e) => {
      e.preventDefault(); e.stopPropagation();
      const d = JSON.parse(ADJ_DEFAULT);
      ({ level: () => { a.level = d.level; a.scope = d.scope; }, special: () => { a.special = d.special; },
         weather: () => { a.precip = d.precip; a.cold = d.cold; a.floor = d.floor; a.scn = []; },
         events: () => { a.events = []; }, traffic: () => { a.traffic = []; a.tActual = false; a.wTraffic = d.wTraffic; } })[b.dataset.grp]();
      syncInputs(); adjChanged(true);
    }));
    $("adjToggle").onclick = () => {
      const c = $("adjCard").classList.toggle("collapsed");
      $("adjToggle").setAttribute("aria-expanded", String(!c));
      localStorageSet("adjCollapsed", c ? "1" : "0");
    };
    if (localStorageGet("adjCollapsed") === "1") $("adjCard").classList.add("collapsed");
    for (const id of ["fCap", "fLoad", "fShare", "fTurn", "fSpeed", "fLay", "fHead"]) $(id).onchange = () => loadFleet().catch((e) => toast(e.message));
  }
  function clampIn(el, lo, hi, def) {
    let v = Number(String(el.value).replace(",", "."));
    if (!Number.isFinite(v)) v = def;
    v = Math.max(lo, Math.min(hi, v)); el.value = v; return v;
  }
  function renderAdjInfo() {
    const a = S.adj;
    $("wChips").innerHTML = a.scn.map((x, i) => `<span class="chip" data-i="${i}" title="Убрать">${short(x.date)}: ${x.mm >= 0 ? "+" : ""}${x.mm} мм${x.t !== null ? `, ${x.t} °C` : ""} ✕</span>`).join("");
    $("eChips").innerHTML = a.events.map((e, i) => `<span class="chip" data-i="${i}" title="Убрать">${e.route === "all" ? "все" : "№ " + e.route}, ${short(e.from)}–${short(e.to)}${e.h0 !== 0 || e.h1 !== 23 ? `, ${pad(e.h0)}–${pad(e.h1 + 1)} ч` : ""}: ×${String(e.k).replace(".", ",")} ✕</span>`).join("");
    [...$("wChips").children].forEach((c) => (c.onclick = () => { a.scn.splice(+c.dataset.i, 1); adjChanged(true); }));
    [...$("eChips").children].forEach((c) => (c.onclick = () => { a.events.splice(+c.dataset.i, 1); adjChanged(true); }));
    $("tChips").innerHTML = (a.tActual ? `<span class="chip" data-a="1" title="Убрать">факт ЦОДД ноя–дек ✕</span>` : "")
      + a.traffic.map((x, i) => `<span class="chip" data-i="${i}" title="Убрать">${short(x.date)}: ${x.score} балл. ✕</span>`).join("");
    [...$("tChips").children].forEach((c) => (c.onclick = () => { if (c.dataset.a) a.tActual = false; else a.traffic.splice(+c.dataset.i, 1); adjChanged(true); }));
    $("tActual").classList.toggle("on", a.tActual);
    const n = (a.level !== 1) + (a.special !== 1) + (a.precip !== -1.1 || a.cold !== -3.4 || a.floor !== 0.9) + a.scn.length
      + a.events.length + a.traffic.length + (a.tActual ? 1 : 0);
    $("adjCount").textContent = n ? `активно: ${n}` : "не заданы";
    $("adjCount").classList.toggle("on", n > 0);
    renderScenarioBadge(n);
    paintAdjControls();
    const q = new URLSearchParams(adjParams()).toString();
    $("adjApi").textContent = q ? `/api/v1/forecast?route=${S.route}&…&${decodeURIComponent(q)}` : "параметры не заданы (прогноз модели)";
    if (!adjActive()) $("adjDelta").innerHTML = `<span class="muted">прогноз модели без коррекции</span>`;
  }
  function renderAdjDelta(k) {
    if (!k.adjusted || !k.delta) {
      $("adjDelta").innerHTML = adjActive() && k.source === "history"
        ? `<span class="muted">выбран период факта — коррекция применяется только к прогнозу</span>`
        : `<span class="muted">прогноз модели без коррекции</span>`;
      return;
    }
    const d = k.delta, cls = d.pct > 0 ? "pos" : d.pct < 0 ? "neg" : "";
    const prev = S.lastDelta || d;
    $("adjDelta").innerHTML = `было <b>${fmt(d.total_before)}</b> → стало <b class="count" data-from="${prev.total_after}" data-to="${d.total_after}">${fmt(d.total_after)}</b> <b class="${cls}">(${sign(d.pct)} %)</b> <span class="muted">пасс. за выбранный период</span>`;
    S.lastDelta = d;
    countUp($("adjDelta").querySelector(".count"));
  }
  /** «было → стало»: the new total counts from the previous one (≈ 400 ms, off under reduced motion). */
  function countUp(el) {
    const a = +el.dataset.from, b = +el.dataset.to;
    if (!Number.isFinite(a) || a === b || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const t0 = performance.now(), dur = 420;
    const step = (t) => {
      const k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3);
      el.textContent = fmt(a + (b - a) * e);
      if (k < 1 && el.isConnected) requestAnimationFrame(step); else el.textContent = fmt(b);
    };
    requestAnimationFrame(step);
  }
  /** Drawer polish: range fill (blue track up to the orange thumb) and orange highlight on values changed from the model. */
  const ADJ_DEFAULTS = { kLevel: 1, kSpecial: 1, wPrecip: -1.1, wCold: -3.4, wFloor: 0.9, tEffect: 0.7 };
  function paintAdjControls() {
    document.querySelectorAll("#adjCard input[type=range]").forEach((r) => {
      const p = ((+r.value - +r.min) / ((+r.max - +r.min) || 1)) * 100;
      r.style.setProperty("--fill", `${p}%`);
    });
    for (const [id, def] of Object.entries(ADJ_DEFAULTS)) {
      const el = $(id);
      if (el) el.classList.toggle("changed", Math.abs(+el.value - def) > 1e-9);
    }
    const k = String($("eK")?.value);
    document.querySelectorAll(".ghost-btn[data-k]").forEach((b) => b.classList.toggle("on", b.dataset.k === k));
  }
  async function loadTrafficInfo() {
    // follows the dashboard date (forecast days) until the dispatcher picks another date in the traffic group
    if (!$("tDate").dataset.user && S.date >= S.coverage.forecast.from) $("tDate").value = S.date;
    const d = $("tDate").value || S.coverage.forecast.from;
    try {
      const t = await api("/traffic", { date_from: d, date_to: d });
      const x = t.days[0];
      const link = x.source_url ? ` <a href="${esc(x.source_url)}" target="_blank" rel="noopener">пост ЦОДД</a>` : "";
      $("tInfo").innerHTML = `${human(d)}: по ЦОДД ${x.reported ? `<b>${String(x.score).replace(".", ",")} балл.</b>${link}` : "поста нет (обычный день ≈ 4)"}, `
        + `норма 3 недель ${String(x.norm).replace(".", ",")}.` + (x.mult !== 1 ? ` Сценарий: ×${x.mult.toFixed(3).replace(".", ",")}.` : "");
    } catch { $("tInfo").textContent = "Данные ЦОДД о пробках не загружены."; }
  }
  async function loadWeatherInfo() {
    const d = S.date >= S.coverage.forecast.from ? S.date : S.coverage.forecast.from;
    try {
      const w = await api("/weather", { date_from: d, date_to: d });
      const x = w.days[0];
      const t = (v) => (v === null ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(1).replace(".", ",")}`);
      const scn = x.scenario ? ` · сценарий: ${x.scenario.add_mm >= 0 ? "+" : ""}${x.scenario.add_mm} мм${x.scenario.temp_c !== null ? `, ${x.scenario.temp_c} °C` : ""}` : "";
      $("wInfo").textContent = `${human(d)}: осадки ${t(x.precip_mm).replace("+", "")} мм, ${t(x.temp_c)} °C${scn}. Погодный множитель: модель ×${x.weather_mult_model.toFixed(3).replace(".", ",")} → ×${x.weather_mult.toFixed(3).replace(".", ",")}`;
    } catch { $("wInfo").textContent = ""; }
  }

  // ---------------- Map ----------------
  let layerLines, layerStops, mapData = null, markers = [];
  // Basemap: CartoDB Positron / Dark Matter now serve an «API KEY REQUIRED» watermark without a key, so the keyless
  // OSM tiles are used and styled per theme in CSS (a Positron-like grey in light, a Dark-Matter-like navy in dark).
  const tileUrl = () => "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
  function initMap() {
    // SVG renderer (≈350 stops): stop colour and size animate smoothly on hour change via CSS transitions
    S.map = L.map("map", { zoomControl: true, preferCanvas: false, scrollWheelZoom: false }).setView([55.765, 37.64], 11);
    S.tiles = L.tileLayer(tileUrl(), {
      maxZoom: 19, className: "basemap",
      attribution: '&copy; участники <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(S.map);
    layerLines = L.layerGroup().addTo(S.map);
    layerStops = L.layerGroup().addTo(S.map);
    // wheel zoom only after the user clicks the map, so page scrolling is not hijacked
    S.map.on("click focus", () => S.map.scrollWheelZoom.enable());
    S.map.on("mouseout", () => S.map.scrollWheelZoom.disable());
    if (window.ResizeObserver) new ResizeObserver(() => S.map.invalidateSize()).observe($("map"));
    applyTheme(localStorageGet("theme"));
    loadLiveTraffic();
  }
  /** Optional live layer (TomTom Flow Segment Data near stops): only when scripts/fetch_traffic.py ran with a working key. */
  async function loadLiveTraffic() {
    let live;
    try { live = await api("/traffic/live"); } catch { return; }
    if (!live.available || !live.points?.length) return;
    const layer = L.layerGroup();
    const col = (r) => (r === null ? css("--text-muted") : r < 0.5 ? css("--bad") : r < 0.75 ? css("--warn") : css("--good"));
    for (const p of live.points) {
      L.circleMarker([p.lat, p.lon], { radius: 6, weight: 0, fillOpacity: 0.45, fillColor: col(p.ratio), interactive: true })
        .bindTooltip(`Пробки TomTom у «${esc(p.name)}»: ${p.current_speed ?? "—"} км/ч при свободной ${p.free_flow_speed ?? "—"} км/ч`
          + (p.road_closure ? " · перекрытие" : ""), { direction: "top" }).addTo(layer);
    }
    L.control.layers(null, { [`Пробки TomTom (сейчас, ${new Date(live.fetched_at).toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" })})`]: layer },
      { collapsed: false, position: "topright" }).addTo(S.map);
  }
  const seqColors = () => [0, 1, 2, 3, 4, 5, 6].map((i) => css(`--seq-${i}`));
  function colorFor(v, max) {
    if (v === null || v === undefined) return css("--route-line");
    const c = seqColors();
    const t = max > 0 ? Math.min(1, v / max) : 0;
    return c[Math.min(c.length - 1, Math.floor(t * (c.length - 0.001)))];
  }
  async function loadMap() {
    const d = S.date; // map is always a one-day, hourly snapshot
    const src = srcFor(d);
    $("mapBadge").textContent = `${src === "history" ? "факт" : "прогноз"} · ${human(d)} · оценка по остановкам`;
    const r = S.route;
    const geo = r === "all" || S.routes.find((x) => x.route === r)?.has_geometry;
    layerLines.clearLayers(); layerStops.clearLayers(); markers = []; mapData = null;
    const note = $("mapNote");
    if (!geo) {
      note.innerHTML = `Геопривязка остановок недоступна для маршрута № ${r}.<br>Прогноз маршрута доступен на графиках и в таблице.`;
      note.classList.remove("hidden"); S.lastFit = null; $("topStops").innerHTML = `<li class="empty">Геопривязка остановок недоступна для маршрута</li>`;
      $("hourSum").textContent = ""; paintLegend(0); return;
    }
    const data = await api("/map", { route: r, date: d, source: src });
    mapData = data;
    const launch = r !== "all" ? launchOf(r) : null;
    if (!routeHasData(r)) {
      note.innerHTML = `Для маршрута № ${r} нет данных о пассажиропотоке — показана только схема остановок.`;
      note.classList.remove("hidden");
    } else if (launch && d < launch) {
      note.innerHTML = `Маршрут № ${r} — новый: запуск ${human(launch)}.<br>До этой даты пассажиропотока нет — выберите дату с ${short(launch)}.`;
      note.classList.remove("hidden");
    } else note.classList.add("hidden");
    for (const [route, dirs] of Object.entries(data.lines)) {
      for (const pts of Object.values(dirs)) {
        L.polyline(pts, { color: css("--route-line"), weight: 3, opacity: 0.7 }).bindTooltip(`Маршрут № ${route}`, { sticky: true }).addTo(layerLines);
      }
    }
    for (const s of data.stops) {
      const m = L.circleMarker([s.lat, s.lon], { radius: 4, weight: 1.5, color: css("--surface-1"), fillOpacity: 0.9, className: "stop-dot" });
      m.on("click", () => openStop(s, m));
      m.bindTooltip("", { direction: "top", offset: [0, -4] });
      m.addTo(layerStops);
      markers.push([s, m]);
    }
    S.map.invalidateSize();
    if (data.stops.length && S.lastFit !== r) S.lastFit = r, S.map.fitBounds(L.latLngBounds(data.stops.map((s) => [s.lat, s.lon])), { padding: [20, 20], maxZoom: 13 });
    paintHour();
  }
  function paintLegend(max) {
    const c = seqColors();
    $("legend").innerHTML = max > 0
      ? `пасс./час на остановке<div class="ramp" style="background:linear-gradient(90deg, ${c.join(", ")})"></div><div class="ends"><span>0</span><span>${fmt(max)}</span></div>`
      : `нет данных для раскраски`;
  }
  function paintHour() {
    $("hourLbl").textContent = `${pad(S.hour)}:00–${pad((S.hour + 1) % 24)}:00`;
    if (!mapData) return;
    const max = mapData.max_value || 0;
    paintLegend(max);
    for (const [s, m] of markers) {
      const v = s.values ? s.values[S.hour] : null;
      const rad = v === null ? 3 : 2.5 + 10 * Math.sqrt(max ? v / max : 0);
      m.setRadius(rad);
      m.setStyle({ fillColor: colorFor(v, max), color: css("--surface-1") });
      m.setTooltipContent(`<b>${s.name}</b><br>маршрут № ${s.route}${s.hub ? " · пересадка" : ""}<br>${v === null ? "нет данных" : `≈ ${fmt(v)} пасс./час`}`);
    }
    let sum = 0, any = false;
    for (const h of Object.values(mapData.route_hourly || {})) if (h[S.hour] !== null) { sum += h[S.hour]; any = true; }
    $("hourSum").textContent = any ? `${fmt(sum)} пасс./час на карте` : "";
    renderTop();
  }
  function renderTop() {
    const agg = new Map();
    for (const [s] of markers) {
      if (!s.values || s.values[S.hour] === null) continue;
      const cur = agg.get(s.stop_id) || { s, v: 0, routes: new Set() };
      cur.v += s.values[S.hour]; cur.routes.add(s.route); agg.set(s.stop_id, cur);
    }
    // merge same-name platforms (both directions) for readability
    const byName = new Map();
    for (const x of agg.values()) {
      const k = x.s.name;
      const cur = byName.get(k) || { s: x.s, v: 0, routes: new Set() };
      cur.v += x.v; x.routes.forEach((r) => cur.routes.add(r)); byName.set(k, cur);
    }
    const top = [...byName.values()].sort((a, b) => b.v - a.v).slice(0, 10);
    $("topTitle").textContent = `Самые загруженные остановки, ${pad(S.hour)}:00`;
    if (!top.length) { $("topStops").innerHTML = `<li class="empty">Нет данных для выбранного часа</li>`; return; }
    const mx = top[0].v || 1;
    $("topStops").innerHTML = top.map((x) => `<li data-id="${x.s.stop_id}"><div class="nm">${esc(x.s.name)}<small>№ ${[...x.routes].join(", ")}</small><div class="bar" style="width:${Math.max(4, (x.v / mx) * 100)}%"></div></div><span class="v">≈ ${fmt(x.v)}</span></li>`).join("");
    [...$("topStops").children].forEach((li) => (li.onclick = () => {
      const hit = markers.find(([s]) => s.stop_id === li.dataset.id);
      if (hit) { S.map.setView(hit[1].getLatLng(), 14); openStop(hit[0], hit[1]); }
    }));
  }
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  function openStop(s, m) {
    const v = s.values ? s.values[S.hour] : null;
    const div = document.createElement("div");
    div.className = "pop";
    div.innerHTML = `<b>${esc(s.name)}</b><div class="m">ID ${s.stop_id} · маршрут № ${s.route} · направление ${s.direction === 0 ? "прямое" : "обратное"}</div>
      <div>${pad(S.hour)}:00 — ${v === null ? "нет данных" : `≈ ${fmt(v)} пасс.`}</div><div class="m">доля остановки в маршруте ${(s.share * 100).toFixed(1)}%</div>`;
    if (s.values) {
      const b = document.createElement("button");
      b.textContent = "Показать динамику остановки";
      b.onclick = () => { S.stop = s.stop_id; S.stopName = s.name; S.map.closePopup(); refresh(); document.getElementById("lineChart").scrollIntoView({ behavior: "smooth", block: "center" }); };
      div.appendChild(b);
    }
    m.bindPopup(div).openPopup();
  }
  function togglePlay() {
    if (S.playing) { clearInterval(S.playing); S.playing = null; $("play").textContent = "▶"; return; }
    $("play").textContent = "❚❚";
    S.playing = setInterval(() => { S.hour = (S.hour + 1) % 24; $("hour").value = S.hour; paintHour(); }, 700);
  }

  // ---------------- Charts ----------------
  const charts = { line: null, heat: null, fleet: null };
  let lastLine = null, lastHeat = null;
  // Charts must follow their container, not only the window: if a chart is first drawn while the page or card is
  // hidden or still being laid out (background tab, collapsed preview pane, mobile reflow), ECharts falls back to a
  // 100 px canvas and stays blank-looking until the next window resize. The map already recovers via its own observer.
  const chartObserver = window.ResizeObserver ? new ResizeObserver((entries) => {
    for (const e of entries) {
      const c = echarts.getInstanceByDom(e.target);
      if (c && e.contentRect.width > 0 && e.contentRect.height > 0
          && (c.getWidth() !== Math.round(e.contentRect.width) || c.getHeight() !== Math.round(e.contentRect.height))) c.resize();
    }
  }) : null;
  function chart(id, key) {
    if (!charts[key] || charts[key].isDisposed()) {
      charts[key] = echarts.init($(id), null, { renderer: "canvas" });
      chartObserver?.observe($(id));
    }
    return charts[key];
  }
  document.addEventListener("visibilitychange", () => { if (!document.hidden) Object.values(charts).forEach((c) => c && !c.isDisposed() && c.resize()); });
  function baseOpt() {
    const t2 = css("--text-secondary"), grid = css("--grid");
    return {
      textStyle: { fontFamily: "Onest, system-ui, sans-serif", color: t2 },
      animationDuration: 450, animationDurationUpdate: 350, animationEasing: "cubicOut", animationEasingUpdate: "cubicOut",
      grid: { left: 56, right: 18, top: 36, bottom: 44 },
      // Round 6 chart theme: rounded tooltip with shadow, pale dashed grid, clickable legend (hover highlights a series)
      tooltip: { trigger: "axis", backgroundColor: css("--surface-raised"), borderColor: css("--border"), borderWidth: 1, padding: [8, 12],
        textStyle: { color: css("--text-primary"), fontFamily: "Onest, system-ui, sans-serif", fontSize: 12.5 },
        extraCssText: `border-radius:12px;box-shadow:${css("--sh-md")};`,
        axisPointer: { type: "line", lineStyle: { color: css("--border-strong"), width: 1 } },
        valueFormatter: (v) => (v === null || v === undefined ? "—" : fmt(v)) },
      legend: { top: 0, left: 0, textStyle: { color: t2 }, itemWidth: 14, itemHeight: 8, itemGap: 20, icon: "roundRect",
        inactiveColor: css("--border-strong"), selectedMode: true },
      emphasis: { focus: "series" },
      yAxis: { type: "value", splitLine: { lineStyle: { color: grid, type: [4, 4] } }, axisLabel: { color: t2, formatter: (v) => fmt(v) } },
    };
  }
  const xAxis = (data, extra = {}) => ({ type: "category", data, axisLine: { lineStyle: { color: css("--border") } }, axisTick: { show: false }, axisLabel: { color: css("--text-secondary") }, ...extra });
  const line = (name, data, color, extra = {}) => ({ name, type: "line", data, showSymbol: false, symbolSize: 8, connectNulls: false, lineStyle: { width: 2, color }, itemStyle: { color }, ...extra });

  async function stopOrRoute(source, from, to, gran) {
    const params = { date_from: from, date_to: to, granularity: gran, ...hours() };
    if (S.stop) return api("/forecast/stop", { stop_id: S.stop, source, ...params });
    return api("/series", { route: S.route, source, ...params });
  }

  async function loadLine() {
    const c1 = css("--series-1"), c2 = css("--series-2");
    setEmpty("lineChart", null);
    if (!routeHasData(S.route)) { chart("lineChart", "line").clear(); $("lineHint").textContent = "Для маршрута нет данных о пассажиропотоке."; setEmpty("lineChart", "Для маршрута нет данных о пассажиропотоке"); return; }
    const who = S.stop ? `остановка «${S.stopName}» (оценка)` : S.route === "all" ? "все маршруты" : `маршрут № ${S.route}`;
    let opt, lineNote = "";
    if (S.horizon === "day") {
      const src = srcFor(S.date);
      // comparison: same weekday, latest actual day before the selected date
      const d = parse(S.date);
      let cmp = new Date(d); cmp.setDate(cmp.getDate() - 7);
      const he = parse(histEnd());
      while (cmp > he) cmp.setDate(cmp.getDate() - 7);
      const cmpStr = iso(cmp);
      const hasCmp = cmpStr >= S.coverage.history.from && routeHasHistory(S.route);
      const [main, ref] = await Promise.all([
        stopOrRoute(src, S.date, S.date, "hour"),
        hasCmp ? stopOrRoute("history", cmpStr, cmpStr, "hour") : Promise.resolve(null),
      ]);
      const hrs = main.points.map((p) => `${pad(p.hour)}:00`);
      const series = [line(`${src === "history" ? "Факт" : main.adjusted ? "Прогноз с коррекцией" : "Прогноз"}${main.model === "hybrid" ? " (гибрид ML)" : ""}, ${short(S.date)} (${WD[d.getDay()]})`, main.points.map((p) => p.value), src === "history" ? c1 : c2, { showSymbol: true })];
      if (main.adjusted) series.push(line("Прогноз модели (без коррекции)", main.baseline.values, css("--text-muted"), { lineStyle: { width: 2, type: "dashed", color: css("--text-muted") } }));
      if (ref) series.unshift(line(`Факт, ${short(cmpStr)} (тот же день недели)`, ref.points.map((p) => p.value), c1, src === "history" ? { lineStyle: { width: 2, color: c1, type: "dashed" } } : {}));
      const band = bandOf(main);
      if (band) series.push(...bandSeries(band, c2));
      const dayAn = src === "history" ? await anomaliesFor(S.date, S.date) : [];
      opt = { ...baseOpt(), xAxis: xAxis(hrs), series };
      opt.tooltip = { ...opt.tooltip, formatter: lineTooltip(band, null) };
      opt.legend = { ...opt.legend, data: series.map((x) => x.name).filter((n) => !n.startsWith("_")) };
      if (dayAn.length) lineNote = " ИИ-детектор: " + dayAn.map((e) => `${e.kind_ru} (маршрут ${e.route}): ${e.label}`).join("; ") + ".";
      $("lineTitle").textContent = `Почасовая загрузка: ${who}`;
      $("lineHint").textContent = (ref ? "Сравнение с последним фактическим днём той же недели. " : "Факта для сравнения нет (новый маршрут). ") + `Часы ${pad(S.hourFrom)}:00–${pad(S.hourTo)}:59.`
        + (band ? " Заливка — 80 % интервал прогноза (P10–P90): с вероятностью 80 % фактическая загрузка окажется внутри." : "") + lineNote;
    } else if (S.horizon === "month") {
      const [a, b] = monthRange(S.month);
      const src = srcFor(a);
      if (src === "history" && !routeHasHistory(S.route)) {
        chart("lineChart", "line").clear(); lastLine = null;
        $("lineTitle").textContent = `Суточные итоги: ${who}`; $("lineHint").textContent = "Факта нет: маршрут новый.";
        setEmpty("lineChart", `Факта нет: маршрут № ${S.route} запущен ${human(launchOf(S.route))}`); return;
      }
      const r = await stopOrRoute(src, a, b, "day");
      const days = r.points.map((p) => p.date);
      const color = src === "history" ? c1 : c2;
      const bars = { name: src === "history" ? "Факт, пасс./сутки" : (r.adjusted ? "Прогноз с коррекцией" : "Прогноз") + (r.model === "hybrid" ? " (гибрид ML)" : "") + ", пасс./сутки", type: "bar", barWidth: "62%",
        data: r.points.map((p) => ({ value: p.value, itemStyle: { color, opacity: [0, 6].includes(parse(p.date).getDay()) ? 0.55 : 1, borderRadius: [4, 4, 0, 0] } })),
        itemStyle: { color } };
      const series = [bars];
      if (r.adjusted) series.push(line("Прогноз модели (без коррекции)", r.baseline.values, css("--text-muted"), { showSymbol: true, symbolSize: 5, lineStyle: { width: 2, type: "dashed", color: css("--text-muted") } }));
      const band = bandOf(r);
      if (band) series.push(...bandSeries(band, color));
      let anByIdx = null;
      if (src === "history" && !S.stop) {
        const ev = await anomaliesFor(a, b);
        if (ev.length) {
          anByIdx = {};
          ev.forEach((e) => { const i = days.indexOf(e.date); if (i >= 0) (anByIdx[i] = anByIdx[i] || []).push(e); });
          const cBad = css("--bad"), cWarn = css("--warn");
          series.push({ name: "Аномалия (ИИ-детектор)", type: "scatter", symbolSize: 11, z: 5,
            data: days.map((_, i) => anByIdx[i] ? { value: [i, (r.points[i].value || 0) * 1.05], itemStyle: { color: anByIdx[i].some((e) => e.kind === "drop") ? cBad : cWarn, borderColor: css("--surface-1"), borderWidth: 2 } } : null).filter(Boolean),
            itemStyle: { color: cBad } });
        }
      }
      opt = { ...baseOpt(), xAxis: xAxis(days.map((x) => `${short(x)} ${WD[parse(x).getDay()]}`), { axisLabel: { color: css("--text-secondary"), interval: 1, rotate: 0, fontSize: 11 } }), series };
      opt.tooltip = { ...opt.tooltip, formatter: lineTooltip(band, anByIdx) };
      opt.legend = { ...opt.legend, data: series.map((x) => x.name).filter((n) => !n.startsWith("_")) };
      if (band) lineNote = " Заливка — 80 % интервал прогноза (P10–P90).";
      if (anByIdx) lineNote = ` Точки — аномальные дни по ИИ-детектору (${Object.keys(anByIdx).length}): красная — провал, жёлтая — всплеск или нетипичный профиль.`;
      $("lineTitle").textContent = `Суточные итоги за ${MONTHS[parse(a).getMonth()]} 2025: ${who}`;
      const sm = r.summary;
      $("lineHint").textContent = `Всего ${fmt(sm.total)} пасс., в среднем ${fmt(sm.avg_per_day)} в сутки. Выходные показаны светлее.` + (r.adjusted ? ` Коррекция: ${sign(r.delta.pct)} % к прогнозу модели.` : "") + lineNote;
    } else {
      if (S.stop) { S.stop = null; $("stopChip").classList.add("hidden"); }
      const y = await api("/scenario/year", { route: S.route, growth: S.growth, band: S.band });
      const labels = y.months.map((m) => `${m.label.slice(0, 3)} ${String(y.scenario_year).slice(2)}`);
      const lo = y.months.map((m) => Math.round(m.low / 1000)), span = y.months.map((m) => Math.round((m.high - m.low) / 1000));
      const tot = y.months.map((m) => Math.round(m.forecast_total / 1000));
      const prev = y.months.map((m) => m.base_2025_avg_per_day ? Math.round(m.base_2025_avg_per_day * new Date(y.scenario_year - 1, m.month, 0).getDate() / 1000) : null);
      const bandColor = css("--seq-1");
      opt = {
        ...baseOpt(), xAxis: xAxis(labels),
        grid: { left: 56, right: 18, top: 56, bottom: 44 },
        yAxis: { ...baseOpt().yAxis, name: "тыс. пасс. в месяц", nameTextStyle: { color: css("--text-secondary"), align: "left" } },
        tooltip: { ...baseOpt().tooltip, valueFormatter: (v) => (v === null || v === undefined ? "—" : `${fmt(v)} тыс.`) },
        series: [
          { name: "_lo", type: "line", data: lo, stack: "band", lineStyle: { opacity: 0 }, symbol: "none", tooltip: { show: false }, silent: true },
          { name: `Коридор ±${y.band_pct} %`, type: "line", data: span, stack: "band", lineStyle: { opacity: 0 }, symbol: "none", areaStyle: { color: bandColor, opacity: 0.45 }, itemStyle: { color: bandColor }, silent: true },
          { name: `${y.scenario_year}: сценарный прогноз`, type: "bar", data: tot, barWidth: "46%", itemStyle: { color: css("--series-1"), borderRadius: [4, 4, 0, 0] }, z: 3 },
          line(`${y.scenario_year - 1}: факт (янв–окт) и прогноз модели (ноя–дек)`, prev, css("--series-2"), { showSymbol: true, symbolSize: 6, z: 4 }),
        ],
      };
      opt.legend = { ...opt.legend, data: [`${y.scenario_year}: сценарный прогноз`, `Коридор ±${y.band_pct} %`, `${y.scenario_year - 1}: факт (янв–окт) и прогноз модели (ноя–дек)`] };
      $("lineTitle").textContent = `Год ${y.scenario_year}: сценарный прогноз по месяцам — ${who}`;
      $("lineHint").textContent = `СЦЕНАРНЫЙ ПРОГНОЗ. ${y.method}. Итого за ${y.scenario_year}: ≈ ${fmt(y.total)} пасс. (${fmt(y.total_low)} – ${fmt(y.total_high)}).` + (y.notes.length ? " " + y.notes.join(" ") : "");
    }
    lastLine = opt;
    chart("lineChart", "line").setOption(opt, true);
    requestAnimationFrame(() => $("lineChart").classList.remove("fade"));
  }

  async function loadHeat() {
    const card = $("heatCard");
    if (!routeHasData(S.route)) { card.classList.add("hidden"); return; }
    card.classList.remove("hidden");
    let rows, cols, data, title;
    if (S.horizon === "year") {
      const r = await api("/series", { route: S.route, source: "combined", granularity: "hour", ...hours() });
      const acc = {};
      for (const p of r.points) {
        if (p.value === null) continue;
        const m = +p.date.slice(5, 7) - 1, k = `${m}|${p.hour}`;
        acc[k] = acc[k] || [0, 0]; acc[k][0] += p.value; acc[k][1]++;
      }
      rows = MONTHS.map((m) => m.slice(0, 3));
      cols = [...Array(S.hourTo - S.hourFrom + 1).keys()].map((i) => S.hourFrom + i);
      data = []; rows.forEach((_, m) => cols.forEach((h, j) => { const a = acc[`${m}|${h}`]; data.push([j, m, a ? Math.round(a[0] / a[1]) : null]); }));
      title = "Тепловая карта: месяц × час (среднее, янв–окт факт, ноя–дек прогноз)";
    } else {
      const ym = S.horizon === "day" ? S.date.slice(0, 7) : S.month;
      const [a, b] = monthRange(ym);
      const r = await stopOrRoute("combined", a, b, "hour");
      const days = [...new Set(r.points.map((p) => p.date))];
      rows = days.map((d) => `${short(d)} ${WD[parse(d).getDay()]}`);
      cols = [...Array(S.hourTo - S.hourFrom + 1).keys()].map((i) => S.hourFrom + i);
      const di = new Map(days.map((d, i) => [d, i]));
      data = r.points.map((p) => [p.hour - S.hourFrom, di.get(p.date), p.value]);
      title = `Тепловая карта: день × час, ${MONTHS[parse(a).getMonth()]} 2025 (${a <= histEnd() ? "факт" : "прогноз"})`;
    }
    $("heatTitle").textContent = title;
    const vals = data.map((d) => d[2]).filter((v) => v !== null);
    const max = vals.length ? Math.max(...vals) : 1;
    const t2 = css("--text-secondary");
    const opt = {
      textStyle: { fontFamily: "Onest, system-ui, sans-serif", color: t2 },
      tooltip: { backgroundColor: css("--surface-1"), borderColor: css("--border"), textStyle: { color: css("--text-primary") },
        formatter: (p) => `${rows[p.value[1]]}, ${pad(cols[p.value[0]])}:00<br><b>${fmt(p.value[2])}</b> пасс.` },
      grid: { left: 78, right: 20, top: 10, bottom: 70 },
      xAxis: { type: "category", data: cols.map((h) => pad(h)), splitArea: { show: false }, axisLabel: { color: t2 }, axisTick: { show: false }, axisLine: { show: false } },
      yAxis: { type: "category", data: rows, inverse: true, axisLabel: { color: t2, fontSize: 11 }, axisTick: { show: false }, axisLine: { show: false } },
      visualMap: { min: 0, max, calculable: true, orient: "horizontal", left: "center", bottom: 4, itemHeight: 180, itemWidth: 10,
        inRange: { color: seqColors() }, textStyle: { color: t2 }, formatter: (v) => fmt(v) },
      series: [{ type: "heatmap", data, itemStyle: { borderColor: css("--surface-1"), borderWidth: 1, borderRadius: 2 },
        emphasis: { itemStyle: { borderColor: css("--text-primary"), borderWidth: 1 } } }],
    };
    lastHeat = opt;
    chart("heatChart", "heat").setOption(opt, true);
  }

  async function loadTable() {
    const p = period();
    const rows = await Promise.all(S.routes.map(async (r) => {
      if (!r.has_data) return { r, k: null };
      try { return { r, k: await api("/kpi", { route: r.route, date_from: p.from, date_to: p.to, source: p.source, ...hours() }) }; }
      catch { return { r, k: null }; }
    }));
    $("tableSub").textContent = `${p.source === "history" ? "факт" : p.source === "forecast" ? "прогноз" : "факт + прогноз"}, ${p.from === p.to ? human(p.from) : `${p.from} — ${p.to}`}`;
    $("routeTable").querySelector("thead").innerHTML = `<tr><th>Маршрут</th><th>Название</th><th class="num">Платформ на карте</th><th class="num">Пассажиров</th><th class="num">В среднем в сутки</th><th class="num">Пиковый час</th><th class="num">Макс. за час</th><th class="num">К прошлому месяцу</th></tr>`;
    $("routeTable").querySelector("tbody").innerHTML = rows.map(({ r, k }) => {
      const ch = k?.change_vs_prev_month?.pct;
      return `<tr data-r="${r.route}" class="${S.route === r.route ? "sel" : ""}"><td><b>№ ${r.route}</b></td><td>${esc(r.name || "—")}</td>
        <td class="num">${r.has_geometry ? r.n_stops : `<span class="muted" title="геопривязка остановок недоступна для маршрута">нет геопривязки</span>`}</td>
        <td class="num">${k && !(r.launch_date && k.total === 0) ? fmt(k.total) : r.launch_date ? `<span class="muted">запуск ${short(r.launch_date)}</span>` : `<span class="muted">нет данных</span>`}</td><td class="num">${k ? fmt(k.avg_per_day) : "—"}</td>
        <td class="num">${k && k.peak_hour !== null && k.total ? pad(k.peak_hour) + ":00" : "—"}</td><td class="num">${k ? fmt(k.max_hourly) : "—"}</td>
        <td class="num">${ch === undefined || ch === null || S.horizon === "year" ? "—" : (ch > 0 ? "+" : "") + ch.toLocaleString("ru-RU") + "%"}</td></tr>`;
    }).join("");
    [...$("routeTable").querySelectorAll("tbody tr")].forEach((tr) => (tr.onclick = () => {
      S.route = tr.dataset.r; S.stop = null; $("route").value = S.route; refresh(); window.scrollTo({ top: 0, behavior: "smooth" });
    }));
  }

  async function loadExplain() {
    const box = $("explainBox");
    if (!S.explainAvailable || S.route === "all" || !routeHasData(S.route) || srcFor(S.date) !== "forecast") { box.classList.add("hidden"); return; }
    const e = await api("/explain", { route: S.route, date: S.date }).catch(() => null);
    if (!e || !e.available) { box.classList.add("hidden"); return; }
    const row = e.hours.find((h) => h.hour === S.hour) || e.hours[0];
    const names = {
      special_mult: "Особый день (праздник/перенос)",
      weather_mult: "Погода (осадки, мороз)",
      rules_mult: "Сетевые события (запуск маршрута 5 с 16.12, бесплатный проезд в новогоднюю ночь)",
      daytype_mult: "Тип дня", trend_mult: "Тренд",
    };
    const pred = row.prediction ?? row.prediction_recomputed;
    const dash = (v) => (v === 1 ? "×1 (нет влияния)" : `×${v.toFixed(3)}`);
    box.classList.remove("hidden");
    $("explainBody").innerHTML = `<p class="hint" style="margin:0 0 6px">Маршрут № ${e.route}, ${human(e.date)}, час ${pad(row.hour)}:00 (меняется ползунком карты)</p>` +
      `<table><tr><td>Базовый профиль (уровень × суточная форма)</td><td>${fmt(row.base)}</td></tr>` +
      e.factors.map((f) => `<tr><td>${names[f] || f}</td><td>${dash(row[f])}</td></tr>`).join("") +
      `<tr><td><b>= Прогноз на час</b></td><td>${fmt(pred)}</td></tr>` +
      (S.model === "hybrid" && row.ml_ratio !== undefined && row.ml_ratio !== null
        ? (S.hybridZero
          ? `<tr><td>ML-поправка LightGBM (справочно: в финале вес 0)</td><td>×${row.ml_ratio.toFixed(3)}</td></tr>`
          : `<tr><td>ML-поправка (LightGBM)</td><td>×${row.ml_ratio.toFixed(3)}</td></tr><tr><td><b>= Прогноз гибрида</b></td><td>${fmt(row.prediction_hybrid)}</td></tr>`) : "") +
      `<tr><td class="muted">За сутки: база → прогноз</td><td class="muted">${fmt(e.daily.base)} → ${fmt(e.daily.prediction)}</td></tr></table>` +
      (Math.abs((row.prediction ?? row.prediction_recomputed) - row.prediction_recomputed) > Math.max(2, 0.02 * row.prediction_recomputed)
        ? `<p class="hint">Прогноз на этот час задан отдельным правилом (например, для нового маршрута) и не равен произведению множителей.</p>` : "") +
      (row.note ? `<p class="hint">Примечание модели: ${esc(row.note)}</p>` : "");
  }

  async function loadDataQuality() {
    try {
      const r = await api("/pipeline/report");
      const g = r.ingest || {};
      const rows = [];
      if (g.raw_rows) rows.push(["Сырых записей валидаций", fmt(g.raw_rows)]);
      if (g.clean_rows) rows.push(["Валидных после очистки", `${fmt(g.clean_rows)} (${((g.clean_rows / g.raw_rows) * 100).toFixed(1).replace(".", ",")}%)`]);
      if (g.runtime_s) rows.push(["Время обработки", `${g.runtime_s} с`]);
      if (g.label_match_pct !== undefined && g.label_match_pct !== null) rows.push(["Совпадение с разметкой организаторов", `${String(g.label_match_pct).replace(".", ",")}% (${fmt(g.label_cells_exact_match)} из ${fmt(g.label_cells)})`]);
      if (r.stops_bound) rows.push(["Остановок, привязанных к маршрутам", fmt(r.stops_bound)]);
      if (!rows.length) return;
      $("dqBody").innerHTML = `<table>${rows.map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join("")}</table>`;
      $("dqBox").classList.remove("hidden");
    } catch { /* report is optional */ }
  }

  async function loadFleet() {
    const card = $("fleetCard");
    if (!routeHasData(S.route)) { card.classList.add("hidden"); renderOverflowKpi(null); renderRisk(null); return; }
    card.classList.remove("hidden");
    const d = S.date;
    const val = (id) => ($(id).value === "" ? null : $(id).value);
    const r = await api("/fleet", { route: S.route, date: d, capacity: val("fCap"), load_target: val("fLoad"), peak_share: val("fShare"),
      turnover: val("fTurn"), speed: val("fSpeed"), layover: val("fLay"), max_headway: val("fHead"), plan_by: S.planP90 ? "p90" : null });
    renderOverflowKpi(r);
    renderRisk(r);
    $("fleetDate").textContent = human(d);
    $("fleetBadge").textContent = `${r.source === "history" ? "по факту" : r.adjusted ? "по прогнозу с коррекцией" : "по прогнозу"} · ${short(d)}`;
    const one = r.routes.length === 1 ? r.routes[0] : null;
    const rows = one ? one.hours : r.total_hours.map((h) => ({ ...h, status: h.required > h.plan ? "risk" : h.required < h.plan ? "surplus" : h.required ? "ok" : "none" }));
    // Round 6 fleet palette: blue = enough trams, orange = add trams, red = overflow likely (P ≥ 50 % or load ≥ 125 % of target)
    const cOver = css("--danger"), cRisk = css("--accent"), cOk = css("--primary"), cSur = css("--seq-2"), cPlan = css("--text-secondary");
    const colorOf = (st, x) => ((x && ((x.p_overflow ?? 0) >= 0.5 || (x.load_at_plan_pct ?? 0) >= 125)) ? cOver
      : st === "risk" ? cRisk : st === "surplus" ? cSur : cOk);
    const hrs = rows.map((x) => `${pad(x.hour)}`);
    const hasP = r.overflow && r.overflow.available;
    const opt = {
      ...baseOpt(),
      tooltip: { ...baseOpt().tooltip, valueFormatter: (v) => (v === null || v === undefined ? "—" : fmt(v)) },
      xAxis: xAxis(hrs),
      grid: { left: 44, right: hasP ? 46 : 12, top: 36, bottom: 30 },
      yAxis: hasP ? [baseOpt().yAxis, { type: "value", min: 0, max: 100, splitLine: { show: false }, axisLabel: { color: css("--text-secondary"), formatter: "{value} %" } }] : baseOpt().yAxis,
      series: [
        { name: "Требуется вагонов на линии", type: "bar", barWidth: "60%", data: rows.map((x) => ({ value: x.required, itemStyle: { color: colorOf(x.status, x), borderRadius: [5, 5, 0, 0] } })), itemStyle: { color: cOk } },
        { name: one && one.plan_source.startsWith("нет истории") ? "Текущий выпуск (нет данных)" : "Текущий выпуск (оценка по факту 4 недель)", type: "line", step: "middle", data: rows.map((x) => x.plan), showSymbol: false, lineStyle: { color: cPlan, width: 2, type: [6, 5], dashOffset: 0 }, itemStyle: { color: cPlan }, z: 4 },
      ],
    };
    if (hasP) opt.series.push({ name: "Вероятность переполнения, %", type: "line", yAxisIndex: 1, smooth: true, showSymbol: false,
      data: rows.map((x) => (x.p_overflow === null || x.p_overflow === undefined ? null : Math.round(x.p_overflow * 100))),
      lineStyle: { color: cOver, width: 2 }, itemStyle: { color: cOver },
      tooltip: { valueFormatter: (v) => (v === null || v === undefined ? "—" : `${v} %`) } });
    chart("fleetChart", "fleet").setOption(opt, true);
    animateSupplyLine();
    const recs = r.recommendations;
    const tag = { risk: ["risk", "риск давки"], surplus: ["surplus", "резерв"], info: ["info", "новый"] };
    // Round 6: recommendation cards (coloured stripe, icon, «Применить» = show that route and hour on «Обзор»)
    const recIcon = { risk: '<path d="M12 5v14M5 12h14"/>', surplus: '<path d="M5 12h14"/>', info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8v.5"/>' };
    $("fleetRecs").innerHTML = recs.length
      ? recs.slice(0, 14).map((x, i) => `<li class="rec ${tag[x.type][0]}"><span class="rec-ico" aria-hidden="true"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round">${recIcon[x.type] || recIcon.info}</svg></span>
          <span class="rec-body"><span class="tag ${tag[x.type][0]}">${tag[x.type][1]}</span><span>${esc(x.text)}</span></span>
          ${x.route ? `<button class="btn small rec-apply" data-i="${i}" title="Открыть маршрут № ${esc(x.route)}${x.from !== null ? ` и ${pad(x.from)}:00` : ""} на «Обзоре»">Применить</button>` : ""}</li>`).join("")
      : `<li class="rec info"><span class="rec-ico" aria-hidden="true"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M5 12l5 5 9-10"/></svg></span><span class="rec-body"><span class="tag info">норма</span><span>Выпуск соответствует прогнозу: изменений не требуется.</span></span></li>`;
    [...$("fleetRecs").querySelectorAll(".rec-apply")].forEach((b) => (b.onclick = () => {
      const x = recs[+b.dataset.i];
      applyQuery({ route: x.route, date_from: r.date, date_to: r.date, hour_ranges: x.from !== null ? [[x.from, x.to]] : [], corrections: {} }, null);
    }));
    const a = r.assumptions;
    $("fleetTitle").textContent = `Выпуск подвижного состава: ${S.route === "all" ? "все маршруты" : "маршрут № " + S.route}`;
    $("fleetHint").textContent = (one ? `Маршрут ${one.route}: длина ${String(one.length_km).replace(".", ",")} км (${one.length_source}), оборот ${fmt(one.round_trip_min)} мин, `
      + `${one.vehicle_model}, вместимость ${one.capacity} пасс., ${String(one.passengers_per_vehicle_per_hour).replace(".", ",")} пасс./ч на вагон при целевой загрузке. ` : "")
      + `Формула: ${a.formula}. Скорость ${String(a.speed_kmh).replace(".", ",")} км/ч (${a.speed_source}). Синий — вагонов хватает (светлее — резерв), оранжевый — нужно добавить вагоны, красный — вероятно переполнение (P ≥ 50 % или загрузка ≥ 125 % целевой). `
      + `Текущий выпуск оценён по фактическому спросу 4 предыдущих недель (тот же день недели), т. к. фактических нарядов по часам в данных нет.`
      + (hasP ? ` Красная линия — вероятность переполнения: ${r.overflow.method}.` : "")
      + (r.plan_by === "p90" ? " Потребность посчитана по P90 — с запасом на верхнюю границу прогноза." : "");
  }

  // ---------------- AI / ML layer ----------------
  const BAND = "80 % интервал";
  function bandOf(r) {
    if (!r || !r.interval) return null;
    const lo = r.points.map((p) => (p.p10 === undefined ? null : p.p10)), hi = r.points.map((p) => (p.p90 === undefined ? null : p.p90));
    return lo.some((v) => v !== null) ? { lo, hi } : null;
  }
  function bandSeries(band, color) {
    const base = { type: "line", stack: "iv", symbol: "none", silent: true, lineStyle: { opacity: 0 }, connectNulls: false, z: 1 };
    return [
      { ...base, name: "_iv_lo", data: band.lo, tooltip: { show: false } },
      { ...base, name: BAND, data: band.lo.map((v, i) => (v === null || band.hi[i] === null ? null : Math.max(0, band.hi[i] - v))),
        areaStyle: { color, opacity: 0.2 }, itemStyle: { color } },
    ];
  }
  function lineTooltip(band, anByIdx) {
    return (params) => {
      const arr = (Array.isArray(params) ? params : [params]).filter((p) => p && p.seriesName);
      if (!arr.length) return "";
      const i = arr[0].dataIndex;
      let s = `${esc(arr[0].axisValueLabel ?? arr[0].name ?? "")}<br>`;
      for (const p of arr) {
        if (p.seriesName.startsWith("_") || p.seriesName === BAND || p.seriesType === "scatter") continue;
        const v = Array.isArray(p.value) ? p.value[1] : p.value;
        s += `${p.marker}${esc(p.seriesName)}: <b>${fmt(v)}</b><br>`;
      }
      if (band && band.lo[i] !== null && band.lo[i] !== undefined) s += `<span style="color:${css("--text-muted")}">${BAND}: ${fmt(band.lo[i])} – ${fmt(band.hi[i])}</span><br>`;
      for (const e of (anByIdx && anByIdx[i]) || []) {
        s += `<span style="color:${e.kind === "drop" ? css("--bad-text") : css("--warn-text")}">● ${esc(e.kind_ru)}${S.route === "all" ? `, маршрут ${e.route}` : ""}: ${esc(e.label)}`
          + `${e.deviation_pct !== null ? ` (${sign(e.deviation_pct)} % к типичному дню)` : ""}</span><br>`;
      }
      return s;
    };
  }
  async function anomaliesFor(a, b) {
    if (!S.ml.anomalies) return [];
    try {
      const r = await api("/anomalies", { route: S.route, date_from: a, date_to: b });
      return r.available ? r.events : [];
    } catch { return []; }
  }
  function renderOverflowKpi(r) {
    const o = (r && r.overflow) || {}, el = $("kOver");
    el.classList.remove("risk", "warn");
    $("kOverLabel").textContent = r ? `Вероятность переполнения, ${short(r.date)}` : "Вероятность переполнения";
    if (!r || !o.available || o.max === null || o.max === undefined) {
      el.textContent = "—";
      $("kOverSub").textContent = !r ? "нет данных о пассажиропотоке" : r.source === "history" ? "считается для дней прогноза" : "нет интервалов прогноза (ML)";
      return;
    }
    const pct = Math.round(o.max * 100);
    el.textContent = `${pct} %`;
    if (pct >= 50) el.classList.add("risk"); else if (pct >= 20) el.classList.add("warn");
    $("kOverSub").textContent = `макс. за сутки: № ${o.route}, ${pad(o.hour)}:00–${pad((o.hour + 1) % 24)}:00${r.plan_by === "p90" ? " · выпуск по P90" : ""}`;
  }

  function initAi() {
    const ml = S.ml;
    $("modelBox").classList.toggle("hidden", !ml.hybrid);
    $("modelSeg").onclick = (e) => { const b = e.target.closest("button"); if (b) setModel(b.dataset.m); };
    $("hybridToggle").disabled = !ml.hybrid;
    $("hybridToggle").onchange = (e) => setModel(e.target.checked ? "hybrid" : "v08");
    $("fP90").disabled = !ml.intervals;
    $("fP90Box").title = ml.intervals ? "Считать потребность по верхней границе 80 % интервала (P90), а не по медиане" : "Нужны интервалы прогноза (intervals.csv)";
    $("fP90").onchange = (e) => { S.planP90 = e.target.checked; loadFleet().catch((x) => toast(x.message)); };
    $("anomKind").onclick = (e) => {
      const b = e.target.closest("button"); if (!b) return;
      S.anomKind = b.dataset.k;
      [...$("anomKind").children].forEach((x) => x.classList.toggle("on", x === b));
      loadAnomalies().catch((x) => toast(x.message));
    };
    $("anomExclude").onclick = () => {
      const n = $("anomNote");
      n.classList.toggle("hidden");
      n.textContent = S.anomNote || "Модель уже обучается с автоочисткой: аномальные дни исключаются из обучения.";
    };
    loadModelInfo();
    initAssistant();
  }
  function setModel(m) {
    if (m === "hybrid" && !S.ml.hybrid) return;
    S.model = m;
    [...$("modelSeg").children].forEach((b) => b.classList.toggle("on", b.dataset.m === m));
    $("hybridToggle").checked = m === "hybrid";
    $("modelBadge").textContent = m === "hybrid" ? "гибрид ML: структурная × LightGBM" : "структурная v08";
    refresh();
  }

  async function loadAnomalies() {
    const r = await api("/anomalies", { route: S.route, kind: S.anomKind || null }).catch(() => null);
    const thead = $("anomTable").querySelector("thead"), tbody = $("anomTable").querySelector("tbody");
    if (!r) return;
    S.anomNote = r.training_note;
    $("anomBadge").textContent = `история ${short(r.date_from)}.${r.date_from.slice(0, 4)} – ${short(r.date_to)}.${r.date_to.slice(0, 4)}`;
    if (!r.available) {
      $("anomSum").innerHTML = `<span class="muted">${esc(r.message)}. Раздел заполнится автоматически, когда ML-пайплайн выгрузит разметку.</span>`;
      $("anomKind").classList.add("hidden");
      thead.innerHTML = ""; tbody.innerHTML = "";
      return;
    }
    $("anomKind").classList.remove("hidden");
    const who = S.route === "all" ? "по всем маршрутам" : `на маршруте № ${S.route}`;
    $("anomSum").innerHTML = `<span><b>${fmt(r.count)}</b> ${r.count % 10 === 1 && r.count % 100 !== 11 ? "аномальный день" : "аномальных дней"} ${who}</span>`
      + Object.entries(r.by_kind).map(([k, n]) => `<span><i class="dot ${k}"></i>${esc(r.kinds[k] || k)}: ${n}</span>`).join("");
    thead.innerHTML = `<tr><th>Дата</th><th>Маршрут</th><th>Тип</th><th>Причина (метка детектора)</th><th class="num">Факт, пасс.</th><th class="num">Типичный день</th><th class="num">Отклонение</th><th class="num">Оценка</th></tr>`;
    const ev = r.events.slice().sort((x, y) => (x.date < y.date ? 1 : -1)).slice(0, 300);
    tbody.innerHTML = ev.length ? ev.map((e) => `<tr data-d="${e.date}" data-r="${esc(e.route)}"><td>${human(e.date)}</td><td>№ ${esc(e.route)}</td>
      <td><span class="tag ${esc(e.kind)}">${esc(e.kind_ru)}</span></td><td class="lbl">${esc(e.label)}</td>
      <td class="num">${fmt(e.actual_total)}</td><td class="num">${fmt(e.typical_total)}</td>
      <td class="num">${e.deviation_pct === null ? "—" : sign(e.deviation_pct) + " %"}</td><td class="num">${String(e.score).replace(".", ",")}</td></tr>`).join("")
      : `<tr><td colspan="8" class="muted">Аномалий этого типа нет</td></tr>`;
    [...tbody.querySelectorAll("tr[data-d]")].forEach((tr) => (tr.onclick = () => {
      const d = tr.dataset.d;
      S.date = d; $("date").value = d; S.month = d.slice(0, 7); $("month").value = S.month;
      if (S.route !== "all" && S.route !== tr.dataset.r) { S.route = tr.dataset.r; $("route").value = S.route; }
      S.stop = null; S.horizon = "month";
      [...$("horizon").children].forEach((x) => x.classList.toggle("on", x.dataset.h === "month"));
      refresh();
      reveal("lineChart");
    }));
  }

  async function loadModelInfo() {
    let m;
    try { m = await api("/model"); } catch { return; }
    $("modelDesc").innerHTML = m.description.map((p) => `<p>${esc(p)}</p>`).join("");
    $("hybridNote").textContent = m.hybrid_available
      ? (m.hybrid_weight_zero ? `Бустинг проверен на скользящем бэктесте и не улучшил точность: в финале вес 0, гибридный ряд — структурная база без ML-поправки${m.hybrid_compare && Math.abs(m.hybrid_compare.pct) >= 0.01 ? ` (${sign(m.hybrid_compare.pct)} % к отправленному v08)` : ""}. Переключатель показывает его на всех графиках, в выпуске и экспорте, а поправку ml_ratio — в объяснении прогноза.`
        : m.hybrid_compare ? `Ноябрь–декабрь: гибрид ${sign(m.hybrid_compare.pct)} % к v08 (${fmt(m.hybrid_compare.hybrid_total)} против ${fmt(m.hybrid_compare.v08_total)} пасс.). Переключает прогноз на всех графиках, в выпуске и экспорте.` : "")
      : "Появится после загрузки hybrid_nov_dec.csv (ML-пайплайн). Сейчас используется v08.";
    S.hybridZero = !!m.hybrid_weight_zero;
    const t = m.fold_table !== null && m.fold_table !== undefined ? m.tables[m.fold_table] : null;
    const isNum = (v) => v.trim() === "—" || /^[-+−]?\d+([.,]\d+)?\s*%?$/.test(v.replace(/\*/g, "").trim());
    const cell = (v) => esc(v).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`(.+?)`/g, "<code>$1</code>");
    const tableHtml = (t) => {
      const numCol = t.header.map((_, j) => t.rows.length > 0 && t.rows.every((r) => r[j] === undefined || isNum(r[j])));
      return `<table><thead><tr>${t.header.map((h, j) => `<th class="${numCol[j] ? "num" : ""}">${cell(h)}</th>`).join("")}</tr></thead><tbody>`
        + t.rows.map((r) => `<tr>${r.map((v, j) => `<td class="${numCol[j] ? "num" : ""}">${cell(v)}</td>`).join("")}</tr>`).join("") + `</tbody></table>`;
    };
    const rest = m.tables.filter((_, i) => i !== m.fold_table);
    $("modelMore").classList.toggle("hidden", !rest.length);
    $("modelTables").innerHTML = rest.map((x) => `<div><h4>${esc(x.title || x.heading || "")}</h4><div class="table-wrap">${tableHtml(x)}</div></div>`).join("");
    if (t) {
      $("foldTitle").textContent = t.title || t.heading || "Качество по фолдам";
      $("foldTable").innerHTML = tableHtml(t);
    } else {
      $("foldTable").innerHTML = `<p class="muted">Отчёт ML (REPORT.md) ещё не загружен: таблица метрик по фолдам появится после запуска scripts/prepare_data.py.</p>`;
    }
    $("modelSummary").textContent = [m.summary, m.interval_avg_width_pct ? `Средняя ширина 80 % интервала: ${String(m.interval_avg_width_pct).replace(".", ",")} % от прогноза.` : ""].filter(Boolean).join(" ");
    $("modelSources").innerHTML = m.sources.map((x) => `<li><a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.name)}</a><small>${esc(x.what)} → ${esc(x.used_in)}</small></li>`).join("");
    $("modelFactors").innerHTML = m.factors.map((f) => `<li><b>${esc(f.name)}</b> <code>${esc(f.key)}</code><small>${esc(f.description)}</small></li>`).join("");
  }

  // ---------------- dispatcher assistant (rule-based, no LLM) ----------------
  function addMsg(kind, html) {
    const d = document.createElement("div");
    d.className = `msg ${kind}`; d.innerHTML = html;
    $("asstLog").appendChild(d); $("asstLog").scrollTop = $("asstLog").scrollHeight;
    return d;
  }
  function initAssistant() {
    const open = (v) => {
      $("asst").classList.toggle("hidden", !v); $("asstBtn").setAttribute("aria-expanded", String(v));
      if (v) { $("asstRef").textContent = `«сегодня» = выбранная дата, ${human(S.date)}`; $("asstQ").focus(); }
    };
    $("asstBtn").onclick = () => open($("asst").classList.contains("hidden"));
    if ($("catHead")) $("catHead").onclick = () => open(true);
    $("asstClose").onclick = () => open(false);
    const ex = ["Где завтра переполнение?", "Сколько вагонов нужно на 17 маршруте в 8 утра?", "Когда час пик на 11 маршруте в пятницу?", "Какие аномалии были на маршруте 1 в мае?", "Как устроена модель?"];
    $("asstEx").innerHTML = ex.map((q) => `<span class="chip">${esc(q)}</span>`).join("");
    [...$("asstEx").children].forEach((c) => (c.onclick = () => ask(c.textContent)));
    $("asstForm").onsubmit = (e) => { e.preventDefault(); const q = $("asstQ").value.trim(); if (q) ask(q); $("asstQ").value = ""; };
    addMsg("a", "Отвечаю по данным сервиса: переполнение, вагоны, пассажиропоток, час пик, аномалии, модель. Укажите маршрут, дату и час.");
  }
  async function apiPost(path, body) {
    const q = new URLSearchParams(Object.entries({ ...adjParams(), ...modelParams() }));
    const r = await fetch(`${API}${path}?${q}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const b = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(b?.error?.message || `Ошибка ${r.status}`);
    return b;
  }
  const INTENTS = { load: "пассажиропоток", vehicles: "вагоны", overflow: "переполнение", peak: "час пик", anomalies: "аномалии", model: "модель", help: "справка" };
  const hrLbl = (a, b) => `${pad(a)}:00–${pad((b + 1) % 24)}:00`;
  async function ask(text, edited = null) {
    addMsg("q", esc(text) + (edited ? ` <small>(исправленные параметры)</small>` : ""));
    const wait = addMsg("a thinking", `<span class="dots">Считаю</span>`);
    try {
      const r = await apiPost("/assistant/query", { text, ref_date: S.date, plan_by: S.planP90 ? "p90" : "p50", ...(edited ? { query: edited } : {}) });
      wait.remove();
      const d = addMsg("a", esc(r.answer) + (r.items.length ? `<ul>${r.items.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>` : ""));
      if (r.intent !== "help" && r.intent !== "model") {
        d.appendChild(queryCard(text, r));
        // answer actions: show the answer on the map («Обзор») or export exactly those parameters
        const acts = document.createElement("div");
        acts.className = "ans-acts";
        acts.innerHTML = `<button class="btn small" data-a="map"><svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 4L3 6v14l6-2 6 2 6-2V4l-6 2-6-2zM9 4v14M15 6v14"/></svg>Показать на карте</button>
          <button class="btn small" data-a="csv"><svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4v11M7 10l5 5 5-5M5 20h14"/></svg>Экспорт</button>`;
        acts.querySelector("[data-a=map]").onclick = () => { applyQuery(r.query, r.action); reveal("map"); };
        acts.querySelector("[data-a=csv]").onclick = () => { applyQuery(r.query, r.action); setTimeout(() => doExport("csv"), 300); };
        d.appendChild(acts);
      }
    } catch (e) { wait.remove(); addMsg("a", esc(e.message)); }
  }
  /** Recognised parameters as chips + an inline editor: «Применить» (to the dashboard) / «Изменить» (re-ask). */
  function queryCard(text, r) {
    const q = r.query, box = document.createElement("div");
    box.className = "qcard";
    const chips = [];
    chips.push(["Что", INTENTS[q.intent] || q.intent]);
    chips.push(["Маршрут", !q.route || q.route === "all" ? "все" : `№ ${q.route}`]);
    if (q.date_from) chips.push([q.date_from === q.date_to ? "Дата" : "Период", q.date_from === q.date_to ? human(q.date_from) : `${short(q.date_from)} – ${short(q.date_to)}`]);
    if (q.hour_ranges && q.hour_ranges.length) chips.push(["Часы", q.hour_ranges.map(([a, b]) => hrLbl(a, b)).join(" и ")]);
    for (const [k, v] of Object.entries(q.corrections || {})) chips.push([{ k_level: "Уровень", k_event: "Событие", w_scenario: "Погода", k_traffic: "Пробки" }[k] || k, v]);
    const fixes = r.fixes && r.fixes.length ? `<div class="muted small">Исправлено: ${esc(r.fixes.join(", "))}</div>` : "";
    box.innerHTML = `<div class="qchips">${chips.map(([k, v]) => `<span class="qchip"><i>${esc(k)}</i>${esc(v)}</span>`).join("")}</div>${fixes}
      <div class="qbtns"><button class="btn small primary" data-act="apply">Применить</button><button class="btn small" data-act="edit">Изменить</button></div>
      <form class="qedit hidden">
        <label>Что<select name="intent">${Object.entries(INTENTS).filter(([k]) => k !== "help").map(([k, v]) => `<option value="${k}" ${k === q.intent ? "selected" : ""}>${v}</option>`).join("")}</select></label>
        <label>Маршрут<select name="route"><option value="all">все</option>${S.routes.filter((x) => x.has_data).map((x) => `<option value="${x.route}" ${x.route === q.route ? "selected" : ""}>№ ${x.route}</option>`).join("")}</select></label>
        <label>С<input type="date" name="date_from" value="${q.date_from || S.date}" min="${S.coverage.combined.from}" max="${S.coverage.combined.to}"></label>
        <label>По<input type="date" name="date_to" value="${q.date_to || q.date_from || S.date}" min="${S.coverage.combined.from}" max="${S.coverage.combined.to}"></label>
        <label>Часы с<select name="hour_from"><option value="">весь день</option>${[...Array(24).keys()].map((h) => `<option value="${h}" ${h === q.hour_from ? "selected" : ""}>${pad(h)}:00</option>`).join("")}</select></label>
        <label>до<select name="hour_to">${[...Array(24).keys()].map((h) => `<option value="${h}" ${h === q.hour_to ? "selected" : ""}>${pad((h + 1) % 24)}:00</option>`).join("")}</select></label>
        <div class="qbtns"><button class="btn small primary" type="submit">Пересчитать</button><button class="btn small" type="button" data-act="cancel">Отмена</button></div>
      </form>`;
    const form = box.querySelector("form");
    box.querySelector("[data-act=edit]").onclick = () => {
      form.classList.toggle("hidden");
      if (!form.classList.contains("hidden")) form.scrollIntoView({ block: "nearest", behavior: "smooth" });
    };
    box.querySelector("[data-act=cancel]").onclick = () => form.classList.add("hidden");
    box.querySelector("[data-act=apply]").onclick = () => applyQuery(q, r.action);
    form.onsubmit = (e) => {
      e.preventDefault();
      const f = new FormData(form);
      const h0 = f.get("hour_from");
      const edited = { intent: f.get("intent"), route: f.get("route"), date_from: f.get("date_from"), date_to: f.get("date_to"),
        corrections: q.corrections || {} };
      if (h0 !== "") { edited.hour_from = +h0; edited.hour_to = Math.max(+h0, +f.get("hour_to")); edited.hour_ranges = [[edited.hour_from, edited.hour_to]]; }
      else edited.hour_ranges = [];
      form.classList.add("hidden");
      ask(text, edited);
    };
    return box;
  }
  /** Apply a recognised query to the dashboard: route, date/period → horizon, hour filter, corrections. */
  function applyQuery(q, act) {
    if (q.route && (q.route === "all" || S.routes.some((x) => x.route === q.route && x.has_data))) { S.route = q.route; $("route").value = q.route; S.stop = null; }
    if (q.date_from) {
      const multi = q.date_to && q.date_to !== q.date_from;
      S.date = q.date_from; $("date").value = q.date_from;
      S.horizon = multi ? "month" : "day";
      if (multi) { S.month = q.date_from.slice(0, 7); $("month").value = S.month; }
      [...$("horizon").children].forEach((x) => x.classList.toggle("on", x.dataset.h === S.horizon));
    }
    if (q.hour_ranges && q.hour_ranges.length) { S.hour = q.hour_ranges[0][0]; $("hour").value = S.hour; }
    const c = q.corrections || {}, a = S.adj;
    if (c.k_event) for (const it of c.k_event.split(";")) {
      const [route, from, to, k, hh] = it.split(":"); const [h0, h1] = hh ? hh.split("-").map(Number) : [0, 23];
      a.events.push({ route, from, to, k: +k, h0, h1 });
    }
    if (c.w_scenario) for (const it of c.w_scenario.split(";")) {
      const [date, mm, t] = it.split(":"); a.scn = a.scn.filter((x) => x.date !== date).concat([{ date, mm: +mm, t: t === undefined ? null : +t }]);
    }
    if (c.k_traffic) for (const it of c.k_traffic.split(";")) {
      if (it === "actual") { a.tActual = true; continue; }
      const [date, sc] = it.split(":"); a.traffic = a.traffic.filter((x) => x.date !== date).concat([{ date, score: +sc }]);
    }
    if (c.k_level) {
      const [r, k] = c.k_level.includes(":") ? c.k_level.split(":") : ["all", c.k_level];
      a.level = +k; a.scope = r === "all" ? "all" : "route"; $("kLevel").value = a.level; $("kLevelScope").value = a.scope;
      $("oLevel").textContent = `×${a.level.toFixed(2).replace(".", ",")}`;
    }
    renderAdjInfo();
    refresh();
    go("overview");
    addMsg("a", "Параметры применены: открыт «Обзор». Можно задать следующий вопрос или изменить параметры выше.");
  }

  // ---------------- app shell (Round 5): views with hash routing, «Сценарий» drawer, filters sheet ----------------
  const VIEWS = ["overview", "fleet", "analytics", "anomalies", "model"];
  const VIEW_TITLE = { overview: "Обзор", fleet: "Выпуск", analytics: "Аналитика", anomalies: "ИИ-аномалии", model: "Модель" };
  const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  function go(view, { push = true, focus = false } = {}) {
    if (!VIEWS.includes(view)) view = "overview";
    const prev = S.view;
    S.view = view;
    for (const v of VIEWS) {
      const on = v === view, p = $(`view-${v}`), t = $(`tab-${v}`);
      p.hidden = !on; p.classList.toggle("active", on);
      t.setAttribute("aria-selected", String(on)); t.tabIndex = on ? 0 : -1;
    }
    // the day/month/year chart is shared: «Обзор» (hourly curve) and «Аналитика» (horizon chart)
    if (view === "overview" || view === "analytics") {
      const card = $("lineChart").closest("section.card"), slot = $(`slot-line-${view}`);
      if (card.parentElement !== slot) slot.appendChild(card);
    }
    if (push && location.hash !== `#${view}`) history.pushState(null, "", `#${view}`);
    document.title = `${VIEW_TITLE[view]} · Трамвай: прогноз загрузки`;
    // charts / map drawn while their view was hidden get their real size now (ResizeObserver also covers this)
    requestAnimationFrame(() => {
      Object.values(charts).forEach((c) => c && !c.isDisposed() && c.resize());
      if (S.map) S.map.invalidateSize();
    });
    if (prev && prev !== view) window.scrollTo({ top: 0, behavior: reducedMotion() ? "auto" : "smooth" });
    if (focus) $(`view-${view}`).focus({ preventScroll: true });
  }
  /** Switch to the view that contains an element, then scroll to it. */
  function reveal(id, block = "center") {
    const v = $(id)?.closest(".view");
    if (v) go(v.id.replace("view-", ""));
    requestAnimationFrame(() => $(id)?.scrollIntoView({ behavior: reducedMotion() ? "auto" : "smooth", block }));
  }
  const focusables = (root) => [...root.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')]
    .filter((el) => !el.disabled && el.offsetParent !== null);
  function openDrawer(open) {
    const d = $("drawer"), b = $("drawerBackdrop");
    $("scnBtn").setAttribute("aria-expanded", String(open));
    if (open) {
      S.drawerReturn = document.activeElement;
      d.hidden = false; b.hidden = false;
      $("adjCard").classList.remove("collapsed");
      requestAnimationFrame(() => { d.classList.add("open"); b.classList.add("open"); });
      setTimeout(() => (focusables(d).find((x) => x.id !== "drawerClose") || d).focus(), 30);
      document.body.classList.add("drawer-open");
    } else {
      d.classList.remove("open"); b.classList.remove("open");
      document.body.classList.remove("drawer-open");
      setTimeout(() => { if (!d.classList.contains("open")) { d.hidden = true; b.hidden = true; } }, reducedMotion() ? 0 : 220);
      S.drawerReturn?.focus?.();
    }
  }
  function openFilters(open) {
    document.body.classList.toggle("filters-open", open);
    $("filtBtn").setAttribute("aria-expanded", String(open));
    if (open) setTimeout(() => focusables($("filters"))[1]?.focus(), 30);
    else $("filtBtn").focus();
  }
  /** Sortable tables: click (or Enter on) a header → sort by that column; aria-sort drives the arrow. */
  function initTableSort() {
    const num = (t) => { const v = parseFloat(String(t).replace(/[\s  %+]/g, "").replace("−", "-").replace(",", ".")); return Number.isFinite(v) ? v : null; };
    for (const id of ["routeTable", "anomTable"]) {
      const table = $(id);
      table.addEventListener("click", (e) => {
        const th = e.target.closest("th");
        if (!th || !table.tHead.contains(th)) return;
        const idx = [...th.parentElement.children].indexOf(th);
        const dir = th.getAttribute("aria-sort") === "ascending" ? "descending" : "ascending";
        [...th.parentElement.children].forEach((x) => x.removeAttribute("aria-sort"));
        th.setAttribute("aria-sort", dir);
        const rows = [...table.tBodies[0].rows];
        const key = (tr) => { const c = tr.cells[idx]; if (!c) return ""; if (idx === 0 && tr.dataset.d) return tr.dataset.d; const n = num(c.textContent); return n === null ? c.textContent.trim().toLowerCase() : n; };
        rows.sort((a, b) => { const x = key(a), y = key(b); const r = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y), "ru"); return dir === "ascending" ? r : -r; });
        rows.forEach((tr) => table.tBodies[0].appendChild(tr));
      });
      table.addEventListener("keydown", (e) => { if ((e.key === "Enter" || e.key === " ") && e.target.matches("th")) { e.preventDefault(); e.target.click(); } });
      new MutationObserver(() => table.querySelectorAll("thead th").forEach((th) => { th.tabIndex = 0; th.classList.add("sortable"); }))
        .observe(table.tHead, { childList: true, subtree: true });
    }
  }
  function initShell() {
    initTableSort();
    const nav = $("viewnav");
    nav.addEventListener("click", (e) => { const b = e.target.closest("[data-view]"); if (b) go(b.dataset.view); });
    nav.addEventListener("keydown", (e) => {  // roving tabindex: ← → ↑ ↓ Home End
      const i = VIEWS.indexOf(S.view);
      const j = { ArrowRight: i + 1, ArrowDown: i + 1, ArrowLeft: i - 1, ArrowUp: i - 1, Home: 0, End: VIEWS.length - 1 }[e.key];
      if (j === undefined) return;
      e.preventDefault();
      const v = VIEWS[(j + VIEWS.length) % VIEWS.length];
      go(v); $(`tab-${v}`).focus();
    });
    document.addEventListener("click", (e) => { const g = e.target.closest("[data-goto]"); if (g) go(g.dataset.goto); });
    window.addEventListener("popstate", () => go(location.hash.slice(1), { push: false }));
    $("scnBtn").onclick = () => openDrawer($("drawer").hidden);
    $("drawerClose").onclick = () => openDrawer(false);
    $("drawerBackdrop").onclick = () => openDrawer(false);
    $("filtBtn").onclick = () => openFilters(!document.body.classList.contains("filters-open"));
    $("filtClose").onclick = () => openFilters(false);
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        if (!$("drawer").hidden) { openDrawer(false); e.preventDefault(); return; }
        if (!$("asst").classList.contains("hidden")) { $("asstClose").click(); $("asstBtn").focus(); e.preventDefault(); return; }
        if (document.body.classList.contains("filters-open")) { openFilters(false); e.preventDefault(); }
      }
      if (e.key === "Tab" && !$("drawer").hidden) {  // focus trap inside the drawer
        const f = focusables($("drawer"));
        if (!f.length) return;
        if (e.shiftKey && document.activeElement === f[0]) { f[f.length - 1].focus(); e.preventDefault(); }
        else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { f[0].focus(); e.preventDefault(); }
      }
    });
    // the sidebar / top tabs stick right under the sticky filter bar, whatever its wrapped height
    // the sidebar / top tabs stick right under the sticky header (Round 6: the filters scroll away)
    const setFH = () => document.documentElement.style.setProperty("--filters-h", `${document.querySelector(".topbar").offsetHeight || 0}px`);
    if (window.ResizeObserver) new ResizeObserver(setFH).observe(document.querySelector(".topbar")); else setFH();
    go(location.hash.slice(1) || "overview", { push: false });
  }
  /** Header badge «Сценарий: N» mirrors the corrections counter; the button tooltip shows «было → стало». */
  function renderScenarioBadge(n) {
    const b = $("scnBadge");
    b.textContent = n; b.hidden = !n;
    $("scnBtn").classList.toggle("active", n > 0);
    $("scnBtn").setAttribute("aria-label", n ? `Сценарий: ${n} активн.` : "Сценарий: корректировки не заданы");
    $("scnBtn").title = n ? `Сценарий: ${n} активн. — ${$("adjDelta").textContent.trim()}` : "Корректирующие коэффициенты: что будет, если…";
  }
  /** Rail «Внимание»: the hours with the highest P(overflow) for the selected date, from the /fleet response. */
  function renderRisk(r) {
    const list = $("riskList");
    if (!r) { list.innerHTML = `<li class="empty">Нет данных о пассажиропотоке для маршрута</li>`; return; }
    $("riskSub").textContent = `${human(r.date)} · ${r.overflow?.available ? "вероятность переполнения по часам" : "рекомендации по выпуску"}`;
    let items = [];
    if (r.overflow?.available) {
      for (const fr of r.routes) for (const x of fr.hours)
        if (x.p_overflow !== null && x.p_overflow !== undefined && x.boardings) items.push({ route: fr.route, hour: x.hour, p: x.p_overflow, x });
      items.sort((a, b) => b.p - a.p);
      items = items.slice(0, 6);
    }
    if (!items.length) {
      const recs = r.recommendations.filter((x) => x.type === "risk").slice(0, 6);
      list.innerHTML = recs.length ? recs.map((x) => `<li class="risk-item watch"><span class="rk-t">${esc(x.text)}</span></li>`).join("")
        : `<li class="empty">Рисков переполнения на ${short(r.date)} не видно 👌</li>`;
      return;
    }
    const lvl = (p) => (p >= 0.5 ? "risk" : p >= 0.2 ? "watch" : "low");  // green stays reserved for spare capacity
    list.innerHTML = items.map((it) => `<li><button class="risk-item ${lvl(it.p)}" data-r="${esc(it.route)}" data-h="${it.hour}">
      <span class="rk-p">${Math.round(it.p * 100)}<small>%</small></span>
      <span class="rk-t"><b>№ ${esc(it.route)} · ${pad(it.hour)}:00–${pad((it.hour + 1) % 24)}:00</b>
      <small>${fmt(it.x.boardings)} пасс./ч · нужно ${it.x.required}${it.x.plan ? `, сейчас ≈ ${it.x.plan}` : ""} ваг.</small></span></button></li>`).join("");
    [...list.querySelectorAll("button.risk-item")].forEach((b) => (b.onclick = () => {
      S.hour = +b.dataset.h; $("hour").value = S.hour;
      if (S.route !== b.dataset.r && S.routes.some((x) => x.route === b.dataset.r)) { S.route = b.dataset.r; $("route").value = S.route; S.stop = null; refresh(); }
      else paintHour();
    }));
  }

  /** «Текущий выпуск» dashed line drifts slowly while the fleet chart is on screen (off under reduced motion). */
  let dashTimer = null;
  function animateSupplyLine() {
    if (dashTimer || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let off = 0;
    dashTimer = setInterval(() => {
      const c = charts.fleet;
      if (!c || c.isDisposed() || !$("fleetChart").offsetParent || document.hidden) return;
      off = (off + 1) % 11;
      c.setOption({ series: [{}, { lineStyle: { dashOffset: -off } }] }, { lazyUpdate: true, silent: true });
    }, 90);
  }
  function rerenderCharts() {
    if (lastLine || lastHeat) refresh();
    if (mapData) paintHour();
  }

  async function doExport(fmtName) {
    const p = period();
    const gran = S.horizon === "day" ? "hour" : S.horizon === "month" ? "day" : "month";
    const q = S.horizon === "year"
      ? new URLSearchParams({ format: fmtName, source: "scenario", route: S.route, ...adjParams(), ...modelParams() })
      : new URLSearchParams({ format: fmtName, source: p.source, route: S.route, date_from: p.from, date_to: p.to, granularity: gran, ...hours(), ...adjParams(), ...modelParams() });
    try {
      const r = await fetch(`${API}/export?${q}`);
      if (!r.ok) { const b = await r.json().catch(() => ({})); throw new Error(b?.error?.message || `Ошибка ${r.status}`); }
      const blob = await r.blob();
      const cd = r.headers.get("Content-Disposition") || "";
      const name = (cd.match(/filename="([^"]+)"/) || [])[1] || `export.${fmtName}`;
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click();
      setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
    } catch (e) { toast(`Экспорт не удался: ${e.message}`); }
  }

  init().catch((e) => toast(`Не удалось загрузить данные: ${e.message}`));
})();
