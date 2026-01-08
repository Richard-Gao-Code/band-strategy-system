import csv
import math
from dataclasses import dataclass
from pathlib import Path
from . import analyzer
from .analyzer import calculate_channel, AnalysisResult

@dataclass(frozen=True)
class Criteria:
    annualized_return_min: float = 0.15
    sharpe_min: float = 0.8
    max_drawdown_max: float = 0.10
    trades_min_exclusive: int = 14
    calmar_min: float = 3.0

def _to_float(x: str) -> float | None:
    if x is None:
        return None
    s = str(x).strip().replace(",", "")
    if not s or s.lower() == "nan":
        return None
    if s.endswith("%"):
        try:
            return float(s[:-1].strip()) / 100.0
        except Exception:
            return None
    try:
        return float(s)
    except Exception:
        return None

def _to_int(x: str) -> int | None:
    v = _to_float(x)
    if v is None or math.isnan(v):
        return None
    return int(v)

def _read_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        print(f"Warning: File not found: {csv_path}")
        return []
    if csv_path.is_dir():
        print(f"Error: Expected a file but got a directory: {csv_path}")
        return []
    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            return list(reader)
    except Exception as e:
        print(f"Error reading {csv_path}: {e}")
        return []


def _calmar_ratio(annualized_return: float, max_drawdown: float) -> float:
    if max_drawdown <= 0:
        return float("inf") if annualized_return > 0 else float("nan")
    return annualized_return / max_drawdown

def _load_results(csv_path: Path) -> tuple[str, list[dict]]:
    rows = _read_csv_rows(csv_path)
    out = []
    for r in rows:
        symbol = (r.get("symbol") or "").strip()
        ann = _to_float(r.get("annualized_return"))
        sharpe = _to_float(r.get("sharpe_ratio"))
        mdd = _to_float(r.get("max_drawdown"))
        trades = _to_int(r.get("trades"))
        mode = (r.get("sell_target_mode") or "").strip()

        if not symbol:
            continue
        if ann is None or sharpe is None or mdd is None or trades is None:
            continue

        out.append(
            {
                "symbol": symbol,
                "annualized_return": ann,
                "sharpe_ratio": sharpe,
                "max_drawdown": mdd,
                "calmar_ratio": _calmar_ratio(ann, mdd),
                "trades": trades,
                "sell_target_mode": mode,
            }
        )

    mode_guess = "unknown"
    if out:
        modes = {x["sell_target_mode"] for x in out if x.get("sell_target_mode")}
        if len(modes) == 1:
            mode_guess = next(iter(modes))
    return mode_guess, out

def _passes(c: Criteria, r: dict) -> bool:
    return (
        r["annualized_return"] >= c.annualized_return_min
        and r["sharpe_ratio"] >= c.sharpe_min
        and r["max_drawdown"] <= c.max_drawdown_max
        and r["trades"] > c.trades_min_exclusive
        and r["calmar_ratio"] >= c.calmar_min
    )

def _robust_score(rows: list[dict]) -> None:
    if not rows:
        return

    # Rank by Calmar (descending)
    def _calmar_key(x):
        v = x["calmar_ratio"]
        if math.isinf(v) and v > 0:
            return 999999.0
        if not math.isfinite(v):
            return -999.0
        return v

    rows.sort(key=_calmar_key, reverse=True)
    for i, r in enumerate(rows):
        r["rank_calmar"] = i + 1

    # Rank by Sharpe (descending)
    rows.sort(key=lambda x: x["sharpe_ratio"], reverse=True)
    for i, r in enumerate(rows):
        r["rank_sharpe"] = i + 1

    # Rank by Annualized Return (descending)
    rows.sort(key=lambda x: x["annualized_return"], reverse=True)
    for i, r in enumerate(rows):
        r["rank_ann"] = i + 1

    # Rank by Max Drawdown (ascending, lower is better)
    rows.sort(key=lambda x: x["max_drawdown"])
    for i, r in enumerate(rows):
        r["rank_mdd"] = i + 1

    # Calculate Rank Sum
    for r in rows:
        r["rank_sum"] = r["rank_calmar"] + r["rank_sharpe"] + r["rank_ann"]

    # Sort by Rank Sum (ascending)
    rows.sort(key=lambda x: x["rank_sum"])

def _read_stock_csv(path: Path):
    rows = []
    if not path.exists():
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

def _analyze_single_stock_detail_text(r: dict) -> list[str]:
    out_lines = []
    symbol = r['symbol']
    out_lines.append(f"\n{symbol} 鈥斺€?RankSum={r['rank_sum']} (C{r['rank_calmar']}+S{r['rank_sharpe']}+A{r['rank_ann']})")
    
    # Find data file
    roots = [
        Path(__file__).resolve().parent.parent / "data",
    ]
    csv_path = None
    for root in roots:
        p = root / f"{symbol}.csv"
        if p.exists():
            csv_path = p
            break
            
    if not csv_path:
        out_lines.append("  [Data File Not Found] - Cannot perform real-time analysis.")
        return out_lines

    data = _read_stock_csv(csv_path)
    if not data:
        out_lines.append("  [Data Load Failed]")
        return out_lines
        
    data.sort(key=lambda x: x["dt"])
    if not data:
        out_lines.append("  [Data Empty]")
        return out_lines
        
    last_bar = data[-1]
    ch = calculate_channel(data)
    
    if not ch:
        out_lines.append("  [Channel Calc Failed]")
        return out_lines
    
    mid = ch["mid"]
    lower = ch["lower"]
    upper = ch["upper"]
    slope = ch["slope_norm"]
    
    close = last_bar["close"]
    
    channel_height = ((upper - lower) / mid) if mid > 0 else 0.0
    dist_to_lower = (close - lower) / lower
    dist_to_lower_pct = dist_to_lower * 100
    
    break_px = lower * (1.0 - analyzer.SIG_CONFIG.channel_break_eps)
    
    # Status
    if close > upper: status = "Overbought (Above Upper)"
    elif close > mid: status = "Hold (Above Mid)"
    elif close > lower: status = "Hold (Below Mid)"
    elif close < break_px: status = "Danger (Channel Broken)"
    else: status = "Buy Zone (Below Lower)"
    
    out_lines.append(f" - 状态 : {status}")
    out_lines.append(f" - 关键数据 :")
    
    # Height Analysis
    h_status = "OK" if channel_height >= analyzer.SIG_CONFIG.min_channel_height else "Fail"
    h_desc = "波动正常" if h_status == "OK" else "波动极小，正在极度缩量横盘"
    out_lines.append(f"   - Height: {channel_height:.2%} ({h_status}) : {h_desc}")
    
    # Distance Analysis
    out_lines.append(f"   - Dist to Lower: {dist_to_lower:.2%} : 离下轨还有 {dist_to_lower_pct:.1f} 个点的距离。")
    
    # Slope Analysis
    s_status = "OK" if abs(slope) <= analyzer.SIG_CONFIG.slope_abs_max else "Fail"
    s_desc = ""
    if slope < -0.01: s_desc = "通道向下倾斜，接飞刀危险"
    elif slope > 0.01: s_desc = "通道向上倾斜，强势"
    else: s_desc = "通道走平"
    out_lines.append(f"   - Slope: {slope:.4f} ({s_status}) : {s_desc}")
    
    # Conclusion & Strategy
    out_lines.append(f" - 结论 & 策略 :")
    if channel_height < 0.05:
        out_lines.append(f"   像一根被压缩的弹簧。变盘在即。盯紧 {lower:.2f}元。如果跌到此位置是绝佳低吸机会。")
    elif dist_to_lower < -analyzer.SIG_CONFIG.channel_break_eps:
        out_lines.append(f"   【警告】股价已有效跌破下轨 ({dist_to_lower:.1%})，触发风控止损。")
        out_lines.append(f"   极度弱势，切勿盲目抄底。等待股价重新站回 {lower:.2f}元上方再做观察。")
    elif slope < -0.01:
        out_lines.append(f"   下跌趋势中，谨慎。目标价位在 {lower:.2f}元。不到此位置不碰。")
    elif dist_to_lower > 0.10:
        out_lines.append(f"   离买点还很远 ({dist_to_lower:.1%})。彻底忘掉它，除非大跌到 {lower:.2f}元。")
    else:
        out_lines.append(f"   正常波动中。关注下方支撑位 {lower:.2f}元。")
    
    return out_lines

def _analyze_single_stock_detail(r: dict):
    lines = _analyze_single_stock_detail_text(r)
    for l in lines:
        print(l)

def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")

def _summarize(title: str, rows: list[dict], c: Criteria) -> dict:
    ok = [r for r in rows if _passes(c, r)]
    _robust_score(ok)

    # Console Output (for debugging or CLI usage)
    print(f"\n==== {title} ====")
    print(f"鎬绘爣鐨? {len(rows)} | 杈炬爣: {len(ok)}")

    summary_text = []
    top_analysis = []
    
    if ok:
        ann_m = _mean([r["annualized_return"] for r in ok])
        shp_m = _mean([r["sharpe_ratio"] for r in ok])
        mdd_m = _mean([r["max_drawdown"] for r in ok])
        cal_m = _mean([r["calmar_ratio"] for r in ok if math.isfinite(r["calmar_ratio"])])
        trd_m = _mean([float(r["trades"]) for r in ok])
        
        stat_line = f"杈炬爣鍧囧€? 骞村寲={ann_m:.2%} 澶忔櫘={shp_m:.2f} Calmar={cal_m:.2f} 鍥炴挙={mdd_m:.2%} 浜ゆ槗={trd_m:.1f}"
        print(stat_line)
        summary_text.append(stat_line)

        top = ok[:5]
        print(f"Top 5 缁煎悎鍒嗘瀽:")
        for r in top:
            _analyze_single_stock_detail(r)
            top_analysis.append({
                "symbol": r["symbol"],
                "lines": _analyze_single_stock_detail_text(r)
            })
    else:
        print("杈炬爣涓虹┖")

    return {
        "all": rows,
        "ok": ok,
        "ok_symbols": {r["symbol"] for r in ok},
        "summary_text": summary_text,
        "top_analysis": top_analysis
    }

def run_selection(
    path_ud: Path, 
    path_mu: Path, 
    max_mdd: float = 0.10, 
    min_trd: int = 15,
    calmar_min: float = 3.0
) -> dict:
    # Reload config from disk to ensure latest parameters are used
    analyzer.reload_config()

    c = Criteria(
        max_drawdown_max=max_mdd, 
        trades_min_exclusive=min_trd - 1, 
        calmar_min=calmar_min
    )
    
    mode1, rows1 = _load_results(path_ud)
    mode2, rows2 = _load_results(path_mu)

    s1 = _summarize(f"涓婅建涓嬬郴 ({mode1})", rows1, c)
    s2 = _summarize(f"涓建涓婄郴 ({mode2})", rows2, c)
    
    return {
        "criteria": {
            "max_drawdown": max_mdd,
            "min_trades": min_trd,
            "calmar_min": calmar_min
        },
        "upper_down": {
            "mode": mode1,
            "total": len(rows1),
            "passed": len(s1["ok"]),
            "data": s1["ok"],
            "summary_text": s1["summary_text"],
            "top_analysis": s1["top_analysis"]
        },
        "mid_up": {
            "mode": mode2,
            "total": len(rows2),
            "passed": len(s2["ok"]),
            "data": s2["ok"],
            "summary_text": s2["summary_text"],
            "top_analysis": s2["top_analysis"]
        }
    }

def run_interactive() -> None:
    print("=== 閫夎偂妯″潡 (Stock Selection) ===")
    
    # Reload config
    analyzer.reload_config()
    
    base_dir = Path(__file__).resolve().parent.parent / "test" / "20260102"
    def_name_ud = "涓婅建涓嬬郴100.csv"
    def_name_mu = "涓建涓婄郴100.csv"
    def_path_ud = base_dir / def_name_ud
    def_path_mu = base_dir / def_name_mu
    
    def resolve_path(user_input: str, default_path: Path, default_filename: str) -> Path:
        if not user_input:
            return default_path
        p = Path(user_input)
        if p.is_dir():
            return p / default_filename
        return p
    
    # Input
    in_ud = input(f"杈撳叆涓婅建涓嬬郴鏂囦欢璺緞 (榛樿: {def_path_ud}): ").strip()
    path_ud = resolve_path(in_ud, def_path_ud, def_name_ud)
    
    in_mu = input(f"杈撳叆涓建涓婄郴鏂囦欢璺緞 (榛樿: {def_path_mu}): ").strip()
    path_mu = resolve_path(in_mu, def_path_mu, def_name_mu)
    
    in_mdd = input("杈撳叆鏈€澶у洖鎾?(榛樿 0.10): ").strip()
    max_mdd = float(in_mdd) if in_mdd else 0.10
    
    in_trd = input("杈撳叆鏈€灏忎氦鏄撴鏁?(榛樿 15): ").strip()
    min_trd = int(in_trd) if in_trd else 15
    
    # Create Criteria
    c = Criteria(max_drawdown_max=max_mdd, trades_min_exclusive=min_trd - 1, calmar_min=3.0)
    
    print("\n姝ｅ湪鍒嗘瀽...")
    mode1, rows1 = _load_results(path_ud)
    mode2, rows2 = _load_results(path_mu)

    s1 = _summarize(f"涓婅建涓嬬郴 ({mode1})", rows1, c)
    s2 = _summarize(f"涓建涓婄郴 ({mode2})", rows2, c)
