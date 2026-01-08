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

if __name__ == "__main__":
    test_batch_param_api()
