/* TradeLab front end: vanilla JS, Lightweight Charts 4.2.0 (vendored). */
"use strict";
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const _cv = document.createElement("canvas").getContext("2d", { willReadFrequently: true });
/* Read a colour token and return rgba(), since the chart library cannot parse oklch(). */
const css = (v) => {
  const raw = getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  if (!raw || raw === "transparent") return raw;
  _cv.clearRect(0, 0, 1, 1);
  _cv.fillStyle = raw;
  _cv.fillRect(0, 0, 1, 1);
  const [r, g, b, a] = _cv.getImageData(0, 0, 1, 1).data;
  return `rgba(${r}, ${g}, ${b}, ${+(a / 255).toFixed(3)})`;
};
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(path, body) {
  const r = await fetch("/api/" + path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  const j = await r.json().catch(() => ({ error: "bad response" }));
  if (!r.ok || (j && j.error && !Array.isArray(j))) throw new Error(j.error || r.statusText);
  return j;
}

/* ---------- formatting ---------- */
function fmt(v, d) {
  if (v == null || Number.isNaN(v)) return "–";
  const a = Math.abs(v);
  if (d == null) d = a >= 1000 ? 2 : a >= 1 ? 2 : a >= 0.01 ? 4 : 6;
  return v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
}
const usd = (v) => (v == null ? "–" : (v < 0 ? "-$" : "$") + fmt(Math.abs(v), 2));
const pct = (v, d = 2) => (v == null ? "–" : (v > 0 ? "+" : "") + fmt(v, d) + "%");
const cls = (v) => (v == null ? "" : v > 0 ? "up" : v < 0 ? "down" : "");
const dt = (t) => (t ? new Date(t * 1000).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "–");
const day = (t) => new Date(t * 1000).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
function ago(t) {
  const s = Date.now() / 1000 - t;
  if (!t) return "";
  if (s < 3600) return Math.max(1, Math.round(s / 60)) + " min ago";
  if (s < 86400) return Math.round(s / 3600) + " h ago";
  return Math.round(s / 86400) + " d ago";
}
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove("show"), 3500);
}
const skel = (n = 5) => Array.from({ length: n }, (_, i) => `<span class="skel ${["w80", "w60", "", "w40"][i % 4]}"></span>`).join("");
const errBox = (e, retry) => `<div class="error">Could not load: ${esc(e.message || e)}${retry ? ` <button class="sm" data-retry="${retry}">Try again</button>` : ""}</div>`;
async function load(el, fn, retry) {
  el.innerHTML = skel();
  try { await fn(); } catch (e) { el.innerHTML = errBox(e, retry); }
}
document.addEventListener("click", (e) => {
  const r = e.target.closest("[data-retry],[data-refresh]");
  if (r) views[r.dataset.retry || r.dataset.refresh]?.(true);
});

function spark(vals) {
  if (!vals || vals.length < 2) return "";
  const w = 96, h = 28, mn = Math.min(...vals), mx = Math.max(...vals), k = mx - mn || 1;
  const d = vals.map((v, i) => `${i ? "L" : "M"}${(i / (vals.length - 1)) * w},${h - 2 - ((v - mn) / k) * (h - 4)}`).join("");
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" aria-hidden="true"><path class="${vals.at(-1) >= vals[0] ? "s-up" : "s-down"}" d="${d}"/></svg>`;
}
function table(cols, rows, opts = {}) {
  if (!rows.length) return `<div class="empty">${opts.empty || "Nothing here yet."}</div>`;
  const th = cols.map((c, i) => `<th class="${c.num ? "num" : ""} ${opts.sort ? "sortable" : ""}" data-i="${i}" scope="col">${c.h}</th>`).join("");
  const tr = rows.map((r) => `<tr class="${opts.click ? "clickable" : ""}" ${opts.click ? `data-sym="${esc(opts.click(r))}" tabindex="0"` : ""}>${cols.map((c) => `<td class="${c.num ? "num" : ""} ${c.cls ? c.cls(r) : ""}">${c.f(r)}</td>`).join("")}</tr>`).join("");
  return `<div class="tbl-wrap"><table><thead><tr>${th}</tr></thead><tbody>${tr}</tbody></table></div>`;
}
function bindRowOpen(el) {
  $$("tr[data-sym]", el).forEach((tr) => {
    const go = () => openChart(tr.dataset.sym);
    tr.addEventListener("click", (e) => { if (!e.target.closest("button")) go(); });
    tr.addEventListener("keydown", (e) => { if (e.key === "Enter") go(); });
  });
}
const symCell = (s, n) => `<span class="sym">${esc(s)}</span>${n ? `<span class="sym-name">${esc(n)}</span>` : ""}`;

/* ---------- routing (state lives in the hash) ---------- */
const route = { view: "overview", symbol: "AAPL", range: "1y" };
function readHash() {
  const [v, q] = location.hash.slice(1).split("?");
  route.view = v || "overview";
  const p = new URLSearchParams(q || "");
  if (p.get("symbol")) route.symbol = p.get("symbol").toUpperCase();
  if (p.get("range")) route.range = p.get("range");
}
function writeHash() {
  const q = route.view === "chart" ? `?symbol=${encodeURIComponent(route.symbol)}&range=${route.range}` : "";
  history.replaceState(null, "", `#${route.view}${q}`);
}
function show() {
  readHash();
  $$(".view").forEach((s) => (s.hidden = s.id !== "v-" + route.view));
  $$(".tabs a").forEach((a) => a.toggleAttribute("aria-current", a.dataset.view === route.view) || (a.dataset.view === route.view && a.setAttribute("aria-current", "page")));
  $$(".tabs a").forEach((a) => (a.dataset.view === route.view ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current")));
  views[route.view]?.();
}
function openChart(sym) {
  route.symbol = sym.toUpperCase();
  location.hash = `chart?symbol=${encodeURIComponent(route.symbol)}&range=${route.range}`;
}
window.addEventListener("hashchange", show);

/* ---------- symbol search ---------- */
function attachSearch(box, onPick) {
  const inp = $("input", box), list = $(".suggest", box);
  let t;
  inp.addEventListener("input", () => {
    clearTimeout(t);
    const q = inp.value.trim();
    if (q.length < 1) { list.hidden = true; return; }
    t = setTimeout(async () => {
      try {
        const res = await api("search?q=" + encodeURIComponent(q));
        list.innerHTML = res.length ? res.map((r) => `<button type="button" data-s="${esc(r.symbol)}"><span><b>${esc(r.symbol)}</b> ${esc(r.name)}</span><span class="muted small">${esc(r.type || "")} ${esc(r.exchange || "")}</span></button>`).join("") : `<div class="empty" style="padding: var(--space-sm)">No match. Try a ticker such as MSFT, BTC-USD, EURUSD=X or GC=F.</div>`;
        list.hidden = false;
      } catch (e) { list.hidden = true; }
    }, 250);
  });
  inp.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); list.hidden = true; onPick(inp.value.trim().toUpperCase()); inp.value = ""; }
    if (e.key === "Escape") list.hidden = true;
  });
  list.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-s]");
    if (b) { list.hidden = true; inp.value = ""; onPick(b.dataset.s); }
  });
  document.addEventListener("click", (e) => { if (!box.contains(e.target)) list.hidden = true; });
}

/* ---------- views ---------- */
const views = {};
let ACCOUNT = null;

views.markets = async () => {
  const wl = $("#watchlist");
  load(wl, async () => {
    const d = await api("quotes");
    const rows = d.quotes.map((q, i) => q || { symbol: d.watchlist[i], error: true });
    wl.innerHTML = table([
      { h: "Symbol", f: (r) => symCell(r.symbol, r.name) },
      { h: "Last", num: 1, f: (r) => fmt(r.price) },
      { h: "Change", num: 1, f: (r) => pct(r.change_pct), cls: (r) => cls(r.change_pct) },
      { h: "Day range", num: 1, f: (r) => (r.low != null ? `${fmt(r.low)} – ${fmt(r.high)}` : "–") },
      { h: "Market", f: (r) => (r.error ? "no quote" : r.open ? "open" : "closed") },
      { h: "", f: (r) => `<button class="ghost sm" data-rm="${esc(r.symbol)}" aria-label="Remove ${esc(r.symbol)}">Remove</button>` },
    ], rows, { click: (r) => r.symbol, empty: "Your watchlist is empty. Add a symbol above." });
    bindRowOpen(wl);
    $$("[data-rm]", wl).forEach((b) => b.addEventListener("click", async () => { await api("watchlist", { symbol: b.dataset.rm, action: "remove" }); views.markets(); }));
  }, "markets");
  const ov = $("#overview");
  if (!ov.dataset.loaded || arguments[0]) load(ov, async () => {
    const d = await api("overview");
    ov.innerHTML = Object.entries(d.groups).map(([g, rows]) => `<h3 style="margin: var(--space-md) 0 var(--space-2xs)">${esc(g)}</h3>` + table([
      { h: "Name", f: (r) => symCell(r.name, r.symbol) },
      { h: "Last", num: 1, f: (r) => (r.error ? "–" : fmt(r.price)) },
      { h: "Day", num: 1, f: (r) => pct(r.change_pct), cls: (r) => cls(r.change_pct) },
      { h: "1 month", num: 1, f: (r) => pct(r.month_pct), cls: (r) => cls(r.month_pct) },
      { h: "Trend", f: (r) => spark(r.spark) },
    ], rows, { click: (r) => r.symbol })).join("");
    bindRowOpen(ov);
    ov.dataset.loaded = 1;
    const f = d.fear_greed;
    $("#fng").innerHTML = f ? `<div class="row" style="align-items: baseline; gap: var(--space-sm)"><span class="fg">${f.value}</span><b>${esc(f.label)}</b></div>
      <div class="meter" role="img" aria-label="Index ${f.value} of 100"><span style="left:${f.value}%"></span></div>
      <div class="row spread small muted"><span>Extreme fear</span><span>Extreme greed</span></div>
      <p class="note">30-day range ${Math.min(...f.history.map((x) => x.v))} to ${Math.max(...f.history.map((x) => x.v))}. Source ${esc(f.source)}.</p>` : `<div class="empty">Index unavailable right now.</div>`;
  }, "markets");
  const mn = $("#mk-news");
  if (!mn.dataset.loaded || arguments[0]) load(mn, async () => {
    const d = await api("news");
    mn.innerHTML = newsList(d.items.slice(0, 12));
    mn.dataset.loaded = 1;
  }, "markets");
};
$("#watch-add").addEventListener("submit", async (e) => {
  e.preventDefault();
  const s = $("#watch-sym").value.trim();
  if (!s) return;
  try { await api("watchlist", { symbol: s }); $("#watch-sym").value = ""; toast(s.toUpperCase() + " added"); views.markets(); } catch (er) { toast(er.message); }
});

function newsList(items) {
  if (!items.length) return `<div class="empty">No headlines from the feeds right now.</div>`;
  return `<ul class="news">${items.map((n) => {
    const s = n.sentiment, c = s > 0.1 ? "s-pos" : s < -0.1 ? "s-neg" : "s-neu";
    return `<li><span class="senti ${c}" title="Headline sentiment">${s > 0 ? "+" : ""}${s.toFixed(2)}</span><div><a href="${esc(n.link)}" target="_blank" rel="noopener">${esc(n.title)}</a>${n.summary ? `<div class="sum small">${esc(n.summary)}</div>` : ""}<div class="meta">${esc(n.source)}, ${ago(n.ts)}</div></div></li>`;
  }).join("")}</ul>`;
}

/* ---------- news view ---------- */
let NEWS = null, newsFilter = "all";
views.news = async (force) => {
  const el = $("#news-list");
  if (NEWS && !force) return renderNews();
  load(el, async () => { NEWS = await api("news"); renderNews(); }, "news");
};
function renderNews() {
  const s = NEWS.summary;
  $("#news-sum").innerHTML = `<div class="figures"><div class="figure"><b>${s.count}</b><span>Headlines</span></div><div class="figure"><b class="up">${s.positive}</b><span>Positive</span></div><div class="figure"><b class="down">${s.negative}</b><span>Negative</span></div><div class="figure"><b>${s.avg > 0 ? "+" : ""}${s.avg.toFixed(2)}</b><span>Average, ${esc(s.label.toLowerCase())}</span></div></div>`;
  const it = NEWS.items.filter((n) => newsFilter === "all" || (newsFilter === "pos" ? n.sentiment > 0.1 : newsFilter === "neg" ? n.sentiment < -0.1 : Math.abs(n.sentiment) <= 0.1));
  $("#news-list").innerHTML = newsList(it);
}
segment($("#news-filter"), [["all", "All"], ["pos", "Positive"], ["neg", "Negative"], ["neu", "Neutral"]], "all", (v) => { newsFilter = v; if (NEWS) renderNews(); });

function segment(el, opts, cur, on) {
  el.innerHTML = opts.map(([v, l]) => `<button type="button" data-v="${v}" aria-pressed="${v === cur}">${l}</button>`).join("");
  el.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    $$("button", el).forEach((x) => x.setAttribute("aria-pressed", x === b));
    on(b.dataset.v);
  });
}

/* ---------- chart view ---------- */
const OVER = { sma20: false, sma50: true, sma200: true, bb: false, ema: false };
let charts = null, chartData = null, curSym = null, lastQuote = null;
function mkChart(el, h) {
  const c = LightweightCharts.createChart(el, {
    autoSize: true,
    localization: { locale: "en-US", dateFormat: "dd MMM 'yy" },
    layout: { background: { color: css("--color-paper") }, textColor: css("--color-muted"), fontFamily: "Albert Sans, sans-serif" },
    grid: { vertLines: { color: css("--chart-grid") }, horzLines: { color: css("--chart-grid") } },
    rightPriceScale: { borderColor: css("--color-rule") },
    timeScale: { borderColor: css("--color-rule"), timeVisible: true },
    crosshair: { mode: 0 },
  });
  return c;
}
function ensureCharts() {
  if (charts) return charts;
  const main = mkChart($("#c-main")), rsi = mkChart($("#c-rsi")), macd = mkChart($("#c-macd"));
  const up = css("--color-up"), dn = css("--color-down");
  const s = {
    main, rsi, macd,
    candle: main.addCandlestickSeries({ upColor: up, downColor: dn, borderUpColor: up, borderDownColor: dn, wickUpColor: up, wickDownColor: dn }),
    vol: main.addHistogramSeries({ priceScaleId: "vol", priceFormat: { type: "volume" }, lastValueVisible: false, priceLineVisible: false }),
    lines: {},
    rsiLine: rsi.addLineSeries({ color: css("--series-6"), lineWidth: 2, priceLineVisible: false }),
    macdLine: macd.addLineSeries({ color: css("--series-1"), lineWidth: 2, priceLineVisible: false }),
    sigLine: macd.addLineSeries({ color: css("--series-2"), lineWidth: 2, priceLineVisible: false }),
    hist: macd.addHistogramSeries({ priceLineVisible: false, lastValueVisible: false }),
  };
  main.priceScale("vol").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
  s.rsiLine.createPriceLine({ price: 70, color: css("--color-rule"), lineStyle: 2, axisLabelVisible: false });
  s.rsiLine.createPriceLine({ price: 30, color: css("--color-rule"), lineStyle: 2, axisLabelVisible: false });
  const defs = { sma20: ["--series-4"], sma50: ["--series-1"], sma200: ["--series-2"], ema12: ["--series-3"], ema26: ["--series-5"], bb_up: ["--series-6"], bb_mid: ["--series-6"], bb_lo: ["--series-6"] };
  for (const [k, [c]] of Object.entries(defs)) s.lines[k] = main.addLineSeries({ color: css(c), lineWidth: k.startsWith("bb") ? 1 : 2, lineStyle: k === "bb_mid" ? 2 : 0, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
  // keep the three panes on one time axis
  const all = [main, rsi, macd];
  all.forEach((c) => c.timeScale().subscribeVisibleLogicalRangeChange((r) => { if (!r || s._sync) return; s._sync = 1; all.forEach((o) => o !== c && o.timeScale().setVisibleLogicalRange(r)); s._sync = 0; }));
  charts = s;
  return s;
}
function drawOverlays() {
  if (!chartData) return;
  const s = charts, bars = chartData.bars, ind = chartData.ind;
  const on = { sma20: OVER.sma20, sma50: OVER.sma50, sma200: OVER.sma200, ema12: OVER.ema, ema26: OVER.ema, bb_up: OVER.bb, bb_mid: OVER.bb, bb_lo: OVER.bb };
  const lg = [];
  const names = { sma20: ["k4", "SMA 20"], sma50: ["k1", "SMA 50"], sma200: ["k2", "SMA 200"], ema12: ["k3", "EMA 12"], ema26: ["k5", "EMA 26"], bb_up: ["k6", "Bollinger 20, 2"] };
  for (const [k, ser] of Object.entries(s.lines)) {
    ser.setData(on[k] ? bars.map((b, i) => (ind[k][i] == null ? { time: b.t } : { time: b.t, value: ind[k][i] })) : []);
    if (on[k] && names[k]) lg.push(`<span><i class="${names[k][0]}"></i>${names[k][1]}</span>`);
  }
  $("#lg-main").innerHTML = lg.join("");
}
segment($("#overlays"), [["sma20", "SMA20"], ["sma50", "SMA50"], ["sma200", "SMA200"], ["ema", "EMA"], ["bb", "BB"]], null, (v) => {
  OVER[v] = !OVER[v];
  $$("#overlays button").forEach((b) => b.setAttribute("aria-pressed", OVER[b.dataset.v]));
  drawOverlays();
});
$$("#overlays button").forEach((b) => b.setAttribute("aria-pressed", OVER[b.dataset.v]));
segment($("#ranges"), [["1d", "1D"], ["5d", "5D"], ["1mo", "1M"], ["3mo", "3M"], ["6mo", "6M"], ["1y", "1Y"], ["2y", "2Y"], ["5y", "5Y"], ["max", "Max"]], "1y", (v) => { route.range = v; writeHash(); loadChart(); });
attachSearch($("#chart-search"), openChart);

views.chart = () => {
  $$("#ranges button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.v === route.range));
  if (curSym !== route.symbol) {
    curSym = route.symbol;
    loadChart();
    loadAnalysis();
    loadSymNews();
    $("#ai-out").innerHTML = "";
  }
  renderTicket();
  refreshAccount();
};

async function loadChart() {
  const s = ensureCharts();
  const sym = route.symbol;
  $("#qhead").innerHTML = `<span class="skel w40" style="width: 240px; height: 28px"></span>`;
  try {
    const d = await api(`chart?symbol=${encodeURIComponent(sym)}&range=${route.range}`);
    if (sym !== route.symbol) return;
    chartData = d;
    const bars = d.bars, up = css("--color-up-fill"), dn = css("--color-down-fill");
    s.candle.setData(bars.map((b) => ({ time: b.t, open: b.o, high: b.h, low: b.l, close: b.c })));
    s.vol.setData(bars.map((b) => ({ time: b.t, value: b.v, color: b.c >= b.o ? up : dn })));
    const ser = (k) => bars.map((b, i) => (d.ind[k][i] == null ? { time: b.t } : { time: b.t, value: d.ind[k][i] }));
    s.rsiLine.setData(ser("rsi"));
    s.macdLine.setData(ser("macd"));
    s.sigLine.setData(ser("macd_signal"));
    s.hist.setData(bars.map((b, i) => (d.ind.macd_hist[i] == null ? { time: b.t } : { time: b.t, value: d.ind.macd_hist[i], color: d.ind.macd_hist[i] >= 0 ? css("--color-up") : css("--color-down") })));
    drawOverlays();
    [s.main, s.rsi, s.macd].forEach((c) => c.timeScale().fitContent());
    s.main.applyOptions({ timeScale: { timeVisible: ["5m", "15m", "1h", "1m"].includes(d.interval) } });
    await renderQuoteHead(d.meta);
  } catch (e) {
    $("#qhead").innerHTML = errBox(e);
  }
}
async function renderQuoteHead(meta) {
  let q = null;
  try { q = await api("quote?symbol=" + encodeURIComponent(route.symbol)); } catch (e) { /* header falls back to chart meta */ }
  lastQuote = q;
  const px = q?.price ?? meta.regularMarketPrice, ch = q?.change_pct;
  $("#qhead").innerHTML = `<h1>${esc(route.symbol)}</h1><span class="muted">${esc(meta.longName || meta.shortName || "")}${meta.fullExchangeName ? ", " + esc(meta.fullExchangeName) : ""}</span>
    <span class="px">${fmt(px)}</span><span class="${cls(ch)} mono">${pct(ch)}</span><span class="muted small">${esc(q?.currency || meta.currency || "")}. ${q ? (q.open ? "Market open" : "Market closed") + ". " + esc(q.source) : ""}</span>`;
  renderTicket();
}

async function loadAnalysis() {
  const sym = route.symbol;
  for (const id of ["#signals", "#levels", "#perf", "#events", "#rating"]) $(id).innerHTML = skel(4);
  try {
    const a = await api("analysis?symbol=" + encodeURIComponent(sym));
    if (sym !== route.symbol) return;
    $("#rating").innerHTML = `<div class="rating"><b class="${a.score > 0 ? "up" : a.score < 0 ? "down" : ""}">${esc(a.rating)}</b><span class="mono">${a.score > 0 ? "+" : ""}${a.score}</span></div>
      <div class="meter" role="img" aria-label="Score ${a.score} from -100 to 100"><span style="left:${(a.score + 100) / 2}%"></span></div>
      <div class="row spread small muted"><span>-100 sell</span><span>+100 buy</span></div>
      <p class="note">Mechanical vote of ${a.signals.length} daily indicators as of ${day(a.as_of)}. Not a forecast.</p>
      ${a.profile?.sector ? `<p class="small" style="margin-top: var(--space-xs)">${esc(a.profile.sector)}, ${esc(a.profile.industry)}</p>` : ""}`;
    $("#signals").innerHTML = table([
      { h: "Indicator", f: (r) => esc(r.name) }, { h: "Reading", num: 1, f: (r) => esc(r.value) },
      { h: "Vote", f: (r) => `<span class="vote v${r.vote}">${r.vote > 0 ? "Buy" : r.vote < 0 ? "Sell" : "Neutral"}</span>` },
    ], a.signals);
    const L = a.levels;
    $("#levels").innerHTML = `<dl class="kv">
      ${L.resistance.slice().reverse().map((v, i) => `<dt>Resistance ${L.resistance.length - i}</dt><dd>${fmt(v)}</dd>`).join("")}
      <dt><b>Last price</b></dt><dd><b>${fmt(a.price)}</b></dd>
      ${L.support.map((v, i) => `<dt>Support ${i + 1}</dt><dd>${fmt(v)}</dd>`).join("")}
      ${Object.entries(L.pivots).map(([k, v]) => `<dt>Pivot ${k}</dt><dd>${fmt(v)}</dd>`).join("")}
      <dt>52-week high</dt><dd>${fmt(L.high_52w)}</dd><dt>52-week low</dt><dd>${fmt(L.low_52w)}</dd>
      ${Object.entries(L.fib_52w).map(([k, v]) => `<dt>Fibonacci ${k}</dt><dd>${fmt(v)}</dd>`).join("")}</dl>
      ${!L.support.length ? `<p class="note">No swing low below the price in the last 180 sessions.</p>` : ""}`;
    const P = a.performance, R = a.risk, V = a.volatility;
    $("#perf").innerHTML = `<dl class="kv">
      ${[["1 week", P["1w"]], ["1 month", P["1m"]], ["3 months", P["3m"]], ["6 months", P["6m"]], ["1 year", P["1y"]], ["Year to date", P.ytd]].map(([k, v]) => `<dt>${k}</dt><dd class="${cls(v)}">${pct(v)}</dd>`).join("")}
      <dt>ATR 14 (daily range)</dt><dd>${fmt(V.atr)} (${fmt(V.atr_pct, 2)}%)</dd>
      <dt>Volatility, annualised</dt><dd>${fmt(V.hist_vol_pct, 1)}%</dd>
      <dt>Max drawdown, 1 year</dt><dd class="down">-${fmt(R.max_drawdown_1y_pct, 1)}%</dd>
      <dt>Sharpe, 1 year</dt><dd>${fmt(R.sharpe_1y, 2)}</dd>
      <dt>Beta to S&amp;P 500</dt><dd>${fmt(R.beta_vs_sp500, 2)}</dd>
      <dt>Correlation to S&amp;P 500</dt><dd>${fmt(R.corr_vs_sp500, 2)}</dd>
      <dt>Stop at 2 ATR below</dt><dd>${fmt(R.suggested_stop_2atr)}</dd></dl>`;
    $("#events").innerHTML = a.events.length ? table([{ h: "Date", f: (r) => day(r.t) }, { h: "Event", f: (r) => esc(r.event) }], a.events.slice().reverse()) : `<div class="empty">No crossover in the last 60 sessions.</div>`;
  } catch (e) {
    for (const id of ["#signals", "#levels", "#perf", "#events", "#rating"]) $(id).innerHTML = errBox(e);
  }
}
async function loadSymNews() {
  const el = $("#sym-news"), sym = route.symbol;
  load(el, async () => {
    const name = (chartData && chartData.meta && (chartData.meta.shortName || "")) || "";
    const d = await api(`news?symbol=${encodeURIComponent(sym)}&name=${encodeURIComponent(name)}`);
    if (sym !== route.symbol) return;
    el.innerHTML = `<p class="small muted">${d.summary.count} headlines, ${d.summary.positive} positive, ${d.summary.negative} negative, average ${d.summary.avg > 0 ? "+" : ""}${d.summary.avg.toFixed(2)}.</p>` + newsList(d.items.slice(0, 20));
  });
}
$("#ai-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const b = $("button", e.target), out = $("#ai-out");
  b.disabled = true;
  out.innerHTML = `<p class="muted">Analysing ${esc(route.symbol)} with indicators and headlines. This takes about 20 to 60 seconds.</p>${skel(4)}`;
  try {
    const r = await api("ai", { symbol: route.symbol, question: $("#ai-q").value });
    out.innerHTML = r.error ? errBox(r.error) : `${esc(r.text)}<p class="note">${esc(r.model)}, ${r.seconds} s.</p>`;
  } catch (er) { out.innerHTML = errBox(er); }
  b.disabled = false;
});

/* ---------- order ticket ---------- */
let side = 1;
function renderTicket() {
  const t = $("#ticket");
  if (!t) return;
  if (!t.dataset.built) {
    t.innerHTML = `<h2>Order ticket</h2>
      <div class="sides" role="group" aria-label="Side"><button type="button" class="buy" data-side="1" aria-pressed="true">Buy</button><button type="button" data-side="-1" aria-pressed="false">Sell</button></div>
      <form id="order-form" class="form-grid" style="margin-top: var(--space-sm)">
        <label class="f">Type<select name="type"><option value="market">Market</option><option value="limit">Limit</option><option value="stop">Stop</option></select></label>
        <label class="f">Quantity<input name="qty" type="number" step="any" min="0" value="10" required></label>
        <label class="f" data-px hidden>Order price<input name="price" type="number" step="any"></label>
        <label class="f">Stop loss<input name="sl" type="number" step="any" placeholder="optional"></label>
        <label class="f">Take profit<input name="tp" type="number" step="any" placeholder="optional"></label>
        <label class="f">Or size by USD<input name="usd" type="number" step="any" placeholder="e.g. 5000"></label>
        <button class="primary" style="grid-column: 1 / -1" id="place">Place order</button>
      </form><div class="est" id="est"></div>`;
    t.dataset.built = 1;
    $$(".sides button", t).forEach((b) => b.addEventListener("click", () => {
      side = +b.dataset.side;
      $$(".sides button", t).forEach((x) => { const on = x === b; x.setAttribute("aria-pressed", on); x.className = on ? (side > 0 ? "buy" : "sell") : ""; });
      renderTicket();
    }));
    const f = $("#order-form");
    f.type.addEventListener("change", () => { $("[data-px]", f).hidden = f.type.value === "market"; renderTicket(); });
    f.usd.addEventListener("input", () => { const p = lastQuote?.price; if (p && f.usd.value) f.qty.value = +(f.usd.value / p / (lastQuote.fx || 1)).toPrecision(6); renderTicket(); });
    f.qty.addEventListener("input", renderTicket);
    f.addEventListener("submit", async (e) => {
      e.preventDefault();
      const body = { symbol: route.symbol, side, qty: f.qty.value, type: f.type.value, price: f.price.value, sl: f.sl.value, tp: f.tp.value };
      try {
        const o = await api("order", body);
        toast(o.status === "filled" ? `Filled ${o.side > 0 ? "buy" : "sell"} ${fmt(o.qty, null)} ${o.symbol} at ${fmt(o.fill_px)}` : o.status === "pending" ? `Order #${o.id} pending. ${o.note}` : `Rejected: ${o.note}`);
        refreshAccount();
      } catch (er) { toast(er.message); }
    });
  }
  const f = $("#order-form"), q = lastQuote;
  $("#place").textContent = `${side > 0 ? "Buy" : "Sell"} ${route.symbol}`;
  $("#place").className = side > 0 ? "buy" : "sell";
  if (q) {
    const px = side > 0 ? q.ask : q.bid, n = +f.qty.value || 0, val = n * px * (q.fx || 1);
    $("#est").innerHTML = `Bid ${fmt(q.bid)}, ask ${fmt(q.ask)}. Estimated value <b class="mono">${usd(val)}</b>${q.currency !== "USD" ? ` (${esc(q.currency)} converted at ${fmt(q.fx, 6)})` : ""}.${q.open ? "" : " Market closed: a market order waits for the next open."}`;
  }
}

/* ---------- portfolio ---------- */
let eqChart = null;
async function refreshAccount() {
  try { ACCOUNT = await api("account"); } catch (e) { return; }
  const a = ACCOUNT;
  $("#simflag").textContent = `Manual sandbox ${usd(a.stats.equity)}`;
  const p = a.positions.find((x) => x.symbol === route.symbol);
  const ph = $("#pos-here");
  if (ph) ph.innerHTML = p ? `<dl class="kv"><dt>Side</dt><dd>${p.side > 0 ? "Long" : "Short"}</dd><dt>Quantity</dt><dd>${fmt(p.qty, null)}</dd><dt>Entry</dt><dd>${fmt(p.entry)}</dd><dt>Profit or loss</dt><dd class="${cls(p.pnl_usd)}">${usd(p.pnl_usd)} (${pct(p.pnl_pct)})</dd><dt>Stop loss</dt><dd>${fmt(p.sl)}</dd><dt>Take profit</dt><dd>${fmt(p.tp)}</dd></dl><div class="row" style="margin-top: var(--space-sm)"><button class="sm" data-close="${esc(p.symbol)}">Close position</button></div>` : `<div class="empty">No position in ${esc(route.symbol)}. Use the ticket above.</div>`;
  bindPosButtons(ph);
  if (route.view === "portfolio") renderPortfolio();
}
function bindPosButtons(el) {
  $$("[data-close]", el).forEach((b) => b.addEventListener("click", async () => {
    try { const t = await api("close", { symbol: b.dataset.close }); toast(`Closed ${t.symbol}: ${usd(t.pnl)}`); refreshAccount(); } catch (e) { toast(e.message); }
  }));
  $$("[data-modify]", el).forEach((b) => b.addEventListener("click", async () => {
    const tr = b.closest("tr"), sl = $("[name=sl]", tr).value, tp = $("[name=tp]", tr).value;
    await api("modify", { symbol: b.dataset.modify, sl, tp });
    toast("Stop and target saved");
    refreshAccount();
  }));
  $$("[data-cancel]", el).forEach((b) => b.addEventListener("click", async () => { await api("cancel", { id: b.dataset.cancel }); toast("Order cancelled"); refreshAccount(); }));
}
views.portfolio = async () => {
  if (!ACCOUNT) { $("#positions").innerHTML = skel(); }
  await refreshAccount();
  if (!ACCOUNT) $("#positions").innerHTML = errBox("account unavailable", "portfolio");
};
function renderPortfolio() {
  const a = ACCOUNT, s = a.stats;
  $("#acct-figs").innerHTML = `<div class="figures">
    <div class="figure hot"><b>${usd(s.equity)}</b><span>Equity</span></div>
    <div class="figure"><b class="${cls(s.return_pct)}">${pct(s.return_pct)}</b><span>Return</span></div>
    <div class="figure"><b>${usd(s.balance)}</b><span>Cash balance</span></div>
    <div class="figure"><b class="${cls(s.unrealized)}">${usd(s.unrealized)}</b><span>Open profit or loss</span></div>
    <div class="figure"><b class="${cls(s.realized)}">${usd(s.realized)}</b><span>Realised</span></div>
    <div class="figure"><b>${usd(s.free_margin)}</b><span>Buying power</span></div>
    <div class="figure"><b>${s.win_rate == null ? "–" : fmt(s.win_rate, 0) + "%"}</b><span>Win rate, ${s.trades} trades</span></div>
    <div class="figure"><b>${fmt(s.max_drawdown_pct, 2)}%</b><span>Max drawdown</span></div></div>`;
  const pos = $("#positions");
  pos.innerHTML = table([
    { h: "Symbol", f: (r) => symCell(r.symbol, r.currency !== "USD" ? r.currency : "") },
    { h: "Side", f: (r) => (r.side > 0 ? "Long" : "Short") },
    { h: "Qty", num: 1, f: (r) => fmt(r.qty, null) }, { h: "Entry", num: 1, f: (r) => fmt(r.entry) },
    { h: "Mark", num: 1, f: (r) => fmt(r.mark) }, { h: "Value", num: 1, f: (r) => usd(r.value_usd) },
    { h: "P/L", num: 1, f: (r) => `${usd(r.pnl_usd)}<br><span class="small">${pct(r.pnl_pct)}</span>`, cls: (r) => cls(r.pnl_usd) },
    { h: "Stop loss", f: (r) => `<input name="sl" type="number" step="any" value="${r.sl ?? ""}" aria-label="Stop loss" style="width: 100px">` },
    { h: "Take profit", f: (r) => `<input name="tp" type="number" step="any" value="${r.tp ?? ""}" aria-label="Take profit" style="width: 100px">` },
    { h: "", f: (r) => `<div class="row"><button class="sm" data-modify="${esc(r.symbol)}">Save</button><button class="sm" data-close="${esc(r.symbol)}">Close</button>${r.market_open === false ? `<span class="small muted">closed</span>` : ""}</div>` },
  ], a.positions, { click: (r) => r.symbol, empty: "No open positions. Open a chart and use the order ticket." });
  bindPosButtons(pos);
  bindRowOpen(pos);
  const ord = $("#orders");
  ord.innerHTML = table([
    { h: "#", num: 1, f: (r) => r.id }, { h: "Time", f: (r) => dt(r.created) }, { h: "Symbol", f: (r) => esc(r.symbol) },
    { h: "Order", f: (r) => `${r.side > 0 ? "Buy" : "Sell"} ${r.type}${r.price ? " @ " + fmt(r.price) : ""}` },
    { h: "Qty", num: 1, f: (r) => fmt(r.qty, null) },
    { h: "Status", f: (r) => `${esc(r.status)}${r.fill_px ? " @ " + fmt(r.fill_px) : ""}${r.note ? `<br><span class="small muted">${esc(r.note)}</span>` : ""}` },
    { h: "", f: (r) => (r.status === "pending" ? `<button class="sm" data-cancel="${r.id}">Cancel</button>` : "") },
  ], a.orders.slice(0, 50), { empty: "No orders yet." });
  bindPosButtons(ord);
  const tot = Object.values(a.allocation).reduce((x, y) => x + y, 0) + Math.max(a.cash_usd - (s.used_margin || 0), 0);
  const allocRows = [...Object.entries(a.allocation).map(([k, v]) => ({ k: k.toLowerCase(), v })), { k: "cash not in use", v: Math.max(a.cash_usd - (s.used_margin || 0), 0) }];
  $("#alloc").innerHTML = table([{ h: "Asset type", f: (r) => esc(r.k) }, { h: "USD", num: 1, f: (r) => usd(r.v) }, { h: "Share", num: 1, f: (r) => (tot ? fmt((r.v / tot) * 100, 1) + "%" : "–") }], allocRows);
  $("#trades").innerHTML = table([
    { h: "Closed", f: (r) => dt(r.closed_ts) }, { h: "Symbol", f: (r) => esc(r.symbol) }, { h: "Side", f: (r) => (r.side > 0 ? "Long" : "Short") },
    { h: "Qty", num: 1, f: (r) => fmt(r.qty, null) }, { h: "Entry", num: 1, f: (r) => fmt(r.entry) }, { h: "Exit", num: 1, f: (r) => fmt(r.exit) },
    { h: "Fees", num: 1, f: (r) => usd(r.fees) }, { h: "Net P/L", num: 1, f: (r) => usd(r.pnl), cls: (r) => cls(r.pnl) }, { h: "Reason", f: (r) => esc(r.reason) },
  ], a.trades, { empty: "No closed trades yet." });
  const st = a.settings, f = $("#reset-form");
  if (!f.dataset.filled) { f.balance.value = st.initial; f.leverage.value = st.leverage; f.fee_pct.value = +(st.fee_rate * 100).toFixed(4); f.min_fee.value = st.min_fee; f.slippage_pct.value = +(st.slippage * 100).toFixed(4); f.allow_short.checked = st.allow_short; f.dataset.filled = 1; }
  if (!eqChart) {
    eqChart = mkChart($("#c-equity"));
    eqChart._s = eqChart.addAreaSeries({ lineColor: css("--series-1"), topColor: css("--color-up-fill"), bottomColor: "transparent", lineWidth: 2 });
  }
  const seen = new Set();
  eqChart._s.setData(a.equity_curve.map(([t, v]) => ({ time: Math.floor(t), value: v })).filter((p) => !seen.has(p.time) && seen.add(p.time)));
  eqChart.timeScale().fitContent();
}
$("#reset-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  if (!confirmReset()) return;
  await api("reset", { balance: f.balance.value, leverage: f.leverage.value, fee_pct: f.fee_pct.value, min_fee: f.min_fee.value, slippage_pct: f.slippage_pct.value, allow_short: f.allow_short.checked });
  toast("Account reset");
  refreshAccount();
});
function confirmReset() {
  const b = $("#reset-form button[type=submit]");
  if (b.dataset.armed) { delete b.dataset.armed; b.textContent = "Reset account"; return true; }
  b.dataset.armed = 1;
  b.textContent = "Press again to erase";
  setTimeout(() => { delete b.dataset.armed; b.textContent = "Reset account"; }, 4000);
  return false;
}

/* ---------- screener ---------- */
let SCR = null, scrSort = { k: "score", dir: -1 }, universe = "universe";
segment($("#scr-universe"), [["universe", "Broad list"], ["watchlist", "Watchlist"]], "universe", (v) => { universe = v; });
views.screener = () => { if (SCR) renderScreener(); else $("#screener").innerHTML = `<div class="empty">Press Run scan to score ${universe === "watchlist" ? "your watchlist" : "about 40 global symbols"}. A first scan takes 10 to 30 seconds.</div>`; };
$("#scr-run").addEventListener("click", () => load($("#screener"), async () => { SCR = await api("screener?list=" + universe); renderScreener(); }, "screener"));
$("#scr-filter").addEventListener("change", () => SCR && renderScreener());
function renderScreener() {
  const f = $("#scr-filter").value;
  let rows = SCR.filter((r) => !r.error).filter((r) => !f || (f === "above200" ? r.above_sma200 : f === "oversold" ? r.rsi < 30 : f === "overbought" ? r.rsi > 70 : r.rating === f));
  rows.sort((a, b) => ((a[scrSort.k] ?? -1e9) > (b[scrSort.k] ?? -1e9) ? 1 : -1) * scrSort.dir);
  const cols = [
    { k: "symbol", h: "Symbol", f: (r) => symCell(r.symbol, r.name) }, { k: "price", h: "Last", num: 1, f: (r) => fmt(r.price) },
    { k: "score", h: "Score", num: 1, f: (r) => (r.score > 0 ? "+" : "") + r.score, cls: (r) => cls(r.score) }, { k: "rating", h: "Rating", f: (r) => esc(r.rating) },
    { k: "rsi", h: "RSI", num: 1, f: (r) => fmt(r.rsi, 1) }, { k: "adx", h: "ADX", num: 1, f: (r) => fmt(r.adx, 1) },
    { k: "atr_pct", h: "ATR %", num: 1, f: (r) => fmt(r.atr_pct, 2) },
    { k: "perf_1m", h: "1 month", num: 1, f: (r) => pct(r.perf_1m, 1), cls: (r) => cls(r.perf_1m) },
    { k: "perf_3m", h: "3 months", num: 1, f: (r) => pct(r.perf_3m, 1), cls: (r) => cls(r.perf_3m) },
    { k: "perf_1y", h: "1 year", num: 1, f: (r) => pct(r.perf_1y, 1), cls: (r) => cls(r.perf_1y) },
    { k: "above_sma200", h: "Above SMA200", f: (r) => (r.above_sma200 == null ? "–" : r.above_sma200 ? "yes" : "no") },
    { k: "events", h: "Recent signal", f: (r) => esc(r.events.join(", ")) },
  ];
  const el = $("#screener");
  const bad = SCR.filter((r) => r.error).map((r) => r.symbol);
  el.innerHTML = table(cols, rows, { sort: 1, click: (r) => r.symbol, empty: "No symbol matches this filter." }) + (bad.length ? `<p class="note">No data for ${esc(bad.join(", "))}.</p>` : "");
  $$("th", el).forEach((th) => th.addEventListener("click", () => { const k = cols[th.dataset.i].k; scrSort = { k, dir: scrSort.k === k ? -scrSort.dir : -1 }; renderScreener(); }));
  bindRowOpen(el);
}

$("#shock-run").addEventListener("click", () => load($("#shocks"), async () => {
  const rows = await api("shocks"), el = $("#shocks");
  el.innerHTML = table([
    { h: "Symbol", f: (r) => `<span class="sym">${esc(r.symbol)}</span><span class="sym-name">${day(r.t)}</span>` },
    { h: "Open gap", num: 1, f: (r) => pct(r.gap, 1), cls: (r) => cls(r.gap) },
    { h: "Rest of day", num: 1, f: (r) => pct(r.day, 1), cls: (r) => cls(r.day) },
    { h: "Volume", num: 1, f: (r) => fmt(r.vmult, 1) + "x" },
    { h: "Since then", num: 1, f: (r) => pct(r.since, 1), cls: (r) => cls(r.since) },
    { h: "Headlines", f: (r) => r.news.length ? r.news.map((n) => `<a href="${esc(n.link)}" target="_blank" rel="noopener">${esc(n.title)}</a>`).join("<br>") : "none found" },
  ], rows, { click: (r) => r.symbol, empty: "No news shock in the last two sessions." });
  bindRowOpen(el);
}, "screener"));

/* ---------- backtest ---------- */
let STRATS = null, btChart = null;
views.backtest = async () => {
  if (STRATS) return;
  try { STRATS = await api("strategies"); } catch (e) { $("#bt-out").innerHTML = errBox(e, "backtest"); return; }
  const sel = $("#bt-strat");
  sel.innerHTML = Object.entries(STRATS).map(([k, v]) => `<option value="${k}">${esc(v.name)}</option>`).join("");
  sel.addEventListener("change", btParams);
  btParams();
};
function btParams() {
  const p = STRATS[$("#bt-strat").value].params;
  $("#bt-params").innerHTML = Object.entries(p).map(([k, v]) => `<label class="f">${esc(k)}<input data-p="${k}" type="number" step="any" value="${v}"></label>`).join("");
}
$("#bt-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target, out = $("#bt-out");
  const params = {};
  $$("[data-p]", f).forEach((i) => (params[i.dataset.p] = +i.value));
  const body = Object.fromEntries(new FormData(f));
  body.allow_short = f.allow_short.checked;
  body.params = params;
  body.symbol = body.symbol.trim().toUpperCase();
  out.innerHTML = skel(6);
  try {
    const r = await api("backtest", body), m = r.metrics;
    out.innerHTML = `<h2>${esc(r.symbol)}, ${esc(r.strategy)}, ${day(r.start)} to ${day(r.end)}</h2>
      <div class="figures">
        <div class="figure hot"><b>${pct(m.return_pct, 1)}</b><span>Strategy return</span></div>
        <div class="figure"><b class="${cls(m.buy_hold_return_pct)}">${pct(m.buy_hold_return_pct, 1)}</b><span>Buy and hold</span></div>
        <div class="figure"><b>${pct(m.cagr_pct, 1)}</b><span>Per year (CAGR)</span></div>
        <div class="figure"><b>${fmt(m.max_drawdown_pct, 1)}%</b><span>Max drawdown (hold ${fmt(m.buy_hold_max_drawdown_pct, 1)}%)</span></div>
        <div class="figure"><b>${fmt(m.sharpe, 2)}</b><span>Sharpe</span></div>
        <div class="figure"><b>${m.trades}</b><span>Trades, win ${m.win_rate == null ? "–" : fmt(m.win_rate, 0) + "%"}</span></div>
        <div class="figure"><b>${fmt(m.profit_factor, 2)}</b><span>Profit factor</span></div>
        <div class="figure"><b>${fmt(m.exposure_pct, 0)}%</b><span>Time in market</span></div></div>
      <div class="chart-box" id="c-bt" style="height: 320px"><div class="chart-legend"><span><i class="k1"></i>Strategy</span><span><i class="k2"></i>Buy and hold</span></div></div>
      <p class="note">${r.bars} ${esc(r.interval)} bars, fee ${r.costs.fee_pct_per_side}% and slippage ${r.costs.slippage_pct_per_side}% per side. One test on one history is not evidence of a future edge: check other symbols, periods and nearby parameters.</p>
      <div class="panel"><h2>Trades</h2>${table([
        { h: "Entry", f: (t) => day(t.entry_t) }, { h: "Exit", f: (t) => day(t.exit_t) }, { h: "Side", f: (t) => (t.side > 0 ? "Long" : "Short") },
        { h: "Entry price", num: 1, f: (t) => fmt(t.entry) }, { h: "Exit price", num: 1, f: (t) => fmt(t.exit) },
        { h: "Return", num: 1, f: (t) => pct(t.ret_pct), cls: (t) => cls(t.ret_pct) }, { h: "Net P/L", num: 1, f: (t) => fmt(t.pnl, 2), cls: (t) => cls(t.pnl) }, { h: "Exit reason", f: (t) => esc(t.reason) },
      ], r.trades.slice().reverse(), { empty: "The rule never traded in this period." })}</div>`;
    const c = mkChart($("#c-bt"));
    c.addLineSeries({ color: css("--series-1"), lineWidth: 2, priceLineVisible: false }).setData(r.equity.map(([t, v]) => ({ time: t, value: v })));
    c.addLineSeries({ color: css("--series-2"), lineWidth: 2, priceLineVisible: false }).setData(r.buy_hold.map(([t, v]) => ({ time: t, value: v })));
    c.timeScale().fitContent();
  } catch (er) { out.innerHTML = errBox(er); }
});

/* ---------- calendar and alerts ---------- */
views.calendar = async () => {
  const el = $("#cal");
  load(el, async () => {
    const ev = await api("calendar"), now = Date.now() / 1000;
    el.innerHTML = table([
      { h: "Date (your time)", f: (r) => `${new Date(r.ts * 1000).toLocaleString("en-GB", { weekday: "short", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}${r.ts < now ? ` <span class="small muted">past</span>` : ""}` },
      { h: "Event", f: (r) => `<b>${esc(r.event)}</b><span class="sym-name">${esc(r.desc)}</span>` },
      { h: "Impact", f: (r) => esc(r.impact) },
      { h: "Source", f: (r) => `<a href="${esc(r.source)}" target="_blank" rel="noopener">schedule</a>` },
    ], ev, { empty: "No scheduled releases in the next 120 days in the calendar file." });
  }, "calendar");
  renderAlerts();
};
async function renderAlerts() {
  try {
    const d = await api("alerts");
    $("#alerts").innerHTML = table([
      { h: "Symbol", f: (r) => esc(r.symbol) }, { h: "Condition", f: (r) => `${r.op} ${fmt(r.price)}` },
      { h: "Status", f: (r) => (r.hit ? "triggered " + dt(r.hit) : "watching") },
      { h: "", f: (r) => `<button class="sm" data-ra="${r.id}">Remove</button>` },
    ], d.alerts, { empty: "No alerts. Add one above; the server checks prices every minute (crypto every 5 seconds)." });
    $$("[data-ra]").forEach((b) => b.addEventListener("click", async () => { await api("alerts", { action: "remove", id: +b.dataset.ra }); renderAlerts(); }));
    $("#alert-log").innerHTML = d.log.length ? `<ul class="news">${d.log.map((l) => `<li><span class="senti s-neu">${dt(l.ts)}</span><div>${esc(l.text)}</div></li>`).join("")}</ul>` : `<div class="empty">Nothing has triggered yet.</div>`;
    const hits = d.log.filter((l) => l.ts > (renderAlerts.seen || Date.now() / 1000 - 1));
    if (renderAlerts.seen && hits.length) toast("Alert: " + hits[0].text);
    renderAlerts.seen = Date.now() / 1000;
  } catch (e) { $("#alerts").innerHTML = errBox(e); }
}
$("#alert-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  try { await api("alerts", { symbol: f.symbol.value, op: f.op.value, price: f.price.value }); f.reset(); toast("Alert added"); renderAlerts(); } catch (er) { toast(er.message); }
});

/* ---------- risk tools ---------- */
function sizeCalc() {
  const f = $("#size-form"), A = +f.acct.value, r = +f.risk.value / 100, E = +f.entry.value, S = +f.stop.value, T = +f.target.value;
  const per = Math.abs(E - S);
  if (!A || !E || !per) { $("#size-out").innerHTML = `<div class="empty">Enter an account size, an entry and a stop that differ.</div>`; return; }
  const risk = A * r, qty = risk / per, rr = T ? Math.abs(T - E) / per : null;
  $("#size-out").innerHTML = `<div class="figures"><div class="figure hot"><b>${fmt(qty, 2)}</b><span>Units to buy</span></div><div class="figure"><b>${usd(qty * E)}</b><span>Position value</span></div><div class="figure"><b>${usd(risk)}</b><span>Loss at stop</span></div><div class="figure"><b>${rr ? fmt(rr, 2) : "–"}</b><span>Reward to risk</span></div></div>
    <p class="small">${qty * E > A ? "The position is larger than the account: it needs leverage, or a wider stop and fewer units." : `Uses ${fmt((qty * E / A) * 100, 1)}% of the account.`} ${rr ? `At this ratio you break even with a win rate above ${fmt(100 / (1 + rr), 1)}%.` : ""}</p>`;
}
function rorCalc() {
  const f = $("#ror-form"), w = +f.win.value / 100, rr = +f.rr.value, r = +f.risk.value / 100, n = Math.min(+f.n.value, 5000);
  const finals = [], dds = [];
  let ruin = 0;
  for (let s = 0; s < 2000; s++) {
    let eq = 1, pk = 1, dd = 0;
    for (let i = 0; i < n; i++) {
      eq *= Math.random() < w ? 1 + r * rr : 1 - r;
      pk = Math.max(pk, eq); dd = Math.max(dd, 1 - eq / pk);
    }
    finals.push(eq); dds.push(dd);
    if (dd >= 0.5) ruin++;
  }
  finals.sort((a, b) => a - b); dds.sort((a, b) => a - b);
  const q = (arr, p) => arr[Math.floor(p * (arr.length - 1))];
  const exp = w * rr - (1 - w);
  $("#ror-out").innerHTML = `<div class="figures"><div class="figure"><b class="${cls(exp)}">${exp >= 0 ? "+" : ""}${fmt(exp, 2)}R</b><span>Expectancy per trade</span></div><div class="figure"><b>${pct((q(finals, 0.5) - 1) * 100, 0)}</b><span>Median result</span></div><div class="figure"><b>${pct((q(finals, 0.05) - 1) * 100, 0)}</b><span>Bad case (5th percentile)</span></div><div class="figure"><b>${fmt(q(dds, 0.95) * 100, 0)}%</b><span>Drawdown, 95th percentile</span></div><div class="figure"><b>${fmt((ruin / 2000) * 100, 1)}%</b><span>Chance of a 50% drawdown</span></div></div>`;
}
["#size-form", "#ror-form"].forEach((id) => $(id).addEventListener("input", id === "#size-form" ? sizeCalc : rorCalc));
views.tools = () => { sizeCalc(); rorCalc(); };

/* ---------- overview of all accounts ---------- */
views.overview = async () => {
  const el = $("#ov-table");
  let d;
  try { d = await api("accounts"); } catch (e) { el.innerHTML = errBox(e, "accounts"); return; }
  $("#ov-sub").textContent = `1 USD = ${fmt(d.thb_per_usd, 2)} THB | social buzz study: ${d.buzz_events ?? "off"} events (analysis only, no account)`;
  el.innerHTML = table([
    { h: "Account", f: (r) => `<a href="#${r.tab}"><b>${esc(r.name)}</b></a>` },
    { h: "Start (THB)", num: 1, f: (r) => fmt(r.start_thb, 0) }, { h: "Start (USD)", num: 1, f: (r) => fmt(r.start_usd, 2) },
    { h: "Equity (USD)", num: 1, f: (r) => fmt(r.equity_usd, 2) },
    { h: "Equity (THB)", num: 1, f: (r) => fmt(r.equity_thb, 0) },
    { h: "Return", num: 1, f: (r) => pct(r.return_pct), cls: (r) => cls(r.return_pct) },
    { h: "Random control (USD)", num: 1, f: (r) => (r.control_usd != null ? fmt(r.control_usd, 2) : "-") },
    { h: "Open", num: 1, f: (r) => r.positions },
    { h: "Status", f: (r) => esc(r.status) },
    { h: "Note", f: (r) => esc(r.note) },
  ], d.rows, { empty: "No accounts." });
};

/* ---------- decision log ---------- */
let logSource = "llm";
let logRequest;
const logMarkup = new WeakMap();
const BADGE = { buy: "BUY", sell: "SELL", adjust: "ADJUST", hold: "PASS" };
const hmin = (s) => (s % 3600 === 0 ? s / 3600 + "h" : s / 3600 >= 1 ? (s / 3600).toFixed(1) + "h" : Math.round(s / 60) + "m");
function cycleCard(c) {
  const key = esc(c.ts);
  const when = new Date(c.ts * 1000).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit" });
  const byDec = {}; (c.decisions || []).forEach((d) => { byDec[d.symbol] = d; });
  const acts = {}; (c.actions || []).forEach((a) => { (acts[a.symbol] = acts[a.symbol] || []).push(a); });
  const outs = {}; (c.outcomes || []).forEach((o) => { (outs[o.symbol] = outs[o.symbol] || []).push(o); });
  const mk = c.market || {}, ac = c.account || {};
  const rows = (c.candidates || []).map((x) => {
    const d = byDec[x.symbol], a = acts[x.symbol] || [], o = outs[x.symbol] || [];
    const heads = (x.headlines || []).map((h) => `${esc(h.title)} <span class="muted">[${esc(h.source)}, lexicon ${h.lexicon ?? "-"}${h.ai_scores && Object.keys(h.ai_scores).length ? ", AI " + Object.values(h.ai_scores).join("/") : ""}]</span>`).join("<br>") || "-";
    const decision = d ? `<b>${BADGE[d.action] || esc(d.action)}</b>${d.action === "buy" ? ` margin ${fmt(d.size_pct, 1)}% x ${fmt(d.leverage || 1, 1)} | ${esc(d.entry || "market")}${d.limit_price ? " @ " + fmt(d.limit_price) : ""} | ${esc(d.horizon || "")} | stop ${fmt(d.stop_pct, 0)}%${d.target_pct ? " target " + fmt(d.target_pct, 0) + "%" : ""} | look again in ${d.review_in_min} min` : ""}<br>${esc(d.reason || "")}` : "<b>PASS</b> (no reason given)";
    const did = a.map((z) => z.kind === "skip" ? `<span class="muted">not executed: ${esc(z.why)}</span>` : z.kind === "order" ? execHtml({ status: z.status, notional_usd: z.notional_usd, margin_usd: z.margin_usd, leverage: z.leverage, entry: z.entry, limit_price: z.limit_price, valid_until: z.valid_until, stop_price: z.stop_price, target_price: z.target_price, risk_pct_equity: z.risk_pct_equity, clipped_by: z.clipped_by, control: z.control, scaled_in: z.scaled_in }) : esc(z.kind + " " + (z.status || ""))).join("<br>");
    const res = o.map((z) => `+${hmin(z.horizon_s)} vs SPY ${pct(z.abnormal * 100)}`).join("<br>");
    return `<tr><td>${symCell(x.symbol, x.name)}</td><td class="num">${pct(x.move_pct)}<br><span class="muted">vs SPY ${x.abnormal_pct != null ? pct(x.abnormal_pct) : "-"}</span></td><td class="num">${fmt(x.volume_ratio, 1)}x</td>
      <td>${decision}${did ? "<br>" + did : ""}</td><td>${heads}</td>
      <td><details data-log-detail="${key}:debate:${esc(x.symbol)}"><summary>bull / bear</summary><b>Bull:</b> ${esc((c.bull || {})[x.symbol] || "-")}<br><b>Bear:</b> ${esc((c.bear || {})[x.symbol] || "-")}</details></td><td>${res || "<span class='muted'>pending</span>"}</td></tr>`;
  }).join("");
  const extra = (c.decisions || []).filter((d) => !(c.candidates || []).some((x) => x.symbol === d.symbol)).map((d) => {
    const a = (acts[d.symbol] || []).map((z) => esc(z.kind + " " + (z.status || z.why || ""))).join(", ");
    return `<li><b>${BADGE[d.action] || esc(d.action)} ${esc(d.symbol)}</b> (position review): ${esc(d.reason || "")}${a ? " <span class='muted'>→ " + a + "</span>" : ""}</li>`;
  }).join("");
  return `<div class="panel" data-log-cycle="${key}" style="margin:12px 0"><div class="row spread"><b>${when} | ${esc(c.trigger || "?")}</b><span class="small muted">${esc(c.model || "")} ${c.seconds != null ? "| " + c.seconds + " s" : ""}</span></div>
    <p class="small muted">SPY ${mk.spy_move_pct != null ? pct(mk.spy_move_pct) : "-"} | VIX ${mk.vix ?? "-"} | account ${fmt(ac.equity_usd, 2)} USD, exposure ${ac.exposure_pct ?? 0}%, ${(ac.positions || []).length} open</p>
    ${c.market_view ? `<p><b>Market view:</b> ${esc(c.market_view)}</p>` : ""}${c.error ? `<p class="down">Error: ${esc(c.error)}</p>` : ""}
    ${rows ? `<div class="tbl-wrap"><table><thead><tr><th>Stock</th><th>Move</th><th>Volume</th><th>Decision and reason</th><th>Headlines the model saw</th><th>Debate</th><th>What happened next</th></tr></thead><tbody>${rows}</tbody></table></div>` : ""}
    ${extra ? `<ul>${extra}</ul>` : ""}${(c.rejected || []).length ? `<p class="small muted">Ignored model output: ${c.rejected.map(esc).join("; ")}</p>` : ""}
    <details data-log-detail="${key}:reply"><summary class="small muted">raw model reply</summary><pre class="small">${esc(c.raw || "")}</pre></details></div>`;
}
function updateLogMarkup(el, markup) {
  if (logMarkup.get(el) === markup) return;
  const open = new Set($$("details[open][data-log-detail]", el).map((detail) => detail.dataset.logDetail));
  const active = document.activeElement;
  const focused = active?.matches("summary") && el.contains(active) ? active.parentElement.dataset.logDetail : undefined;
  const scrollKey = (wrap) => wrap.closest("[data-log-cycle]")?.dataset.logCycle || "";
  const scroll = new Map($$(".tbl-wrap", el).map((wrap) => [scrollKey(wrap), wrap.scrollLeft]));
  el.innerHTML = markup;
  logMarkup.set(el, markup);
  for (const detail of $$("details[data-log-detail]", el)) {
    detail.open = open.has(detail.dataset.logDetail);
    if (focused === detail.dataset.logDetail) $("summary", detail).focus({ preventScroll: true });
  }
  for (const wrap of $$(".tbl-wrap", el)) wrap.scrollLeft = scroll.get(scrollKey(wrap)) || 0;
}
views.logs = async () => {
  $("#lg-llm").onclick = () => { logSource = "llm"; views.logs(); };
  $("#lg-evt").onclick = () => { logSource = "evt"; views.logs(); };
  const box = $("#lg-cycles");
  const source = logSource;
  if (logRequest?.source === source) return;
  const request = logRequest = { source };
  const current = () => logRequest === request && logSource === source && route.view === "logs";
  try {
    if (source === "llm") {
      const d = await api("llm_log?n=30");
      if (!current()) return;
      updateLogMarkup($("#lg-note"), "Each card is one decision cycle of the DeepSeek trader: what it was shown, the bull and bear cases, its decision and reason for every stock (including why it passed), what the system did, and the result afterwards. Newest first.");
      updateLogMarkup(box, d.cycles.length ? d.cycles.map(cycleCard).join("") : `<div class="empty">No decision cycles yet. The model is asked when a stock moves 5%+ on real volume, and to review open positions.</div>`);
      updateLogMarkup($("#lg-closed"), table([
        { h: "When", f: (r) => new Date(r.ts * 1000).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) },
        { h: "Account", f: (r) => esc(r.account || r.kind) }, { h: "Stock", f: (r) => symCell(r.symbol || "", "") },
        { h: "Why closed", f: (r) => esc(r.reason || r.message || "") }, { h: "P/L %", num: 1, f: (r) => (r.pnl_pct != null ? pct(r.pnl_pct) : "-"), cls: (r) => cls(r.pnl_pct) },
        { h: "Held (h)", num: 1, f: (r) => (r.held_hours != null ? fmt(r.held_hours, 1) : "-") },
      ], d.closed, { empty: "No closed trades yet." }));
    } else {
      const d = await api("event_log?n=60");
      if (!current()) return;
      updateLogMarkup($("#lg-note"), "Event trader (fixed rule): every large-cap move of 5%+ on real volume, with the headlines, what the rule did, and why it did not trade when it did not.");
      updateLogMarkup(box, table([
        { h: "When", f: (r) => new Date(r.ts * 1000).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) },
        { h: "What", f: (r) => esc(r.kind) }, { h: "Stock", f: (r) => symCell(r.symbol || "", "") },
        { h: "Move", num: 1, f: (r) => (r.move_pct != null ? pct(r.move_pct) : "-") },
        { h: "Context", f: (r) => (r.kind === "event" ? `SPY ${r.spy_move_pct != null ? pct(r.spy_move_pct) : "-"}, vs SPY ${r.abnormal_move_pct != null ? pct(r.abnormal_move_pct) : "-"}, VIX ${r.vix ?? "-"}, volume ${fmt(r.vol_ratio, 1)}x` : "") },
        { h: "Decision", f: (r) => (r.kind === "event" ? (r.entry ? `bought ${fmt(r.entry.usd, 2)} USD (control ${esc((r.control || {}).symbol || "-")})` : esc(r.skipped ? "not traded: " + r.skipped : r.direction === "down" ? "not traded: down-move (data only)" : "-")) : esc(r.message || "")) },
        { h: "Headlines", f: (r) => (r.headlines || []).map((x) => esc(x.title)).join("<br>") },
      ], d.rows, { empty: "No events yet." }));
      updateLogMarkup($("#lg-closed"), "");
    }
  } catch (e) {
    if (current()) updateLogMarkup(box, errBox(e, "logs"));
  } finally {
    if (logRequest === request) logRequest = undefined;
  }
};

function execHtml(x) {
  if (!x) return "-";
  if (x.status === "skipped") return `<span class="muted">not executed: ${esc(x.why || "")}</span>`;
  const bits = [esc(x.status) + (x.scaled_in ? " (added to position)" : "")];
  if (x.notional_usd != null) bits.push(`notional ${fmt(x.notional_usd, 2)} USD, margin ${fmt(x.margin_usd, 2)} USD, ${fmt(x.leverage, 1)}x`);
  if (x.entry === "limit") bits.push(`limit ${fmt(x.limit_price)}${x.valid_until ? " until " + new Date(x.valid_until * 1000).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }) : ""}`);
  if (x.stop_price) bits.push(`stop ${fmt(x.stop_price)}${x.target_price ? ", target " + fmt(x.target_price) : ""}`);
  if (x.risk_pct_equity != null) bits.push(`loss at stop ${fmt(x.risk_pct_equity, 1)}% of equity`);
  if ((x.clipped_by || []).length) bits.push(`<span class="muted">cut by: ${esc(x.clipped_by.join("; "))}</span>`);
  if (x.control) bits.push(`control ${esc(x.control)}`);
  return bits.join("<br>");
}

/* ---------- DeepSeek trader ---------- */
views.llm = async () => {
  const figs = $("#llm-figs");
  let l;
  try { l = await api("llm_trader"); } catch (e) { figs.innerHTML = errBox(e, "llm_trader"); return; }
  if (l.disabled) { figs.innerHTML = `<div class="empty">The DeepSeek trader is off on this server (needs the OPENROUTER_API_KEY secret).</div>`; return; }
  const ev = l.evaluation || {}, dis = ev.discrimination || {};
  $("#llm-sub").textContent = `${l.model} | calls today ${l.calls_today}/${l.max_calls_day}${l.error ? " | " + l.error : ""}`;
  figs.innerHTML = `<div class="figures">
    <div class="figure hot"><b>${fmt(l.equity_usd, 2)} USD</b><span>DeepSeek account (${fmt(l.equity_thb, 0)} THB, from ${fmt(l.capital_thb, 0)} THB = ${fmt(l.capital_usd, 2)} USD)</span></div>
    <div class="figure"><b>${fmt(l.control_equity_usd, 2)} USD</b><span>Random control account</span></div>
    <div class="figure"><b>${ev.closed_pairs ?? 0} / ${ev.needed ?? 30}</b><span>closed pairs needed</span></div>
    <div class="figure"><b>${l.paused ? "Paused" : "Running"}</b><span>last scan ${l.last_scan_age_s ?? "never"} s ago</span></div></div>
    <p><b>Verdict:</b> ${esc(ev.verdict || "")}</p>
    <p class="small muted">Every stock shown to the model is also scored +1 day vs SPY. Bought: ${dis.bought ? dis.bought.n : 0} scored${dis.bought && dis.bought.mean_abnormal_1d != null ? ", mean " + pct(dis.bought.mean_abnormal_1d * 100) : ""}.
    Passed: ${dis.passed ? dis.passed.n : 0} scored${dis.passed && dis.passed.mean_abnormal_1d != null ? ", mean " + pct(dis.passed.mean_abnormal_1d * 100) : ""}. Rules: research/llm_trader/protocol.md</p>`;
  $("#llm-pos").innerHTML = table([
    { h: "Stock", f: (r) => symCell(r.symbol, "") }, { h: "Entry", num: 1, f: (r) => fmt(r.entry) }, { h: "Mark", num: 1, f: (r) => fmt(r.mark) },
    { h: "P/L", num: 1, f: (r) => pct(r.pnl_pct), cls: (r) => cls(r.pnl_pct) },
    { h: "Leverage", num: 1, f: (r) => fmt(r.leverage, 1) + "x" },
    { h: "Notional (USD)", num: 1, f: (r) => fmt(r.notional_usd, 2) }, { h: "Margin (USD)", num: 1, f: (r) => fmt(r.margin_usd, 2) },
    { h: "Stop", num: 1, f: (r) => fmt(r.stop) }, { h: "Target", num: 1, f: (r) => fmt(r.target) },
    { h: "Horizon", f: (r) => esc(r.horizon || "-") }, { h: "Held (h)", num: 1, f: (r) => fmt(r.held_hours, 1) },
    { h: "Why", f: (r) => esc(r.your_reason || "") + ((r.clipped_by || []).length ? `<br><span class="muted">cut by: ${esc(r.clipped_by.join("; "))}</span>` : "") },
  ], l.positions, { empty: "No open positions." });
  $("#llm-list").innerHTML = table([
    { h: "When", f: (r) => new Date(r.ts * 1000).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit" }) },
    { h: "Stock", f: (r) => symCell(r.symbol, "") }, { h: "Action", f: (r) => esc(r.action) },
    { h: "Size % (margin)", num: 1, f: (r) => (r.action === "buy" ? fmt(r.size_pct, 1) : "-") }, { h: "Leverage", num: 1, f: (r) => (r.action === "buy" ? fmt(r.leverage, 1) + "x" : "-") },
    { h: "Entry", f: (r) => (r.action === "buy" ? esc(r.entry || "market") + (r.limit_price ? " @ " + fmt(r.limit_price) : "") : "-") },
    { h: "Horizon", f: (r) => esc(r.horizon || "-") },
    { h: "Stop / target %", f: (r) => (["buy", "adjust"].includes(r.action) ? `${r.stop_pct != null ? fmt(r.stop_pct, 0) : "-"} / ${r.target_pct != null ? fmt(r.target_pct, 0) : "-"}` : "-") },
    { h: "Look again (min)", num: 1, f: (r) => (r.action === "sell" ? "-" : fmt(r.review_in_min, 0)) },
    { h: "Result", f: (r) => execHtml(r.executed) },
    { h: "Reason (model)", f: (r) => esc(r.reason) },
  ], l.decisions, { empty: "No decisions yet; the model is asked when new shocks appear." });
};

/* ---------- social buzz ---------- */
views.buzz = async () => {
  const figs = $("#bz-figs");
  let d;
  try { d = await api("buzz"); } catch (e) { figs.innerHTML = errBox(e, "buzz"); return; }
  if (d.disabled) { figs.innerHTML = `<div class="empty">Buzz monitor is off on this server.</div>`; return; }
  const e1 = d.eval_1d || {};
  $("#bz-sub").textContent = `scans every ${d.scan_every_s}s, last ${d.last_scan_age_s ?? "never"}s ago | universe ${d.universe} stocks${d.error ? " | error: " + d.error : ""}`;
  figs.innerHTML = `<div class="figures">
    <div class="figure hot"><b>${d.n_events}</b><span>buzz events</span></div>
    <div class="figure"><b>${e1.events ?? 0} / ${e1.needed ?? 100}</b><span>events with a +1d result</span></div>
    <div class="figure"><b>${e1.mean != null ? pct(e1.mean * 100) : "-"}</b><span>mean +1d return vs SPY</span></div>
    <div class="figure"><b>${e1.control_mean != null ? pct(e1.control_mean * 100) : "-"}</b><span>matched controls</span></div></div>
    <p class="small muted">${esc(d.rule)}</p><p><b>Verdict:</b> ${esc(e1.verdict || "")}</p>`;
  $("#bz-top").innerHTML = table([
    { h: "Rank", num: 1, f: (r) => r.rank }, { h: "Ticker", f: (r) => symCell(r.ticker, r.name) },
    { h: "Mentions", num: 1, f: (r) => fmt(r.mentions, 0) }, { h: "24h ago", num: 1, f: (r) => fmt(r.mentions_24h, 0) },
    { h: "Upvotes", num: 1, f: (r) => fmt(r.upvotes, 0) },
  ], d.top_now, { empty: "Waiting for the first scan." });
  $("#bz-list").innerHTML = table([
    { h: "When", f: (r) => new Date(r.ts * 1000).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) },
    { h: "Ticker", f: (r) => symCell(r.ticker, r.name) },
    { h: "Mentions", num: 1, f: (r) => `${r.mentions} (was ${r.mentions_24h})` },
    { h: "Move", num: 1, f: (r) => pct(r.move_pct), cls: (r) => cls(r.move_pct) },
    { h: "+1h / +1d vs SPY", f: (r) => `${r.out["3600"] != null ? pct(r.out["3600"] * 100) : "-"} / ${r.out["86400"] != null ? pct(r.out["86400"] * 100) : "-"}` },
    { h: "Control +1d", f: (r) => (r.out_ctrl["86400"] != null ? pct(r.out_ctrl["86400"] * 100) : esc(r.control ? r.control.symbol : "-")) },
    { h: "Headlines", f: (r) => (r.headlines || []).map((x) => esc(x.title)).join("<br>") || "-" },
  ], d.events, { empty: "No events yet." });
};

/* ---------- event trader ---------- */
views.events = async () => {
  const figs = $("#ev-figs"), list = $("#ev-list");
  let d;
  try { d = await api("events"); } catch (e) { figs.innerHTML = errBox(e, "events"); return; }
  const ev = d.evaluation || {};
  $("#ev-sub").textContent = `scans every ${d.scan_every_s}s, last scan ${d.last_scan_age_s ?? "never"}s ago${d.error ? " | error: " + d.error : ""}`;
  figs.innerHTML = `<div class="figures">
    <div class="figure hot"><b>${fmt(d.equity_thb, 0)} THB</b><span>Rule account, from ${fmt(d.capital_thb, 0)} THB</span></div>
    <div class="figure"><b>${fmt(d.control_equity_usd, 2)} USD</b><span>Random control account</span></div>
    <div class="figure"><b>${d.n_events}</b><span>events (${d.n_up} up-shocks)</span></div>
    <div class="figure"><b>${ev.closed_pairs ?? 0} / ${ev.needed ?? 30}</b><span>closed pairs needed</span></div>
    <div class="figure"><b>${d.paused ? "Paused" : "Running"}</b><span>${esc(d.rules.shock)}</span></div></div>
    <p class="small muted">${esc(d.rules.trade)}</p><p><b>Verdict:</b> ${esc(ev.verdict || "")}</p>`;
  $("#ev-pos").innerHTML = table([
    { h: "Stock", f: (r) => symCell(r.symbol, "") }, { h: "Entry", num: 1, f: (r) => fmt(r.entry) }, { h: "Mark", num: 1, f: (r) => fmt(r.mark) },
    { h: "P/L", num: 1, f: (r) => pct(r.pnl_pct), cls: (r) => cls(r.pnl_pct) }, { h: "Notional (USD)", num: 1, f: (r) => fmt(r.notional_usd, 2) },
    { h: "Stop", num: 1, f: (r) => fmt(r.stop) },
    { h: "Sells at (20 h rule)", f: (r) => new Date(r.exit_at * 1000).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) },
    { h: "Why it bought", f: (r) => esc(r.why || "") },
    { h: "Random control", f: (r) => (r.control ? `${esc(r.control.symbol)} ${r.control.pnl_pct != null ? pct(r.control.pnl_pct) : ""}` : "-") },
  ], d.positions, { empty: "No open positions right now. The rule holds at most 3 at a time; later shocks show 'max positions' below." });
  list.innerHTML = table([
    { h: "When", f: (r) => new Date(r.ts * 1000).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) },
    { h: "Stock", f: (r) => symCell(r.symbol, "") },
    { h: "Move", num: 1, f: (r) => pct(r.move_pct), cls: (r) => cls(r.move_pct) },
    { h: "Volume x", num: 1, f: (r) => fmt(r.vol_ratio, 1) },
    { h: "Traded", f: (r) => (r.entry ? `long ${fmt(r.entry.usd, 2)} USD vs ${esc(r.control ? r.control.symbol : "-")}` : esc(r.skipped || (r.direction === "down" ? "data only" : "-"))) },
    { h: "+1h / +1d", f: (r) => `${r.out["3600"] != null ? pct(r.out["3600"] * 100) : "-"} / ${r.out["86400"] != null ? pct(r.out["86400"] * 100) : "-"}` },
    { h: "Headlines", f: (r) => (r.headlines || []).map((x) => esc(x.title)).join("<br>") || "-" },
  ], d.events, { empty: "No events yet." });
};

/* ---------- auto trader ---------- */
let autoChart = null;
const TAGN = { below_sma200: "below its 200-day average", vol_spike: "volatility spike" };
views.auto = async () => {
  const figs = $("#auto-figs");
  if (!figs.innerHTML) figs.innerHTML = skel(3);
  let d;
  try { d = await api("auto"); } catch (e) { figs.innerHTML = errBox(e, "auto"); return; }
  const s = d.stats, m = d.model || {}, thbRet = d.equity_thb != null ? d.equity_thb - d.capital_thb : null;
  figs.innerHTML = `<div class="figures">
    <div class="figure hot"><b>${fmt(d.equity_thb, 0)} THB</b><span>Equity, from ${fmt(d.capital_thb, 0)} THB</span></div>
    <div class="figure"><b class="${cls(thbRet)}">${thbRet == null ? "–" : (thbRet >= 0 ? "+" : "") + fmt(thbRet, 0)} THB</b><span>Profit or loss</span></div>
    <div class="figure"><b class="${cls(s.return_pct)}">${pct(s.return_pct)}</b><span>Return in USD</span></div>
    <div class="figure"><b>${usd(s.equity)}</b><span>Equity in USD</span></div>
    <div class="figure"><b>${d.months.length}</b><span>Months completed</span></div>
    <div class="figure"><b>${fmt(s.max_drawdown_pct, 1)}%</b><span>Max drawdown</span></div>
    <div class="figure"><b>${d.paused ? "Paused" : d.learning ? "Learning" : "Running"}</b><span>rebalances monthly, checks every ${d.check_every_s || 900} s</span></div></div>`;
  $("#auto-pause").textContent = d.paused ? "Resume" : "Pause";
  $("#auto-pause").dataset.auto = d.paused ? "resume" : "pause";
  const v = m.valid, sv = m.spy_valid;
  $("#auto-model").innerHTML = m.label ? `<p><b>${esc(m.label)}</b>, chosen from ${m.settings_tested} settings. ${m.status === "live" ? "Trading it." : "Not trading: it lost money in the validation years."}</p>
    ${table([
      { h: "Period", f: (r) => `${esc(r.k)}<span class="sym-name">${esc(r.span)}</span>` },
      { h: "Per year", num: 1, f: (r) => pct(r.s.cagr, 1), cls: (r) => cls(r.s.cagr) },
      { h: "Max drawdown", num: 1, f: (r) => fmt(r.s.mdd, 1) + "%" },
      { h: "Worst year", num: 1, f: (r) => pct(r.s.worst_year, 1), cls: (r) => cls(r.s.worst_year) },
      { h: "Positive years", num: 1, f: (r) => esc(r.s.pos_years) },
      { h: "Sharpe", num: 1, f: (r) => fmt(r.s.sharpe, 2) },
    ], [{ k: "Train (used to choose)", span: m.train_span, s: m.train }, { k: "Validation (not used to choose)", span: m.valid_span, s: v }, { k: "SPY buy and hold, validation", span: m.valid_span, s: sv }])}` : `<div class="empty">Learning has not finished yet. The first pass takes under a minute after start.</div>`;
  $("#auto-targets").innerHTML = d.targets.length ? table([
    { h: "Asset", f: (r) => symCell(r.symbol, r.name) }, { h: "Target", num: 1, f: (r) => fmt(r.weight, 0) + "%" },
    { h: "Flags at entry", f: (r) => esc(r.tags.map((t) => TAGN[t] || t).join(", ") || "none") },
  ], d.targets) : `<div class="empty">All cash for ${esc(d.rebalanced || "this month")}: no asset beat cash over the lookback, so the rule stays out. It checks again at the next monthly rebalance.</div>`;
  const li = (arr, empty) => (arr.length ? `<ul class="news">${arr.map((l) => `<li><span class="senti s-neu">${dt(l.ts)}</span><div>${esc(l.text)}</div></li>`).join("")}</ul>` : `<div class="empty">${empty}</div>`);
  $("#auto-lessons").innerHTML = li(d.lessons.slice(0, 40), "No lessons yet.");
  $("#auto-log").innerHTML = li(d.log.slice(0, 40), "No activity yet.");
  $("#auto-months").innerHTML = table([
    { h: "Month", f: (r) => esc(r.month) }, { h: "Return", num: 1, f: (r) => pct(r.ret), cls: (r) => cls(r.ret) },
    { h: "Held", f: (r) => esc(Object.keys(r.hold).join(", ") || "cash") }, { h: "Flags", f: (r) => esc(r.tags.map((t) => TAGN[t] || t).join(", ") || "none") },
  ], d.months, { empty: "No month completed yet. The first result appears at the next month change." });
  $("#auto-pos").innerHTML = table([
    { h: "Asset", f: (r) => symCell(r.symbol, r.name) }, { h: "Qty", num: 1, f: (r) => fmt(r.qty, null) }, { h: "Entry", num: 1, f: (r) => fmt(r.entry) },
    { h: "Mark", num: 1, f: (r) => fmt(r.mark) }, { h: "Value", num: 1, f: (r) => usd(r.value_usd) }, { h: "Weight", num: 1, f: (r) => fmt(r.weight, 0) + "%" },
    { h: "P/L", num: 1, f: (r) => usd(r.pnl_usd), cls: (r) => cls(r.pnl_usd) },
  ], d.positions, { empty: "No open position: the portfolio is in cash." });
  $("#auto-grid").innerHTML = table([
    { h: "Setting", f: (r) => esc(r.label) }, { h: "Train per year", num: 1, f: (r) => pct(r.train.cagr, 1), cls: (r) => cls(r.train.cagr) },
    { h: "Train Sharpe", num: 1, f: (r) => fmt(r.train.sharpe, 2) }, { h: "Validation per year", num: 1, f: (r) => pct(r.valid.cagr, 1), cls: (r) => cls(r.valid.cagr) },
    { h: "Validation drawdown", num: 1, f: (r) => fmt(r.valid.mdd, 1) + "%" },
  ], d.grid, { empty: "Not learned yet." });
  if (!autoChart) { autoChart = mkChart($("#c-auto")); autoChart._s = autoChart.addAreaSeries({ lineColor: css("--series-1"), topColor: css("--color-up-fill"), bottomColor: "rgba(0, 0, 0, 0)", lineWidth: 2 }); }
  const seen = new Set();
  autoChart._s.setData([...d.equity_curve, [Date.now() / 1000, s.equity]].map(([t, val]) => ({ time: Math.floor(t), value: val })).filter((p) => !seen.has(p.time) && seen.add(p.time)));
  autoChart.timeScale().fitContent();
  renderHunter();
};
async function renderHunter() {
  let h;
  try { h = await api("hunter"); } catch (e) { $("#hunt-figs").innerHTML = errBox(e); return; }
  const pl = h.equity_thb - h.capital_thb;
  $("#hunt-figs").innerHTML = `<div class="figures"><div class="figure ${h.ruined ? "" : "hot"}"><b>${fmt(h.equity_thb, 0)} THB</b><span>Equity, from ${fmt(h.capital_thb, 0)} THB</span></div>
    <div class="figure"><b class="${cls(pl)}">${pl >= 0 ? "+" : ""}${fmt(pl, 0)} THB</b><span>Profit or loss</span></div>
    <div class="figure"><b>${h.month_multiple == null ? "–" : fmt(h.month_multiple, 2) + "x"}</b><span>This month vs its start</span></div>
    <div class="figure"><b>${h.ruined ? "Ruined" : h.target_done ? "Target hit" : "Hunting"}</b><span>leverage ${h.lev}x</span></div></div>`;
  $("#hunt-pos").innerHTML = table([{ h: "Coin", f: (r) => esc(r.symbol) }, { h: "Entry", num: 1, f: (r) => fmt(r.entry) }, { h: "Mark", num: 1, f: (r) => fmt(r.mark) }, { h: "Notional", num: 1, f: (r) => usd(r.notional) }], h.positions, { empty: "Flat: no coin is in an uptrend (above its 50-day average with a positive 30-day return)." });
  $("#hunt-months").innerHTML = table([{ h: "Month", f: (r) => esc(r.month) }, { h: "Result", num: 1, f: (r) => fmt(r.multiple, 2) + "x", cls: (r) => cls(r.multiple - 1) }], h.months, { empty: "No month finished yet." });
  $("#hunt-log").innerHTML = h.log.length ? `<ul class="news">${h.log.slice(0, 25).map((l) => `<li><span class="senti s-neu">${dt(l.ts)}</span><div>${esc(l.text)}</div></li>`).join("")}</ul>` : `<div class="empty">No activity yet.</div>`;
}
$("#hunt-reset").addEventListener("click", async (e) => {
  const b = e.currentTarget;
  if (!b.dataset.armed) { b.dataset.armed = 1; b.textContent = "Press again to restart"; setTimeout(() => { delete b.dataset.armed; b.textContent = "Restart hunter"; }, 4000); return; }
  delete b.dataset.armed; b.textContent = "Restart hunter";
  await api("hunter", { action: "reset" }); toast("Hunter restarted with 5,000 THB"); setTimeout(renderHunter, 1500);
});
$$("[data-auto]").forEach((b) => b.addEventListener("click", async () => {
  const act = b.dataset.auto;
  if (act === "reset") {
    if (!b.dataset.armed) { b.dataset.armed = 1; b.textContent = "Press again to erase"; setTimeout(() => { delete b.dataset.armed; b.textContent = "Restart"; }, 4000); return; }
    delete b.dataset.armed; b.textContent = "Restart";
  }
  try { await api("auto", { action: act }); toast(act === "learn" ? "Relearning" : act === "reset" ? "Restarted with 5,000 THB" : act === "pause" ? "Paused" : "Resumed"); setTimeout(views.auto, 1500); } catch (e) { toast(e.message); }
}));

/* ---------- live refresh ---------- */
setInterval(() => {
  if (document.hidden) return;
  if (route.view === "markets") views.markets();
  else if (route.view === "overview") views.overview();
  else if (route.view === "auto") views.auto();
  else if (route.view === "events") views.events();
  else if (route.view === "llm") views.llm();
  else if (route.view === "logs") views.logs();
  else if (route.view === "buzz") views.buzz();
  else if (route.view === "portfolio" || route.view === "chart") refreshAccount();
  if (route.view === "chart" && curSym) api("quote?symbol=" + encodeURIComponent(curSym)).then((q) => { if (q && !q.error && curSym === route.symbol) { lastQuote = q; const el = $("#qhead .px"); if (el) el.textContent = fmt(q.price); renderTicket(); } }).catch(() => {});
  renderAlerts();
}, 5000);

/* ---------- language switch (English / Thai) ---------- */
/* Static text is translated by exact match; numbers, tickers, headlines and the model's own notes stay as they are
   (the DeepSeek trader writes its reasons in Thai itself). Sentences with embedded numbers are not covered. */
const TH = {
  "Overview": "ภาพรวม", "Auto trader": "บอทหลัก", "Markets": "ตลาด", "Chart and analysis": "กราฟและวิเคราะห์", "Portfolio": "พอร์ต",
  "DeepSeek": "ดีปซีค", "Logs": "บันทึกการตัดสินใจ", "Events": "เหตุการณ์", "Buzz": "กระแสโซเชียล", "News": "ข่าว", "Screener": "สแกนหุ้น",
  "Backtest": "ทดสอบย้อนหลัง", "Calendar and alerts": "ปฏิทินและแจ้งเตือน", "Risk tools": "เครื่องมือความเสี่ยง",
  "Manual sandbox": "บัญชีทดลองสั่งเอง", "Simulated money": "เงินจำลอง",
  "All simulated accounts side by side": "ทุกบัญชีจำลองเทียบกัน", "Account": "บัญชี", "Start (USD)": "ทุนเริ่ม (USD)",
  "Equity (USD)": "มูลค่า (USD)", "Equity (THB)": "มูลค่า (บาท)", "Start (THB)": "ทุนเริ่ม (บาท)", "Return": "ผลตอบแทน", "Random control (USD)": "บัญชีสุ่มเทียบ (USD)",
  "Open": "ถืออยู่", "Status": "สถานะ", "Note": "หมายเหตุ", "Loading...": "กำลังโหลด...",
  "DeepSeek trader (paper money)": "DeepSeek เทรดเดอร์ (เงินจำลอง)", "Open positions": "ตำแหน่งที่ถืออยู่",
  "Decisions and the model's reasons": "การตัดสินใจและเหตุผลของโมเดล", "Open positions of the rule": "ตำแหน่งที่กติกาถืออยู่",
  "Event trader (paper)": "Event trader (เงินจำลอง)", "Large single-stock moves with headlines": "หุ้นที่ขยับแรงพร้อมข่าว",
  "Decision log: why it bought, why it passed": "บันทึกการตัดสินใจ: ทำไมซื้อ ทำไมไม่ซื้อ", "DeepSeek trader": "DeepSeek trader",
  "Event trader": "Event trader", "Closed trades (stops, targets, sells) and errors": "การปิดสถานะ (ตัดขาดทุน เป้า ขาย) และข้อผิดพลาด",
  "Social buzz, whole US market (analysis only)": "กระแสโซเชียลทั้งตลาดสหรัฐ (วิเคราะห์เท่านั้น)", "Most mentioned right now": "ถูกพูดถึงมากที่สุดตอนนี้",
  "Buzz events (surges in mentions) and what happened next": "เหตุการณ์กระแสพุ่ง (คนพูดถึงเพิ่มกะทันหัน) และผลหลังจากนั้น",
  "Stock": "หุ้น", "Entry": "ราคาเข้า", "Mark": "ราคาตอนนี้", "P/L": "กำไร/ขาดทุน", "Stop": "ตัดขาดทุน", "Target": "เป้ากำไร",
  "Horizon": "ระยะถือ", "Held (h)": "ถือมา (ชม.)", "Why": "เหตุผล", "When": "เวลา", "Action": "การตัดสินใจ", "Size %": "ขนาด %",
  "Size % (margin)": "ขนาด % (เงินประกัน)", "Leverage": "เลเวอเรจ", "Notional (USD)": "มูลค่าสถานะ (USD)", "Margin (USD)": "เงินประกัน (USD)",
  "Result": "ผล", "Reason (model)": "เหตุผล (โมเดล)", "Stop / target %": "ตัดขาดทุน / เป้า %", "Look again (min)": "กลับมาดูอีก (นาที)",
  "Move": "ขยับ", "Volume": "ปริมาณ", "Volume x": "ปริมาณ x", "Traded": "ผลการเทรด", "Headlines": "พาดหัวข่าว", "Debate": "โต้แย้ง",
  "Decision and reason": "การตัดสินใจและเหตุผล", "Headlines the model saw": "ข่าวที่โมเดลเห็น", "What happened next": "หลังจากนั้น",
  "Sells at (20 h rule)": "ขายเมื่อ (กฎ 20 ชม.)", "Why it bought": "ทำไมถึงซื้อ", "Random control": "หุ้นสุ่มเทียบ", "Account": "บัญชี",
  "Why closed": "ปิดเพราะ", "P/L %": "กำไร/ขาดทุน %", "Mentions": "จำนวนที่ถูกพูดถึง", "24h ago": "24 ชม.ก่อน", "Upvotes": "โหวตขึ้น",
  "Rank": "อันดับ", "Ticker": "สัญลักษณ์", "+1h / +1d vs SPY": "+1 ชม. / +1 วัน เทียบ SPY", "Control +1d": "หุ้นสุ่ม +1 วัน",
  "What": "ประเภท", "Context": "บริบท", "Decision": "การตัดสินใจ", "Running": "กำลังทำงาน", "Paused": "หยุดอยู่",
  "DeepSeek account": "บัญชี DeepSeek", "Random control account": "บัญชีสุ่มเทียบ", "closed pairs needed": "คู่ที่ปิดแล้ว / ที่ต้องการ",
  "events with a +1d result": "เหตุการณ์ที่มีผล +1 วัน", "buzz events": "เหตุการณ์กระแส", "mean +1d return vs SPY": "ผลตอบแทน +1 วันเฉลี่ย เทียบ SPY",
  "matched controls": "หุ้นสุ่มที่เทียบ", "Verdict:": "ข้อสรุป:", "Refresh": "รีเฟรช", "Reset account": "รีเซ็ตบัญชี", "Pause": "หยุดชั่วคราว",
  "Restart": "เริ่มใหม่", "Learn now": "เรียนรู้ใหม่", "Equity": "มูลค่าบัญชี", "Profit or loss": "กำไรหรือขาดทุน", "Months completed": "เดือนที่ครบ",
  "Max drawdown": "ขาดทุนสูงสุดจากจุดสูงสุด", "Equity in USD": "มูลค่าเป็น USD", "Return in USD": "ผลตอบแทนเป็น USD", "Current model": "โมเดลปัจจุบัน",
  "This month's targets": "เป้าหมายเดือนนี้", "Equity curve": "เส้นมูลค่าบัญชี", "Orders": "ออเดอร์", "Allocation": "สัดส่วน", "Cash balance": "เงินสด",
  "Open profit or loss": "กำไรขาดทุนที่ยังไม่ปิด", "Realised": "ปิดแล้ว", "Buying power": "กำลังซื้อ", "Win rate, 0 trades": "อัตราชนะ, 0 เทรด",
  "Top headlines": "พาดหัวข่าวเด่น", "Order ticket": "ใบสั่งซื้อขาย", "Technical rating": "คะแนนทางเทคนิค", "Run scan": "สแกน",
  "Broad list": "รายการกว้าง", "Watchlist": "รายการที่ติดตาม", "Run backtest": "ทดสอบย้อนหลัง", "Add alert": "เพิ่มแจ้งเตือน",
  "Date (your time)": "วันที่ (เวลาของคุณ)", "Impact": "ผลกระทบ", "Source": "แหล่งที่มา", "Price alerts": "แจ้งเตือนราคา",
  "No open positions.": "ไม่มีตำแหน่งที่ถืออยู่", "No decisions yet.": "ยังไม่มีการตัดสินใจ", "No events yet.": "ยังไม่มีเหตุการณ์",
  "Nothing here yet.": "ยังไม่มีข้อมูล", "No accounts.": "ไม่มีบัญชี", "Waiting for the first scan.": "รอการสแกนครั้งแรก", "No closed trades yet.": "ยังไม่มีการปิดสถานะ",
};
let LANG = "en";
try { LANG = localStorage.getItem("lang") || "en"; } catch (e) { /* private window */ }
const NOTE_TH = [
  [/^Every account below is separate play money.*$/, "ทุกบัญชีด้านล่างเป็นเงินจำลองแยกกัน แต่ละบัญชีมีทุนเริ่มต้นและกติกาของตัวเอง ตัวเลข 100,000 ดอลลาร์ที่แถบบนคือบัญชีทดลองสั่งเอง ไม่ใช่บอท ส่วนบอทเริ่มด้วย 5,000 บาท (ราว 147 ดอลลาร์)"],
  [/^Each card is one decision cycle.*$/, "แต่ละการ์ดคือการตัดสินใจหนึ่งรอบของ DeepSeek: สิ่งที่โมเดลเห็น การโต้แย้งฝั่งซื้อ/ค้าน การตัดสินใจและเหตุผลของทุกตัว (รวมทั้งที่ไม่ซื้อ) สิ่งที่ระบบทำ และผลหลังจากนั้น เรียงใหม่สุดก่อน"],
  [/^Event trader \(fixed rule\).*$/, "Event trader (กติกาตายตัว): ทุกหุ้นใหญ่ที่ขยับตั้งแต่ 5% พร้อมปริมาณซื้อขายจริง พร้อมข่าว สิ่งที่กติกาทำ และเหตุผลที่ไม่เทรด"],
  [/^No open positions right now\..*$/, "ตอนนี้ไม่มีตำแหน่งที่ถืออยู่ กติกาถือได้สูงสุด 3 ตัวพร้อมกัน เหตุการณ์ที่เกินจะขึ้นว่า 'max positions' ด้านล่าง"],
];
const textNodes = (root) => { const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT); const out = []; while (w.nextNode()) out.push(w.currentNode); return out; };
function applyLang() {
  const btn = $("#lang-btn");
  const buttonLabel = LANG === "th" ? "EN" : "ไทย";
  if (btn && btn.textContent !== buttonLabel) btn.textContent = buttonLabel;
  if (document.documentElement.lang !== LANG) document.documentElement.lang = LANG;
  for (const n of textNodes(document.body)) {
    if (n.parentNode && ["SCRIPT", "STYLE"].includes(n.parentNode.nodeName)) continue;
    if (n.__en === undefined) {
      const raw = n.nodeValue.trim();
      if (!raw) continue;
      const hit = TH[raw] || (NOTE_TH.find(([re]) => re.test(raw)) || [])[1];
      if (!hit) continue;
      n.__en = n.nodeValue;
      n.__th = n.nodeValue.replace(raw, hit);
    }
    const want = LANG === "th" ? n.__th : n.__en;
    if (want !== undefined && n.nodeValue !== want) n.nodeValue = want;
  }
}
// Translate DOM updates before the next paint instead of showing English for a frame.
new MutationObserver(applyLang).observe(document.body, { childList: true, subtree: true, characterData: true });
document.addEventListener("click", (e) => {
  if (e.target.id !== "lang-btn") return;
  LANG = LANG === "th" ? "en" : "th";
  try { localStorage.setItem("lang", LANG); } catch (err) { /* ignore */ }
  applyLang();
});

show();
refreshAccount();
applyLang();

/* layout probe for automated checks: ?probe writes scrollWidth/viewport width to body[data-sw] */
if (location.search === "?probe") setTimeout(() => { document.body.dataset.sw = document.documentElement.scrollWidth + "/" + window.innerWidth; }, 9000);
