
/* -------------------------------------------------------------------------- */
/*                                 Constants                                  */
/* -------------------------------------------------------------------------- */

const PARAM_DEFINITIONS = {
  "channel_period": {
    name: "通道周期",
    type: "整数 (Days)",
    default: "20",
    range: "10 - 120",
    unit: "天",
    desc: "计算通道（中轨/上下轨）的回看周期。",
    logic: "周期越大越平滑、信号越少；周期越小越敏感、信号越多。",
    example: "20 / 30 / 60",
    suggestion: "短线更小；中线更大。"
  },
  "buy_touch_eps": {
    name: "买入容差",
    type: "数值 (Ratio)",
    default: "0.005",
    range: "0.0 - 0.05",
    unit: "比例",
    desc: "触及下轨买入的容差，用于允许略高于下轨的触发。",
    logic: "触发价 ≈ 下轨 * (1 + buy_touch_eps)。",
    example: "0.005 (0.5%)",
    suggestion: "调大: 更容易触发；调小: 更贴近下轨。"
  },
  "sell_trigger_eps": {
    name: "卖出触发",
    type: "数值 (Ratio)",
    default: "0.005",
    range: "0.0 - 0.05",
    unit: "比例",
    desc: "卖出触发的容差，用于提高/降低卖出目标价。",
    logic: "与 sell_target_mode 配合，按中轨/上轨计算目标价并加减该比例。",
    example: "0.005 (0.5%)",
    suggestion: "调大: 目标更远；调小: 更容易止盈/止损。"
  },
  "sell_target_mode": {
    name: "卖出目标模式",
    type: "枚举",
    default: "mid_up",
    range: "mid_up / mid_down / upper_down",
    unit: "",
    desc: "选择用哪条线（中轨/上轨）来计算卖出目标价。",
    logic: "mid_up: 中轨上浮；mid_down: 中轨下浮；upper_down: 上轨下浮。",
    example: "mid_up",
    suggestion: "中轨上浮更稳健；上轨下浮更激进。"
  },
  "channel_break_eps": {
    name: "破位阈值",
    type: "数值 (Ratio)",
    default: "0.02",
    range: "0.0 - 0.10",
    unit: "比例",
    desc: "判断通道破位/止损的阈值。",
    logic: "通常以价格相对通道线的偏离幅度进行判定。",
    example: "0.02 (2%)",
    suggestion: "调大: 更宽松；调小: 更敏感。"
  },
  "entry_fill_eps": {
    name: "买入滑点",
    type: "数值 (Ratio)",
    default: "0.002",
    range: "0.0 - 0.02",
    unit: "比例",
    desc: "模拟买入成交价偏离的滑点。",
    logic: "成交价≈信号价*(1+entry_fill_eps)。",
    example: "0.002 (0.2%)",
    suggestion: "越大越保守。"
  },
  "exit_fill_eps": {
    name: "卖出滑点",
    type: "数值 (Ratio)",
    default: "0.002",
    range: "0.0 - 0.02",
    unit: "比例",
    desc: "模拟卖出成交价偏离的滑点。",
    logic: "成交价≈信号价*(1-exit_fill_eps)。",
    example: "0.002 (0.2%)",
    suggestion: "越大越保守。"
  },
  "stop_loss_mul": {
    name: "止损倍数",
    type: "数值 (Ratio)",
    default: "0.97",
    range: "0.80 - 1.00",
    unit: "倍数",
    desc: "止损价相对买入价的倍率。",
    logic: "止损价≈买入价*stop_loss_mul。",
    example: "0.97 (约-3%)",
    suggestion: "调小: 止损更紧；调大: 止损更松。"
  },
  "stop_loss_on_close": {
    name: "止损按收盘",
    type: "布尔 (Yes/No)",
    default: "true",
    range: "true / false",
    unit: "",
    desc: "是否使用收盘价作为止损判定与成交基准。",
    logic: "启用后，止损更贴近收盘执行逻辑。",
    example: "true",
    suggestion: "回测一致性建议启用。"
  },
  "stop_loss_panic_eps": {
    name: "恐慌阈值",
    type: "数值 (Ratio)",
    default: "0.02",
    range: "0.0 - 0.20",
    unit: "比例",
    desc: "极端行情下的快速止损阈值。",
    logic: "当满足更极端的破位条件时触发更快退出。",
    example: "0.02 (2%)",
    suggestion: "调大: 更难触发；调小: 更容易触发。"
  },
  "max_holding_days": {
    name: "最大持仓天数",
    type: "整数 (Days)",
    default: "20",
    range: "1 - 200",
    unit: "天",
    desc: "持仓超过该天数后触发退出逻辑。",
    logic: "用于限制资金占用与降低持仓拖累。",
    example: "20",
    suggestion: "周期策略可适当增大。"
  },
  "cooling_period": {
    name: "冷却期",
    type: "整数 (Days)",
    default: "5",
    range: "0 - 60",
    unit: "天",
    desc: "卖出后等待若干天才允许再次买入。",
    logic: "减少频繁进出与噪声交易。",
    example: "5",
    suggestion: "震荡市可适当调大。"
  },
  "slope_abs_max": {
    name: "斜率上限",
    type: "数值 (Slope)",
    default: "0.01",
    range: "0.0 - 0.10",
    unit: "归一化",
    desc: "限制通道中轨斜率的绝对值上限。",
    logic: "abs(slope_norm) ≤ slope_abs_max。",
    example: "0.01",
    suggestion: "调小: 更严格过滤趋势过强；调大: 更宽松。"
  },
  "min_slope_norm": {
    name: "归一斜率下限",
    type: "数值 (Slope)",
    default: "-1.0",
    range: "-1.0 - 0.0",
    unit: "归一化",
    desc: "限制中轨斜率的下限（过于下行的通道不参与）。",
    logic: "slope_norm ≥ min_slope_norm。",
    example: "-0.002",
    suggestion: "调大: 更严格排除下行；调小: 更宽松。"
  },
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
  },
  "min_mid_room": {
    name: "中轨空间",
    type: "数值 (Ratio)",
    default: "0.015",
    range: "0.0 - 0.20",
    unit: "比例",
    desc: "要求中轨附近留出一定空间，过滤拥挤通道。",
    logic: "mid_room ≥ min_mid_room。",
    example: "0.015 (1.5%)",
    suggestion: "调大: 更严格；调小: 更宽松。"
  },
  "min_mid_profit_pct": {
    name: "最小利润",
    type: "数值 (Ratio)",
    default: "0.0",
    range: "0.0 - 0.50",
    unit: "比例",
    desc: "盈利过滤阈值，用于限制最低盈利要求。",
    logic: "利润率 ≥ min_mid_profit_pct。",
    example: "0.02 (2%)",
    suggestion: "调大: 更严格；调小: 更宽松。"
  },
  "min_rr_to_mid": {
    name: "最小风险收益比",
    type: "数值 (RR)",
    default: "0.0",
    range: "0.0 - 10.0",
    unit: "倍",
    desc: "风险收益比过滤阈值。",
    logic: "RR ≥ min_rr_to_mid。",
    example: "1.5",
    suggestion: "调大: 更严格；调小: 更宽松。"
  },
  "scan_recent_days": {
    name: "扫描天数",
    type: "整数 (Days)",
    default: "1",
    range: "1 - 60",
    unit: "天",
    desc: "扫描时只关注最近 N 天内的信号/日志。",
    logic: "用于控制扫描窗口，避免过旧信号。",
    example: "1 / 5 / 20",
    suggestion: "短线用小；复盘用大。"
  },
  "require_index_condition": {
    name: "指数确认",
    type: "布尔 (Yes/No)",
    default: "true",
    range: "true / false",
    unit: "",
    desc: "是否要求指数条件满足才允许买入。",
    logic: "启用后更保守，过滤指数环境不佳时的信号。",
    example: "true",
    suggestion: "保守策略建议启用。"
  },
  "index_bear_exit": {
    name: "熊市强退",
    type: "布尔 (Yes/No)",
    default: "true",
    range: "true / false",
    unit: "",
    desc: "当指数处于熊市判定时是否强制退出。",
    logic: "用于降低系统性风险暴露。",
    example: "true",
    suggestion: "保守策略建议启用。"
  },
  "fill_at_close": {
    name: "收盘成交",
    type: "布尔 (Yes/No)",
    default: "true",
    range: "true / false",
    unit: "",
    desc: "是否用收盘价执行成交。",
    logic: "启用后更贴近收盘策略回测。",
    example: "true",
    suggestion: "回测一致性建议启用。"
  },
  "trend_ma_period": {
    name: "趋势均线",
    type: "整数 (Days)",
    default: "0",
    range: "0 - 250",
    unit: "天",
    desc: "趋势均线周期，0 表示不启用。",
    logic: "用于过滤趋势不符合的标的。",
    example: "0 / 60 / 120",
    suggestion: "周期越大越平滑。"
  },
  "index_trend_ma_period": {
    name: "指数均线",
    type: "整数 (Days)",
    default: "0",
    range: "0 - 250",
    unit: "天",
    desc: "指数趋势均线周期，0 表示不启用。",
    logic: "用于指数环境趋势过滤。",
    example: "0 / 20 / 60",
    suggestion: "保守策略可启用。"
  },
  "require_rebound": {
    name: "要求反弹",
    type: "布尔 (Yes/No)",
    default: "false",
    range: "true / false",
    unit: "",
    desc: "是否要求出现反弹特征后才允许买入。",
    logic: "用于减少下跌中接飞刀。",
    example: "false",
    suggestion: "抄底风格可启用。"
  },
  "require_green": {
    name: "要求阳线",
    type: "布尔 (Yes/No)",
    default: "false",
    range: "true / false",
    unit: "",
    desc: "是否要求当天为阳线才允许买入。",
    logic: "用于过滤弱势日的触发。",
    example: "false",
    suggestion: "更稳健时启用。"
  },
  "max_positions": {
    name: "最大持仓数",
    type: "整数 (Count)",
    default: "5",
    range: "1 - 50",
    unit: "只",
    desc: "组合允许同时持有的最大股票数量。",
    logic: "限制分散程度与资金管理。",
    example: "5",
    suggestion: "越小越集中、越大越分散。"
  },
  "max_position_pct": {
    name: "单票仓位上限",
    type: "数值 (Ratio)",
    default: "0.10",
    range: "0.01 - 1.00",
    unit: "比例",
    desc: "单只股票的最大资金占比。",
    logic: "用于控制单票风险暴露。",
    example: "0.10 (10%)",
    suggestion: "保守策略调小。"
  },
  "pivot_confirm_days": {
    name: "企稳确认窗口",
    type: "整数 (Days)",
    default: "3",
    range: "0 - 30",
    unit: "天",
    desc: "底部企稳确认窗口，0 表示不启用。",
    logic: "用于确认底部是否形成。",
    example: "3",
    suggestion: "调大: 更严格；调小: 更敏感。"
  },
  "pivot_no_new_low_tol": {
    name: "不创新低容差",
    type: "数值 (Ratio)",
    default: "0.01",
    range: "0.0 - 0.20",
    unit: "比例",
    desc: "企稳确认期间不创新低的容差。",
    logic: "允许在一定容差内的低点波动。",
    example: "0.01 (1%)",
    suggestion: "调大: 更宽松；调小: 更严格。"
  },
  "pivot_rebound_amp": {
    name: "反弹幅度",
    type: "数值 (Ratio)",
    default: "0.02",
    range: "0.0 - 0.50",
    unit: "比例",
    desc: "企稳确认所需的最小反弹幅度。",
    logic: "反弹幅度 ≥ pivot_rebound_amp。",
    example: "0.02 (2%)",
    suggestion: "调大: 更严格；调小: 更敏感。"
  },
  "pivot_confirm_requires_sig": {
    name: "显著低点才启用企稳",
    type: "布尔 (Yes/No)",
    default: "true",
    range: "true / false",
    unit: "",
    desc: "是否仅在出现显著低点信号时启用企稳确认。",
    logic: "避免无意义的企稳判定。",
    example: "true",
    suggestion: "保守策略建议启用。"
  },
  "volatility_ratio_max": {
    name: "波动率比率上限",
    type: "数值 (Ratio)",
    default: "1.0",
    range: "0.5 - 3.0",
    unit: "比率",
    desc: "短期波动率/长期波动率的上限过滤。",
    logic: "vol_ratio ≤ volatility_ratio_max。",
    example: "1.0",
    suggestion: "调小: 排除波动骤增；调大: 更宽松。"
  }
};

const STRATEGY_PARAM_ID_BY_KEY = {
  channel_period: "cfg-channel-period",
  buy_touch_eps: "cfg-buy-eps",
  sell_trigger_eps: "cfg-sell-eps",
  sell_target_mode: "cfg-sell-mode",
  channel_break_eps: "cfg-break-eps",
  entry_fill_eps: "cfg-entry-eps",
  exit_fill_eps: "cfg-exit-eps",
  stop_loss_mul: "cfg-stop-loss",
  stop_loss_on_close: "cfg-stop-loss-on-close",
  stop_loss_panic_eps: "cfg-stop-loss-panic-eps",
  max_holding_days: "cfg-max-hold",
  cooling_period: "cfg-cool",
  slope_abs_max: "cfg-slope-abs",
  min_slope_norm: "cfg-min-slope-norm",
  vol_shrink_min: "cfg-vol-shrink-min",
  vol_shrink_max: "cfg-vol-shrink-max",
  min_channel_height: "cfg-min-height",
  min_mid_room: "cfg-min-room",
  scan_recent_days: "cfg-recent-days",
  require_index_condition: "cfg-require-index-confirm",
  index_bear_exit: "cfg-index-bear-exit",
  fill_at_close: "cfg-fill-at-close",
  trend_ma_period: "cfg-trend-ma-period",
  index_trend_ma_period: "cfg-index-trend-ma-period",
  require_rebound: "cfg-require-rebound",
  require_green: "cfg-require-green",
  max_positions: "cfg-max-positions",
  max_position_pct: "cfg-max-position-pct",
  pivot_confirm_days: "cfg-pivot-confirm-days",
  pivot_no_new_low_tol: "cfg-pivot-no-new-low-tol",
  pivot_rebound_amp: "cfg-pivot-rebound-amp",
  pivot_confirm_requires_sig: "cfg-pivot-confirm-requires-sig",
  min_mid_profit_pct: "cfg-min-mid-profit-pct",
  min_rr_to_mid: "cfg-min-rr-to-mid",
  volatility_ratio_max: "cfg-volatility-ratio-max",
};

const STRATEGY_PARAM_KEY_BY_ID = Object.fromEntries(
  Object.entries(STRATEGY_PARAM_ID_BY_KEY).map(([k, id]) => [id, k])
);

const _RECENT_CFG_KEYS_STORAGE_KEY = "recent_cfg_keys_v1";
const _RECENT_CFG_KEYS_MAX = 20;

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

const _BATCH_TASK_STORAGE_KEY = "batch_task_ids_v1";
const _BATCH_TASK_MAX_KEEP = 5;
let _batchTasksState = {
  taskIds: [],
  timer: null,
  auto: true,
  lastStatuses: {},
  refreshing: false
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

function _normalizeConfigKey(key) {
  const k = String(key || "").trim();
  if (!k) return null;
  const alias = {
    min_height: "min_channel_height",
    min_room: "min_mid_room",
    panic_eps: "stop_loss_panic_eps",
    max_hold_days: "max_holding_days",
    trend_ma: "trend_ma_period",
    index_ma: "index_trend_ma_period",
    break_eps: "channel_break_eps",
    min_profit: "min_mid_profit_pct",
    min_rr: "min_rr_to_mid",
  };
  return alias[k] || k;
}

function _loadRecentConfigKeys() {
  try {
    const raw = localStorage.getItem(_RECENT_CFG_KEYS_STORAGE_KEY);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr.map(x => String(x)).filter(Boolean) : [];
  } catch {
    return [];
  }
}

function _saveRecentConfigKeys(keys) {
  try {
    const arr = Array.isArray(keys) ? keys.map(x => String(x)).filter(Boolean) : [];
    localStorage.setItem(_RECENT_CFG_KEYS_STORAGE_KEY, JSON.stringify(arr.slice(0, _RECENT_CFG_KEYS_MAX)));
  } catch {}
}

function _markRecentConfigKey(key) {
  const k = String(key || "").trim();
  if (!k) return;
  const cur = _loadRecentConfigKeys();
  const next = [k, ...cur.filter(x => x !== k)];
  _saveRecentConfigKeys(next);
}

function _getRecentConfigKeySet() {
  return new Set(_loadRecentConfigKeys());
}

function _getConfigInputElByKey(key) {
  const k = String(key || "").trim();
  if (!k) return null;
  const id = STRATEGY_PARAM_ID_BY_KEY[k];
  const byId = id ? document.getElementById(id) : null;
  if (byId) return byId;
  try {
    const bindings = _collectConfigBindings();
    return bindings.get(k) || null;
  } catch {
    return null;
  }
}

function _isDefaultDifferentFromCurrent(key, el) {
  const k = String(key || "").trim();
  if (!k || !el) return false;
  const def = PARAM_DEFINITIONS[k];
  if (!def || def.default == null) return false;

  const defRaw = String(def.default).trim();
  if (el.type === "checkbox") {
    const defBool = defRaw === "true" || defRaw === "1";
    return Boolean(el.checked) !== defBool;
  }

  const curRaw = String(el.value ?? "").trim();
  if (el.type === "number") {
    const curNum = Number(curRaw);
    const defNum = Number(defRaw);
    if (!Number.isFinite(defNum)) return false;
    if (!Number.isFinite(curNum)) return true;
    return curNum !== defNum;
  }

  return curRaw !== defRaw;
}

function _jumpToConfigKey(key) {
  const k = String(key || "").trim();
  if (!k) return;
  try {
    setActiveView("config");
  } catch {}

  const el = _getConfigInputElByKey(k);
  if (!el) return;

  try {
    el.scrollIntoView({ behavior: "smooth", block: "center" });
  } catch {
    try { el.scrollIntoView(); } catch {}
  }

  try {
    el.focus({ preventScroll: true });
  } catch {
    try { el.focus(); } catch {}
  }

  const cls = ["ring-2", "ring-blue-500", "ring-offset-2", "ring-offset-white", "dark:ring-offset-slate-900"];
  try {
    el.classList.add(...cls);
    setTimeout(() => {
      try { el.classList.remove(...cls); } catch {}
    }, 1200);
  } catch {}
}

function initRecentConfigKeyTracking() {
  for (const [key, id] of Object.entries(STRATEGY_PARAM_ID_BY_KEY)) {
    const el = document.getElementById(id);
    if (!el) continue;
    const handler = () => {
      _markRecentConfigKey(key);
      const inputParams = getStrategyConfigFromUI();
      const dbgParams = (_debugState && _debugState.lastResult && _debugState.lastResult.params) ? _debugState.lastResult.params : null;
      _renderDebugParamsPanel({ __input_params: inputParams, __running_params: dbgParams });
      _renderBacktestParamsPanel({ __input_params: inputParams, __running_params: null });
    };
    el.addEventListener("input", handler);
    el.addEventListener("change", handler);
  }
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

function _loadBatchTaskIds() {
  try {
    const raw = localStorage.getItem(_BATCH_TASK_STORAGE_KEY);
    const arr = JSON.parse(raw || "[]");
    if (!Array.isArray(arr)) return [];
    return arr.map(x => String(x || "").trim()).filter(Boolean);
  } catch (e) {
    return [];
  }
}

function _saveBatchTaskIds(taskIds) {
  try {
    localStorage.setItem(_BATCH_TASK_STORAGE_KEY, JSON.stringify(taskIds || []));
  } catch (e) {}
}

function rememberBatchTaskId(taskId) {
  const tid = String(taskId || "").trim();
  if (!tid) return;
  const ids = _loadBatchTaskIds();
  const next = [tid, ...ids.filter(x => x !== tid)].slice(0, _BATCH_TASK_MAX_KEEP);
  _saveBatchTaskIds(next);
  _batchTasksState.taskIds = next;
}

function _pruneBatchTaskIds() {
  const ids = Array.isArray(_batchTasksState.taskIds) ? _batchTasksState.taskIds : [];
  const next = ids.map(x => String(x || "").trim()).filter(Boolean).slice(0, _BATCH_TASK_MAX_KEEP);
  _batchTasksState.taskIds = next;
  _saveBatchTaskIds(next);
}

function _batchEls() {
  return {
    panel: document.getElementById("pt-tasks-panel"),
    list: document.getElementById("pt-tasks-list"),
    msg: document.getElementById("pt-tasks-msg"),
    btnRefresh: document.getElementById("pt-tasks-refresh"),
    chkAuto: document.getElementById("pt-tasks-auto")
  };
}

function _fmtNum(v, digits) {
  if (v == null) return "--";
  const n = Number(v);
  if (!Number.isFinite(n)) return "--";
  const d = Number.isFinite(Number(digits)) ? Math.max(0, Math.min(8, Number(digits))) : 4;
  return n.toFixed(d);
}

const _BATCH_TASK_POLL_INTERVAL = {
  running: 5000,
  completed: 30000,
  cancelled: 30000,
  default: 10000,
};

const _TASK_CENTER_STORAGE_KEY = "chhf_task_center_v1";
const _TASK_CENTER_MAX_KEEP = 200;

const _taskCenterState = {
  selectedId: null,
};

function _taskCenterNowIso() {
  return new Date().toISOString();
}

function _taskCenterId() {
  try {
    if (window.crypto && typeof window.crypto.randomUUID === "function") return window.crypto.randomUUID();
  } catch (e) {}
  const t = Date.now();
  const r = Math.floor(Math.random() * 1e9);
  return `t_${t}_${r}`;
}

function _taskCenterLoadAll() {
  try {
    const raw = localStorage.getItem(_TASK_CENTER_STORAGE_KEY);
    const data = JSON.parse(raw || "[]");
    const arr = Array.isArray(data) ? data : [];
    const out = [];
    for (const it of arr) {
      if (!it || typeof it !== "object") continue;
      const id = String(it.id || "").trim();
      if (!id) continue;
      out.push({
        id,
        type: String(it.type || "unknown"),
        title: typeof it.title === "string" ? it.title : "",
        status: String(it.status || "unknown"),
        created_at: String(it.created_at || ""),
        finished_at: it.finished_at ? String(it.finished_at) : "",
        archived: !!it.archived,
        recent_days: (it.recent_days == null || !Number.isFinite(Number(it.recent_days))) ? null : Number(it.recent_days),
        progress_done: (it.progress_done == null || !Number.isFinite(Number(it.progress_done))) ? 0 : Math.trunc(Number(it.progress_done)),
        progress_total: (it.progress_total == null || !Number.isFinite(Number(it.progress_total))) ? 0 : Math.trunc(Number(it.progress_total)),
        summary: typeof it.summary === "string" ? it.summary : "",
        request: (it.request && typeof it.request === "object") ? it.request : null,
        signal_results: Array.isArray(it.signal_results) ? it.signal_results : [],
        backtest_results: Array.isArray(it.backtest_results) ? it.backtest_results : [],
        errors: Array.isArray(it.errors) ? it.errors : [],
      });
    }
    out.sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
    return out;
  } catch (e) {
    return [];
  }
}

function _taskCenterSaveAll(tasks) {
  const arr = Array.isArray(tasks) ? tasks : [];
  try {
    localStorage.setItem(_TASK_CENTER_STORAGE_KEY, JSON.stringify(arr.slice(0, _TASK_CENTER_MAX_KEEP)));
  } catch (e) {}
}

function _taskCenterUpsert(task) {
  if (!task || typeof task !== "object") return;
  const id = String(task.id || "").trim();
  if (!id) return;
  const all = _taskCenterLoadAll();
  const idx = all.findIndex(x => String(x.id) === id);
  const next = {
    ...(idx >= 0 ? all[idx] : {}),
    ...task,
    id,
  };
  if (idx >= 0) all[idx] = next;
  else all.unshift(next);
  _taskCenterSaveAll(all);
}

function _taskCenterUpdate(taskId, patch) {
  const tid = String(taskId || "").trim();
  if (!tid) return;
  const all = _taskCenterLoadAll();
  const idx = all.findIndex(x => String(x.id) === tid);
  if (idx < 0) return;
  all[idx] = { ...all[idx], ...(patch && typeof patch === "object" ? patch : {}) };
  _taskCenterSaveAll(all);
}

function _taskCenterAppendError(taskId, errMsg) {
  const tid = String(taskId || "").trim();
  if (!tid) return;
  const msg = String(errMsg || "").trim();
  if (!msg) return;
  const all = _taskCenterLoadAll();
  const idx = all.findIndex(x => String(x.id) === tid);
  if (idx < 0) return;
  const prev = all[idx];
  const errors = Array.isArray(prev.errors) ? prev.errors.slice() : [];
  errors.unshift({ at: _taskCenterNowIso(), message: msg });
  all[idx] = { ...prev, errors };
  _taskCenterSaveAll(all);
}

function _taskCenterAppendBacktestRow(taskId, row) {
  const tid = String(taskId || "").trim();
  if (!tid) return;
  const all = _taskCenterLoadAll();
  const idx = all.findIndex(x => String(x.id) === tid);
  if (idx < 0) return;
  const prev = all[idx];
  const rows = Array.isArray(prev.backtest_results) ? prev.backtest_results.slice() : [];
  rows.push(row);
  all[idx] = { ...prev, backtest_results: rows.slice(0, 5000) };
  _taskCenterSaveAll(all);
}

function _taskCenterAppendSignalRow(taskId, row) {
  const tid = String(taskId || "").trim();
  if (!tid) return;
  const all = _taskCenterLoadAll();
  const idx = all.findIndex(x => String(x.id) === tid);
  if (idx < 0) return;
  const prev = all[idx];
  const rows = Array.isArray(prev.signal_results) ? prev.signal_results.slice() : [];
  rows.push(row);
  all[idx] = { ...prev, signal_results: rows.slice(0, 5000) };
  _taskCenterSaveAll(all);
}

function _taskCenterVisibleTasks(tasks) {
  const arr = Array.isArray(tasks) ? tasks : [];
  return arr.filter(t => t && !t.archived);
}

function _taskCenterStatusBadge(status) {
  const s = String(status || "").toLowerCase();
  if (s === "running") return `<span class="text-blue-600 dark:text-blue-400 font-bold">运行中</span>`;
  if (s === "completed") return `<span class="text-emerald-600 dark:text-emerald-400 font-bold">完成</span>`;
  if (s === "error") return `<span class="text-rose-600 dark:text-rose-400 font-bold">失败</span>`;
  if (s === "cancelled") return `<span class="text-slate-500 font-bold">已取消</span>`;
  return `<span class="text-slate-500 font-bold">${_escapeHtml(status || "-")}</span>`;
}

function _taskCenterRenderList() {
  const tbody = document.getElementById("task-list");
  if (!tbody) return;
  const tasks = _taskCenterVisibleTasks(_taskCenterLoadAll());
  tbody.innerHTML = "";
  if (!tasks.length) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="px-3 py-6 text-center text-slate-400 dark:text-slate-500" colspan="6">暂无任务（运行一次回测/扫描后会自动记录）</td>
    `;
    tbody.appendChild(tr);
    return;
  }
  for (const t of tasks) {
    const tr = document.createElement("tr");
    const created = t.created_at ? new Date(t.created_at) : null;
    const timeText = created && !Number.isNaN(created.getTime()) ? created.toLocaleString() : (t.created_at || "-");
    const progressText = t.progress_total ? `${t.progress_done || 0}/${t.progress_total || 0}` : "-";
    const recentDaysText = t.recent_days == null ? "-" : String(t.recent_days);
    const signalText = t.summary ? _escapeHtml(t.summary) : "-";
    const selected = _taskCenterState.selectedId && String(_taskCenterState.selectedId) === String(t.id);
    tr.className = `hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors ${selected ? "bg-slate-50 dark:bg-slate-800/50" : ""}`;
    tr.dataset.taskId = String(t.id);
    tr.innerHTML = `
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-600 dark:text-slate-400 font-mono">${_escapeHtml(timeText)}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50">${_taskCenterStatusBadge(t.status)}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-600 dark:text-slate-400">${_escapeHtml(recentDaysText)}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-600 dark:text-slate-400 font-mono">${_escapeHtml(progressText)}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-700 dark:text-slate-300 truncate max-w-[260px]" title="${_escapeHtml(t.summary || "")}">${signalText}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-center whitespace-nowrap">
        <button class="text-blue-600 hover:text-blue-800 underline text-[10px] mr-2" data-action="view" data-task-id="${_escapeHtml(t.id)}">查看</button>
        <button class="text-rose-600 hover:text-rose-800 underline text-[10px]" data-action="delete" data-task-id="${_escapeHtml(t.id)}">删除</button>
      </td>
    `;
    tbody.appendChild(tr);
  }
}

function _taskCenterSetCopyButton(btnId, textProvider) {
  const btn = document.getElementById(btnId);
  if (!btn) return;
  btn.onclick = async () => {
    try {
      const text = String(textProvider ? textProvider() : "");
      if (!text) return;
      if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
        await navigator.clipboard.writeText(text);
      } else {
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.style.position = "fixed";
        ta.style.left = "-9999px";
        document.body.appendChild(ta);
        ta.focus();
        ta.select();
        document.execCommand("copy");
        ta.remove();
      }
    } catch (e) {}
  };
}

function _taskCenterRenderDetail(taskId) {
  const titleEl = document.getElementById("task-detail-title");
  const detailEl = document.getElementById("task-detail");
  const rerunBtn = document.getElementById("task-rerun");
  const signalBlock = document.getElementById("task-signal-block");
  const backtestBlock = document.getElementById("task-backtest-block");
  const errorsTbody = document.getElementById("task-errors");
  const signalTbody = document.getElementById("task-results");
  const backtestTbody = document.getElementById("task-backtest-results");
  if (!titleEl || !detailEl) return;

  const tid = String(taskId || "").trim();
  if (!tid) {
    titleEl.textContent = "任务详情";
    detailEl.textContent = "";
    if (rerunBtn) rerunBtn.disabled = true;
    if (signalTbody) signalTbody.innerHTML = "";
    if (backtestTbody) backtestTbody.innerHTML = "";
    if (errorsTbody) errorsTbody.innerHTML = "";
    if (backtestBlock) backtestBlock.classList.add("hidden");
    if (signalBlock) signalBlock.classList.remove("hidden");
    return;
  }

  const all = _taskCenterLoadAll();
  const t = all.find(x => String(x.id) === tid);
  if (!t) return;

  titleEl.textContent = `${t.type || "task"} · ${t.id}`;
  const detailObj = {
    id: t.id,
    type: t.type,
    status: t.status,
    created_at: t.created_at,
    finished_at: t.finished_at || null,
    recent_days: t.recent_days,
    progress: t.progress_total ? `${t.progress_done || 0}/${t.progress_total || 0}` : null,
    summary: t.summary || null,
    request: t.request || null,
  };
  detailEl.textContent = JSON.stringify(detailObj, null, 2);

  if (rerunBtn) rerunBtn.disabled = !(t && t.request && (t.type === "backtest" || t.type === "param_batch_test"));

  if (errorsTbody) {
    errorsTbody.innerHTML = "";
    const errs = Array.isArray(t.errors) ? t.errors : [];
    for (const e of errs) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 font-mono text-slate-600 dark:text-slate-400">${_escapeHtml((e && e.at) ? String(e.at).slice(0, 19).replace("T", " ") : "-")}</td>
        <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-rose-600 dark:text-rose-400">${_escapeHtml((e && e.message) ? e.message : "-")}</td>
      `;
      errorsTbody.appendChild(tr);
    }
  }

  const isBacktest = t.type === "backtest";
  if (backtestBlock) backtestBlock.classList.toggle("hidden", !isBacktest);
  if (signalBlock) signalBlock.classList.toggle("hidden", isBacktest);

  if (signalTbody) {
    signalTbody.innerHTML = "";
    const rows = Array.isArray(t.signal_results) ? t.signal_results : [];
    for (const r of rows) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 font-mono text-slate-700 dark:text-slate-300">${_escapeHtml(r && r.symbol ? r.symbol : "-")}</td>
        <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 font-mono text-slate-600 dark:text-slate-400">${_escapeHtml(r && r.date ? r.date : "-")}</td>
        <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-center">${_escapeHtml(r && r.status ? r.status : "-")}</td>
      `;
      signalTbody.appendChild(tr);
    }
  }

  if (backtestTbody) {
    backtestTbody.innerHTML = "";
    const rows = Array.isArray(t.backtest_results) ? t.backtest_results : [];
    for (const r of rows) {
      const sym = r && r.symbol ? String(r.symbol) : "-";
      const trt = (r && Number.isFinite(Number(r.total_return))) ? (Number(r.total_return) * 100).toFixed(2) + "%" : "-";
      const sc = (r && Number.isFinite(Number(r.score))) ? Number(r.score).toFixed(2) : "-";
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 font-mono text-slate-700 dark:text-slate-300">${_escapeHtml(sym)}</td>
        <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono font-bold">${_escapeHtml(trt)}</td>
        <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono text-slate-600 dark:text-slate-400">${_escapeHtml(sc)}</td>
      `;
      backtestTbody.appendChild(tr);
    }
  }

  _taskCenterSetCopyButton("task-copy-results", () => JSON.stringify(t.signal_results || [], null, 2));
  _taskCenterSetCopyButton("task-copy-backtest", () => JSON.stringify(t.backtest_results || [], null, 2));
  _taskCenterSetCopyButton("task-copy-errors", () => JSON.stringify(t.errors || [], null, 2));
}

function _taskCenterSelect(taskId) {
  _taskCenterState.selectedId = taskId ? String(taskId) : null;
  _taskCenterRenderList();
  _taskCenterRenderDetail(_taskCenterState.selectedId);
}

function _taskCenterArchiveCompleted() {
  const all = _taskCenterLoadAll();
  const next = all.map(t => {
    const st = String(t.status || "").toLowerCase();
    if (st === "running") return t;
    return { ...t, archived: true };
  });
  _taskCenterSaveAll(next);
}

function _taskCenterExportVisible() {
  const tasks = _taskCenterVisibleTasks(_taskCenterLoadAll());
  const blob = new Blob([JSON.stringify(tasks, null, 2)], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `task_center_${new Date().toISOString().slice(0, 10)}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function _runBacktestStream(req, onMsg) {
  const resp = await fetch("/api/backtest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req)
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || `启动失败: HTTP ${resp.status}`);
  }
  if (!resp.body) throw new Error("响应无流数据");
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
      const msg = JSON.parse(line);
      if (onMsg) onMsg(msg);
    }
  }
}

async function runBacktestTask(req, ui) {
  const taskId = _taskCenterId();
  _taskCenterUpsert({
    id: taskId,
    type: "backtest",
    title: "回测",
    status: "running",
    created_at: _taskCenterNowIso(),
    archived: false,
    request: req,
    progress_done: 0,
    progress_total: 0,
    backtest_results: [],
    errors: [],
    summary: "",
  });
  _taskCenterRenderList();

  let total = 0;
  let done = 0;
  try {
    await _runBacktestStream(req, (msg) => {
      if (!msg || typeof msg !== "object") return;
      if (msg.type === "start") {
        total = Number(msg.total) || 0;
        _taskCenterUpdate(taskId, { progress_total: total, progress_done: 0, status: "running" });
        if (ui && ui.statusEl) ui.statusEl.textContent = total ? `回测中 0/${total}` : "回测中...";
      } else if (msg.type === "result") {
        done += 1;
        if (msg.data) _taskCenterAppendBacktestRow(taskId, msg.data);
        _taskCenterUpdate(taskId, {
          progress_done: done,
          summary: `${done} 条回测结果`,
          status: "running",
        });
        if (ui && ui.tbody && msg.data) renderBacktestRowToTbody(ui.tbody, msg.data);
        if (ui && ui.statusEl) ui.statusEl.textContent = total ? `回测中 ${done}/${total}` : `回测中 ${done}`;
      } else if (msg.type === "error") {
        const m = msg.message ? String(msg.message) : "未知错误";
        _taskCenterAppendError(taskId, m);
        _taskCenterUpdate(taskId, { status: "error", summary: "回测失败" });
        if (ui && ui.logsEl) appendRunLog(`Error: ${m}`);
      } else if (msg.type === "end") {
        _taskCenterUpdate(taskId, { status: "completed", finished_at: _taskCenterNowIso(), summary: `${done} 条回测结果` });
        if (ui && ui.statusEl) ui.statusEl.textContent = "完成";
        if (ui && ui.tbody && done === 0) {
          const tr = document.createElement("tr");
          tr.innerHTML = `<td class="px-3 py-6 text-center text-slate-400 dark:text-slate-500" colspan="18">暂无回测结果（请检查股票列表/区间/数据目录）</td>`;
          ui.tbody.appendChild(tr);
        }
      }
      if (_taskCenterState.selectedId && String(_taskCenterState.selectedId) === String(taskId)) {
        _taskCenterRenderDetail(taskId);
      }
    });
    _taskCenterUpdate(taskId, { status: "completed", finished_at: _taskCenterNowIso(), summary: `${done} 条回测结果` });
  } catch (e) {
    _taskCenterAppendError(taskId, toMsg(e));
    _taskCenterUpdate(taskId, { status: "error", finished_at: _taskCenterNowIso(), summary: "回测失败" });
    throw e;
  } finally {
    _taskCenterRenderList();
  }
  return taskId;
}

function initTaskCenterPanel() {
  const btnRefresh = document.getElementById("task-refresh");
  const btnArchive = document.getElementById("task-archive");
  const btnExport = document.getElementById("task-export");
  const btnClear = document.getElementById("task-clear");
  const rerunBtn = document.getElementById("task-rerun");
  const tbody = document.getElementById("task-list");
  if (!tbody) return;

  if (btnRefresh) btnRefresh.onclick = () => _taskCenterRenderList();
  if (btnArchive) btnArchive.onclick = () => {
    _taskCenterArchiveCompleted();
    if (_taskCenterState.selectedId) _taskCenterState.selectedId = null;
    _taskCenterRenderList();
    _taskCenterRenderDetail(null);
  };
  if (btnExport) btnExport.onclick = () => _taskCenterExportVisible();
  if (btnClear) btnClear.onclick = () => {
    if (!confirm("确定要清空任务中心吗？")) return;
    _taskCenterSaveAll([]);
    _taskCenterState.selectedId = null;
    _taskCenterRenderList();
    _taskCenterRenderDetail(null);
  };

  tbody.onclick = (ev) => {
    const t = ev.target;
    const action = t && t.dataset ? t.dataset.action : null;
    const taskId = t && t.dataset ? t.dataset.taskId : null;
    if (action === "view" && taskId) {
      _taskCenterSelect(taskId);
      return;
    }
    if (action === "delete" && taskId) {
      if (!confirm("确定要删除此任务吗？")) return;
      const all = _taskCenterLoadAll().filter(x => String(x.id) !== String(taskId));
      _taskCenterSaveAll(all);
      if (_taskCenterState.selectedId && String(_taskCenterState.selectedId) === String(taskId)) _taskCenterState.selectedId = null;
      _taskCenterRenderList();
      _taskCenterRenderDetail(_taskCenterState.selectedId);
      return;
    }
    const row = t && typeof t.closest === "function" ? t.closest("tr[data-task-id]") : null;
    const rid = row ? row.dataset.taskId : null;
    if (rid) _taskCenterSelect(rid);
  };

  if (rerunBtn) {
    rerunBtn.onclick = async () => {
      const tid = _taskCenterState.selectedId;
      if (!tid) return;
      const all = _taskCenterLoadAll();
      const t = all.find(x => String(x.id) === String(tid));
      if (!t || !t.request) return;
      try {
        if (t.type === "backtest") {
          setActiveView("backtest");
          await runBacktestTask(t.request, {
            statusEl: document.getElementById("bt-status"),
            tbody: document.getElementById("bt-results"),
            logsEl: document.getElementById("run-logs"),
          });
        }
      } catch (e) {}
    };
  }

  _taskCenterRenderList();
  _taskCenterRenderDetail(null);
}

function updateCancelButton(taskId, status) {
  const tid = String(taskId || "").trim();
  if (!tid) return;
  const row = document.querySelector(`[data-task-id="${tid}"]`);
  const btn = row ? row.querySelector(".cancel-btn") : null;
  if (!btn) return;

  if (status === "running") {
    btn.style.display = "inline-block";
    btn.disabled = false;
    btn.textContent = "取消任务";
  } else {
    btn.style.display = "none";
  }
}

function _getBatchTaskEffectiveStatus(taskId, statusMap, errorsMap) {
  const tid = String(taskId || "").trim();
  if (!tid) return "--";
  const stNow = (statusMap && statusMap[tid]) ? statusMap[tid] : null;
  const stPrev = (_batchTasksState.lastStatuses && _batchTasksState.lastStatuses[tid]) ? _batchTasksState.lastStatuses[tid] : null;
  const err = (errorsMap && errorsMap[tid]) ? String(errorsMap[tid]) : "";
  const s = (stNow && stNow.status) ? String(stNow.status) : ((stPrev && stPrev.status) ? String(stPrev.status) : "");
  return s || (err ? "error" : "--");
}

function _calcBatchTasksPollDelayMs(statusMap, errorsMap) {
  const ids = _batchTasksState.taskIds || [];
  for (const tid of ids) {
    const st = _getBatchTaskEffectiveStatus(tid, statusMap, errorsMap);
    if (st === "running") return _BATCH_TASK_POLL_INTERVAL.running;
  }
  return _BATCH_TASK_POLL_INTERVAL.completed;
}

function _clearBatchTasksTimer() {
  if (_batchTasksState.timer) {
    clearTimeout(_batchTasksState.timer);
    _batchTasksState.timer = null;
  }
}

function _scheduleNextBatchTasksPoll(delayMs) {
  _clearBatchTasksTimer();
  if (!_batchTasksState.auto) return;
  const ms = Number.isFinite(Number(delayMs)) ? Math.max(1000, Number(delayMs)) : _BATCH_TASK_POLL_INTERVAL.default;
  _batchTasksState.timer = setTimeout(() => {
    refreshBatchTasksStatus().catch(() => {});
  }, ms);
}

function _renderBatchTasks(statusMap, errorsMap) {
  const { list } = _batchEls();
  if (!list) return;
  const ids = _batchTasksState.taskIds || [];
  if (!ids.length) {
    list.innerHTML = `<div class="text-[10px] text-slate-400 dark:text-slate-500">暂无任务（启动一次批量测试后会自动记录 task_id）</div>`;
    return;
  }

  const rows = ids.map(taskId => {
    const stNow = (statusMap && statusMap[taskId]) || null;
    const stPrev = (_batchTasksState.lastStatuses && _batchTasksState.lastStatuses[taskId]) || null;
    const st = stNow || stPrev || null;
    const err = (errorsMap && errorsMap[taskId]) || "";
    const status = _getBatchTaskEffectiveStatus(taskId, statusMap, errorsMap);
    const progress = st && st.progress ? String(st.progress) : "--";
    const agg = (st && st.aggregation && typeof st.aggregation === "object") ? st.aggregation : null;
    const winRate = agg ? _fmtNum(agg.win_rate, 4) : "--";
    const avgReturn = agg ? _fmtNum(agg.avg_return, 6) : "--";
    const rejRate = agg ? _fmtNum(agg.rejection_rate, 4) : "--";

    const showCancel = status === "running";
    const cancelStyle = showCancel ? "display:inline-block" : "display:none";
    const action = `<button type="button" class="cancel-btn" onclick="cancelBatchTask(${JSON.stringify(taskId)})" style="color: blue; text-decoration: underline; background: transparent; border: 0; padding: 0; cursor: pointer; ${cancelStyle};" ${showCancel ? "" : "disabled"}>取消任务</button>`;

    const errHtml = err ? `<div class="text-[10px] text-red-600 dark:text-red-400 mt-1">${_escapeHtml(err)}</div>` : "";

    return `
      <tr data-task-id="${String(taskId)}">
        <td class="px-2 py-1 border">${_escapeHtml(taskId)}</td>
        <td class="px-2 py-1 border">${_escapeHtml(status)}</td>
        <td class="px-2 py-1 border">${_escapeHtml(progress)}</td>
        <td class="px-2 py-1 border">${_escapeHtml(winRate)}</td>
        <td class="px-2 py-1 border">${_escapeHtml(avgReturn)}</td>
        <td class="px-2 py-1 border">${_escapeHtml(rejRate)}</td>
        <td class="px-2 py-1 border">${action}</td>
      </tr>
      ${errHtml ? `<tr><td class="px-2 py-1 border" colspan="7">${errHtml}</td></tr>` : ""}
    `;
  }).join("");

  list.innerHTML = `
    <table border="1" cellspacing="0" cellpadding="3" class="text-[10px] w-full">
      <thead>
        <tr>
          <th class="px-2 py-1">task_id</th>
          <th class="px-2 py-1">状态</th>
          <th class="px-2 py-1">进度</th>
          <th class="px-2 py-1">胜率</th>
          <th class="px-2 py-1">平均收益</th>
          <th class="px-2 py-1">拒绝率</th>
          <th class="px-2 py-1">操作</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

async function refreshBatchTasksStatus() {
  const { msg } = _batchEls();
  _pruneBatchTaskIds();
  const ids = _batchTasksState.taskIds || [];
  if (!ids.length) {
    _renderBatchTasks({}, {});
    return;
  }
  if (_batchTasksState.refreshing) return;
  _batchTasksState.refreshing = true;
  if (msg) msg.textContent = "刷新中...";

  const statusMap = {};
  const errorsMap = {};
  const removed = new Set();

  try {
    await Promise.all(ids.map(async (taskId) => {
      try {
        const resp = await fetch(`/batch_test/status?task_id=${encodeURIComponent(taskId)}`, { method: "GET" });
        if (resp.status === 404) {
          removed.add(String(taskId || "").trim());
          return;
        }
        if (!resp.ok) {
          const err = await resp.json().catch(() => ({}));
          throw new Error(err.detail || `HTTP ${resp.status}`);
        }
        statusMap[taskId] = await resp.json();
      } catch (e) {
        errorsMap[taskId] = toMsg(e);
      }
    }));

    if (removed.size) {
      const nextIds = ids.filter(x => !removed.has(String(x || "").trim()));
      _batchTasksState.taskIds = nextIds;
      _saveBatchTaskIds(nextIds);
    }

    const prev = (_batchTasksState.lastStatuses && typeof _batchTasksState.lastStatuses === "object") ? _batchTasksState.lastStatuses : {};
    _batchTasksState.lastStatuses = { ...prev, ...statusMap };

    _renderBatchTasks(statusMap, errorsMap);
    for (const tid of _batchTasksState.taskIds || []) {
      updateCancelButton(tid, _getBatchTaskEffectiveStatus(tid, statusMap, errorsMap));
    }
    if (msg) msg.textContent = `已刷新 ${( _batchTasksState.taskIds || [] ).length} 个任务（${new Date().toLocaleTimeString()}）`;
  } finally {
    _batchTasksState.refreshing = false;
    if ((_batchTasksState.taskIds || []).length) {
      _scheduleNextBatchTasksPoll(_calcBatchTasksPollDelayMs(statusMap, errorsMap));
    } else {
      _clearBatchTasksTimer();
    }
  }
}

async function cancelBatchTask(taskId) {
  const tid = String(taskId || "").trim();
  if (!tid) return;
  if (!confirm("确定要取消此任务吗？")) return;
  try {
    const resp = await fetch("/batch_test/cancel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_id: tid })
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `取消失败: HTTP ${resp.status}`);
    }
    alert("取消成功");
  } catch (e) {
    alert("取消失败: " + toMsg(e));
  } finally {
    await refreshBatchTasksStatus();
  }
}

function _setBatchTasksAuto(enabled) {
  _batchTasksState.auto = !!enabled;
  _clearBatchTasksTimer();
  if (_batchTasksState.auto) refreshBatchTasksStatus().catch(() => {});
}

function initBatchTasksPanel() {
  const { panel, btnRefresh, chkAuto } = _batchEls();
  if (!panel) return;

  _batchTasksState.taskIds = _loadBatchTaskIds();

  if (btnRefresh) {
    btnRefresh.onclick = () => refreshBatchTasksStatus();
  }
  if (chkAuto) {
    chkAuto.onchange = () => _setBatchTasksAuto(!!chkAuto.checked);
  }

  _setBatchTasksAuto(chkAuto ? !!chkAuto.checked : true);
  refreshBatchTasksStatus().catch(() => {});
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
    const symbol = _normSymbol(tr.dataset.symbol || (tr.querySelector("td") ? tr.querySelector("td").textContent : ""));
    if (!symbol) continue;

    const trades = Number(tr.dataset.trades);
    const win_rate = Number(tr.dataset.win_rate);
    const total_return = Number(tr.dataset.total_return);
    const max_drawdown = Number(tr.dataset.max_drawdown);
    const score = Number(tr.dataset.score);
    const score_robust = Number(tr.dataset.score_robust);
    const range = tr.dataset.range || (() => {
      const beg = normalizeYmOrYmd(val("bt-beg", ""), "beg");
      const end = normalizeYmOrYmd(val("bt-end", ""), "end");
      if (!beg && !end) return "-";
      return `${beg || "-"} ~ ${end || "-"}`;
    })();

    const scoreSafe = Number.isFinite(score) ? score : (Number.isFinite(total_return) ? total_return * 100 : 0);
    const scoreRobustSafe = Number.isFinite(score_robust)
      ? score_robust
      : ((Number.isFinite(scoreSafe) ? scoreSafe : 0) - (Number.isFinite(max_drawdown) ? Math.abs(max_drawdown) * 100 : 0));

    parsed.push({
      symbol,
      bt: {
        trades: Number.isFinite(trades) ? trades : null,
        win_rate: Number.isFinite(win_rate) ? win_rate : null,
        total_return: Number.isFinite(total_return) ? total_return : null,
        max_drawdown: Number.isFinite(max_drawdown) ? max_drawdown : null,
        score: Number.isFinite(scoreSafe) ? Number(scoreSafe.toFixed(4)) : 0,
        score_robust: Number.isFinite(scoreRobustSafe) ? Number(scoreRobustSafe.toFixed(4)) : 0,
        range,
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
  _scanSetTraceVisible(false);
  _scanSetTraceStatus("");
  _scanRenderTrace([]);
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

function _scanSetTraceVisible(show) {
  const wrap = document.getElementById("scan-trace-wrap");
  if (!wrap) return;
  wrap.classList.toggle("hidden", !show);
}

function _scanSetTraceStatus(text) {
  const el = document.getElementById("scan-trace-status");
  if (el) el.textContent = text || "";
}

function _scanRenderTrace(trace) {
  const tbody = document.getElementById("scan-trace");
  if (!tbody) return;
  tbody.innerHTML = "";
  const list = Array.isArray(trace) ? trace : [];
  if (list.length === 0) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td class="px-3 py-3 border-b border-slate-100 dark:border-slate-800/50 text-slate-500 dark:text-slate-400" colspan="6">暂无决策链数据</td>`;
    tbody.appendChild(tr);
    return;
  }
  for (const step of list) {
    if (!step || typeof step !== "object") continue;
    const tr = document.createElement("tr");
    const passed = step.passed;
    const passedText = passed === true ? "通过" : (passed === false ? "失败" : "-");
    const passedCls = passed === true ? "text-emerald-600" : (passed === false ? "text-rose-600" : "text-slate-500");
    tr.innerHTML = `
      <td class="px-3 py-2 border-b border-slate-100 dark:border-slate-800/50 font-bold text-slate-700 dark:text-slate-200">${_escapeHtml(step.step ?? "-")}</td>
      <td class="px-3 py-2 border-b border-slate-100 dark:border-slate-800/50 text-slate-600 dark:text-slate-400">${_escapeHtml(step.check ?? "-")}</td>
      <td class="px-3 py-2 border-b border-slate-100 dark:border-slate-800/50 text-slate-600 dark:text-slate-400 font-mono">${_escapeHtml(step.threshold ?? "-")}</td>
      <td class="px-3 py-2 border-b border-slate-100 dark:border-slate-800/50 text-slate-600 dark:text-slate-400 font-mono">${_escapeHtml(step.actual ?? "-")}</td>
      <td class="px-3 py-2 border-b border-slate-100 dark:border-slate-800/50 font-bold ${passedCls}">${_escapeHtml(passedText)}</td>
      <td class="px-3 py-2 border-b border-slate-100 dark:border-slate-800/50 text-slate-600 dark:text-slate-400">${_escapeHtml(step.reason ?? "-")}</td>
    `;
    tbody.appendChild(tr);
  }
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
  tr.className = "hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors cursor-pointer";
  tr.dataset.symbol = String(symbol);
  tr.dataset.date = String(dt || "").slice(0, 10);
  try {
    const trc = (env && Array.isArray(env.trace)) ? env.trace : [];
    tr.dataset.trace = JSON.stringify(trc);
  } catch (_) {
    tr.dataset.trace = "[]";
  }
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
  tr.addEventListener("click", () => {
    const dtText = String(dt || "").slice(0, 10);
    let trace = [];
    try {
      trace = JSON.parse(tr.dataset.trace || "[]");
    } catch (_) {
      trace = [];
    }
    _scanSetTraceVisible(true);
    _scanSetTraceStatus(`${symbol} · ${dtText || "-"}`);
    _scanRenderTrace(trace);
  });
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

  const taskId = _taskCenterId();
  _taskCenterUpsert({
    id: taskId,
    type: "scan",
    title: "扫描",
    status: "running",
    created_at: _taskCenterNowIso(),
    archived: false,
    request: null,
    recent_days: null,
    progress_done: 0,
    progress_total: 0,
    signal_results: [],
    errors: [],
    summary: "",
  });
  _taskCenterRenderList();

  try {
    const req = {
      data_dir: dataDir,
      symbols: parseSymbolsInput(val("scan-symbols", "")),
      index_data: useIndex ? (indexData || null) : null,
      index_symbol: useIndex ? (indexSymbol || null) : null,
      use_realtime: !!useRealtime,
      ...getStrategyConfigFromUI(),
    };
    _taskCenterUpdate(taskId, { request: req, recent_days: req.scan_recent_days ?? null });

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
          _taskCenterUpdate(taskId, { progress_total: total, progress_done: 0, status: "running" });
          continue;
        }

        if (msg.type === "heartbeat") {
          const p = _parseProgress(msg.progress);
          if (p) {
            done = p.done;
            total = p.total;
            _setScanProgress(done, total);
            _taskCenterUpdate(taskId, { progress_total: total, progress_done: done, status: "running" });
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
          if (msg.status === "success") {
            _renderScanResultRow(msg.data);
            const d = (msg.data && typeof msg.data === "object") ? msg.data : {};
            const env = (d.env && typeof d.env === "object") ? d.env : {};
            const statusText = env.index_bear ? "指数熊" : (env.ok ? "买点" : "过滤");
            _taskCenterAppendSignalRow(taskId, { symbol: d.symbol || "-", date: d.date || "-", status: statusText });
          } else {
            const m = msg.message || "未知错误";
            appendRunLog(`Error: ${m}`);
            _taskCenterAppendError(taskId, m);
          }
          _taskCenterUpdate(taskId, { progress_total: total || 0, progress_done: done || 0, status: "running", summary: `扫描 ${done || 0}/${total || 0}` });
          _taskCenterRenderList();
          continue;
        }

        if (msg.type === "error") {
          const m = msg.message || "未知错误";
          appendRunLog(`Error: ${m}`);
          _taskCenterAppendError(taskId, m);
          _taskCenterUpdate(taskId, { status: "error", summary: "扫描失败", finished_at: _taskCenterNowIso() });
          _taskCenterRenderList();
          continue;
        }

        if (msg.type === "cancelled") {
          appendRunLog(`已中断 ${msg.progress || ""}`.trim());
          _taskCenterUpdate(taskId, { status: "cancelled", summary: "已中断", finished_at: _taskCenterNowIso() });
          _taskCenterRenderList();
          continue;
        }

        if (msg.type === "end") {
          appendRunLog("扫描结束");
          _taskCenterUpdate(taskId, { status: "completed", summary: `扫描完成 ${done || 0}/${total || 0}`, finished_at: _taskCenterNowIso() });
          _taskCenterRenderList();
          continue;
        }
      }
    }

    _setScanStatus("完成");
  } catch (e) {
    const msg = toMsg(e);
    _setScanStatus(`Error: ${msg}`);
    appendRunLog(`Error: ${msg}`);
    _taskCenterAppendError(taskId, msg);
    _taskCenterUpdate(taskId, { status: "error", summary: "扫描失败", finished_at: _taskCenterNowIso() });
    _taskCenterRenderList();
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
    const fromId = el.id ? STRATEGY_PARAM_KEY_BY_ID[el.id] : null;
    const k = fromId || elToKey.get(el);
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

function _ptGetQuickParamKeys() {
  let keys = [];
  try {
    const cfg = getStrategyConfigFromUI();
    if (cfg && typeof cfg === "object") keys = Object.keys(cfg);
  } catch (_) {}
  if (!keys.length) keys = Object.keys(PARAM_DEFINITIONS || {});
  return Array.from(new Set(keys)).filter(Boolean).sort();
}

function _ptKeyLabel(k) {
  const d = (PARAM_DEFINITIONS && PARAM_DEFINITIONS[k]) ? PARAM_DEFINITIONS[k] : null;
  const name = d && d.name ? String(d.name) : "";
  return name ? `${name} (${k})` : k;
}

function _ptDispatchChange(el) {
  if (!el) return;
  el.dispatchEvent(new Event("input"));
  el.dispatchEvent(new Event("change"));
}

function _ptUpsertKvToLine(line, k, v) {
  const raw = String(line ?? "");
  const parts = raw.split(",").map(s => s.trim()).filter(Boolean);
  const kvText = `${k}=${v}`;
  if (!parts.length) return kvText;
  let hit = false;
  const out = parts.map(p => {
    const idx = p.indexOf("=");
    if (idx <= 0) return p;
    const pk = p.slice(0, idx).trim();
    if (pk !== k) return p;
    hit = true;
    return kvText;
  });
  if (!hit) out.push(kvText);
  return out.join(", ");
}

function _ptInsertIntoCurrentLine(textarea, k, v) {
  const text = String(textarea.value ?? "");
  const isActive = document.activeElement === textarea;
  const pos = (!isActive && text)
    ? text.length
    : ((typeof textarea.selectionStart === "number") ? textarea.selectionStart : text.length);
  const lineStart = Math.max(0, text.lastIndexOf("\n", Math.max(0, pos - 1)) + 1);
  const lineEnd = (() => {
    const i = text.indexOf("\n", pos);
    return i === -1 ? text.length : i;
  })();
  const line = text.slice(lineStart, lineEnd);
  const nextLine = _ptUpsertKvToLine(line, k, v);
  const nextText = text.slice(0, lineStart) + nextLine + text.slice(lineEnd);
  textarea.value = nextText;
  const nextPos = lineStart + nextLine.length;
  textarea.selectionStart = nextPos;
  textarea.selectionEnd = nextPos;
  _ptDispatchChange(textarea);
}

function _ptEnsureNewLineAtEnd(textarea) {
  const text = String(textarea.value ?? "");
  const next = text && !text.endsWith("\n") ? (text + "\n") : text;
  textarea.value = next;
  textarea.selectionStart = next.length;
  textarea.selectionEnd = next.length;
  _ptDispatchChange(textarea);
}

function initParamBatchQuickInsert() {
  const keySel = document.getElementById("pt-param-key");
  const valInput = document.getElementById("pt-param-value");
  const insertBtn = document.getElementById("pt-param-insert-btn");
  const newLineBtn = document.getElementById("pt-param-newline-btn");
  const textarea = document.getElementById("pt-param-sets");

  if (!keySel || !valInput || !insertBtn || !newLineBtn || !textarea) return;

  const keys = _ptGetQuickParamKeys();
  keySel.innerHTML = keys.map(k => `<option value="${_escapeHtml(k)}">${_escapeHtml(_ptKeyLabel(k))}</option>`).join("");

  insertBtn.onclick = () => {
    const k = String(keySel.value || "").trim();
    const vRaw = String(valInput.value || "").trim();
    if (!k) return alert("请选择参数");
    if (!vRaw) return alert("请输入参数值");

    textarea.focus();
    _ptInsertIntoCurrentLine(textarea, k, vRaw);
  };

  newLineBtn.onclick = () => {
    textarea.focus();
    _ptEnsureNewLineAtEnd(textarea);
  };

  valInput.addEventListener("keydown", (ev) => {
    if (ev.key !== "Enter") return;
    ev.preventDefault();
    insertBtn.click();
  });
}

function _ptGetGridMode() {
  const nodes = document.querySelectorAll('input[name="pt-grid-mode"]');
  for (const n of nodes) {
    if (n && n.checked) return String(n.value || "manual");
  }
  return "manual";
}

function _ptSetGridMode(nextMode) {
  const modes = ["manual", "file", "range"];
  const mode = modes.includes(String(nextMode)) ? String(nextMode) : "manual";
  const nodes = document.querySelectorAll('input[name="pt-grid-mode"]');
  for (const n of nodes) {
    if (!n) continue;
    n.checked = String(n.value) === mode;
  }

  const fileBtn = document.getElementById("pt-grid-file-btn");
  const fileName = document.getElementById("pt-grid-file-name");
  const input = document.getElementById("pt-param-grid");
  if (fileBtn) fileBtn.classList.toggle("hidden", mode !== "file");
  if (fileName) fileName.classList.toggle("hidden", mode !== "file");

  if (input) {
    if (mode === "manual") {
      input.placeholder = "例如：vol_shrink_min: [1.00, 1.02, 1.05]\nvol_shrink_max: [1.12, 1.15, 1.18]\n\n或：{\"vol_shrink_min\":[1.0,1.02],\"vol_shrink_max\":[1.12,1.15]}";
    } else if (mode === "range") {
      input.placeholder = "例如：vol_shrink_min: [0.1, 0.5, 0.1]\nvol_shrink_max: [10, 30, 10]\n\n自动组合：5×3=15";
    } else {
      input.placeholder = "选择 JSON/CSV 文件导入参数空间或参数组合";
    }
  }
}

function _ptParseMaybeNumber(v) {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  const s = String(v ?? "").trim();
  if (!s) return "";
  if ((s.startsWith('"') && s.endsWith('"')) || (s.startsWith("'") && s.endsWith("'"))) return s.slice(1, -1);
  const n = Number(s);
  return Number.isFinite(n) ? n : s;
}

function _ptTryParseJson(text) {
  const t = String(text || "").trim();
  if (!t) return null;
  if (!(t.startsWith("{") || t.startsWith("["))) return null;
  try {
    return JSON.parse(t);
  } catch {
    return null;
  }
}

function _ptDecimalsFromStep(step) {
  const s = String(step);
  if (s.includes("e-")) {
    const p = s.split("e-")[1];
    const n = Number(p);
    return Number.isFinite(n) ? Math.min(12, Math.max(0, n)) : 6;
  }
  const idx = s.indexOf(".");
  if (idx === -1) return 0;
  return Math.min(12, Math.max(0, s.length - idx - 1));
}

function _ptBuildRange(start, end, step) {
  const s = parseFloat(start);
  const e = parseFloat(end);
  const st = parseFloat(step);
  if (!Number.isFinite(s) || !Number.isFinite(e) || !Number.isFinite(st)) throw new Error("范围模式需要数字: [start, end, step]");
  if (st === 0) return [s];
  if (s < e && st < 0) throw new Error("范围模式 step 方向不正确");
  if (s > e && st > 0) throw new Error("范围模式 step 方向不正确");

  const out = [];
  const eps = 1e-10;
  const maxLen = 20000;
  const pushVal = (x) => {
    const v = (Math.abs(st) < 1) ? parseFloat(x.toFixed(6)) : (Math.round(x * 1000000) / 1000000);
    out.push(v);
  };

  if (st > 0) {
    for (let i = s; i <= e + eps && out.length < maxLen; i += st) pushVal(i);
  } else {
    for (let i = s; i >= e - eps && out.length < maxLen; i += st) pushVal(i);
  }

  if (out.length >= maxLen) throw new Error("范围模式生成数量过大");
  return out;
}

function _ptExtractFirstBracketExpr(s) {
  const m = String(s ?? "").match(/\[[^\[\]]*\]/);
  return m ? m[0] : "";
}

function _ptNormalizeGridLine(line) {
  let s = String(line ?? "").trim();
  s = s.replace(/^\s*[-*•]\s+/, "");
  s = s.replace(/^\s*\d+\.\s+/, "");
  return s.trim();
}

function _ptParseRangeExpression(expr) {
  const m = String(expr ?? "").trim().match(/^\[\s*([^,\]]+)\s*,\s*([^,\]]+)\s*,\s*([^,\]]+)\s*\]$/);
  if (!m) return null;
  const s = parseFloat(m[1]);
  const e = parseFloat(m[2]);
  const st = parseFloat(m[3]);
  if (!Number.isFinite(s) || !Number.isFinite(e) || !Number.isFinite(st)) return null;
  const dist = e - s;
  const eps = 1e-10;
  if (st !== 0) {
    if (dist > 0 && st < 0) return null;
    if (dist < 0 && st > 0) return null;
    if (Math.abs(st) > Math.abs(dist) + eps && Math.abs(dist) > eps) return null;
  }
  try {
    return _ptBuildRange(s, e, st);
  } catch {
    return null;
  }
}

function _ptUniqValues(arr) {
  const out = [];
  const seen = new Set();
  for (const v of (arr || [])) {
    const k = (typeof v === "number" && Number.isFinite(v)) ? `n:${v}` : `s:${String(v)}`;
    if (seen.has(k)) continue;
    seen.add(k);
    out.push(v);
  }
  return out;
}

function _ptParseGridLines(text, mode) {
  const lines = String(text || "").split("\n").map(l => l.trim()).filter(l => l && !l.startsWith("#"));
  const keys = [];
  const values = [];

  for (const line of lines) {
    const normLine = _ptNormalizeGridLine(line);
    const parts = normLine.split(/[:=]/);
    if (parts.length < 2) continue;
    const key = parts[0].trim();
    if (!key) continue;
    let valStr = parts.slice(1).join(":").trim();
    if (!valStr) continue;

    const bracketExpr = _ptExtractFirstBracketExpr(valStr);
    if (bracketExpr) {
      if (mode === "range") {
        const range = _ptParseRangeExpression(bracketExpr);
        if (range) {
          keys.push(key);
          values.push(range);
          continue;
        }
      }
      const inner = bracketExpr.slice(1, -1).trim();
      const rawParts = inner ? inner.split(",").map(v => v.trim()).filter(Boolean) : [];
      const vs = rawParts.map(_ptParseMaybeNumber);
      keys.push(key);
      values.push(vs);
    } else {
      const v = _ptParseMaybeNumber(valStr.split("#")[0].trim());
      keys.push(key);
      values.push([v]);
    }
  }

  return { keys, values };
}

function _ptJsonGridToKeyValues(obj, mode) {
  const keys = [];
  const values = [];
  for (const [k, v] of Object.entries(obj || {})) {
    const key = String(k || "").trim();
    if (!key) continue;
    if (Array.isArray(v)) {
      const vs = v.map(_ptParseMaybeNumber);
      if (mode === "range" && vs.length === 3 && vs.every(x => typeof x === "number" && Number.isFinite(x))) {
        const s = Number(vs[0]);
        const e = Number(vs[1]);
        const st = Number(vs[2]);
        const dist = e - s;
        const eps = 1e-10;
        const okDir = st === 0 ? true : !((dist > 0 && st < 0) || (dist < 0 && st > 0));
        const okStep = Math.abs(dist) <= eps ? true : (Math.abs(st) <= Math.abs(dist) + eps);
        if (okDir && okStep) {
          keys.push(key);
          values.push(_ptBuildRange(s, e, st));
        } else {
          keys.push(key);
          values.push(vs);
        }
      } else {
        keys.push(key);
        values.push(vs);
      }
    } else {
      keys.push(key);
      values.push([_ptParseMaybeNumber(v)]);
    }
  }
  return { keys, values };
}

function _ptParamSetsToLines(paramSets) {
  const out = [];
  for (const ps of paramSets || []) {
    if (!ps || typeof ps !== "object") continue;
    const parts = [];
    for (const [k, v] of Object.entries(ps)) {
      if (String(k) === "__name__") continue;
      const vv = typeof v === "string" ? v : (typeof v === "number" ? String(v) : JSON.stringify(v));
      parts.push(`${k}=${vv}`);
    }
    if (parts.length) out.push(parts.join(", "));
  }
  return out;
}

function _ptParseGridInput(text, mode) {
  const j = _ptTryParseJson(text);
  if (Array.isArray(j)) {
    const paramSets = j.filter(x => x && typeof x === "object");
    return { kind: "param_sets", paramSets };
  }
  if (j && typeof j === "object") {
    const { keys, values } = _ptJsonGridToKeyValues(j, mode);
    return { kind: "grid", keys, values };
  }
  const { keys, values } = _ptParseGridLines(text, mode);
  return { kind: "grid", keys, values };
}

function _ptCountCombos(values) {
  let n = 1n;
  for (const arr of values || []) {
    const len = Array.isArray(arr) ? arr.length : 0;
    n *= BigInt(len);
    if (n > 1000000000n) return { count: n, capped: true };
  }
  return { count: n, capped: false };
}

function _ptUpdateGridPreview() {
  const input = document.getElementById("pt-param-grid");
  const preview = document.getElementById("pt-grid-preview");
  if (!input || !preview) return;
  const text = String(input.value || "").trim();
  if (!text) {
    preview.textContent = "";
    return;
  }
  const mode = _ptGetGridMode();
  try {
    const parsed = _ptParseGridInput(text, mode);
    if (parsed.kind === "param_sets") {
      const n = BigInt(parsed.paramSets.length || 0);
      preview.textContent = `预计生成 ${n.toString()} 组参数组合`;
      return;
    }
    const keys = parsed.keys || [];
    const values = parsed.values || [];
    if (!keys.length) {
      preview.textContent = "未识别到有效的参数配置";
      return;
    }
    const { count, capped } = _ptCountCombos(values);
    const label = capped ? `${count.toString()}+` : count.toString();
    preview.textContent = `预计生成 ${label} 组参数组合`;
  } catch (e) {
    preview.textContent = `解析失败: ${e.message}`;
  }
}

function initParamGridInputModes() {
  const input = document.getElementById("pt-param-grid");
  const fileBtn = document.getElementById("pt-grid-file-btn");
  const fileInput = document.getElementById("pt-grid-file");
  const fileName = document.getElementById("pt-grid-file-name");
  if (!input) return;

  const radios = document.querySelectorAll('input[name="pt-grid-mode"]');
  for (const r of radios) {
    if (!r) continue;
    r.addEventListener("change", () => {
      _ptSetGridMode(_ptGetGridMode());
      _ptUpdateGridPreview();
    });
  }

  input.addEventListener("input", () => _ptUpdateGridPreview());
  _ptSetGridMode(_ptGetGridMode());
  _ptUpdateGridPreview();

  if (fileBtn && fileInput) {
    fileBtn.onclick = () => fileInput.click();
  }

  if (fileInput) {
    fileInput.addEventListener("change", async () => {
      const f = fileInput.files && fileInput.files[0] ? fileInput.files[0] : null;
      if (!f) return;
      if (fileName) {
        fileName.textContent = f.name;
        fileName.classList.remove("hidden");
      }
      const ext = String(f.name || "").toLowerCase().split(".").pop() || "";
      const text = await f.text();
      const output = document.getElementById("pt-param-sets");
      const mode = _ptGetGridMode();

      try {
        if (ext === "csv") {
          const rows = String(text || "").split(/\r?\n/).map(l => l.trim()).filter(Boolean);
          if (!rows.length) throw new Error("CSV 为空");
          const headers = rows[0].split(",").map(s => s.trim()).filter(Boolean);
          if (!headers.length) throw new Error("CSV 表头为空");
          const paramSets = [];
          for (const line of rows.slice(1)) {
            const cols = line.split(",").map(s => s.trim());
            const obj = {};
            for (let i = 0; i < headers.length; i++) {
              const k = headers[i];
              const v = cols[i] ?? "";
              if (!k) continue;
              const pv = _ptParseMaybeNumber(v);
              if (pv === "") continue;
              obj[k] = pv;
            }
            if (Object.keys(obj).length) paramSets.push(obj);
          }
          if (!paramSets.length) throw new Error("CSV 未解析到任何参数组合行");
          if (output) output.value = _ptParamSetsToLines(paramSets).join("\n");
          _ptUpdateGridPreview();
          return;
        }

        const j = _ptTryParseJson(text);
        if (Array.isArray(j)) {
          const paramSets = j.filter(x => x && typeof x === "object");
          if (!paramSets.length) throw new Error("JSON 数组未包含参数对象");
          if (output) output.value = _ptParamSetsToLines(paramSets).join("\n");
          _ptUpdateGridPreview();
          return;
        }
        if (j && typeof j === "object") {
          const { keys, values } = _ptJsonGridToKeyValues(j, mode === "file" ? "range" : mode);
          const lines = keys.map((k, i) => `${k}: [${(values[i] || []).join(", ")}]`);
          input.value = lines.join("\n");
          _ptUpdateGridPreview();
          return;
        }
        throw new Error("仅支持 JSON/CSV 文件");
      } catch (e) {
        alert("导入失败: " + e.message);
      }
    });
  }
}

function generateParamGrid() {
  const input = document.getElementById("pt-param-grid");
  const output = document.getElementById("pt-param-sets");
  const status = document.getElementById("pt-status");
  const preview = document.getElementById("pt-grid-preview");
  
  if (!input || !output) return;
  
  const text = input.value.trim();
  if (!text) {
    alert("请输入网格参数配置");
    return;
  }
  
  try {
    const mode = _ptGetGridMode();
    const parsed = _ptParseGridInput(text, mode);
    if (parsed.kind === "param_sets") {
      const linesOut = _ptParamSetsToLines(parsed.paramSets);
      output.value = linesOut.join("\n");
      const msg = `总计：${linesOut.length}种组合`;
      if (preview) {
        const showN = Math.min(linesOut.length, 500);
        const numbered = linesOut.slice(0, showN).map((ln, i) => `${i + 1}. ${ln}`);
        preview.textContent = showN < linesOut.length ? (msg + "\n" + numbered.join("\n") + `\n...（仅展示前${showN}行）`) : (msg + "\n" + numbered.join("\n"));
      }
      if (status && !_paramTestState.running) status.textContent = msg;
      return;
    }
    const keys = parsed.keys || [];
    const values = (parsed.values || []).map(vs => _ptUniqValues(vs));
    if (!keys.length) {
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
    const msg = `总计：${linesOut.length}种组合`;
    if (preview) {
      const showN = Math.min(linesOut.length, 500);
      const numbered = linesOut.slice(0, showN).map((ln, i) => `${i + 1}. ${ln}`);
      preview.textContent = showN < linesOut.length ? (msg + "\n" + numbered.join("\n") + `\n...（仅展示前${showN}行）`) : (msg + "\n" + numbered.join("\n"));
    }
    if (status && !_paramTestState.running) status.textContent = msg;
    
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
    if (msg.task_id) rememberBatchTaskId(msg.task_id);
    if (status) status.textContent = `开始测试: 共 ${msg.total} 个任务`;
    refreshBatchTasksStatus().catch(() => {});
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
  } else if (msg.type === "end") {
    refreshBatchTasksStatus().catch(() => {});
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
      b.classList.add("active");
    } else {
      b.classList.remove("active");
    }
  });

  try {
    if (id === "backtest") {
      _renderBacktestParamsPanel(getStrategyConfigFromUI());
    } else if (id === "debug") {
      const p = (_debugState && _debugState.lastResult && _debugState.lastResult.params) ? _debugState.lastResult.params : getStrategyConfigFromUI();
      _renderDebugParamsPanel(p);
    }
  } catch {}
}

let _cfgBindings = null;

function _extractConfigKey(labelText) {
  const m = String(labelText || "").match(/\(([^)]+)\)/);
  const raw = m ? m[1].trim() : null;
  return _normalizeConfigKey(raw);
}

function _collectConfigBindings() {
  if (typeof STRATEGY_PARAM_ID_BY_KEY === "object" && STRATEGY_PARAM_ID_BY_KEY) {
    const bindings = new Map();
    for (const [key, id] of Object.entries(STRATEGY_PARAM_ID_BY_KEY)) {
      const el = document.getElementById(id);
      if (!el) continue;
      bindings.set(key, el);
    }
    return bindings;
  }

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
  _cfgBindings = _collectConfigBindings();
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
  _cfgBindings = _collectConfigBindings();
  const raw = (cfg && typeof cfg === "object") ? cfg : {};
  const data = {};
  for (const [k, v] of Object.entries(raw)) {
    const nk = _normalizeConfigKey(k);
    if (nk) data[nk] = v;
    else data[k] = v;
  }
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

async function refreshPresetVersions(name, selectedVersion = null) {
  const sel = document.getElementById("preset-version-select");
  if (!sel) return;
  const nm = (name || "").trim();
  sel.innerHTML = "";
  if (!nm) return;
  try {
    const url = `/api/presets/versions?name=${encodeURIComponent(nm)}`;
    const resp = await fetch(url);
    const data = await resp.json().catch(() => ({}));
    const versions = Array.isArray(data.versions) ? data.versions : [];
    const opt0 = document.createElement("option");
    opt0.value = "";
    opt0.textContent = versions.length ? "请选择版本" : "暂无版本";
    sel.appendChild(opt0);
    for (const v of versions) {
      const opt = document.createElement("option");
      opt.value = String(v);
      opt.textContent = String(v);
      sel.appendChild(opt);
    }
    if (selectedVersion) sel.value = selectedVersion;
  } catch {}
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
    if (sel.value) refreshPresetVersions(sel.value);
  } catch (e) {
    _setPresetStatus(`加载失败: ${toMsg(e)}`, false);
  }
}

function _slotPresetName(code) {
  const c = String(code || "").trim().toUpperCase();
  if (c === "A" || c === "B" || c === "C") return `槽位${c}`;
  return "槽位A";
}

function initPresets() {
  const sel = document.getElementById("preset-select");
  const nameInput = document.getElementById("preset-name");
  const btnSave = document.getElementById("preset-save");
  const btnApply = document.getElementById("preset-apply");
  const btnDelete = document.getElementById("preset-delete");
  if (!sel || !nameInput || !btnSave || !btnApply || !btnDelete) return;

  sel.addEventListener("change", async () => {
    if (sel.value) nameInput.value = sel.value;
    const name = (sel.value || "").trim();
    if (!name) return;
    try {
      const url = `/api/presets/get?name=${encodeURIComponent(name)}`;
      const resp = await fetch(url);
      const data = await resp.json().catch(() => ({}));
      if (!data.ok) return _setPresetStatus(data.msg || "加载失败", false);
      applyConfigToUI(data.config || {});
      _setPresetStatus(`已加载预设: ${name}`, true);
      refreshPresetVersions(name);
    } catch (e) {
      _setPresetStatus(`加载失败: ${toMsg(e)}`, false);
    }
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
      refreshPresetVersions(name);
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
      refreshPresetVersions(name);
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
      refreshPresetVersions("");
    } catch (e) {
      _setPresetStatus(`删除失败: ${toMsg(e)}`, false);
    }
  });

  refreshPresets();
}

function initPresetSlotsAndVersioning() {
  const slotSel = document.getElementById("slot-select");
  const btnSlotSave = document.getElementById("slot-save");
  const btnSlotLoad = document.getElementById("slot-load");
  const btnRollback = document.getElementById("preset-rollback");
  const presetSel = document.getElementById("preset-select");
  const verSel = document.getElementById("preset-version-select");
  if (slotSel && btnSlotSave) {
    btnSlotSave.addEventListener("click", async () => {
      const name = _slotPresetName(slotSel.value);
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
        if (presetSel) presetSel.value = name;
        const nameInput = document.getElementById("preset-name");
        if (nameInput) nameInput.value = name;
        refreshPresetVersions(name);
      } catch (e) {
        _setPresetStatus(`保存失败: ${toMsg(e)}`, false);
      }
    });
  }
  if (slotSel && btnSlotLoad) {
    btnSlotLoad.addEventListener("click", async () => {
      const name = _slotPresetName(slotSel.value);
      try {
        const resp = await fetch("/api/presets/load", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name })
        });
        const data = await resp.json().catch(() => ({}));
        if (!data.ok) return _setPresetStatus(data.msg || "切换失败", false);
        applyConfigToUI(data.config || {});
        _setPresetStatus(data.msg || "已切换", true);
        await refreshPresets(name);
        refreshPresetVersions(name);
      } catch (e) {
        _setPresetStatus(`切换失败: ${toMsg(e)}`, false);
      }
    });
  }
  if (btnRollback && presetSel && verSel) {
    btnRollback.addEventListener("click", async () => {
      const name = (presetSel.value || "").trim();
      const version = (verSel.value || "").trim();
      if (!name) return _setPresetStatus("请选择预设", false);
      if (!version) return _setPresetStatus("请选择版本", false);
      try {
        const resp = await fetch("/api/presets/rollback", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, version })
        });
        const data = await resp.json().catch(() => ({}));
        if (!data.ok) return _setPresetStatus(data.msg || "回溯失败", false);
        applyConfigToUI(data.config || {});
        _setPresetStatus(data.msg || "已回溯", true);
        await refreshPresets(name);
        refreshPresetVersions(name, version);
      } catch (e) {
        _setPresetStatus(`回溯失败: ${toMsg(e)}`, false);
      }
    });
  }
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
  const list = Array.isArray(trace) ? trace : [];
  if (list.length === 0) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-500 dark:text-slate-400" colspan="6">暂无决策链数据（无成交时默认展示最后一个交易日）</td>
    `;
    tbody.appendChild(tr);
    return;
  }
  for (const step of list) {
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
  _renderParamsListPanel("debug-param-panel-summary", "debug-param-panel-groups", params, { emptyText: "未返回参数" });
}

function _renderBacktestParamsPanel(params) {
  _renderParamsListPanel("bt-param-panel-summary", "bt-param-panel-groups", params, { emptyText: "未初始化参数" });
}

function _renderParamsListPanel(summaryId, groupsId, params, { emptyText } = {}) {
  const sum = document.getElementById(summaryId);
  const groups = document.getElementById(groupsId);
  if (!sum || !groups) return;
  const payload = (params && typeof params === "object") ? params : {};
  const input = (payload && typeof payload.__input_params === "object" && payload.__input_params) ? payload.__input_params : payload;
  const running = (payload && typeof payload.__running_params === "object" && payload.__running_params) ? payload.__running_params : null;
  const actual = (payload && typeof payload.__actual_env === "object" && payload.__actual_env) ? payload.__actual_env : null;
  const keysSet = new Set([
    ...Object.keys((input && typeof input === "object") ? input : {}),
    ...Object.keys((running && typeof running === "object") ? running : {}),
  ]);
  const keys = Array.from(keysSet).sort();
  sum.textContent = keys.length ? `共 ${keys.length} 个参数` : (emptyText || "");
  groups.innerHTML = "";

  const runtimeMap = (key) => {
    const k0 = String(key || "").trim();
    if (!k0) return null;
    if (k0 === "min_channel_height") return { field: "channel_height", digits: 4 };
    if (k0 === "min_mid_room") return { field: "mid_room", digits: 4 };
    if (k0 === "min_slope_norm") return { field: "slope_norm", digits: 4 };
    if (k0 === "slope_abs_max") return { field: "slope_norm", digits: 4 };
    if (k0 === "vol_shrink_threshold") return { field: "vol_ratio", digits: 2 };
    if (k0 === "vol_shrink_min") return { field: "vol_ratio", digits: 2 };
    if (k0 === "vol_shrink_max") return { field: "vol_ratio", digits: 2 };
    if (k0 === "volatility_ratio_max") return { field: "vol_ratio", digits: 2 };
    if (k0 === "cooling_period") return { field: "cooling_left", digits: 0 };
    if (k0 === "cooling_days") return { field: "cooling_left", digits: 0 };
    if (k0 === "pivot_confirm_days") return { field: "pivot_j", digits: 0 };
    return null;
  };

  const fmtAny = (v, digits = 4) => {
    if (v == null) return "-";
    if (typeof v === "boolean") return v ? "true" : "false";
    const n = Number(v);
    if (Number.isFinite(n)) return n.toFixed(digits);
    return String(v);
  };

  const recent = _getRecentConfigKeySet();
  const list = document.createElement("div");
  list.className = "border border-slate-100 dark:border-slate-800 rounded-lg overflow-hidden";

  for (const rawKey of keys) {
    const k = _normalizeConfigKey(rawKey) || rawKey;
    const row = document.createElement("div");
    row.className = "px-2 py-1 flex items-center justify-between gap-2 hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors cursor-pointer";

    const left = document.createElement("div");
    left.className = "min-w-0";
    const def = PARAM_DEFINITIONS[k];
    const displayName = def && def.name ? `${def.name} (${k})` : k;
    left.innerHTML = `<div class="text-[11px] font-bold text-slate-700 dark:text-slate-200 truncate">${_escapeHtml(displayName)}</div>`;

    const badges = document.createElement("div");
    badges.className = "flex items-center gap-1 shrink-0";
    if (recent.has(k)) {
      const b = document.createElement("span");
      b.className = "inline-block px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-100 dark:bg-blue-900/20 dark:text-blue-300 dark:border-blue-900/40 text-[10px] font-bold";
      b.textContent = "最近修改";
      badges.appendChild(b);
    }

    const inputEl = _getConfigInputElByKey(k);
    if (inputEl && _isDefaultDifferentFromCurrent(k, inputEl)) {
      const b = document.createElement("span");
      b.className = "inline-block px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-100 dark:bg-blue-900/20 dark:text-blue-300 dark:border-blue-900/40 text-[10px] font-bold";
      b.textContent = "默认≠当前";
      badges.appendChild(b);
    }

    const right = document.createElement("div");
    right.className = "flex items-center gap-2 shrink-0";
    right.appendChild(badges);
    const valWrap = document.createElement("div");
    valWrap.className = "flex flex-col items-end leading-tight";

    const getV = (obj) => {
      if (!obj || typeof obj !== "object") return undefined;
      if (rawKey in obj) return obj[rawKey];
      if (k in obj) return obj[k];
      return undefined;
    };

    const vInput = getV(input);
    const vRunning = getV(running);
    let vActual = undefined;
    let vActualDigits = 4;
    if (actual) {
      const m = runtimeMap(k);
      if (m && m.field) {
        vActual = actual[m.field];
        vActualDigits = Number.isFinite(Number(m.digits)) ? Number(m.digits) : 4;
      }
    }

    const mkLine = (label, value, cls) => {
      const line = document.createElement("div");
      line.className = "flex items-center gap-1";
      const lab = document.createElement("span");
      lab.className = "text-[10px] font-bold text-slate-400 dark:text-slate-500";
      lab.textContent = label;
      const valEl = document.createElement("span");
      valEl.className = cls;
      valEl.textContent = label === "实际" ? fmtAny(value, vActualDigits) : (value == null ? "-" : String(value));
      line.appendChild(lab);
      line.appendChild(valEl);
      return line;
    };

    valWrap.appendChild(mkLine("配置", vInput, "font-mono text-[11px] text-slate-600 dark:text-slate-300"));
    if (running && (vRunning != null) && String(vRunning) !== String(vInput)) {
      valWrap.appendChild(mkLine("运行", vRunning, "font-mono text-[11px] text-slate-500 dark:text-slate-400"));
    }
    if (vActual != null) {
      valWrap.appendChild(mkLine("实际", vActual, "font-mono text-[11px] text-slate-700 dark:text-slate-200"));
    }
    right.appendChild(valWrap);

    row.appendChild(left);
    row.appendChild(right);

    row.addEventListener("click", () => _jumpToConfigKey(k));
    list.appendChild(row);
  }

  groups.appendChild(list);
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
      _renderDebugParamsPanel({ __input_params: getStrategyConfigFromUI(), __running_params: (_debugState.lastResult && _debugState.lastResult.params) ? _debugState.lastResult.params : null, __actual_env: (day && typeof day === "object") ? day : null });
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
    _renderDebugParamsPanel({ __input_params: getStrategyConfigFromUI(), __running_params: (_debugState.lastResult && _debugState.lastResult.params) ? _debugState.lastResult.params : null, __actual_env: (day && typeof day === "object") ? day : null });
  } else {
    _debugState.selectedTradeIdx = -1;
    _renderDebugFeatureSnapshot({});
    const last = (dailyData && Array.isArray(dailyData) && dailyData.length) ? dailyData[dailyData.length - 1] : null;
    _renderDebugTrace(last && Array.isArray(last.trace) ? last.trace : []);
    _renderDebugParamsPanel({ __input_params: getStrategyConfigFromUI(), __running_params: (_debugState.lastResult && _debugState.lastResult.params) ? _debugState.lastResult.params : null, __actual_env: (last && typeof last === "object") ? last : null });
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
    _renderDebugParamsPanel({ __input_params: getStrategyConfigFromUI(), __running_params: (data.params || {}) });
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

let _btState = {
  symbol: null,
  runningParams: null
};

function _btSetTraceStatus(text) {
  const el = document.getElementById("bt-trace-status");
  if (el) el.textContent = text || "";
}

function _btSetTraceVisible(show) {
  const wrap = document.getElementById("bt-trace-wrap");
  if (!wrap) return;
  wrap.classList.toggle("hidden", !show);
}

function _btRenderTrace(trace) {
  const tbody = document.getElementById("bt-trace");
  if (!tbody) return;
  tbody.innerHTML = "";
  const list = Array.isArray(trace) ? trace : [];
  if (list.length === 0) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td class="px-3 py-3 border-b border-slate-50 dark:border-slate-800/50 text-slate-500 dark:text-slate-400" colspan="6">暂无决策链数据（请在明细请求中启用 capture_logs）</td>`;
    tbody.appendChild(tr);
    return;
  }
  for (const step of list) {
    if (!step || typeof step !== "object") continue;
    const tr = document.createElement("tr");
    const passed = step.passed;
    const passedText = passed === true ? "通过" : (passed === false ? "失败" : "-");
    const passedCls = passed === true ? "text-emerald-600" : (passed === false ? "text-rose-600" : "text-slate-500");
    tr.innerHTML = `
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 font-bold text-slate-700 dark:text-slate-200">${_escapeHtml(step.step ?? "-")}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-600 dark:text-slate-400">${_escapeHtml(step.check ?? "-")}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-600 dark:text-slate-400 font-mono">${_escapeHtml(step.threshold ?? "-")}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-600 dark:text-slate-400 font-mono">${_escapeHtml(step.actual ?? "-")}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 font-bold ${passedCls}">${_escapeHtml(passedText)}</td>
      <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-600 dark:text-slate-400">${_escapeHtml(step.reason ?? "-")}</td>
    `;
    tbody.appendChild(tr);
  }
}

function _btPickLastTrace(signalLogs) {
  const logs = Array.isArray(signalLogs) ? signalLogs : [];
  for (let i = logs.length - 1; i >= 0; i--) {
    const it = logs[i];
    if (!it || typeof it !== "object") continue;
    const tr = it.trace;
    if (Array.isArray(tr) && tr.length) return it;
  }
  return null;
}

function _btPickSignalDateForTrade(trade, signalLogs) {
  const entry = (trade && (trade.entry_date || trade.entry_dt)) ? String(trade.entry_date || trade.entry_dt) : "";
  const entryD = entry ? new Date(entry) : null;
  if (!entryD || Number.isNaN(entryD.getTime())) return entry;
  let best = null;
  for (const it of (signalLogs || [])) {
    if (!it || typeof it !== "object" || !it.date) continue;
    if (Number(it.final_signal || 0) !== 1) continue;
    const d = new Date(String(it.date));
    if (Number.isNaN(d.getTime())) continue;
    if (d.getTime() >= entryD.getTime()) continue;
    if (!best || d.getTime() > best.getTime()) best = d;
  }
  if (best) return best.toISOString().slice(0, 10);
  return entry;
}

function _btFirstFailedStep(trace) {
  const list = Array.isArray(trace) ? trace : [];
  for (const s of list) {
    if (s && typeof s === "object" && s.passed === false) return s;
  }
  return null;
}

function _btClearDetail() {
  const body = document.getElementById("bt-detail-body");
  if (body) body.innerHTML = "";
  const st = document.getElementById("bt-detail-status");
  if (st) st.textContent = "-";
  _btSetTraceVisible(false);
  _btSetTraceStatus("");
  _btRenderTrace([]);
}

function _btRenderTrades(symbol, trades, signalLogs) {
  const tbody = document.getElementById("bt-detail-body");
  const st = document.getElementById("bt-detail-status");
  if (!tbody) return;
  tbody.innerHTML = "";

  const list = Array.isArray(trades) ? trades : [];
  let cum = 0.0;
  if (list.length === 0) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td class="px-3 py-6 text-center text-slate-400 dark:text-slate-500" colspan="16">无成交（将展示最后交易日的过滤原因）</td>`;
    tbody.appendChild(tr);

    _btSetTraceVisible(true);
    const last = _btPickLastTrace(signalLogs);
    const trace = last && Array.isArray(last.trace) ? last.trace : [];
    const failed = _btFirstFailedStep(trace);
    const dateText = last && (last.dt || last.date) ? String(last.dt || last.date).slice(0, 10) : "";
    const failedText = failed ? `${failed.step || "Unknown"} · ${failed.reason || failed.check || ""}` : "";
    if (st) st.textContent = `${symbol} · 无成交` + (dateText ? ` · ${dateText}` : "") + (failedText ? ` · 过滤：${failedText}` : "");
    _btSetTraceStatus(dateText ? `日期：${dateText}` : "");
    _btRenderTrace(trace);
    _renderBacktestParamsPanel({ __input_params: getStrategyConfigFromUI(), __running_params: _btState.runningParams, __actual_env: last });
  } else {
    for (const t of list) {
      const x = t && typeof t === "object" ? t : {};
      const pnl = Number(x.pnl);
      if (Number.isFinite(pnl)) cum += pnl;
      const ret = Number(x.return_rate ?? x.return_pct);
      const retText = Number.isFinite(ret) ? `${(ret * 100).toFixed(2)}%` : "-";
      const retCls = Number.isFinite(ret) ? (ret > 0 ? "text-red-600" : (ret < 0 ? "text-green-600" : "text-slate-500")) : "text-slate-500";
      const idxOk = (x.entry_index_confirmed === true) ? "✓" : "-";
      const tr = document.createElement("tr");
      tr.className = "hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors cursor-pointer";
      tr.innerHTML = `
        <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-700 dark:text-slate-300 font-mono">${_escapeHtml(String(x.symbol || symbol || "-"))}</td>
        <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-600 dark:text-slate-400 font-mono">${_escapeHtml(String(x.entry_dt || x.entry_date || "-").slice(0, 10))}</td>
        <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-600 dark:text-slate-400 font-mono">${_escapeHtml(String(x.exit_dt || x.exit_date || "-").slice(0, 10))}</td>
        <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-600 dark:text-slate-400 text-right font-mono">${_escapeHtml(String(x.qty ?? "-"))}</td>
        <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono text-slate-600 dark:text-slate-400">${_escapeHtml(String(x.entry_price ?? "-"))}</td>
        <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono text-slate-600 dark:text-slate-400">${_escapeHtml(String(x.exit_price ?? "-"))}</td>
        <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-700 dark:text-slate-200">${_escapeHtml(String(x.entry_reason || "-"))}</td>
        <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-700 dark:text-slate-200">${_escapeHtml(String(x.exit_reason || "-"))}</td>
        <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono text-slate-600 dark:text-slate-400">${_escapeHtml(x.initial_stop == null ? "-" : String(x.initial_stop))}</td>
        <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono text-slate-600 dark:text-slate-400">${_escapeHtml(x.trailing_stop == null ? "-" : String(x.trailing_stop))}</td>
        <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono font-bold text-slate-700 dark:text-slate-200">${_escapeHtml(Number.isFinite(pnl) ? pnl.toFixed(2) : "-")}</td>
        <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono text-slate-600 dark:text-slate-400">${_escapeHtml(Number.isFinite(cum) ? cum.toFixed(2) : "-")}</td>
        <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono font-bold ${retCls}">${_escapeHtml(retText)}</td>
        <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono text-slate-600 dark:text-slate-400">${_escapeHtml(x.r_multiple == null ? "-" : String(x.r_multiple))}</td>
        <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono text-slate-600 dark:text-slate-400">${_escapeHtml(String(x.holding_days ?? "-"))}</td>
        <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-center font-mono text-slate-600 dark:text-slate-400">${_escapeHtml(idxOk)}</td>
      `;
      tr.addEventListener("click", () => {
        const sigDate = _btPickSignalDateForTrade(x, signalLogs);
        const day = (signalLogs || []).find(it => it && String(it.date || "").startsWith(sigDate));
        const trace = day && Array.isArray(day.trace) ? day.trace : [];
        const failed = _btFirstFailedStep(trace);
        const failedText = failed ? `${failed.step || "Unknown"} · ${failed.reason || failed.check || ""}` : "";
        _btSetTraceVisible(true);
        _btSetTraceStatus(sigDate ? `日期：${sigDate}` : "");
        if (st) st.textContent = `${symbol} · 成交 · ${sigDate || "-"}` + (failedText ? ` · 过滤：${failedText}` : "");
        _btRenderTrace(trace);
        _renderBacktestParamsPanel({ __input_params: getStrategyConfigFromUI(), __running_params: _btState.runningParams, __actual_env: day });
      });
      tbody.appendChild(tr);
    }

    _btSetTraceVisible(false);
    _btSetTraceStatus("");
    _btRenderTrace([]);
    if (st) st.textContent = `${symbol} · ${list.length} 笔成交`;
  }
}

async function _btLoadDetail(symbol) {
  const st = document.getElementById("bt-detail-status");
  if (st) st.textContent = `${symbol} · 加载中...`;
  _btSetTraceVisible(false);
  _btSetTraceStatus("");
  _btRenderTrace([]);
  try {
    const data = await fetchBacktestDetailForSymbol(symbol);
    const trades = data && (data.trades || (data.data && data.data.trades)) ? (data.trades || data.data.trades) : [];
    const signalLogs = data && (data.signal_logs || (data.data && data.data.signal_logs)) ? (data.signal_logs || data.data.signal_logs) : [];
    const runningParams = data && (data.params || (data.data && data.data.params)) ? (data.params || data.data.params) : null;
    _btState = { symbol: String(symbol || ""), runningParams: runningParams };
    _renderBacktestParamsPanel({ __input_params: getStrategyConfigFromUI(), __running_params: runningParams, __actual_env: null });
    _btRenderTrades(symbol, trades, signalLogs);
  } catch (e) {
    if (st) st.textContent = `${symbol} · 获取详情失败`;
    _btSetTraceStatus("");
    _btRenderTrace([]);
  }
}

function renderBacktestRowToTbody(tbody, d) {
  if (!tbody || !d) return;
  const tr = document.createElement("tr");
  tr.className = "hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors";
  const symbol = d.symbol || "-";
  const beg = d.beg || null;
  const end = d.end || null;
  const range = (beg || end) ? `${beg || "-"} ~ ${end || "-"}` : "-";

  const totalReturn = d.total_return;
  const annualizedReturn = d.annualized_return;
  const maxDrawdown = d.max_drawdown;
  const drawdownDuration = d.drawdown_duration;
  const maxDrawdownDate = d.max_drawdown_date;
  const sharpeRatio = d.sharpe_ratio;
  const expectancy = d.expectancy;
  const profitFactor = d.profit_factor;
  const avgHoldDays = d.avg_hold_days;
  const score = d.score;
  const scoreRobust = d.score_robust;
  const winRate = d.win_rate;
  const trades = d.trades;
  const maxWinStreak = d.max_win_streak;
  const maxLossStreak = d.max_loss_streak;
  const finalEquity = d.final_equity;
  const anomalies = d.anomalies;

  tr.dataset.symbol = String(symbol);
  tr.dataset.range = String(range);
  tr.dataset.total_return = String(totalReturn ?? "");
  tr.dataset.annualized_return = String(annualizedReturn ?? "");
  tr.dataset.max_drawdown = String(maxDrawdown ?? "");
  tr.dataset.sharpe_ratio = String(sharpeRatio ?? "");
  tr.dataset.expectancy = String(expectancy ?? "");
  tr.dataset.profit_factor = String(profitFactor ?? "");
  tr.dataset.avg_hold_days = String(avgHoldDays ?? "");
  tr.dataset.score = String(score ?? "");
  tr.dataset.score_robust = String(scoreRobust ?? "");
  tr.dataset.win_rate = String(winRate ?? "");
  tr.dataset.trades = String(trades ?? "");
  tr.dataset.final_equity = String(finalEquity ?? "");
  tr.dataset.anomalies = String(anomalies ?? "");

  const fmtPct = (v, opts = {}) => {
    const clsBase = (opts && typeof opts.clsBase === "string") ? opts.clsBase : "";
    const signColor = (opts && typeof opts.signColor === "boolean") ? opts.signColor : true;
    if (v == null) return `<span class="${clsBase}">-</span>`;
    const n = Number(v);
    if (!Number.isFinite(n)) return `<span class="${clsBase}">-</span>`;
    const clsSign = signColor ? (n > 0 ? "text-red-600" : (n < 0 ? "text-green-600" : "text-slate-500")) : "";
    return `<span class="${[clsBase, clsSign].filter(Boolean).join(" ")}">${(n * 100).toFixed(2)}%</span>`;
  };

  const fmtNum = (v, digits = 2) => {
    const n = Number(v);
    if (!Number.isFinite(n)) return "-";
    return n.toFixed(digits);
  };

  const fmtInt = (v) => {
    const n = Number(v);
    if (!Number.isFinite(n)) return "-";
    return String(Math.trunc(n));
  };

  const fmtMoney = (v) => {
    const n = Number(v);
    if (!Number.isFinite(n)) return "-";
    try {
      return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    } catch (_) {
      return n.toFixed(2);
    }
  };

  tr.innerHTML = `
    <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-700 dark:text-slate-300 font-medium font-mono">${_escapeHtml(symbol)}</td>
    <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-slate-600 dark:text-slate-400 font-mono">${_escapeHtml(range)}</td>
    <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono font-bold">${fmtPct(totalReturn)}</td>
    <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono">${fmtPct(annualizedReturn)}</td>
    <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono">${fmtPct(maxDrawdown, { clsBase: "text-green-600", signColor: false })}</td>
    <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono text-slate-600 dark:text-slate-400">${_escapeHtml(fmtInt(drawdownDuration))}</td>
    <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 font-mono text-slate-600 dark:text-slate-400">${_escapeHtml(maxDrawdownDate || "-")}</td>
    <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono text-slate-600 dark:text-slate-400">${_escapeHtml(fmtNum(sharpeRatio, 2))}</td>
    <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono text-slate-600 dark:text-slate-400">${_escapeHtml(fmtNum(expectancy, 4))}</td>
    <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono text-slate-600 dark:text-slate-400">${_escapeHtml(fmtNum(profitFactor, 2))}</td>
    <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono text-slate-600 dark:text-slate-400">${_escapeHtml(fmtNum(avgHoldDays, 1))}</td>
    <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono text-slate-700 dark:text-slate-300 font-bold">${_escapeHtml(fmtNum(score, 2))}</td>
    <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono text-slate-700 dark:text-slate-300">${_escapeHtml(fmtNum(scoreRobust, 2))}</td>
    <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono">${fmtPct(winRate)}</td>
    <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono text-slate-600 dark:text-slate-400">${_escapeHtml(fmtInt(trades))}</td>
    <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 font-mono text-slate-600 dark:text-slate-400">${_escapeHtml(`${String(Number.isFinite(Number(maxWinStreak)) ? Math.trunc(Number(maxWinStreak)) : 0)}/${String(Number.isFinite(Number(maxLossStreak)) ? Math.trunc(Number(maxLossStreak)) : 0)}`)}</td>
    <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 text-right font-mono text-slate-600 dark:text-slate-400">${_escapeHtml(fmtMoney(finalEquity))}</td>
    <td class="px-3 py-2 border-b border-slate-50 dark:border-slate-800/50 font-mono text-slate-600 dark:text-slate-400">${_escapeHtml(fmtInt(anomalies))}</td>
  `;
  tbody.appendChild(tr);
}

async function fetchBacktestDetailForSymbol(symbol) {
  const dataDir = val("bt-data-dir", "").trim();
  const beg = normalizeYmOrYmd(val("bt-beg", ""), "beg");
  const end = normalizeYmOrYmd(val("bt-end", ""), "end");

  const useIndex = boolv("bt-use-index", true);
  const indexData = val("bt-index-data", "").trim();
  const indexSymbol = val("bt-index-symbol", "000300.SH").trim();
  const calcScore = boolv("bt-calc-score", false);
  const calcRobust = boolv("bt-calc-robust", false);
  const robustSegments = intv("bt-robust-segments", 4);

  const config = {
    ...getStrategyConfigFromUI(),
    capture_logs: true,
    index_data: useIndex ? (indexData || null) : null,
    index_symbol: useIndex ? (indexSymbol || null) : null,
    calc_score: !!calcScore,
    calc_robust: !!calcRobust,
    robust_segments: Number.isFinite(Number(robustSegments)) ? Number(robustSegments) : 0,
  };

  const params = new URLSearchParams();
  params.set("symbol", symbol);
  params.set("data_dir", dataDir);
  params.set("config", JSON.stringify(config));
  if (beg) params.set("beg", beg);
  if (end) params.set("end", end);
  params.set("detail", "true");

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
    const useIndex = boolv("bt-use-index", true);
    const indexData = val("bt-index-data", "").trim();
    const indexSymbol = val("bt-index-symbol", "000300.SH").trim();
    const calcScore = boolv("bt-calc-score", false);
    const calcRobust = boolv("bt-calc-robust", false);
    const robustSegments = intv("bt-robust-segments", 4);

    const req = {
      data_dir: dataDir,
      symbols: parseSymbolsInput(val("bt-symbols", "")),
      beg: normalizeYmOrYmd(val("bt-beg", ""), "beg"),
      end: normalizeYmOrYmd(val("bt-end", ""), "end"),
      index_data: useIndex ? (indexData || null) : null,
      index_symbol: useIndex ? (indexSymbol || null) : null,
      calc_score: !!calcScore,
      calc_robust: !!calcRobust,
      robust_segments: Number.isFinite(Number(robustSegments)) ? Number(robustSegments) : 0,
      detail: false,
      ...getStrategyConfigFromUI()
    };
    
    if (symbolsOverride) req.symbols = symbolsOverride;
    await runBacktestTask(req, { statusEl: status, tbody, logsEl });
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
  initPresetSlotsAndVersioning();
  initDebugUI();
  initConfigParamHelpBinding();
  initRecentConfigKeyTracking();
  _smartLoadFileList();
  _poolInitUI();
  initBatchTasksPanel();
  initTaskCenterPanel();
  _renderDebugParamsPanel({ __input_params: getStrategyConfigFromUI(), __running_params: null });
  _renderBacktestParamsPanel({ __input_params: getStrategyConfigFromUI(), __running_params: null });
  
  // Bind Batch Test buttons
  const btnExp = document.getElementById("pt-export-btn");
  if(btnExp) btnExp.onclick = exportParamTestExcel;
  const btnGrid = document.getElementById("pt-grid-gen-btn");
  if(btnGrid) btnGrid.onclick = generateParamGrid;
  const btnRun = document.getElementById("pt-run-btn");
  if(btnRun) btnRun.onclick = runParamBatchTest;
  initParamBatchQuickInsert();
  initParamGridInputModes();
  
  // Bind Backtest button
  const btBtn = document.getElementById("bt-btn");
  if (btBtn) btBtn.onclick = () => runChannelHFBacktest();

  const btBody = document.getElementById("bt-results");
  if (btBody) {
    btBody.onclick = (ev) => {
      const t = ev.target;
      const row = t && typeof t.closest === "function" ? t.closest("tr") : null;
      const symbol = row && row.dataset ? row.dataset.symbol : null;
      if (symbol) _btLoadDetail(String(symbol));
    };
  }
  const btClear = document.getElementById("bt-detail-clear");
  if (btClear) btClear.onclick = () => _btClearDetail();
  _btClearDetail();

  const scanBody = document.getElementById("scan-results");
  if (scanBody) {
    scanBody.onclick = (ev) => {
      const t = ev.target;
      const row = t && typeof t.closest === "function" ? t.closest("tr") : null;
      if (!row || !row.dataset) return;
      let trace = [];
      try {
        trace = JSON.parse(row.dataset.trace || "[]");
      } catch (_) {
        trace = [];
      }
      const symbol = row.dataset.symbol || "-";
      const dt = row.dataset.date || "";
      _scanSetTraceVisible(true);
      _scanSetTraceStatus(`${symbol}${dt ? ` · ${dt}` : ""}`);
      _scanRenderTrace(trace);
    };
  }
  
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
  window.cancelBatchTask = cancelBatchTask;
  
  setActiveView("scan"); // Default view
}

document.addEventListener("DOMContentLoaded", initApp);
