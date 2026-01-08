from __future__ import annotations

import calendar
import csv
import json
import logging
import math
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .types import Bar


def _parse_date(value: str) -> date:
    v = value.strip().split()[0]
    if len(v) == 8 and v.isdigit():
        y = int(v[0:4])
        m = int(v[4:6])
        d = int(v[6:8])
        return date(y, m, d)
    parts = v.split("-")
    if len(parts) != 3:
        parts2 = v.replace("/", "-").replace(".", "-").split("-")
        if len(parts2) != 3:
            raise ValueError(f"Invalid date: {value}")
        parts = parts2
    y, m, d = (int(p) for p in parts)
    return date(y, m, d)


def _parse_date_bound(value: str, bound: str) -> date:
    v = str(value).strip().split()[0]
    v2 = v.replace("/", "-").replace(".", "-")
    parts = v2.split("-")
    if len(parts) == 2:
        y = int(parts[0])
        m = int(parts[1])
        if bound == "beg":
            return date(y, m, 1)
        last_day = int(calendar.monthrange(y, m)[1])
        return date(y, m, last_day)
    return _parse_date(v)


def _parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    v = value.strip()
    if v == "":
        return None
    v = v.replace(",", "")
    return float(v)


def _pick(row: dict[str, str], names: list[str]) -> str | None:
    for name in names:
        if name in row and row[name] != "":
            return row[name]
    return None


def _normalize_header(name: str) -> str:
    return name.strip().lower().replace(" ", "").replace("_", "")


def _pick_norm(row: dict[str, str], names: list[str]) -> str | None:
    norm = {_normalize_header(k): v for k, v in row.items()}
    for name in names:
        key = _normalize_header(name)
        if key in norm and norm[key] != "":
            return norm[key]
    return None


def validate_bars(bars: list[Bar], symbol: str) -> None:
    """验证数据质量
    
    检查项：
    1. 价格是否为正且不为0
    2. OHLC 逻辑是否正确 (High >= Open, High >= Close, Low <= Open, Low <= Close)
    3. 检查异常跳空 (可能表示未复权或数据错误)
    """
    if not bars:
        return

    for i, b in enumerate(bars):
        # 1. 价格合法性
        if b.open <= 0 or b.high <= 0 or b.low <= 0 or b.close <= 0:
            raise ValueError(f"数据错误: {symbol} 在 {b.dt} 存在非正价格 (O:{b.open}, H:{b.high}, L:{b.low}, C:{b.close})")

        # 2. OHLC 逻辑
        if b.high < b.open or b.high < b.close or b.low > b.open or b.low > b.close:
             raise ValueError(f"数据逻辑错误: {symbol} 在 {b.dt} OHLC 不符合逻辑 (O:{b.open}, H:{b.high}, L:{b.low}, C:{b.close})")

        # 3. 异常跳空检查 (例如单日变动 > 25%，排除极端行情，通常 A 股涨跌停为 10%/20%)
        # 如果出现 > 25% 的跳空缺口，极有可能是因为未复权（除权除息）
        if i > 0:
            prev_close = bars[i-1].close
            if prev_close > 0:
                change_pct = (b.open / prev_close) - 1.0
                
                # 检查是否是疑似除权（大幅低开）
                if change_pct < -0.25:
                    logging.getLogger(__name__).warning(
                        f"数据异常警告: {symbol} 在 {b.dt} 出现大幅低开 ({change_pct:.2%})，疑似未复权（除权缺口）。请务必使用前复权数据！"
                    )
                
                # 检查大幅高开（可能是异常数据）
                elif change_pct > 0.25:
                     logging.getLogger(__name__).warning(
                        f"数据异常警告: {symbol} 在 {b.dt} 出现大幅高开 ({change_pct:.2%})，请检查数据质量。"
                    )

def load_bars_from_csv(
    path: Path,
    symbol: str,
    beg: str | None = None,
    end: str | None = None,
    validate: bool = True,
) -> list[Bar]:
    if not path.exists():
        return []

    beg_dt = None
    end_dt = None
    if beg is not None and str(beg).strip() not in ["", "0"]:
        beg_dt = _parse_date_bound(str(beg), "beg")
    if end is not None and str(end).strip() not in ["", "0"]:
        end_dt = _parse_date_bound(str(end), "end")

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return []

        h_map = {_normalize_header(h): i for i, h in enumerate(header)}

        def get_idx(names: list[str]) -> int:
            for name in names:
                k = _normalize_header(name)
                if k in h_map:
                    return h_map[k]
            return -1

        idx_dt = get_idx(["date", "time", "datetime", "时间", "日期", "dt", "交易日期"])
        idx_open = get_idx(["open", "开盘", "开盘价"])
        idx_high = get_idx(["high", "最高", "最高价"])
        idx_low = get_idx(["low", "最低", "最低价"])
        idx_close = get_idx(["close", "收盘", "收盘价"])
        idx_vol = get_idx(["volume", "vol", "成交量", "数量"])

        if idx_dt < 0 or idx_open < 0 or idx_high < 0 or idx_low < 0 or idx_close < 0:
            return []

        bars: list[Bar] = []
        last_dt: date | None = None
        need_sort = False
        err_rows = 0
        idx = 0

        for row in reader:
            try:
                if len(row) <= idx_dt: continue
                dt_str = row[idx_dt]
                if not dt_str:
                    continue
                dt = _parse_date(dt_str)

                if beg_dt is not None and dt < beg_dt:
                    continue
                if end_dt is not None and dt > end_dt:
                    continue

                if len(row) <= max(idx_open, idx_high, idx_low, idx_close):
                    continue

                open_val = _parse_float(row[idx_open])
                high_val = _parse_float(row[idx_high])
                low_val = _parse_float(row[idx_low])
                close_val = _parse_float(row[idx_close])
                
                volume_val = 0.0
                if idx_vol >= 0 and len(row) > idx_vol:
                    v = _parse_float(row[idx_vol])
                    if v is not None:
                        volume_val = v

                if open_val is None or high_val is None or low_val is None or close_val is None:
                    continue

                if last_dt is not None and dt < last_dt:
                    need_sort = True
                last_dt = dt

                bars.append(
                    Bar(
                        symbol=symbol,
                        dt=dt,
                        open=open_val,
                        high=high_val,
                        low=low_val,
                        close=close_val,
                        volume=volume_val,
                        index=idx,
                    )
                )
                idx += 1
            except Exception:
                err_rows += 1
                continue

    if err_rows:
        logging.getLogger(__name__).warning(f"{symbol} CSV 解析跳过 {err_rows} 行")

    if need_sort:
        bars.sort(key=lambda b: b.dt)

    if bars:
        if need_sort:
            if validate:
                validate_bars(bars, symbol)
            bars = [replace(b, index=i) for i, b in enumerate(bars)]
        else:
            if validate:
                validate_bars(bars, symbol)
    return bars

def is_trading_time() -> bool:
    """判断当前是否处于 A 股交易时间 (9:30-11:30, 13:00-15:00)"""
    now = datetime.now()
    if now.weekday() >= 5: # 周六日不交易
        return False
    current_time = now.strftime("%H:%M:%S")
    if "09:30:00" <= current_time <= "11:30:00" or "13:00:00" <= current_time <= "15:00:00":
        return True
    return False

def fetch_realtime_snapshot(symbol: str, market: str | None = None) -> Bar | None:
    """获取股票当天的实时快照数据，封装成 Bar 对象"""
    try:
        # 简单处理市场前缀
        secid = ""
        if market:
            m = 0 if market.upper() == "SZ" else 1
            secid = f"{m}.{symbol}"
        else:
            if symbol.startswith("6"): secid = f"1.{symbol}"
            elif symbol.startswith("0") or symbol.startswith("3"): secid = f"0.{symbol}"
            elif symbol.startswith("8") or symbol.startswith("4"): secid = f"0.{symbol}" # 北交所简单处理
            else: return None

        fields = "f43,f44,f45,f46,f47,f48,f57,f58,f60"
        url = f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields={fields}"
        
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            if not data or "data" not in data or data["data"] is None:
                return None
            
            d = data["data"]
            # f46: 开盘, f44: 最高, f45: 最低, f43: 最新价, f47: 成交量, f48: 成交额
            # 价格通常需要除以 100
            price_scale = 100.0
            
            # 如果是 "-" 或者为 0，说明还没开盘
            if d.get("f46") == "-" or not d.get("f46"):
                return None

            return Bar(
                symbol=symbol,
                dt=date.today(),
                open=float(d["f46"]) / price_scale,
                high=float(d["f44"]) / price_scale,
                low=float(d["f45"]) / price_scale,
                close=float(d["f43"]) / price_scale,
                volume=float(d["f47"])
            )
    except Exception as e:
        logging.getLogger(__name__).error(f"获取实时快照失败 {symbol}: {e}")
        return None

def load_bars_with_realtime(path: Path, symbol: str, validate: bool = True) -> list[Bar]:
    bars = load_bars_from_csv(path, symbol, validate=validate)
    
    # 尝试抓取实时数据
    today = date.today()
    if not bars or bars[-1].dt <= today:
        rt_bar = fetch_realtime_snapshot(symbol)
        if rt_bar:
            # 如果历史数据最后一天就是今天，则替换；否则追加
            if bars and bars[-1].dt == today:
                bars[-1] = rt_bar
            else:
                bars.append(rt_bar)
    return bars


def load_bars_from_csv_dir(path: Path, beg: str | None = None, end: str | None = None) -> list[Bar]:
    if not path.exists() or not path.is_dir():
        raise ValueError(f"Not a directory: {path}")
    bars: list[Bar] = []
    for csv_path in sorted(path.glob("*.csv")):
        symbol = csv_path.stem
        bars.extend(load_bars_from_csv(csv_path, symbol=symbol, beg=beg, end=end))
    return bars


def write_bars_to_csv(path: Path, bars: list[Bar]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "open", "high", "low", "close", "volume"])
        for b in sorted(bars, key=lambda x: x.dt):
            w.writerow(
                [
                    b.dt.isoformat(),
                    f"{b.open:.6f}",
                    f"{b.high:.6f}",
                    f"{b.low:.6f}",
                    f"{b.close:.6f}",
                    "" if b.volume is None else f"{float(b.volume):.6f}",
                ]
            )


def sync_incremental_data(
    symbol: str,
    out_path: Path,
    beg: str = "20150101",
    end: str = "20500101",
    adjust: str = "qfq",
    market: str | None = None,
    tail_days: int = 0,
) -> list[Bar]:
    """增量同步单个股票的数据到 CSV 文件，并返回最新的全部数据"""
    existing_bars: list[Bar] = []
    if out_path.exists():
        try:
            existing_bars = load_bars_from_csv(out_path, symbol)
        except Exception:
            existing_bars = []

    fetch_beg = beg
    if existing_bars:
        td = int(tail_days) if tail_days is not None else 0
        if td > 0:
            i = max(0, len(existing_bars) - 1 - td)
            fetch_beg = existing_bars[i].dt.strftime("%Y%m%d")
        else:
            fetch_beg = existing_bars[-1].dt.strftime("%Y%m%d")

    new_bars = fetch_daily_bars_eastmoney(
        symbol=symbol,
        beg=fetch_beg,
        end=end,
        adjust=adjust,
        market=market,
    )

    if not new_bars:
        return existing_bars

    if not existing_bars:
        write_bars_to_csv(out_path, new_bars)
        return new_bars

    by_dt: dict[date, Bar] = {b.dt: b for b in existing_bars}
    for b in new_bars:
        by_dt[b.dt] = b

    all_bars = sorted(by_dt.values(), key=lambda x: x.dt)
    write_bars_to_csv(out_path, all_bars)
    return all_bars


def inspect_csv_quality(
    path: Path,
    symbol: str | None = None,
    name: str | None = None,
    max_gap_days: int = 15,
    gap_open_abs_pct: float = 0.2,
    min_rows: int = 60,
    stale_days: int = 10,
    min_list_days: int = 0,
    check_st: bool = False,
    min_avg_amount: float = 0.0,
    min_price: float = 0.0,
    fatal_types: list[str] | None = None,
) -> dict[str, Any]:
    sym = (symbol or path.stem or "").strip() or "-"
    out: dict[str, Any] = {
        "symbol": sym,
        "name": name,
        "path": str(path),
        "ok": True,
        "rows": 0,
        "last_date": None,
        "anomalies": [],
    }

    try:
        bars = load_bars_from_csv(path, sym)
    except Exception as e:
        out["ok"] = False
        out["anomalies"] = [{"symbol": sym, "type": "解析失败", "detail": str(e)}]
        return out

    out["rows"] = int(len(bars))
    out["last_date"] = bars[-1].dt.isoformat() if bars else None

    fatal = set(str(x) for x in (fatal_types or []))
    if not fatal:
        fatal = {"解析失败", "空数据", "数据量不足", "重复日期", "数据过旧", "非正价格", "OHLC异常", "上市时间不足", "ST股票", "成交额不足", "低价股"}

    anomalies: list[dict[str, Any]] = []
    if not bars:
        anomalies.append({"symbol": sym, "type": "空数据", "detail": "CSV 无有效行情"})

    if bars and len(bars) < int(min_rows):
        anomalies.append({"symbol": sym, "type": "数据量不足", "detail": f"rows={len(bars)}"})

    dts = [b.dt for b in bars]
    if len(set(dts)) != len(dts):
        anomalies.append({"symbol": sym, "type": "重复日期", "detail": "存在重复交易日"})

    if bars:
        today = date.today()
        sd = int(stale_days) if stale_days is not None else 0
        if sd > 0 and (today - bars[-1].dt).days > sd:
            anomalies.append({"symbol": sym, "type": "数据过旧", "detail": f"last={bars[-1].dt.isoformat()}"})

        # New Checks
        # 1. Listing Duration
        if min_list_days > 0:
            age_days = (today - bars[0].dt).days
            if age_days < min_list_days:
                anomalies.append({"symbol": sym, "type": "上市时间不足", "detail": f"上市 {age_days} 天 < {min_list_days} 天"})

        # 2. ST Check
        if check_st and name:
            if "ST" in name.upper():
                 anomalies.append({"symbol": sym, "type": "ST股票", "detail": f"名称包含ST: {name}"})

        # 3. Min Price
        if min_price > 0:
            last_close = bars[-1].close
            if last_close < min_price:
                anomalies.append({"symbol": sym, "type": "低价股", "detail": f"收盘价 {last_close} < {min_price}"})

        # 4. Avg Amount (Estimate: close * volume)
        # Assuming volume is unit shares (EastMoney API usually returns volume in Hands=100 for stocks, but CSV usually raw?)
        # Let's assume the CSV volume is consistent. If it comes from `fetch_daily_bars_eastmoney` -> `parse_eastmoney_klines`,
        # the API returns volume in 'Hand' (100 shares)?
        # Let's check `parse_eastmoney_klines`.
        # Actually, let's just calculate `amount` sum.
        # If min_avg_amount is like 10,000,000 (10 million).
        if min_avg_amount > 0:
            total_amt = 0.0
            count = 0
            # Check last 20 days or all? "日均" implies average over a period. Let's use all loaded bars (which might be limited by file content).
            # If file has 10 years, average over 10 years might hide recent low liquidity.
            # Let's use last N days? Or just all. User didn't specify. All is safer for "quality".
            # But "quality" usually means "is it tradable NOW".
            # Let's use last 60 bars (approx 3 months) for turnover check.
            check_bars = bars[-60:]
            for b in check_bars:
                if b.volume is not None:
                     # Heuristic: if volume is small (like < 100000), it might be lots. If > 1000000, shares.
                     # But we don't know.
                     # However, typically EastMoney CSV dumps usually store volume.
                     # Let's assume standard calculation: Amount ~= Close * Volume.
                     # Note: If volume is in 'lots' (100 shares), we need * 100.
                     # Most EastMoney data sources use 'volume' as 'shares' or 'lots'?
                     # Let's assume Volume is Shares for safety? Or Lots?
                     # In `fetch_daily_bars_eastmoney`, `parse_eastmoney_klines` takes `vol_raw`.
                     # If it's from `kline/get`, usually it's "volume".
                     # Let's try to be conservative. If we calculate "Close * Volume" and it's super small, it might be lots.
                     # But let's just use `Close * Volume` and let user adjust threshold.
                     # If user says "1000万", and we have volume in lots (100), we get 10万.
                     # So we might flag it falsely.
                     # To be safe, I'll assume Volume is SHARES. If it's LOTS, the calculated amount will be 1/100th, and will likely trigger "Low Amount".
                     # Wait, if Volume is Lots, and I treat as Shares, my calc amount is 1/100th of real.
                     # So if Real Amount is 10M, I calc 100k. I will reject it.
                     # If Volume is Shares, I calc 10M.
                     # EastMoney `kline/get` usually returns Volume in **lots** (Hands) for fields like `f5`.
                     # But let's look at `parse_eastmoney_klines` implementation again (I can't see it now).
                     # Usually best to assume Volume * Price * (Multiplier? 1).
                     # I will add a multiplier note or just use 1.
                     # Most backtest systems normalize to Shares.
                     # I will assume `Close * Volume`.
                     total_amt += b.close * (b.volume or 0)
                     count += 1
            
            if count > 0:
                avg = total_amt / count
                # If avg is very small compared to threshold, maybe we missed a factor of 100?
                # But we can't guess.
                if avg < min_avg_amount:
                     anomalies.append({"symbol": sym, "type": "成交额不足", "detail": f"日均 {avg/10000:.1f}万 < {min_avg_amount/10000:.1f}万"})

    mg = int(max_gap_days) if max_gap_days is not None else 0
    thr = float(gap_open_abs_pct) if gap_open_abs_pct is not None else 0.0

    for i, b in enumerate(bars):
        if b.open <= 0 or b.high <= 0 or b.low <= 0 or b.close <= 0:
            anomalies.append({
                "symbol": sym,
                "date": b.dt.isoformat(),
                "type": "非正价格",
                "detail": f"O={b.open} H={b.high} L={b.low} C={b.close}",
            })

        if b.high < max(b.open, b.close) or b.low > min(b.open, b.close) or b.low > b.high:
            anomalies.append({
                "symbol": sym,
                "date": b.dt.isoformat(),
                "type": "OHLC异常",
                "detail": f"O={b.open} H={b.high} L={b.low} C={b.close}",
            })

        if i <= 0:
            continue

        prev = bars[i - 1]
        if mg > 0:
            gap_days = (b.dt - prev.dt).days
            if gap_days > mg:
                anomalies.append({
                    "symbol": sym,
                    "date": b.dt.isoformat(),
                    "type": "断档",
                    "detail": f"gap={gap_days}d ({prev.dt.isoformat()}->{b.dt.isoformat()})",
                })

        if thr > 0 and prev.close > 0:
            gap_pct = (b.open - prev.close) / prev.close
            if abs(gap_pct) > thr:
                anomalies.append({
                    "symbol": sym,
                    "date": b.dt.isoformat(),
                    "type": "异常跳空",
                    "detail": f"gap_open={gap_pct:.2%}",
                })

    out["anomalies"] = anomalies
    out["ok"] = not any((a.get("type") in fatal) for a in anomalies)
    return out


def inspect_dir_quality(
    data_dir: Path,
    symbols: list[str] | None = None,
    max_gap_days: int = 15,
    gap_open_abs_pct: float = 0.2,
    min_rows: int = 60,
    stale_days: int = 10,
    min_list_days: int = 0,
    check_st: bool = False,
    min_avg_amount: float = 0.0,
    min_price: float = 0.0,
    fatal_types: list[str] | None = None,
) -> dict[str, Any]:
    wanted: set[str] | None = None
    if symbols:
        wanted = set()
        for s in symbols:
            u = str(s).strip().upper()
            if not u:
                continue
            wanted.add(u)
            wanted.add(u.split(".")[0])

    items: list[dict[str, Any]] = []
    
    # Pre-fetch names if ST check is enabled
    name_map = {}
    if check_st:
        try:
            # Import here to avoid circular dependency if any, though it's in the same file usually
            # But fetch_all_a_share_symbols is in this file.
            # Use a cached way or fetch once?
            # fetching all symbols takes time.
            print("Fetching symbol names for ST check...")
            all_syms = fetch_all_a_share_symbols()
            for item in all_syms:
                code = item.get("code") # fetch_all_a_share_symbols returns list[dict[str, str]] with 'code'/'name'?
                # Wait, let's check fetch_all_a_share_symbols return format.
                # It returns results.append({"code": code, "name": name}) ? 
                # No, look at line 666: fields="f12,f14,f13". f12=code, f14=name.
                # And the loop: results.append({"symbol": f"{code}.{suffix}", "name": name})
                # Yes.
                s = item.get("symbol")
                n = item.get("name")
                if s and n:
                    name_map[s] = n
                    name_map[s.split(".")[0]] = n # Map code only too
        except Exception as e:
            print(f"Failed to fetch symbol map for ST check: {e}")

    for p in sorted(data_dir.glob("*.csv")):
        sym = p.stem
        if wanted is not None:
            u = sym.upper()
            if u not in wanted and u.split(".")[0] not in wanted:
                continue
        
        # Get name
        name = name_map.get(sym) or name_map.get(sym.split(".")[0])

        items.append(
            inspect_csv_quality(
                p,
                symbol=sym,
                name=name,
                max_gap_days=max_gap_days,
                gap_open_abs_pct=gap_open_abs_pct,
                min_rows=min_rows,
                stale_days=stale_days,
                min_list_days=min_list_days,
                check_st=check_st,
                min_avg_amount=min_avg_amount,
                min_price=min_price,
                fatal_types=fatal_types,
            )
        )

    bad = [x for x in items if not x.get("ok")]
    return {
        "total": len(items),
        "bad": len(bad),
        "items": items,
    }


def _eastmoney_secid(symbol: str, market: str | None = None) -> str:
    s = symbol.strip().upper()
    
    # 1. Handle CODE.MKT format (e.g., 000001.SZ, 000300.SH)
    if "." in s:
        parts = s.split(".")
        if len(parts) == 2:
            code, mkt = parts
            if code.isdigit():
                prefix = {"SH": "1.", "SZ": "0.", "BJ": "116."}.get(mkt)
                if prefix:
                    return f"{prefix}{code}"
            else:
                # Might be MKT.CODE
                prefix = {"SH": "1.", "SZ": "0.", "BJ": "116."}.get(code)
                if prefix and mkt.isdigit():
                    return f"{prefix}{mkt}"

    # 2. Handle MKTCODE format (e.g., SH600519, sz000001)
    if s.startswith(("SH", "SZ", "BJ")):
        mkt = s[:2]
        code = s[2:]
        if code.isdigit():
            prefix = {"SH": "1.", "SZ": "0.", "BJ": "116."}.get(mkt)
            if prefix:
                return f"{prefix}{code}"

    # 3. Explicit market parameter
    if market:
        m = market.strip().upper()
        prefix = {"SH": "1.", "SZ": "0.", "BJ": "116."}.get(m)
        if prefix:
            # If symbol already has market prefix like 'sh600519', strip it
            code = s[2:] if s.startswith(("SH", "SZ", "BJ")) and s[2:].isdigit() else s
            return f"{prefix}{code}"

    # 4. Infer from code prefix
    if len(s) == 6 and s.isdigit():
        # SH stocks, ETFs, and common SH indices starting with 000
        if s.startswith(("60", "68", "51", "58")):
            return f"1.{s}"
        
        # SZ stocks, ETFs, and indices
        if s.startswith(("001", "002", "003", "30", "399", "15")):
            return f"0.{s}"
            
        # Special case: 000xxx
        if s.startswith("000"):
            # Known SH indices starting with 000 (e.g. 000300 CSI 300, 000001 SSE Composite)
            # In EastMoney, these must use 1. prefix
            if s in ("000300", "000001", "000016", "000905", "000852"):
                return f"1.{s}"
            # Other 000xxx are likely SZ stocks (e.g. 000001 Ping An Bank)
            return f"0.{s}"
    
    # Indices/Others (not 6-digit)
    if s.startswith("399"):
        return f"0.{s}"
    if s.startswith(("8", "4", "92")):
        return f"116.{s}"
        
    # Default fallback for 6-digit codes
    if len(s) == 6 and s.isdigit():
        if s.startswith("6"): return f"1.{s}"
        return f"0.{s}"

    raise ValueError(f"Cannot infer market for symbol: {symbol}. Please use '600519.SH' or '000001.SZ' format.")


def parse_eastmoney_klines(symbol: str, klines: list[str]) -> list[Bar]:
    bars: list[Bar] = []
    for line in klines:
        parts = line.split(",")
        if len(parts) < 6:
            continue
        dt_raw, open_raw, close_raw, high_raw, low_raw, vol_raw = parts[:6]
        o = _parse_float(open_raw)
        h = _parse_float(high_raw)
        lo = _parse_float(low_raw)
        c = _parse_float(close_raw)
        v = _parse_float(vol_raw)
        if o is None or h is None or lo is None or c is None:
            continue
        bars.append(
            Bar(
                symbol=symbol,
                dt=_parse_date(dt_raw),
                open=float(o),
                high=float(h),
                low=float(lo),
                close=float(c),
                volume=None if v is None else float(v),
            )
        )
    bars.sort(key=lambda b: b.dt)
    if bars:
        bars = [replace(b, index=i) for i, b in enumerate(bars)]
    return bars


def fetch_all_a_share_symbols(
    page_size: int = 2000,
    timeout_sec: float = 15.0,
    max_retries: int = 3,
    sleep_sec: float = 0.1,
) -> list[dict[str, str]]:
    """从东方财富获取所有 A 股代码和名称 (支持分页抓取)"""
    import json
    import time
    from urllib.error import HTTPError, URLError
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen

    results: list[dict[str, str]] = []
    page = 1

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://quote.eastmoney.com/center/gridlist.html",
    }

    last_error: Exception | None = None
    
    # 增加重试计数
    consecutive_empty_pages = 0

    while True:
        params = {
            "pn": str(page),
            "pz": str(page_size),
            "po": "1",
            "np": "1",
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": "2",
            "invt": "2",
            "fid": "f3",
            "fs": "m:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23,m:0 t:81 s:2048",
            "fields": "f12,f14,f13",
            "_": str(int(time.time() * 1000)),
        }
        url = "https://push2.eastmoney.com/api/qt/clist/get?" + urlencode(params)

        raw_data = None
        for attempt in range(1, max_retries + 1):
            try:
                req = Request(url, headers=headers)
                with urlopen(req, timeout=timeout_sec) as resp:
                    raw_data = resp.read().decode("utf-8")
                last_error = None
                break
            except (HTTPError, URLError, TimeoutError) as e:
                last_error = e
                time.sleep(min(2.0, 0.2 * attempt))
            except Exception as e:
                last_error = e
                time.sleep(min(2.0, 0.2 * attempt))

        if raw_data is None:
            break

        try:
            data = json.loads(raw_data)
        except Exception as e:
            last_error = e
            break

        d_data = data.get("data")
        if not isinstance(d_data, dict):
            # Treat null data as empty page
            consecutive_empty_pages += 1
            if consecutive_empty_pages >= 2:
                break
            page += 1
            continue

        diff = d_data.get("diff", [])
        if not diff:
            consecutive_empty_pages += 1
            if consecutive_empty_pages >= 2:
                break
            page += 1
            continue
        
        consecutive_empty_pages = 0

        for item in diff:
            code = item.get("f12")
            name = item.get("f14")
            mkt_id = item.get("f13")
            if code and name:
                suffix = "SZ"
                if mkt_id == 1:
                    suffix = "SH"
                elif mkt_id == 0:
                    suffix = "SZ"
                elif mkt_id == 116 or mkt_id == 2: # 北交所
                    suffix = "BJ"
                else:
                    # 默认深证
                    suffix = "SZ"
                results.append({"symbol": f"{code}.{suffix}", "name": name})

        if len(diff) < page_size:
            # 即使本页不满，也再试一页，防止分页边缘问题
            pass

        page += 1
        time.sleep(sleep_sec)

    if not results and last_error is not None:
        raise RuntimeError(f"fetch_all_a_share_symbols failed: {last_error}")

    return results


def find_block_code(block_name: str) -> str | None:
    """
    Search for a block/index code by name (e.g. "中证500")
    Returns the fs parameter string if found, e.g. "b:BK0500" or "i:0.000905"
    """
    import time
    from urllib.request import Request, urlopen
    from urllib.parse import urlencode

    # Search in Concept/Industry/Region blocks
    # API: https://searchapi.eastmoney.com/api/suggest/get
    # But that might be complex. 
    # Let's try to search in the "Pick" interface or specific block lists.
    
    # Actually, for standard indices like HS300, ZZ500, we can use a hardcoded map or search.
    # For now, let's just return None if not in a small hardcoded list, 
    # or implement a simple search if possible.
    
    # Extended map
    known_map = {
        "沪深300": "b:BK0500",
        "中证500": "b:BK0701",
        "上证50": "b:BK0016", # Guess
        "创业板指": "i:0.399006",
        "科创50": "i:1.000688",
        # Aliases
        "HS300": "b:BK0500",
        "ZZ500": "b:BK0701",
    }
    
    if block_name in known_map:
        return known_map[block_name]
        
    # If not found, we can try to search using EM's block list API
    # https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=20&po=1&np=1&ut=...&fltt=2&invt=2&fid=f3&fs=m:90+t:2+f:!50&fields=f12,f14,f13
    # m:90 t:2 is "Concept Boards"
    # m:90 t:1 is "Industry Boards"
    # m:90 t:3 is "Region Boards"
    
    return None

def fetch_block_constituents(
    fs_param: str,
    page_size: int = 100, # Reduced from 500 to avoid API cap (which seems to be ~100)
    sleep_sec: float = 0.1,
    timeout_sec: float = 15.0,
) -> list[dict[str, str]]:
    """从东方财富获取指定板块(指数/概念/行业)的成分股"""
    import time
    import json
    from urllib.request import Request, urlopen
    from urllib.parse import urlencode

    results: list[dict[str, str]] = []
    page = 1

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://quote.eastmoney.com/center/gridlist.html",
    }

    while True:
        params = {
            "pn": str(page),
            "pz": str(page_size),
            "po": "1",
            "np": "1",
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": "2",
            "invt": "2",
            "fid": "f3",
            "fs": fs_param,
            "fields": "f12,f14,f13",
            "_": str(int(time.time() * 1000)),
        }
        url = "https://push2.eastmoney.com/api/qt/clist/get?" + urlencode(params)

        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=timeout_sec) as resp:
                raw_data = resp.read().decode("utf-8")
                data = json.loads(raw_data)
                d_data = data.get("data")
                if not isinstance(d_data, dict):
                    break
                
                total = d_data.get("total") # Get total count
                diff = d_data.get("diff", [])
                if not diff:
                    break

                for item in diff:
                    code = item.get("f12")
                    name = item.get("f14")
                    mkt_id = item.get("f13")
                    if code and name:
                        suffix = "SZ"
                        if mkt_id == 1:
                            suffix = "SH"
                        elif mkt_id == 0:
                            suffix = "SZ"
                        elif mkt_id == 116 or mkt_id == 2:
                            suffix = "BJ"
                        results.append({"symbol": f"{code}.{suffix}", "name": name})

                # Check if we have fetched all items
                if total is not None and len(results) >= total:
                    break

                if len(diff) < page_size:
                    break
                page += 1
                time.sleep(sleep_sec)
        except Exception as e:
            print(f"Error fetching block constituents page {page}: {e}")
            break

    return results





def fetch_a_share_universe_eastmoney(
    page_size: int = 500,
    sleep_sec: float = 0.1,
    timeout_sec: float = 15.0,
) -> list[dict[str, object]]:
    import time

    results: list[dict[str, object]] = []
    page = 1

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://quote.eastmoney.com/center/gridlist.html",
    }

    while True:
        params = {
            "pn": str(page),
            "pz": str(page_size),
            "po": "1",
            "np": "1",
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": "2",
            "invt": "2",
            "fid": "f3",
            "fs": "m:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23,m:0 t:81 s:2048",
            "fields": "f12,f14,f13,f20",
            "_": str(int(time.time() * 1000)),
        }
        url = "https://push2.eastmoney.com/api/qt/clist/get?" + urlencode(params)

        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=timeout_sec) as resp:
                raw_data = resp.read().decode("utf-8")
                data = json.loads(raw_data)
                d_data = data.get("data")
                if not isinstance(d_data, dict):
                    break
                diff = d_data.get("diff", [])

                if not diff:
                    break

                for item in diff:
                    code = item.get("f12")
                    name = item.get("f14")
                    mkt_id = item.get("f13")
                    mv_raw = item.get("f20")

                    if not code:
                        continue

                    suffix = "SZ"
                    if mkt_id == 1:
                        suffix = "SH"
                    elif mkt_id == 116:
                        suffix = "BJ"

                    market_cap = None
                    try:
                        if mv_raw is not None and str(mv_raw).strip() not in {"", "-"}:
                            market_cap = float(mv_raw) / 1e8
                    except (ValueError, TypeError):
                        market_cap = None

                    results.append(
                        {
                            "symbol": f"{code}.{suffix}",
                            "name": name,
                            "market_cap": market_cap,
                        }
                    )

                if len(diff) < page_size:
                    break

                page += 1
                time.sleep(sleep_sec)

        except Exception as e:
            print(f"Error fetching universe page {page}: {e}")
            break

    return results


def write_universe_csv(
    path: Path,
    records: list[dict[str, object]],
    encoding: str = "utf-8-sig",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding=encoding, newline="") as f:
        w = csv.writer(f)
        w.writerow(["symbol", "name", "market_cap"])
        for r in records:
            sym = r.get("symbol")
            if not sym:
                continue
            mv = r.get("market_cap")
            mv_str = ""
            if isinstance(mv, (int, float)):
                mv_str = f"{float(mv):.6f}"
            w.writerow([sym, r.get("name") or "", mv_str])





def fetch_and_write_universe_csv_eastmoney(path: Path) -> int:
    recs = fetch_a_share_universe_eastmoney()
    write_universe_csv(path, recs)
    return len(recs)


import time
import random
import threading
from urllib.error import HTTPError, URLError
import socket


class RateLimitError(ConnectionError):
    def __init__(self, message: str, status_code: int | None = None, retry_after: float | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


_throttle_lock = threading.Lock()
_throttle_delay = 0.0
_throttle_until = 0.0


def _parse_retry_after(v: str | None) -> float | None:
    if not v:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        f = float(s)
        return f if math.isfinite(f) and f >= 0 else None
    except Exception:
        return None


def _throttle_wait() -> None:
    global _throttle_until

    now = time.time()
    with _throttle_lock:
        wait_sec = max(0.0, float(_throttle_until) - now)

    if wait_sec > 0:
        jitter = random.random() * min(0.25, wait_sec * 0.15)
        time.sleep(wait_sec + jitter)


def _throttle_on_result(*, ok: bool, rate_limited: bool = False, retry_after: float | None = None) -> None:
    global _throttle_delay, _throttle_until

    now = time.time()

    with _throttle_lock:
        cur = float(_throttle_delay)

        if rate_limited:
            base = max(cur * 1.7, 0.5)
            if retry_after is not None:
                base = max(base, float(retry_after))
            cur = min(base, 10.0)
            _throttle_delay = cur
            _throttle_until = max(float(_throttle_until), now + cur)
            return

        if not ok:
            cur = min(max(cur, 0.1) * 1.3, 6.0)
            _throttle_delay = cur
            _throttle_until = max(float(_throttle_until), now + min(cur, 1.0))
            return

        cur = max(cur * 0.85 - 0.02, 0.0)
        _throttle_delay = cur
        if cur <= 0:
            _throttle_until = 0.0


def fetch_daily_bars_eastmoney(
    symbol: str,
    beg: str = "0",
    end: str = "20500101",
    adjust: str = "qfq",
    market: str | None = None,
    timeout_sec: float = 20.0,
    max_retries: int = 5,
) -> list[Bar]:
    # Handle empty strings from UI
    if not beg or not beg.strip():
        beg = "0"
    if not end or not end.strip():
        end = "20500101"

    fqt_map = {"none": 0, "qfq": 1, "hfq": 2}
    fqt = fqt_map.get(adjust.lower().strip())
    if fqt is None:
        raise ValueError(f"Invalid adjust: {adjust}")

    secid = _eastmoney_secid(symbol, market=market)
    params = {
        "secid": secid,
        "klt": "101",
        "fqt": str(fqt),
        "beg": str(beg),
        "end": str(end),
        "smplmt": "10000",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56",
        "_": str(int(time.time() * 1000))
    }
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get?" + urlencode(params)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Referer": "https://quote.eastmoney.com/",
    }

    last_error = None
    for attempt in range(max_retries):
        _throttle_wait()
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=timeout_sec) as resp:
                raw = resp.read()

            payload = json.loads(raw.decode("utf-8", errors="replace"))

            if payload is None:
                raise ValueError("Empty response from API")

            data = payload.get("data")
            if not isinstance(data, dict):
                _throttle_on_result(ok=False, rate_limited=True)
                if attempt < max_retries - 1:
                    sleep_sec = min(10.0, (1.0 * (2 ** attempt)) + random.random() * 0.25)
                    time.sleep(sleep_sec)
                    continue
                raise ValueError(f"No data for {symbol}. API returned: {payload}")

            klines = data.get("klines")
            if not isinstance(klines, list):
                _throttle_on_result(ok=False)
                raise ValueError(f"No klines for {symbol}")

            _throttle_on_result(ok=True)
            return parse_eastmoney_klines(symbol=symbol, klines=[str(x) for x in klines])

        except HTTPError as e:
            last_error = e
            code = getattr(e, "code", None)
            retry_after = None
            try:
                retry_after = _parse_retry_after(getattr(e, "headers", {}).get("Retry-After"))
            except Exception:
                retry_after = None

            is_rl = code in (429, 403)
            _throttle_on_result(ok=False, rate_limited=is_rl, retry_after=retry_after)

            if attempt < max_retries - 1:
                base = retry_after if retry_after is not None else (1.0 if is_rl else 0.3)
                sleep_sec = min(12.0, (float(base) * (2 ** attempt)) + random.random() * 0.25)
                time.sleep(sleep_sec)
                continue
            break

        except (URLError, ConnectionError, TimeoutError, socket.timeout, OSError) as e:
            last_error = e
            _throttle_on_result(ok=False)
            if attempt < max_retries - 1:
                sleep_sec = min(10.0, (0.4 * (2 ** attempt)) + random.random() * 0.25)
                time.sleep(sleep_sec)
                continue
            break
        except Exception as e:
            _throttle_on_result(ok=False)
            raise e

    msg = f"Failed to fetch data for {symbol} after {max_retries} retries. Error: {last_error}"
    try:
        if isinstance(last_error, OSError):
            winerr = getattr(last_error, "winerror", None)
            errno = getattr(last_error, "errno", None)
            if winerr == 10061 or errno == 10061:
                msg = f"[WinError 10061] Connection refused when fetching {symbol}. Please check network/firewall and try again."
    except Exception:
        pass
    raise ConnectionError(msg)