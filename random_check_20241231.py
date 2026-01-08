import sys
import os
import csv
import random
import glob
import numpy as np
from datetime import datetime, date
from pathlib import Path

sys.path.append(os.getcwd())

from core.channel_hf import ChannelHFConfig, ChannelHFStrategy
from core.types import Bar

def parse_date(d_str):
    try:
        return datetime.strptime(d_str, "%Y-%m-%d").date()
    except:
        return None

def load_bars(csv_path):
    bars = []
    symbol = os.path.basename(csv_path).replace(".csv", "")
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row: continue
            try:
                dt = parse_date(row[0])
                if not dt: continue
                
                # Check row length to avoid index errors
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

def main():
    # 1. Get pool
    all_csvs = glob.glob("data/*.csv")
    pool = [f for f in all_csvs if "universe.csv" not in f]
    
    if len(pool) < 10:
        print(f"Pool size too small: {len(pool)}")
        return
        
    # Random sample 10
    selected_files = random.sample(pool, 10)
    
    target_date = date(2024, 12, 31)
    
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
    
    results = []
    
    print(f"{'Symbol':<10} | {'Height%':<8} | {'Room%':<8} | {'Signal':<6} | {'Remark'}")
    print("-" * 60)
    
    pass_count = 0
    
    for csv_file in selected_files:
        bars = load_bars(csv_file)
        if not bars:
            print(f"{os.path.basename(csv_file):<10} | {'N/A':<8} | {'N/A':<8} | {'N/A':<6} | No Data")
            continue
            
        # Find index of target date
        idx_target = -1
        for i, b in enumerate(bars):
            if b.dt == target_date:
                idx_target = i
                break
                
        if idx_target == -1:
            # If date not found, maybe data ends earlier or starts later
            # Try to find closest previous date? No, strict check for now
            print(f"{bars[0].symbol:<10} | {'N/A':<8} | {'N/A':<8} | {'N/A':<6} | Date Not Found")
            continue
            
        # Run strategy logic for this point
        # We need enough history
        if idx_target < cfg.channel_period:
             print(f"{bars[0].symbol:<10} | {'N/A':<8} | {'N/A':<8} | {'N/A':<6} | Insufficient History")
             continue
             
        # Need to pass bars up to target (or all bars) to strategy
        # Passing all bars is fine, we just query at idx_target
        strategy = ChannelHFStrategy(bars, config=cfg)
        res = strategy._get_channel_lines(bars[0].symbol, idx_target)
        
        if not res:
             print(f"{bars[0].symbol:<10} | {'N/A':<8} | {'N/A':<8} | {'N/A':<6} | Calc Failed")
             continue
             
        mid, lower, upper, slope_norm, vol_ratio, pivot_j = res
        
        height_pct = ((upper - lower) / mid) if mid > 0 else 0.0
        room_pct = ((mid - lower) / mid) if mid > 0 else 0.0
        
        # Check Signal (Full Logic)
        bar = bars[idx_target]
        ok_slope = slope_norm >= cfg.min_slope_norm
        ok_vol = vol_ratio <= cfg.vol_shrink_threshold
        ok_height = height_pct >= cfg.min_channel_height
        ok_room = room_pct >= cfg.min_mid_room
        
        buy_price = lower * (1.0 + cfg.buy_touch_eps)
        ok_touch = bar.low <= buy_price
        
        break_price = lower * (1.0 - cfg.channel_break_eps)
        ok_break = bar.close < break_price
        
        is_signal = ok_slope and ok_vol and ok_height and ok_room and ok_touch and (not ok_break)
        
        # Check Pass Rate criteria (Height >= 5% and Room >= 1.5%)
        # Note: These are cfg.min_channel_height (0.05) and cfg.min_mid_room (0.015)
        # So we can just use ok_height and ok_room
        if ok_height and ok_room:
            pass_count += 1
            
        print(f"{bars[0].symbol:<10} | {height_pct*100:<7.2f}% | {room_pct*100:<7.2f}% | {str(is_signal):<6} |")
        
    print("-" * 60)
    print(f"通过率 (Height>=5% & Room>=1.5%): {pass_count}/10 ({pass_count/10*100:.0f}%)")

if __name__ == "__main__":
    main()

def main():
    # 1. Get pool
    all_csvs = glob.glob("data/*.csv")
    pool = [f for f in all_csvs if "universe.csv" not in f]
    
    if len(pool) < 10:
        print(f"Pool size too small: {len(pool)}")
        return
        
    # Random sample 10
    selected_files = random.sample(pool, 10)
    
    target_date = date(2024, 12, 31)
    
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
    
    results = []
    
    print(f"{'Symbol':<10} | {'Height%':<8} | {'Room%':<8} | {'Signal':<6} | {'Remark'}")
    print("-" * 60)
    
    pass_count = 0
    
    for csv_file in selected_files:
        bars = load_bars(csv_file)
        if not bars:
            print(f"{os.path.basename(csv_file):<10} | {'N/A':<8} | {'N/A':<8} | {'N/A':<6} | No Data")
            continue
            
        # Find index of target date
        idx_target = -1
        for i, b in enumerate(bars):
            if b.dt == target_date:
                idx_target = i
                break
                
        if idx_target == -1:
            # If date not found, maybe data ends earlier or starts later
            print(f"{bars[0].symbol:<10} | {'N/A':<8} | {'N/A':<8} | {'N/A':<6} | Date Not Found")
            continue
            
        # Run strategy logic for this point
        # We need enough history
        if idx_target < cfg.channel_period:
             print(f"{bars[0].symbol:<10} | {'N/A':<8} | {'N/A':<8} | {'N/A':<6} | Insufficient History")
             continue
             
        # Need to pass bars up to target (or all bars) to strategy
        # Passing all bars is fine, we just query at idx_target
        strategy = ChannelHFStrategy(bars, config=cfg)
        res = strategy._get_channel_lines(bars[0].symbol, idx_target)
        
        if not res:
             print(f"{bars[0].symbol:<10} | {'N/A':<8} | {'N/A':<8} | {'N/A':<6} | Calc Failed")
             continue
             
        mid, lower, upper, slope_norm, vol_ratio, pivot_j = res
        
        height_pct = ((upper - lower) / mid) if mid > 0 else 0.0
        room_pct = ((mid - lower) / mid) if mid > 0 else 0.0
        
        # Check Signal (Full Logic)
        bar = bars[idx_target]
        ok_slope = slope_norm >= cfg.min_slope_norm
        ok_vol = vol_ratio <= cfg.vol_shrink_threshold
        ok_height = height_pct >= cfg.min_channel_height
        ok_room = room_pct >= cfg.min_mid_room
        
        buy_price = lower * (1.0 + cfg.buy_touch_eps)
        ok_touch = bar.low <= buy_price
        
        break_price = lower * (1.0 - cfg.channel_break_eps)
        ok_break = bar.close < break_price
        
        is_signal = ok_slope and ok_vol and ok_height and ok_room and ok_touch and (not ok_break)
        
        # Check Pass Rate criteria (Height >= 5% and Room >= 1.5%)
        # Note: These are cfg.min_channel_height (0.05) and cfg.min_mid_room (0.015)
        # So we can just use ok_height and ok_room
        if ok_height and ok_room:
            pass_count += 1
            
        print(f"{bars[0].symbol:<10} | {height_pct*100:<7.2f}% | {room_pct*100:<7.2f}% | {str(is_signal):<6} |")
        
    print("-" * 60)
    print(f"通过率 (Height>=5% & Room>=1.5%): {pass_count}/10 ({pass_count/10*100:.0f}%)")

if __name__ == "__main__":
    main()