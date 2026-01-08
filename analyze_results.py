import sys
from pathlib import Path

# Ensure the current directory is in sys.path to allow importing from core
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

from core.selector import run_interactive

if __name__ == "__main__":
    run_interactive()

