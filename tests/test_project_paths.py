import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src import extract, load


def test_paths_are_project_root_relative():
    assert extract.STATE_FILE == project_root / "data" / "raw" / "matchweek_state.json"
    assert load.OUTPUT_FILE == project_root / "data" / "processed" / "matches.csv"
