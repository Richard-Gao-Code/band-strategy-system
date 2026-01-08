import sys
import json
import shutil
from pathlib import Path

# Use the unified config path from core/analyzer
try:
    from core.analyzer import get_config_dict, save_config_dict
    CONFIG_PATH = Path(__file__).parent / "config.json"
except ImportError:
    # Fallback if core not found (though it should be)
    CONFIG_PATH = Path(__file__).parent / "config.json"
    
    def get_config_dict():
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
        
    def save_config_dict(data):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True

PRESETS_DIR = Path(__file__).parent / "presets"

def ensure_presets_dir():
    if not PRESETS_DIR.exists():
        PRESETS_DIR.mkdir()

def list_presets():
    ensure_presets_dir()
    files = list(PRESETS_DIR.glob("*.json"))
    if not files:
        print("No presets found.")
        return
    print("\nAvailable Presets:")
    for f in files:
        print(f"  - {f.stem}")
    print("")

def save_preset(name):
    ensure_presets_dir()
    current_config = get_config_dict()
    if not current_config:
        print("Error: Current config.json is empty or missing.")
        return
    
    target_path = PRESETS_DIR / f"{name}.json"
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(current_config, f, ensure_ascii=False, indent=4)
    print(f"✅ Saved current configuration as preset '{name}'")

def load_preset(name):
    ensure_presets_dir()
    source_path = PRESETS_DIR / f"{name}.json"
    if not source_path.exists():
        print(f"Error: Preset '{name}' not found.")
        return
    
    with open(source_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    if save_config_dict(data):
        print(f"✅ Loaded preset '{name}' into config.json")
    else:
        print("Error: Failed to write to config.json")

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python manage_presets.py list")
        print("  python manage_presets.py save <name>")
        print("  python manage_presets.py load <name>")
        return

    action = sys.argv[1].lower()
    
    if action == "list":
        list_presets()
    elif action == "save":
        if len(sys.argv) < 3:
            print("Error: Missing preset name.")
            return
        save_preset(sys.argv[2])
    elif action == "load":
        if len(sys.argv) < 3:
            print("Error: Missing preset name.")
            return
        load_preset(sys.argv[2])
    else:
        print(f"Unknown command: {action}")

if __name__ == "__main__":
    main()