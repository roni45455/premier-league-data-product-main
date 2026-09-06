from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_FILE = PROJECT_ROOT / "data" / "processed" / "matches.csv"

# match_id is no longer stored, so a match is identified by the fixture
# itself: a pairing occurs once per matchweek
NATURAL_KEY = ["matchweek", "home_team", "away_team"]
DATE_FORMAT = "%d-%m-%Y"


def load(new_matches):
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    new_data = pd.DataFrame(new_matches)

    if OUTPUT_FILE.exists():
        existing_data = pd.read_csv(OUTPUT_FILE)

        combined = pd.concat(
            [existing_data, new_data],
            ignore_index=True
        )

        # A later revision of the same fixture replaces the earlier one
        combined = (
            combined
            .sort_values("last_update")
            .drop_duplicates(
                subset=NATURAL_KEY,
                keep="last"
            )
        )

    else:
        combined = new_data

    # match_date is DD-MM-YYYY, which does not sort chronologically as text
    kickoff = pd.to_datetime(
        combined["match_date"] + " " + combined["kickoff_time"],
        format=f"{DATE_FORMAT} %H:%M",
        errors="coerce"
    )

    combined = (
        combined
        .assign(_kickoff=kickoff)
        .sort_values(["matchweek", "_kickoff"])
        .drop(columns="_kickoff")
        .reset_index(drop=True)
    )

    combined.to_csv(
        OUTPUT_FILE,
        index=False
    )

    print(f"Saved {len(combined)} matches to {OUTPUT_FILE}")

    return combined
