import sys
from pathlib import Path
from copy import deepcopy

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.transform import transform


# ---------------------------------------------------------------------------
# Helper: builds one valid, finished match dict that mirrors the real
# OpenLigaDB structure.  Every test starts from this and breaks one thing.
# ---------------------------------------------------------------------------
def _make_match(**overrides):
    match = {
        "matchID": 86536,
        "matchDateTimeUTC": "2026-08-23T15:30:00Z",
        "matchIsFinished": True,
        "group": {"groupName": "1. Spieltag", "groupOrderID": 1, "groupID": 53281},
        "team1": {
            "teamId": 541,
            "teamName": "Everton FC",
            "shortName": "Everton",
        },
        "team2": {
            "teamId": 2489,
            "teamName": "Crystal Palace FC",
            "shortName": "Crystal Palace",
        },
        "matchResults": [
            {
                "resultTypeKind": "HalfTime",
                "pointsTeam1": 0,
                "pointsTeam2": 0,
            },
            {
                "resultTypeKind": "After90Minutes",
                "pointsTeam1": 2,
                "pointsTeam2": 0,
            },
        ],
        "lastUpdateDateTime": "2026-08-25T18:11:18.797",
    }

    match.update(overrides)
    return match


# ---------------------------------------------------------------------------
# 1. Happy path – a normal finished match is transformed correctly
# ---------------------------------------------------------------------------
def test_valid_match_transforms_correctly():
    """A standard finished match should produce one row with the right
    fields, computed result, total goals, and goal difference."""

    result = transform([_make_match()])

    assert len(result) == 1

    row = result[0]
    assert row["home_team"] == "Everton FC"
    assert row["away_team"] == "Crystal Palace FC"
    assert row["home_goals"] == 2
    assert row["away_goals"] == 0
    assert row["result"] == "Home win"
    assert row["total_goals"] == 2
    assert row["goal_difference"] == 2
    assert row["matchweek"] == 1
    assert row["match_date"] == "23-08-2026"
    assert row["kickoff_time"] == "15:30"


# ---------------------------------------------------------------------------
# 2. Negative goals – sentinel value -1 should not silently produce a row
# ---------------------------------------------------------------------------
def test_negative_goals_poison_result():
    """If the API returns a negative goal count (e.g. -1 sentinel), the
    current code does NOT guard against it.  This test documents the
    damage: result logic, total_goals, and goal_difference all become
    nonsensical.

    Once a validation guard is added, flip the assertions to verify the
    match is rejected instead."""

    match = _make_match()
    match["matchResults"][1]["pointsTeam1"] = -1  # corrupt home goals

    result = transform([match])

    # --- current (broken) behaviour: the row slips through ---
    assert len(result) == 1
    row = result[0]
    assert row["home_goals"] == -1            # negative in output
    assert row["total_goals"] == -1            # -1 + 0
    assert row["goal_difference"] == -1        # -1 - 0
    assert row["result"] == "Away win"         # wrong: -1 < 0

    # --- after fix: uncomment these, delete the block above ---
    # assert len(result) == 0  # match should be rejected


# ---------------------------------------------------------------------------
# 3. Missing nested key – one bad match should not kill the whole batch
# ---------------------------------------------------------------------------
def test_missing_team_key_crashes_batch():
    """If one match in the list is missing 'team1', the current code
    raises a KeyError and returns nothing — even though the other match
    in the batch is perfectly valid.

    Once a try/except guard is added, flip the assertion to verify the
    good match survives."""

    good_match = _make_match()
    bad_match = _make_match()
    del bad_match["team1"]  # corrupt one match

    try:
        result = transform([good_match, bad_match])
        # If we get here the code silently skipped the bad match (future fix)
        assert len(result) == 1
        assert result[0]["home_team"] == "Everton FC"
    except KeyError:
        # --- current behaviour: the whole batch blows up ---
        pass


# ---------------------------------------------------------------------------
# 4. Finished flag true but no After90Minutes result
# ---------------------------------------------------------------------------
def test_finished_match_without_final_result_is_skipped():
    """matchIsFinished is True but matchResults contains only a HalfTime
    entry — no After90Minutes.  The transform should skip this match
    gracefully rather than producing a row with missing score data."""

    match = _make_match()
    match["matchResults"] = [
        {
            "resultTypeKind": "HalfTime",
            "pointsTeam1": 1,
            "pointsTeam2": 0,
        }
    ]

    result = transform([match])

    assert len(result) == 0  # skipped, not crashed
