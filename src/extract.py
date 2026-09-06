import json
from pathlib import Path
import requests

#retrieve the data from the API and store it in a local file for later processing
BASE_URL = "https://api.openligadb.de"
LEAGUE = "pl"
SEASON = 2026

# Paths are resolved from this file, not the working directory,
# so the ETL can be run from anywhere
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
STATE_FILE = RAW_DIR / "matchweek_state.json"


# Call an OpenLigaDB endpoint and return the parsed JSON
def _get(endpoint):
    return requests.get(f"{BASE_URL}/{endpoint}").json()


# Write data to disk as UTF-8 JSON
def _write_json(path, data):
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


# Load the matchweek ledger, or an empty one on the first run
def _read_state():
    if not STATE_FILE.exists():
        return {}

    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


# Fetch every matchweek up to the live one, skipping those already
# sealed as complete, and return only the matches actually fetched
def extract():
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    # Get the current matchweek from the API
    current_matchweek = _get(f"getcurrentgroup/{LEAGUE}")["groupOrderID"]

    print(f"\nCurrent matchweek: {current_matchweek}")

    state = _read_state()
    all_matches = []

    # Loop through every matchweek, skipping those already marked as complete
    for matchweek in range(1, current_matchweek + 1):

        # Check if this matchweek is already marked as complete in the state file
        key = str(matchweek)
        is_complete = state.get(key, {}).get("complete", False)

        # A finished matchweek cannot change, but the live one still can
        if is_complete and matchweek != current_matchweek:
            print(f"MW {matchweek}: complete -> skipped")
            continue

        print(f"MW {matchweek}: fetching...")

        # Fetch the matches for this matchweek and write them to disk
        matches = _get(f"getmatchdata/{LEAGUE}/{SEASON}/{matchweek}")
        _write_json(RAW_DIR / f"matchweek_{matchweek}.json", matches)
        all_matches.extend(matches)

        # Determine if all matches in this matchweek are finished, and update the state
        complete = all(match["matchIsFinished"] for match in matches)
        state[key] = {"complete": complete}

        print(f"MW {matchweek}: {len(matches)} matches, complete = {complete}")

    # Write the updated state back to disk
    _write_json(STATE_FILE, state)

    print(f"\nTotal matches returned: {len(all_matches)}")

    return all_matches
