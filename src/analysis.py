import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# Core helper: "unpivot" each match into two team-perspective rows
# ---------------------------------------------------------------------------

def build_team_matches(df):
    """
    Turn match-level rows into team-level rows.

    Every match produces two rows — one from the home team's perspective
    and one from the away team's.  Each row carries:
        matchweek, match_date, team, opponent, venue,
        goals_for, goals_against, result (W/D/L), points
    """
    rows = []

    for _, m in df.iterrows():
        home = m["home_team"]
        away = m["away_team"]
        hg = int(m["home_goals"])
        ag = int(m["away_goals"])
        mw = int(m["matchweek"])
        md = m["match_date"]

        if hg > ag:
            h_result, a_result = "W", "L"
            h_pts, a_pts = 3, 0
        elif hg < ag:
            h_result, a_result = "L", "W"
            h_pts, a_pts = 0, 3
        else:
            h_result, a_result = "D", "D"
            h_pts, a_pts = 1, 1

        rows.append({
            "matchweek": mw, "match_date": md,
            "team": home, "opponent": away, "venue": "Home",
            "goals_for": hg, "goals_against": ag,
            "result": h_result, "points": h_pts,
        })
        rows.append({
            "matchweek": mw, "match_date": md,
            "team": away, "opponent": home, "venue": "Away",
            "goals_for": ag, "goals_against": hg,
            "result": a_result, "points": a_pts,
        })

    tm = pd.DataFrame(rows)

    if not tm.empty:
        tm = tm.sort_values(["team", "matchweek"]).reset_index(drop=True)

    return tm


# ---------------------------------------------------------------------------
# League table
# ---------------------------------------------------------------------------

def compute_league_table(team_matches):
    """
    Standard Premier League standings sorted by points then goal difference.

    Returns a DataFrame with columns:
        Pos, Team, MP, W, D, L, GF, GA, GD, Pts
    """
    if team_matches.empty:
        return pd.DataFrame()

    agg = (
        team_matches
        .groupby("team")
        .agg(
            MP=("points", "count"),
            W=("result", lambda s: (s == "W").sum()),
            D=("result", lambda s: (s == "D").sum()),
            L=("result", lambda s: (s == "L").sum()),
            GF=("goals_for", "sum"),
            GA=("goals_against", "sum"),
            Pts=("points", "sum"),
        )
        .assign(GD=lambda d: d["GF"] - d["GA"])
        .sort_values(["Pts", "GD", "GF"], ascending=False)
        .reset_index()
        .rename(columns={"team": "Team"})
    )

    agg.insert(0, "Pos", range(1, len(agg) + 1))

    return agg


# ---------------------------------------------------------------------------
# Team form — chronological W/D/L list
# ---------------------------------------------------------------------------

def get_team_form(team_matches, team):
    """
    Return a list of dicts with matchweek, result, opponent, venue,
    goals_for, goals_against — sorted chronologically.
    """
    mask = team_matches["team"] == team
    subset = team_matches.loc[mask].sort_values("matchweek")

    return subset.to_dict("records")


# ---------------------------------------------------------------------------
# Points per game — overall and post-win
# ---------------------------------------------------------------------------

def compute_ppg_metrics(team_matches, team):
    """
    Returns dict: overall_ppg, post_win_ppg, post_win_n,
                  post_draw_ppg, post_draw_n.
    """
    form = get_team_form(team_matches, team)

    total_pts = sum(m["points"] for m in form)
    total_mp = len(form)

    overall_ppg = total_pts / total_mp if total_mp else None

    # Conditional PPG: look at match t whose *previous* match was a W / D / L
    post_win_pts, post_win_n = [], 0
    post_draw_pts, post_draw_n = [], 0

    for i in range(1, len(form)):
        prev_result = form[i - 1]["result"]
        current_pts = form[i]["points"]

        if prev_result == "W":
            post_win_pts.append(current_pts)
            post_win_n += 1
        elif prev_result == "D":
            post_draw_pts.append(current_pts)
            post_draw_n += 1

    return {
        "overall_ppg": round(overall_ppg, 2) if overall_ppg is not None else None,
        "post_win_ppg": round(sum(post_win_pts) / post_win_n, 2) if post_win_n else None,
        "post_win_n": post_win_n,
        "post_draw_ppg": round(sum(post_draw_pts) / post_draw_n, 2) if post_draw_n else None,
        "post_draw_n": post_draw_n,
    }


# ---------------------------------------------------------------------------
# Bounce-back rate
# ---------------------------------------------------------------------------

def compute_bounce_back(team_matches, team):
    """
    Bounce-back = count(L → W) / count(L → any).

    Returns dict: rate (0-1 or None), losses_followed (int),
                  bounced_back (int).
    """
    form = get_team_form(team_matches, team)

    losses_followed = 0
    bounced_back = 0

    for i in range(len(form) - 1):
        if form[i]["result"] == "L":
            losses_followed += 1
            if form[i + 1]["result"] == "W":
                bounced_back += 1

    rate = bounced_back / losses_followed if losses_followed else None

    return {
        "rate": round(rate, 2) if rate is not None else None,
        "losses_followed": losses_followed,
        "bounced_back": bounced_back,
    }


# ---------------------------------------------------------------------------
# Transition matrix  P(result_t | result_{t-1})
# ---------------------------------------------------------------------------

RESULTS_ORDER = ["W", "D", "L"]


def compute_transition_matrix(team_matches, team=None):
    """
    3×3 matrix of P(next_result | prev_result).

    If team is None, uses all teams (league-wide).
    Returns a DataFrame (rows = previous, cols = next) with values 0-1,
    and total counts per row.
    """
    if team:
        mask = team_matches["team"] == team
        subset = team_matches.loc[mask].sort_values("matchweek")
        groups = [(team, subset)]
    else:
        groups = list(team_matches.sort_values("matchweek").groupby("team"))

    counts = pd.DataFrame(
        0, index=RESULTS_ORDER, columns=RESULTS_ORDER, dtype=int
    )

    for _, grp in groups:
        results = grp["result"].tolist()
        for i in range(len(results) - 1):
            prev_r = results[i]
            next_r = results[i + 1]
            if prev_r in RESULTS_ORDER and next_r in RESULTS_ORDER:
                counts.loc[prev_r, next_r] += 1

    row_totals = counts.sum(axis=1)

    probs = counts.div(row_totals, axis=0).fillna(0).round(2)

    return probs, counts, row_totals


# ---------------------------------------------------------------------------
# Goals scored / conceded per matchweek for a team
# ---------------------------------------------------------------------------

def compute_goals_trend(team_matches, team):
    """
    Returns DataFrame with matchweek, goals_for, goals_against
    for the selected team.
    """
    mask = team_matches["team"] == team
    subset = (
        team_matches
        .loc[mask, ["matchweek", "goals_for", "goals_against"]]
        .sort_values("matchweek")
        .reset_index(drop=True)
    )

    return subset


# ---------------------------------------------------------------------------
# Clean sheet rate
# ---------------------------------------------------------------------------

def compute_clean_sheet_rate(team_matches, team):
    """
    Fraction of matches where goals_against == 0.
    Returns dict: rate (0-1), clean_sheets (int), total (int).
    """
    mask = team_matches["team"] == team
    subset = team_matches.loc[mask]

    total = len(subset)
    clean = int((subset["goals_against"] == 0).sum())
    rate = clean / total if total else None

    return {
        "rate": round(rate, 2) if rate is not None else None,
        "clean_sheets": clean,
        "total": total,
    }


# ---------------------------------------------------------------------------
# Home vs away split
# ---------------------------------------------------------------------------

def compute_home_away_split(team_matches, team):
    """
    Returns dict with 'Home' and 'Away' sub-dicts containing
    MP, W, D, L, GF, GA, PPG.
    """
    mask = team_matches["team"] == team
    subset = team_matches.loc[mask]

    split = {}

    for venue in ["Home", "Away"]:
        v = subset[subset["venue"] == venue]
        mp = len(v)

        if mp == 0:
            split[venue] = {
                "MP": 0, "W": 0, "D": 0, "L": 0,
                "GF": 0, "GA": 0, "PPG": None,
            }
            continue

        split[venue] = {
            "MP": mp,
            "W": int((v["result"] == "W").sum()),
            "D": int((v["result"] == "D").sum()),
            "L": int((v["result"] == "L").sum()),
            "GF": int(v["goals_for"].sum()),
            "GA": int(v["goals_against"].sum()),
            "PPG": round(v["points"].sum() / mp, 2),
        }

    return split


# ---------------------------------------------------------------------------
# Data quality summary
# ---------------------------------------------------------------------------

def compute_data_quality(df, team_matches):
    """
    Returns a dict with key data-quality metrics visible in the dashboard.
    """
    matchweeks_loaded = sorted(df["matchweek"].unique().tolist())
    total_matches = len(df)
    total_team_rows = len(team_matches)
    teams = sorted(team_matches["team"].unique().tolist())

    # Check for expected 10 matches per complete matchweek
    mw_counts = df.groupby("matchweek").size().to_dict()
    incomplete_mws = {
        mw: cnt for mw, cnt in mw_counts.items() if cnt < 10
    }

    # Missing values
    missing = df.isnull().sum()
    missing_cols = {
        col: int(cnt) for col, cnt in missing.items() if cnt > 0
    }

    return {
        "matchweeks_loaded": matchweeks_loaded,
        "total_matches": total_matches,
        "total_team_rows": total_team_rows,
        "num_teams": len(teams),
        "teams": teams,
        "matches_per_matchweek": mw_counts,
        "incomplete_matchweeks": incomplete_mws,
        "missing_values": missing_cols,
        "last_update": df["last_update"].max() if "last_update" in df.columns else None,
    }