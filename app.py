import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path

from src.analysis import (
    build_team_matches,
    compute_league_table,
    get_team_form,
    compute_ppg_metrics,
    compute_bounce_back,
    compute_transition_matrix,
    compute_goals_trend,
    compute_clean_sheet_rate,
    compute_home_away_split,
    compute_data_quality,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="PL 26/27 Analyst Dashboard",
    page_icon="⚽",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Global style — larger fonts, compact table, readable abbreviations
# ---------------------------------------------------------------------------

st.markdown("""
<style>
    /* Base font bump */
    html, body, [class*="st-"] {
        font-size: 16px;
    }

    /* KPI metric values bigger */
    [data-testid="stMetricValue"] {
        font-size: 28px !important;
    }

    /* KPI metric labels */
    [data-testid="stMetricLabel"] {
        font-size: 15px !important;
    }

    /* Section headers */
    .stMarkdown h5 {
        font-size: 20px !important;
        margin-bottom: 4px !important;
    }

    /* Dataframe cells */
    .stDataFrame td, .stDataFrame th {
        font-size: 14px !important;
        padding: 4px 8px !important;
    }

    /* Subtitle helper text under abbreviations */
    .kpi-subtitle {
        color: gray;
        font-size: 12px;
        margin-top: -14px;
        padding-bottom: 4px;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

C_WIN = "#2ECC71"      # green
C_DRAW = "#F39C12"     # amber
C_LOSS = "#E74C3C"     # red
C_BG_CARD = "#1A1A2E"  # dark navy
C_ACCENT = "#16213E"   # slightly lighter navy
C_TEXT = "#EAEAEA"      # off-white
C_MUTED = "#7F8C8D"    # muted gray
C_HIGHLIGHT = "#3B82F6" # blue highlight for selected team


RESULT_COLOUR = {"W": C_WIN, "D": C_DRAW, "L": C_LOSS}

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

DATA_PATH = Path(__file__).resolve().parent / "data" / "processed" / "matches.csv"


@st.cache_data
def load_data():
    if not DATA_PATH.exists():
        return pd.DataFrame(), pd.DataFrame()
    df = pd.read_csv(DATA_PATH)
    tm = build_team_matches(df)
    return df, tm


df, team_matches = load_data()

if df.empty:
    st.error("No data found. Run `python etl.py` first to fetch match data.")
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar — team selector
# ---------------------------------------------------------------------------

league_table = compute_league_table(team_matches)
teams_sorted = league_table["Team"].tolist()

st.sidebar.markdown("## ⚽ Team Analyst View")
selected_team = st.sidebar.selectbox(
    "Select your team",
    options=teams_sorted,
    index=0,
)

# Quick context in sidebar
pos_row = league_table[league_table["Team"] == selected_team].iloc[0]
st.sidebar.markdown("---")
st.sidebar.metric("League Position", f"{int(pos_row['Pos'])} / {len(teams_sorted)}")
st.sidebar.metric("Points", int(pos_row["Pts"]))
st.sidebar.metric("Goal Difference", f"{int(pos_row['GD']):+d}")

# Data quality in sidebar expander
dq = compute_data_quality(df, team_matches)
with st.sidebar.expander("📊 Data Quality"):
    st.caption(f"**Matches loaded:** {dq['total_matches']}")
    st.caption(f"**Teams:** {dq['num_teams']}")
    st.caption(f"**Matchweeks:** {', '.join(str(m) for m in dq['matchweeks_loaded'])}")
    if dq["incomplete_matchweeks"]:
        for mw, cnt in dq["incomplete_matchweeks"].items():
            st.caption(f"⚠️ MW {mw}: {cnt}/10 matches")
    if dq["missing_values"]:
        for col, cnt in dq["missing_values"].items():
            st.caption(f"⚠️ {col}: {cnt} missing")
    else:
        st.caption("✅ No missing values")
    if dq["last_update"]:
        st.caption(f"**Last ETL update:** {dq['last_update'][:16]}")


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown(
    f"<h1 style='text-align:center; margin-bottom:0;'>"
    f"{selected_team}</h1>"
    f"<p style='text-align:center; color:gray; margin-top:0;'>"
    f"Premier League 2026/27 — Analyst Dashboard</p>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Row 1 — KPI cards + form cubes
# ---------------------------------------------------------------------------

ppg = compute_ppg_metrics(team_matches, selected_team)
bb = compute_bounce_back(team_matches, selected_team)
cs = compute_clean_sheet_rate(team_matches, selected_team)
form = get_team_form(team_matches, selected_team)

kpi_cols = st.columns(5)

with kpi_cols[0]:
    st.metric("MP", int(pos_row["MP"]))
    st.markdown('<p class="kpi-subtitle">Matches Played</p>', unsafe_allow_html=True)

with kpi_cols[1]:
    st.metric("PPG", ppg["overall_ppg"] if ppg["overall_ppg"] is not None else "—")
    st.markdown('<p class="kpi-subtitle">Points Per Game</p>', unsafe_allow_html=True)

with kpi_cols[2]:
    val = ppg["post_win_ppg"] if ppg["post_win_ppg"] is not None else "—"
    st.metric("PW-PPG", val)
    n_label = f"(n={ppg['post_win_n']})" if ppg["post_win_n"] else ""
    st.markdown(f'<p class="kpi-subtitle">PPG After a Win {n_label}</p>', unsafe_allow_html=True)

with kpi_cols[3]:
    bb_display = f"{int(bb['rate'] * 100)}%" if bb["rate"] is not None else "—"
    st.metric("BB%", bb_display)
    if bb["losses_followed"] > 0:
        bb_sub = f"Bounce-Back · {bb['bounced_back']}/{bb['losses_followed']} losses → win"
    else:
        bb_sub = "Bounce-Back · No losses yet"
    st.markdown(f'<p class="kpi-subtitle">{bb_sub}</p>', unsafe_allow_html=True)

with kpi_cols[4]:
    cs_display = f"{int(cs['rate'] * 100)}%" if cs["rate"] is not None else "—"
    st.metric("CS%", cs_display)
    st.markdown(
        f'<p class="kpi-subtitle">Clean Sheets · {cs["clean_sheets"]}/{cs["total"]} games</p>',
        unsafe_allow_html=True,
    )

# Form cubes
st.markdown("##### Recent Form")

form_html_parts = []
for m in form:
    r = m["result"]
    colour = RESULT_COLOUR[r]
    tooltip = f"MW{m['matchweek']}: {'vs' if m['venue']=='Home' else '@'} {m['opponent']} ({m['goals_for']}-{m['goals_against']})"
    form_html_parts.append(
        f'<div title="{tooltip}" style="'
        f"display:inline-block; width:48px; height:48px; "
        f"background:{colour}; color:white; font-weight:700; "
        f"font-size:22px; text-align:center; line-height:48px; "
        f"border-radius:6px; margin-right:8px; cursor:default;"
        f'">{r}</div>'
    )

record_str = f"{int(pos_row['W'])}W  {int(pos_row['D'])}D  {int(pos_row['L'])}L"
form_html = (
    '<div style="display:flex; align-items:center; gap:12px; flex-wrap:wrap;">'
    + "".join(form_html_parts)
    + f'<span style="color:gray; font-size:16px; margin-left:8px;">{record_str}</span>'
    + "</div>"
)
st.markdown(form_html, unsafe_allow_html=True)

st.markdown("")

# ---------------------------------------------------------------------------
# Row 2 — League table + Goals trend
# ---------------------------------------------------------------------------

col_table, col_chart = st.columns([3, 2])

with col_table:
    st.markdown("##### League Standings")

    display_table = league_table[["Pos", "Team", "MP", "W", "D", "L", "GF", "GA", "GD", "Pts"]].copy()

    def highlight_team(row):
        if row["Team"] == selected_team:
            return [f"background-color: {C_HIGHLIGHT}22; font-weight: 700"] * len(row)
        return [""] * len(row)

    styled = (
        display_table.style
        .apply(highlight_team, axis=1)
        .set_properties(**{"text-align": "center"})
        .set_properties(subset=["Team"], **{"text-align": "left"})
        .hide(axis="index")
    )

    st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
        height=300,
    )

with col_chart:
    st.markdown("##### Goals Per Matchweek")

    goals = compute_goals_trend(team_matches, selected_team)

    if not goals.empty:
        fig_goals = go.Figure()

        fig_goals.add_trace(go.Bar(
            x=goals["matchweek"].astype(str),
            y=goals["goals_for"],
            name="Scored",
            marker_color=C_WIN,
        ))

        fig_goals.add_trace(go.Bar(
            x=goals["matchweek"].astype(str),
            y=goals["goals_against"],
            name="Conceded",
            marker_color=C_LOSS,
        ))

        fig_goals.update_layout(
            barmode="group",
            xaxis_title="Matchweek",
            yaxis_title="Goals",
            yaxis=dict(dtick=1),
            legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center"),
            margin=dict(l=20, r=20, t=40, b=40),
            height=380,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )

        st.plotly_chart(fig_goals, use_container_width=True)
    else:
        st.info("No match data for this team yet.")

# ---------------------------------------------------------------------------
# Row 3 — Home/Away split + Transition matrix
# ---------------------------------------------------------------------------

col_split, col_matrix = st.columns(2)

with col_split:
    st.markdown("##### Home vs Away")

    ha = compute_home_away_split(team_matches, selected_team)

    venues = ["Home", "Away"]
    bar_colours = {
        "W": C_WIN,
        "D": C_DRAW,
        "L": C_LOSS,
    }

    fig_ha = go.Figure()

    for result_type in ["W", "D", "L"]:
        fig_ha.add_trace(go.Bar(
            x=venues,
            y=[ha[v][result_type] for v in venues],
            name={"W": "Win", "D": "Draw", "L": "Loss"}[result_type],
            marker_color=bar_colours[result_type],
        ))

    fig_ha.update_layout(
        barmode="stack",
        yaxis_title="Matches",
        yaxis=dict(dtick=1),
        legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center"),
        margin=dict(l=20, r=20, t=40, b=40),
        height=340,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )

    st.plotly_chart(fig_ha, use_container_width=True)

    # PPG comparison underneath
    home_ppg = ha["Home"]["PPG"] if ha["Home"]["PPG"] is not None else "—"
    away_ppg = ha["Away"]["PPG"] if ha["Away"]["PPG"] is not None else "—"
    st.markdown(
        f'<div style="display:flex; justify-content:space-around; text-align:center;">'
        f'<div><span style="font-size:28px; font-weight:700;">{home_ppg}</span>'
        f'<br><span style="color:gray; font-size:14px;">Home PPG</span>'
        f'<br><span style="color:gray; font-size:11px;">Points Per Game at Home</span></div>'
        f'<div><span style="font-size:28px; font-weight:700;">{away_ppg}</span>'
        f'<br><span style="color:gray; font-size:14px;">Away PPG</span>'
        f'<br><span style="color:gray; font-size:11px;">Points Per Game Away</span></div>'
        f"</div>",
        unsafe_allow_html=True,
    )

with col_matrix:
    st.markdown("##### Transition Probabilities")
    st.caption("Likelihood of next result given the previous one")

    # Toggle between team and league-wide
    matrix_scope = st.radio(
        "Scope",
        ["Selected team", "League-wide"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if matrix_scope == "Selected team":
        probs, counts, totals = compute_transition_matrix(team_matches, selected_team)
    else:
        probs, counts, totals = compute_transition_matrix(team_matches, None)

    labels_display = ["Win", "Draw", "Loss"]

    # Build annotation text: show probability and count
    annotations = []
    for i, prev in enumerate(["W", "D", "L"]):
        for j, nxt in enumerate(["W", "D", "L"]):
            p = probs.loc[prev, nxt]
            n = counts.loc[prev, nxt]
            total = totals[prev]
            if total > 0:
                text = f"{p:.0%}<br><span style='font-size:11px;color:gray'>({n}/{total})</span>"
            else:
                text = "—"
            annotations.append(text)

    z_values = probs.values.tolist()

    fig_tm = go.Figure(data=go.Heatmap(
        z=z_values,
        x=labels_display,
        y=labels_display,
        text=[[annotations[i * 3 + j] for j in range(3)] for i in range(3)],
        texttemplate="%{text}",
        colorscale=[
            [0.0, "#2C3E50"],
            [0.5, "#F39C12"],
            [1.0, "#27AE60"],
        ],
        showscale=False,
        hoverinfo="skip",
    ))

    fig_tm.update_layout(
        xaxis_title="Next Result →",
        yaxis_title="Previous Result",
        yaxis=dict(autorange="reversed"),
        margin=dict(l=20, r=20, t=20, b=60),
        height=340,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )

    st.plotly_chart(fig_tm, use_container_width=True)

# ---------------------------------------------------------------------------
# Row 4 — Match log
# ---------------------------------------------------------------------------

st.markdown("##### Match Log")

form_df = pd.DataFrame(form)

if not form_df.empty:
    display_log = form_df[["matchweek", "match_date", "opponent", "venue", "goals_for", "goals_against", "result"]].copy()
    display_log.columns = ["MW", "Date", "Opponent", "Venue", "GF", "GA", "Result"]

    def colour_result(val):
        colours = {"W": C_WIN, "D": C_DRAW, "L": C_LOSS}
        c = colours.get(val, "")
        return f"color: {c}; font-weight: 700" if c else ""

    styled_log = (
        display_log.style
        .map(colour_result, subset=["Result"])
        .set_properties(**{"text-align": "center"})
        .set_properties(subset=["Opponent"], **{"text-align": "left"})
        .hide(axis="index")
    )

    st.dataframe(styled_log, use_container_width=True, hide_index=True)
else:
    st.info("No matches played yet.")