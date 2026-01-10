import sys
import os
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

if __name__ == "__main__":
    test_batch_param_api()
