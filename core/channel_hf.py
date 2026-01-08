from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

from .broker import PortfolioBroker
from .event_engine import EventStrategy, MarketFrame
from .types import Bar, Order, Side
import numpy as np


def calculate_volatility_ratio(close_prices: np.ndarray, short_window: int = 5, long_window: int = 20) -> tuple[float, float, float] | None:
    arr = np.asarray(close_prices, dtype=float)
    if arr.size < (int(long_window) + 1):
        return None

    prev = arr[:-1]
    nxt = arr[1:]
    if prev.size == 0:
        return None

    returns = (nxt / np.maximum(prev, 1e-12)) - 1.0
    sw = max(1, int(short_window))
    lw = max(1, int(long_window))
    if returns.size < max(sw, lw):
        return None

    short_ret = returns[-sw:]
    long_ret = returns[-lw:]
    short_vol = float(np.std(short_ret, ddof=1)) if short_ret.size > 1 else 0.0
    long_vol = float(np.std(long_ret, ddof=1)) if long_ret.size > 1 else 0.0
    ratio = 1.0 if long_vol == 0.0 else (short_vol / long_vol)
    return short_vol, long_vol, float(ratio)


@dataclass(frozen=True)
class ChannelHFConfig:
    channel_period: int = 20

    buy_touch_eps: float = 0.005
    sell_trigger_eps: float = 0.005
    sell_target_mode: str = "mid_up"
    channel_break_eps: float = 0.02

    stop_loss_mul: float = 0.97
    stop_loss_on_close: bool = True
    stop_loss_panic_eps: float = 0.02

    max_holding_days: int = 20
    cooling_period: int = 5
    scan_recent_days: int = 20

    slope_abs_max: float = 0.01
    vol_shrink_threshold: float = 0.9
    vol_shrink_min: float | None = None
    vol_shrink_max: float | None = None
    volatility_ratio_max: float = 1.0

    min_channel_height: float = 0.05
    min_mid_room: float = 0.015

    min_mid_profit_pct: float = 0.0
    min_rr_to_mid: float = 0.0
    min_slope_norm: float = -1.0

    pivot_k: int = 2
    pivot_drop_min: float = 0.03
    pivot_rebound_days: int = 2

    pivot_confirm_days: int = 3
    pivot_no_new_low_tol: float = 0.01
    pivot_rebound_amp: float = 0.02
    pivot_confirm_requires_sig: bool = True

    require_index_condition: bool = True
    index_symbol: str = "000300.SH"
    index_ma_5: int = 5
    index_ma_10: int = 10
    index_ma_20: int = 20
    index_ma_30: int = 30
    index_bear_exit: bool = True

    max_positions: int = 5
    max_position_pct: float = 1.0

    entry_fill_eps: float = 0.002
    exit_fill_eps: float = 0.002
    fill_at_close: bool = True
    capture_logs: bool = False
    
    trend_ma_period: int = 0  # 0 means disabled, e.g. 60 for MA60

    require_rebound: bool = False
    require_green: bool = False
    index_trend_ma_period: int = 0


class ChannelHFStrategy(EventStrategy):
    def __init__(self, bars: List[Bar], config: Optional[ChannelHFConfig] = None, index_bars: Optional[List[Bar]] = None) -> None:
        self.config = config or ChannelHFConfig()
        self.bars_by_symbol: Dict[str, List[Bar]] = {}
        for b in bars:
            self.bars_by_symbol.setdefault(b.symbol, []).append(b)

        self._closes_by_symbol: Dict[str, np.ndarray] = {}
        self._highs_by_symbol: Dict[str, np.ndarray] = {}
        self._lows_by_symbol: Dict[str, np.ndarray] = {}
        self._vols_by_symbol: Dict[str, np.ndarray] = {}
        for sym, blist in self.bars_by_symbol.items():
            self._closes_by_symbol[sym] = np.array([float(b.close) for b in blist], dtype=float)
            self._highs_by_symbol[sym] = np.array([float(b.high) for b in blist], dtype=float)
            self._lows_by_symbol[sym] = np.array([float(b.low) for b in blist], dtype=float)
            self._vols_by_symbol[sym] = np.array([float(b.volume or 0.0) for b in blist], dtype=float)

        self.positions_days: Dict[str, int] = {}
        self.signal_logs: List[dict] = []
        self.index_bars: Dict[date, Bar] = {}
        self._index_bear_by_dt: Dict[date, bool] = {}
        self._index_trend_val_by_dt: Dict[date, float] = {}
        if index_bars:
            sorted_index = sorted(index_bars, key=lambda b: b.dt)
            self.index_bars = {b.dt: b for b in sorted_index}

            dts = [b.dt for b in sorted_index]
            closes = [float(b.close) for b in sorted_index]

            def _sma_series(n: int) -> list[float | None]:
                n = int(n)
                if n <= 0:
                    return [None for _ in closes]
                out: list[float | None] = [None for _ in closes]
                s = 0.0
                for i, c in enumerate(closes):
                    s += c
                    if i >= n:
                        s -= closes[i - n]
                    if i >= n - 1:
                        out[i] = s / n
                return out

            ma5 = _sma_series(int(self.config.index_ma_5))
            ma10 = _sma_series(int(self.config.index_ma_10))
            ma20 = _sma_series(int(self.config.index_ma_20))
            ma30 = _sma_series(int(self.config.index_ma_30))
            ma_trend = _sma_series(int(self.config.index_trend_ma_period))

            for i, dt_val in enumerate(dts):
                if ma_trend[i] is not None:
                    self._index_trend_val_by_dt[dt_val] = float(ma_trend[i])

                a, b, c, d = ma5[i], ma10[i], ma20[i], ma30[i]
                if a is None or b is None or c is None or d is None:
                    continue
                self._index_bear_by_dt[dt_val] = bool(d > c > b > a)

        self.cooling_left: Dict[str, int] = {}

    @staticmethod
    @lru_cache(maxsize=64)
    def _linreg_x_cache(n: int) -> tuple[np.ndarray, float, float]:
        n = int(n)
        if n <= 0:
            return np.array([], dtype=float), 0.0, 0.0
        x = np.arange(n, dtype=float)
        x_mean = (float(n - 1) / 2.0) if n > 1 else 0.0
        x_centered = x - x_mean
        denom = float(np.dot(x_centered, x_centered))
        return x_centered, denom, x_mean

    def _fit_midline(self, closes: np.ndarray) -> tuple[float, float]:
        n = int(len(closes))
        if n < 2:
            return 0.0, float(closes[-1]) if n else 0.0

        x_centered, denom, x_mean = self._linreg_x_cache(n)
        y = closes.astype(float, copy=False)
        y_mean = float(np.mean(y))

        if denom <= 0.0:
            m = 0.0
        else:
            m = float(np.dot(x_centered, (y - y_mean)) / denom)

        c = y_mean - (m * x_mean)
        return float(m), float(c)

    def _pick_pivot_low(self, lows: np.ndarray, highs: np.ndarray) -> int | None:
        k = max(1, int(self.config.pivot_k))
        n = int(len(lows))
        if n < (2 * k + 3):
            return None

        candidates: List[Tuple[float, int]] = []
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
            if drop < max(0.0, float(self.config.pivot_drop_min)):
                continue

            rebound_days = max(1, int(self.config.pivot_rebound_days))
            after = lows[j + 1 : j + 1 + rebound_days]
            if after.size and float(np.min(after)) <= lj:
                continue

            candidates.append((lj, j))

        if not candidates:
            return None

        # Sort by price ascending, then by index descending (more recent first)
        candidates.sort(key=lambda x: (x[0], -x[1]))
        return candidates[0][1]

    def _get_channel_lines(self, symbol: str, i: int) -> tuple[float, float, float, float, float, int | None, int | None, float, bool] | None:
        if i is None:
            return None

        period = max(10, int(self.config.channel_period))
        if i + 1 < period:
            return None

        start = i - period + 1
        closes_all = self._closes_by_symbol.get(symbol)
        highs_all = self._highs_by_symbol.get(symbol)
        lows_all = self._lows_by_symbol.get(symbol)
        vols_all = self._vols_by_symbol.get(symbol)
        if closes_all is None or highs_all is None or lows_all is None or vols_all is None:
            return None

        closes = closes_all[start : i + 1]
        highs = highs_all[start : i + 1]
        lows = lows_all[start : i + 1]
        vols = vols_all[start : i + 1]

        m, c = self._fit_midline(closes)
        x_last = float(period - 1)
        mid = (m * x_last) + c
        slope_norm = (m / mid) if mid > 0 else 0.0

        pivot_pick = self._pick_pivot_low(lows, highs)
        pivot_is_sig = pivot_pick is not None
        pivot_j = pivot_pick
        if pivot_j is None:
            pivot_j = int(np.argmin(lows))

        pivot_low = float(lows[pivot_j])
        pivot_abs_i = int(start + int(pivot_j))

        pivot_mid = (m * float(pivot_j)) + c
        offset = pivot_low - pivot_mid

        lower = mid + offset
        upper = mid - offset

        avg_vol = float(np.mean(vols)) if len(vols) else 0.0
        cur_vol = float(vols[-1]) if len(vols) else 0.0
        vol_ratio = (cur_vol / avg_vol) if avg_vol > 0 else 1.0

        return mid, lower, upper, slope_norm, vol_ratio, pivot_j, pivot_abs_i, pivot_low, pivot_is_sig

    def _index_is_bear(self, dt_val: date) -> bool | None:
        if not self.index_bars:
            return None
        if dt_val not in self.index_bars:
            return None
        if dt_val not in self._index_bear_by_dt:
            return None
        return bool(self._index_bear_by_dt[dt_val])

    def on_open(self, i: int, frame: MarketFrame, broker: PortfolioBroker) -> None:
        for sym, pos in broker.positions.items():
            if pos.is_open:
                self.positions_days[sym] = self.positions_days.get(sym, 0) + 1
        for sym in frame.symbols:
            left = self.cooling_left.get(sym, 0)
            if left > 0:
                self.cooling_left[sym] = left - 1

    def on_close(self, i: int, frame: MarketFrame, broker: PortfolioBroker) -> List[Order]:
        orders: List[Order] = []

        sell_mode = str(getattr(self.config, "sell_target_mode", "mid_up") or "mid_up").strip().lower()

        def _sell_target_px(mid: float, upper: float) -> float:
            eps = max(0.0, float(self.config.sell_trigger_eps))
            if sell_mode == "mid_up":
                return mid * (1.0 + eps)
            if sell_mode == "upper_down":
                return upper * (1.0 - eps)
            return mid * (1.0 - eps)

        open_positions = [p for p in broker.positions.values() if p.is_open]
        open_count = len(open_positions)

        for symbol in frame.symbols:
            bar = frame.bars[symbol]
            dt = bar.dt

            ch = self._get_channel_lines(symbol, i)
            if not ch:
                continue

            mid, lower, upper, slope_norm, vol_ratio, pivot_j, pivot_abs_i, pivot_low, pivot_is_sig = ch

            # Tracing Setup
            cap_logs = bool(getattr(self.config, "capture_logs", False))
            log = None
            trace_steps = []
            
            def add_trace(step, check, threshold, actual, passed, reason=""):
                if cap_logs:
                    trace_steps.append({
                        "step": step,
                        "check": check,
                        "threshold": str(threshold),
                        "actual": str(actual),
                        "passed": bool(passed),
                        "reason": str(reason) if not passed else ""
                    })
                return passed

            index_bear = self._index_is_bear(dt)
            index_ok = True
            if self.config.require_index_condition and index_bear is True:
                index_ok = False
            
            # Trace Index
            add_trace("IndexFilter", "Index Not Bear", "False", str(index_bear), index_ok, "Index is Bearish")

            if self.config.index_trend_ma_period > 0:
                idx_ma = self._index_trend_val_by_dt.get(dt)
                idx_bar = self.index_bars.get(dt)
                if idx_ma is not None and idx_bar:
                    passed = idx_bar.close >= idx_ma
                    index_ok = index_ok and passed
                    add_trace("IndexMA", "Index > MA", f">{idx_ma:.2f}", f"{idx_bar.close:.2f}", passed, "Index below Trend MA")

            has_position = broker.positions.get(symbol) is not None and broker.positions[symbol].is_open

            channel_height = ((upper - lower) / mid) if mid > 0 else 0.0
            mid_room = ((mid - lower) / mid) if mid > 0 else 0.0

            vr_min = getattr(self.config, "vol_shrink_min", None)
            vr_max = getattr(self.config, "vol_shrink_max", None)
            vr_thr = float(getattr(self.config, "vol_shrink_threshold", 0.9))

            vol_ok = True
            vol_thr_text = ""
            vol_fail_reason = ""
            if vr_min is not None or vr_max is not None:
                mn = float(vr_min) if vr_min is not None else float("-inf")
                mx = float(vr_max) if vr_max is not None else float("inf")
                vol_ok = (float(vol_ratio) >= mn) and (float(vol_ratio) <= mx)
                vol_thr_text = f"[{mn:.2f}, {mx:.2f}]"
                if not vol_ok:
                    if float(vol_ratio) < mn:
                        vol_fail_reason = "低于下限"
                    elif float(vol_ratio) > mx:
                        vol_fail_reason = "高于上限"
                    else:
                        vol_fail_reason = "区间外"
            elif vr_thr > 0:
                if vr_thr >= 1.0:
                    vol_ok = float(vol_ratio) >= vr_thr
                    vol_thr_text = f">={vr_thr:.2f}"
                    if not vol_ok:
                        vol_fail_reason = "低于阈值"
                else:
                    vol_ok = float(vol_ratio) <= vr_thr
                    vol_thr_text = f"<={vr_thr:.2f}"
                    if not vol_ok:
                        vol_fail_reason = "高于阈值"
            if not vol_ok and not vol_fail_reason:
                vol_fail_reason = "量能条件失败"
            
            # Prepare Base Log
            if cap_logs:
                dt_str = dt.isoformat()
                log = {
                    "date": dt_str,
                    "symbol": symbol,
                    "mid": mid,
                    "upper": upper,
                    "lower": lower,
                    "open": bar.open,
                    "close": bar.close,
                    "low": bar.low,
                    "high": bar.high,
                    "has_position": bool(has_position),
                    "index_bear": index_bear,
                    "index_ok": index_ok,
                    "final_signal": 0,
                    "slope_norm": slope_norm,
                    "channel_height": channel_height,
                    "mid_room": mid_room,
                    "vol_ratio": vol_ratio,
                    "cooling_left": self.cooling_left.get(symbol, 0),
                    "pivot_j": pivot_j,
                    "pivot_abs_i": pivot_abs_i,
                    "pivot_low": pivot_low,
                    "pivot_is_sig": pivot_is_sig,
                    "trace": trace_steps # Link reference
                }

            if not has_position:
                # 1. Max Positions
                if not add_trace("MaxPos", "Open Count < Max", f"<{self.config.max_positions}", f"{open_count}", open_count < max(1, int(self.config.max_positions)), "Max positions reached"):
                    if log: self.signal_logs.append(log)
                    continue

                # 2. Cooling Period
                if not add_trace("Cooling", "Cooling Left == 0", "0", f"{self.cooling_left.get(symbol, 0)}", self.cooling_left.get(symbol, 0) <= 0, "In cooling period"):
                    if log: self.signal_logs.append(log)
                    continue
                
                # 3. Rebound Requirement
                if self.config.require_rebound:
                    if not add_trace("Rebound", "Close >= Lower", f">={lower:.2f}", f"{bar.close:.2f}", bar.close >= lower, "No rebound from lower"):
                        if log: self.signal_logs.append(log)
                        continue

                # 4. Green Candle Requirement
                if self.config.require_green:
                    if not add_trace("CandleColor", "Close > Open", f">{bar.open:.2f}", f"{bar.close:.2f}", bar.close > bar.open, "Not a green candle"):
                        if log: self.signal_logs.append(log)
                        continue
                
                vol_ratio_max = float(getattr(self.config, "volatility_ratio_max", 1.0))
                if vol_ratio_max < 1.0:
                    closes_all = self._closes_by_symbol.get(symbol)
                    close_slice = closes_all[: i + 1] if closes_all is not None else None
                    v = calculate_volatility_ratio(close_slice) if close_slice is not None else None
                    if v is None:
                        add_trace("Volatility", "Data Enough", ">=21 closes", f"{i + 1}", True)
                    else:
                        short_vol, long_vol, ratio = v
                        actual = f"{short_vol * 100:.2f}%/{long_vol * 100:.2f}%={ratio:.2f}"
                        if not add_trace("Volatility", "VolRatio <= Max", f"<={vol_ratio_max:.2f}", actual, ratio <= vol_ratio_max, "Volatility too high"):
                            if log: self.signal_logs.append(log)
                            continue

                # 5. Trend MA Filter
                ma_period = int(getattr(self.config, "trend_ma_period", 0))
                if ma_period > 0:
                    if i < ma_period - 1:
                        add_trace("TrendMA", "Data Enough", f">={ma_period}", f"{i+1}", False, "Not enough data for MA")
                        if log: self.signal_logs.append(log)
                        continue
                    
                    closes_all = self._closes_by_symbol.get(symbol)
                    start_idx = i - ma_period + 1
                    ma_slice = closes_all[start_idx : i + 1]
                    ma_val = float(np.mean(ma_slice))
                    
                    if not add_trace("TrendMA", "Close >= MA", f">={ma_val:.2f}", f"{bar.close:.2f}", bar.close >= ma_val, "Price below Trend MA"):
                        if log: self.signal_logs.append(log)
                        continue

                # 6. Slope Min
                min_slope_norm = float(self.config.min_slope_norm)
                if min_slope_norm > -1.0:
                    if not add_trace("SlopeMin", "Slope >= Min", f">={min_slope_norm:.4f}", f"{slope_norm:.4f}", float(slope_norm) >= min_slope_norm, "Slope too negative"):
                        if log: self.signal_logs.append(log)
                        continue

                # 7. Slope Abs Max
                if not add_trace("SlopeMax", "Abs(Slope) <= Max", f"<={self.config.slope_abs_max:.4f}", f"{abs(float(slope_norm)):.4f}", abs(float(slope_norm)) <= max(0.0, float(self.config.slope_abs_max)), "Slope too steep"):
                    if log: self.signal_logs.append(log)
                    continue

                # 8. Channel Height
                if not add_trace("ChanHeight", "Height >= Min", f">={self.config.min_channel_height:.3f}", f"{channel_height:.3f}", channel_height >= max(0.0, float(self.config.min_channel_height)), "Channel too narrow"):
                    if log: self.signal_logs.append(log)
                    continue

                # 9. Mid Room
                if not add_trace("MidRoom", "Room >= Min", f">={self.config.min_mid_room:.3f}", f"{mid_room:.3f}", mid_room >= max(0.0, float(self.config.min_mid_room)), "Not enough room to mid"):
                    if log: self.signal_logs.append(log)
                    continue
                
                # 10. Volume Shrink
                if not add_trace("VolumeShrinkFilter", "VolRatio Check", vol_thr_text, f"{vol_ratio:.2f}", vol_ok, vol_fail_reason):
                    if log: self.signal_logs.append(log)
                    continue

                # 11. Touch Lower
                touch_px = lower * (1.0 + max(0.0, float(self.config.buy_touch_eps)))
                touch_ok = bar.low <= touch_px
                if not add_trace("TouchLowerFilter", "Low <= TouchPx", f"<={touch_px:.2f}", f"{bar.low:.2f}", touch_ok, "Did not touch lower band"):
                     if log: self.signal_logs.append(log)
                     continue
                
                # 12. Index Confirmation (Already checked but need to block here)
                if not add_trace("IndexConfirm", "Index OK", "True", str(index_ok), index_ok, "Index not confirmed"):
                    if log: self.signal_logs.append(log)
                    continue

                # 13. Pivot Confirmation
                confirm_days = int(getattr(self.config, "pivot_confirm_days", 0))
                if confirm_days > 0:
                    req_sig = bool(getattr(self.config, "pivot_confirm_requires_sig", True))
                    if req_sig:
                         if not add_trace("PivotSig", "Is Significant", "True", str(pivot_is_sig), bool(pivot_is_sig), "Not a significant pivot"):
                            if log: self.signal_logs.append(log)
                            continue

                    if pivot_abs_i is None or i - int(pivot_abs_i) < confirm_days - 1:
                        # Too recent or invalid
                         add_trace("PivotDays", "Confirmed Days", f">={confirm_days}", f"{i - int(pivot_abs_i) + 1 if pivot_abs_i is not None else 0}", False, "Pivot too recent")
                         if log: self.signal_logs.append(log)
                         continue
                    
                    add_trace("PivotDays", "Confirmed Days", f">={confirm_days}", f"{i - int(pivot_abs_i) + 1}", True)

                    start_i = max(int(pivot_abs_i), i - confirm_days + 1)
                    lows_all = self._lows_by_symbol.get(symbol)
                    highs_all = self._highs_by_symbol.get(symbol)
                    
                    if lows_all is not None and highs_all is not None:
                        win_lows = lows_all[start_i : i + 1]
                        win_highs = highs_all[start_i : i + 1]

                        tol = max(0.0, float(getattr(self.config, "pivot_no_new_low_tol", 0.01)))
                        min_low = float(np.min(win_lows)) if win_lows.size else float(bar.low)
                        
                        if not add_trace("NoNewLow", "MinLow >= Pivot*(1-Tol)", f">={float(pivot_low) * (1.0 - tol):.2f}", f"{min_low:.2f}", min_low >= float(pivot_low) * (1.0 - tol), "New low formed"):
                            if log: self.signal_logs.append(log)
                            continue

                        amp_req = max(0.0, float(getattr(self.config, "pivot_rebound_amp", 0.02)))
                        max_high = float(np.max(win_highs)) if win_highs.size else float(bar.high)
                        amp = (max_high / float(pivot_low)) - 1.0 if float(pivot_low) > 0 else 0.0
                        
                        if not add_trace("ReboundAmp", "Amp >= Req", f">={amp_req:.3f}", f"{amp:.3f}", amp >= amp_req, "Rebound too weak"):
                            if log: self.signal_logs.append(log)
                            continue

                entry_px = bar.close * (1.0 + max(0.0, float(self.config.entry_fill_eps)))
                target_px = _sell_target_px(mid, upper)

                # 14. Min Profit
                min_mid_profit_pct = max(0.0, float(self.config.min_mid_profit_pct))
                if min_mid_profit_pct > 0.0:
                    profit_pct = (target_px / entry_px) - 1.0 if entry_px > 0 else -1.0
                    if not add_trace("MinProfit", "Profit% >= Min", f">={min_mid_profit_pct:.3f}", f"{profit_pct:.3f}", profit_pct >= min_mid_profit_pct, "Potential profit too low"):
                        if log: self.signal_logs.append(log)
                        continue

                # 15. Min RR
                min_rr_to_mid = max(0.0, float(self.config.min_rr_to_mid))
                if min_rr_to_mid > 0.0:
                    stop_mul = max(0.0, float(self.config.stop_loss_mul))
                    initial_stop = entry_px * stop_mul
                    risk = entry_px - initial_stop
                    reward = target_px - entry_px
                    rr = (reward / risk) if risk > 0 else -1.0
                    if not add_trace("MinRR", "RR >= Min", f">={min_rr_to_mid:.2f}", f"{rr:.2f}", rr >= min_rr_to_mid, "Risk/Reward too low"):
                        if log: self.signal_logs.append(log)
                        continue

                # EXECUTE BUY
                scale = 1.0
                target_notional = broker.equity * max(0.0, float(self.config.max_position_pct)) * scale
                lot = max(1, int(broker.config.lot_size))
                qty = int(target_notional / max(0.01, entry_px))
                qty = (qty // lot) * lot
                if qty < lot:
                    qty = 0

                if qty > 0:
                    initial_stop = entry_px * max(0.0, float(self.config.stop_loss_mul))

                    order = Order(
                        symbol=symbol,
                        qty=qty,
                        side=Side.BUY,
                        dt=bar.dt,
                        reason="BuyLower",
                        initial_stop=initial_stop,
                        limit_price=(entry_px if self.config.fill_at_close else None),
                    )
                    orders.append(order)
                    if log is not None:
                        log["final_signal"] = 1
                        add_trace("FinalDecision", "Buy", "-", "-", True, "All conditions passed")

            else:
                pos = broker.positions[symbol]
                qty = int(pos.qty)

                exit_reason = None

                if self.config.index_bear_exit and (index_bear is True):
                    exit_reason = "IndexBear"

                if exit_reason is None and pos.initial_stop is not None:
                    stop_px = float(pos.initial_stop)
                    panic_eps = max(0.0, float(self.config.stop_loss_panic_eps))

                    if panic_eps > 0.0 and bar.low <= stop_px * (1.0 - panic_eps):
                        exit_reason = "StopLossPanic"
                    else:
                        if bool(self.config.stop_loss_on_close):
                            if bar.close <= stop_px:
                                exit_reason = "StopLoss"
                        else:
                            if bar.low <= stop_px:
                                exit_reason = "StopLoss"

                days = int(self.positions_days.get(symbol, 0))
                if exit_reason is None and days >= max(1, int(self.config.max_holding_days)):
                    exit_reason = "TimeExit"

                target_px = _sell_target_px(mid, upper)
                if exit_reason is None and bar.high >= target_px:
                    exit_reason = "SellTarget"

                break_px = lower * (1.0 - max(0.0, float(self.config.channel_break_eps)))
                if exit_reason is None and bar.close < break_px:
                    exit_reason = "ChannelBreak"

                if exit_reason is not None and qty > 0:
                    exit_px = bar.close * (1.0 - max(0.0, float(self.config.exit_fill_eps)))
                    orders.append(
                        Order(
                            symbol=symbol,
                            qty=qty,
                            side=Side.SELL,
                            dt=bar.dt,
                            reason=exit_reason,
                            # 卖出使用市价单，确保立即执行（不管高低），避免跳空低开无法离场
                            limit_price=None,
                        )
                    )
                    if log is not None:
                        if exit_reason == "IndexBear":
                            add_trace("Exit", "IndexBear", "True", str(index_bear), True, "")
                        elif exit_reason == "StopLossPanic" and pos.initial_stop is not None:
                            stop_px = float(pos.initial_stop)
                            panic_eps = max(0.0, float(self.config.stop_loss_panic_eps))
                            thr = stop_px * (1.0 - panic_eps)
                            add_trace("Exit", "Panic Stop", f"<={thr:.2f}", f"{bar.low:.2f}", True, "")
                        elif exit_reason == "StopLoss" and pos.initial_stop is not None:
                            stop_px = float(pos.initial_stop)
                            if bool(self.config.stop_loss_on_close):
                                add_trace("Exit", "Close <= Stop", f"<={stop_px:.2f}", f"{bar.close:.2f}", True, "")
                            else:
                                add_trace("Exit", "Low <= Stop", f"<={stop_px:.2f}", f"{bar.low:.2f}", True, "")
                        elif exit_reason == "TimeExit":
                            add_trace("Exit", "Holding Days", f">={max(1, int(self.config.max_holding_days))}", f"{days}", True, "")
                        elif exit_reason == "SellTarget":
                            add_trace("Exit", "High >= Target", f">={target_px:.2f}", f"{bar.high:.2f}", True, "")
                        elif exit_reason == "ChannelBreak":
                            add_trace("Exit", "Close < Break", f"<{break_px:.2f}", f"{bar.close:.2f}", True, "")
                        log["final_signal"] = -1
                    self.positions_days[symbol] = 0
                    self.cooling_left[symbol] = max(0, int(self.config.cooling_period))

            if log is not None:
                self.signal_logs.append(log)

        return orders
