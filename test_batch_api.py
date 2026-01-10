import sys
import os
import asyncio
from pathlib import Path
from fastapi.testclient import TestClient

# Add parent directory to path to import app
sys.path.append(str(Path(__file__).parent))

from app import app

client = TestClient(app)

def test_batch_param_api():
    # Setup request payload
    # We need a valid data_dir. I see 'data' folder in the LS output.
    data_dir = str(Path(__file__).parent / "data")
    
    payload = {
        "data_dir": data_dir,
        "symbols": ["000001.SZ"], # Use a symbol that likely exists
        "param_sets": [
            {"vol_shrink_min": 0.5, "vol_shrink_max": 2.0, "__name__": "Loose Params"},
            {"vol_shrink_min": 1.0, "vol_shrink_max": 1.0, "__name__": "Strict Params"}
        ],
        "beg": "20230101",
        "end": "20230201"
    }

    print(f"Testing with payload: {payload}")

    try:
        response = client.post("/api/param_batch_test", json=payload)
        
        print(f"Response status: {response.status_code}")
        if response.status_code != 200:
            print(f"Error: {response.text}")
            return

        print("Response content:")
        for line in response.iter_lines():
            if line:
                print(line)
                
    except Exception as e:
        print(f"Exception: {e}")

def test_batch_aggregation_combo_top():
    from core.scanner_runner import BatchAggregation

    agg = BatchAggregation()
    agg.update_from_result({"symbol": "A", "total_return": 0.10, "win_rate": 0.6, "__combo_label__": "C1", "__combo__": {"p": 1}})
    agg.update_from_result({"symbol": "B", "total_return": 0.20, "win_rate": 0.7, "__combo_label__": "C1", "__combo__": {"p": 1}})
    agg.update_from_result({"symbol": "C", "total_return": -0.05, "win_rate": 0.4, "__combo_label__": "C2", "__combo__": {"p": 2}})
    d = agg.to_dict()

    assert d["combo_top"][0]["combo_label"] == "C1"
    assert d["combo_top"][0]["samples"] == 2
    assert abs(d["combo_top"][0]["avg_return"] - 0.15) < 1e-6

def test_batch_task_status_includes_grid_metadata():
    from core.scanner_runner import BatchTaskManager

    m = BatchTaskManager(max_tasks=2, ttl_seconds=3600)
    st = m.create_task(total=10, grid_metadata={"combos": 3, "symbols": 2, "param_keys": ["a"]})
    s = m.get_status(st.task_id)
    assert s["grid_metadata"]["combos"] == 3
    assert "progress" in s


def test_performance_endpoints():
    from config.database import init_db, get_db
    from data.storage.repository import ParamPerformanceRepository

    init_db()
    strategy = "test_strategy_perf_api"
    payload = {
        "strategy_name": strategy,
        "param_combo": {"ma_period": 20, "rsi_period": 14, "stop_loss": 0.02},
        "metrics": {"total_return": 0.15, "max_drawdown": 0.05},
        "sample_size": 100,
        "sharpe_ratio": 1.2,
        "win_rate": 0.65,
        "max_drawdown": 0.05,
        "stability_score": 0.0,
    }
    with get_db() as db:
        ParamPerformanceRepository.save(db, payload)

    r_best = client.get(f"/api/performance/best/{strategy}", params={"limit": 5})
    assert r_best.status_code == 200
    j_best = r_best.json()
    assert j_best["strategy"] == strategy
    assert j_best["count"] >= 1
    assert isinstance(j_best["results"], list) and j_best["results"]
    assert "param_combo" in j_best["results"][0]

    r_hist = client.get(f"/api/performance/history/{strategy}", params={"days": 365, "limit": 5})
    assert r_hist.status_code == 200
    j_hist = r_hist.json()
    assert j_hist["strategy"] == strategy
    assert j_hist["count"] >= 1

    r_stats = client.get(f"/api/performance/stats/{strategy}")
    assert r_stats.status_code == 200
    j_stats = r_stats.json()
    assert j_stats["strategy"] == strategy
    assert j_stats["total_tests"] >= 1


def test_random_optimizer_baseline():
    from core.optimization.random_optimizer import RandomOptimizer

    opt = RandomOptimizer(
        strategy_name="channel_hf",
        param_space={
            "window": {"min": 10, "max": 30, "type": "int"},
            "threshold": {"min": 0.1, "max": 0.3},
            "mode": ["A", "B", "C"],
            "side": {"choices": ["long", "short"]},
        },
    )

    res = asyncio.run(opt.optimize(n_iterations=25, objective="sharpe_ratio"))
    assert res.success is True
    assert isinstance(res.best_params, dict)
    assert isinstance(res.best_score, float)
    assert res.iterations == 25
    assert isinstance(res.history, list) and len(res.history) == 25
    assert res.metadata.get("optimizer") == "random"


def test_optimizer_manager_persists_history():
    from config.database import init_db, get_db
    from core.optimization.optimizer_manager import OptimizerManager
    from data.storage.models import OptimizationHistory

    init_db()
    strategy_name = "test_strategy_opt_mgr"

    async def _run():
        manager = OptimizerManager()
        return await manager.run_optimization(
            optimizer_type="random",
            strategy_name=strategy_name,
            param_space={
                "ma_period": {"min": 5, "max": 60, "type": "int"},
                "rsi_period": {"min": 7, "max": 21, "type": "int"},
                "stop_loss": {"min": 0.01, "max": 0.05},
                "take_profit": {"min": 0.02, "max": 0.08},
            },
            n_iterations=10,
        )

    out = asyncio.run(_run())
    assert out["success"] is True
    assert out["optimizer_type"] == "random"
    assert out["strategy_name"] == strategy_name

    with get_db() as db:
        row = (
            db.query(OptimizationHistory)
            .filter(
                OptimizationHistory.strategy_name == strategy_name,
                OptimizationHistory.optimization_type == "random",
            )
            .order_by(OptimizationHistory.optimization_date.desc())
            .first()
        )
        assert row is not None
        assert isinstance(row.optimized_params, dict)

if __name__ == "__main__":
    test_batch_param_api()
