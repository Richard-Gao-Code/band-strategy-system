import sys
import os
import csv
import numpy as np
from datetime import datetime, date
from pathlib import Path

import json

# Ensure we can import from core
sys.path.append(os.getcwd())

from dataclasses import fields

from core.channel_hf import ChannelHFConfig, ChannelHFStrategy
from core.types import Bar

def load_config():
    config_path = Path(__file__).parent / "config.json"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}

def parse_date(d_str):
    try:
        return datetime.strptime(d_str, "%Y-%m-%d").date()
    except:
        return None

def load_bars(symbol):
    csv_path = Path(__file__).parent / "data" / f"{symbol}.csv"
    if not csv_path.exists():
        return None
        
    bars = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row: continue
            try:
                dt = parse_date(row[0])
                if not dt: continue
                if len(row) < 6: continue
                
                b = Bar(
                    symbol=symbol,
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
    return bars

def check_stock(symbol, target_date_str="2024-12-31"):
    print(f"\n=== 股票 {symbol} ({target_date_str}) 信号生成详情 ===")
    
    target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    bars = load_bars(symbol)
    
    if not bars:
        print("Error: 数据文件不存在或为空")
        return

    # 1. 基础数据检查
    idx_target = -1
    for i, b in enumerate(bars):
        if b.dt == target_date:
            idx_target = i
            break
            
    if idx_target == -1:
        print(f"Error: 未找到目标日期 {target_date} 的数据")
        return
        
    # Load config from file to match UI
    config_dict = load_config()
    # Default fallback if config file is missing or partial
    # 完全从config.json加载，不设置任何硬编码默认值
    default_config = {}
    # Update defaults with loaded config
    default_config.update(config_dict)
    
    # Force disable index confirm for single stock debug if desired, 
    # BUT user actually wanted to test 601000 with index bear check in previous turn?
    # Actually user said "I closed index confirm" in this turn.
    # So we should respect config.json's require_index_confirm (which is now false).
    
    allowed = {f.name for f in fields(ChannelHFConfig)}
    clean_config = {k: v for k, v in default_config.items() if k in allowed}
    cfg = ChannelHFConfig(**clean_config)
    print(f"[Config] channel_period={cfg.channel_period}, require_index_condition={cfg.require_index_condition}")
    print(f"[Config] slope_abs_max={cfg.slope_abs_max}, min_slope_norm={cfg.min_slope_norm}, vol_shrink_threshold={cfg.vol_shrink_threshold}")
    
    period = cfg.channel_period
    start_idx = idx_target - period + 1
    if start_idx < 0:
        print(f"Error: 历史数据不足，需要 {period} 天，仅有 {idx_target + 1} 天")
        return
        
    start_date = bars[start_idx].dt
    print("[1] 基础数据检查：")
    print(f"    - 计算窗口：{start_date} 至 {target_date}")
    print(f"    - 数据完整性：{period}/{period} ✅")
    
    # 2. 核心算法输出
    strategy = ChannelHFStrategy(bars, config=cfg)
    res = strategy._get_channel_lines(symbol, idx_target)
    
    if not res:
        print("Error: 通道计算失败")
        return
        
    mid, lower, upper, slope_norm, vol_ratio, pivot_j = res
    
    pivot_abs_idx = start_idx + pivot_j
    pivot_bar = bars[pivot_abs_idx]
    
    print("\n[2] 核心算法输出：")
    print(f"    - 显著低点：{pivot_bar.dt}, 价格 {pivot_bar.low:.2f}")
    print(f"    - 中轨值：{mid:.2f}")
    print(f"    - 下轨值：{lower:.2f}")
    print(f"    - 上轨值：{upper:.2f}")
    print(f"    - 归一化斜率：{slope_norm:.4f}")
    print(f"    - 量比：{vol_ratio:.2f}")

    # 3. 过滤条件逐一检查
    print("\n[3] 过滤条件逐一检查：")
    
    bar = bars[idx_target]
    
    # Height
    height_pct = ((upper - lower) / mid) if mid > 0 else 0.0
    ok_height = height_pct >= cfg.min_channel_height
    mark = "✅" if ok_height else "❌"
    print(f"    - 通道高度 >= {cfg.min_channel_height*100}%：{height_pct*100:.2f}% {mark}")
    
    # Room
    room_pct = ((mid - lower) / mid) if mid > 0 else 0.0
    ok_room = room_pct >= cfg.min_mid_room
    mark = "✅" if ok_room else "❌"
    print(f"    - 下轨-中轨空间 >= {cfg.min_mid_room*100}%：{room_pct*100:.2f}% {mark}")
    
    # Slope
    min_s = cfg.min_slope_norm
    max_s = cfg.slope_abs_max # Note: config calls it slope_abs_max but logic uses it as max abs value?
    # Logic in code: if abs(slope_norm) > slope_abs_max: continue
    # And: if slope_norm < min_slope_norm: continue
    
    ok_slope_min = slope_norm >= min_s
    ok_slope_max = abs(slope_norm) <= max_s
    ok_slope = ok_slope_min and ok_slope_max
    
    mark = "✅" if ok_slope else "❌"
    print(f"    - 归一化斜率 ∈ [{min_s}, {max_s}]：{slope_norm:.4f} {mark}")
    if not ok_slope_min: print(f"      -> 失败原因：斜率 < {min_s}")
    if not ok_slope_max: print(f"      -> 失败原因：绝对值 > {max_s}")
    
    # Vol
    vr_thresh = cfg.vol_shrink_threshold
    ok_vol = vol_ratio <= vr_thresh
    mark = "✅" if ok_vol else "❌"
    print(f"    - 量能收缩 <= {vr_thresh}：{vol_ratio:.2f} {mark}")
    
    # Touch
    buy_price = lower * (1.0 + cfg.buy_touch_eps)
    ok_touch = bar.low <= buy_price
    mark = "✅" if ok_touch else "❌"
    print(f"    - 触碰下轨 (Low <= Lower*{1+cfg.buy_touch_eps:.3f})：")
    print(f"      Low({bar.low}) <= BuyPrice({buy_price:.2f}) {mark}")
    
    # Not Break
    break_price = lower * (1.0 - cfg.channel_break_eps)
    ok_break = bar.close < break_price
    # We want NOT break
    mark = "✅" if not ok_break else "❌"
    print(f"    - 未跌破下轨 (Close >= Lower*{1-cfg.channel_break_eps:.2f})：")
    print(f"      Close({bar.close}) >= BreakPrice({break_price:.2f}) {mark}")
    
    # 4. Final
    is_signal = ok_height and ok_room and ok_slope and ok_vol and ok_touch and (not ok_break)
    print("\n[4] 最终信号汇总：")
    print(f"    - 所有条件通过：{'是' if is_signal else '否'}")
    print(f"    - Signal：{is_signal}")

def main():
    # 601000.SH @ 2024-01-23 (Checking IndexBear)
    check_stock("601000.SH", "2024-01-23")
    
    # 002624.SZ @ 2024-01-22 (Checking Slope)
    check_stock("002624.SZ", "2024-01-22")
    check_stock("300725.SZ")
    check_stock("300496.SZ")

if __name__ == "__main__":
    main()