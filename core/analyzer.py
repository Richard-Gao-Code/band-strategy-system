import csv
import math
import json
from dataclasses import dataclass, fields
from pathlib import Path
import numpy as np

@dataclass(frozen=True)
class SignalConfig:
    channel_period: int = 20
    buy_touch_eps: float = 0.005
    min_channel_height: float = 0.05
    min_mid_room: float = 0.015
    slope_abs_max: float = 0.01
    pivot_k: int = 2
    pivot_drop_min: float = 0.03
    pivot_rebound_days: int = 2
    vol_shrink_threshold: float = 0.9
    vol_shrink_min: float | None = None
    vol_shrink_max: float | None = None
    channel_break_eps: float = 0.02

def _load_system_config() -> SignalConfig:
    """Load config.json from project root if exists"""
    try:
        # core/analyzer.py -> core -> channel_hf_webui
        root = Path(__file__).resolve().parent.parent
        config_path = root / "config.json"
        
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            # Filter keys that match SignalConfig fields
            valid_keys = {f.name for f in fields(SignalConfig)}
            filtered_data = {k: v for k, v in data.items() if k in valid_keys}
            
            # Use default for missing keys
            return SignalConfig(**filtered_data)
    except Exception as e:
        print(f"Error loading config.json: {e}")
    
    return SignalConfig()

def reload_config():
    global SIG_CONFIG
    SIG_CONFIG = _load_system_config()

SIG_CONFIG = _load_system_config()

@dataclass
class AnalysisResult:
    symbol: str
    date: str
    close: float
    low: float
    lower: float
    mid: float
    upper: float
    height: float
    slope: float
    vol_ratio: float
    dist_to_lower: float
    height_ok: bool
    slope_ok: bool
    vol_ok: bool
    touch_ok: bool
    
    @property
    def status_desc(self) -> str:
        if self.close > self.mid:
            return "Hold (Above Mid)"
        elif self.close > self.lower:
            return "Hold (Below Mid)"
        else:
            return "Below Lower (Possible Buy)"

def _linreg_x_cache(n: int) -> tuple[np.ndarray, float, float]:
    n = int(n)
    if n <= 0:
        return np.array([], dtype=float), 0.0, 0.0
    x = np.arange(n, dtype=float)
    x_mean = (float(n - 1) / 2.0) if n > 1 else 0.0
    x_centered = x - x_mean
    denom = float(np.dot(x_centered, x_centered))
    return x_centered, denom, x_mean

def _fit_midline(closes: np.ndarray) -> tuple[float, float]:
    n = int(len(closes))
    if n < 2:
        return 0.0, float(closes[-1]) if n else 0.0

    x_centered, denom, x_mean = _linreg_x_cache(n)
    y = closes.astype(float, copy=False)
    y_mean = float(np.mean(y))

    if denom <= 0.0:
        m = 0.0
    else:
        m = float(np.dot(x_centered, (y - y_mean)) / denom)

    c = y_mean - (m * x_mean)
    return float(m), float(c)

def _pick_pivot_low(lows: np.ndarray, highs: np.ndarray) -> int | None:
    k = max(1, int(SIG_CONFIG.pivot_k))
    n = int(len(lows))
    if n < (2 * k + 3):
        return None

    best: int | None = None
    for j in range(k, n - k - 1):
        lj = float(lows[j])
        if lj <= 0:
            continue

        left = lows[j - k : j]
        right = lows[j + 1 : j + 1 + k]
        if left.size == 0 or right.size == 0:
            continue
        if not (lj < float(np.min(left)) and lj < float(np.min(right))):
            continue

        prev_peak = float(np.max(highs[: j + 1])) if j >= 1 else float(highs[0])
        if prev_peak <= 0:
            continue
        drop = (prev_peak / lj) - 1.0
        if drop < max(0.0, float(SIG_CONFIG.pivot_drop_min)):
            continue

        rebound_days = max(1, int(SIG_CONFIG.pivot_rebound_days))
        after = lows[j + 1 : j + 1 + rebound_days]
        if after.size and float(np.min(after)) <= lj:
            continue

        best = j

    return best

def calculate_channel(data: list[dict]):
    period = SIG_CONFIG.channel_period
    if len(data) < period:
        return None

    closes = np.array([d["close"] for d in data[-period:]], dtype=float)
    highs = np.array([d["high"] for d in data[-period:]], dtype=float)
    lows = np.array([d["low"] for d in data[-period:]], dtype=float)
    vols = np.array([d["vol"] for d in data[-period:]], dtype=float)

    m, c = _fit_midline(closes)
    x_last = float(period - 1)
    mid = (m * x_last) + c
    slope_norm = (m / mid) if mid > 0 else 0.0

    pivot_j = _pick_pivot_low(lows, highs)
    if pivot_j is None:
        pivot_j = int(np.argmin(lows))

    pivot_low = float(lows[pivot_j])
    pivot_mid = (m * float(pivot_j)) + c
    offset = pivot_low - pivot_mid

    lower = mid + offset
    upper = mid - offset
    
    avg_vol = float(np.mean(vols)) if len(vols) else 0.0
    cur_vol = float(vols[-1]) if len(vols) else 0.0
    vol_ratio = (cur_vol / avg_vol) if avg_vol > 0 else 1.0

    return {
        "mid": mid,
        "lower": lower,
        "upper": upper,
        "slope_norm": slope_norm,
        "vol_ratio": vol_ratio
    }

def read_stock_csv(path: Path):
    rows = []
    if not path.exists():
        # print(f"File not found: {path}") # Silent fail or let caller handle
        return []
    
    with path.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            dt_str = r.get("date") or r.get("trade_date") or r.get("Date")
            try:
                close = float(r.get("close") or r.get("Close"))
                high = float(r.get("high") or r.get("High"))
                low = float(r.get("low") or r.get("Low"))
                vol = float(r.get("volume") or r.get("Volume") or r.get("vol") or 0)
            except:
                continue
            
            if dt_str and close > 0:
                rows.append({
                    "dt": dt_str,
                    "close": close,
                    "high": high,
                    "low": low,
                    "vol": vol
                })
    return rows

def get_stock_analysis(symbol: str, csv_path: Path) -> AnalysisResult | None:
    data = read_stock_csv(csv_path)
    if not data:
        return None

    data.sort(key=lambda x: x["dt"])
    last_bar = data[-1]
    ch = calculate_channel(data)
    
    if not ch:
        return None

    mid = ch["mid"]
    lower = ch["lower"]
    upper = ch["upper"]
    slope = ch["slope_norm"]
    vol_r = ch["vol_ratio"]
    
    close = last_bar["close"]
    low = last_bar["low"]
    
    channel_height = ((upper - lower) / mid) if mid > 0 else 0.0
    
    touch_px = lower * (1.0 + SIG_CONFIG.buy_touch_eps)
    touch_ok = low <= touch_px
    
    height_ok = channel_height >= SIG_CONFIG.min_channel_height
    slope_ok = abs(slope) <= SIG_CONFIG.slope_abs_max
    if SIG_CONFIG.vol_shrink_min is not None or SIG_CONFIG.vol_shrink_max is not None:
        mn = float(SIG_CONFIG.vol_shrink_min) if SIG_CONFIG.vol_shrink_min is not None else float("-inf")
        mx = float(SIG_CONFIG.vol_shrink_max) if SIG_CONFIG.vol_shrink_max is not None else float("inf")
        vol_ok = bool(float(vol_r) >= mn and float(vol_r) <= mx)
    else:
        vol_ok = vol_r <= SIG_CONFIG.vol_shrink_threshold

    dist_to_lower = (close - lower) / lower if lower > 0 else 0.0
    
    return AnalysisResult(
        symbol=symbol,
        date=last_bar["dt"],
        close=close,
        low=low,
        lower=lower,
        mid=mid,
        upper=upper,
        height=channel_height,
        slope=slope,
        vol_ratio=vol_r,
        dist_to_lower=dist_to_lower,
        height_ok=height_ok,
        slope_ok=slope_ok,
        vol_ok=vol_ok,
        touch_ok=touch_ok
    )
