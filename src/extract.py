import json
import time
from pathlib import Path
import requests

#retrieve the data from the API and store it in a local file for later processing
BASE_URL = "https://api.openligadb.de"
LEAGUE = "pl"
SEASON = 2026

# Give up on a request after 10 seconds instead of waiting forever,
# and allow one retry in case the failure was a brief network blip
TIMEOUT = 10
RETRY_DELAY = 2

# Paths are resolved from this file, not the working directory,
# so the ETL can be run from anywhere
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
STATE_FILE = RAW_DIR / "matchweek_state.json"


# Call an OpenLigaDB endpoint and return the parsed JSON.
# raise_for_status() turns an error response (404, 500, 503) into an
# exception, so an error page is never parsed as if it were match data
def _get(endpoint):
    url = f"{BASE_URL}/{endpoint}"

    try:
        response = requests.get(url, timeout=TIMEOUT)
        response.raise_for_status()

    # Try once more before giving up; if the second attempt also fails,
    # the exception is raised and the ETL stops
    except requests.RequestException as error:
        print(f"Request failed ({error}), retrying in {RETRY_DELAY}s...")
        time.sleep(RETRY_DELAY)

        response = requests.get(url, timeout=TIMEOUT)
        response.raise_for_status()

    return response.json()


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

        # Save the state after each matchweek, so that if a later matchweek
        # fails the progress made so far is not lost on the next run
        _write_json(STATE_FILE, state)

        print(f"MW {matchweek}: {len(matches)} matches, complete = {complete}")

    print(f"\nTotal matches returned: {len(all_matches)}")

    return all_matches
