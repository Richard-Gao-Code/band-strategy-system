import sys
from pathlib import Path
from datetime import datetime
import numpy as np

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

from core.data import load_bars_from_csv

def _sma_series(closes: list[float], n: int) -> list[float | None]:
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

def main():
    index_path = Path(__file__).parent / "data/000300.SH.csv"
    if not index_path.exists():
        print("Error: 000300.SH.csv not found")
        return

    # Load enough data for MA30
    print("Loading index data...")
    bars = load_bars_from_csv(index_path, symbol="000300.SH", beg="2023-11-01", end="2024-01-31")
    if not bars:
        print("No data found")
        return

    # Sort by date
    bars.sort(key=lambda b: b.dt)
    
    closes = [float(b.close) for b in bars]
    dates = [b.dt for b in bars]

    # Calculate MAs
    ma5 = _sma_series(closes, 5)
    ma10 = _sma_series(closes, 10)
    ma20 = _sma_series(closes, 20)
    ma30 = _sma_series(closes, 30)

    print("\n=== 2024年1月 大盘(000300.SH) 均线状态检查 ===")
    print(f"{'日期':<12} | {'Close':<8} | {'MA5':<8} | {'MA10':<8} | {'MA20':<8} | {'MA30':<8} | {'状态 (MA30>20>10>5?)':<20}")
    print("-" * 100)

    count_bear = 0
    count_total = 0

    for i, dt in enumerate(dates):
        dt_str = dt.isoformat()
        if not dt_str.startswith("2024-01"):
            continue

        c = closes[i]
        m5 = ma5[i]
        m10 = ma10[i]
        m20 = ma20[i]
        m30 = ma30[i]

        if any(x is None for x in [m5, m10, m20, m30]):
            print(f"{dt_str:<12} | {c:<8.2f} | N/A (Not enough data)")
            continue

        # Check Bearish Alignment: MA30 > MA20 > MA10 > MA5
        is_bear = (m30 > m20 > m10 > m5)
        status = "BEAR (空头排列)" if is_bear else "Mix/Bull"
        
        # Check strictness
        # Maybe user wants to know if it's just "mostly" bear
        
        print(f"{dt_str:<12} | {c:<8.2f} | {m5:<8.2f} | {m10:<8.2f} | {m20:<8.2f} | {m30:<8.2f} | {status}")
        
        count_total += 1
        if is_bear:
            count_bear += 1

    print("-" * 100)
    print(f"Total Days: {count_total}")
    print(f"Bear Days: {count_bear}")
    print(f"Ratio: {count_bear/count_total:.2%}")

if __name__ == "__main__":
    main()