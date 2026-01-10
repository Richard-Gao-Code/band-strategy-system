from __future__ import annotations
import asyncio
import csv
import datetime
import json
import logging
import math
import os
import re
import shutil
import secrets
import sys
import time
from pathlib import Path
from urllib.parse import quote
from typing import Any, Optional
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from contextlib import asynccontextmanager


def _json_sanitize(x: Any) -> Any:
    if x is None:
        return None

    if isinstance(x, (str, int, bool)):
        return x

    if isinstance(x, float):
        return x if math.isfinite(x) else None

    if isinstance(x, dict):
        return {str(k): _json_sanitize(v) for k, v in x.items()}

    if isinstance(x, (list, tuple)):
        return [_json_sanitize(v) for v in x]

    item = getattr(x, "item", None)
    if callable(item):
        try:
            return _json_sanitize(item())
        except Exception:
            pass

    return x


def _json_dumps(x: Any) -> str:
    return json.dumps(_json_sanitize(x), ensure_ascii=False, allow_nan=False)

app_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(app_dir))

from core.scanner_runner import scan_channel_hf_for_symbol_path, backtest_channel_hf_for_symbol_path, BatchTaskManager
from core.debug_runner import debug_analyze_channel_hf, reanalyze_channel_hf_trade_features
from core.batch_runner import resolve_file_path, resolve_any_path
from core.data import fetch_all_a_share_symbols, inspect_csv_quality, inspect_dir_quality, sync_incremental_data, fetch_block_constituents, find_block_code
from core.smart_analyze import SmartAnalyzer
from core.selector import run_selection

logger = logging.getLogger(__name__)
batch_task_manager = BatchTaskManager()

DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")


class RunReq(BaseModel):
    symbol: str | None = None
    data: str | None = None
    data_dir: str | None = None
    index_data: str | None = None
    index_symbol: str | None = "000300.SH"
    beg: str | None = None
    end: str | None = None
    scan_recent_days: int = 1
    calc_score: bool = False
    calc_robust: bool = False
    robust_segments: int = 0
    use_realtime: bool = False
    symbols: list[str] | None = None

    channel_period: int = 20
    trend_ma_period: int = 0
    index_trend_ma_period: int = 0
    require_rebound: bool = False
    require_green: bool = False
    
    buy_touch_eps: float | None = 0.005
    sell_trigger_eps: float | None = 0.005
    sell_target_mode: str | None = "mid_up"
    channel_break_eps: float | None = 0.02

    entry_fill_eps: float | None = 0.002
    exit_fill_eps: float | None = 0.002

    stop_loss_mul: float = 0.97
    stop_loss_pct: float | None = None
    stop_loss_on_close: bool = True
    stop_loss_panic_eps: float = 0.02

    max_holding_days: int = 20
    cooling_period: int = 5

    slope_abs_max: float = 0.01
    slope_vol_max: float | None = 0.01
    min_slope_norm: float = -1.0
    
    vol_shrink_threshold: float | None = 0.9
    vol_shrink_min: float | None = None
    vol_shrink_max: float | None = None

    min_channel_height: float | None = 0.05
    min_mid_room: float | None = 0.015
    min_mid_profit_pct: float = 0.0
    min_rr_to_mid: float = 0.0

    require_index_condition: bool = True
    index_bear_exit: bool = True
    fill_at_close: bool = True
    detail: bool = True


class ParamBatchReq(RunReq):
    param_sets: list[dict[str, Any]] | None = None


class DataSyncReq(BaseModel):
    out_dir: str
    symbols: list[str] | None = None
    full: bool = False
    beg: str = "20150101"
    end: str = "20500101"
    adjust: str = "qfq"
    market: str | None = None
    tail_days: int = 5
    max_concurrency: int = 8


class FetchConstituentsReq(BaseModel):
    index_name: str


class DataScheduleReq(DataSyncReq):
    interval_min: int = 60
    post_backtest: bool = False
    post_backtest_topn: int = 20
    post_backtest_stage1_topk: int = 200
    post_backtest_robust_segments: int = 4
    post_backtest_min_trades: int = 0
    post_backtest_index_symbol: str = "000300.SH"
    post_backtest_beg: str | None = None
    post_backtest_end: str | None = None


class DataQualityReq(BaseModel):
    data_dir: str
    symbols: list[str] | None = None
    max_gap_days: int = 15
    gap_open_abs_pct: float = 0.2
    min_rows: int = 60
    stale_days: int = 10
    min_list_days: int = 1460 # Default 4 years
    check_st: bool = True
    min_avg_amount: float = 10000000.0 # Default 1000w
    min_price: float = 3.0
    fatal_types: list[str] | None = None


class SmartAnalyzeReq(BaseModel):
    file_path: str
    query: str


executor = None
executor_max_workers = 0
io_executor = None
_data_sched_task: asyncio.Task | None = None
_data_sched_stop: asyncio.Event | None = None
_data_sched_lock = asyncio.Lock()
_data_sched_state: dict[str, Any] = {
    "running": False,
    "interval_min": 0,
    "cfg": None,
    "phase": None,
    "progress_text": None,
    "progress_done": 0,
    "progress_total": 0,
    "last_run_at": None,
    "last_summary": None,
    "last_backtest_at": None,
    "last_backtest": None,
    "last_error": None,
}

_scan_jobs: dict[str, dict[str, Any]] = {}
_scan_jobs_lock = asyncio.Lock()

_trade_feature_lock = asyncio.Lock()
_trade_feature_dir = app_dir / "exports"
_trade_feature_store_path = _trade_feature_dir / "trade_features.json"

def _parse_date_any(s: str | None) -> datetime.date | None:
    if not s:
        return None
    v = str(s).strip()
    if not v:
        return None
    if re.fullmatch(r"\d{8}", v):
        try:
            return datetime.datetime.strptime(v, "%Y%m%d").date()
        except Exception:
            return None
    try:
        return datetime.datetime.fromisoformat(v).date()
    except Exception:
        return None

def _ensure_trade_feature_dir() -> None:
    try:
        _trade_feature_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

def _load_trade_feature_store() -> list[dict[str, Any]]:
    _ensure_trade_feature_dir()
    if not _trade_feature_store_path.exists():
        return []
    try:
        with open(_trade_feature_store_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []

def _save_trade_feature_store(items: list[dict[str, Any]]) -> None:
    _ensure_trade_feature_dir()
    tmp = _trade_feature_store_path.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        tmp.replace(_trade_feature_store_path)
    except Exception:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass

def _upsert_trade_feature_records(
    *,
    existing: list[dict[str, Any]],
    new_snapshots: list[dict[str, Any]],
    params_snapshot: dict[str, Any] | None,
    now_iso: str,
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for it in existing:
        if isinstance(it, dict) and it.get("transaction_id"):
            by_id[str(it["transaction_id"])] = it

    for snap in new_snapshots:
        if not isinstance(snap, dict):
            continue
        tid = str(snap.get("transaction_id") or "").strip()
        if not tid:
            continue
        rec = by_id.get(tid)
        if not rec:
            rec = {
                "transaction_id": tid,
                "created_at": now_iso,
            }
            by_id[tid] = rec
        rec["updated_at"] = now_iso
        if params_snapshot is not None:
            rec["params_snapshot"] = params_snapshot
        if "feature_snapshot_original" not in rec or not isinstance(rec.get("feature_snapshot_original"), dict):
            rec["feature_snapshot_original"] = snap
        rec["feature_snapshot"] = snap
        for k in ("stock_code", "entry_date", "exit_date", "entry_dt", "exit_dt", "return_rate", "exit_reason"):
            if k in snap:
                rec[k] = snap.get(k)
    out = list(by_id.values())
    out.sort(key=lambda x: str(x.get("entry_dt") or x.get("entry_date") or ""))
    return out

async def _persist_trade_features_from_debug_result(res: dict[str, Any]) -> None:
    if not isinstance(res, dict):
        return
    if str(res.get("status") or "") != "success":
        return
    trades = res.get("trades")
    if not isinstance(trades, list) or not trades:
        return
    snaps = []
    for t in trades:
        if not isinstance(t, dict):
            continue
        fs = t.get("feature_snapshot")
        if isinstance(fs, dict) and fs.get("transaction_id"):
            fs2 = dict(fs)
            if t.get("entry_dt"):
                fs2["entry_dt"] = t.get("entry_dt")
            if t.get("exit_dt"):
                fs2["exit_dt"] = t.get("exit_dt")
            if t.get("qty") is not None:
                fs2["qty"] = t.get("qty")
            snaps.append(fs2)
    if not snaps:
        return
    now_iso = datetime.datetime.now().isoformat(timespec="seconds")
    params_snapshot = res.get("params") if isinstance(res.get("params"), dict) else None
    async with _trade_feature_lock:
        existing = _load_trade_feature_store()
        merged = _upsert_trade_feature_records(existing=existing, new_snapshots=snaps, params_snapshot=params_snapshot, now_iso=now_iso)
        _save_trade_feature_store(merged)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global executor, executor_max_workers, io_executor

    io_workers_raw = os.environ.get("CHHF_IO_WORKERS", "")
    try:
        io_workers = int(io_workers_raw) if str(io_workers_raw).strip() else max(32, int((os.cpu_count() or 2) * 8))
    except Exception:
        io_workers = max(32, int((os.cpu_count() or 2) * 8))
    io_workers = max(4, min(io_workers, 256))
    io_executor = ThreadPoolExecutor(max_workers=io_workers)

    max_workers_raw = os.environ.get("CHHF_MAX_WORKERS", "")
    cpu_n = int(os.cpu_count() or 2)
    try:
        max_workers = int(max_workers_raw) if str(max_workers_raw).strip() else min(8, cpu_n)
    except Exception:
        max_workers = min(8, cpu_n)
    max_workers = max(1, min(max_workers, 64))
    executor_max_workers = int(max_workers)
    executor = ProcessPoolExecutor(max_workers=max_workers)

    yield

    try:
        io_executor.shutdown()
    except Exception:
        pass
    executor.shutdown()

app = FastAPI(lifespan=lifespan)
static_dir = Path(__file__).resolve().parent / "static_bak"
if not static_dir.exists():
    print(f"Warning: static directory {static_dir} does not exist, creating it.")
    static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


class SelectorReq(BaseModel):
    path_ud: str
    path_mu: str
    max_mdd: float = 0.10
    min_trd: int = 15
    calmar_min: float = 3.0


@app.post("/api/selector")
async def api_selector(req: SelectorReq):
    try:
        def resolve_csv_path(user_path: str, default_name: str) -> Path:
            p = Path(user_path)
            if p.is_dir():
                return p / default_name
            return p

        p_ud = resolve_csv_path(req.path_ud, "上轨下系100.csv")
        p_mu = resolve_csv_path(req.path_mu, "中轨上系100.csv")
        
        if not p_ud.exists():
             raise HTTPException(status_code=400, detail=f"文件不存在: {p_ud}")
        if not p_ud.is_file():
             raise HTTPException(status_code=400, detail=f"路径不是文件: {p_ud}")

        if not p_mu.exists():
             raise HTTPException(status_code=400, detail=f"文件不存在: {p_mu}")
        if not p_mu.is_file():
             raise HTTPException(status_code=400, detail=f"路径不是文件: {p_mu}")

        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(
            None,
            lambda: run_selection(
                p_ud, 
                p_mu, 
                max_mdd=req.max_mdd, 
                min_trd=req.min_trd, 
                calmar_min=req.calmar_min
            )
        )
        return {"status": "success", "data": res}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---- Preset Management APIs ----

PRESETS_DIR = Path(__file__).parent / "presets"
ACTIVE_PRESET_FILE = PRESETS_DIR / "active_preset.txt"
CONFIG_PATH = Path(__file__).parent / "config.json"

PRESETS_DIR.mkdir(parents=True, exist_ok=True)

def get_config_dict() -> dict[str, Any]:
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                v = json.load(f)
            return v if isinstance(v, dict) else {}
    except Exception:
        pass
    return {}


DEFAULT_PRESET_ORDER = ["默认", "保守", "激进"]


def _default_presets() -> dict[str, dict[str, Any]]:
    base = get_config_dict()
    return {
        "默认": dict(base),
        "保守": {
            **base,
            "vol_shrink_min": 1.04,
            "vol_shrink_max": 1.10,
            "min_channel_height": 0.06,
            "max_positions": 3,
            "max_position_pct": 0.08,
        },
        "激进": {
            **base,
            "vol_shrink_min": 0.98,
            "vol_shrink_max": 1.20,
            "min_channel_height": 0.04,
            "max_positions": 8,
            "max_position_pct": 0.12,
        },
    }


def _list_preset_names() -> list[str]:
    files = list(PRESETS_DIR.glob("*.json"))
    disk = sorted({f.stem for f in files})
    defaults = _default_presets()
    ordered_defaults = [n for n in DEFAULT_PRESET_ORDER if n in defaults and n not in disk]
    return ordered_defaults + disk


def _load_preset_config(name: str) -> dict[str, Any] | None:
    nm = (name or "").strip()
    if not nm:
        return None
    target = PRESETS_DIR / f"{nm}.json"
    if target.exists():
        try:
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return None
    defaults = _default_presets()
    if nm in defaults:
        data = defaults.get(nm) or {}
        return data if isinstance(data, dict) else {}
    return None


def save_config_dict(data: Any) -> bool:
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data if data is not None else {}, f, ensure_ascii=False, indent=4)
        return True
    except Exception:
        return False


def _get_active_preset_name() -> str:
    if ACTIVE_PRESET_FILE.exists():
        try:
            return ACTIVE_PRESET_FILE.read_text("utf-8").strip()
        except Exception:
            pass
    return ""


def _set_active_preset_name(name: str) -> None:
    try:
        ACTIVE_PRESET_FILE.write_text(name or "", encoding="utf-8")
    except Exception:
        pass


@app.get("/api/presets")
def api_list_presets():
    active = _get_active_preset_name()
    if active and not (PRESETS_DIR / f"{active}.json").exists() and active not in _default_presets():
        active = ""
        _set_active_preset_name("")
    return {"presets": _list_preset_names(), "active": active}


@app.get("/api/presets/get")
def api_get_preset(name: str = ""):
    nm = (name or "").strip()
    if not nm:
        return {"ok": False, "msg": "名称不能为空"}

    data = _load_preset_config(nm)
    if data is None:
        return {"ok": False, "msg": f"预设 {nm} 不存在"}
    return {"ok": True, "config": data}


class PresetReq(BaseModel):
    name: str
    cfg: dict[str, Any] | None = None


@app.post("/api/config/save")
def api_save_current_config(req: dict[str, Any]):
    """Save the provided config directly to config.json (used for live sync)"""
    if save_config_dict(req):
        return {"ok": True, "msg": "Config synced"}
    return {"ok": False, "msg": "Failed to sync config"}


@app.post("/api/presets/save")
def api_save_preset(req: PresetReq):
    name = req.name.strip()
    if not name:
        return {"ok": False, "msg": "名称不能为空"}

    current = req.cfg if (req.cfg and isinstance(req.cfg, dict)) else get_config_dict()
    if not current:
        return {"ok": False, "msg": "当前配置为空，无法保存"}

    target = PRESETS_DIR / f"{name}.json"
    try:
        with open(target, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=4)
        return {"ok": True, "msg": f"已保存预设: {name}"}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


@app.post("/api/presets/load")
def api_load_preset(req: PresetReq):
    name = req.name.strip()
    target = PRESETS_DIR / f"{name}.json"
    if not name:
        return {"ok": False, "msg": "名称不能为空"}

    try:
        # If cfg is provided in request, use it and update the preset file too
        if req.cfg and isinstance(req.cfg, dict):
            data = req.cfg
            with open(target, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        else:
            data = _load_preset_config(name)
            if data is None:
                return {"ok": False, "msg": f"预设 {name} 不存在"}

        if save_config_dict(data):
            try:
                from core.analyzer import reload_config
                reload_config()
            except Exception:
                pass
            _set_active_preset_name(name)
            return {"ok": True, "msg": f"已应用预设: {name}", "config": data}

        return {"ok": False, "msg": "写入config.json失败"}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


@app.post("/api/presets/delete")
def api_delete_preset(req: PresetReq):
    name = req.name.strip()
    target = PRESETS_DIR / f"{name}.json"
    if not name:
        return {"ok": False, "msg": "名称不能为空"}
    if name in _default_presets() and not target.exists():
        return {"ok": False, "msg": f"内置预设 {name} 不支持删除"}
    if not target.exists():
        return {"ok": False, "msg": f"预设 {name} 不存在"}

    try:
        target.unlink()
        if _get_active_preset_name() == name:
            _set_active_preset_name("")
        return {"ok": True, "msg": f"已删除预设: {name}"}
    except Exception as e:
        return {"ok": False, "msg": str(e)}

# ---- End Preset APIs ----

@app.get("/")
def index() -> Any:
    return FileResponse(static_dir / "index.html")


@app.post("/api/scan")
async def api_scan(req: RunReq):
    try:
        loop = asyncio.get_event_loop()

        # Resolve the directory path first
        base_dir = await loop.run_in_executor(None, resolve_any_path, req.data_dir)
        if not base_dir or not base_dir.is_dir():
            raise HTTPException(status_code=400, detail=f"无效的股票目录地址: {req.data_dir}")

        # Scan directory for CSV files and build symbol_paths map
        symbol_paths = {}
        for f in base_dir.glob("*.csv"):
            symbol = f.stem  # Filename without extension
            symbol_paths[symbol] = f

        if not symbol_paths:
            raise HTTPException(status_code=400, detail="目录下未找到任何CSV数据文件")

        # Filter out index symbols if provided
        if req.index_symbol:
            idx_prefix = req.index_symbol.split(".")[0].upper()
            symbol_paths = {
                s: p
                for s, p in symbol_paths.items()
                if not (
                    s.upper() == "BENCH"
                    or s.upper() == idx_prefix
                    or s.upper().startswith(idx_prefix + ".")
                )
            }

        if req.symbols:
            wanted_raw = [str(s).strip() for s in (req.symbols or []) if str(s).strip()]
            wanted: set[str] = set()
            for x in wanted_raw:
                u = x.upper()
                wanted.add(u)
                wanted.add(u.split(".")[0])

            def _keep(sym: str) -> bool:
                u = sym.upper()
                return u in wanted or u.split(".")[0] in wanted

            symbol_paths = {s: p for s, p in symbol_paths.items() if _keep(s)}

        if not symbol_paths:
            raise HTTPException(status_code=400, detail="过滤后无有效股票数据")

        index_path = None
        if req.index_data:
            index_path = await loop.run_in_executor(None, resolve_file_path, req.index_data)
            if index_path is None:
                raise HTTPException(status_code=400, detail=f"无效的指数数据文件: {req.index_data}")

        cfg = req.dict()

        async def result_generator():
            job_id = secrets.token_hex(8)
            cancel_ev = asyncio.Event()
            async with _scan_jobs_lock:
                _scan_jobs[job_id] = {
                    "running": True,
                    "cancelled": False,
                    "total": 0,
                    "done": 0,
                    "errors": 0,
                    "started_at": time.time(),
                    "ended_at": None,
                    "job_id": job_id,
                    "cancel_ev": cancel_ev,
                }

            try:
                symbols_local = list(symbol_paths.keys())
                total = len(symbols_local)
                pool = executor if total > 1 else None
                max_parallel = max(1, min(executor_max_workers or 1, total))
                async with _scan_jobs_lock:
                    if job_id in _scan_jobs:
                        _scan_jobs[job_id]["total"] = total

                yield _json_dumps({"type": "start", "job_id": job_id, "total": total}) + "\n"

                remaining = list(symbols_local)
                active: set[asyncio.Future] = set()
                fut_to_sym: dict[asyncio.Future, str] = {}

                def _schedule_one(sym: str) -> asyncio.Future:
                    path = symbol_paths[sym]
                    fut = loop.run_in_executor(
                        pool,
                        scan_channel_hf_for_symbol_path,
                        sym,
                        path,
                        index_path,
                        cfg,
                    )
                    fut_to_sym[fut] = sym
                    return fut

                def _fill_active() -> None:
                    while remaining and len(active) < max_parallel and not cancel_ev.is_set():
                        sym = remaining.pop(0)
                        active.add(_schedule_one(sym))

                _fill_active()

                last_beat = time.perf_counter()

                done = 0
                errors = 0

                while active:
                    if cancel_ev.is_set():
                        break

                    done_set, _ = await asyncio.wait(
                        active,
                        timeout=2.0,
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    if not done_set:
                        now = time.perf_counter()
                        if now - last_beat >= 5.0:
                            last_beat = now
                            prog = f"{done}/{total}"
                            yield _json_dumps({"type": "heartbeat", "progress": prog}) + "\n"
                        continue

                    for fut in done_set:
                        active.remove(fut)
                        sym = fut_to_sym.pop(fut, "")
                        done += 1
                        prog = f"{done}/{total}"
                        try:
                            res = await fut
                            yield _json_dumps({"type": "result", "status": "success", "data": res, "progress": prog}) + "\n"
                        except Exception as e:
                            errors += 1
                            yield _json_dumps({"type": "error", "message": str(e), "progress": prog}) + "\n"
                        finally:
                            async with _scan_jobs_lock:
                                if job_id in _scan_jobs:
                                    _scan_jobs[job_id]["done"] = done
                                    _scan_jobs[job_id]["errors"] = errors

                    _fill_active()

                if cancel_ev.is_set():
                    for fut in list(active):
                        try:
                            fut.cancel()
                        except Exception:
                            pass
                    async with _scan_jobs_lock:
                        if job_id in _scan_jobs:
                            _scan_jobs[job_id]["running"] = False
                            _scan_jobs[job_id]["cancelled"] = True
                            _scan_jobs[job_id]["ended_at"] = time.time()
                    yield _json_dumps({"type": "cancelled", "progress": f"{done}/{total}"}) + "\n"
                    yield _json_dumps({"type": "end"}) + "\n"
                    return

                async with _scan_jobs_lock:
                    if job_id in _scan_jobs:
                        _scan_jobs[job_id]["running"] = False
                        _scan_jobs[job_id]["ended_at"] = time.time()
                yield _json_dumps({"type": "end"}) + "\n"
            except Exception as e:
                async with _scan_jobs_lock:
                    if job_id in _scan_jobs:
                        _scan_jobs[job_id]["running"] = False
                        _scan_jobs[job_id]["ended_at"] = time.time()
                yield _json_dumps({"type": "error", "message": str(e)}) + "\n"
            except asyncio.CancelledError:
                cancel_ev.set()
                async with _scan_jobs_lock:
                    if job_id in _scan_jobs:
                        _scan_jobs[job_id]["running"] = False
                        _scan_jobs[job_id]["cancelled"] = True
                        _scan_jobs[job_id]["ended_at"] = time.time()
                raise
            finally:
                async with _scan_jobs_lock:
                    _scan_jobs.pop(job_id, None)

        return StreamingResponse(result_generator(), media_type="application/x-ndjson")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ScanCancelReq(BaseModel):
    job_id: str


@app.post("/api/scan/cancel")
async def api_scan_cancel(req: ScanCancelReq):
    jid = (req.job_id or "").strip()
    if not jid:
        raise HTTPException(status_code=400, detail="job_id 不能为空")

    async with _scan_jobs_lock:
        job = _scan_jobs.get(jid)
        if not job:
            return {"ok": False, "msg": "任务不存在或已结束"}
        ev = job.get("cancel_ev")
        if isinstance(ev, asyncio.Event):
            ev.set()
        job["cancelled"] = True
        job["running"] = False
        job["ended_at"] = time.time()
    return {"ok": True, "msg": "已请求中断"}


@app.post("/api/backtest")
async def api_backtest(req: RunReq):
    try:
        loop = asyncio.get_event_loop()

        base_dir = await loop.run_in_executor(None, resolve_any_path, req.data_dir)
        if not base_dir or not base_dir.is_dir():
            raise HTTPException(status_code=400, detail=f"无效的股票目录地址: {req.data_dir}")

        symbol_paths = {}
        for f in base_dir.glob("*.csv"):
            symbol = f.stem
            symbol_paths[symbol] = f

        if not symbol_paths:
            raise HTTPException(status_code=400, detail="目录下未找到任何CSV数据文件")

        # 排除常见指数文件，避免它们被当做股票进行回测
        # 除非用户明确指定了要回测这些 specific symbols (via req.symbols)
        if not req.symbols:
            common_indices_prefixes = {"000001", "000300", "000905", "000852", "399001", "399006", "899050", "BENCH"}
            symbol_paths = {
                s: p
                for s, p in symbol_paths.items()
                if not any(s.upper().startswith(prefix) for prefix in common_indices_prefixes)
            }

        if req.symbols:
             wanted_raw = [str(s).strip() for s in req.symbols if str(s).strip()]
             wanted = set()
             for x in wanted_raw:
                 wanted.add(x.upper())
                 wanted.add(x.upper().split(".")[0])
             
             def _keep(sym: str) -> bool:
                 u = sym.upper()
                 return u in wanted or u.split(".")[0] in wanted
             
             symbol_paths = {s: p for s, p in symbol_paths.items() if _keep(s)}
        
        if not symbol_paths:
            raise HTTPException(status_code=400, detail="No symbols found after filter")

        index_path = None
        if req.index_data:
            index_path = await loop.run_in_executor(None, resolve_file_path, req.index_data)

        cfg = req.dict()
        
        # Generator for streaming results
        async def result_generator():
            try:
                symbols_local = list(symbol_paths.keys())
                pool = executor if len(symbols_local) > 1 else None
                yield _json_dumps({"type": "start", "total": len(symbols_local)}) + "\n"
                tasks = []
                for sym in symbols_local:
                    path = symbol_paths[sym]
                    tasks.append(
                        loop.run_in_executor(
                            pool,
                            backtest_channel_hf_for_symbol_path,
                            sym,
                            path,
                            index_path,
                            cfg,
                        )
                    )
                
                pending = set(tasks)
                done = 0
                total = len(tasks)
                last_beat = time.perf_counter()

                while pending:
                    done_set, _ = await asyncio.wait(
                        pending,
                        timeout=2.0,
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    
                    if not done_set:
                        now = time.perf_counter()
                        if now - last_beat >= 5.0:
                            last_beat = now
                            prog = f"{done}/{total}"
                            yield _json_dumps({"type": "heartbeat", "progress": prog}) + "\n"
                        continue

                    for fut in done_set:
                        pending.remove(fut)
                        done += 1
                        prog = f"{done}/{total}"
                        try:
                            res = await fut
                            yield _json_dumps({"type": "result", "status": "success", "data": res, "progress": prog}) + "\n"
                        except Exception as e:
                            yield _json_dumps({"type": "error", "message": str(e), "progress": prog}) + "\n"

                yield _json_dumps({"type": "end"}) + "\n"
            except Exception as e:
                yield _json_dumps({"type": "error", "message": str(e)}) + "\n"

        return StreamingResponse(result_generator(), media_type="application/x-ndjson")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/param_batch_test")
async def api_param_batch_test(req: ParamBatchReq):
    try:
        loop = asyncio.get_event_loop()

        base_dir = await loop.run_in_executor(None, resolve_any_path, req.data_dir)
        if not base_dir or not base_dir.is_dir():
            raise HTTPException(status_code=400, detail=f"无效的股票目录地址: {req.data_dir}")

        symbol_paths = {}
        for f in base_dir.glob("*.csv"):
            symbol = f.stem
            symbol_paths[symbol] = f

        if not symbol_paths:
            raise HTTPException(status_code=400, detail="目录下未找到任何CSV数据文件")

        if not req.symbols:
            common_indices_prefixes = {"000001", "000300", "000905", "000852", "399001", "399006", "899050", "BENCH"}
            symbol_paths = {
                s: p
                for s, p in symbol_paths.items()
                if not any(s.upper().startswith(prefix) for prefix in common_indices_prefixes)
            }

        if req.symbols:
            wanted_raw = [str(s).strip() for s in req.symbols if str(s).strip()]
            wanted = set()
            for x in wanted_raw:
                wanted.add(x.upper())
                wanted.add(x.upper().split(".")[0])

            def _keep(sym: str) -> bool:
                u = sym.upper()
                return u in wanted or u.split(".")[0] in wanted

            symbol_paths = {s: p for s, p in symbol_paths.items() if _keep(s)}

        if not symbol_paths:
            raise HTTPException(status_code=400, detail="No symbols found after filter")

        index_path = None
        if req.index_data:
            index_path = await loop.run_in_executor(None, resolve_file_path, req.index_data)

        cfg_base = req.dict()
        param_sets = req.param_sets if isinstance(req.param_sets, list) else []
        param_sets = [x for x in param_sets if isinstance(x, dict) and x]
        if not param_sets:
            raise HTTPException(status_code=400, detail="param_sets 不能为空")

        async def result_generator():
            started_at = datetime.datetime.now().isoformat()
            done = 0
            symbols_local = list(symbol_paths.keys())
            total = len(symbols_local) * len(param_sets)
            param_keys = set()
            for ps in param_sets:
                if not isinstance(ps, dict):
                    continue
                for k in ps.keys():
                    kk = str(k).strip()
                    if not kk or kk == "__name__":
                        continue
                    param_keys.add(kk)
            grid_metadata = {
                "combos": len(param_sets),
                "symbols": len(symbols_local),
                "total": total,
                "param_keys": sorted(param_keys),
            }
            st = batch_task_manager.create_task(total=total, grid_metadata=grid_metadata)
            task_id = st.task_id

            try:
                # 状态机：running -> completed / cancelled（cancelled 可随时由 cancel 接口触发）
                logger.info(
                    "Batch test started: task_id=%s total=%s combos=%s symbols=%s",
                    task_id,
                    total,
                    len(param_sets),
                    len(symbols_local),
                )
                yield _json_dumps({"type": "start", "task_id": task_id, "total": total, "combos": len(param_sets), "symbols": len(symbols_local), "started_at": started_at, "grid_metadata": grid_metadata}) + "\n"

                pool = executor if len(symbols_local) > 1 else None
                max_in_flight = max(1, min(16, int(executor_max_workers or 4)))

                for combo_idx, combo in enumerate(param_sets):
                    if batch_task_manager.is_cancel_requested(task_id):
                        break

                    combo_name = combo.get("__name__")
                    combo_label = str(combo_name).strip() if combo_name else f"组合{combo_idx + 1}"
                    merged_cfg = dict(cfg_base)
                    for k, v in combo.items():
                        if str(k).strip() == "__name__":
                            continue
                        merged_cfg[str(k)] = v

                    yield _json_dumps({"type": "combo_start", "combo_idx": combo_idx + 1, "combo_total": len(param_sets), "combo_label": combo_label}) + "\n"

                    symbols_iter = iter(symbols_local)
                    pending: set[asyncio.Future] = set()

                    def _submit_next() -> bool:
                        try:
                            sym = next(symbols_iter)
                        except StopIteration:
                            return False
                        path = symbol_paths[sym]
                        fut = loop.run_in_executor(
                            pool,
                            backtest_channel_hf_for_symbol_path,
                            sym,
                            path,
                            index_path,
                            merged_cfg,
                        )

                        def _swallow_future_exc(f: asyncio.Future) -> None:
                            try:
                                if f.cancelled():
                                    return
                                _ = f.exception()
                            except Exception:
                                return

                        fut.add_done_callback(_swallow_future_exc)
                        pending.add(fut)
                        return True

                    for _ in range(max_in_flight):
                        if batch_task_manager.is_cancel_requested(task_id):
                            break
                        if not _submit_next():
                            break

                    while pending:
                        if batch_task_manager.is_cancel_requested(task_id):
                            break

                        done_set, _ = await asyncio.wait(pending, timeout=2.0, return_when=asyncio.FIRST_COMPLETED)
                        if not done_set:
                            prog = f"{done}/{total}"
                            yield _json_dumps({"type": "heartbeat", "progress": prog, "total": total, "done": done}) + "\n"
                            continue

                        for fut in done_set:
                            pending.remove(fut)
                            done += 1
                            prog = f"{done}/{total}"
                            try:
                                res = await fut
                                res_for_agg = res if isinstance(res, dict) else None
                                if isinstance(res_for_agg, dict):
                                    res_for_agg = dict(res_for_agg)
                                    res_for_agg["__combo__"] = combo
                                    res_for_agg["__combo_label__"] = combo_label
                                    res_for_agg["__combo_idx__"] = combo_idx + 1
                                batch_task_manager.update_progress(task_id, res=res_for_agg)
                                payload = {
                                    "type": "result",
                                    "status": "success",
                                    "data": res,
                                    "progress": prog,
                                    "combo_idx": combo_idx + 1,
                                    "combo_total": len(param_sets),
                                    "combo_label": combo_label,
                                    "combo": combo,
                                }
                                yield _json_dumps(payload) + "\n"
                            except Exception as e:
                                batch_task_manager.update_progress(task_id, res={"error": str(e), "__combo__": combo, "__combo_label__": combo_label, "__combo_idx__": combo_idx + 1})
                                yield _json_dumps({"type": "error", "message": str(e), "progress": prog, "combo_label": combo_label}) + "\n"

                            if not batch_task_manager.is_cancel_requested(task_id):
                                _submit_next()

                ended_at = datetime.datetime.now().isoformat()
                if not batch_task_manager.is_cancel_requested(task_id):
                    batch_task_manager.mark_completed(task_id)
                    logger.info("Batch test completed: task_id=%s progress=%s/%s", task_id, done, total)
                    yield _json_dumps({"type": "end", "task_id": task_id, "ended_at": ended_at, "progress": f"{done}/{total}", "status": "completed"}) + "\n"
                else:
                    batch_task_manager.mark_cancelled(task_id)
                    logger.info("Batch test cancelled: task_id=%s progress=%s/%s", task_id, done, total)
                    yield _json_dumps({"type": "end", "task_id": task_id, "ended_at": ended_at, "progress": f"{done}/{total}", "status": "cancelled"}) + "\n"
            except asyncio.CancelledError:
                try:
                    batch_task_manager.request_cancel(task_id)
                    batch_task_manager.mark_cancelled(task_id)
                except Exception:
                    pass
                logger.info("Batch test client disconnected: task_id=%s", task_id)
                raise

        return StreamingResponse(result_generator(), media_type="application/x-ndjson")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/batch_test/cancel")
async def batch_test_cancel(request: Request):
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid JSON body")
    except Exception:
        raise HTTPException(status_code=400, detail="invalid request body")

    task_id = None
    if isinstance(payload, dict):
        task_id = payload.get("task_id")
    task_id = str(task_id).strip() if task_id is not None else ""
    if not task_id:
        raise HTTPException(status_code=400, detail="missing task_id")

    try:
        batch_task_manager.request_cancel(task_id)
        return {"status": "cancel_requested"}
    except KeyError:
        raise HTTPException(status_code=404, detail="task not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/batch_test/status")
async def batch_test_status(task_id: str = Query(..., description="批量任务ID")):
    try:
        return batch_task_manager.get_status(str(task_id).strip())
    except KeyError:
        raise HTTPException(status_code=404, detail="task not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/backtest_detail")
async def api_backtest_detail(req: RunReq):
    try:
        loop = asyncio.get_event_loop()

        if not req.data_dir:
            raise HTTPException(status_code=400, detail="缺少 data_dir")
        if not req.symbol:
            raise HTTPException(status_code=400, detail="缺少 symbol")

        base_dir = await loop.run_in_executor(None, resolve_any_path, req.data_dir)
        if not base_dir or not base_dir.is_dir():
            raise HTTPException(status_code=400, detail=f"无效的股票目录地址: {req.data_dir}")

        wanted = str(req.symbol).strip()
        wanted_u = wanted.upper()
        wanted_stem_u = wanted_u.split(".")[0]

        target_file: Path | None = None
        target_symbol: str | None = None
        for f in base_dir.glob("*.csv"):
            stem_u = f.stem.upper()
            stem_main = stem_u.split(".")[0]
            if stem_u == wanted_u or stem_main == wanted_u or stem_u == wanted_stem_u or stem_main == wanted_stem_u:
                target_file = f
                target_symbol = f.stem
                break

        if not target_file or not target_symbol:
            raise HTTPException(status_code=400, detail=f"未找到标的数据文件: {wanted}")

        index_path = None
        if req.index_data:
            index_path = await loop.run_in_executor(None, resolve_file_path, req.index_data)

        cfg = req.dict()
        cfg["detail"] = bool(req.detail)

        result = await loop.run_in_executor(
            executor,
            backtest_channel_hf_for_symbol_path,
            target_symbol,
            target_file,
            index_path,
            cfg,
        )

        if isinstance(result, dict) and result.get("error"):
            raise HTTPException(status_code=400, detail=str(result.get("error")))

        # 确保结果是 EventBacktestResult 对象，然后调用 to_dict()
        from core.event_engine import EventBacktestResult
        if isinstance(result, EventBacktestResult):
            result_dict = result.to_dict()
        else:
            # 如果已经是字典，直接使用
            result_dict = result

        # 添加必要的元数据
        result_dict.update({
            "symbol": target_symbol,
            "data_dir": str(base_dir),
            "beg": req.beg,
            "end": req.end,
        })

        return result_dict
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/backtest/detail")
async def api_backtest_detail_get(
    symbol: str = Query(..., description="标的代码"),
    data_dir: str = Query(..., description="数据目录路径"),
    config: str = Query(..., description="策略配置的JSON字符串"),
    beg: Optional[str] = Query(None, description="开始日期，YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="结束日期，YYYY-MM-DD"),
    detail: bool = Query(True, description="是否返回详情")
):
    """
    获取单标的回测详情 (GET接口，用于前端拒绝分析弹窗)
    此接口是对现有 POST /api/backtest_detail 的包装。
    """
    import json  # 确保导入json模块
    # 将查询参数组装成 AnalyzeReq 对象
    # 注意：前端传来的config是JSON字符串，需要解析为字典
    try:
        config_dict = json.loads(config)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid config JSON string")

    if not isinstance(config_dict, dict):
        raise HTTPException(status_code=400, detail="Invalid config JSON string")

    run_req = RunReq(
        symbol=symbol,
        data_dir=data_dir,
        beg=beg,
        end=end,
        detail=detail,
        **config_dict,
    )
    # 直接调用现有的 POST 接口处理逻辑
    return await api_backtest_detail(run_req)

def _resolve_out_dir(out_dir: str) -> Path:
    p = resolve_any_path(out_dir)
    if not p:
        raise HTTPException(status_code=400, detail=f"无效输出目录: {out_dir}")
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"创建输出目录失败: {p} ({e})")
    if not p.is_dir():
        raise HTTPException(status_code=400, detail=f"输出目录不是文件夹: {p}")
    return p

def _normalize_symbols(symbols: list[str] | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for s in (symbols or []):
        v = str(s).strip().upper()
        if not v:
            continue
        if v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out

def _backup_pool_path(out_dir: Path) -> Path:
    return out_dir / "backup_pool.json"

def _write_backup_pool(out_dir: Path, items: list[dict[str, Any]]) -> None:
    p = _backup_pool_path(out_dir)
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def _read_backup_pool(out_dir: Path) -> list[dict[str, Any]]:
    p = _backup_pool_path(out_dir)
    if not p.exists() or not p.is_file():
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, list) else []
    except Exception:
        return []

async def _sync_one_symbol(loop: asyncio.AbstractEventLoop, symbol: str, out_dir: Path, req: DataSyncReq) -> dict[str, Any]:
    sym = str(symbol).strip().upper()
    out_path = out_dir / f"{sym}.csv"

    max_retry = 3
    last_err: Exception | None = None
    for attempt in range(1, max_retry + 1):
        try:
            def _do() -> dict[str, Any]:
                bars = sync_incremental_data(
                    symbol=sym,
                    out_path=out_path,
                    beg=req.beg,
                    end=req.end,
                    adjust=req.adjust,
                    market=req.market,
                    tail_days=req.tail_days,
                )
                last_date = bars[-1].dt.isoformat() if bars else None
                return {"symbol": sym, "bars": len(bars), "last_date": last_date, "path": str(out_path)}

            return await loop.run_in_executor(io_executor, _do)
        except Exception as e:
            last_err = e
            await asyncio.sleep(min(2.0, 0.2 * attempt))

    return {"symbol": sym, "error": str(last_err or "同步失败")}

@app.post("/api/data/sync")
async def api_data_sync(req: DataSyncReq):
    try:
        loop = asyncio.get_event_loop()
        out_dir = await loop.run_in_executor(None, _resolve_out_dir, req.out_dir)

        symbols: list[str] = []
        if req.full:
            all_syms = await loop.run_in_executor(io_executor, fetch_all_a_share_symbols)
            market = str(req.market or "").strip().upper()
            for it in (all_syms or []):
                s = it.get("symbol") if isinstance(it, dict) else None
                if not s:
                    continue
                su = str(s).strip().upper()
                if market and not su.endswith("." + market):
                    continue
                symbols.append(su)
        else:
            symbols = _normalize_symbols(req.symbols)

        if not symbols:
            raise HTTPException(status_code=400, detail="未找到要同步的股票代码（请填写 symbols 或勾选全量）")

        max_conc = int(req.max_concurrency) if req.max_concurrency is not None else 8
        max_conc = max(1, min(max_conc, 64))
        sem = asyncio.Semaphore(max_conc)

        async def result_generator():
            try:
                total = len(symbols)
                yield _json_dumps({"type": "meta", "total": total, "out_dir": str(out_dir)}) + "\n"

                done = 0
                ok = 0
                bad = 0

                async def _run(sym: str) -> dict[str, Any]:
                    async with sem:
                        return await _sync_one_symbol(loop, sym, out_dir, req)

                pending: set[asyncio.Task] = set()
                for s in symbols:
                    pending.add(asyncio.create_task(_run(s)))

                while pending:
                    done_set, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED, timeout=2.0)
                    if not done_set:
                        yield _json_dumps({"type": "phase", "message": f"同步中... {done}/{total} ok={ok} err={bad}"}) + "\n"
                        continue

                    for t in done_set:
                        done += 1
                        prog = f"{done}/{total}"
                        try:
                            r = t.result()
                            if isinstance(r, dict) and r.get("error"):
                                bad += 1
                                yield _json_dumps({"type": "result", "status": "error", "data": r, "progress": prog}) + "\n"
                            else:
                                ok += 1
                                yield _json_dumps({"type": "result", "status": "success", "data": r, "progress": prog}) + "\n"
                        except Exception as e:
                            bad += 1
                            yield _json_dumps({"type": "result", "status": "error", "data": {"symbol": "-", "error": str(e)}, "progress": prog}) + "\n"

                yield _json_dumps({"type": "end", "total": total, "ok": ok, "err": bad}) + "\n"
            except Exception as e:
                yield _json_dumps({"type": "error", "message": str(e)}) + "\n"

        return StreamingResponse(result_generator(), media_type="application/x-ndjson")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/data/quality_check_stream")
async def api_data_quality_check_stream(req: DataQualityReq):
    try:
        loop = asyncio.get_event_loop()
        data_dir = await loop.run_in_executor(None, resolve_any_path, req.data_dir)
        if not data_dir or not data_dir.is_dir():
            raise HTTPException(status_code=400, detail=f"无效的股票目录地址: {req.data_dir}")

        wanted = None
        if req.symbols:
            wanted = set()
            for s in req.symbols:
                u = str(s).strip().upper()
                if not u:
                    continue
                wanted.add(u)
                wanted.add(u.split(".")[0])

        files: list[Path] = []
        for p in sorted(data_dir.glob("*.csv")):
            if wanted is not None:
                u = p.stem.upper()
                if u not in wanted and u.split(".")[0] not in wanted:
                    continue
            files.append(p)

        check_st = bool(req.check_st)
        name_map: dict[str, str] = {}
        if check_st:
            try:
                all_syms = await loop.run_in_executor(io_executor, fetch_all_a_share_symbols)
                for it in (all_syms or []):
                    if not isinstance(it, dict):
                        continue
                    s = it.get("symbol")
                    n = it.get("name")
                    if s and n:
                        su = str(s).strip().upper()
                        name_map[su] = str(n)
                        name_map[su.split(".")[0]] = str(n)
            except Exception:
                name_map = {}

        async def result_generator():
            try:
                total = len(files)
                yield _json_dumps({"type": "meta", "total": total}) + "\n"

                bad = 0
                done = 0
                for p in files:
                    sym = p.stem
                    nm = name_map.get(sym.upper()) or name_map.get(sym.upper().split(".")[0])
                    def _do_one() -> dict[str, Any]:
                        return inspect_csv_quality(
                            p,
                            symbol=sym,
                            name=nm,
                            max_gap_days=req.max_gap_days,
                            gap_open_abs_pct=req.gap_open_abs_pct,
                            min_rows=req.min_rows,
                            stale_days=req.stale_days,
                            min_list_days=req.min_list_days,
                            check_st=check_st,
                            min_avg_amount=req.min_avg_amount,
                            min_price=req.min_price,
                            fatal_types=req.fatal_types,
                        )

                    it = await loop.run_in_executor(io_executor, _do_one)
                    done += 1
                    if not (it and it.get("ok")):
                        bad += 1
                    yield _json_dumps({"type": "result", "data": it, "bad": bad, "progress": f"{done}/{total}"}) + "\n"
                    if done % 50 == 0:
                        await asyncio.sleep(0)

                yield _json_dumps({"type": "end", "total": total, "bad": bad}) + "\n"
            except Exception as e:
                yield _json_dumps({"type": "error", "message": str(e)}) + "\n"

        return StreamingResponse(result_generator(), media_type="application/x-ndjson")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/data/backup_pool")
async def api_data_backup_pool(out_dir: str = "", limit: int = 500):
    loop = asyncio.get_event_loop()
    od = await loop.run_in_executor(None, _resolve_out_dir, out_dir)
    items = _read_backup_pool(od)
    lim = max(1, min(int(limit) if limit is not None else 500, 5000))
    def _key(x: Any) -> str:
        v = x.get("updated_at") if isinstance(x, dict) else None
        return str(v or "")
    items.sort(key=_key, reverse=True)
    return items[:lim]

def _sched_log(line: str) -> None:
    try:
        logs = _data_sched_state.get("logs")
        if not isinstance(logs, list):
            logs = []
        logs.append(str(line))
        if len(logs) > 300:
            logs = logs[-300:]
        _data_sched_state["logs"] = logs
    except Exception:
        pass

async def _run_data_sync_batch(cfg: DataScheduleReq) -> dict[str, Any]:
    loop = asyncio.get_event_loop()
    out_dir = await loop.run_in_executor(None, _resolve_out_dir, cfg.out_dir)

    symbols: list[str] = []
    if cfg.full:
        all_syms = await loop.run_in_executor(io_executor, fetch_all_a_share_symbols)
        market = str(cfg.market or "").strip().upper()
        for it in (all_syms or []):
            s = it.get("symbol") if isinstance(it, dict) else None
            if not s:
                continue
            su = str(s).strip().upper()
            if market and not su.endswith("." + market):
                continue
            symbols.append(su)
    else:
        symbols = _normalize_symbols(cfg.symbols)

    total = len(symbols)
    if total <= 0:
        return {"total": 0, "ok": 0, "err": 0}

    max_conc = int(cfg.max_concurrency) if cfg.max_concurrency is not None else 8
    max_conc = max(1, min(max_conc, 64))
    sem = asyncio.Semaphore(max_conc)

    done = 0
    ok = 0
    err = 0
    last_errs: list[dict[str, Any]] = []

    async def _run(sym: str) -> dict[str, Any]:
        async with sem:
            return await _sync_one_symbol(loop, sym, out_dir, cfg)

    pending: set[asyncio.Task] = set()
    for s in symbols:
        pending.add(asyncio.create_task(_run(s)))

    while pending:
        done_set, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for t in done_set:
            done += 1
            _data_sched_state["progress_done"] = done
            _data_sched_state["progress_total"] = total
            _data_sched_state["progress_text"] = f"{done}/{total} ok={ok} err={err}"
            try:
                r = t.result()
                if isinstance(r, dict) and r.get("error"):
                    err += 1
                    last_errs.append(r)
                    _sched_log(f"[data] err {r.get('symbol')} {r.get('error')}")
                else:
                    ok += 1
                    _sched_log(f"[data] ok {r.get('symbol')} bars={r.get('bars')} last={r.get('last_date')}")
            except Exception as e:
                err += 1
                last_errs.append({"symbol": "-", "error": str(e)})
                _sched_log(f"[data] err - {e}")

        if done % 120 == 0:
            await asyncio.sleep(0)

    return {"total": total, "ok": ok, "err": err, "errors": last_errs[-50:], "out_dir": str(out_dir)}

async def _run_post_backtest(cfg: DataScheduleReq, out_dir: Path) -> dict[str, Any]:
    try:
        base_dir = out_dir
        if not base_dir.exists() or not base_dir.is_dir():
            return {"ok": False, "msg": "out_dir 不存在"}

        symbols: list[str] = []
        if cfg.symbols:
            symbols = _normalize_symbols(cfg.symbols)
        else:
            for p in base_dir.glob("*.csv"):
                symbols.append(p.stem)

        stage1_topk = max(1, min(int(cfg.post_backtest_stage1_topk or 200), 2000))
        symbols = symbols[:stage1_topk]
        if not symbols:
            return {"ok": False, "msg": "没有可回测的标的"}

        idx_path = None
        if cfg.post_backtest_index_symbol:
            idx_sym = str(cfg.post_backtest_index_symbol).strip()
            if idx_sym:
                guess = base_dir / f"{idx_sym}.csv"
                if guess.exists():
                    idx_path = guess

        cfg_bt = get_config_dict()
        if cfg.post_backtest_beg:
            cfg_bt["beg"] = cfg.post_backtest_beg
        if cfg.post_backtest_end:
            cfg_bt["end"] = cfg.post_backtest_end
        cfg_bt["calc_score"] = True
        cfg_bt["calc_robust"] = True
        cfg_bt["robust_segments"] = int(cfg.post_backtest_robust_segments or 4)
        cfg_bt["index_symbol"] = cfg.post_backtest_index_symbol

        loop = asyncio.get_event_loop()
        pool = executor if len(symbols) > 1 else None
        futs: list[asyncio.Future] = []
        for sym in symbols:
            p = base_dir / f"{sym}.csv"
            if not p.exists():
                continue
            futs.append(
                loop.run_in_executor(
                    pool,
                    backtest_channel_hf_for_symbol_path,
                    sym,
                    p,
                    idx_path,
                    cfg_bt,
                )
            )

        results: list[dict[str, Any]] = []
        for r in await asyncio.gather(*futs, return_exceptions=True):
            if isinstance(r, Exception):
                continue
            if isinstance(r, dict) and r.get("error"):
                continue
            if isinstance(r, dict):
                results.append(r)

        def _num(x: Any) -> float:
            try:
                v = float(x)
                return v if math.isfinite(v) else float("-inf")
            except Exception:
                return float("-inf")

        results.sort(key=lambda x: (_num(x.get("score_robust")), _num(x.get("score"))), reverse=True)
        topn = max(1, min(int(cfg.post_backtest_topn or 20), 500))
        now = datetime.datetime.now().isoformat(timespec="seconds")
        items = []
        for it in results[:topn]:
            sym = it.get("symbol")
            if not sym:
                continue
            items.append(
                {
                    "symbol": sym,
                    "score": it.get("score"),
                    "score_robust": it.get("score_robust"),
                    "trades": it.get("trades"),
                    "updated_at": now,
                }
            )
        _write_backup_pool(out_dir, items)
        return {"ok": True, "topn": len(items)}
    except Exception as e:
        return {"ok": False, "msg": str(e)}

async def _data_schedule_loop(cfg: DataScheduleReq):
    async with _data_sched_lock:
        _data_sched_state["running"] = True
        _data_sched_state["interval_min"] = int(cfg.interval_min)
        _data_sched_state["cfg"] = cfg.dict()
        _data_sched_state["phase"] = "running"
        _data_sched_state["progress_text"] = None
        _data_sched_state["progress_done"] = 0
        _data_sched_state["progress_total"] = 0
        _data_sched_state["last_error"] = None

    while True:
        if _data_sched_stop and _data_sched_stop.is_set():
            break
        try:
            async with _data_sched_lock:
                _data_sched_state["phase"] = "sync"
                _data_sched_state["progress_done"] = 0
                _data_sched_state["progress_total"] = 0
                _data_sched_state["progress_text"] = "starting"
            s = await _run_data_sync_batch(cfg)
            async with _data_sched_lock:
                _data_sched_state["last_run_at"] = datetime.datetime.now().isoformat(timespec="seconds")
                _data_sched_state["last_summary"] = s
                _data_sched_state["phase"] = "idle"
                _data_sched_state["progress_text"] = None
                _data_sched_state["last_error"] = None

            if cfg.post_backtest:
                async with _data_sched_lock:
                    _data_sched_state["phase"] = "post_backtest"
                    _data_sched_state["progress_text"] = "running"
                out_dir = _resolve_out_dir(cfg.out_dir)
                bt = await _run_post_backtest(cfg, out_dir)
                async with _data_sched_lock:
                    _data_sched_state["last_backtest_at"] = datetime.datetime.now().isoformat(timespec="seconds")
                    _data_sched_state["last_backtest"] = bt
                    _data_sched_state["phase"] = "idle"
                    _data_sched_state["progress_text"] = None

        except Exception as e:
            async with _data_sched_lock:
                _data_sched_state["last_error"] = str(e)
                _data_sched_state["phase"] = "error"
                _data_sched_state["progress_text"] = None

        interval_min = int(cfg.interval_min) if cfg.interval_min is not None else 60
        interval_min = max(1, min(interval_min, 24 * 60))
        for _ in range(interval_min * 30):
            if _data_sched_stop and _data_sched_stop.is_set():
                break
            await asyncio.sleep(2)

    async with _data_sched_lock:
        _data_sched_state["running"] = False
        _data_sched_state["phase"] = None
        _data_sched_state["progress_text"] = None

@app.post("/api/data/schedule_start")
async def api_data_schedule_start(req: DataScheduleReq):
    global _data_sched_task, _data_sched_stop
    async with _data_sched_lock:
        if _data_sched_task and not _data_sched_task.done():
            return {"ok": True, "state": _data_sched_state}

        _data_sched_stop = asyncio.Event()
        _data_sched_task = asyncio.create_task(_data_schedule_loop(req))
        return {"ok": True, "state": _data_sched_state}

@app.post("/api/data/schedule_stop")
async def api_data_schedule_stop():
    global _data_sched_task, _data_sched_stop
    async with _data_sched_lock:
        if _data_sched_stop:
            _data_sched_stop.set()
        t = _data_sched_task

    if t:
        try:
            await asyncio.wait_for(t, timeout=5.0)
        except Exception:
            try:
                t.cancel()
            except Exception:
                pass
    return {"ok": True}

@app.get("/api/data/schedule_status")
async def api_data_schedule_status():
    async with _data_sched_lock:
        return dict(_data_sched_state)


class AnalyzeReq(BaseModel):
    symbol: str
    data_dir: str
    index_data: str | None = None
    index_symbol: str | None = "000300.SH"
    beg: str | None = None
    end: str | None = None
    config: dict[str, Any]

@app.post("/api/debug/analyze")
async def api_debug_analyze(req: AnalyzeReq):
    try:
        loop = asyncio.get_event_loop()

        # Resolve the directory path first
        base_dir = await loop.run_in_executor(None, resolve_any_path, req.data_dir)
        if not base_dir or not base_dir.is_dir():
            raise HTTPException(status_code=400, detail=f"Invalid data directory: {req.data_dir}")

        # Pick concrete data file path
        target_file = None
        for ext in [".csv", ".txt"]:
            p = base_dir / f"{req.symbol}{ext}"
            if p.exists():
                target_file = p
                break
        if not target_file:
            candidates = list(base_dir.glob(f"{req.symbol}.*"))
            if candidates:
                target_file = candidates[0]
        if not target_file:
            raise HTTPException(status_code=400, detail=f"Data file for {req.symbol} not found in {base_dir}")
        
        idx_path = None
        if req.index_data:
            idx_path = await loop.run_in_executor(None, resolve_file_path, req.index_data)
        
        res = await loop.run_in_executor(
            executor,
            debug_analyze_channel_hf,
            req.symbol,
            target_file,
            idx_path,
            {**req.config, "beg": req.beg, "end": req.end, "index_symbol": req.index_symbol}
        )
        try:
            await _persist_trade_features_from_debug_result(res if isinstance(res, dict) else {})
        except Exception:
            pass
        return res
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

class TradeFeatureListResp(BaseModel):
    items: list[dict[str, Any]]

@app.get("/api/trade_features/list")
async def api_trade_features_list(symbol: str | None = None, beg: str | None = None, end: str | None = None):
    sym = (symbol or "").strip().upper()
    beg_dt = _parse_date_any(beg)
    end_dt = _parse_date_any(end)
    async with _trade_feature_lock:
        items = _load_trade_feature_store()
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        if sym:
            sc = str(it.get("stock_code") or "").strip().upper()
            if sc and sc != sym and sc.split(".")[0] != sym.split(".")[0]:
                continue
        d0 = _parse_date_any(str(it.get("entry_dt") or it.get("entry_date") or ""))
        if beg_dt is not None and (d0 is None or d0 < beg_dt):
            continue
        if end_dt is not None and (d0 is None or d0 > end_dt):
            continue
        out.append(it)
    return {"items": out}

@app.get("/api/trade_features/get")
async def api_trade_features_get(transaction_id: str):
    tid = str(transaction_id or "").strip()
    if not tid:
        raise HTTPException(status_code=400, detail="transaction_id 不能为空")
    async with _trade_feature_lock:
        items = _load_trade_feature_store()
    for it in items:
        if not isinstance(it, dict):
            continue
        if str(it.get("transaction_id") or "").strip() == tid:
            return {"item": it}
    raise HTTPException(status_code=404, detail="未找到对应交易记录")

def _csv_escape(x: Any) -> str:
    s = "" if x is None else str(x)
    if any(ch in s for ch in [",", "\"", "\n", "\r"]):
        return "\"" + s.replace("\"", "\"\"") + "\""
    return s

def _fmt_pct_ratio(x: Any, digits: int = 2) -> str:
    try:
        v = float(x)
    except Exception:
        return ""
    if not math.isfinite(v):
        return ""
    return f"{v * 100:.{int(digits)}f}%"

def _fmt_num(x: Any, digits: int) -> str:
    try:
        v = float(x)
    except Exception:
        return ""
    if not math.isfinite(v):
        return ""
    return f"{v:.{int(digits)}f}"

@app.get("/api/trade_features/export_csv")
async def api_trade_features_export_csv(
    symbol: str | None = None,
    beg: str | None = None,
    end: str | None = None,
    transaction_ids: str | None = None,
):
    sym = (symbol or "").strip().upper()
    beg_dt = _parse_date_any(beg)
    end_dt = _parse_date_any(end)
    wanted = None
    if transaction_ids:
        parts = [p.strip() for p in str(transaction_ids).split(",")]
        tids = [p for p in parts if p]
        wanted = set(tids) if tids else None
    async with _trade_feature_lock:
        items = _load_trade_feature_store()
    filtered = []
    for it in items:
        if not isinstance(it, dict):
            continue
        if wanted is not None:
            tid = str(it.get("transaction_id") or "").strip()
            if tid not in wanted:
                continue
        if sym:
            sc = str(it.get("stock_code") or "").strip().upper()
            if sc and sc != sym and sc.split(".")[0] != sym.split(".")[0]:
                continue
        d0 = _parse_date_any(str(it.get("entry_dt") or it.get("entry_date") or ""))
        if beg_dt is not None and (d0 is None or d0 < beg_dt):
            continue
        if end_dt is not None and (d0 is None or d0 > end_dt):
            continue
        filtered.append(it)

    if filtered:
        ds = [_parse_date_any(str(x.get("entry_dt") or x.get("entry_date") or "")) for x in filtered]
        ds2 = [d for d in ds if d is not None]
        if beg_dt is None and ds2:
            beg_dt = min(ds2)
        if end_dt is None and ds2:
            end_dt = max(ds2)

    beg_s = beg_dt.strftime("%Y%m%d") if beg_dt else "00000000"
    end_s = end_dt.strftime("%Y%m%d") if end_dt else "99999999"
    export_s = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    code_s = sym.split(".")[0] if sym else "ALL"
    filename = f"交易特征_{code_s}_{beg_s}_{end_s}_{export_s}.csv"

    params_set = set()
    for it in filtered:
        ps = it.get("params_snapshot")
        try:
            params_set.add(json.dumps(ps, ensure_ascii=False, sort_keys=True))
        except Exception:
            params_set.add("")
    params_head = ""
    if len(params_set) == 1:
        try:
            params_head = next(iter(params_set))
        except Exception:
            params_head = ""
    else:
        params_head = _json_dumps({"mixed": True})

    headers = [
        "交易ID","入场日期","出场日期","股票代码","收益率","持仓天数","出场原因",
        "短期波动率%","长期波动率%","波动率比率","波动率阈值","波动率通过",
        "收盘价","MA20值","买入容差","趋势通过",
        "量能收缩率","量能下限","量能上限","量能通过",
        "通道斜率","斜率下限","斜率通过",
        "通道高度%","高度阈值%","高度通过",
        "中轨空间%","空间阈值%","空间通过",
        "冷却通过","企稳天数","企稳通过",
        "预估盈利%","盈利阈值%","盈利通过",
        "预估风险收益比","收益比阈值","收益比通过",
    ]

    def _iter_lines():
        yield "\ufeff"
        yield f"# 导出时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        yield f"# 策略版本：channel_hf\n"
        yield f"# 参数快照：{params_head}\n"
        yield f"# 总交易数：{len(filtered)}\n"
        if beg_dt and end_dt:
            yield f"# 时间范围：{beg_dt.isoformat()}至{end_dt.isoformat()}\n"
        yield "\n"
        yield ",".join([_csv_escape(h) for h in headers]) + "\n"
        for it in filtered:
            fs = it.get("feature_snapshot") if isinstance(it.get("feature_snapshot"), dict) else None
            if not fs:
                continue
            row = [
                fs.get("transaction_id"),
                it.get("entry_dt") or fs.get("entry_date"),
                it.get("exit_dt") or fs.get("exit_date"),
                fs.get("stock_code"),
                _fmt_pct_ratio(fs.get("return_rate"), 2),
                fs.get("holding_days"),
                fs.get("exit_reason"),
                _fmt_pct_ratio(fs.get("vol_short"), 2),
                _fmt_pct_ratio(fs.get("vol_long"), 2),
                _fmt_num(fs.get("vol_ratio"), 3),
                _fmt_num(fs.get("vol_threshold"), 3),
                "1" if fs.get("vol_pass") is True else ("0" if fs.get("vol_pass") is False else ""),
                _fmt_num(fs.get("price"), 2),
                _fmt_num(fs.get("ma20"), 2),
                _fmt_num(fs.get("buy_touch_eps"), 3),
                "1" if fs.get("trend_pass") is True else ("0" if fs.get("trend_pass") is False else ""),
                _fmt_num(fs.get("volume_ratio"), 3),
                _fmt_num(fs.get("vol_shrink_min"), 3),
                _fmt_num(fs.get("vol_shrink_max"), 3),
                "1" if fs.get("volume_pass") is True else ("0" if fs.get("volume_pass") is False else ""),
                _fmt_num(fs.get("slope_value"), 4),
                _fmt_num(fs.get("slope_min"), 4),
                "1" if fs.get("slope_pass") is True else ("0" if fs.get("slope_pass") is False else ""),
                _fmt_pct_ratio(fs.get("height_value"), 2),
                _fmt_pct_ratio(fs.get("height_min"), 2),
                "1" if fs.get("height_pass") is True else ("0" if fs.get("height_pass") is False else ""),
                _fmt_pct_ratio(fs.get("room_value"), 2),
                _fmt_pct_ratio(fs.get("room_min"), 2),
                "1" if fs.get("room_pass") is True else ("0" if fs.get("room_pass") is False else ""),
                "1" if fs.get("cooling_pass") is True else ("0" if fs.get("cooling_pass") is False else ""),
                fs.get("pivot_confirm_days"),
                "1" if fs.get("pivot_pass") is True else ("0" if fs.get("pivot_pass") is False else ""),
                _fmt_pct_ratio(fs.get("min_profit_value"), 2),
                _fmt_pct_ratio(fs.get("min_profit_threshold"), 2),
                "1" if fs.get("profit_pass") is True else ("0" if fs.get("profit_pass") is False else ""),
                _fmt_num(fs.get("min_rr_value"), 2),
                _fmt_num(fs.get("min_rr_threshold"), 2),
                "1" if fs.get("rr_pass") is True else ("0" if fs.get("rr_pass") is False else ""),
            ]
            yield ",".join([_csv_escape(x) for x in row]) + "\n"

    resp = StreamingResponse(_iter_lines(), media_type="text/csv; charset=utf-8")
    resp.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"
    return resp

class TradeFeaturesReanalyzeReq(BaseModel):
    symbol: str
    data_dir: str
    index_data: str | None = None
    index_symbol: str | None = "000300.SH"
    config: dict[str, Any]
    transaction_ids: list[str]

@app.post("/api/trade_features/reanalyze")
async def api_trade_features_reanalyze(req: TradeFeaturesReanalyzeReq):
    loop = asyncio.get_event_loop()
    sym = str(req.symbol or "").strip()
    if not sym:
        raise HTTPException(status_code=400, detail="symbol 不能为空")
    tids = [str(x).strip() for x in (req.transaction_ids or []) if str(x).strip()]
    if not tids:
        raise HTTPException(status_code=400, detail="transaction_ids 不能为空")

    base_dir = await loop.run_in_executor(None, resolve_any_path, req.data_dir)
    if not base_dir or not base_dir.is_dir():
        raise HTTPException(status_code=400, detail=f"Invalid data directory: {req.data_dir}")
    target_file = None
    for ext in [".csv", ".txt"]:
        p = base_dir / f"{sym}{ext}"
        if p.exists():
            target_file = p
            break
    if not target_file:
        candidates = list(base_dir.glob(f"{sym}.*"))
        if candidates:
            target_file = candidates[0]
    if not target_file:
        raise HTTPException(status_code=400, detail=f"Data file for {sym} not found in {base_dir}")

    idx_path = None
    if req.index_data:
        idx_path = await loop.run_in_executor(None, resolve_file_path, req.index_data)

    async with _trade_feature_lock:
        items = _load_trade_feature_store()
    wanted = set(tids)
    targets = []
    for it in items:
        if not isinstance(it, dict):
            continue
        tid = str(it.get("transaction_id") or "").strip()
        if tid not in wanted:
            continue
        fs0 = it.get("feature_snapshot_original") if isinstance(it.get("feature_snapshot_original"), dict) else None
        fs = it.get("feature_snapshot") if isinstance(it.get("feature_snapshot"), dict) else None
        src = fs0 or fs or {}
        targets.append({
            "entry_dt": it.get("entry_dt") or src.get("entry_date"),
            "exit_dt": it.get("exit_dt") or src.get("exit_date"),
            "qty": src.get("qty") or it.get("qty") or 0,
            "entry_price": src.get("entry_price") or 0.0,
            "exit_price": src.get("exit_price") or 0.0,
            "holding_days": src.get("holding_days") or 0,
            "exit_reason": src.get("exit_reason") or "",
            "return_rate": src.get("return_rate") or 0.0,
        })

    if not targets:
        raise HTTPException(status_code=400, detail="未找到对应交易记录")

    cfg = dict(req.config or {})
    cfg["index_symbol"] = req.index_symbol

    res = await loop.run_in_executor(
        executor,
        reanalyze_channel_hf_trade_features,
        sym,
        target_file,
        idx_path,
        cfg,
        targets,
    )
    if not isinstance(res, dict) or str(res.get("status") or "") != "success":
        raise HTTPException(status_code=400, detail=str(res.get("message") if isinstance(res, dict) else "重新分析失败"))

    items2 = res.get("items") if isinstance(res.get("items"), list) else []
    snaps = []
    for x in items2:
        if isinstance(x, dict) and isinstance(x.get("feature_snapshot"), dict):
            snaps.append(x["feature_snapshot"])

    now_iso = datetime.datetime.now().isoformat(timespec="seconds")
    params_snapshot = cfg
    async with _trade_feature_lock:
        existing = _load_trade_feature_store()
        merged = _upsert_trade_feature_records(existing=existing, new_snapshots=snaps, params_snapshot=params_snapshot, now_iso=now_iso)
        for r in merged:
            if isinstance(r, dict) and str(r.get("transaction_id") or "") in wanted:
                r["reanalyzed_at"] = now_iso
        _save_trade_feature_store(merged)

    return {"ok": True, "count": len(snaps)}

def _list_smart_data_files() -> list[str]:
    roots = [
        app_dir / "test",
        app_dir / "analyze",
        app_dir / "exports",
    ]
    exts = {".csv", ".xls", ".xlsx"}

    out: list[tuple[float, str]] = []
    seen: set[str] = set()

    for r in roots:
        if not r.exists() or not r.is_dir():
            continue
        for p in r.rglob("*"):
            try:
                if not p.is_file():
                    continue
                if p.suffix.lower() not in exts:
                    continue
                if p.name.startswith("~$"):
                    continue
                sp = str(p.resolve())
                if sp in seen:
                    continue
                seen.add(sp)
                try:
                    mt = p.stat().st_mtime
                except Exception:
                    mt = 0.0
                out.append((float(mt), sp))
            except Exception:
                continue

    out.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in out[:500]]

@app.get("/api/list_data_files")
async def api_list_data_files():
    return _list_smart_data_files()

@app.post("/api/smart_analyze")
async def api_smart_analyze(req: SmartAnalyzeReq):
    loop = asyncio.get_event_loop()
    try:
        p = await loop.run_in_executor(None, resolve_any_path, req.file_path)
        if not p or not p.exists() or not p.is_file():
            raise HTTPException(status_code=400, detail=f"文件不存在: {req.file_path}")

        ext = p.suffix.lower()
        if ext not in {".csv", ".xls", ".xlsx"}:
            raise HTTPException(status_code=400, detail="文件格式不支持，仅支持 .csv / .xls / .xlsx")

        api_key = (os.environ.get("DASHSCOPE_API_KEY") or "").strip() or (DASHSCOPE_API_KEY or "").strip()
        if not api_key:
            raise HTTPException(status_code=400, detail="未配置 DASHSCOPE_API_KEY，无法进行智能问数分析")

        def _do() -> dict[str, Any]:
            analyzer = SmartAnalyzer(api_key)
            return analyzer.analyze(str(p), str(req.query or "").strip())

        res = await loop.run_in_executor(io_executor, _do)
        if isinstance(res, dict) and res.get("error"):
            detail = str(res.get("error") or "分析失败")
            extra = []
            if res.get("detail"):
                extra.append(str(res.get("detail")))
            if res.get("hint"):
                extra.append(str(res.get("hint")))
            if extra:
                detail = detail + "；" + "；".join(extra)
            raise HTTPException(
                status_code=400,
                detail=detail + "。格式要求：CSV/Excel，CSV 建议 UTF-8/UTF-8-SIG 或 GBK 编码，分隔符支持逗号/制表符/分号。",
            )

        return res
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn, os
    host = os.environ.get("CHHF_HOST", "127.0.0.1")
    try:
        port = int(os.environ.get("CHHF_PORT", "18002"))
    except Exception:
        port = 18002
    uvicorn.run(app, host=host, port=port)
