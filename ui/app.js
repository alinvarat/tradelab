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

function target3x(a) {
  // Every account here is judged against one goal: 3x the starting capital. Closed pairs are only the evidence count.
  const eq = a.equity_usd, cap = a.capital_usd, ev = a.evaluation || {};
  if (eq == null || !cap) return "";
  const pct = Math.max(0, Math.min(100, (eq - cap) / (2 * cap) * 100));
  return `<div class="figure"><b>${eq.toFixed(2)} / ${(3 * cap).toFixed(2)} USD</b><span>toward the 3x goal (${pct.toFixed(0)}%) | closed pairs ${ev.closed_pairs ?? 0}</span></div>`;
}

async function api(path, body) {
  const r = await fetch("/api/" + path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  const j = await r.json().catch(() => ({ error: "bad response" }));
  // A status payload (trader, buzz, event trader) carries its last error in `error` next to real data: that is a
  // warning to show, not a failed request. Only an HTTP error or an error-only body fails the call.
  const errorOnly = j && j.error && !Array.isArray(j) && Object.keys(j).every((k) => ["error", "symbol", "name"].includes(k));
  if (!r.ok || errorOnly) throw new Error(j.error || r.statusText);
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
function toast(msg, detail) {
  const t = $("#toast");
  t.textContent = msg;
  if (detail) t.insertAdjacentHTML("beforeend", ` ${originalText(detail)}`);
  t.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove("show"), 3500);
}
function toastError(error) {
  toast("Request failed:", error.message || String(error));
}
const skel = (n = 5) => Array.from({ length: n }, (_, i) => `<span class="skel ${["w80", "w60", "", "w40"][i % 4]}"></span>`).join("");
const errBox = (e, retry) => `<div class="error"><span>Could not load:</span> <span translate="no">${esc(e.message || e)}</span>${retry ? ` <button class="sm" data-retry="${retry}">Try again</button>` : ""}</div>`;
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
    tr.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target === tr) go(); });
  });
}
const originalText = (s) => `<span translate="no">${esc(s)}</span>`;
const symCell = (s, n) => `<span class="sym" translate="no">${esc(s)}</span>${n ? `<span class="sym-name" translate="no">${esc(n)}</span>` : ""}`;

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
        list.innerHTML = res.length ? res.map((r) => `<button type="button" data-s="${esc(r.symbol)}" translate="no"><span><b>${esc(r.symbol)}</b> ${esc(r.name)}</span><span class="muted small">${esc(r.type || "")} ${esc(r.exchange || "")}</span></button>`).join("") : `<div class="empty" style="padding: var(--space-sm)">No match. Try a ticker such as MSFT, BTC-USD, EURUSD=X or GC=F.</div>`;
        list.hidden = false;
      } catch (e) { list.innerHTML = errBox(e); list.hidden = false; }
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

views.markets = async (refresh = false) => {
  const wl = $("#watchlist");
  load(wl, async () => {
    const d = await api("quotes");
    const rows = d.quotes.map((q, i) => q || { symbol: d.watchlist[i], error: true });
    wl.innerHTML = table([
      { h: "Symbol", f: (r) => symCell(r.symbol, r.name) },
      { h: "Last", num: 1, f: (r) => fmt(r.price) },
      { h: "Change", num: 1, f: (r) => pct(r.change_pct), cls: (r) => cls(r.change_pct) },
      { h: "Day range", num: 1, f: (r) => (r.low != null ? `${fmt(r.low)} – ${fmt(r.high)}` : "–") },
      { h: "Market", f: (r) => (r.error ? "No quote" : r.open ? "Market open" : "Market closed") },
      { h: "", f: (r) => `<button class="ghost sm" data-rm="${esc(r.symbol)}" aria-label="Remove ${esc(r.symbol)}">Remove</button>` },
    ], rows, { click: (r) => r.symbol, empty: "Your watchlist is empty. Add a symbol above." });
    bindRowOpen(wl);
    $$("[data-rm]", wl).forEach((b) => b.addEventListener("click", async () => {
      try { await api("watchlist", { symbol: b.dataset.rm, action: "remove" }); views.markets(); } catch (e) { toastError(e); }
    }));
  }, "markets");
  const ov = $("#overview");
  if (!ov.dataset.loaded || refresh) load(ov, async () => {
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
  if (!mn.dataset.loaded || refresh) load(mn, async () => {
    const d = await api("news");
    mn.innerHTML = newsList(d.items.slice(0, 12));
    mn.dataset.loaded = 1;
  }, "markets");
};
$("#watch-add").addEventListener("submit", async (e) => {
  e.preventDefault();
  const s = $("#watch-sym").value.trim();
  if (!s) return;
  try { await api("watchlist", { symbol: s }); $("#watch-sym").value = ""; toast(s.toUpperCase() + " added"); views.markets(); } catch (er) { toastError(er); }
});

function newsList(items) {
  if (!items.length) return `<div class="empty">No headlines from the feeds right now.</div>`;
  return `<ul class="news">${items.map((n) => {
    const s = n.sentiment, c = s > 0.1 ? "s-pos" : s < -0.1 ? "s-neg" : "s-neu";
    return `<li><span class="senti ${c}" title="Headline sentiment">${s > 0 ? "+" : ""}${s.toFixed(2)}</span><div><a href="${esc(n.link)}" target="_blank" rel="noopener" translate="no">${esc(n.title)}</a>${n.summary ? `<div class="sum small" translate="no">${esc(n.summary)}</div>` : ""}<div class="meta">${originalText(n.source)}, ${ago(n.ts)}</div></div></li>`;
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
  const s = NEWS.summary, a = NEWS.archive || {}, lt = NEWS.latency || {};
  const lat = (label, x) => x ? `${label} ${x.complete_pairs ?? 0}/${x.needed ?? 100} pairs, net vs control ${x.mean_net != null ? pct(x.mean_net * 100) : "-"}${x.net_ci95 ? " (CI " + pct(x.net_ci95[0] * 100) + " to " + pct(x.net_ci95[1] * 100) + ")" : ""} — ${x.verdict || ""}` : `${label} waiting for data`;
  $("#news-sum").innerHTML = `<div class="figures"><div class="figure"><b>${s.count}</b><span>Headlines</span></div><div class="figure"><b class="up">${s.positive}</b><span>Positive</span></div><div class="figure"><b class="down">${s.negative}</b><span>Negative</span></div><div class="figure"><b>${s.avg > 0 ? "+" : ""}${s.avg.toFixed(2)}</b><span>Average, ${esc(s.label.toLowerCase())}</span></div></div>
    <p class="small muted">Archive: ${a.linked ?? 0} linked headlines in the last scan, ${a.ai_scored ?? 0} AI-scored, ${a.labels ?? 0} return labels written, ${a.feeds_ok ?? 0}/${a.feeds ?? 0} sources healthy. The DeepSeek trader reads this archive, not only the live list below.</p>
    <p class="small muted">News latency, entry at first sight after ${(lt.horizons?.["1m"]?.cost_round_trip_pct ?? 0.14).toFixed(2)}% cost: ${lat("+1m", (lt.horizons || {})["1m"])}; ${lat("+5m", (lt.horizons || {})["5m"])}.</p>`;
  const it = NEWS.items.filter((n) => newsFilter === "all" || (newsFilter === "pos" ? n.sentiment > 0.1 : newsFilter === "neg" ? n.sentiment < -0.1 : Math.abs(n.sentiment) <= 0.1));
  $("#news-list").innerHTML = newsList(it);
}
segment($("#news-filter"), [["all", "All"], ["pos", "Positive"], ["neg", "Negative"], ["neu", "Neutral"]], "all", (v) => { newsFilter = v; if (NEWS) renderNews(); });

function segment(el, opts, cur, on) {
  el.innerHTML = opts.map(([v, l, label]) => `<button type="button" data-v="${v}" aria-pressed="${v === cur}"${label ? ` aria-label="${label}"` : ""}>${l}</button>`).join("");
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
segment($("#overlays"), [["sma20", "SMA20", "20-period simple moving average"], ["sma50", "SMA50", "50-period simple moving average"], ["sma200", "SMA200", "200-period simple moving average"], ["ema", "EMA", "Exponential moving averages"], ["bb", "BB", "Bollinger Bands"]], null, (v) => {
  OVER[v] = !OVER[v];
  $$("#overlays button").forEach((b) => b.setAttribute("aria-pressed", OVER[b.dataset.v]));
  drawOverlays();
});
$$("#overlays button").forEach((b) => b.setAttribute("aria-pressed", OVER[b.dataset.v]));
segment($("#ranges"), [["1d", "1D", "1 day"], ["5d", "5D", "5 days"], ["1mo", "1M", "1 month"], ["3mo", "3M", "3 months"], ["6mo", "6M", "6 months"], ["1y", "1Y", "1 year"], ["2y", "2Y", "2 years"], ["5y", "5Y", "5 years"], ["max", "Max", "Maximum available history"]], "1y", (v) => { route.range = v; writeHash(); loadChart(); });
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
    await renderQuoteHead(d.meta, sym, bars.length === 0);
  } catch (e) {
    $("#qhead").innerHTML = errBox(e);
  }
}
async function renderQuoteHead(meta, sym, empty) {
  let q = null;
  try { q = await api("quote?symbol=" + encodeURIComponent(sym)); } catch (e) { /* header falls back to chart meta */ }
  if (sym !== route.symbol) return;                 // the user switched while this quote was loading
  lastQuote = q;
  const px = q?.price ?? meta.regularMarketPrice, ch = q?.change_pct;
  $("#qhead").innerHTML = `<h1 translate="no">${esc(route.symbol)}</h1><span class="muted" translate="no">${esc(meta.longName || meta.shortName || "")}${meta.fullExchangeName ? ", " + esc(meta.fullExchangeName) : ""}</span>
    <span class="px">${fmt(px)}</span><span class="${cls(ch)} mono">${pct(ch)}</span><span class="muted small">${originalText(q?.currency || meta.currency || "")}. ${q ? `<span>${q.open ? "Market open" : "Market closed"}</span>. ${originalText(q.source)}` : ""}</span>${empty ? `<span class="muted small">No price history in this range.</span>` : ""}`;
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
      ${a.profile?.sector ? `<p class="small" translate="no" style="margin-top: var(--space-xs)">${esc(a.profile.sector)}, ${esc(a.profile.industry)}</p>` : ""}`;
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
    out.innerHTML = r.error ? errBox(r.error) : `${originalText(r.text)}<p class="note">${originalText(r.model)}, ${r.seconds} s.</p>`;
  } catch (er) { out.innerHTML = errBox(er); }
  b.disabled = false;
});

/* ---------- order ticket ---------- */
let side = 1;
function renderTicket() {
  const t = $("#ticket");
  if (!t) return;
  const orderPrice = () => {
    const f = $("#order-form");
    if (!f) return null;
    if (f.type.value !== "market" && +f.price.value > 0) return +f.price.value;   // the user's limit/stop price
    return side > 0 ? lastQuote?.ask : lastQuote?.bid;
  };
  if (!t.dataset.built) {
    t.innerHTML = `<h2>Order ticket</h2>
      <div class="sides" role="group" aria-label="Side"><button type="button" class="buy" data-side="1" aria-pressed="true">Buy</button><button type="button" data-side="-1" aria-pressed="false">Sell</button></div>
      <form id="order-form" class="form-grid" style="margin-top: var(--space-sm)">
        <label class="f">Type<select name="type"><option value="market">Market order</option><option value="limit">Limit order</option><option value="stop">Stop order</option></select></label>
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
    f.usd.addEventListener("input", () => { const p = orderPrice(); if (p && f.usd.value) f.qty.value = +(f.usd.value / p / (lastQuote?.fx || 1)).toPrecision(6); renderTicket(); });
    f.price.addEventListener("input", () => {
      if (f.usd.value) { const p = orderPrice(); if (p) f.qty.value = +(f.usd.value / p / (lastQuote?.fx || 1)).toPrecision(6); }
      renderTicket();
    });
    f.qty.addEventListener("input", renderTicket);
    f.addEventListener("submit", async (e) => {
      e.preventDefault();
      const body = { symbol: route.symbol, side, qty: f.qty.value, type: f.type.value, price: f.price.value, sl: f.sl.value, tp: f.tp.value };
      try {
        const o = await api("order", body);
        toast(o.status === "filled" ? `Filled ${o.side > 0 ? "buy" : "sell"} ${fmt(o.qty, null)} ${o.symbol} at ${fmt(o.fill_px)}` : o.status === "pending" ? `Order #${o.id} pending. ${o.note}` : `Rejected: ${o.note}`);
        refreshAccount();
      } catch (er) { toastError(er); }
    });
  }
  const f = $("#order-form"), q = lastQuote;
  $("#place").textContent = `${side > 0 ? "Buy" : "Sell"} ${route.symbol}`;
  $("#place").className = side > 0 ? "buy" : "sell";
  if (q) {
    const px = orderPrice() ?? (side > 0 ? q.ask : q.bid), n = +f.qty.value || 0, val = n * px * (q.fx || 1);
    const limit = f.type.value !== "market" && +f.price.value > 0 ? ` at your limit ${fmt(px)}` : "";
    $("#est").innerHTML = `<span>Bid ${fmt(q.bid)}, ask ${fmt(q.ask)}.</span> <span>Estimated value${limit}</span> <b class="mono">${usd(val)}</b>${q.currency !== "USD" ? ` <span>(${esc(q.currency)} converted at ${fmt(q.fx, 6)})</span>` : ""}.${q.open ? "" : " <span>Market closed: a market order waits for the next open.</span>"}`;
  } else $("#est").textContent = "No quote";
}

/* ---------- portfolio ---------- */
let eqChart = null;
async function refreshAccount() {
  try { ACCOUNT = await api("account"); } catch (e) {
    if (!ACCOUNT && route.view === "chart") $("#pos-here").innerHTML = errBox(e);
    return;
  }
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
    try { const t = await api("close", { symbol: b.dataset.close }); toast(`Closed ${t.symbol}: ${usd(t.pnl)}`); refreshAccount(); } catch (e) { toastError(e); }
  }));
  $$("[data-modify]", el).forEach((b) => b.addEventListener("click", async () => {
    const tr = b.closest("tr"), sl = $("[name=sl]", tr).value, tp = $("[name=tp]", tr).value;
    try {
      await api("modify", { symbol: b.dataset.modify, sl, tp });
      toast("Stop and target saved");
      refreshAccount();
    } catch (e) { toastError(e); }
  }));
  $$("[data-cancel]", el).forEach((b) => b.addEventListener("click", async () => {
    try { await api("cancel", { id: b.dataset.cancel }); toast("Order cancelled"); refreshAccount(); } catch (e) { toastError(e); }
  }));
}
views.portfolio = async () => {
  if (!ACCOUNT) { $("#positions").innerHTML = skel(); }
  await refreshAccount();
  if (!ACCOUNT) $("#positions").innerHTML = `<div class="error">Account unavailable. <button class="sm" data-retry="portfolio">Try again</button></div>`;
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
    { h: "", f: (r) => `<div class="row"><button class="sm" data-modify="${esc(r.symbol)}">Save</button><button class="sm" data-close="${esc(r.symbol)}">Close position</button>${r.market_open === false ? `<span class="small muted">Market closed</span>` : ""}</div>` },
  ], a.positions, { click: (r) => r.symbol, empty: "No open positions. Open a chart and use the order ticket." });
  bindPosButtons(pos);
  bindRowOpen(pos);
  const ord = $("#orders");
  ord.innerHTML = table([
    { h: "#", num: 1, f: (r) => r.id }, { h: "Time", f: (r) => dt(r.created) }, { h: "Symbol", f: (r) => originalText(r.symbol) },
    { h: "Order", f: (r) => `<span>${r.side > 0 ? "Buy" : "Sell"}</span> <span>${esc(r.type)}</span>${r.price ? " @ " + fmt(r.price) : ""}` },
    { h: "Qty", num: 1, f: (r) => fmt(r.qty, null) },
    { h: "Status", f: (r) => `<span>${esc(r.status)}</span>${r.fill_px ? " @ " + fmt(r.fill_px) : ""}${r.note ? `<br><span class="small muted">${esc(r.note)}</span>` : ""}` },
    { h: "", f: (r) => (r.status === "pending" ? `<button class="sm" data-cancel="${r.id}">Cancel</button>` : "") },
  ], a.orders.slice(0, 50), { empty: "No orders yet." });
  bindPosButtons(ord);
  const tot = Object.values(a.allocation).reduce((x, y) => x + y, 0) + Math.max(a.cash_usd - (s.used_margin || 0), 0);
  const allocRows = [...Object.entries(a.allocation).map(([k, v]) => ({ k: k.toLowerCase(), v })), { k: "cash not in use", v: Math.max(a.cash_usd - (s.used_margin || 0), 0) }];
  $("#alloc").innerHTML = table([{ h: "Asset type", f: (r) => esc(r.k) }, { h: "USD", num: 1, f: (r) => usd(r.v) }, { h: "Share", num: 1, f: (r) => (tot ? fmt((r.v / tot) * 100, 1) + "%" : "–") }], allocRows);
  $("#trades").innerHTML = table([
    { h: "Closed", f: (r) => dt(r.closed_ts) }, { h: "Symbol", f: (r) => originalText(r.symbol) }, { h: "Side", f: (r) => (r.side > 0 ? "Long" : "Short") },
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
  try {
    await api("reset", { balance: f.balance.value, leverage: f.leverage.value, fee_pct: f.fee_pct.value, min_fee: f.min_fee.value, slippage_pct: f.slippage_pct.value, allow_short: f.allow_short.checked });
    toast("Account reset");
    refreshAccount();
  } catch (er) { toastError(er); }
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
  sel.innerHTML = Object.entries(STRATS).map(([k, v]) => `<option value="${esc(k)}">${esc(v.name)}</option>`).join("");
  sel.addEventListener("change", btParams);
  btParams();
};
function btParams() {
  const p = STRATS[$("#bt-strat").value].params;
  const labels = { fast: "Fast period", slow: "Slow period", period: "Lookback period", low: "Lower RSI threshold", high: "Upper RSI threshold", signal: "Signal period", k: "Band width (standard deviations)", entry: "Entry period", exit: "Exit period" };
  $("#bt-params").innerHTML = Object.entries(p).map(([k, v]) => `<label class="f">${esc(labels[k] || k)}<input data-p="${esc(k)}" type="number" step="any" value="${esc(v)}"></label>`).join("");
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
    out.innerHTML = `<h2>${originalText(r.symbol)}, <span>${esc(r.strategy)}</span>, <span>${day(r.start)} to ${day(r.end)}</span></h2>
      <div class="figures">
        <div class="figure hot"><b>${pct(m.return_pct, 1)}</b><span>Strategy return</span></div>
        <div class="figure"><b class="${cls(m.buy_hold_return_pct)}">${pct(m.buy_hold_return_pct, 1)}</b><span>Buy and hold</span></div>
        <div class="figure"><b>${pct(m.cagr_pct, 1)}</b><span>Per year (CAGR)</span></div>
        <div class="figure"><b>${fmt(m.max_drawdown_pct, 1)}%</b><span>Max drawdown (hold ${fmt(m.buy_hold_max_drawdown_pct, 1)}%)</span></div>
        <div class="figure"><b>${fmt(m.sharpe, 2)}</b><span>Sharpe</span></div>
        <div class="figure"><b>${m.trades}</b><span>Trades, win ${m.win_rate == null ? "–" : fmt(m.win_rate, 0) + "%"}</span></div>
        <div class="figure"><b>${fmt(m.profit_factor, 2)}</b><span>Profit factor</span></div>
        <div class="figure"><b>${fmt(m.exposure_pct, 0)}%</b><span>Time in market</span></div></div>
      <div class="chart-box" id="c-bt" role="region" aria-label="Strategy versus buy and hold equity chart" style="height: 320px"><div class="chart-legend"><span><i class="k1"></i>Strategy</span><span><i class="k2"></i>Buy and hold</span></div></div>
      <p class="note">${r.bars} ${esc(r.interval)} bars, fee ${r.costs.fee_pct_per_side}% and slippage ${r.costs.slippage_pct_per_side}% per side. One test on one history is not evidence of a future edge: check other symbols, periods and nearby parameters.</p>
      <div class="panel"><h2>Trades</h2>${table([
        { h: "Entry date", f: (t) => day(t.entry_t) }, { h: "Exit date", f: (t) => day(t.exit_t) }, { h: "Side", f: (t) => (t.side > 0 ? "Long" : "Short") },
        { h: "Entry price", num: 1, f: (t) => fmt(t.entry) }, { h: "Exit price", num: 1, f: (t) => fmt(t.exit) },
        { h: "Return", num: 1, f: (t) => pct(t.ret_pct), cls: (t) => cls(t.ret_pct) }, { h: "Net P/L", num: 1, f: (t) => fmt(t.pnl, 2), cls: (t) => cls(t.pnl) }, { h: "Exit reason", f: (t) => esc(t.reason === "stop" ? "Stop loss" : t.reason) },
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
const accountAmounts = (thb, dollars) => thb == null ? "–" : `${fmt(thb, 2)} THB<span class="sym-name">${fmt(dollars, 2)} USD</span>`;
views.overview = async () => {
  const el = $("#ov-table");
  let d;
  try { d = await api("accounts"); } catch (e) { el.innerHTML = errBox(e, "overview"); return; }
  $("#ov-sub").textContent = `Current exchange rate: 1 USD = ${fmt(d.thb_per_usd, 2)} THB | Buzz events: ${d.buzz_events ?? "–"}`;
  el.innerHTML = table([
    { h: "Account", f: (r) => `<a href="#${r.tab}"><b>${esc(r.name)}</b></a>` },
    { h: "Starting capital", num: 1, f: (r) => accountAmounts(r.start_thb, r.start_usd) },
    { h: "Equity", num: 1, f: (r) => accountAmounts(r.equity_thb, r.equity_usd) },
    { h: "Random control account", num: 1, f: (r) => accountAmounts(r.control_thb, r.control_usd) },
    { h: "Return", num: 1, f: (r) => pct(r.return_pct), cls: (r) => cls(r.return_pct) },
    { h: "Open", num: 1, f: (r) => r.positions },
    { h: "Status", f: (r) => esc(r.status) },
    { h: "Note", f: (r) => esc(r.note) },
  ], d.rows, { empty: "No accounts." });
};

/* ---------- decision log ---------- */
let logSource = "llm";
let logRequest;
const logMarkup = new WeakMap();
const BADGE = { buy: "BUY", sell: "SELL", adjust: "ADJUST" };
const hmin = (s) => (s % 3600 === 0 ? s / 3600 + "h" : s / 3600 >= 1 ? (s / 3600).toFixed(1) + "h" : Math.round(s / 60) + "m");
function cycleCard(c) {
  const key = esc(c.ts);
  const when = new Date(c.ts * 1000).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit" });
  const byDec = {}; (c.decisions || []).forEach((d) => { byDec[d.symbol] = d; });
  const acts = {}; (c.actions || []).forEach((a) => { (acts[a.symbol] = acts[a.symbol] || []).push(a); });
  const outs = {}; (c.outcomes || []).forEach((o) => { (outs[o.symbol] = outs[o.symbol] || []).push(o); });
  const mk = c.market || {}, ac = c.account || {};
  const held = new Set((ac.positions || []).map((position) => position.symbol));
  const badge = (d) => esc(d.action === "hold" ? (held.has(d.symbol) ? "Hold position" : "Pass on entry") : BADGE[d.action] || d.action);
  const rows = (c.candidates || []).map((x) => {
    const d = byDec[x.symbol], a = acts[x.symbol] || [], o = outs[x.symbol] || [];
    const heads = (x.headlines || []).map((h) => `${esc(h.title)} <span class="muted">[${esc(h.source)}, lexicon ${h.lexicon ?? "-"}${h.ai_scores && Object.keys(h.ai_scores).length ? ", AI " + Object.values(h.ai_scores).join("/") : ""}]</span>`).join("<br>") || "-";
    const decision = d ? `<b>${badge(d)}</b>${d.action === "buy" ? ` margin ${fmt(d.size_pct, 1)}% x ${fmt(d.leverage || 1, 1)} | ${esc(d.entry || "market")}${d.limit_price ? " @ " + fmt(d.limit_price) : ""} | ${esc(d.horizon || "")} | stop ${fmt(d.stop_pct, 0)}%${d.target_pct ? " target " + fmt(d.target_pct, 0) + "%" : ""} | look again in ${d.review_in_min} min` : ""}<br>${esc(d.reason || "")}` : "<b>No model decision</b>";
    const did = a.map((z) => z.kind === "skip" ? `<span class="muted">not executed: ${esc(z.why)}</span>` : z.kind === "order" ? execHtml({ status: z.status, notional_usd: z.notional_usd, margin_usd: z.margin_usd, leverage: z.leverage, entry: z.entry, limit_price: z.limit_price, valid_until: z.valid_until, stop_price: z.stop_price, target_price: z.target_price, risk_pct_equity: z.risk_pct_equity, clipped_by: z.clipped_by, control: z.control, scaled_in: z.scaled_in }) : z.kind.startsWith("limit_") ? esc(z.kind.replace("limit_", "limit order ") + (z.order_id != null ? " #" + z.order_id : "") + (z.status ? " (" + z.status + ")" : "")) : esc(z.kind + " " + (z.status || ""))).join("<br>");
    const res = o.map((z) => `+${hmin(z.horizon_s)} vs SPY ${pct(z.abnormal * 100)}`).join("<br>");
    return `<tr><td>${symCell(x.symbol, x.name)}</td><td class="num">${pct(x.move_pct)}<br><span class="muted">vs SPY ${x.abnormal_pct != null ? pct(x.abnormal_pct) : "-"}</span></td><td class="num">${fmt(x.volume_ratio, 1)}x</td>
      <td>${decision}${did ? "<br>" + did : ""}</td><td>${heads}</td>
      <td><details data-log-detail="${key}:debate:${esc(x.symbol)}"><summary>bull / bear</summary><b>Bull:</b> ${esc((c.bull || {})[x.symbol] || "-")}<br><b>Bear:</b> ${esc((c.bear || {})[x.symbol] || "-")}${(c.bull_rebuttal || {})[x.symbol] ? `<br><b>Bull rebuttal:</b> ${esc(c.bull_rebuttal[x.symbol])}` : ""}${(c.bear_rebuttal || {})[x.symbol] ? `<br><b>Bear rebuttal:</b> ${esc(c.bear_rebuttal[x.symbol])}` : ""}</details></td><td>${res || "<span class='muted'>pending</span>"}</td></tr>`;
  }).join("");
  const extra = (c.decisions || []).filter((d) => !(c.candidates || []).some((x) => x.symbol === d.symbol)).map((d) => {
    const a = (acts[d.symbol] || []).map((z) => esc(z.kind + " " + (z.status || z.why || ""))).join(", ");
    return `<li><b><span>${badge(d)}</span> ${esc(d.symbol)}</b> (position review): ${esc(d.reason || "")}${a ? " <span class='muted'>→ " + a + "</span>" : ""}</li>`;
  }).join("");
  return `<div class="panel" data-log-cycle="${key}" style="margin:12px 0"><div class="row spread"><b>${when} | ${esc(c.trigger || "?")}</b><span class="small muted">${esc(c.model || "")} ${c.seconds != null ? "| " + c.seconds + " s" : ""}</span></div>
    <p class="small muted">SPY ${mk.spy_move_pct != null ? pct(mk.spy_move_pct) : "-"} | VIX ${mk.vix ?? "-"} | account ${fmt(ac.equity_usd, 2)} USD, exposure ${ac.exposure_pct ?? 0}%, ${(ac.positions || []).length} open</p>
    ${c.market_view ? `<p><b>Market view:</b> ${esc(c.market_view)}</p>` : ""}${c.error ? `<p class="down">Error: ${esc(c.error)}</p>` : ""}
    ${c.risk ? `<p class="small muted"><b>Risk review:</b> ${Object.entries(c.risk.reviews || {}).map(([s, r]) => `${esc(s)} ${r.approve ? "approved" : "vetoed"}${r.size_multiplier != null && r.size_multiplier < 1 ? " (" + Math.round(r.size_multiplier * 100) + "% size)" : ""}${r.reason ? ": " + esc(r.reason) : ""}`).join(" | ") || esc(c.risk.error || "no comments")}</p>` : ""}
    ${c.analysts ? `<details data-log-detail="${key}:analysts"><summary class="small muted">analyst notes</summary>${Object.entries(c.analysts).map(([n, notes]) => `<p class="small"><b>${esc(n)}:</b> ${Object.entries(notes || {}).map(([s, v]) => `${esc(s)} ${esc(v)}`).join("; ") || "-"}</p>`).join("")}</details>` : ""}
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
      updateLogMarkup(box, d.cycles.length ? d.cycles.map(cycleCard).join("") : `<div class="empty">No decision cycles yet. The model is asked on new shocks, linked news, social buzz, and at least every 15 minutes.</div>`);
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

function accountComparison(d, label) {
  return `<div class="figure hot"><b>${fmt(d.equity_thb, 2)} THB</b><span>${label}</span><div class="small">${fmt(d.equity_usd, 2)} USD</div></div>
    <div class="figure"><b>${fmt(d.control_equity_thb, 2)} THB</b><span>Random control account</span><div class="small">${fmt(d.control_equity_usd, 2)} USD</div></div>`;
}
const accountBasis = (d) => `<p class="small muted"><span>Starting capital for each account</span> ${fmt(d.capital_thb, 2)} THB (${fmt(d.capital_usd, 2)} USD). <span>Both accounts use their opening exchange rate for THB.</span></p>`;

/* ---------- DeepSeek trader ---------- */
views.llm = async () => {
  const figs = $("#llm-figs");
  let l;
  try { l = await api("llm_trader"); } catch (e) { figs.innerHTML = errBox(e, "llm"); return; }
  if (l.disabled) { figs.innerHTML = `<div class="empty">The DeepSeek trader is off on this server (needs the OPENROUTER_API_KEY secret).</div>`; return; }
  const ev = l.evaluation || {}, dis = ev.discrimination || {}, cl = l.classes || {};
  const classes = Object.entries(cl).map(([k, v]) => `${v} ${k}`).join(", ");
  $("#llm-sub").textContent = `${l.model} | ${l.universe_size} symbols (${classes}) | calls today ${l.calls_today}/${l.max_calls_day} | next scheduled scan in ${l.next_scan_in_s ?? "?"} s${l.error ? " | " + l.error : ""}`;
  figs.innerHTML = `<div class="figures">
    ${accountComparison(l, "DeepSeek account")}
    ${target3x(l)}
    <div class="figure"><b>${l.paused ? "Paused" : "Running"}</b><span>last scan ${l.last_scan_age_s ?? "never"} s ago</span></div></div>
    ${accountBasis(l)}
    <p class="small muted">Protocol v4.1: the same paper account now runs three analyst calls (news, price, macro), a bull/bear debate with a rebuttal round, an advisory risk review that can only veto or cut size, 30-trade memory and up to 24 candidates, with a scheduled scan every 10 minutes. v4.2 keeps everything above but sends every call of a cycle with the same data block first, so the model's prompt cache makes the later calls cheaper and faster; the real cost per cycle is logged. Headlines on closed markets wait for a pre-open briefing (09:10-09:29 New York) whose watchlist starts the first cycle at the open, and a scheduled scan with nothing new is skipped. v4 rules are unchanged otherwise: the model sees US stocks, ETFs, commodity futures, FX and crypto, chooses whether to trade, the margin (0-100% of equity), leverage (1-20x, margin = notional / leverage), entry, stop, target and when to look again. The control account buys a random symbol in the same asset class with the same notional and leverage.</p>
    <p><b>Verdict:</b> ${esc(ev.verdict || "")}</p>
    <p class="small muted">Every symbol shown to the model is also scored +1 day vs SPY. Bought: ${dis.bought ? dis.bought.n : 0} scored${dis.bought && dis.bought.mean_abnormal_1d != null ? ", mean " + pct(dis.bought.mean_abnormal_1d * 100) : ""}.
    Passed: ${dis.passed ? dis.passed.n : 0} scored${dis.passed && dis.passed.mean_abnormal_1d != null ? ", mean " + pct(dis.passed.mean_abnormal_1d * 100) : ""}. Rules: research/llm_trader/protocol.md</p>
    ${Object.keys(ev.by_class || {}).length ? `<p class="small muted">By asset class (closed pairs): ${Object.entries(ev.by_class).map(([k, v]) => `${k} ${v.n}, mean difference ${pct(v.mean_diff * 100)}`).join(" | ")}</p>` : ""}`;
  $("#llm-pos").innerHTML = table([
    { h: "Stock", f: (r) => symCell(r.symbol, "") }, { h: "Class", f: (r) => esc(r.asset_class || "-") },
    { h: "Side", f: (r) => esc(r.side === "short" ? "Short" : "Long") },
    { h: "Entry", num: 1, f: (r) => fmt(r.entry) }, { h: "Mark", num: 1, f: (r) => fmt(r.mark) },
    { h: "P/L", num: 1, f: (r) => pct(r.pnl_pct), cls: (r) => cls(r.pnl_pct) },
    { h: "Leverage", num: 1, f: (r) => fmt(r.leverage, 1) + "x" },
    { h: "Notional (USD)", num: 1, f: (r) => fmt(r.notional_usd, 2) }, { h: "Margin (USD)", num: 1, f: (r) => fmt(r.margin_usd, 2) },
    { h: "Stop", num: 1, f: (r) => fmt(r.stop) }, { h: "Target", num: 1, f: (r) => fmt(r.target) },
    { h: "Horizon", f: (r) => esc(r.horizon || "-") }, { h: "Held (h)", num: 1, f: (r) => fmt(r.held_hours, 1) },
    { h: "Why", f: (r) => esc(r.your_reason || "") + ((r.clipped_by || []).length ? `<br><span class="muted">cut by: ${esc(r.clipped_by.join("; "))}</span>` : "") },
  ], l.positions, { empty: "No open positions." });
  $("#llm-list").innerHTML = table([
    { h: "When", f: (r) => new Date(r.ts * 1000).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit" }) },
    { h: "Stock", f: (r) => symCell(r.symbol, "") }, { h: "Class", f: (r) => esc(r.asset_class || "-") },
    { h: "Action", f: (r) => esc(r.action) },
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
    <div class="figure hot"><b>${e1.complete_pairs ?? 0} / ${e1.needed ?? 100}</b><span>complete pairs with +1d</span></div>
    <div class="figure"><b>${e1.events ?? 0}</b><span>events with a +1d result</span></div>
    <div class="figure"><b>${e1.missing_control ?? 0}</b><span>events without a control result</span></div>
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
    ${accountComparison(d, "Event trader account")}
    <div class="figure"><b>${d.n_events}</b><span>events (${d.n_up} up-shocks)</span></div>
    ${target3x(d)}
    <div class="figure"><b>${d.paused ? "Paused" : "Running"}</b><span>${esc(d.rules.shock)}</span></div></div>
    ${accountBasis(d)}<p class="small muted"><b>Fixed rule, not the AI. No leverage (1x).</b> ${esc(d.rules.trade)}. A pair is counted only after both the stock and its random control have closed, so 0/30 with positions still open is normal.</p><p><b>Verdict:</b> ${esc(ev.verdict || "")}</p>`;
  $("#ev-pos").innerHTML = table([
    { h: "Stock", f: (r) => symCell(r.symbol, "") }, { h: "Entry", num: 1, f: (r) => fmt(r.entry) }, { h: "Mark", num: 1, f: (r) => fmt(r.mark) },
    { h: "P/L", num: 1, f: (r) => pct(r.pnl_pct), cls: (r) => cls(r.pnl_pct) },
    { h: "Leverage", f: () => "1x (none)" },
    { h: "Position size (USD)", num: 1, f: (r) => fmt(r.notional_usd, 2) },
    { h: "Stop price", num: 1, f: (r) => fmt(r.stop) },
    { h: "Eligible to exit after", f: (r) => dt(r.exit_at) },
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
const autoFlags = (tags) => tags.length ? tags.map((tag) => Object.hasOwn(TAGN, tag) ? `<span>${TAGN[tag]}</span>` : originalText(tag)).join(", ") : "none";
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
  $("#auto-model").innerHTML = m.label ? `<p><b>${esc(m.label)}</b>, <span>chosen from ${m.settings_tested} settings.</span> <span>${m.status === "live" ? "Trading it." : "Not trading: it lost money in the validation years."}</span></p>
    ${table([
      { h: "Period", f: (r) => `${esc(r.k)}<span class="sym-name">${esc(r.span)}</span>` },
      { h: "Per year", num: 1, f: (r) => pct(r.s.cagr, 1), cls: (r) => cls(r.s.cagr) },
      { h: "Max drawdown", num: 1, f: (r) => fmt(r.s.mdd, 1) + "%" },
      { h: "Worst year", num: 1, f: (r) => pct(r.s.worst_year, 1), cls: (r) => cls(r.s.worst_year) },
      { h: "Positive years", num: 1, f: (r) => esc(r.s.pos_years) },
      { h: "Sharpe", num: 1, f: (r) => fmt(r.s.sharpe, 2) },
    ], [{ k: "Train (used to choose)", span: m.train_span, s: m.train }, { k: "Validation (not used to choose)", span: m.valid_span, s: v }, { k: "SPY buy and hold, validation", span: m.valid_span, s: sv }])}` : `<div class="empty">Learning has not finished yet. The first pass takes under a minute after start.</div>`;
  $("#auto-targets").innerHTML = d.targets.length ? table([
    { h: "Asset", f: (r) => symCell(r.symbol, r.name) }, { h: "Target weight", num: 1, f: (r) => fmt(r.weight, 0) + "%" },
    { h: "Flags at entry", f: (r) => autoFlags(r.tags) },
  ], d.targets) : `<div class="empty">All cash for ${esc(d.rebalanced || "this month")}: no asset beat cash over the lookback, so the rule stays out. It checks again at the next monthly rebalance.</div>`;
  const li = (arr, empty) => (arr.length ? `<ul class="news">${arr.map((l) => `<li><span class="senti s-neu">${dt(l.ts)}</span><div translate="no">${esc(l.text)}</div></li>`).join("")}</ul>` : `<div class="empty">${empty}</div>`);
  $("#auto-lessons").innerHTML = li(d.lessons.slice(0, 40), "No lessons yet.");
  $("#auto-log").innerHTML = li(d.log.slice(0, 40), "No activity yet.");
  $("#auto-months").innerHTML = table([
    { h: "Month", f: (r) => esc(r.month) }, { h: "Return", num: 1, f: (r) => pct(r.ret), cls: (r) => cls(r.ret) },
    { h: "Held", f: (r) => Object.keys(r.hold).length ? originalText(Object.keys(r.hold).join(", ")) : "cash" }, { h: "Flags", f: (r) => autoFlags(r.tags) },
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
  $("#hunt-pos").innerHTML = table([{ h: "Coin", f: (r) => originalText(r.symbol) }, { h: "Entry", num: 1, f: (r) => fmt(r.entry) }, { h: "Mark", num: 1, f: (r) => fmt(r.mark) }, { h: "Notional", num: 1, f: (r) => usd(r.notional) }], h.positions, { empty: "Flat: no coin is in an uptrend (above its 50-day average with a positive 30-day return)." });
  $("#hunt-months").innerHTML = table([{ h: "Month", f: (r) => esc(r.month) }, { h: "Result", num: 1, f: (r) => fmt(r.multiple, 2) + "x", cls: (r) => cls(r.multiple - 1) }], h.months, { empty: "No month finished yet." });
  $("#hunt-log").innerHTML = h.log.length ? `<ul class="news">${h.log.slice(0, 25).map((l) => `<li><span class="senti s-neu">${dt(l.ts)}</span><div translate="no">${esc(l.text)}</div></li>`).join("")}</ul>` : `<div class="empty">No activity yet.</div>`;
}
$("#hunt-reset").addEventListener("click", async (e) => {
  const b = e.currentTarget;
  if (!b.dataset.armed) { b.dataset.armed = 1; b.textContent = "Press again to restart"; setTimeout(() => { delete b.dataset.armed; b.textContent = "Restart hunter"; }, 4000); return; }
  delete b.dataset.armed; b.textContent = "Restart hunter";
  try { await api("hunter", { action: "reset" }); toast("Hunter restarted with 5,000 THB"); setTimeout(renderHunter, 1500); } catch (er) { toastError(er); }
});
$$("[data-auto]").forEach((b) => b.addEventListener("click", async () => {
  const act = b.dataset.auto;
  if (act === "reset") {
    if (!b.dataset.armed) { b.dataset.armed = 1; b.textContent = "Press again to erase"; setTimeout(() => { delete b.dataset.armed; b.textContent = "Restart"; }, 4000); return; }
    delete b.dataset.armed; b.textContent = "Restart";
  }
  try { await api("auto", { action: act }); toast(act === "learn" ? "Relearning" : act === "reset" ? "Restarted with 5,000 THB" : act === "pause" ? "Paused" : "Resumed"); setTimeout(views.auto, 1500); } catch (e) { toastError(e); }
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
/* Match fixed and formatted UI labels. Preserve tickers, headline text and the original model response. */
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
  "Stock": "หุ้น", "Class": "ประเภทสินทรัพย์", "Entry": "ราคาเข้า", "Mark": "ราคาตอนนี้", "P/L": "กำไร/ขาดทุน", "Stop": "ตัดขาดทุน", "Stop price": "ราคาตัดขาดทุน", "Target": "เป้ากำไร",
  "Horizon": "ระยะถือ", "Held (h)": "ถือมา (ชม.)", "Why": "เหตุผล", "When": "เวลา", "Action": "การตัดสินใจ", "Size %": "ขนาด %",
  "Size % (margin)": "ขนาด % (เงินประกัน)", "Leverage": "เลเวอเรจ", "Notional (USD)": "มูลค่าสถานะ (USD)", "Margin (USD)": "เงินประกัน (USD)",
  "Position size (USD)": "ขนาดสถานะ (USD)", "1x (none)": "1 เท่า (ไม่ใช้เลเวอเรจ)",
  "Result": "ผล", "Reason (model)": "เหตุผล (โมเดล)", "Stop / target %": "ตัดขาดทุน / เป้า %", "Look again (min)": "กลับมาดูอีก (นาที)",
  "Move": "ขยับ", "Volume": "ปริมาณ", "Volume x": "ปริมาณ x", "Traded": "ผลการเทรด", "Headlines": "พาดหัวข่าว", "Debate": "โต้แย้ง",
  "Decision and reason": "การตัดสินใจและเหตุผล", "Headlines the model saw": "ข่าวที่โมเดลเห็น", "What happened next": "หลังจากนั้น",
  "Sells at (20 h rule)": "ขายเมื่อ (กฎ 20 ชม.)", "Why it bought": "ทำไมถึงซื้อ", "Random control": "หุ้นสุ่มเทียบ", "Account": "บัญชี",
  "Why closed": "ปิดเพราะ", "P/L %": "กำไร/ขาดทุน %", "Mentions": "จำนวนที่ถูกพูดถึง", "24h ago": "24 ชม.ก่อน", "Upvotes": "โหวตขึ้น",
  "Rank": "อันดับ", "Ticker": "สัญลักษณ์", "+1h / +1d vs SPY": "+1 ชม. / +1 วัน เทียบ SPY", "Control +1d": "หุ้นสุ่ม +1 วัน",
  "What": "ประเภท", "Context": "บริบท", "Decision": "การตัดสินใจ", "Running": "กำลังทำงาน", "Paused": "หยุดอยู่",
  "DeepSeek account": "บัญชี DeepSeek", "Random control account": "บัญชีสุ่มเทียบ", "closed pairs needed": "คู่ที่ปิดแล้ว / ที่ต้องการ",
  "Event trader account": "บัญชี Event trader", "Starting capital": "ทุนเริ่มต้น",
  "Starting capital for each account": "ทุนเริ่มต้นต่อบัญชี",
  "Both accounts use their opening exchange rate for THB.": "ทั้งสองบัญชีใช้อัตราตอนเปิดบัญชีในการแปลงเป็นบาท",
  "Eligible to exit after": "ครบเวลาถือ (ขายเมื่อตลาดเปิด)", "max positions": "ถือครบจำนวนที่กำหนด",
  "data only": "เก็บข้อมูลเท่านั้น", "running": "กำลังทำงาน", "paused": "หยุดชั่วคราว", "ruined": "ทุนต่ำกว่าเกณฑ์",
  "buy": "ซื้อ", "sell": "ขาย", "hold": "ไม่ส่งคำสั่ง", "adjust": "ปรับสถานะ",
  "closed": "ปิดสถานะแล้ว", "filled": "จับคู่แล้ว", "pending": "รอผล", "adjusted": "ปรับแล้ว",
  "intraday": "ภายในวัน", "swing": "ถือหลายวัน", "scalp": "ถือช่วงสั้น",
  "Market open": "ตลาดเปิด", "Market closed": "ตลาดปิด", "No quote": "ไม่มีราคา",
  "Hold position": "ถือสถานะต่อ", "Pass on entry": "ไม่เปิดสถานะ", "No model decision": "โมเดลไม่ได้ตอบ",
  "you place the orders": "ส่งคำสั่งเอง", "Manual paper trading account": "บัญชีจำลองสำหรับส่งคำสั่งเอง",
  "No decisions yet; the model is asked when new shocks appear.": "ยังไม่มีคำตัดสิน ระบบจะถามโมเดลเมื่อพบหุ้นที่เคลื่อนไหวแรง",
  "+1h / +1d": "+1 ชม. / +1 วัน",
  "events with a +1d result": "เหตุการณ์ที่มีผล +1 วัน", "buzz events": "เหตุการณ์กระแส", "mean +1d return vs SPY": "ผลตอบแทน +1 วันเฉลี่ย เทียบ SPY",
  "complete pairs with +1d": "คู่ครบ (หุ้นกับหุ้นสุ่ม) ที่มีผล +1 วัน", "events without a control result": "เหตุการณ์ที่หุ้นสุ่มยังไม่มีผล",
  "matched controls": "หุ้นสุ่มที่เทียบ", "Verdict:": "ข้อสรุป:", "Refresh": "รีเฟรช", "Reset account": "รีเซ็ตบัญชี", "Pause": "หยุดชั่วคราว",
  "Restart": "เริ่มใหม่", "Learn now": "เรียนรู้ใหม่", "Equity": "มูลค่าบัญชี", "Profit or loss": "กำไรหรือขาดทุน", "Months completed": "เดือนที่ครบ",
  "Max drawdown": "ขาดทุนสูงสุดจากจุดสูงสุด", "Equity in USD": "มูลค่าเป็น USD", "Return in USD": "ผลตอบแทนเป็น USD", "Current model": "โมเดลปัจจุบัน",
  "This month's targets": "เป้าหมายเดือนนี้", "Equity curve": "เส้นมูลค่าบัญชี", "Orders": "ออเดอร์", "Allocation": "สัดส่วน", "Cash balance": "เงินสด",
  "Open profit or loss": "กำไรขาดทุนที่ยังไม่ปิด", "Realised": "ปิดแล้ว", "Buying power": "กำลังซื้อ",
  "Top headlines": "พาดหัวข่าวเด่น", "Order ticket": "ใบสั่งซื้อขาย", "Technical rating": "คะแนนทางเทคนิค", "Run scan": "สแกน",
  "Broad list": "รายการกว้าง", "Watchlist": "รายการที่ติดตาม", "Run backtest": "ทดสอบย้อนหลัง", "Add alert": "เพิ่มแจ้งเตือน",
  "Date (your time)": "วันที่ (เวลาของคุณ)", "Impact": "ผลกระทบ", "Source": "แหล่งที่มา", "Price alerts": "แจ้งเตือนราคา",
  "No open positions.": "ไม่มีตำแหน่งที่ถืออยู่", "No decisions yet.": "ยังไม่มีการตัดสินใจ", "No events yet.": "ยังไม่มีเหตุการณ์",
  "Nothing here yet.": "ยังไม่มีข้อมูล", "No accounts.": "ไม่มีบัญชี", "Waiting for the first scan.": "รอการสแกนครั้งแรก", "No closed trades yet.": "ยังไม่มีการปิดสถานะ",
};
let LANG = "en";
try { if (localStorage.getItem("lang") === "th") LANG = "th"; } catch (e) { /* private window */ }
const NOTE_TH = [
  [/^Every account below is separate play money.*$/, "ทุกบัญชีใช้เงินจำลอง บัญชีสั่งเองแปลงเป็นบาทด้วยค่าเงินล่าสุด บัญชีบอทเริ่มที่ 5,000 บาท ส่วนยอดเงินบาทของบอทและบัญชีสุ่มเทียบใช้อัตราตอนเปิดบัญชีนั้น"],
  [/^(\d+\/\d+) pairs vs random control$/, "คู่ที่ปิดแล้ว $1 เทียบบัญชีสุ่ม"],
  [/^toward the 3x goal \((\d+)%\) \| closed pairs (\d+)$/, "ความคืบหน้าสู่เป้า 3 เท่า $1% | คู่ที่ปิดแล้ว $2"],
  [/^Each card is one decision cycle.*$/, "แต่ละการ์ดคือการตัดสินใจหนึ่งรอบของ DeepSeek: สิ่งที่โมเดลเห็น การโต้แย้งฝั่งซื้อ/ค้าน การตัดสินใจและเหตุผลของทุกตัว (รวมทั้งที่ไม่ซื้อ) สิ่งที่ระบบทำ และผลหลังจากนั้น เรียงใหม่สุดก่อน"],
  [/^Event trader \(fixed rule\).*$/, "Event trader (กติกาตายตัว): ทุกหุ้นใหญ่ที่ขยับตั้งแต่ 5% พร้อมปริมาณซื้อขายจริง พร้อมข่าว สิ่งที่กติกาทำ และเหตุผลที่ไม่เทรด"],
  [/^No open positions right now\..*$/, "ตอนนี้ไม่มีตำแหน่งที่ถืออยู่ กติกาถือได้สูงสุด 3 ตัวพร้อมกัน เหตุการณ์ที่เกินจะขึ้นว่า 'max positions' ด้านล่าง"],
  [/^Current exchange rate: 1 USD = ([\d,.]+) THB \| Buzz events: (.+)$/, "ค่าเงินล่าสุด 1 USD = $1 THB | เหตุการณ์กระแส $2 รายการ"],
  [/^(deepseek\/[^ ]+) \| calls today (\d+\/\d+)$/, "$1 | เรียกโมเดลวันนี้ $2 ครั้ง"],
  [/^(deepseek\/[^ ]+) \| (\d+) symbols \((.*)\) \| calls today (\d+\/\d+) \| next scheduled scan in (\d+) s$/, "$1 | $2 สินทรัพย์ ($3) | เรียกโมเดลวันนี้ $4 ครั้ง | สแกนตามกำหนดในอีก $5 วินาที"],
  [/^last scan (\d+) s ago$/, "สแกนล่าสุด $1 วินาทีที่แล้ว"],
  [/^scans every (\d+)s, last scan (\d+)s ago$/, "สแกนทุก $1 วินาที สแกนล่าสุด $2 วินาทีที่แล้ว"],
  [/^scans every (\d+)s, last scan nevers ago$/, "สแกนทุก $1 วินาที ยังไม่เคยสแกน"],
  [/^events \((\d+) up-shocks\)$/, "เหตุการณ์ (หุ้นขึ้นแรง $1 ครั้ง)"],
  [/^move >= ([\d.]+)% vs previous close, day volume >= ([\d.]+)x 50-day average$/, "ราคาขยับอย่างน้อย $1% เทียบราคาปิดก่อนหน้า และปริมาณซื้อขายวันนี้อย่างน้อย $2 เท่าของค่าเฉลี่ย 50 วัน"],
  [/^long ([\d.]+)% of equity at first sight of an UP shock, hold (\d+) h, stop ([\d.]+)%, max (\d+) open; control = random non-shock stock, same time and rules$/, "ซื้อด้วย $1% ของมูลค่าบัญชีเมื่อพบหุ้นขึ้นแรงครั้งแรก ถือ $2 ชม. ตัดขาดทุน $3% ถือพร้อมกันได้สูงสุด $4 ตัว บัญชีเทียบสุ่มหุ้นที่ไม่ได้ขยับแรงและใช้เวลาและกติกาเดียวกัน"],
  [/^too early \((\d+\/\d+) closed pairs\): no conclusion allowed$/, "มีคู่ปิด $1 คู่ ยังสรุปไม่ได้"],
  [/^too early \((\d+\/\d+) complete pairs\): no conclusion allowed$/, "มีคู่ครบ (หุ้นกับหุ้นสุ่ม) $1 คู่ ยังสรุปไม่ได้"],
  [/^limit order filled #(\d+)$/, "คำสั่ง limit จับคู่แล้ว #$1"],
  [/^limit order expired #(\d+) \(expired\)$/, "คำสั่ง limit หมดอายุ #$1"],
  [/^limit order rejected #(\d+) \((.+)\)$/, "คำสั่ง limit ถูกปฏิเสธ #$1 ($2)"],
  [/^Protocol v4\.1: the same paper account.*$/, "กติกา v4.1: ใช้บัญชีจำลองเดิมและเก็บสถิติต่อเนื่อง เพิ่มนักวิเคราะห์ 3 ด้าน (ข่าว ราคา มาโคร) โต้แย้งกระทิง/หมีสองรอบ รวมรอบตอบโต้ ให้ผู้จัดการความเสี่ยงตรวจได้เพียงลดขนาดหรือวีโต้ ห้ามเพิ่ม และจำผลตัดสิน 30 รายการ สแกนทั้งตลาดทุก 10 นาที v4.2 ทำทุกอย่างเหมือนเดิม แต่ส่งข้อมูลก้อนเดียวกันไว้ต้นข้อความทุกครั้งในรอบเดียวกัน ให้ cache ของโมเดลทำให้ครั้งถัดๆ ไปถูกลงและเร็วขึ้น และบันทึกค่าใช้จ่ายจริงของแต่ละรอบ ข่าวของตลาดที่ปิดอยู่จะรอสรุปก่อนตลาดเปิด (09:10-09:29 เวลานิวยอร์ก) แล้วใช้รายชื่อที่สรุปไว้เป็นรอบแรกตอนเปิดตลาด และข้ามการสแกนตามรอบที่ไม่มีอะไรใหม่ กติกาอื่นยังเหมือน v4: โมเดลเห็นหุ้นสหรัฐ ETF สินค้าโภคภัณฑ์ ฟอเร็กซ์ และคริปโต เลือกเองว่าจะเทรดไหม เงินประกัน 0-100% ของมูลค่าบัญชี เลเวอเรจ 1-20 เท่า ราคาเข้า จุดตัดขาดทุน เป้ากำไร และเวลากลับมาดู บัญชีเทียบซื้อสินทรัพย์สุ่มประเภทเดียวกันด้วยมูลค่าและเลเวอเรจเท่ากัน"],
  [/^Fixed rule, not the AI\..*$/, "กติกาตายตัว ไม่ใช่ AI และไม่ใช้เลเวอเรจ (1 เท่า) ซื้อ 5% ของมูลค่าบัญชีต่อครั้ง ถือได้สูงสุด 3 ตัว ตัดขาดทุน 8% และขายเมื่อครบ 20 ชั่วโมง บัญชีเทียบสุ่มหุ้นที่ไม่ได้ขยับแรงด้วยเวลาและกติกาเดียวกัน คู่จะนับเมื่อทั้งหุ้นและหุ้นสุ่มปิดสถานะแล้ว ดังนั้น 0/30 ขณะยังถือสถานะอยู่เป็นเรื่องปกติ"],
  [/^Archive: (\d+) linked headlines.*$/, "คลังข่าว: รอบล่าสุดเชื่อมข่าวกับหุ้นได้ $1 พาดหัว ให้คะแนนด้วย AI แล้ว และเขียนป้ายผลตอบแทนแล้ว ระบบ DeepSeek อ่านคลังนี้ ไม่ได้อ่านเฉพาะรายการสดด้านล่าง"],
  [/^first sight of a ([+\-\d.]+)% move on ([\d.]+)x volume \(SPY unavailable at entry\)$/, "ซื้อเมื่อพบว่าราคาขยับ $1% ครั้งแรก ปริมาณซื้อขาย $2 เท่าของค่าเฉลี่ย ตอนเข้าไม่มีข้อมูล SPY"],
  [/^first sight of a ([+\-\d.]+)% move on ([\d.]+)x volume \(SPY ([+\-\d.]+)%\)$/, "ซื้อเมื่อพบว่าราคาขยับ $1% ครั้งแรก ปริมาณซื้อขาย $2 เท่าของค่าเฉลี่ย (SPY $3%)"],
  [/^long ([\d,.]+) USD vs (.+)$/, "ซื้อ $1 USD เทียบกับ $2"],
  [/^Every stock shown to the model is also scored \+1 day vs SPY\. Bought: (\d+) scored([^.]*(?:\.[\d]+%?)?)\.\s+Passed: (\d+) scored([^.]*(?:\.[\d]+%?)?)\. Rules: research\/llm_trader\/protocol\.md$/, "วัดผลของหุ้นที่โมเดลเห็นหลัง 1 วันเทียบกับ SPY หุ้นที่ซื้อมีผลแล้ว $1 ตัว$2 หุ้นที่ไม่ซื้อมีผลแล้ว $3 ตัว$4"],
];
// These labels belong to the five localized trading pages and their shared shell.
// Keep legacy translations on other pages independent; some words mean different things there.
const PAGE_ROOTS = "#v-auto, #v-markets, #v-chart, #v-portfolio, #v-backtest, .topbar, #toast";
const PAGE_TH = {
  "Views": "เมนูหน้าต่าง ๆ", "Could not load:": "โหลดไม่สำเร็จ:", "Request failed:": "ดำเนินการไม่สำเร็จ:", "Try again": "ลองอีกครั้ง",
  "Auto trader equity chart": "กราฟมูลค่าบัญชีบอทหลัก", "Price and volume chart": "กราฟราคาและปริมาณซื้อขาย",
  "RSI chart": "กราฟ RSI", "MACD chart": "กราฟ MACD", "Portfolio equity chart": "กราฟมูลค่าพอร์ต",
  "Strategy versus buy and hold equity chart": "กราฟมูลค่าบัญชีเทียบกลยุทธ์กับการซื้อและถือ",
  "5,000 THB of simulated money in a monthly momentum portfolio of ten global assets. It relearns daily and reviews its losing months.": "เงินจำลอง 5,000 บาทในพอร์ตโมเมนตัมรายเดือนที่เลือกจากสินทรัพย์ทั่วโลกสิบตัว ระบบเรียนรู้ใหม่ทุกวันและทบทวนเดือนที่ขาดทุน",
  "Each month it holds the assets with the strongest recent return, only if they beat cash; otherwise it holds cash. Costs 0.10% fee and 0.05% slippage per side. Past results do not predict future returns.": "แต่ละเดือนระบบเลือกถือสินทรัพย์ที่ให้ผลตอบแทนล่าสุดสูงสุด เฉพาะเมื่อชนะการถือเงินสด มิฉะนั้นจะถือเงินสด ค่าธรรมเนียม 0.10% และส่วนต่างจากราคาที่คาด 0.05% ต่อฝั่ง ผลในอดีตไม่ได้บอกผลตอบแทนในอนาคต",
  "Lessons from mistakes": "บทเรียนจากข้อผิดพลาด", "Activity": "กิจกรรม", "Monthly results": "ผลรายเดือน", "Settings tested, best train first": "การตั้งค่าที่ทดสอบ เรียงตามผลในช่วงฝึก",
  "Hunter: 20x crypto trend, 6x monthly target": "Hunter: ตามแนวโน้มคริปโตด้วยเลเวอเรจ 20 เท่า เป้ารายเดือน 6 เท่า",
  "A separate 5,000 THB paper account. Backtest 2023-2026: a 6x month in about 1 of 10 months, the account wiped in about 1 of 2 months. Shown so the gamble can be judged on real forward results.": "บัญชีจำลองแยก 5,000 บาท ผลย้อนหลังปี 2023–2026 ถึง 6 เท่าประมาณ 1 ใน 10 เดือน และเสียทุนหมดประมาณ 1 ใน 2 เดือน แสดงไว้เพื่อประเมินความเสี่ยงจากผลจำลองนับจากนี้",
  "Positions": "สถานะที่ถือ", "Months": "เดือน", "Learning": "กำลังเรียนรู้", "Resume": "ทำงานต่อ",
  "Trading it.": "กำลังใช้เทรด", "Not trading: it lost money in the validation years.": "ไม่เทรด เพราะขาดทุนในช่วงตรวจสอบ",
  "Train (used to choose)": "ช่วงฝึก (ใช้เลือกกติกา)", "Validation (not used to choose)": "ช่วงตรวจสอบ (ไม่ใช้เลือกกติกา)", "SPY buy and hold, validation": "ซื้อและถือ SPY ในช่วงตรวจสอบ",
  "Learning has not finished yet. The first pass takes under a minute after start.": "ยังเรียนรู้ไม่เสร็จ รอบแรกใช้เวลาไม่ถึงหนึ่งนาทีหลังเริ่ม",
  "Period": "ช่วงเวลา", "Per year": "ต่อปี", "Worst year": "ปีที่ผลแย่ที่สุด", "Positive years": "จำนวนปีที่ได้กำไร", "Asset": "สินทรัพย์",
  "Target weight": "สัดส่วนเป้าหมาย", "Weight": "สัดส่วน",
  "Flags at entry": "เงื่อนไขตอนเข้า", "Flags": "เงื่อนไข", "below its 200-day average": "ต่ำกว่าค่าเฉลี่ย 200 วัน", "volatility spike": "ความผันผวนพุ่งสูง",
  "none": "ไม่มี", "this month": "เดือนนี้", "No lessons yet.": "ยังไม่มีบทเรียน", "No activity yet.": "ยังไม่มีกิจกรรม",
  "Month": "เดือน", "Held": "สินทรัพย์ที่ถือ", "cash": "เงินสด", "No month completed yet. The first result appears at the next month change.": "ยังไม่ครบเดือน ผลรอบแรกจะแสดงเมื่อขึ้นเดือนใหม่",
  "No open position: the portfolio is in cash.": "ไม่มีสถานะเปิด พอร์ตถือเงินสด",
  "Setting": "การตั้งค่า", "Train per year": "ผลต่อปีในช่วงฝึก", "Train Sharpe": "Sharpe ช่วงฝึก",
  "Validation per year": "ผลต่อปีในช่วงตรวจสอบ", "Validation drawdown": "การลดลงจากจุดสูงสุดในช่วงตรวจสอบ", "Not learned yet.": "ยังไม่ได้เรียนรู้",
  "This month vs its start": "เทียบกับต้นเดือนนี้", "Ruined": "ทุนหมด", "Target hit": "ถึงเป้าแล้ว", "Hunting": "กำลังหาจังหวะ", "Coin": "เหรียญ", "Notional": "มูลค่าสถานะ",
  "Flat: no coin is in an uptrend (above its 50-day average with a positive 30-day return).": "ไม่มีสถานะ เพราะไม่มีเหรียญที่เป็นขาขึ้น (สูงกว่าค่าเฉลี่ย 50 วันและผลตอบแทน 30 วันเป็นบวก)",
  "No month finished yet.": "ยังไม่ครบเดือน", "Restart hunter": "เริ่ม Hunter ใหม่", "Press again to restart": "กดอีกครั้งเพื่อเริ่มใหม่",
  "Hunter restarted with 5,000 THB": "เริ่ม Hunter ใหม่ด้วย 5,000 บาท", "Restarted with 5,000 THB": "เริ่มใหม่ด้วย 5,000 บาท", "Relearning": "กำลังเรียนรู้ใหม่", "Resumed": "ทำงานต่อแล้ว",

  "Global indices, rates, commodities, crypto and your watchlist.": "ดัชนีทั่วโลก อัตราดอกเบี้ย สินค้าโภคภัณฑ์ คริปโต และรายการติดตามของคุณ",
  "Add symbol": "เพิ่มสัญลักษณ์", "Add symbol, e.g. AMD": "เพิ่มสัญลักษณ์ เช่น AMD", "Add": "เพิ่ม", "Global overview": "ภาพรวมตลาดโลก", "Crypto fear and greed": "ดัชนีความกลัวและความโลภของคริปโต",
  "Symbol": "สัญลักษณ์", "Last": "ราคาล่าสุด", "Change": "การเปลี่ยนแปลง", "Day range": "ช่วงราคาวันนี้", "Market": "ตลาด", "Remove": "นำออก",
  "Your watchlist is empty. Add a symbol above.": "รายการติดตามว่าง เพิ่มสัญลักษณ์ด้านบนได้",
  "Name": "ชื่อ", "Day": "วันนี้", "Trend": "แนวโน้ม", "Indices": "ดัชนี", "Rates and FX": "ดอกเบี้ยและค่าเงิน", "Commodities": "สินค้าโภคภัณฑ์", "Crypto": "คริปโต", "US sectors": "กลุ่มอุตสาหกรรมสหรัฐ",
  "Extreme fear": "กลัวมาก", "Fear": "กลัว", "Neutral": "เป็นกลาง", "Greed": "โลภ", "Extreme greed": "โลภมาก",
  "Index unavailable right now.": "ยังไม่มีข้อมูลดัชนี", "Headline sentiment": "อารมณ์ของพาดหัวข่าว", "No headlines from the feeds right now.": "ตอนนี้ไม่มีพาดหัวข่าวจากฟีด",

  "Search symbol or company": "ค้นหาสัญลักษณ์หรือชื่อบริษัท", "Range": "ช่วงเวลา", "Overlays": "เส้นบนกราฟ", "No price history in this range.": "ไม่มีประวัติราคาในช่วงนี้",
  "20-period simple moving average": "ค่าเฉลี่ยเคลื่อนที่แบบง่าย 20 แท่ง", "50-period simple moving average": "ค่าเฉลี่ยเคลื่อนที่แบบง่าย 50 แท่ง", "200-period simple moving average": "ค่าเฉลี่ยเคลื่อนที่แบบง่าย 200 แท่ง",
  "Exponential moving averages": "ค่าเฉลี่ยเคลื่อนที่แบบเอ็กซ์โพเนนเชียล", "Bollinger Bands": "กรอบ Bollinger",
  "1D": "1 วัน", "5D": "5 วัน", "1M": "1 เดือน", "3M": "3 เดือน", "6M": "6 เดือน", "1Y": "1 ปี", "2Y": "2 ปี", "5Y": "5 ปี", "Max": "ทั้งหมด", "Maximum available history": "ข้อมูลย้อนหลังทั้งหมดที่มี",
  "1 day": "1 วัน", "5 days": "5 วัน", "1 week": "1 สัปดาห์", "1 month": "1 เดือน", "3 months": "3 เดือน", "6 months": "6 เดือน", "1 year": "1 ปี", "2 years": "2 ปี", "5 years": "5 ปี", "10 years": "10 ปี", "Year to date": "ตั้งแต่ต้นปี",
  "30 / 70 bands": "ระดับ 30 / 70", "Signal": "เส้นสัญญาณ", "Histogram": "ฮิสโตแกรม", "Bollinger 20, 2": "กรอบ Bollinger 20, 2",
  "Technical signals": "สัญญาณทางเทคนิค", "Key levels": "ระดับราคาสำคัญ", "Performance and risk": "ผลตอบแทนและความเสี่ยง", "Recent events": "เหตุการณ์ล่าสุด",
  "AI analyst": "นักวิเคราะห์ AI", "Runs Claude Sonnet once per press; logged to data/ai_log.jsonl": "เรียก Claude Sonnet หนึ่งครั้งต่อการกด และบันทึกลง data/ai_log.jsonl",
  "Question": "คำถาม", "Optional question, e.g. Is a pullback entry reasonable here?": "คำถาม (ไม่บังคับ) เช่น จังหวะย่อเหมาะที่จะเข้าซื้อไหม", "Analyze": "วิเคราะห์",
  "News for this symbol": "ข่าวของสินทรัพย์นี้", "Position here": "สถานะของสินทรัพย์นี้", "No match. Try a ticker such as MSFT, BTC-USD, EURUSD=X or GC=F.": "ไม่พบผลลัพธ์ ลองใช้สัญลักษณ์ เช่น MSFT, BTC-USD, EURUSD=X หรือ GC=F",
  "Strong buy": "ซื้อแรง", "Strong sell": "ขายแรง", "Buy": "ซื้อ", "Sell": "ขาย", "-100 sell": "-100 ขาย", "+100 buy": "+100 ซื้อ",
  "Indicator": "ตัวชี้วัด", "Reading": "ค่าที่อ่านได้", "Vote": "สัญญาณ", "Last price": "ราคาล่าสุด", "52-week high": "สูงสุด 52 สัปดาห์", "52-week low": "ต่ำสุด 52 สัปดาห์",
  "No swing low below the price in the last 180 sessions.": "ไม่พบจุดต่ำเฉพาะช่วงที่ต่ำกว่าราคาปัจจุบันใน 180 รอบซื้อขายล่าสุด",
  "ATR 14 (daily range)": "ATR 14 (ช่วงราคาเฉลี่ยรายวัน)", "Volatility, annualised": "ความผันผวนต่อปี", "Max drawdown, 1 year": "การลดลงสูงสุดจากจุดสูงสุดใน 1 ปี",
  "Sharpe, 1 year": "Sharpe ใน 1 ปี", "Beta to S&P 500": "เบตาเทียบ S&P 500", "Correlation to S&P 500": "สหสัมพันธ์กับ S&P 500", "Stop at 2 ATR below": "จุดตัดขาดทุนต่ำกว่าราคา 2 ATR",
  "Date": "วันที่", "Event": "เหตุการณ์", "No crossover in the last 60 sessions.": "ไม่มีสัญญาณตัดกันใน 60 รอบซื้อขายล่าสุด",
  "Price vs SMA20": "ราคาเทียบ SMA20", "Price vs SMA50": "ราคาเทียบ SMA50", "Price vs SMA200": "ราคาเทียบ SMA200", "SMA50 vs SMA200": "SMA50 เทียบ SMA200",
  "golden cross zone": "อยู่เหนือจุดตัดขาขึ้น", "death cross zone": "อยู่ใต้จุดตัดขาลง", "MACD histogram": "ฮิสโตแกรม MACD", "OBV 20-bar trend": "แนวโน้ม OBV 20 แท่ง", "rising": "เพิ่มขึ้น", "falling": "ลดลง",
  "Golden cross (SMA50 above SMA200)": "จุดตัดขาขึ้น (SMA50 ตัดเหนือ SMA200)", "Death cross (SMA50 below SMA200)": "จุดตัดขาลง (SMA50 ตัดใต้ SMA200)",
  "MACD bullish crossover": "MACD ตัดขึ้นเหนือเส้นสัญญาณ", "MACD bearish crossover": "MACD ตัดลงใต้เส้นสัญญาณ",
  "Side": "ฝั่ง", "Type": "ประเภท", "Market order": "คำสั่งตามราคาตลาด", "Limit order": "คำสั่งจำกัดราคา", "Stop order": "คำสั่งสต็อป",
  "Quantity": "จำนวน", "Order price": "ราคาที่ตั้ง", "Stop loss": "ตัดขาดทุน", "Take profit": "ทำกำไร", "optional": "ไม่บังคับ",
  "Or size by USD": "หรือระบุมูลค่าเป็น USD", "e.g. 5000": "เช่น 5000", "Place order": "ส่งคำสั่ง", "Estimated value": "มูลค่าโดยประมาณ",
  "Market closed: a market order waits for the next open.": "ตลาดปิด คำสั่งตามราคาตลาดจะรอจนตลาดเปิดครั้งถัดไป",
  "Long": "ซื้อ (Long)", "Short": "ขายชอร์ต (Short)", "Close position": "ปิดสถานะ",

  "Paper account in USD. Fills at bid and ask with fees and slippage.": "บัญชีจำลองหน่วย USD ใช้ราคาเสนอซื้อหรือเสนอขายและคิดค่าธรรมเนียมกับส่วนต่างจากราคาที่คาด",
  "Trade history": "ประวัติการเทรด", "Account settings": "การตั้งค่าบัญชี", "Starting balance (USD)": "ยอดเงินเริ่มต้น (USD)",
  "Fee per side (%)": "ค่าธรรมเนียมต่อฝั่ง (%)", "Minimum fee (USD)": "ค่าธรรมเนียมขั้นต่ำ (USD)", "Slippage per side (%)": "ส่วนต่างจากราคาที่คาดต่อฝั่ง (%)", "Allow short selling": "อนุญาตให้ขายชอร์ต",
  "Reset erases positions, orders and history and starts again with these settings.": "การรีเซ็ตจะล้างสถานะ คำสั่ง และประวัติ แล้วเริ่มใหม่ด้วยการตั้งค่านี้",
  "Qty": "จำนวน", "Value": "มูลค่า", "Save": "บันทึก", "No open positions. Open a chart and use the order ticket.": "ไม่มีสถานะเปิด เปิดกราฟแล้วใช้ใบสั่งซื้อขาย",
  "Time": "เวลา", "Order": "คำสั่ง", "market": "ตามราคาตลาด", "limit": "จำกัดราคา", "stop": "สต็อป", "rejected": "ถูกปฏิเสธ", "cancelled": "ยกเลิกแล้ว", "Cancel": "ยกเลิก",
  "waiting for a quote": "กำลังรอราคา", "market closed: fills at the next open quote": "ตลาดปิด จะจับคู่ที่ราคาแรกเมื่อตลาดเปิด",
  "invalid quantity, type or price": "จำนวน ประเภท หรือราคาไม่ถูกต้อง", "short selling is disabled": "ไม่ได้เปิดใช้การขายชอร์ต",
  "No orders yet.": "ยังไม่มีคำสั่ง", "Asset type": "ประเภทสินทรัพย์", "Share": "สัดส่วน", "cash not in use": "เงินสดที่ไม่ได้ใช้",
  "equity": "หุ้น", "cryptocurrency": "คริปโต", "currency": "สกุลเงิน", "future": "ฟิวเจอร์ส", "index": "ดัชนี", "other": "อื่น ๆ",
  "Closed": "เวลาปิดสถานะ", "Exit": "ราคาออก", "Fees": "ค่าธรรมเนียม", "Net P/L": "กำไร/ขาดทุนสุทธิ", "Reason": "เหตุผล",
  "order": "คำสั่ง", "manual": "ปิดเอง", "stop loss": "ตัดขาดทุน", "take profit": "ทำกำไร", "stop out": "บังคับปิดสถานะ",
  "Account unavailable.": "ยังโหลดข้อมูลบัญชีไม่ได้", "Account reset": "รีเซ็ตบัญชีแล้ว", "Press again to erase": "กดอีกครั้งเพื่อล้างข้อมูล",
  "Stop and target saved": "บันทึกจุดตัดขาดทุนและเป้ากำไรแล้ว", "Order cancelled": "ยกเลิกคำสั่งแล้ว",

  "Signal at the close, fill at the next open, fees and slippage on both sides.": "ใช้สัญญาณจากราคาปิด จำลองจับคู่ที่ราคาเปิดครั้งถัดไป และคิดค่าธรรมเนียมกับส่วนต่างจากราคาที่คาดทั้งสองฝั่ง",
  "Strategy": "กลยุทธ์", "History": "ข้อมูลย้อนหลัง", "Bar size": "ช่วงเวลาต่อแท่ง", "Daily": "รายวัน", "Weekly": "รายสัปดาห์", "Capital": "เงินทุน",
  "Position size (% equity)": "ขนาดสถานะ (% มูลค่าบัญชี)", "Stop (x ATR, 0 = none)": "จุดตัดขาดทุน (เท่าของ ATR, 0 = ไม่ใช้)", "Allow shorts": "อนุญาตให้ขายชอร์ต",
  "SMA crossover": "SMA ตัดกัน", "EMA crossover": "EMA ตัดกัน", "RSI mean reversion": "RSI กลับสู่ค่าเฉลี่ย", "MACD signal cross": "MACD ตัดเส้นสัญญาณ",
  "Bollinger breakout": "ทะลุกรอบ Bollinger", "Bollinger mean reversion": "กลับสู่ค่าเฉลี่ยด้วย Bollinger", "Donchian breakout (turtle)": "ทะลุกรอบ Donchian (Turtle)",
  "Fast period": "ระยะสั้น", "Slow period": "ระยะยาว", "Lookback period": "จำนวนแท่งย้อนหลัง", "Lower RSI threshold": "เกณฑ์ RSI ล่าง", "Upper RSI threshold": "เกณฑ์ RSI บน",
  "Signal period": "คาบเส้นสัญญาณ", "Band width (standard deviations)": "ความกว้างกรอบ (ส่วนเบี่ยงเบนมาตรฐาน)", "Entry period": "ช่วงย้อนหลังสำหรับเข้า", "Exit period": "ช่วงย้อนหลังสำหรับออก",
  "Strategy return": "ผลตอบแทนกลยุทธ์", "Buy and hold": "ซื้อและถือ", "Per year (CAGR)": "ผลตอบแทนทบต้นต่อปี (CAGR)", "Profit factor": "อัตราส่วนกำไรรวมต่อขาดทุนรวม", "Time in market": "สัดส่วนเวลาที่ถือสถานะ",
  "Trades": "รายการเทรด", "Entry date": "วันที่เข้า", "Exit date": "วันที่ออก", "Entry price": "ราคาเข้า", "Exit price": "ราคาออก", "Exit reason": "เหตุผลที่ปิดสถานะ",
  "signal": "สัญญาณ", "end of test": "สิ้นสุดการทดสอบ", "The rule never traded in this period.": "กติกาไม่ส่งคำสั่งในช่วงนี้",
};
const PAGE_NOTE_TH = [
  [/^Manual sandbox (.+)$/, "บัญชีทดลองสั่งเอง $1"],
  [/^Equity, from ([\d,.]+) THB$/, "มูลค่าบัญชี จากทุน $1 บาท"],
  [/^rebalances monthly, checks every (\d+) s$/, "ปรับพอร์ตทุกเดือน ตรวจทุก $1 วินาที"],
  [/^chosen from (\d+) settings\.$/, "เลือกจาก $1 การตั้งค่า"],
  [/^top (\d+) by (\d+)-day return(, SMA200 guard)?, (inverse-volatility weights|equal weights)$/, (_, top, days, guard, weights) =>
    `เลือก ${top} อันดับแรกตามผลตอบแทน ${days} วัน${guard ? " โดยกรองด้วย SMA200" : ""} ให้น้ำหนัก${weights === "equal weights" ? "เท่ากัน" : "ผกผันกับความผันผวน"}`],
  [/^All cash for (this month|\d{4}-\d{2}): no asset beat cash over the lookback, so the rule stays out\. It checks again at the next monthly rebalance\.$/, (_, month) =>
    `ถือเงินสดทั้งหมด${month === "this month" ? "เดือนนี้" : `ในเดือน ${month}`} เพราะไม่มีสินทรัพย์ชนะเงินสดในช่วงที่ใช้วัด ระบบจะตรวจอีกครั้งเมื่อถึงรอบปรับพอร์ตเดือนถัดไป`],
  [/^leverage ([\d.]+)x$/, "เลเวอเรจ $1 เท่า"],
  [/^Remove (.+)$/, "นำ $1 ออก"],
  [/^Index (\d+) of 100$/, "ดัชนี $1 จาก 100"],
  [/^30-day range ([-\d.]+) to ([-\d.]+)\. Source (.+)\.$/, "ช่วง 30 วัน $1 ถึง $2 แหล่งข้อมูล $3"],
  [/^, (\d+) min ago$/, ", $1 นาทีที่แล้ว"],
  [/^, (\d+) h ago$/, ", $1 ชม. ที่แล้ว"],
  [/^, (\d+) d ago$/, ", $1 วันที่แล้ว"],
  [/^Score ([-\d]+) from -100 to 100$/, "คะแนน $1 จากช่วง -100 ถึง 100"],
  [/^Mechanical vote of (\d+) daily indicators as of (.+)\. Not a forecast\.$/, "คะแนนตามกฎจากตัวชี้วัดรายวัน $1 ตัว ณ $2 ไม่ใช่การคาดการณ์"],
  [/^Resistance (\d+)$/, "แนวต้าน $1"],
  [/^Support (\d+)$/, "แนวรับ $1"],
  [/^Pivot (\S+)$/, "จุดหมุน $1"],
  [/^Fibonacci (\S+)$/, "ฟีโบนัชชี $1"],
  [/^([\d.]+), ([+-]DI) leads$/, "$1 โดย $2 นำ"],
  [/^(\d+) headlines, (\d+) positive, (\d+) negative, average ([+-]?[\d.]+)\.$/, "พาดหัว $1 ข่าว บวก $2 ลบ $3 คะแนนเฉลี่ย $4"],
  [/^Analysing (.+) with indicators and headlines\. This takes about 20 to 60 seconds\.$/, "กำลังวิเคราะห์ $1 จากตัวชี้วัดและพาดหัวข่าว ใช้เวลาประมาณ 20 ถึง 60 วินาที"],
  [/^, ([\d.]+) s\.$/, ", $1 วินาที"],
  [/^Buy (.+)$/, "ซื้อ $1"],
  [/^Sell (.+)$/, "ขาย $1"],
  [/^Bid (.+), ask (.+)\.$/, "ราคาเสนอซื้อ $1 ราคาเสนอขาย $2"],
  [/^Estimated value at your limit (.+)$/, "มูลค่าโดยประมาณที่ราคาจำกัด $1"],
  [/^\((.+) converted at (.+)\)$/, "(แปลงจาก $1 ด้วยอัตรา $2)"],
  [/^No position in (.+)\. Use the ticket above\.$/, "ไม่มีสถานะใน $1 ใช้ใบสั่งซื้อขายด้านบนได้"],
  [/^([A-Z0-9.^=/-]+) added$/, "เพิ่ม $1 แล้ว"],
  [/^Filled (buy|sell) (.+) at (.+)$/, (_, side, position, price) => `จับคู่คำสั่ง${side === "buy" ? "ซื้อ" : "ขาย"} ${position} ที่ราคา ${price}`],
  [/^Order #(\d+) pending\. ?(.*)$/, "คำสั่ง #$1 รอจับคู่ $2"],
  [/^Rejected: (.+)$/, "คำสั่งถูกปฏิเสธ: $1"],
  [/^Closed (.+): (.+)$/, "ปิดสถานะ $1: $2"],
  [/^Win rate, (\d+) trades$/, "อัตราชนะ จาก $1 รายการ"],
  [/^insufficient buying power \(need (.+) USD, free (.+)\)$/, "กำลังซื้อไม่พอ (ต้องใช้ $1 USD เหลือ $2 USD)"],
  [/^(\d{1,2} \w{3} \d{4}) to (\d{1,2} \w{3} \d{4})$/, "$1 ถึง $2"],
  [/^Max drawdown \(hold (.+)%\)$/, "การลดลงสูงสุดจากจุดสูงสุด (ซื้อและถือ $1%)"],
  [/^Trades, win (.+)$/, "จำนวนรายการ อัตราชนะ $1"],
  [/^(\d+) (\S+) bars, fee ([\d.]+)% and slippage ([\d.]+)% per side\. One test on one history is not evidence of a future edge: check other symbols, periods and nearby parameters\.$/, (_, count, interval, fee, slip) =>
    `ข้อมูล ${count} แท่ง (${interval === "1d" ? "รายวัน" : interval === "1wk" ? "รายสัปดาห์" : interval}) ค่าธรรมเนียม ${fee}% และส่วนต่างจากราคาที่คาด ${slip}% ต่อฝั่ง การทดสอบครั้งเดียวกับข้อมูลชุดเดียวไม่ได้พิสูจน์ความได้เปรียบในอนาคต ควรตรวจสัญลักษณ์ ช่วงเวลา และค่าพารามิเตอร์ใกล้เคียงอื่น ๆ`],
];
const localizedValues = new WeakMap();
const labelAttrs = ["aria-label", "placeholder", "title"];
function translateValue(node, inPage) {
  const current = node.nodeValue;
  let pair = localizedValues.get(node);
  // Renderers may overwrite the same text or attribute rather than replacing its DOM node.
  if (!pair || current !== pair.applied) {
    const raw = current.trim();
    if (!raw) return;
    const fixed = inPage && Object.hasOwn(PAGE_TH, raw) ? PAGE_TH[raw] : Object.hasOwn(TH, raw) ? TH[raw] : undefined;
    const rule = fixed ? undefined : (inPage && PAGE_NOTE_TH.find(([pattern]) => pattern.test(raw))) || NOTE_TH.find(([pattern]) => pattern.test(raw));
    if (!fixed && !rule) { localizedValues.delete(node); return; }
    const hit = fixed || raw.replace(...rule);
    pair = { en: current, th: current.replace(raw, () => hit) };
    localizedValues.set(node, pair);
  }
  const want = LANG === "th" ? pair.th : pair.en;
  pair.applied = want;
  if (current !== want) node.nodeValue = want;
}
function applyLang() {
  const btn = $("#lang-btn");
  const buttonLabel = LANG === "th" ? "EN" : "ไทย";
  if (btn && btn.textContent !== buttonLabel) btn.textContent = buttonLabel;
  const switchLabel = LANG === "th" ? "เปลี่ยนภาษาเป็นอังกฤษ" : "Switch to Thai";
  if (btn && btn.getAttribute("aria-label") !== switchLabel) btn.setAttribute("aria-label", switchLabel);
  if (document.documentElement.lang !== LANG) document.documentElement.lang = LANG;
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const n = walker.currentNode, parent = n.parentElement;
    if (!n.nodeValue.trim() || !parent || parent.closest("script, style, [translate=no]")) continue;
    translateValue(n, Boolean(parent.closest(PAGE_ROOTS)));
  }
  for (const el of $$("[aria-label],[placeholder],[title]")) {
    if (el === btn || !el.closest(PAGE_ROOTS) || el.closest("[translate=no]")) continue;
    for (const name of labelAttrs) {
      const attr = el.getAttributeNode(name);
      if (attr) translateValue(attr, true);
    }
  }
}
// Translate DOM updates before the next paint instead of showing English for a frame.
new MutationObserver(applyLang).observe(document.body, { childList: true, subtree: true, characterData: true, attributeFilter: labelAttrs });
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
