import re
from collections import defaultdict
from pathlib import Path
import pandas as pd
import streamlit as st
import xml.etree.ElementTree as ET

# =========================
# Brand & tema (F.C. København)
# =========================
BRAND = {
    "primary": "#001E96",   # FCK blå (justér hvis du har officiel hex)
    "white":   "#FFFFFF",
    "accent":  "#D00000",   # rød accent (løven)
    "bg":      "#001E96",
    "text":    "#0B1221",
    "muted":   "#001E96",
    "grey":    "#001E96",
}
LOGO_PATH = "/Users/nicklaspedersen/Desktop/SUPERLIGA DATA 25-26/FC_Copenhagen_logo.svg.png"
PAGE_TITLE = "F.C. København - Throw-in Analysis"
PAGE_ICON = LOGO_PATH  # kan også være en emoji: "🦁"

TEAM_NAME = "FC København"
TEAM_ALIASES = {
    "FC København", "F.C. København", "FC Copenhagen", "F.C. Copenhagen",
    "København", "Copenhagen"
}

st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="wide")

# Global CSS (chips, tabeller, headerbar, baggrund)
st.markdown(f"""
<style>
/* Baggrund og tekst */
.stApp {{
  background: linear-gradient(180deg, {BRAND["bg"]} 0%, #FFFFFF 100%);
  color: {BRAND["text"]};
}}
/* Headerbar med logo */
.fck-header {{
  display:flex; align-items:center; gap:12px; padding:10px 14px; margin-bottom:8px;
  border-radius:14px; background: {BRAND["white"]}; border:1px solid {BRAND["grey"]}33;
  box-shadow: 0 4px 14px rgba(0,0,0,0.04);
}}
.fck-header h1 {{
  font-size: 1.25rem; line-height:1.2; margin:0;
}}
.fck-kicker {{
  color:{BRAND["muted"]}; font-weight:600; letter-spacing: .02em; text-transform:uppercase;
  font-size:.8rem;
}}
/* Sidebar titel */
section[data-testid="stSidebar"] .stHeading, .stSidebar h2, .stSidebar h3 {{
  color: {BRAND["primary"]};
}}
/* Chips-stil radio/segmented control */
[data-baseweb="button-group"] button, .stRadio [role="radiogroup"] > label {{
  border-radius: 999px !important;
}}
.stRadio label span {{
  padding: 6px 12px !important; border-radius:999px !important; border:1px solid {BRAND["grey"]};
}}
.stRadio label div[role="radio"][aria-checked="true"] + span {{
  background: {BRAND["primary"]}; color: white; border-color:{BRAND["primary"]};
}}
/* DataFrame header */
[data-testid="stDataFrame"] thead th {{
  background: {BRAND["primary"]} !important; color: white !important;
}}
/* Knapper */
.stButton>button {{
  border-radius: 12px; border: 1px solid {BRAND["primary"]};
  background: {BRAND["primary"]}; color:white;
}}
.stButton>button:hover {{ filter: brightness(0.95); }}
/* Metric chips */
.fck-chip {{
  display:inline-flex; align-items:center; gap:8px; padding:6px 10px; border-radius:999px;
  background:{BRAND["white"]}; border:1px solid {BRAND["grey"]}66; color:{BRAND["text"]};
  font-size:.9rem; margin: 2px 6px 10px 0;
}}
/* Små badges */
.badge {{
  display:inline-block; padding:2px 8px; border-radius:999px; font-size:.75rem; font-weight:600;
  border:1px solid {BRAND["grey"]}; color:{BRAND["muted"]};
}}
</style>
""", unsafe_allow_html=True)

# Header-komponent
header_cols = st.columns([0.08, 0.92])
with header_cols[0]:
    try:
        st.image(LOGO_PATH, use_container_width=True)
    except Exception:
        st.markdown(f"<div class='badge'>FCK</div>", unsafe_allow_html=True)
with header_cols[1]:
    st.markdown(f"""
    <div class="fck-header">
      <div class="fck-kicker">Analyse</div>
      <h1>{PAGE_TITLE}</h1>
    </div>
    """, unsafe_allow_html=True)

# =========================
# Sidebar: indstillinger
# =========================
st.sidebar.subheader("Indstillinger")
DATA_BASE = st.sidebar.text_input(
    "Base path til data",
    value="/Users/nicklaspedersen/Desktop/SUPERLIGA DATA 25-26",
    help="Mappe der indeholder R1, R2, ... med F24/F7/SRML."
)
st.sidebar.caption("Tip: Læg logo i `assets/fck_logo.png` eller justér sti i koden.")

# =========================
# Hjælpere (fælles)
# =========================
def natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.findall(r"\d+|\D+", s)]

def list_round_dirs(base: str):
    p = Path(base).expanduser()
    if not p.exists():
        return []
    return sorted([d for d in p.iterdir() if d.is_dir() and re.fullmatch(r"R\d+", d.name)],
                  key=lambda x: natural_key(x.name))

def extract_match_id(name: str):
    nums = re.findall(r"(\d{5,})", name)
    return nums[-1] if nums else None

def is_f7_filename(path: Path) -> bool:
    up = path.stem.upper()
    return ("F7" in up or "F70" in up or "SRML" in up or "MATCHRESULTS" in up)

def get_match_info_from_f24(f24_path: Path):
    """Returner (matchnavn, dato) ud fra <Game>."""
    home = away = None
    date = None
    try:
        root = ET.parse(f24_path).getroot()
        game = root.find(".//Game")
        if game is not None:
            home = game.get("home_team_name")
            away = game.get("away_team_name")
            date = game.get("game_date") or game.get("GameDate") or game.get("date")
        if not (home and away):
            home_el = root.find(".//Team[@Side='Home']") or root.find(".//Team[@side='Home']")
            away_el = root.find(".//Team[@Side='Away']") or root.find(".//Team[@side='Away']")
            if home_el is not None and away_el is not None:
                home = home_el.get("TeamName") or home_el.get("name")
                away = away_el.get("TeamName") or away_el.get("name")
    except Exception:
        pass

    match_name = f"{home} - {away}" if home and away else f24_path.stem
    match_date = None
    if date:
        try:
            match_date = pd.to_datetime(date).date()
        except Exception:
            pass
    return match_name, match_date

def collect_round_data(round_dir: Path):
    f24_files = [f for f in round_dir.iterdir()
                 if f.is_file() and f.suffix.lower()==".xml" and "F24" in f.stem.upper()]
    f7_files  = [f for f in round_dir.iterdir()
                 if f.is_file() and f.suffix.lower()==".xml" and is_f7_filename(f)]

    f7_by_id = {(extract_match_id(f7.name) or f7.stem): f7 for f7 in f7_files}

    rows = []
    for f24 in f24_files:
        mid = extract_match_id(f24.name) or f24.stem
        f7  = f7_by_id.get(mid)
        match_name, match_date = get_match_info_from_f24(f24)
        rows.append({
            "Date": match_date.strftime("%d-%m-%Y") if match_date else "",
            "Match": match_name,
            "F24 file": f24.name,
            "F7 file": f7.name if f7 else "(mangler)",
            "_sortdate": match_date
        })
    return rows

# =========================
# Throw-in analyse – parsing
# =========================
EVENT_TYPE_PASS = 1
EVENT_TYPE_BALL_OUT = 5
QUALIFIER_THROW_IN = 107

def _safe_int(val, default=0):
    try:
        return int(val)
    except Exception:
        return default

def _safe_float(val):
    try:
        return float(val)
    except Exception:
        return None

def build_team_maps_from_f7(f7_path: Path):
    """
    Returnér (name_map, side_map):
      - name_map: {'t1234': 'Team', '1234': 'Team'}
      - side_map: {'t1234': 'Home'/'Away', '1234': 'Home'/'Away'}
    """
    name_map, side_map = {}, {}
    try:
        root = ET.parse(str(f7_path)).getroot()
        for team in root.findall(".//Team"):
            uid = team.attrib.get("uID")
            name_el = team.find("Name")
            name = (name_el.text if name_el is not None else None) or team.attrib.get("TeamName")
            if uid and name:
                name_map[uid] = name
                if uid.startswith("t") and uid[1:].isdigit():
                    name_map[uid[1:]] = name
        for td in root.findall(".//MatchData/TeamData"):
            tref = td.attrib.get("TeamRef"); side = td.attrib.get("Side")
            if tref and side:
                side_map[tref] = side
                if tref.startswith("t") and tref[1:].isdigit():
                    side_map[tref[1:]] = side
    except Exception:
        pass
    return name_map, side_map

def _parse_game_events(game_elem, team_name_map=None, team_side_map=None):
    """Parser <Event>; returnerer meta + sorteret events (inkl. x,y)."""
    game_meta = {
        "game_id": game_elem.attrib.get("id", ""),
        "game_date": game_elem.attrib.get("game_date", ""),
    }
    events = []
    for ev in game_elem.findall("Event"):
        type_id   = _safe_int(ev.attrib.get("type_id", -1), -1)
        period_id = _safe_int(ev.attrib.get("period_id", -1), -1)
        team_id   = ev.attrib.get("team_id", "")
        min_ = _safe_int(ev.attrib.get("min", 0), 0)
        sec_ = _safe_int(ev.attrib.get("sec", 0), 0)
        time_s = min_ * 60 + sec_
        x = _safe_float(ev.attrib.get("x"))
        y = _safe_float(ev.attrib.get("y"))
        quals = set(_safe_int(q.attrib.get("qualifier_id", -1), -1) for q in ev.findall("Q") if q is not None)
        team_name = team_name_map.get(team_id, team_id) if team_name_map else team_id
        team_side = team_side_map.get(team_id) if team_side_map else None
        events.append({
            "type_id": type_id, "period_id": period_id, "team_id": team_id,
            "team_name": team_name, "team_side": team_side,
            "min": min_, "sec": sec_, "time_s": time_s,
            "x": x, "y": y, "qualifiers": quals,
            "game_date": game_meta["game_date"],
        })
    events.sort(key=lambda x: (x["period_id"], x["time_s"]))
    return game_meta, events

def _zone_from_x(x):
    """Absolut tredjedel (0-100 opdelt i 3)."""
    if x is None:
        return "Unknown"
    if x <= 33.3333:
        return "First 1/3"
    elif x <= 66.6666:
        return "Second 1/3"
    else:
        return "Last 1/3"

def _is_fck(name: str) -> bool:
    if not name:
        return False
    return name in TEAM_ALIASES

def _compute_throwin_delays(events):
    """
    type_id=5 → næste (type_id=1 + qualifier 107) i samme periode.
    Gem x,y + Zone, og sæt Third = Zone (absolut).
    """
    rows, n = [], len(events)
    for i, e in enumerate(events):
        if e["type_id"] != EVENT_TYPE_BALL_OUT:
            continue
        period = e["period_id"]
        t_out = e["time_s"]
        j = i + 1
        while j < n and events[j]["period_id"] == period:
            nxt = events[j]
            if nxt["type_id"] == EVENT_TYPE_BALL_OUT:
                break
            if nxt["type_id"] == EVENT_TYPE_PASS and (QUALIFIER_THROW_IN in nxt["qualifiers"]):
                delay = max(0, nxt["time_s"] - t_out)
                z = _zone_from_x(nxt.get("x"))
                team_name = nxt["team_name"]
                rows.append({
                    "Period": period,
                    "Ball out (mm:ss)": f"{e['min']:02d}:{e['sec']:02d}",
                    "Throw-in (mm:ss)": f"{nxt['min']:02d}:{nxt['sec']:02d}",
                    "Delay (s)": round(delay, 1),
                    "Team": team_name,
                    "Side": nxt["team_side"] or "",
                    "x": nxt.get("x"), "y": nxt.get("y"),
                    "Zone": z,
                    "Third": z,   # <-- Third == Zone
                    "is_FCK": _is_fck(team_name),
                })
                break
            j += 1
    return rows

@st.cache_data(show_spinner=False)
def parse_throwin_delays_from_f24_cached(f24_str_path: str, f7_str_path: str | None, cache_buster: int = 5):
    """Parser F24 (+ F7) og returnerer DF med kast + delay + x,y + Zone/Third + game date."""
    f24_path = Path(f24_str_path)
    f7_path = Path(f7_str_path) if f7_str_path else None

    name_map, side_map = {}, {}
    if f7_path and f7_path.exists():
        name_map, side_map = build_team_maps_from_f7(f7_path)

    all_rows = []
    try:
        root = ET.parse(str(f24_path)).getroot()
    except Exception:
        return pd.DataFrame()

    for game in root.findall(".//Game"):
        game_meta, events = _parse_game_events(game, team_name_map=name_map, team_side_map=side_map)
        rows = _compute_throwin_delays(events)
        for r in rows:
            all_rows.append({
                **r,
                "Game date": game_meta.get("game_date", ""),
            })
    return pd.DataFrame(all_rows)

# =========================
# UI: Tabs
# =========================
tab_superliga, tab_matches, tab_data = st.tabs(
    ["League overview", "Matches", "Data"]
)

# ---- Superliga/FCK throw-ins (oversigt) ----
with tab_superliga:
    st.header("Superliga throw-ins 2025/26")
    round_dirs_all = list_round_dirs(DATA_BASE)
    if not round_dirs_all:
        st.stop()

    def _round_num(p: Path):
        m = re.search(r"R(\d+)$", p.name)
        return int(m.group(1)) if m else None

    round_nums = [n for n in (_round_num(p) for p in round_dirs_all) if n is not None]
    min_r, max_r = min(round_nums), max(round_nums)

    sel_min, sel_max = st.slider("Choose round/s",
                                 min_value=min_r, max_value=max_r,
                                 value=(min_r, max_r), step=1)

    selected_rounds = {r for r in range(sel_min, sel_max + 1)}
    round_dirs = [p for p in round_dirs_all if _round_num(p) in selected_rounds]

    side_filter = st.radio("Choose Home/Away", ["All", "Home", "Away"],
                           horizontal=True, key="superliga_side_filter")
    third_filter = st.radio("Choose Third",
                            ["All", "First 1/3", "Second 1/3", "Last 1/3"],
                            horizontal=True, key="superliga_third_filter")

    # Saml kast på tværs af valgte runder
    all_rows = []
    for round_dir in round_dirs:
        rows = collect_round_data(round_dir)
        if not rows:
            continue
        df_round = pd.DataFrame(rows)
        for _, r in df_round.iterrows():
            f24_path = round_dir / r["F24 file"]
            f7_path  = (round_dir / r["F7 file"]) if r["F7 file"] != "(mangler)" else None
            df_throw = parse_throwin_delays_from_f24_cached(str(f24_path), str(f7_path) if f7_path else None, 5)
            if not df_throw.empty:
                df_throw["Round"] = round_dir.name
                df_throw["Match"] = r["Match"]
                all_rows.append(df_throw)

    if not all_rows:
        st.info("Ingen indkast fundet i det valgte interval.")
        st.stop()

    season_df = pd.concat(all_rows, ignore_index=True)

    if side_filter != "All":
        season_df = season_df[season_df["Side"] == side_filter]
    if third_filter != "All":
        season_df = season_df[season_df["Third"] == third_filter]

    if season_df.empty:
        st.info("Ingen indkast efter valgte filtre.")
        st.stop()

    season_df["Delay (s)"] = pd.to_numeric(season_df["Delay (s)"], errors="coerce")

    # Overview pr. hold (med FCK-fremhævning)
    g = season_df.groupby("Team", dropna=False)
    overview = pd.DataFrame({
        "Games": g["Match"].nunique(),
        "Total throw-ins": g.size(),
        "Avg. delay (s)": g["Delay (s)"].mean().round(2),
        "Throw-ins <7s": g.apply(lambda x: (x["Delay (s)"] < 7).sum()),
    }).reset_index()
    overview["Throw-ins per game"] = (overview["Total throw-ins"] / overview["Games"]).round(2)

# Altair chart – FCK blå vs. grå (uden at bryde sorteringen)
import altair as alt

metric = st.selectbox("Choose metric",
                      ["Avg. delay (s)", "Throw-ins per game",
                       "Total throw-ins", "Throw-ins <7s"])

overview_sorted = overview.sort_values([metric, "Team"], ascending=[False, True]).reset_index(drop=True)

chart_df = pd.DataFrame({
    "Team": overview_sorted["Team"],
    "Value": pd.to_numeric(overview_sorted[metric], errors="coerce"),
}).dropna()
chart_df["is_FCK"] = chart_df["Team"].apply(lambda t: t in TEAM_ALIASES)

# Eksplicit sorteringsorden = rækkefølgen i overview_sorted
team_order = overview_sorted["Team"].tolist()
chart_h = max(300, len(chart_df) * 32)

chart = (
    alt.Chart(chart_df, height=chart_h, width="container")
      .mark_bar()
      .encode(
          y=alt.Y("Team:N", sort=team_order, title="Team"),
          x=alt.X("Value:Q", title=metric),
          # Én mark + conditional color => ingen lag der forstyrrer sortering
          color=alt.condition(alt.datum.is_FCK,
                              alt.value(BRAND["primary"]),     # FCK
                              alt.value("#A1A1A1")),           # øvrige
          tooltip=["Team", "Value"]
      )
      .configure_legend(disable=True)  # vi bruger ikke en egentlig farve-legend
)

st.altair_chart(chart, use_container_width=True)

st.dataframe(overview_sorted, hide_index=True)

with st.expander("Raw indkast (alle kampe)"):
        raw_cols = ["Round", "Match", "Side", "Third", "Zone", "x", "y", "Period",
                    "Ball out (mm:ss)", "Throw-in (mm:ss)", "Delay (s)", "Team", "Game date", "is_FCK"]
        raw_cols = [c for c in raw_cols if c in season_df.columns]
        st.dataframe(season_df[raw_cols], hide_index=True)

# ---- Kampe ----
with tab_matches:
    st.header("Kampe")
    for round_dir in list_round_dirs(DATA_BASE):
        rows = collect_round_data(round_dir)
        if rows:
            df = pd.DataFrame(rows)
            if "_sortdate" in df.columns:
                df = df.sort_values("_sortdate", na_position="last")
            st.subheader(round_dir.name)
            st.dataframe(df.drop(columns=["_sortdate"]), hide_index=True)

# ---- Kampdata (indkast pr. kamp) ----
with tab_data:
    st.header("Kampdata – Indkast")

    rounds = list_round_dirs(DATA_BASE)
    if rounds:
        round_choice = st.selectbox("Vælg runde", rounds, format_func=lambda p: p.name)
        rows = collect_round_data(round_choice)
        if rows:
            matches_df = pd.DataFrame(rows)
            match_choice = st.selectbox("Vælg kamp", matches_df["Match"])

            f24_file = matches_df.loc[matches_df["Match"] == match_choice, "F24 file"].values[0]
            f7_file  = matches_df.loc[matches_df["Match"] == match_choice, "F7 file"].values[0]

            f24_path = round_choice / f24_file
            f7_path  = (round_choice / f7_file) if f7_file != "(mangler)" else None

            df_throw = parse_throwin_delays_from_f24_cached(str(f24_path), str(f7_path) if f7_path else None, 5)
            if not df_throw.empty:
                st.subheader(f"Indkast – {match_choice}")

                # Sorter kronologisk og nummerér kast
                def _to_seconds(mmss):
                    try:
                        m, s = str(mmss).split(":")
                        return int(m) * 60 + int(s)
                    except Exception:
                        return 10**9  # fallback

                df_throw["_sort"] = pd.to_numeric(df_throw["Period"], errors="coerce").fillna(0).astype(int) * 10_000 \
                                   + df_throw["Ball out (mm:ss)"].map(_to_seconds)
                df_throw = df_throw.sort_values("_sort").drop(columns=["_sort"]).reset_index(drop=True)
                df_throw["Throw-in #"] = range(1, len(df_throw)+1)
                df_throw["is_FCK"] = df_throw["Team"].apply(lambda t: t in TEAM_ALIASES)

                # Toggles (øverst)
                side_tog = st.radio("Side", ["All", "Home", "Away"],
                                    horizontal=True, key="data_side_filter")
                period_tog = st.radio("Periode", ["All", "1", "2"],
                                      horizontal=True, key="data_period_filter")
                delay_tog = st.radio("Delay-filter", ["All", "< 7s only"],
                                     horizontal=True, key="data_delay_filter")
                third_tog = st.radio("Tredjedel (absolut)",
                                     ["All", "First 1/3", "Second 1/3", "Last 1/3"],
                                     horizontal=True, key="data_third_filter")

                # Anvend filtre
                df_plot = df_throw.copy()
                if side_tog != "All":
                    df_plot = df_plot[df_plot["Side"] == side_tog]
                if period_tog != "All":
                    df_plot = df_plot[pd.to_numeric(df_plot["Period"], errors="coerce") == int(period_tog)]
                if delay_tog != "All":
                    df_plot = df_plot[pd.to_numeric(df_plot["Delay (s)"], errors="coerce") < 7]
                if third_tog != "All":
                    df_plot = df_plot[df_plot["Third"] == third_tog]

                # Layout: map venstre, tabeller højre
                col1, col2 = st.columns([1.1, 1.65])

                with col1:
                    try:
                        from mplsoccer import Pitch
                        import matplotlib.pyplot as plt
                        import matplotlib.patheffects as pe

                        pitch = Pitch(pitch_type="opta", line_zorder=2,
                                      pitch_color="white", line_color="black")
                        fig, ax = pitch.draw(figsize=(5.2, 4.2))  # kompakt

                        if df_plot.empty:
                            st.info("Ingen indkast matcher de valgte filtre.")
                        else:
                            # FCK = blå, andre = lysegrå
                            import numpy as np
                            def color_for_team(team):
                                return BRAND["primary"] if team in TEAM_ALIASES else "#C8CDD9"

                            # Plot pr. hold
                            for team, sub in df_plot.groupby(df_plot["Team"].fillna("Unknown")):
                                x = pd.to_numeric(sub["x"], errors="coerce")
                                y = pd.to_numeric(sub["y"], errors="coerce")
                                mask = x.notna() & y.notna()
                                if not mask.any():
                                    continue
                                sizes = 60 + pd.to_numeric(sub["Delay (s)"], errors="coerce").fillna(0) * 10
                                face = color_for_team(team)
                                edge = "#000000" if team in TEAM_ALIASES else "#666666"

                                ax.scatter(
                                    x[mask].astype(float), y[mask].astype(float),
                                    s=sizes[mask],
                                    facecolors=face,
                                    edgecolors=edge,
                                    linewidth=0.8,
                                    alpha=0.95,
                                    zorder=3,
                                    label=team
                                )

                                # Nummer i cirklen
                                for _, row in sub[mask].iterrows():
                                    ax.text(
                                        float(row["x"]), float(row["y"]), str(int(row["Throw-in #"])),
                                        ha="center", va="center",
                                        fontsize=7, color="white",
                                        zorder=4,
                                        path_effects=[pe.withStroke(linewidth=1.8, foreground="black")]
                                    )

                            # Legende (læg FCK først)
                            handles, labels = ax.get_legend_handles_labels()
                            if labels:
                                order = sorted(range(len(labels)), key=lambda i: 0 if labels[i] in TEAM_ALIASES else 1)
                                handles = [handles[i] for i in order]
                                labels = [labels[i] for i in order]
                                ax.legend(handles, labels,
                                          loc="upper center", bbox_to_anchor=(0.5, -0.05),
                                          ncol=3, frameon=True, title="Hold")

                        st.pyplot(fig, use_container_width=True, clear_figure=True)
                        st.caption("Circle size = Delay in seconds")
                        st.caption("Direction of play for both teams = Right")
                    except Exception as e:
                        st.warning(f"Kunne ikke tegne banen: {e}")

                with col2:
                    display_cols = [
                        "Period", "Ball out (mm:ss)", "Throw-in (mm:ss)",
                        "Delay (s)", "Team", "Side", "Third", "Zone",
                        "x", "y", "Game date", "Throw-in #", "is_FCK"
                    ]
                    show_cols = [c for c in display_cols if c in df_plot.columns]
                    st.dataframe(df_plot[show_cols], hide_index=True, height=360)

                    st.subheader("Gennemsnit pr. hold (kamp)")
                    if df_plot.empty:
                        st.info("Ingen kast i den aktuelle filtrering.")
                    else:
                        agg = df_plot.groupby("Team")["Delay (s)"].mean().reset_index()
                        agg["Delay (s)"] = pd.to_numeric(agg["Delay (s)"], errors="coerce").round(1)
                        # Fremhæv FCK i tabel (visuelt via kolonne)
                        agg["FCK"] = agg["Team"].apply(lambda t: "🦁" if t in TEAM_ALIASES else "")
                        agg = agg[["FCK", "Team", "Delay (s)"]].sort_values(["FCK","Delay (s)"], ascending=[False, True])
                        st.dataframe(agg, hide_index=True, height=200)
            else:
                st.info("Ingen indkast fundet i denne kamp.")
