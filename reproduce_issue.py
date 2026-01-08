import sys
import os
from pathlib import Path
import json

# Add current directory to sys.path
sys.path.append(os.getcwd())

from core.scanner_runner import backtest_channel_hf_for_symbol_path

def run_test():
    symbol = "000001.SZ"
    data_path = Path("data/000001.SZ.csv")
    index_path = Path("data/000300.SH.csv")
    
    if not data_path.exists():
        print(f"Error: {data_path} does not exist.")
        return

    # Common config
    base_config = {
        "beg": "2023-01-01",
        "end": "2023-12-31",
        "initial_cash": 1000000,
        "detail": True, # Get detailed result including trades
        "channel_period": 20,
        "buy_touch_eps": 0.01,
        "sell_trigger_eps": 0.01,
        "sell_target_mode": "mid_up"
    }

    # Test mid_up
    print(f"Running backtest with sell_target_mode='mid_up'...")
    res_mid_up = backtest_channel_hf_for_symbol_path(symbol, data_path, index_path, base_config)
    
    # Test upper_down
    config_upper_down = base_config.copy()
    config_upper_down["sell_target_mode"] = "upper_down"
    print(f"Running backtest with sell_target_mode='upper_down'...")
    res_upper_down = backtest_channel_hf_for_symbol_path(symbol, data_path, index_path, config_upper_down)

    # Compare
    metrics_mid = res_mid_up.get("metrics", {})
    metrics_upper = res_upper_down.get("metrics", {})
    
    # Convert metrics to string representation for comparison if they are dicts
    print(f"\nMetrics (mid_up): {metrics_mid}")
    print(f"Metrics (upper_down): {metrics_upper}")
    
    trades_mid = res_mid_up.get("trades", [])
    trades_upper = res_upper_down.get("trades", [])
    
    print(f"Trades count (mid_up): {len(trades_mid)}")
    print(f"Trades count (upper_down): {len(trades_upper)}")
    
    # Simple equality check
    metrics_match = str(metrics_mid) == str(metrics_upper)
    trades_match = len(trades_mid) == len(trades_upper)
    
    if trades_match:
         for i in range(len(trades_mid)):
             t1 = trades_mid[i]
             t2 = trades_upper[i]
             # Check exit price specifically
             if t1.get('exit_price') != t2.get('exit_price'):
                 trades_match = False
                 print(f"Trade {i} exit price mismatch: {t1.get('exit_price')} vs {t2.get('exit_price')}")
                 break

    if metrics_match and trades_match:
        print("\nRESULT: IDENTICAL. The issue is reproduced.")
    else:
        print("\nRESULT: DIFFERENT.")

if __name__ == "__main__":
    run_test()