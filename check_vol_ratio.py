import sys
import os
import csv
import glob
import numpy as np
from datetime import datetime, date

sys.path.append(os.getcwd())

from core.types import Bar

def parse_date(d_str):
    try:
        return datetime.strptime(d_str, "%Y-%m-%d").date()
    except:
        return None

def load_vols(csv_path):
    vols = []
    dts = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row: continue
            try:
                dt = parse_date(row[0])
                if not dt: continue
                if len(row) < 6: continue
                
                vols.append(float(row[5]))
                dts.append(dt)
            except:
                pass
    return dts, vols

def main():
    target_date = date(2024, 12, 31)
    period = 30
    threshold = 0.9
    
    csv_files = glob.glob("data/*.csv")
    total_checked = 0
    passed_count = 0
    
    print(f"Checking Volume Ratio (<= {threshold}) for {target_date}...")
    
    for csv_file in csv_files:
        if "universe.csv" in csv_file: continue
        
        dts, vols = load_vols(csv_file)
        if not dts: continue
        
        # Find index
        try:
            idx = dts.index(target_date)
        except ValueError:
            continue
            
        if idx < period - 1:
            continue
            
        # Calc logic matching ChannelHFStrategy
        # avg_vol is mean of period ending at i
        # vols slice: [start : i + 1]
        start = idx - period + 1
        window_vols = vols[start : idx + 1]
        
        avg_vol = np.mean(window_vols) if len(window_vols) else 0.0
        cur_vol = vols[idx]
        
        vol_ratio = (cur_vol / avg_vol) if avg_vol > 0 else 1.0
        
        total_checked += 1
        if vol_ratio <= threshold:
            passed_count += 1
            
    if total_checked > 0:
        rate = passed_count / total_checked
        print(f"\nTotal Checked: {total_checked}")
        print(f"Passed: {passed_count}")
        print(f"Pass Rate: {rate*100:.2f}%")
    else:
        print("No valid data found for target date.")

if __name__ == "__main__":
    main()