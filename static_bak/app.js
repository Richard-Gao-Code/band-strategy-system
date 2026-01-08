
/* -------------------------------------------------------------------------- */
/*                                 Constants                                  */
/* -------------------------------------------------------------------------- */

const PARAM_DEFINITIONS = {
  "vol_shrink_min": {
    name: "最小缩量比例",
    type: "数值 (Ratio)",
    default: "0.5",
    range: "0.1 - 1.0",
    unit: "比例 (1.0=100%)",
    desc: "控制买入时的成交量缩量下限。",
    logic: "当日成交量 / 前N日均量 ≥ 该值。例如 0.5 表示当日量至少是均量的 50%。",
    example: "0.6 (表示量能至少萎缩到 60%)",
    suggestion: "调大: 排除过度缩量；调小: 允许极度缩量。"
  },
  "vol_shrink_max": {
    name: "最大缩量比例",
    type: "数值 (Ratio)",
    default: "1.0",
    range: "0.5 - 2.0",
    unit: "比例 (1.0=100%)",
    desc: "控制买入时的成交量缩量上限。",
    logic: "当日成交量 / 前N日均量 ≤ 该值。例如 1.0 表示当日量不超过均量。",
    example: "1.0 (表示量能必须缩量或持平)",
    suggestion: "调大: 允许放量（>1.0）；调小: 要求更严格的缩量。"
  },
  "min_channel_height": {
    name: "最小通道高度",
    type: "数值 (Ratio)",
    default: "0.04",
    range: "0.01 - 0.20",
    unit: "比例 (0.04=4%)",
    desc: "控制通道形态的最低高度要求，过滤波动过小的股票。",
    logic: "(上轨 - 下轨) / 中轨 ≥ 该值。",
    example: "0.06 (表示通道宽度至少 6%)",
    suggestion: "调高: 选波动大的股票；调低: 包含波动小的股票。"
  },
  "close_in_channel_min": {
    name: "收盘价位置下限",
    type: "数值 (0-1)",
    default: "0.0",
    range: "0.0 - 1.0",
    unit: "位置分位",
    desc: "收盘价在通道内的相对位置下限。",
    logic: "(收盘 - 下轨) / (上轨 - 下轨) ≥ 该值。",
    example: "0.2 (收盘价不能在通道最底部20%区域)",
    suggestion: "调高: 避免抄底过深；调低: 允许更低位置买入。"
  },
  "close_in_channel_max": {
    name: "收盘价位置上限",
    type: "数值 (0-1)",
    default: "0.5",
    range: "0.0 - 1.0",
    unit: "位置分位",
    desc: "收盘价在通道内的相对位置上限。",
    logic: "(收盘 - 下轨) / (上轨 - 下轨) ≤ 该值。",
    example: "0.5 (收盘价必须在通道下半区)",
    suggestion: "调高: 允许追高；调低: 只在底部区域买入。"
  }
};

/* -------------------------------------------------------------------------- */
/*                               Global State                                 */
/* -------------------------------------------------------------------------- */

let currentTaskId = null;
let _autosaveDebounce = null;
let _dataSyncAbort = null;
let _lastQualityPayload = null;
let _poolCache = null;

// Batch Test State
let _paramTestState = {
  running: false,
  results: [],
  abortController: null
};

/* -------------------------------------------------------------------------- */
/*                                  Helpers                                   */
/* -------------------------------------------------------------------------- */

function val(id, def = "") {
  const el = document.getElementById(id);
  return el ? el.value : def;
}

function num(id, def = 0) {
  const v = Number(val(id));
  return Number.isFinite(v) ? v : def;
}

function intv(id, def = 0) {
  return Math.floor(num(id, def));
}

function boolv(id, def = false) {
  const el = document.getElementById(id);
  return el ? el.checked : def;
}

function setInputValue(id, v) {
  const el = document.getElementById(id);
  if (el) el.value = v;
}

function toMsg(e) {
  if (!e) return "";
  if (typeof e === "string") return e;
  if (e.message) return e.message;
  return JSON.stringify(e);
}

function _escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function parseSymbolsInput(text) {
  if (!text) return [];
  return text.split(/[\n,;]+/).map(s => s.trim()).filter(Boolean);
}

function appendRunLog(msg) {
  const el = document.getElementById("run-logs");
  if (!el) return;
  const line = `[${new Date().toLocaleTimeString()}] ${msg}\n`;
  el.textContent += line;
  el.scrollTop = el.scrollHeight;
}

function _numOrNull(id) {
  const el = document.getElementById(id);
  if (!el) return null;
  const raw = (el.value ?? "").toString().trim();
  if (!raw) return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

function _intOrNull(id) {
  const n = _numOrNull(id);
  if (n == null) return null;
  return Math.trunc(n);
}

function _fmtNumber(v, digits = 2) {
  const n = Number(v);
  if (!Number.isFinite(n)) return "-";
  return n.toFixed(digits);
}

function _fmtBool(v) {
  if (v === true) return "是";
  if (v === false) return "否";
  return "-";
}

function _parseProgress(progressStr) {
  const m = String(progressStr || "").match(/(\d+)\s*\/\s*(\d+)/);
  if (!m) return null;
  const done = Number(m[1]);
  const total = Number(m[2]);
  if (!Number.isFinite(done) || !Number.isFinite(total) || total <= 0) return null;
  return { done, total };
}

function _poolStorageKey() {
  return "chhf_pool_v1";
}

function _normSymbol(s) {
  return String(s || "").trim().toUpperCase();
}

function _parsePctText(s) {
  const raw = String(s || "").trim();
  if (!raw) return null;
  if (raw === "-") return null;
  const m = raw.match(/-?\d+(\.\d+)?/);
  if (!m) return null;
  const n = Number(m[0]);
  if (!Number.isFinite(n)) return null;
  return raw.includes("%") ? n / 100.0 : n;
}

function _poolLoad() {
  if (_poolCache) return _poolCache;
  try {
    const raw = localStorage.getItem(_poolStorageKey());
    const data = raw ? JSON.parse(raw) : [];
    const list = Array.isArray(data) ? data : [];
    const out = [];
    const seen = new Set();
    for (const it of list) {
      const sym = _normSymbol(it && it.symbol);
      if (!sym || seen.has(sym)) continue;
      seen.add(sym);
      out.push({
        symbol: sym,
        alert_price: (it && Number.isFinite(Number(it.alert_price))) ? Number(it.alert_price) : null,
        note: (it && typeof it.note === "string") ? it.note : "",
        bt: (it && it.bt && typeof it.bt === "object") ? it.bt : null,
        updated_at: (it && it.updated_at) ? String(it.updated_at) : "",
      });
    }
    _poolCache = out;
    return out;
  } catch (e) {
    _poolCache = [];
    return _poolCache;
  }
}

function _poolSave(list) {
  const arr = Array.isArray(list) ? list : [];
  _poolCache = arr;
  try {
    localStorage.setItem(_poolStorageKey(), JSON.stringify(arr.slice(0, 500)));
  } catch (e) {}
}

function _poolUpsert(item) {
  const sym = _normSymbol(item && item.symbol);
  if (!sym) return;
  const now = new Date().toISOString();
  const list = _poolLoad().slice();
  const idx = list.findIndex(x => _normSymbol(x.symbol) === sym);
  const merged = {
    ...(idx >= 0 ? list[idx] : {}),
    ...item,
    symbol: sym,
    updated_at: now,
  };
  if (idx >= 0) list[idx] = merged;
  else list.unshift(merged);
  _poolSave(list.slice(0, 500));
}

function _poolRemove(symbol) {
  const sym = _normSymbol(symbol);
  if (!sym) return;
  const list = _poolLoad().filter(x => _normSymbol(x.symbol) !== sym);
  _poolSave(list);
}

function _poolGetSelectedSymbols() {
  const items = Array.from(document.querySelectorAll("#pool-list input.pool-row-select[type='checkbox']:checked"));
  return items.map(el => _normSymbol(el.dataset.symbol)).filter(Boolean);
}

function _poolSetBatchActionsVisible(visible) {
  const box = document.getElementById("pool-batch-actions");
  if (box) box.classList.toggle("hidden", !visible);
}

function _poolRender() {
  const tbody = document.getElementById("pool-list");
  const countEl = document.getElementById("pool-count");
  if (!tbody) return;
  tbody.innerHTML = "";

  const filterText = String(val("pool-filter-text", "") || "").trim().toUpperCase();
  const minScore = Number(val("pool-min-score", "")) || 0;
  const minRobust = Number(val("pool-min-robust", "")) || 0;
  const minAnnualized = Number(val("pool-min-annualized", "")) || 0;

  const list = _poolLoad();
  const rows = [];
  for (const it of list) {
    const sym = _normSymbol(it.symbol);
    if (!sym) continue;
    const note = String(it.note || "");
    if (filterText) {
      const hay = (sym + " " + note).toUpperCase();
      if (!hay.includes(filterText)) continue;
    }
    const bt = (it && it.bt) ? it.bt : null;
    const score = Number(bt && bt.score) || 0;
    const robust = Number(bt && bt.score_robust) || 0;
    const annualized = Number(bt && bt.annualized) || 0;
    if (minScore && score < minScore) continue;
    if (minRobust && robust < minRobust) continue;
    if (minAnnualized && annualized < minAnnualized) continue;
    rows.push(it);
  }

  if (countEl) countEl.textContent = String(rows.length);

  const fmtPct = (v) => {
    if (v == null || !Number.isFinite(Number(v))) return "-";
    return (Number(v) * 100).toFixed(2) + "%";
  };

  for (const it of rows) {
    const sym = _normSymbol(it.symbol);
    const bt = (it && it.bt) ? it.bt : null;
    const trades = bt && Number.isFinite(Number(bt.trades)) ? Number(bt.trades) : null;
    const winRate = bt && Number.isFinite(Number(bt.win_rate)) ? Number(bt.win_rate) : null;
    const totalReturn = bt && Number.isFinite(Number(bt.total_return)) ? Number(bt.total_return) : null;
    const note = String(it.note || "");
    const alertPx = (it.alert_price != null && Number.isFinite(Number(it.alert_price))) ? Number(it.alert_price) : null;

    const tr = document.createElement("tr");
    tr.className = "hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors";
    tr.innerHTML = `
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50">
        <input type="checkbox" class="form-checkbox h-4 w-4 text-blue-600 rounded border-slate-300 dark:border-slate-700 dark:bg-slate-800 pool-row-select" data-symbol="${_escapeHtml(sym)}" />
      </td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 font-mono text-slate-700 dark:text-slate-300">${_escapeHtml(sym)}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-500 dark:text-slate-400">${_escapeHtml((bt && bt.range) ? bt.range : "-")}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono">${fmtPct(totalReturn)}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono">${fmtPct(bt && bt.annualized)}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono">${bt && bt.mdd_days != null ? _escapeHtml(bt.mdd_days) : "-"}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono">${bt && bt.last_price != null ? _escapeHtml(bt.last_price) : "-"}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono">${alertPx != null ? alertPx.toFixed(2) : "-"}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-600 dark:text-slate-400">${_escapeHtml(bt && bt.signal ? bt.signal : "-")}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono">${bt && bt.sharpe != null ? _escapeHtml(bt.sharpe) : "-"}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono">${bt && bt.profit_factor != null ? _escapeHtml(bt.profit_factor) : "-"}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono">${bt && bt.score != null ? _escapeHtml(bt.score) : "-"}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono">${bt && bt.score_robust != null ? _escapeHtml(bt.score_robust) : "-"}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono">${fmtPct(winRate)}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono">${trades != null ? trades : "-"}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono">${bt && bt.equity_end != null ? _escapeHtml(bt.equity_end) : "-"}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-600 dark:text-slate-400 truncate max-w-[180px]" title="${_escapeHtml(note)}">${_escapeHtml(note || "-")}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-center">
        <button class="text-blue-600 hover:text-blue-800 underline text-[10px] mr-2 pool-row-bt" data-symbol="${_escapeHtml(sym)}">回测</button>
        <button class="text-purple-600 hover:text-purple-800 underline text-[10px] mr-2 pool-row-scan" data-symbol="${_escapeHtml(sym)}">扫描</button>
        <button class="text-rose-600 hover:text-rose-800 underline text-[10px] pool-row-del" data-symbol="${_escapeHtml(sym)}">删除</button>
      </td>
    `;
    tbody.appendChild(tr);
  }

  _poolSetBatchActionsVisible(_poolGetSelectedSymbols().length > 0);
}

function _poolOpenIO(mode) {
  const box = document.getElementById("pool-io-container");
  const ta = document.getElementById("pool-io");
  if (!box || !ta) return;
  box.classList.remove("hidden");
  if (mode === "export") {
    ta.value = JSON.stringify(_poolLoad(), null, 2);
  } else {
    ta.value = "";
  }
}

function _poolImportFromText(text) {
  const raw = String(text || "").trim();
  if (!raw) return { ok: false, msg: "内容为空" };
  let items = null;
  if (raw.startsWith("[") || raw.startsWith("{")) {
    try {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) items = parsed;
      else if (parsed && typeof parsed === "object") items = [parsed];
    } catch (e) {}
  }
  if (!items) {
    const syms = raw.split(/[\n,;\t ]+/).map(s => _normSymbol(s)).filter(Boolean);
    items = syms.map(s => ({ symbol: s }));
  }
  const list = _poolLoad().slice();
  const map = new Map(list.map(x => [_normSymbol(x.symbol), x]));
  for (const it of items) {
    const sym = _normSymbol(it && it.symbol);
    if (!sym) continue;
    const cur = map.get(sym) || { symbol: sym };
    const merged = {
      ...cur,
      ...it,
      symbol: sym,
      alert_price: (it && Number.isFinite(Number(it.alert_price))) ? Number(it.alert_price) : cur.alert_price ?? null,
      note: (it && typeof it.note === "string") ? it.note : (cur.note || ""),
      updated_at: new Date().toISOString(),
    };
    map.set(sym, merged);
  }
  const out = Array.from(map.values()).slice(0, 500);
  _poolSave(out);
  _poolRender();
  return { ok: true, msg: `已导入/合并 ${items.length} 条` };
}

function poolImportFromBacktest() {
  const topn = Math.max(1, Math.min(500, intv("pool-topn", 30)));
  const orderby = val("pool-orderby", "score_robust").trim();
  const rows = Array.from(document.querySelectorAll("#bt-results tr"));
  if (!rows.length) {
    alert("请先运行一次回测，产生回测结果后再导入");
    return;
  }
  const parsed = [];
  for (const tr of rows) {
    const tds = Array.from(tr.querySelectorAll("td"));
    if (tds.length < 5) continue;
    const symbol = _normSymbol(tds[0].textContent);
    if (!symbol) continue;
    const trades = Number(String(tds[1].textContent || "").trim());
    const win_rate = _parsePctText(tds[2].textContent);
    const total_return = _parsePctText(tds[3].textContent);
    const max_drawdown = _parsePctText(tds[4].textContent);
    const score = Number.isFinite(total_return) ? total_return * 100 : 0;
    const score_robust = (Number.isFinite(total_return) ? total_return * 100 : 0) - (Number.isFinite(max_drawdown) ? Math.abs(max_drawdown) * 100 : 0);
    parsed.push({
      symbol,
      bt: {
        trades: Number.isFinite(trades) ? trades : null,
        win_rate,
        total_return,
        max_drawdown,
        score: Number(score.toFixed(4)),
        score_robust: Number(score_robust.toFixed(4)),
        range: (() => {
          const beg = normalizeYmOrYmd(val("bt-beg", ""), "beg");
          const end = normalizeYmOrYmd(val("bt-end", ""), "end");
          if (!beg && !end) return "-";
          return `${beg || "-"} ~ ${end || "-"}`;
        })(),
      }
    });
  }
  parsed.sort((a, b) => {
    const av = Number(a.bt && a.bt[orderby]) || 0;
    const bv = Number(b.bt && b.bt[orderby]) || 0;
    return bv - av;
  });
  const picked = parsed.slice(0, topn);
  for (const it of picked) _poolUpsert(it);
  _poolRender();
  alert(`已从回测导入 ${picked.length} 只股票到池子`);
}

function _poolRunBacktest(symbols) {
  const syms = Array.isArray(symbols) ? symbols : [];
  if (!syms.length) return;
  setActiveView("backtest");
  setInputValue("bt-symbols", syms.join(", "));
  runChannelHFBacktest(syms);
}

function _poolRunScan(symbols) {
  const syms = Array.isArray(symbols) ? symbols : [];
  if (!syms.length) return;
  setActiveView("scan");
  setInputValue("scan-symbols", syms.join(", "));
  runChannelHFScan();
}

function _poolInitUI() {
  const addBtn = document.getElementById("pool-add");
  if (addBtn) addBtn.onclick = () => {
    const sym = _normSymbol(val("pool-symbol", ""));
    if (!sym) {
      alert("请输入股票代码");
      return;
    }
    const apRaw = String(val("pool-alert-price", "") || "").trim();
    const ap = apRaw ? Number(apRaw) : null;
    _poolUpsert({ symbol: sym, alert_price: (ap != null && Number.isFinite(ap)) ? ap : null });
    _poolRender();
  };

  const watchBtn = document.getElementById("pool-watch");
  if (watchBtn) watchBtn.onclick = () => {
    const syms = _poolLoad().map(x => _normSymbol(x.symbol)).filter(Boolean);
    setActiveView("scan");
    setInputValue("scan-symbols", syms.join(", "));
  };

  const btBtn = document.getElementById("pool-backtest");
  if (btBtn) btBtn.onclick = () => {
    const syms = _poolLoad().map(x => _normSymbol(x.symbol)).filter(Boolean);
    _poolRunBacktest(syms);
  };

  const scanBtn = document.getElementById("pool-scan");
  if (scanBtn) scanBtn.onclick = () => {
    const syms = _poolLoad().map(x => _normSymbol(x.symbol)).filter(Boolean);
    _poolRunScan(syms);
  };

  const clearBtn = document.getElementById("pool-clear");
  if (clearBtn) clearBtn.onclick = () => {
    if (!confirm("确认清空池子？")) return;
    _poolSave([]);
    _poolRender();
  };

  const exportBtn = document.getElementById("pool-export");
  if (exportBtn) exportBtn.onclick = () => _poolOpenIO("export");

  const exportCsvBtn = document.getElementById("pool-export-csv");
  if (exportCsvBtn) exportCsvBtn.onclick = () => {
    const list = _poolLoad();
    const rows = [["symbol", "alert_price", "note"]];
    for (const it of list) rows.push([it.symbol, it.alert_price != null ? String(it.alert_price) : "", String(it.note || "")]);
    const csv = rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    const url = URL.createObjectURL(blob);
    link.setAttribute("href", url);
    link.setAttribute("download", `pool_${new Date().toISOString().slice(0,10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const importBtn = document.getElementById("pool-import");
  if (importBtn) importBtn.onclick = () => _poolOpenIO("import");

  const importConfirmBtn = document.getElementById("pool-import-confirm");
  if (importConfirmBtn) importConfirmBtn.onclick = () => {
    const ta = document.getElementById("pool-io");
    const box = document.getElementById("pool-io-container");
    const r = _poolImportFromText(ta ? ta.value : "");
    if (!r.ok) alert(r.msg || "导入失败");
    else {
      if (box) box.classList.add("hidden");
      alert(r.msg || "导入成功");
    }
  };

  const filterIds = ["pool-filter-text", "pool-min-score", "pool-min-robust", "pool-min-annualized"];
  for (const id of filterIds) {
    const el = document.getElementById(id);
    if (el) el.addEventListener("input", () => _poolRender());
  }

  const selAll = document.getElementById("pool-select-all");
  if (selAll) selAll.addEventListener("change", () => {
    const checked = !!selAll.checked;
    for (const cb of Array.from(document.querySelectorAll("#pool-list input.pool-row-select[type='checkbox']"))) {
      cb.checked = checked;
    }
    _poolSetBatchActionsVisible(_poolGetSelectedSymbols().length > 0);
  });

  const batchDel = document.getElementById("pool-batch-del");
  if (batchDel) batchDel.onclick = () => {
    const syms = _poolGetSelectedSymbols();
    if (!syms.length) return;
    if (!confirm(`确认删除选中的 ${syms.length} 只股票？`)) return;
    for (const s of syms) _poolRemove(s);
    _poolRender();
  };

  const batchBt = document.getElementById("pool-batch-bt");
  if (batchBt) batchBt.onclick = () => {
    const syms = _poolGetSelectedSymbols();
    if (!syms.length) return;
    _poolRunBacktest(syms);
  };

  const batchScan = document.getElementById("pool-batch-scan");
  if (batchScan) batchScan.onclick = () => {
    const syms = _poolGetSelectedSymbols();
    if (!syms.length) return;
    _poolRunScan(syms);
  };

  const tbody = document.getElementById("pool-list");
  if (tbody) tbody.addEventListener("click", (ev) => {
    const t = ev.target;
    if (!t) return;
    const sym = _normSymbol(t.dataset && t.dataset.symbol);
    if (t.classList && t.classList.contains("pool-row-del")) {
      if (!sym) return;
      _poolRemove(sym);
      _poolRender();
      return;
    }
    if (t.classList && t.classList.contains("pool-row-bt")) {
      if (!sym) return;
      _poolRunBacktest([sym]);
      return;
    }
    if (t.classList && t.classList.contains("pool-row-scan")) {
      if (!sym) return;
      _poolRunScan([sym]);
      return;
    }
    if (t.classList && t.classList.contains("pool-row-select")) {
      _poolSetBatchActionsVisible(_poolGetSelectedSymbols().length > 0);
      return;
    }
  });

  _poolRender();
}

async function _smartLoadFileList() {
  const sel = document.getElementById("smart-file-select");
  if (!sel) return;
  try {
    const resp = await fetch("/api/list_data_files");
    if (!resp.ok) throw new Error("加载失败");
    const files = await resp.json();
    const arr = Array.isArray(files) ? files : [];
    sel.innerHTML = "";
    const opt0 = document.createElement("option");
    opt0.value = "";
    opt0.textContent = arr.length ? "请选择..." : "未找到可用文件";
    sel.appendChild(opt0);
    for (const p of arr) {
      const o = document.createElement("option");
      o.value = String(p);
      o.textContent = String(p);
      sel.appendChild(o);
    }
  } catch (e) {
    sel.innerHTML = `<option value="">加载失败</option>`;
  }
}

async function runSmartAsk() {
  const btn = document.getElementById("smart-ask-btn");
  const fileSel = document.getElementById("smart-file-select");
  const qInput = document.getElementById("smart-query-input");
  const container = document.getElementById("smart-result-container");
  const answerEl = document.getElementById("smart-answer-text");
  const sqlEl = document.getElementById("smart-sql-text");
  const headEl = document.getElementById("smart-table-head");
  const bodyEl = document.getElementById("smart-table-body");
  if (!fileSel || !qInput || !answerEl || !sqlEl || !headEl || !bodyEl) return;

  const filePath = String(fileSel.value || "").trim();
  const query = String(qInput.value || "").trim();
  if (!filePath) {
    alert("请选择数据文件");
    return;
  }
  if (!query) {
    alert("请输入问题");
    return;
  }

  if (btn) btn.disabled = true;
  if (container) container.classList.add("hidden");
  answerEl.textContent = "";
  sqlEl.textContent = "";
  headEl.innerHTML = "";
  bodyEl.innerHTML = "";

  try {
    const resp = await fetch("/api/smart_analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_path: filePath, query }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || "请求失败");
    }
    const data = await resp.json();
    answerEl.textContent = String(data.answer || "");
    sqlEl.textContent = String(data.sql || "");
    const rows = Array.isArray(data.data) ? data.data : [];
    const cols = rows.length ? Object.keys(rows[0] || {}) : [];
    if (cols.length) {
      const trh = document.createElement("tr");
      trh.className = "bg-slate-50/90 dark:bg-slate-800/90";
      trh.innerHTML = cols.map(c => `<th class="px-3 py-2 text-left font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider border-b border-slate-100 dark:border-slate-800">${_escapeHtml(c)}</th>`).join("");
      headEl.appendChild(trh);
      for (const r of rows) {
        const tr = document.createElement("tr");
        tr.className = "hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors";
        tr.innerHTML = cols.map(c => `<td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-700 dark:text-slate-300">${_escapeHtml(r && r[c] != null ? r[c] : "")}</td>`).join("");
        bodyEl.appendChild(tr);
      }
    }
    if (container) container.classList.remove("hidden");
  } catch (e) {
    alert("分析失败: " + toMsg(e));
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function runSelector() {
  const btn = document.getElementById("selector-run-btn");
  const statusEl = document.getElementById("selector-status");
  const outEl = document.getElementById("selector-results");
  if (!statusEl || !outEl) return;

  const pathUd = val("sel-path-ud", "").trim();
  const pathMu = val("sel-path-mu", "").trim();
  const maxMdd = Number(val("sel-max-mdd", "0.10"));
  const minTrd = intv("sel-min-trd", 15);
  const calmarMin = Number(val("sel-calmar-min", "3.0"));
  if (!pathUd || !pathMu) {
    alert("请填写两个文件路径");
    return;
  }

  if (btn) btn.disabled = true;
  statusEl.textContent = "运行中";
  outEl.textContent = "";
  try {
    const resp = await fetch("/api/selector", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        path_ud: pathUd,
        path_mu: pathMu,
        max_mdd: Number.isFinite(maxMdd) ? maxMdd : 0.10,
        min_trd: Number.isFinite(minTrd) ? minTrd : 15,
        calmar_min: Number.isFinite(calmarMin) ? calmarMin : 3.0,
      }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || "请求失败");
    }
    const data = await resp.json();
    statusEl.textContent = "完成";
    outEl.textContent = JSON.stringify(data, null, 2);
  } catch (e) {
    statusEl.textContent = "失败";
    outEl.textContent = toMsg(e);
  } finally {
    if (btn) btn.disabled = false;
  }
}

function getStrategyConfigFromUI() {
  return {
    channel_period: intv("cfg-channel-period", 20),
    buy_touch_eps: num("cfg-buy-eps", 0.005),
    sell_trigger_eps: num("cfg-sell-eps", 0.005),
    sell_target_mode: val("cfg-sell-mode", "mid_up"),
    channel_break_eps: num("cfg-break-eps", 0.02),
    entry_fill_eps: num("cfg-entry-eps", 0.002),
    exit_fill_eps: num("cfg-exit-eps", 0.002),
    stop_loss_mul: num("cfg-stop-loss", 0.97),
    stop_loss_on_close: boolv("cfg-stop-loss-on-close", true),
    stop_loss_panic_eps: num("cfg-stop-loss-panic-eps", 0.02),
    max_holding_days: intv("cfg-max-hold", 20),
    cooling_period: intv("cfg-cool", 5),
    slope_abs_max: num("cfg-slope-abs", 0.01),
    min_slope_norm: num("cfg-min-slope-norm", -1.0),
    vol_shrink_min: _numOrNull("cfg-vol-shrink-min"),
    vol_shrink_max: _numOrNull("cfg-vol-shrink-max"),
    min_channel_height: _numOrNull("cfg-min-height") ?? 0.05,
    min_mid_room: _numOrNull("cfg-min-room") ?? 0.015,
    min_mid_profit_pct: _numOrNull("cfg-min-mid-profit-pct") ?? 0.0,
    min_rr_to_mid: _numOrNull("cfg-min-rr-to-mid") ?? 0.0,
    scan_recent_days: _intOrNull("cfg-recent-days") ?? 1,
    require_index_condition: boolv("cfg-require-index-confirm", true),
    index_bear_exit: boolv("cfg-index-bear-exit", true),
    fill_at_close: boolv("cfg-fill-at-close", true),
    trend_ma_period: _intOrNull("cfg-trend-ma-period") ?? 0,
    index_trend_ma_period: _intOrNull("cfg-index-trend-ma-period") ?? 0,
    require_rebound: boolv("cfg-require-rebound", false),
    require_green: boolv("cfg-require-green", false),
    max_positions: _intOrNull("cfg-max-positions") ?? 5,
    max_position_pct: _numOrNull("cfg-max-position-pct") ?? 0.10,
    pivot_confirm_days: _intOrNull("cfg-pivot-confirm-days"),
    pivot_no_new_low_tol: _numOrNull("cfg-pivot-no-new-low-tol"),
    pivot_rebound_amp: _numOrNull("cfg-pivot-rebound-amp"),
    pivot_confirm_requires_sig: boolv("cfg-pivot-confirm-requires-sig", true),
    volatility_ratio_max: _numOrNull("cfg-volatility-ratio-max"),
  };
}

function _clearScanResults() {
  const tbody = document.getElementById("scan-results");
  if (tbody) tbody.innerHTML = "";
}

function _setScanUiRunning(running) {
  const btn = document.getElementById("scan-btn");
  const cancelBtn = document.getElementById("scan-cancel-btn");
  if (btn) btn.disabled = !!running;
  if (cancelBtn) cancelBtn.classList.toggle("hidden", !running);
}

function _setScanStatus(text) {
  const el = document.getElementById("scan-status");
  if (el) el.textContent = text;
}

function _setScanProgress(done, total) {
  const bar = document.getElementById("scan-progress-bar");
  const txt = document.getElementById("scan-progress-text");
  const pct = total > 0 ? Math.max(0, Math.min(100, (done / total) * 100)) : 0;
  if (bar) bar.style.width = `${pct.toFixed(2)}%`;
  if (txt) txt.textContent = total > 0 ? `${done}/${total}` : "";
}

function _renderScanResultRow(data) {
  const tbody = document.getElementById("scan-results");
  if (!tbody || !data) return;

  const env = data.env || {};
  const cfg = getStrategyConfigFromUI();

  const symbol = data.symbol || env.symbol || "-";
  const dt = env.date || data.last_date || "-";
  const indexBear = env.index_bear;
  const slopeNorm = env.slope_norm;
  const channelHeight = env.channel_height;
  const upper = env.upper;
  const mid = env.mid;
  const lower = env.lower;
  const volRatio = env.vol_ratio;
  const sig = env.final_signal;

  const buyEps = Number(cfg.buy_touch_eps ?? 0.005);
  const sellEps = Number(cfg.sell_trigger_eps ?? 0.005);
  const stopMul = Number(cfg.stop_loss_mul ?? 0.97);
  const sellMode = String(cfg.sell_target_mode || "mid_up").trim().toLowerCase();

  const buyPx = (Number.isFinite(Number(lower)) ? Number(lower) * (1.0 + Math.max(0, buyEps)) : null);
  const stopPx = (buyPx != null && Number.isFinite(stopMul) ? buyPx * Math.max(0, stopMul) : null);
  let sellPx = null;
  if (Number.isFinite(Number(mid)) && Number.isFinite(Number(upper))) {
    if (sellMode === "mid_up") sellPx = Number(mid) * (1.0 + Math.max(0, sellEps));
    else if (sellMode === "upper_down") sellPx = Number(upper) * (1.0 - Math.max(0, sellEps));
    else sellPx = Number(mid) * (1.0 - Math.max(0, sellEps));
  }

  const statusText = sig === 1 ? "买入" : (sig === -1 ? "卖出" : "-");

  const tr = document.createElement("tr");
  tr.className = "hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors";
  tr.innerHTML = `
    <td class="px-3 py-2 border-b border-slate-100 dark:border-slate-800/50 font-mono text-slate-700 dark:text-slate-300">${symbol}</td>
    <td class="px-3 py-2 border-b border-slate-100 dark:border-slate-800/50 font-mono text-slate-600 dark:text-slate-400">${dt}</td>
    <td class="px-3 py-2 border-b border-slate-100 dark:border-slate-800/50 text-slate-600 dark:text-slate-400">${_fmtBool(indexBear)}</td>
    <td class="px-3 py-2 border-b border-slate-100 dark:border-slate-800/50 text-right font-mono text-slate-600 dark:text-slate-400">${_fmtNumber(slopeNorm, 4)}</td>
    <td class="px-3 py-2 border-b border-slate-100 dark:border-slate-800/50 text-right font-mono text-slate-600 dark:text-slate-400">${_fmtNumber(channelHeight, 4)}</td>
    <td class="px-3 py-2 border-b border-slate-100 dark:border-slate-800/50 text-right font-mono text-slate-600 dark:text-slate-400">${_fmtNumber(upper, 2)}</td>
    <td class="px-3 py-2 border-b border-slate-100 dark:border-slate-800/50 text-right font-mono text-slate-600 dark:text-slate-400">${_fmtNumber(mid, 2)}</td>
    <td class="px-3 py-2 border-b border-slate-100 dark:border-slate-800/50 text-right font-mono text-slate-600 dark:text-slate-400">${_fmtNumber(lower, 2)}</td>
    <td class="px-3 py-2 border-b border-slate-100 dark:border-slate-800/50 text-right font-mono text-blue-600 dark:text-blue-400">${_fmtNumber(buyPx, 2)}</td>
    <td class="px-3 py-2 border-b border-slate-100 dark:border-slate-800/50 text-right font-mono text-rose-600 dark:text-rose-400">${_fmtNumber(stopPx, 2)}</td>
    <td class="px-3 py-2 border-b border-slate-100 dark:border-slate-800/50 text-right font-mono text-emerald-600 dark:text-emerald-400">${_fmtNumber(sellPx, 2)}</td>
    <td class="px-3 py-2 border-b border-slate-100 dark:border-slate-800/50 text-right font-mono text-slate-600 dark:text-slate-400">${_fmtNumber(volRatio, 2)}</td>
    <td class="px-3 py-2 border-b border-slate-100 dark:border-slate-800/50 text-slate-700 dark:text-slate-300 font-bold">${statusText}</td>
    <td class="px-3 py-2 border-b border-slate-100 dark:border-slate-800/50 text-slate-500 dark:text-slate-400 text-[11px] truncate max-w-[240px]">${_escapeHtml((env.trace && env.trace.length) ? env.trace[env.trace.length - 1].reason : (data.error || ""))}</td>
  `;
  tbody.appendChild(tr);
}

async function runChannelHFScan() {
  const btn = document.getElementById("scan-btn");
  const status = document.getElementById("scan-status");
  const logsEl = document.getElementById("run-logs");

  _clearScanResults();
  _setScanProgress(0, 0);
  if (logsEl) logsEl.textContent = "";

  const dataDir = val("scan-data-dir", "").trim();
  if (!dataDir) {
    if (status) status.textContent = "请输入股票文件目录地址";
    return;
  }

  _setScanUiRunning(true);
  _setScanStatus("扫描中");
  appendRunLog("启动扫描...");

  const useIndex = boolv("scan-use-index", true);
  const useRealtime = boolv("scan-use-realtime", false);
  const indexData = val("scan-index-data", "").trim();
  const indexSymbol = val("scan-index-symbol", "000300.SH").trim();

  try {
    const req = {
      data_dir: dataDir,
      symbols: parseSymbolsInput(val("scan-symbols", "")),
      index_data: useIndex ? (indexData || null) : null,
      index_symbol: useIndex ? (indexSymbol || null) : null,
      use_realtime: !!useRealtime,
      ...getStrategyConfigFromUI(),
    };

    const resp = await fetch("/api/scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || "启动失败");
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buf = "";
    let total = 0;
    let done = 0;

    while (true) {
      const { done: streamDone, value } = await reader.read();
      if (streamDone) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop() || "";

      for (const line of lines) {
        if (!line.trim()) continue;
        const msg = JSON.parse(line);

        if (msg.type === "start") {
          total = Number(msg.total || 0);
          currentTaskId = msg.job_id || null;
          done = 0;
          _setScanProgress(done, total);
          appendRunLog(`扫描开始 job_id=${currentTaskId || "-" } total=${total}`);
          continue;
        }

        if (msg.type === "heartbeat") {
          const p = _parseProgress(msg.progress);
          if (p) {
            done = p.done;
            total = p.total;
            _setScanProgress(done, total);
          }
          appendRunLog(`扫描中... ${msg.progress || ""}`.trim());
          continue;
        }

        if (msg.type === "result") {
          const p = _parseProgress(msg.progress);
          if (p) {
            done = p.done;
            total = p.total;
          } else {
            done += 1;
          }
          _setScanProgress(done, total);
          if (msg.status === "success") _renderScanResultRow(msg.data);
          else appendRunLog(`Error: ${msg.message || "未知错误"}`);
          continue;
        }

        if (msg.type === "error") {
          appendRunLog(`Error: ${msg.message || "未知错误"}`);
          continue;
        }

        if (msg.type === "cancelled") {
          appendRunLog(`已中断 ${msg.progress || ""}`.trim());
          continue;
        }

        if (msg.type === "end") {
          appendRunLog("扫描结束");
          continue;
        }
      }
    }

    _setScanStatus("完成");
  } catch (e) {
    const msg = toMsg(e);
    _setScanStatus(`Error: ${msg}`);
    appendRunLog(`Error: ${msg}`);
  } finally {
    _setScanUiRunning(false);
    currentTaskId = null;
  }
}

async function cancelChannelHFScan() {
  const jid = currentTaskId;
  if (!jid) {
    appendRunLog("当前没有可中断的扫描任务");
    return;
  }
  try {
    const resp = await fetch("/api/scan/cancel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: jid }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || "中断失败");
    }
    const data = await resp.json().catch(() => ({}));
    appendRunLog(data.msg || "已请求中断");
  } catch (e) {
    appendRunLog(`Error: ${toMsg(e)}`);
  }
}

async function runDataSyncOnce() {
  const btn = document.getElementById("data-sync-btn");
  const statusEl = document.getElementById("data-sync-status");
  const logsEl = document.getElementById("run-logs");

  if (logsEl) logsEl.textContent = "";

  const outDir = val("data-out-dir", "").trim();
  if (!outDir) {
    if (statusEl) statusEl.textContent = "请输入输出目录";
    return;
  }

  if (_dataSyncAbort) {
    try { _dataSyncAbort.abort(); } catch {}
  }
  _dataSyncAbort = new AbortController();

  if (btn) btn.disabled = true;
  if (statusEl) statusEl.textContent = "同步中...";
  appendRunLog("启动数据同步...");

  try {
    const req = {
      out_dir: outDir,
      beg: val("data-beg", "20150101").trim(),
      end: val("data-end", "20500101").trim(),
      adjust: val("data-adjust", "qfq").trim(),
      market: val("data-market", "").trim() || null,
      tail_days: intv("data-tail-days", 5),
      max_concurrency: intv("data-max-conc", 8),
      full: boolv("data-full", false),
      symbols: parseSymbolsInput(val("data-symbols", "")),
    };

    const resp = await fetch("/api/data/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
      signal: _dataSyncAbort.signal,
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || "启动失败");
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buf = "";
    let total = 0;
    let ok = 0;
    let bad = 0;

    while (true) {
      const { done: streamDone, value } = await reader.read();
      if (streamDone) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop() || "";

      for (const line of lines) {
        if (!line.trim()) continue;
        const msg = JSON.parse(line);

        if (msg.type === "meta") {
          total = Number(msg.total || 0);
          appendRunLog(`同步开始 total=${total} out_dir=${msg.out_dir || "-"}`);
          if (statusEl) statusEl.textContent = `同步中... 0/${total}`;
          continue;
        }

        if (msg.type === "phase") {
          if (statusEl) statusEl.textContent = msg.message || "同步中...";
          appendRunLog(msg.message || "同步中...");
          continue;
        }

        if (msg.type === "result") {
          const r = msg.data || {};
          const sym = r.symbol || "-";
          if (msg.status === "success") {
            ok += 1;
            appendRunLog(`OK ${sym} bars=${r.bars || 0} last=${r.last_date || "-"}`);
          } else {
            bad += 1;
            appendRunLog(`ERR ${sym} ${r.error || "同步失败"}`);
          }
          if (statusEl) statusEl.textContent = `同步中... ${msg.progress || ""} ok=${ok} err=${bad}`.trim();
          continue;
        }

        if (msg.type === "end") {
          if (statusEl) statusEl.textContent = `完成 total=${msg.total || total} ok=${msg.ok ?? ok} err=${msg.err ?? bad}`;
          appendRunLog("同步结束");
          continue;
        }

        if (msg.type === "error") {
          const m = msg.message || "未知错误";
          if (statusEl) statusEl.textContent = `Error: ${m}`;
          appendRunLog(`Error: ${m}`);
          continue;
        }
      }
    }
  } catch (e) {
    const m = toMsg(e);
    if (statusEl) statusEl.textContent = `Error: ${m}`;
    appendRunLog(`Error: ${m}`);
  } finally {
    if (btn) btn.disabled = false;
  }
}

function stopDataSyncStream() {
  if (_dataSyncAbort) {
    try { _dataSyncAbort.abort(); } catch {}
  }
  appendRunLog("已停止读取同步输出");
}

function _renderParamHelpInline(key) {
  const out = document.getElementById("config-help-content");
  if (!out) return;
  const k = String(key || "").trim();
  if (!k) {
    out.textContent = "";
    return;
  }

  const def = PARAM_DEFINITIONS[k];
  if (def) {
    const lines = [
      `${def.name} (${k})`,
      `类型：${def.type}`,
      `默认：${def.default}`,
      `范围：${def.range}`,
      `单位：${def.unit}`,
      "",
      `说明：${def.desc}`,
      `逻辑：${def.logic}`,
      `示例：${def.example}`,
      `建议：${def.suggestion}`,
    ];
    out.textContent = lines.join("\n");
    return;
  }

  out.textContent = `参数：${k}\n暂无内置说明`;
}

function initConfigParamHelpBinding() {
  const root = document.getElementById("view-config");
  if (!root) return;
  const bindings = _collectConfigBindings();
  const elToKey = new Map();
  for (const [k, el] of bindings.entries()) {
    if (el) elToKey.set(el, k);
  }

  const handler = (ev) => {
    const t = ev.target;
    if (!(t instanceof HTMLElement)) return;
    const el = t.closest("input, select, textarea");
    if (!el) return;
    const k = elToKey.get(el);
    if (k) _renderParamHelpInline(k);
  };

  root.addEventListener("focusin", handler);
  root.addEventListener("click", handler);
}

/* -------------------------------------------------------------------------- */
/*                           Rejection Analysis                               */
/* -------------------------------------------------------------------------- */

async function showRejectionDetails(symbol) {
  // Create or get modal
  let modal = document.getElementById("rejection-modal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "rejection-modal";
    modal.className = "fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm hidden";
    modal.innerHTML = `
      <div class="bg-white dark:bg-slate-800 rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden border border-slate-200 dark:border-slate-700">
        <div class="px-6 py-4 border-b border-slate-100 dark:border-slate-700 flex justify-between items-center bg-slate-50 dark:bg-slate-800/50">
          <h3 class="text-lg font-bold text-slate-800 dark:text-slate-100">拒绝详情分析: <span id="rej-symbol" class="text-blue-600 font-mono"></span></h3>
          <button onclick="document.getElementById('rejection-modal').classList.add('hidden')" class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </div>
        <div class="flex-1 overflow-auto p-0">
          <table class="min-w-full text-sm text-left">
            <thead class="bg-slate-50 dark:bg-slate-800/80 sticky top-0 z-10 text-xs font-semibold text-slate-500 uppercase tracking-wider">
              <tr>
                <th class="px-6 py-3 border-b border-slate-200 dark:border-slate-700">日期</th>
                <th class="px-6 py-3 border-b border-slate-200 dark:border-slate-700">过滤器类型</th>
                <th class="px-6 py-3 border-b border-slate-200 dark:border-slate-700">检查条件</th>
                <th class="px-6 py-3 border-b border-slate-200 dark:border-slate-700 text-right">实际值</th>
                <th class="px-6 py-3 border-b border-slate-200 dark:border-slate-700 text-right">阈值要求</th>
                <th class="px-6 py-3 border-b border-slate-200 dark:border-slate-700">拒绝原因</th>
              </tr>
            </thead>
            <tbody id="rej-tbody" class="divide-y divide-slate-100 dark:divide-slate-700/50"></tbody>
          </table>
          <div id="rej-loading" class="p-8 text-center text-slate-500">加载中...</div>
          <div id="rej-empty" class="p-8 text-center text-slate-500 hidden">无拒绝记录</div>
        </div>
        <div class="px-6 py-4 border-t border-slate-100 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 flex justify-end gap-3">
          <button id="rej-export-btn" class="btn-secondary px-4 py-2 text-sm">导出 CSV</button>
          <button onclick="document.getElementById('rejection-modal').classList.add('hidden')" class="btn-primary px-4 py-2 text-sm">关闭</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  }

  const symbolEl = document.getElementById("rej-symbol");
  const tbody = document.getElementById("rej-tbody");
  const loading = document.getElementById("rej-loading");
  const empty = document.getElementById("rej-empty");
  const exportBtn = document.getElementById("rej-export-btn");

  if (symbolEl) symbolEl.textContent = symbol;
  if (tbody) tbody.innerHTML = "";
  if (loading) loading.classList.remove("hidden");
  if (empty) empty.classList.add("hidden");
  modal.classList.remove("hidden");

  try {
    const d = await fetchBacktestDetailForSymbol(symbol);
    if (loading) loading.classList.add("hidden");

    const rejections = d && d.rejections ? d.rejections : [];
    // If no structured rejections, try to parse from text (fallback)
    // Note: Ideally backend provides `rejections` array.

    if (!rejections || rejections.length === 0) {
      if (empty) empty.classList.remove("hidden");
      exportBtn.onclick = null;
      exportBtn.disabled = true;
      return;
    }

    exportBtn.disabled = false;
    exportBtn.onclick = () => exportRejectionDetailsCsv(rejections, symbol);

    rejections.forEach(r => {
      const tr = document.createElement("tr");
      tr.className = "hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors";
      tr.innerHTML = `
        <td class="px-6 py-3 text-slate-700 dark:text-slate-300 whitespace-nowrap font-mono">${r.date || "-"}</td>
        <td class="px-6 py-3 text-slate-600 dark:text-slate-400">${r.filter_type || "-"}</td>
        <td class="px-6 py-3 text-slate-600 dark:text-slate-400 text-xs">${_escapeHtml(r.condition || "-")}</td>
        <td class="px-6 py-3 text-right font-mono text-slate-700 dark:text-slate-300">${r.actual_value || "-"}</td>
        <td class="px-6 py-3 text-right font-mono text-slate-700 dark:text-slate-300">${r.threshold || "-"}</td>
        <td class="px-6 py-3 text-red-600 dark:text-red-400 font-medium">${_escapeHtml(r.reason || "-")}</td>
      `;
      tbody.appendChild(tr);
    });

  } catch (e) {
    if (loading) loading.classList.add("hidden");
    if (tbody) tbody.innerHTML = `<tr><td colspan="6" class="px-6 py-4 text-center text-red-500">加载失败: ${e.message}</td></tr>`;
  }
}

function exportRejectionDetailsCsv(rejections, symbol) {
  if (!rejections || !rejections.length) return;
  
  const headers = ["日期", "过滤器类型", "检查条件", "实际值", "阈值要求", "拒绝原因"];
  const rows = rejections.map(r => [
    r.date,
    r.filter_type,
    r.condition,
    r.actual_value,
    r.threshold,
    r.reason
  ]);

  const csvContent = [
    headers.join(","),
    ...rows.map(r => r.map(c => `"${String(c || "").replace(/"/g, '""')}"`).join(","))
  ].join("\n");

  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const link = document.createElement("a");
  const url = URL.createObjectURL(blob);
  link.setAttribute("href", url);
  link.setAttribute("download", `rejection_details_${symbol}_${new Date().toISOString().slice(0,10)}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

/* -------------------------------------------------------------------------- */
/*                           Batch Parameter Test                             */
/* -------------------------------------------------------------------------- */

function generateParamGrid() {
  const input = document.getElementById("pt-param-grid");
  const output = document.getElementById("pt-param-sets");
  const status = document.getElementById("pt-status");
  
  if (!input || !output) return;
  
  const text = input.value.trim();
  if (!text) {
    alert("请输入网格参数配置");
    return;
  }
  
  try {
    const lines = text.split("\n").map(l => l.trim()).filter(l => l && !l.startsWith("#"));
    const keys = [];
    const values = [];
    
    for (const line of lines) {
      const parts = line.split(/[:=]/);
      if (parts.length < 2) continue;
      
      const key = parts[0].trim();
      let valStr = parts.slice(1).join(":").trim();
      
      if (valStr.startsWith("[") && valStr.endsWith("]")) {
        try {
          const inner = valStr.slice(1, -1);
          const vs = inner.split(",").map(v => {
            v = v.trim();
            if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) {
              return v.slice(1, -1);
            }
            return isNaN(Number(v)) ? v : Number(v);
          });
          keys.push(key);
          values.push(vs);
        } catch (e) {
          console.warn("Failed to parse list:", valStr);
        }
      } else {
        const v = isNaN(Number(valStr)) ? valStr : Number(valStr);
        keys.push(key);
        values.push([v]);
      }
    }
    
    if (keys.length === 0) {
      alert("未识别到有效的参数配置");
      return;
    }
    
    const cartesian = (args) => {
      const r = [];
      const max = args.length - 1;
      const helper = (arr, i) => {
        for (let j = 0, l = args[i].length; j < l; j++) {
          const a = arr.slice(0);
          a.push(args[i][j]);
          if (i === max) r.push(a);
          else helper(a, i + 1);
        }
      };
      helper([], 0);
      return r;
    };
    
    const combos = cartesian(values);
    const linesOut = combos.map(combo => {
      return combo.map((v, i) => `${keys[i]}=${v}`).join(", ");
    });
    
    output.value = linesOut.join("\n");
    if (status) status.textContent = `已生成 ${linesOut.length} 组参数组合`;
    
  } catch (e) {
    alert("生成失败: " + e.message);
  }
}

async function runParamBatchTest() {
  const btn = document.getElementById("pt-run-btn");
  const exportBtn = document.getElementById("pt-export-btn");
  const status = document.getElementById("pt-status");
  const tbody = document.getElementById("pt-results");
  const symbolsInput = document.getElementById("pt-symbols");
  const paramSetsInput = document.getElementById("pt-param-sets");
  
  if (_paramTestState.running) {
    if (confirm("确定要停止当前测试吗？")) {
      if (_paramTestState.abortController) _paramTestState.abortController.abort();
      _paramTestState.running = false;
    }
    return;
  }
  
  const symsRaw = symbolsInput ? symbolsInput.value.trim() : "";
  if (!symsRaw) { alert("请输入股票代码"); return; }
  
  const paramsRaw = paramSetsInput ? paramSetsInput.value.trim() : "";
  if (!paramsRaw) { alert("请输入参数组合"); return; }
  
  const symbols = parseSymbolsInput(symsRaw);
  if (!symbols.length) { alert("未找到有效的股票代码"); return; }
  
  const paramSets = [];
  const lines = paramsRaw.split("\n").map(l => l.trim()).filter(l => l && !l.startsWith("#"));
  for (const line of lines) {
    const parts = line.split(",");
    const set = {};
    let label = "";
    for (const part of parts) {
      const kv = part.split("=");
      if (kv.length === 2) {
        const k = kv[0].trim();
        const v = kv[1].trim();
        if (k && v) {
          const numV = Number(v);
          set[k] = isNaN(numV) ? v : numV;
          if (!label) label = `${k}=${v}`;
        }
      }
    }
    if (Object.keys(set).length > 0) {
      set["__name__"] = line;
      paramSets.push(set);
    }
  }
  
  if (paramSets.length === 0) { alert("未识别到有效的参数组合"); return; }
  
  _paramTestState.running = true;
  _paramTestState.results = [];
  _paramTestState.abortController = new AbortController();
  
  if (btn) {
    btn.textContent = "停止测试";
    btn.classList.add("bg-red-600", "hover:bg-red-700");
    btn.classList.remove("btn-primary");
  }
  if (exportBtn) exportBtn.disabled = true;
  if (tbody) tbody.innerHTML = "";
  if (status) status.textContent = "准备开始...";
  
  const baseCfg = getStrategyConfigFromUI();
  const dataDir = val("scan-data-dir", "").trim(); 
  if (!dataDir) {
    alert("请在选股/回测界面设置数据目录");
    _paramTestState.running = false;
    resetBtn();
    return;
  }
  
  const req = {
    data_dir: dataDir,
    symbols: symbols,
    param_sets: paramSets,
    ...baseCfg
  };
  
  try {
    const resp = await fetch("/api/param_batch_test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
      signal: _paramTestState.abortController.signal
    });
    
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || "启动失败");
    }
    
    const reader = resp.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buf = "";
    
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop() || "";
      
      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          const msg = JSON.parse(line);
          handleBatchMsg(msg, status, tbody);
        } catch (e) {
          console.error("Parse error", e);
        }
      }
    }
    
  } catch (e) {
    if (e.name !== "AbortError") {
      alert("测试出错: " + e.message);
      if (status) status.textContent = "出错: " + e.message;
    } else {
      if (status) status.textContent = "已停止";
    }
  } finally {
    _paramTestState.running = false;
    resetBtn();
    if (exportBtn) exportBtn.disabled = false;
  }
  
  function resetBtn() {
    if (btn) {
      btn.textContent = "开始批量测试";
      btn.classList.remove("bg-red-600", "hover:bg-red-700");
      btn.classList.add("btn-primary");
    }
  }
}

function handleBatchMsg(msg, status, tbody) {
  if (msg.type === "start") {
    if (status) status.textContent = `开始测试: 共 ${msg.total} 个任务`;
  } else if (msg.type === "heartbeat") {
    if (status) status.textContent = `进行中: ${msg.progress}`;
  } else if (msg.type === "result") {
    const d = msg.data;
    if (!d) return;
    
    const row = {
      symbol: d.symbol,
      combo_label: msg.combo_label,
      trades: d.trades,
      win_rate: d.win_rate,
      total_return: d.total_return,
      max_drawdown: d.max_drawdown,
      combo: msg.combo
    };
    
    _paramTestState.results.push(row);
    renderBatchRow(tbody, row);
  }
}

function renderBatchRow(tbody, r) {
  if (!tbody) return;
  const tr = document.createElement("tr");
  tr.className = "hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors";
  
  const fmtPct = (v) => {
    if (v == null || !Number.isFinite(Number(v))) return "-";
    const n = Number(v);
    const cls = n > 0 ? "text-red-600 dark:text-red-400" : (n < 0 ? "text-green-600 dark:text-green-400" : "text-slate-500");
    return `<span class="${cls}">${(n * 100).toFixed(2)}%</span>`;
  };
  
  tr.innerHTML = `
    <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-700 dark:text-slate-300 font-medium">${r.symbol || "-"}</td>
    <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-500 dark:text-slate-400 truncate max-w-[150px]" title="${_escapeHtml(r.combo_label)}">${_escapeHtml(r.combo_label)}</td>
    <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right text-slate-600 dark:text-slate-400">${r.trades || 0}</td>
    <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono">${fmtPct(r.win_rate)}</td>
    <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono font-bold">${fmtPct(r.total_return)}</td>
    <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono text-green-600 dark:text-green-400">${fmtPct(r.max_drawdown)}</td>
  `;
  tbody.appendChild(tr);
}

function exportParamTestExcel() {
  const results = _paramTestState.results;
  if (!results || !results.length) {
    alert("暂无结果可导出");
    return;
  }
  
  const headers = ["股票代码", "参数组合", "交易次数", "胜率", "总收益", "最大回撤"];
  const rows = results.map(r => [
    r.symbol,
    r.combo_label,
    r.trades,
    (r.win_rate * 100).toFixed(2) + "%",
    (r.total_return * 100).toFixed(2) + "%",
    (r.max_drawdown * 100).toFixed(2) + "%"
  ]);
  
  const csvContent = [
    headers.join(","),
    ...rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(","))
  ].join("\n");
  
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const link = document.createElement("a");
  const url = URL.createObjectURL(blob);
  link.setAttribute("href", url);
  link.setAttribute("download", `batch_test_results_${new Date().toISOString().slice(0,10)}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

/* -------------------------------------------------------------------------- */
/*                          Parameter Help Modal                              */
/* -------------------------------------------------------------------------- */

function showParamHelpModal() {
  let modal = document.getElementById("param-help-modal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "param-help-modal";
    modal.className = "fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm hidden";
    modal.innerHTML = `
      <div class="bg-white dark:bg-slate-800 rounded-xl shadow-2xl w-full max-w-4xl max-h-[85vh] flex flex-col overflow-hidden border border-slate-200 dark:border-slate-700">
        <div class="px-6 py-4 border-b border-slate-100 dark:border-slate-700 flex justify-between items-center bg-slate-50 dark:bg-slate-800/50">
          <h3 class="text-lg font-bold text-slate-800 dark:text-slate-100">参数详细说明</h3>
          <button onclick="document.getElementById('param-help-modal').classList.add('hidden')" class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </div>
        <div class="flex-1 overflow-auto p-6 space-y-6" id="param-help-content"></div>
        <div class="px-6 py-4 border-t border-slate-100 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 text-right">
          <button onclick="document.getElementById('param-help-modal').classList.add('hidden')" class="btn-primary px-6 py-2">关闭</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
    
    // Populate content
    const container = document.getElementById("param-help-content");
    for (const [key, def] of Object.entries(PARAM_DEFINITIONS)) {
      const section = document.createElement("div");
      section.className = "border-b border-slate-100 dark:border-slate-700 pb-6 last:border-0";
      section.innerHTML = `
        <div class="flex items-center gap-2 mb-2">
          <h4 class="text-base font-bold text-blue-600 dark:text-blue-400">${def.name}</h4>
          <span class="text-xs font-mono text-slate-400 dark:text-slate-500 bg-slate-100 dark:bg-slate-700/50 px-2 py-0.5 rounded">${key}</span>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs mb-3">
          <div><span class="font-bold text-slate-500">类型:</span> ${def.type}</div>
          <div><span class="font-bold text-slate-500">默认:</span> ${def.default}</div>
          <div><span class="font-bold text-slate-500">范围:</span> ${def.range}</div>
          <div><span class="font-bold text-slate-500">单位:</span> ${def.unit}</div>
        </div>
        <div class="space-y-2 text-sm text-slate-600 dark:text-slate-300">
          <p><span class="font-bold">说明:</span> ${def.desc}</p>
          <p><span class="font-bold">逻辑:</span> ${def.logic}</p>
          <p><span class="font-bold">示例:</span> ${def.example}</p>
          <div class="bg-amber-50 dark:bg-amber-900/10 p-2 rounded border border-amber-100 dark:border-amber-900/20 text-xs">
            <span class="font-bold text-amber-600 dark:text-amber-500">💡 优化建议:</span> ${def.suggestion}
          </div>
        </div>
      `;
      container.appendChild(section);
    }
  }
  
  document.getElementById("param-help-modal").classList.remove("hidden");
}

/* -------------------------------------------------------------------------- */
/*                           Core Logic (Merged)                              */
/* -------------------------------------------------------------------------- */

function _autosaveRead(el) {
  const k = `autosave_v1_${el.id}`;
  return localStorage.getItem(k);
}
function _autosaveWrite(el) {
  const k = `autosave_v1_${el.id}`;
  localStorage.setItem(k, el.value);
}
function _autosaveApply(el, val) {
  el.value = val;
}
function initAutoSaveInputs() {
  const nodes = Array.from(document.querySelectorAll("input[id], textarea[id], select[id]"));
  for (const el of nodes) {
    if (!el || !el.id) continue;
    if (el.id.startsWith("pool-")) continue;
    if (el.id.startsWith("preset-")) continue;
    
    const raw = _autosaveRead(el);
    if (raw != null) _autosaveApply(el, raw);

    const h = () => {
      if (_autosaveDebounce) clearTimeout(_autosaveDebounce);
      _autosaveDebounce = setTimeout(() => _autosaveWrite(el), 500);
    };
    el.addEventListener("input", h);
    el.addEventListener("change", h);
  }
}

function initNav() {
  const navs = document.querySelectorAll("nav button[data-target]");
  navs.forEach(btn => {
    btn.addEventListener("click", () => {
      const t = btn.dataset.target;
      setActiveView(t);
    });
  });
}

function setActiveView(id) {
  document.querySelectorAll("section[id^='view-']").forEach(el => el.classList.add("hidden"));
  const t = document.getElementById(`view-${id}`);
  if (t) t.classList.remove("hidden");
  
  document.querySelectorAll("nav button").forEach(b => {
    const viewId = b.dataset.view || b.dataset.target;
    if (viewId === id) {
      b.classList.add("bg-blue-50", "text-blue-600", "dark:bg-blue-900/20", "dark:text-blue-400");
      b.classList.remove("text-slate-500", "dark:text-slate-400", "hover:bg-slate-50");
    } else {
      b.classList.remove("bg-blue-50", "text-blue-600", "dark:bg-blue-900/20", "dark:text-blue-400");
      b.classList.add("text-slate-500", "dark:text-slate-400", "hover:bg-slate-50");
    }
  });
}

let _cfgBindings = null;

function _extractConfigKey(labelText) {
  const m = String(labelText || "").match(/\(([^)]+)\)/);
  return m ? m[1].trim() : null;
}

function _collectConfigBindings() {
  const bindings = new Map();
  const root = document.getElementById("view-config") || document;
  const labels = Array.from(root.querySelectorAll("label"));
  for (const lb of labels) {
    const key = _extractConfigKey(lb.textContent);
    if (!key) continue;
    let el = lb.querySelector("input, select, textarea");
    if (!el && lb.parentElement) el = lb.parentElement.querySelector("input, select, textarea");
    if (!el) continue;
    bindings.set(key, el);
  }
  return bindings;
}

function readConfigFromUI() {
  if (!_cfgBindings) _cfgBindings = _collectConfigBindings();
  const cfg = {};
  for (const [key, el] of _cfgBindings.entries()) {
    if (!el) continue;
    if (el.type === "checkbox") {
      cfg[key] = !!el.checked;
      continue;
    }
    const raw = (el.value ?? "").toString();
    if (el.type === "number") {
      if (raw.trim() === "") continue;
      const n = Number(raw);
      if (Number.isFinite(n)) cfg[key] = n;
      continue;
    }
    cfg[key] = raw;
  }
  return cfg;
}

function applyConfigToUI(cfg) {
  if (!_cfgBindings) _cfgBindings = _collectConfigBindings();
  const data = (cfg && typeof cfg === "object") ? cfg : {};
  for (const [key, el] of _cfgBindings.entries()) {
    if (!el) continue;
    if (!(key in data)) continue;
    const v = data[key];
    if (el.type === "checkbox") {
      el.checked = !!v;
      el.dispatchEvent(new Event("change"));
      continue;
    }
    el.value = v == null ? "" : String(v);
    el.dispatchEvent(new Event("input"));
    el.dispatchEvent(new Event("change"));
  }
}

function _setPresetStatus(msg, ok = true) {
  const el = document.getElementById("preset-status");
  if (!el) return;
  el.textContent = msg || "";
  el.className = ok
    ? "text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-900/20 dark:text-emerald-400 dark:border-emerald-900/40"
    : "text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-rose-50 text-rose-700 border border-rose-200 dark:bg-rose-900/20 dark:text-rose-400 dark:border-rose-900/40";
}

function _renderActivePreset(active) {
  const tag = document.getElementById("active-preset-tag");
  const nameEl = document.getElementById("active-preset-name");
  if (!tag || !nameEl) return;
  if (active) {
    nameEl.textContent = active;
    tag.classList.remove("hidden");
  } else {
    nameEl.textContent = "";
    tag.classList.add("hidden");
  }
}

async function refreshPresets(selectedName = null) {
  const sel = document.getElementById("preset-select");
  if (!sel) return;
  try {
    const resp = await fetch("/api/presets");
    const data = await resp.json().catch(() => ({}));
    const presets = Array.isArray(data.presets) ? data.presets : [];
    const active = (data.active || "").toString();
    sel.innerHTML = "";
    const opt0 = document.createElement("option");
    opt0.value = "";
    opt0.textContent = presets.length ? "请选择" : "暂无预设";
    sel.appendChild(opt0);
    for (const name of presets) {
      const opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name;
      sel.appendChild(opt);
    }
    const target = (selectedName || active || "").toString();
    if (target) sel.value = target;
    _renderActivePreset(active);
    const nameInput = document.getElementById("preset-name");
    if (nameInput && sel.value && !nameInput.value.trim()) nameInput.value = sel.value;
  } catch (e) {
    _setPresetStatus(`加载失败: ${toMsg(e)}`, false);
  }
}

function initPresets() {
  const sel = document.getElementById("preset-select");
  const nameInput = document.getElementById("preset-name");
  const btnSave = document.getElementById("preset-save");
  const btnApply = document.getElementById("preset-apply");
  const btnDelete = document.getElementById("preset-delete");
  if (!sel || !nameInput || !btnSave || !btnApply || !btnDelete) return;

  sel.addEventListener("change", () => {
    if (sel.value) nameInput.value = sel.value;
  });

  btnSave.addEventListener("click", async () => {
    const name = (nameInput.value || sel.value || "").trim();
    if (!name) return _setPresetStatus("名称不能为空", false);
    const cfg = readConfigFromUI();
    try {
      const resp = await fetch("/api/presets/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, cfg })
      });
      const data = await resp.json().catch(() => ({}));
      if (!data.ok) return _setPresetStatus(data.msg || "保存失败", false);
      _setPresetStatus(data.msg || "已保存", true);
      await refreshPresets(name);
      sel.value = name;
      nameInput.value = name;
    } catch (e) {
      _setPresetStatus(`保存失败: ${toMsg(e)}`, false);
    }
  });

  btnApply.addEventListener("click", async () => {
    const name = (sel.value || nameInput.value || "").trim();
    if (!name) return _setPresetStatus("请选择或输入名称", false);
    try {
      const resp = await fetch("/api/presets/load", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name })
      });
      const data = await resp.json().catch(() => ({}));
      if (!data.ok) return _setPresetStatus(data.msg || "应用失败", false);
      applyConfigToUI(data.config || {});
      _setPresetStatus(data.msg || "已应用", true);
      await refreshPresets(name);
    } catch (e) {
      _setPresetStatus(`应用失败: ${toMsg(e)}`, false);
    }
  });

  btnDelete.addEventListener("click", async () => {
    const name = (sel.value || "").trim();
    if (!name) return _setPresetStatus("请选择要删除的预设", false);
    try {
      const resp = await fetch("/api/presets/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name })
      });
      const data = await resp.json().catch(() => ({}));
      if (!data.ok) return _setPresetStatus(data.msg || "删除失败", false);
      _setPresetStatus(data.msg || "已删除", true);
      nameInput.value = "";
      await refreshPresets("");
    } catch (e) {
      _setPresetStatus(`删除失败: ${toMsg(e)}`, false);
    }
  });

  refreshPresets();
}

let _debugState = {
  lastResult: null,
  selectedTradeIdx: -1
};

function _fmtPct(v) {
  if (v == null || !Number.isFinite(Number(v))) return "-";
  return (Number(v) * 100).toFixed(2) + "%";
}

function _fmtNum(v, digits = 2) {
  if (v == null || !Number.isFinite(Number(v))) return "-";
  return Number(v).toFixed(digits);
}

function _renderDebugOverview(overview) {
  const root = document.getElementById("debug-overview");
  if (!root) return;
  const o = (overview && typeof overview === "object") ? overview : {};
  const items = [
    ["交易数", o.total_trades],
    ["胜率", _fmtPct(o.win_rate)],
    ["总收益", _fmtPct(o.total_return)],
    ["年化", _fmtPct(o.annual_return)],
    ["最大回撤", _fmtPct(o.max_drawdown)],
    ["夏普", _fmtNum(o.sharpe_ratio, 2)],
    ["平均持仓", _fmtNum(o.avg_holding_days, 1)],
    ["ProfitFactor", _fmtNum(o.profit_factor, 2)]
  ];
  root.innerHTML = "";
  for (const [k, v] of items) {
    const card = document.createElement("div");
    card.className = "border border-slate-100 dark:border-slate-800 rounded-lg p-2 bg-slate-50/40 dark:bg-slate-900/20";
    card.innerHTML = `
      <div class="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider">${_escapeHtml(k)}</div>
      <div class="text-sm font-bold text-slate-800 dark:text-slate-100 mt-1">${_escapeHtml(v)}</div>
    `;
    root.appendChild(card);
  }
}

function _pickSignalDateForTrade(trade, dailyData) {
  const entry = (trade && (trade.entry_date || trade.entry_dt)) ? String(trade.entry_date || trade.entry_dt) : "";
  const entryD = entry ? new Date(entry) : null;
  if (!entryD || Number.isNaN(entryD.getTime())) return entry;
  let best = null;
  for (const it of (dailyData || [])) {
    if (!it || !it.date) continue;
    if (Number(it.final_signal || 0) !== 1) continue;
    const d = new Date(String(it.date));
    if (Number.isNaN(d.getTime())) continue;
    if (d.getTime() >= entryD.getTime()) continue;
    if (!best || d.getTime() > best.getTime()) best = d;
  }
  if (best) return best.toISOString().slice(0, 10);
  return entry;
}

function _renderDebugTrace(trace) {
  const wrap = document.getElementById("debug-trade-trace-wrap");
  const tbody = document.getElementById("debug-trace");
  if (!wrap || !tbody) return;
  const show = boolv("dbg-show-trace", true);
  if (!show) {
    wrap.classList.add("hidden");
    return;
  }
  wrap.classList.remove("hidden");
  tbody.innerHTML = "";
  if (!Array.isArray(trace) || trace.length === 0) return;
  for (const step of trace) {
    if (!step || typeof step !== "object") continue;
    const tr = document.createElement("tr");
    const passed = step.passed;
    const passedText = passed === true ? "通过" : (passed === false ? "失败" : "-");
    const passedCls = passed === true ? "text-emerald-600" : (passed === false ? "text-rose-600" : "text-slate-500");
    tr.innerHTML = `
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 font-bold text-slate-700 dark:text-slate-200">${_escapeHtml(step.step ?? "-")}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-600 dark:text-slate-300">${_escapeHtml(step.check ?? step.condition ?? "-")}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-600 dark:text-slate-300">${_escapeHtml(step.threshold ?? "-")}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-600 dark:text-slate-300">${_escapeHtml(step.actual ?? step.value ?? "-")}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 font-bold ${passedCls}">${_escapeHtml(passedText)}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-600 dark:text-slate-300">${_escapeHtml(step.reason ?? step.fail_reason ?? step.message ?? "-")}</td>
    `;
    tbody.appendChild(tr);
  }
}

function _setDebugFeatureTab(tab) {
  const btns = Array.from(document.querySelectorAll(".dbg-feature-tab-btn"));
  const panels = Array.from(document.querySelectorAll(".dbg-feature-tab-content"));
  for (const b of btns) {
    const active = b.dataset.tab === tab;
    if (active) {
      b.className = "dbg-feature-tab-btn px-3 py-1 rounded-lg text-xs font-bold bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-300";
    } else {
      b.className = "dbg-feature-tab-btn px-3 py-1 rounded-lg text-xs font-bold bg-slate-100 dark:bg-slate-800/60 text-slate-700 dark:text-slate-200";
    }
  }
  for (const p of panels) {
    if (!p || !p.id) continue;
    if (p.id === `dbg-feature-tab-${tab}`) p.classList.remove("hidden");
    else p.classList.add("hidden");
  }
}

function _renderDebugFeatureSnapshot(snapshot) {
  const core = document.getElementById("dbg-feature-tab-core");
  const channel = document.getElementById("dbg-feature-tab-channel");
  const decision = document.getElementById("dbg-feature-tab-decision");
  if (!core || !channel || !decision) return;
  const s = (snapshot && typeof snapshot === "object") ? snapshot : {};

  const coreKeys = [
    "transaction_id",
    "stock_code",
    "entry_date",
    "exit_date",
    "entry_price",
    "exit_price",
    "holding_days",
    "exit_reason",
    "return_rate",
    "min_profit_value",
    "min_profit_threshold",
    "profit_pass",
    "min_rr_value",
    "min_rr_threshold",
    "rr_pass"
  ];
  const channelKeys = [
    "buy_touch_eps",
    "slope_value",
    "slope_min",
    "slope_pass",
    "height_value",
    "height_min",
    "height_pass",
    "room_value",
    "room_min",
    "room_pass",
    "volume_ratio",
    "vol_shrink_min",
    "vol_shrink_max",
    "volume_pass",
    "vol_ratio",
    "vol_threshold",
    "vol_pass",
    "trend_pass",
    "cooling_pass",
    "pivot_confirm_days",
    "pivot_pass"
  ];

  const pick = (keys) => {
    const out = {};
    for (const k of keys) if (k in s) out[k] = s[k];
    return out;
  };

  core.textContent = JSON.stringify(pick(coreKeys), null, 2);
  channel.textContent = JSON.stringify(pick(channelKeys), null, 2);
  decision.classList.add("hidden");
  _setDebugFeatureTab("core");
}

function _renderDebugParamsPanel(params) {
  const sum = document.getElementById("debug-param-panel-summary");
  const groups = document.getElementById("debug-param-panel-groups");
  if (!sum || !groups) return;
  const p = (params && typeof params === "object") ? params : {};
  const keys = Object.keys(p).sort();
  sum.textContent = keys.length ? `共 ${keys.length} 个参数` : "未返回参数";
  groups.innerHTML = "";
  const box = document.createElement("div");
  box.className = "border border-slate-100 dark:border-slate-800 rounded-lg p-2 bg-slate-50/40 dark:bg-slate-900/20";
  const lines = keys.map(k => `${k}: ${p[k]}`).join("\n");
  box.innerHTML = `<pre class="text-[10px] whitespace-pre-wrap text-slate-700 dark:text-slate-200">${_escapeHtml(lines)}</pre>`;
  groups.appendChild(box);
}

function _renderDebugTrades(trades, dailyData) {
  const tbody = document.getElementById("debug-trades");
  if (!tbody) return;
  tbody.innerHTML = "";
  const list = Array.isArray(trades) ? trades : [];
  for (let i = 0; i < list.length; i++) {
    const t = list[i] || {};
    const tr = document.createElement("tr");
    tr.className = "hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors cursor-pointer";
    const ret = Number(t.return_rate ?? t.return_pct);
    const retCls = Number.isFinite(ret) ? (ret > 0 ? "text-red-600" : (ret < 0 ? "text-green-600" : "text-slate-500")) : "text-slate-500";
    tr.innerHTML = `
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50">
        <input type="radio" name="dbg-trade-pick" ${i === 0 ? "checked" : ""} />
      </td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-600 dark:text-slate-300">${i + 1}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-700 dark:text-slate-200 font-mono">${_escapeHtml(String(t.entry_date || t.entry_dt || "-").slice(0, 10))}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-700 dark:text-slate-200 font-mono">${_escapeHtml(String(t.exit_date || t.exit_dt || "-").slice(0, 10))}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-600 dark:text-slate-300 font-mono">${_escapeHtml(_fmtNum(t.entry_price, 2))}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-600 dark:text-slate-300 font-mono">${_escapeHtml(_fmtNum(t.exit_price, 2))}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 font-mono font-bold ${retCls}">${_escapeHtml(_fmtPct(ret))}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-600 dark:text-slate-300 font-mono">${_escapeHtml(_fmtNum(t.r_multiple, 2))}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-600 dark:text-slate-300">${_escapeHtml(String(t.holding_days ?? "-"))}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-600 dark:text-slate-300">${_escapeHtml(t.exit_reason ?? "-")}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50">
        <button class="text-blue-600 hover:text-blue-800 underline text-[10px]">查看</button>
      </td>
    `;
    tr.addEventListener("click", (ev) => {
      const tag = (ev.target && ev.target.tagName) ? ev.target.tagName.toLowerCase() : "";
      if (tag !== "input") {
        const radio = tr.querySelector("input[type='radio']");
        if (radio) radio.checked = true;
      }
      _debugState.selectedTradeIdx = i;
      const snap = t.feature_snapshot || {};
      _renderDebugFeatureSnapshot(snap);
      const sigDate = _pickSignalDateForTrade(t, dailyData);
      const day = (dailyData || []).find(x => x && String(x.date || "").startsWith(sigDate));
      _renderDebugTrace(day ? day.trace : []);
    });
    tbody.appendChild(tr);
  }
  if (list.length) {
    _debugState.selectedTradeIdx = 0;
    const first = list[0] || {};
    _renderDebugFeatureSnapshot(first.feature_snapshot || {});
    const sigDate = _pickSignalDateForTrade(first, dailyData);
    const day = (dailyData || []).find(x => x && String(x.date || "").startsWith(sigDate));
    _renderDebugTrace(day ? day.trace : []);
  } else {
    _debugState.selectedTradeIdx = -1;
    _renderDebugFeatureSnapshot({});
    _renderDebugTrace([]);
  }
}

async function runDebugAnalyze() {
  const btn = document.getElementById("debug-run-btn");
  const symbol = val("dbg-symbol", "").trim();
  const dataDir = val("dbg-data-dir", "").trim();
  if (!symbol) return alert("请输入股票代码");
  if (!dataDir) return alert("请输入数据目录");

  const beg = normalizeYmOrYmd(val("dbg-beg", ""), "beg");
  const end = normalizeYmOrYmd(val("dbg-end", ""), "end");
  const indexData = val("dbg-index-data", "").trim();
  const indexSymbol = val("dbg-index-symbol", "000300.SH").trim();

  if (btn) {
    btn.disabled = true;
    btn.textContent = "分析中...";
  }

  try {
    const config = readConfigFromUI();
    const req = {
      symbol,
      data_dir: dataDir,
      index_data: indexData || null,
      index_symbol: indexSymbol || null,
      beg,
      end,
      config
    };
    const resp = await fetch("/api/debug/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req)
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || "请求失败");
    }
    const data = await resp.json();
    _debugState.lastResult = data;
    if (!data || data.status !== "success") {
      throw new Error((data && (data.message || data.msg)) || "分析失败");
    }
    _renderDebugOverview(data.overview || {});
    _renderDebugParamsPanel(data.params || {});
    _renderDebugTrades(data.trades || [], data.daily_data || []);
  } catch (e) {
    alert("分析失败: " + toMsg(e));
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "开始分析";
    }
  }
}

function initDebugUI() {
  const tabBtns = Array.from(document.querySelectorAll(".dbg-feature-tab-btn"));
  for (const b of tabBtns) {
    b.addEventListener("click", () => {
      const tab = b.dataset.tab;
      if (tab) _setDebugFeatureTab(tab);
    });
  }
}

function normalizeYmOrYmd(input, kind) {
  const s = (input || "").trim();
  if (!s) return null;
  const m1 = s.match(/^\d{4}-\d{2}-\d{2}$/);
  if (m1) return s;
  const m2 = s.match(/^(\d{4})-(\d{2})$/);
  if (m2) {
    if (kind === "beg") return `${m2[1]}-${m2[2]}-01`;
    const y = Number(m2[1]);
    const mon = Number(m2[2]);
    const lastDay = new Date(y, mon, 0).getDate();
    return `${m2[1]}-${m2[2]}-${lastDay}`;
  }
  return null;
}

// ---------------------- Backtest Logic ----------------------

function renderBacktestRowToTbody(tbody, d) {
  if (!tbody || !d) return;
  const tr = document.createElement("tr");
  tr.className = "hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors";
  
  const env = d.env || {};
  const stats = d.stats || {};
  const isRejected = !!d.error || (d.reasons && d.reasons.length > 0);
  
  // Format helpers
  const fmtPct = (v) => {
    if (v == null) return "-";
    const n = Number(v);
    const cls = n > 0 ? "text-red-600" : (n < 0 ? "text-green-600" : "text-slate-500");
    return `<span class="${cls}">${(n * 100).toFixed(2)}%</span>`;
  };
  
  // Prepare Rejection Text
  let rejText = "-";
  let rejBtn = "";
  
  if (isRejected) {
    const reasons = d.reasons || [];
    const count = reasons.length;
    // Example: Volume condition failed: 195 (低于下限:120, 高于上限:75)
    // We construct a summary string
    const map = {};
    reasons.forEach(r => {
      const k = r.filter_type || "Unknown";
      if (!map[k]) map[k] = 0;
      map[k]++;
    });
    const summary = Object.entries(map).map(([k, v]) => `${k}: ${v}`).join(", ");
    rejText = `<span class="text-slate-400 text-[10px]">${summary || "Rejected"}</span>`;
    
    // Add "View Details" button
    rejBtn = `<button onclick="showRejectionDetails('${d.symbol}')" class="text-blue-600 hover:text-blue-800 underline text-[10px] ml-2">查看详情</button>`;
  }

  tr.innerHTML = `
    <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-700 font-medium">${d.symbol}</td>
    <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right text-slate-600">${stats.trades || 0}</td>
    <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono">${fmtPct(stats.win_rate)}</td>
    <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono font-bold">${fmtPct(stats.total_return)}</td>
    <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono text-green-600">${fmtPct(stats.max_drawdown)}</td>
    <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-xs">
      ${rejText} ${rejBtn}
    </td>
  `;
  tbody.appendChild(tr);
}

async function fetchBacktestDetailForSymbol(symbol) {
  const dataDir = val("bt-data-dir", "").trim();
  const beg = normalizeYmOrYmd(val("bt-beg", ""), "beg");
  const end = normalizeYmOrYmd(val("bt-end", ""), "end");
  
  const req = {
    symbol,
    data_dir: dataDir,
    beg,
    end,
    ...getStrategyConfigFromUI()
  };
  
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(req)) {
    if (v != null) params.append(k, v);
  }
  
  const resp = await fetch(`/api/backtest/detail?${params.toString()}`);
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || "获取详情失败");
  }
  return await resp.json();
}

async function runChannelHFBacktest(symbolsOverride = null) {
  const btn = document.getElementById("bt-btn");
  const status = document.getElementById("bt-status");
  const tbody = document.getElementById("bt-results");
  if (tbody) tbody.innerHTML = "";
  const logsEl = document.getElementById("run-logs");
  if (logsEl) logsEl.textContent = "";

  const dataDir = val("bt-data-dir", "").trim();
  if (!dataDir) {
    if (status) status.textContent = "请输入股票文件目录地址";
    return;
  }

  if (btn) btn.disabled = true;
  if (status) status.textContent = "回测中...";

  try {
    const req = {
      data_dir: dataDir,
      symbols: parseSymbolsInput(val("bt-symbols", "")),
      beg: normalizeYmOrYmd(val("bt-beg", ""), "beg"),
      end: normalizeYmOrYmd(val("bt-end", ""), "end"),
      ...getStrategyConfigFromUI()
    };
    
    if (symbolsOverride) req.symbols = symbolsOverride;

    const resp = await fetch("/api/backtest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req)
    });

    if (!resp.ok) throw new Error("启动失败");

    const reader = resp.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buf = "";
    let total = 0, done = 0;

    while (true) {
      const { done: streamDone, value } = await reader.read();
      if (streamDone) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop() || "";

      for (const line of lines) {
        if (!line.trim()) continue;
        const msg = JSON.parse(line);

        if (msg.type === "start") {
          total = msg.total;
          if (status) status.textContent = `回测中 0/${total}`;
        }
        if (msg.type === "result") {
          done++;
          renderBacktestRowToTbody(tbody, msg.data);
          if (status) status.textContent = `回测中 ${done}/${total}`;
        }
        if (msg.type === "end") {
          if (status) status.textContent = "完成";
        }
        if (msg.type === "error") {
          appendRunLog(`Error: ${msg.message}`);
        }
      }
    }
  } catch (e) {
    if (status) status.textContent = `Error: ${e.message}`;
  } finally {
    if (btn) btn.disabled = false;
  }
}

// ---------------------- Initialization ----------------------

function initApp() {
  console.log("App initializing... v20250108_merged");
  initNav();
  initAutoSaveInputs();
  initPresets();
  initDebugUI();
  initConfigParamHelpBinding();
  _smartLoadFileList();
  _poolInitUI();
  
  // Bind Batch Test buttons
  const btnExp = document.getElementById("pt-export-btn");
  if(btnExp) btnExp.onclick = exportParamTestExcel;
  const btnGrid = document.getElementById("pt-grid-gen-btn");
  if(btnGrid) btnGrid.onclick = generateParamGrid;
  const btnRun = document.getElementById("pt-run-btn");
  if(btnRun) btnRun.onclick = runParamBatchTest;
  
  // Bind Backtest button
  const btBtn = document.getElementById("bt-btn");
  if (btBtn) btBtn.onclick = () => runChannelHFBacktest();
  
  // Bind Parameter Help
  window.showParamHelpModal = showParamHelpModal;
  window.runChannelHFScan = runChannelHFScan;
  window.cancelChannelHFScan = cancelChannelHFScan;
  window.runDataSyncOnce = runDataSyncOnce;
  window.stopDataSyncStream = stopDataSyncStream;
  window.setActiveView = setActiveView;
  window.runSelector = runSelector;
  window.poolImportFromBacktest = poolImportFromBacktest;
  window.runSmartAsk = runSmartAsk;
  
  setActiveView("scan"); // Default view
}

document.addEventListener("DOMContentLoaded", initApp);
