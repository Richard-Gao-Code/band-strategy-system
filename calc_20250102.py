import sys
import os
import csv
import numpy as np
from datetime import datetime, date
from pathlib import Path

sys.path.append(os.getcwd())

from core.channel_hf import ChannelHFConfig, ChannelHFStrategy
from core.types import Bar

def parse_date(d_str):
    return datetime.strptime(d_str, "%Y-%m-%d").date()

def main():
    # 1. Load Data
    csv_path = Path("data/000001.SZ.csv")
    bars = []
    
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row: continue
            try:
                dt = parse_date(row[0])
                b = Bar(
                    symbol="000001.SZ",
                    dt=dt,
                    open=float(row[4]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[1]),
                    volume=float(row[5])
                )
                bars.append(b)
            except:
                pass
    
    bars.sort(key=lambda x: x.dt)
    
    target_date = date(2024, 12, 31)
    bars_main = [b for b in bars if b.dt <= target_date]
    
    if not bars_main:
        print("No data found!")
        return

    # 2. Config
    cfg = ChannelHFConfig(
        channel_period=30,
        min_slope_norm=-0.01,
        vol_shrink_threshold=0.9,
        pivot_k=2,
        pivot_drop_min=0.03,
        pivot_rebound_days=2,
        min_channel_height=0.05,
        min_mid_room=0.015,
        buy_touch_eps=0.005,
        sell_trigger_eps=0.005,
        stop_loss_mul=0.97,
        channel_break_eps=0.02
    )
    
    strategy = ChannelHFStrategy(bars_main, config=cfg)
    
    # 3. Core Data Table (Last 3 days)
    indices_to_check = range(len(bars_main) - 3, len(bars_main))
    
    print("核心数据表（最后3个交易日）:")
    print(f"{'Date':<12} | {'Close':<8} | {'Mid':<8} | {'Lower':<8} | {'Height%':<8} | {'Room%':<8} | {'Signal'}")
    print("-" * 90)
    
    for i in indices_to_check:
        if i < 0: continue
        bar = bars_main[i]
        res = strategy._get_channel_lines(bar.symbol, i)
        
        if not res:
            print(f"{bar.dt} | N/A")
            continue
            
        mid, lower, upper, slope_norm, vol_ratio, pivot_j = res
        
        height_pct = (upper - lower) / mid if mid > 0 else 0
        room_pct = (mid - lower) / mid if mid > 0 else 0
        
        # Check Signal
        ok_slope = slope_norm >= cfg.min_slope_norm
        ok_vol = vol_ratio <= cfg.vol_shrink_threshold
        ok_height = height_pct >= cfg.min_channel_height
        ok_room = room_pct >= cfg.min_mid_room
        
        buy_price = lower * (1.0 + cfg.buy_touch_eps)
        ok_touch = bar.low <= buy_price
        
        break_price = lower * (1.0 - cfg.channel_break_eps)
        ok_break = bar.close < break_price
        
        is_signal = ok_slope and ok_vol and ok_height and ok_room and ok_touch and (not ok_break)
        
        print(f"{bar.dt} | {bar.close:<8.2f} | {mid:<8.2f} | {lower:<8.2f} | {height_pct*100:<7.2f}% | {room_pct*100:<7.2f}% | {is_signal}")

    # 4. Key Logic Verification for 2024-12-31
    print("\n关键逻辑点验证 (2024-12-31):")
    idx_31 = len(bars_main) - 1
    bar_31 = bars_main[idx_31]
    
    period = 30
    start_idx = idx_31 - period + 1
    end_idx = idx_31
    
    start_date = bars_main[start_idx].dt
    end_date = bars_main[end_idx].dt
    print(f"1. 30天窗口: {start_date} 至 {end_date} (共{end_idx - start_idx + 1}天)")
    
    highs = strategy._highs_by_symbol["000001.SZ"][start_idx : end_idx + 1]
    lows = strategy._lows_by_symbol["000001.SZ"][start_idx : end_idx + 1]
    
    print("2. 窗口内识别出的所有显著低点:")
    k = cfg.pivot_k
    n = len(lows)
    
    candidates = []
    # Replicate logic to show all
    for j in range(k, n - k - 1):
        lj = float(lows[j])
        if lj <= 0: continue
        
        left = lows[j - k : j]
        right = lows[j + 1 : j + 1 + k]
        if not (lj < np.min(left) and lj < np.min(right)):
            continue
            
        prev_peak = np.max(highs[: j + 1])
        drop = (prev_peak / lj) - 1.0
        if drop < cfg.pivot_drop_min:
            continue
            
        rebound_days = cfg.pivot_rebound_days
        after = lows[j + 1 : j + 1 + rebound_days]
        if after.size and np.min(after) <= lj:
            continue
            
        abs_idx = start_idx + j
        d = bars_main[abs_idx].dt
        candidates.append((d, lj, j))
        print(f"   - 日期: {d}, 价格: {lj:.2f}")
        
    if not candidates:
        print("   (无)")
    else:
        # Sort to show who should win
        # Price asc, then index desc (larger j is more recent)
        candidates.sort(key=lambda x: (x[1], -x[2]))
        best_cand = candidates[0]
        print(f"   -> 根据规则(最低价优先，同价取近)，应选: {best_cand[0]} (Price: {best_cand[1]:.2f})")
        
    res_31 = strategy._get_channel_lines(bar_31.symbol, idx_31)
    mid, lower, upper, slope_norm, vol_ratio, pivot_j = res_31
    
    sel_abs_idx = start_idx + pivot_j
    sel_bar = bars_main[sel_abs_idx]
    print(f"3. 最终选中的显著低点:")
    print(f"   日期: {sel_bar.dt}, 价格: {sel_bar.low:.2f}")
    
    m = slope_norm * mid
    print(f"4. 通道斜率:")
    print(f"   原始斜率 (Raw): {m:.5f}")
    print(f"   归一化斜率 (Norm): {slope_norm:.5f}")

if __name__ == "__main__":
    main()