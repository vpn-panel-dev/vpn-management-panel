import sys
from pathlib import Path

# Ensure the panel directory is on the Python path so "app" imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
