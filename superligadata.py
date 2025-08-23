import re
from collections import defaultdict
from pathlib import Path
import pandas as pd
import streamlit as st
import xml.etree.ElementTree as ET

# --- Dropbox sync (folder -> zip) --------------------------------------------
import os, io, zipfile, requests

REMOTE_DROPBOX_FOLDER = os.getenv(
    "DROPBOX_FOLDER_URL",
    "https://www.dropbox.com/scl/fo/qm6y55m4o9u1y357vni7e/ADRY08n0Ugs9yzttqKge_kE?rlkey=n9l1rbo2y7cq4es6w3ykh64ct&st=bi4fdp6c&dl=0"
).replace("dl=0", "dl=1")  # force direct download

LOCAL_CACHE = Path("./data").resolve()

def _download_dropbox_folder_zip(folder_url: str, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    r = requests.get(folder_url, timeout=120)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        zf.extractall(out_dir)  # extracts a top-level folder created by Dropbox

def _find_rounds_base(root: Path) -> Path | None:
    """Return the path that directly contains R1/R2/... folders."""
    try:
        if root.exists():
            dirs = [d for d in root.iterdir() if d.is_dir()]
            if any(re.fullmatch(r"R\d+", d.name) for d in dirs):
                return root
            for sub in dirs:
                subdirs = [d for d in sub.iterdir() if d.is_dir()]
                if any(re.fullmatch(r"R\d+", d.name) for d in subdirs):
                    return sub
    except Exception:
        pass
    return None

# Bootstrap cache once if empty
if not LOCAL_CACHE.exists() or not any(LOCAL_CACHE.iterdir()):
    try:
        _download_dropbox_folder_zip(REMOTE_DROPBOX_FOLDER, LOCAL_CACHE)
    except Exception:
        pass

DEFAULT_BASE_FROM_CACHE = _find_rounds_base(LOCAL_CACHE)
# -----------------------------------------------------------------------------


# =========================
# Brand & tema (F.C. København)
# =========================
BRAND = {
    "primary": "#001E96",
    "white":   "#FFFFFF",
    "accent":  "#D00000",
    "bg":      "#001E96",
    "text":    "#0B1221",
    "muted":   "#001E96",
    "grey":    "#001E96",
}

LOGO_URL = (
    "https://www.dropbox.com/scl/fi/egr4olrw44a22nfptcbsb/FC_Copenhagen_logo.svg.png"
    "?rlkey=sk5my2fzqtzmbnj0zqo9vg0rf&st=g9ezcgzq&dl=0"
)
LOGO_URL = LOGO_URL.replace("www.dropbox.com", "dl.dropboxusercontent.com").replace("dl=0", "raw=1")

APP_TITLE = "F.C. Copenhagen analytics"
PAGE_ICON = LOGO_URL

TEAM_ALIASES = {
    "FC København", "F.C. København", "FC Copenhagen", "F.C. Copenhagen",
    "København", "Copenhagen"
}

st.set_page_config(page_title=APP_TITLE, page_icon=PAGE_ICON, layout="wide")

# === Module switcher (render før evt. st.stop) ===
with st.sidebar:
    st.markdown("### Modules")
    MODULES = [
        "Throw-ins",
        "Shots (Under development)",

    ]
    module = st.radio(" ", MODULES, index=0, key="module_switcher")
    st.divider()

# --- Hent logo som bytes (fix til iOS/Safari) --------------------------------
@st.cache_resource(show_spinner=False)
def fetch_logo_bytes(url: str) -> bytes | None:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; StreamlitLogoFetcher/1.0)"}
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        return r.content
    except Exception:
        return None
# -----------------------------------------------------------------------------


st.markdown(f"""
<style>
.stApp {{ background: linear-gradient(180deg, {BRAND["bg"]} 0%, #FFFFFF 100%); color: {BRAND["text"]}; }}
.fck-header {{ display:flex; align-items:center; gap:12px; padding:10px 14px; margin-bottom:8px;
  border-radius:14px; background: {BRAND["white"]}; border:1px solid {BRAND["grey"]}33; box-shadow: 0 4px 14px rgba(0,0,0,0.04); }}
.fck-header h1 {{ font-size: 1.25rem; line-height:1.2; margin:0; }}
.fck-kicker {{ color:{BRAND["muted"]}; font-weight:600; letter-spacing: .02em; text-transform:uppercase; font-size:.8rem; }}

section[data-testid="stSidebar"] .stHeading, .stSidebar h2, .stSidebar h3 {{ color: {BRAND["primary"]}; }}

[data-baseweb="button-group"] button, .stRadio [role="radiogroup"] > label {{ border-radius: 999px !important; }}
.stRadio label span {{
  padding: 4px 10px !important;
  border-radius:999px !important; border:1px solid {BRAND["grey"]}AA; font-size: 0.88rem;
}}
.stRadio label div[role="radio"][aria-checked="true"] + span {{ background: {BRAND["primary"]}; color: white; border-color:{BRAND["primary"]}; }}

[data-testid="stDataFrame"] thead th {{ background: {BRAND["primary"]} !important; color: white !important; }}

.stButton>button {{ border-radius: 12px; border: 1px solid {BRAND["primary"]}; background: {BRAND["primary"]}; color:white; }}
.stButton>button:hover {{ filter: brightness(0.95); }}

.badge {{ display:inline-block; padding:2px 8px; border-radius:999px; font-size:.75rem; font-weight:600;
  border:1px solid {BRAND["grey"]}; color:{BRAND["muted"]}; }}

/* Filter titles: bold + underline, BLACK */
.filter-title {{
  font-weight: 800; text-decoration: underline; color:{BRAND["text"]};
  margin: 0.2rem 0 0.35rem 0;
}}
.filter-block {{ margin-bottom: .5rem; }}
</style>
""", unsafe_allow_html=True)

# =========================
# Sidebar: Indstillinger (Uden base-path + tip)
# =========================
st.sidebar.subheader("Indstillinger")
if st.sidebar.button("🔄 Sync data from Dropbox"):
    try:
        _download_dropbox_folder_zip(REMOTE_DROPBOX_FOLDER, LOCAL_CACHE)
        st.success("Synkroniseret fra Dropbox.")
        st.rerun()
    except Exception as e:
        st.error(f"Sync fejlede: {e}")

# Ingen base-path input i UI. Vi finder automatisk base:
DATA_BASE = os.getenv("FCK_DATA_BASE") or (str(DEFAULT_BASE_FROM_CACHE) if DEFAULT_BASE_FROM_CACHE else "/Volumes/10eren-Analyse/[8] Data/Superliga Data 25/26")
_base = Path(DATA_BASE).expanduser()
if not _base.exists():
    st.error(
        "Data-mappe ikke tilgængelig. Brug 'Sync data from Dropbox' (anbefalet) "
        "eller sæt ENV variablen FCK_DATA_BASE til en mappe med R1/R2…"
    )
    st.stop()

# Header
header_cols = st.columns([0.2, 0.8])
with header_cols[0]:
    logo_bytes = fetch_logo_bytes(LOGO_URL)
    if logo_bytes:
        st.image(logo_bytes, use_container_width=True)
    else:
        try:
            st.image(LOGO_URL, use_container_width=True)
        except Exception:
            st.markdown("<div class='badge'>FCK</div>", unsafe_allow_html=True)
with header_cols[1]:
    ACTIVE_TITLE = f"{module}"
    st.markdown(f"""
    <div class="fck-header">
      <div class="fck-kicker"></div>
      <h1>{ACTIVE_TITLE}</h1>
    </div>
    """, unsafe_allow_html=True)

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

def is_f7_like_filename(path: Path) -> bool:
    up = path.stem.upper()
    return ("F7" in up or "SRML" in up or "MATCHRESULTS" in up)

def is_f70_filename(path: Path) -> bool:
    return "F70" in path.stem.upper()

def get_match_info_from_f24(f24_path: Path):
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
                 if f.is_file() and f.suffix.lower()==".xml" and is_f7_like_filename(f)]
    f70_files = [f for f in round_dir.iterdir()
                 if f.is_file() and f.suffix.lower()==".xml" and is_f70_filename(f)]

    f7_by_id  = {(extract_match_id(f.name)  or f.stem): f for f in f7_files}
    f70_by_id = {(extract_match_id(f.name) or f.stem): f for f in f70_files}

    rows = []
    for f24 in f24_files:
        mid = extract_match_id(f24.name) or f24.stem
        f7  = f7_by_id.get(mid)
        f70 = f70_by_id.get(mid)
        match_name, match_date = get_match_info_from_f24(f24)
        rows.append({
            "Date": match_date.strftime("%d-%m-%Y") if match_date else "",
            "Match": match_name,
            "F24 file": f24.name,
            "F7 file":  f7.name  if f7  else "(mangler)",
            "F70 file": f70.name if f70 else "(mangler)",
            "_sortdate": match_date
        })
    return rows

# =========================
# Throw-in analyse – parsing
# =========================
EVENT_TYPE_PASS = 1
EVENT_TYPE_BALL_OUT = 5
QUALIFIER_THROW_IN = 107

SHOT_TYPES = {13, 14, 15, 16}
def _is_pass(ev): return ev.get("type_id") == EVENT_TYPE_PASS
def _is_shot(ev): return ev.get("type_id") in SHOT_TYPES
def _is_goal(ev): return ev.get("type_id") == 16

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

def build_xg_map_from_f70(f70_path: Path):
    """Opta F70 xG: qualifier_id=321 -> map event_id -> xG."""
    xg_map = {}
    try:
        root = ET.parse(str(f70_path)).getroot()
        game = root.find(".//Game")
        if game is None:
            return xg_map
        for ev in game.findall("Event"):
            eid = ev.attrib.get("id")
            if not eid:
                continue
            xg = None
            for q in ev.findall("Q"):
                if q.attrib.get("qualifier_id") == "321":
                    try:
                        xg = float(q.attrib.get("value", "0"))
                    except Exception:
                        xg = None
                    break
            if xg is not None:
                xg_map[str(eid)] = xg
    except Exception:
        pass
    return xg_map

def in_box_opta(x, y, side="offensive"):
    if x is None or y is None:
        return False
    if side == "offensive":
        return (84.3 <= float(x) <= 100.0) and (20.4 <= float(y) <= 79.6)
    elif side == "defensive":
        return (0.0 <= float(x) <= 15.7) and (20.4 <= float(y) <= 79.6)
    return False

def _parse_game_events(game_elem, team_name_map=None, team_side_map=None):
    game_meta = {
        "game_id": game_elem.attrib.get("id", ""),
        "game_date": game_elem.attrib.get("game_date", ""),
    }
    events = []
    for ev in game_elem.findall("Event"):
        event_id = ev.attrib.get("id", "")
        type_id   = _safe_int(ev.attrib.get("type_id", -1), -1)
        period_id = _safe_int(ev.attrib.get("period_id", -1), -1)
        team_id   = ev.attrib.get("team_id", "")
        min_ = _safe_int(ev.attrib.get("min", 0), 0)
        sec_ = _safe_int(ev.attrib.get("sec", 0), 0)
        time_s = min_ * 60 + sec_

        x = _safe_float(ev.attrib.get("x"))
        y = _safe_float(ev.attrib.get("y"))

        qmap = {}; qset = set()
        for q in ev.findall("Q"):
            qid = _safe_int(q.attrib.get("qualifier_id", -1), -1)
            qset.add(qid)
            if "value" in q.attrib:
                qmap[qid] = q.attrib["value"]

        end_x = _safe_float(qmap.get(140))
        end_y = _safe_float(qmap.get(141))

        team_name = team_name_map.get(team_id, team_id) if team_name_map else team_id
        team_side = team_side_map.get(team_id) if team_side_map else None
        events.append({
            "event_id": event_id,
            "type_id": type_id, "period_id": period_id,
            "team_id": team_id, "team_name": team_name, "team_side": team_side,
            "min": min_, "sec": sec_, "time_s": time_s,
            "x": x, "y": y, "end_x": end_x, "end_y": end_y,
            "qualifiers": qset, "qmap": qmap,
            "game_date": game_meta["game_date"],
        })
    events.sort(key=lambda x: (x["period_id"], x["time_s"]))
    return game_meta, events

def _zone_from_x(x):
    if x is None: return "Unknown"
    if x <= 33.3333: return "First 1/3"
    elif x <= 66.6666: return "Second 1/3"
    else: return "Last 1/3"

def _is_fck(name: str) -> bool:
    if not name: return False
    return name in TEAM_ALIASES

def _compute_throwin_delays(events):
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

                end_x = nxt.get("end_x"); end_y = nxt.get("end_y")
                z_end = _zone_from_x(end_x)
                end_in_box = in_box_opta(end_x, end_y, side="offensive")

                rows.append({
                    "Period": period,
                    "Ball out (mm:ss)": f"{e['min']:02d}:{e['sec']:02d}",
                    "Throw-in (mm:ss)": f"{nxt['min']:02d}:{nxt['sec']:02d}",
                    "Delay (s)": round(delay, 1),
                    "Team": nxt["team_name"], "Side": nxt["team_side"] or "",
                    "x": nxt.get("x"), "y": nxt.get("y"),
                    "Zone": z, "Third": z,
                    "end_x": end_x, "end_y": end_y,
                    "End zone": z_end, "End third": z_end,
                    "Thrown into the box": end_in_box,  # renamed
                    "is_FCK": _is_fck(nxt["team_name"]),
                    "throwin_event_id": nxt.get("event_id", ""),
                    "throwin_team_id": nxt.get("team_id", ""),
                    "throwin_time_s": nxt.get("time_s", None),
                    "throwin_period": nxt.get("period_id", None),
                })
                break
            j += 1
    return rows

# --- Pasningskæde helpers -----------------------------------------------------
def _forward_chain(seq_events, start_idx, max_gap_s=10):
    start = seq_events[start_idx]
    team = start["team_id"]; period = start["period_id"]
    chain = [start_idx]
    cur = start_idx
    while cur + 1 < len(seq_events):
        nxt = seq_events[cur + 1]
        if nxt["period_id"] != period: break
        if nxt["team_id"]  != team:    break
        if (nxt["time_s"] - seq_events[cur]["time_s"]) > max_gap_s: break
        chain.append(cur + 1)
        cur += 1
    return chain

def _summarize_chain(seq_events, chain_idx_list):
    start = seq_events[chain_idx_list[0]]
    last  = seq_events[chain_idx_list[-1]]
    n_pass = sum(1 for i in chain_idx_list if _is_pass(seq_events[i]))
    n_evt  = len(chain_idx_list)
    dur    = max(0, last["time_s"] - start["time_s"])
    ends_shot = _is_shot(last)
    if _is_pass(last):
        ex, ey = last.get("end_x"), last.get("end_y")
    else:
        ex, ey = last.get("x"), last.get("y")
    return {
        "Seq events": n_evt,
        "Seq passes": n_pass,
        "Seq duration (s)": round(float(dur), 1),
        "Seq ends with shot": bool(ends_shot),
        "Seq last x": ex, "Seq last y": ey,
        "Seq last type": ("Shot" if ends_shot else "Pass"),
    }

def _enrich_throwins_with_sequences(
    events: list[dict],
    df_throw: pd.DataFrame,
    xg_map: dict[str, float] | None,
    max_gap_s: int = 10,
    shot_window_s: int = 30
) -> pd.DataFrame:
    if df_throw.empty:
        return df_throw

    seq_events = [e for e in events if _is_pass(e) or _is_shot(e)]

    by_eid_seq = {e.get("event_id",""): idx for idx, e in enumerate(seq_events) if e.get("event_id")}
    sig_map_seq = defaultdict(list)
    for idx, e in enumerate(seq_events):
        sig_map_seq[(e.get("period_id"), e.get("time_s"), e.get("team_id"))].append(idx)

    by_eid_all = {e.get("event_id",""): idx for idx, e in enumerate(events) if e.get("event_id")}
    sig_map_all = defaultdict(list)
    for idx, e in enumerate(events):
        sig_map_all[(e.get("period_id"), e.get("time_s"), e.get("team_id"))].append(idx)

    def _first_shot_within(all_events, start_idx_all, team_id, period_id, window_s):
        t0 = all_events[start_idx_all]["time_s"]
        k = start_idx_all
        while k < len(all_events):
            ev = all_events[k]
            if ev["period_id"] != period_id:
                break
            dt = ev["time_s"] - t0
            if dt > window_s:
                break
            if ev["team_id"] == team_id and _is_shot(ev):
                return ev, dt
            k += 1
        return None, None

    out_rows = []
    for r in df_throw.to_dict("records"):
        add = {
            "Seq events": None, "Seq passes": None, "Seq duration (s)": None,
            "Seq ends with shot": None, "Seq last x": None, "Seq last y": None, "Seq last type": None,
            "Shot in 30s": False, "Goal in 30s": False,
            "Shot time from TI (s)": None, "Shot x": None, "Shot y": None,
            "Shot xG (30s)": None, "Shot event id": None,
        }

        idx_seq = None
        eid = r.get("throwin_event_id", "")
        if eid and eid in by_eid_seq:
            idx_seq = by_eid_seq[eid]
        else:
            sig = (r.get("throwin_period"), r.get("throwin_time_s"), r.get("throwin_team_id"))
            cand = sig_map_seq.get(sig, [])
            if cand: idx_seq = cand[0]

        if idx_seq is not None and seq_events:
            chain = _forward_chain(seq_events, idx_seq, max_gap_s=max_gap_s)
            add.update(_summarize_chain(seq_events, chain))

        idx_all = None
        if eid and eid in by_eid_all:
            idx_all = by_eid_all[eid]
        else:
            sig = (r.get("throwin_period"), r.get("throwin_time_s"), r.get("throwin_team_id"))
            cand = sig_map_all.get(sig, [])
            if cand: idx_all = cand[0]

        if idx_all is not None:
            shot_ev, dt = _first_shot_within(events, idx_all, r.get("throwin_team_id"), r.get("throwin_period"), shot_window_s)
            if shot_ev is not None:
                add["Shot in 30s"] = True
                add["Goal in 30s"] = _is_goal(shot_ev)
                add["Shot time from TI (s)"] = round(float(dt), 1)
                add["Shot x"] = shot_ev.get("x"); add["Shot y"] = shot_ev.get("y")
                add["Shot event id"] = shot_ev.get("event_id")
                if xg_map:
                    add["Shot xG (30s)"] = float(xg_map.get(str(shot_ev.get("event_id","")), None)) if xg_map is not None else None

        out_rows.append({**r, **add})

    return pd.DataFrame(out_rows)

# --- Outlier / retention / versions ------------------------------------------
OUTLIER_THR = 40  # sekunder
BALL_RETENTION_THR_S = 7.0
SCHEMA_VER = 10
# -----------------------------------------------------------------------------

def _mark_outliers(df: pd.DataFrame, thr: float = OUTLIER_THR) -> pd.Series:
    d = pd.to_numeric(df.get("Delay (s)"), errors="coerce")
    return d > float(thr)

@st.cache_data(show_spinner=False)
def parse_throwin_delays_from_f24_cached(
    f24_str_path: str,
    f7_str_path: str | None,
    f70_str_path: str | None,
    cache_buster: int = SCHEMA_VER
):
    f24_path = Path(f24_str_path)
    f7_path = Path(f7_str_path) if f7_str_path else None
    f70_path = Path(f70_str_path) if f70_str_path else None

    name_map, side_map = {}, {}
    if f7_path and f7_path.exists():
        name_map, side_map = build_team_maps_from_f7(f7_path)

    xg_map = {}
    if f70_path and f70_path.exists():
        xg_map = build_xg_map_from_f70(f70_path)

    all_rows = []
    try:
        root = ET.parse(str(f24_path)).getroot()
    except Exception:
        return pd.DataFrame()

    for game in root.findall(".//Game"):
        game_meta, events = _parse_game_events(game, team_name_map=name_map, team_side_map=side_map)
        base_rows = _compute_throwin_delays(events)

        df_enriched = _enrich_throwins_with_sequences(
            events, pd.DataFrame(base_rows), xg_map=xg_map, max_gap_s=10, shot_window_s=30
        )

        df_enriched["Seq duration (s)"] = pd.to_numeric(df_enriched.get("Seq duration (s)"), errors="coerce")
        df_enriched["Ball retention"] = df_enriched["Seq duration (s)"].fillna(0) >= float(BALL_RETENTION_THR_S)

        for r in df_enriched.to_dict("records"):
            r["Game date"] = game_meta.get("game_date", "")
            all_rows.append(r)

    return pd.DataFrame(all_rows)

# =============================================================================
#                                  MODULES
# =============================================================================
def render_throwins_module():
    tab_superliga, tab_matches, tab_data, tab_compare = st.tabs(
        ["Throw in overview", "Matches", "Throw in Data", "Comparison"]
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

        # ---------- FILTERS ABOVE GRAPH ----------
        st.markdown("<div class='filter-block'><div class='filter-title'>Rounds</div></div>", unsafe_allow_html=True)
        sel_min, sel_max = st.slider(" ",
                                     min_value=min_r, max_value=max_r,
                                     value=(min_r, max_r), step=1, key="ov_rounds")

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1:
            st.markdown("<div class='filter-title'>Home/Away</div>", unsafe_allow_html=True)
            side_filter = st.radio(" ", ["All", "Home", "Away"], horizontal=False, key="superliga_side_filter")
        with c2:
            st.markdown("<div class='filter-title'>Third</div>", unsafe_allow_html=True)
            third_filter = st.radio("  ", ["All", "First 1/3", "Second 1/3", "Last 1/3"],
                                    horizontal=False, key="superliga_third_filter")
        with c3:
            st.markdown("<div class='filter-title'>Thrown into the box</div>", unsafe_allow_html=True)
            thrown_box_filter = st.radio("   ", ["All", "Yes", "No"], horizontal=False, key="superliga_thrownbox_filter")
        with c4:
            st.markdown("<div class='filter-title'>Ball retention (≥7s)</div>", unsafe_allow_html=True)
            retention_filter = st.radio("    ", ["All", "Retained", "Lost"], horizontal=False, key="superliga_retention_filter")
        with c5:
            st.markdown("<div class='filter-title'>Shot ≤30s</div>", unsafe_allow_html=True)
            shot30_filter = st.radio("     ", ["All", "Yes", "No"], horizontal=False, key="superliga_shot30_filter")
        with c6:
            st.markdown("<div class='filter-title'>Goal ≤30s</div>", unsafe_allow_html=True)
            goal30_filter = st.radio("      ", ["All", "Yes", "No"], horizontal=False, key="superliga_goal30_filter")
        # ----------------------------------------

        selected_rounds = {r for r in range(sel_min, sel_max + 1)}
        round_dirs = [p for p in round_dirs_all if _round_num(p) in selected_rounds]

        all_rows = []
        for round_dir in round_dirs:
            rows = collect_round_data(round_dir)
            if not rows:
                continue
            df_round = pd.DataFrame(rows)
            for _, r in df_round.iterrows():
                f24_path = round_dir / r["F24 file"]
                f7_path  = (round_dir / r["F7 file"])  if r["F7 file"]  != "(mangler)" else None
                f70_path = (round_dir / r["F70 file"]) if r["F70 file"] != "(mangler)" else None
                df_throw = parse_throwin_delays_from_f24_cached(str(f24_path), str(f7_path) if f7_path else None,
                                                                str(f70_path) if f70_path else None, SCHEMA_VER)
                if not df_throw.empty:
                    df_throw["Round"] = round_dir.name
                    df_throw["Match"] = r["Match"]
                    all_rows.append(df_throw)

        if not all_rows:
            st.info("Ingen indkast fundet i det valgte interval.")
            st.stop()

        season_df = pd.concat(all_rows, ignore_index=True)

        if "Thrown into the box" not in season_df.columns and "End in box" in season_df.columns:
            season_df["Thrown into the box"] = season_df["End in box"]

        for col, default in [
            ("Thrown into the box", False),
            ("end_x", None), ("end_y", None),
            ("End zone", None), ("End third", None),
            ("Seq events", None), ("Seq passes", None), ("Seq duration (s)", None),
            ("Seq ends with shot", None), ("Seq last type", None), ("Seq last x", None), ("Seq last y", None),
            ("Ball retention", False),
            ("Shot in 30s", False), ("Goal in 30s", False),
            ("Shot time from TI (s)", None), ("Shot x", None), ("Shot y", None), ("Shot xG (30s)", 0.0),
        ]:
            if col not in season_df.columns:
                season_df[col] = default

        if side_filter != "All":
            season_df = season_df[season_df["Side"] == side_filter]
        if third_filter != "All":
            season_df = season_df[season_df["Third"] == third_filter]
        if thrown_box_filter != "All":
            season_df = season_df[season_df["Thrown into the box"] == (thrown_box_filter == "Yes")]
        if retention_filter != "All":
            season_df = season_df[season_df["Ball retention"] == (retention_filter == "Retained")]
        if shot30_filter != "All":
            season_df = season_df[season_df["Shot in 30s"] == (shot30_filter == "Yes")]
        if goal30_filter != "All":
            season_df = season_df[season_df["Goal in 30s"] == (goal30_filter == "Yes")]

        if season_df.empty:
            st.info("Ingen indkast efter valgte filtre.")
            st.stop()

        season_df["Delay (s)"] = pd.to_numeric(season_df["Delay (s)"], errors="coerce")
        season_df["Shot xG (30s)"] = pd.to_numeric(season_df["Shot xG (30s)"], errors="coerce")
        season_df["is_outlier"] = _mark_outliers(season_df)
        season_df_used = season_df[~season_df["is_outlier"]].copy()

        g = season_df_used.groupby("Team", dropna=False)

        games = g["Match"].nunique().rename("Games")
        tot_throw = g.size().rename("Total throw-ins")
        avg_delay = g["Delay (s)"].mean().round(2).rename("Avg. delay (s)")
        lt7 = g.apply(lambda x: (pd.to_numeric(x["Delay (s)"], errors="coerce") < 7).sum()).rename("Throw-ins <7s")
        total_delay = g["Delay (s)"].sum().round(1).rename("Total delay (s)")

        thrown_cnt = g.apply(lambda x: x["Thrown into the box"].fillna(False).sum()).rename("Thrown into box")
        thrown_pct = ((thrown_cnt / tot_throw) * 100).round(1).rename("% thrown into box")
        thrown_per_game = (thrown_cnt / games).round(2).rename("Thrown into box per game")

        retained_cnt = g.apply(lambda x: x["Ball retention"].fillna(False).sum()).rename("Retained throw-ins")
        pct_retained = ((retained_cnt / tot_throw) * 100).round(1).rename("Retention %")
        retained_per_game = (retained_cnt / games).round(2).rename("Retained per game")

        shot30_cnt = g.apply(lambda x: x["Shot in 30s"].fillna(False).sum()).rename("TI shots ≤30s")
        shot30_pct = ((shot30_cnt / tot_throw) * 100).round(1).rename("% TI shots ≤30s")
        goal30_cnt = g.apply(lambda x: x["Goal in 30s"].fillna(False).sum()).rename("TI goals ≤30s")
        goal30_pct = ((goal30_cnt / tot_throw) * 100).round(1).rename("% TI goals ≤30s")
        xg30_sum   = g["Shot xG (30s)"].sum().round(2).rename("TI xG ≤30s")
        xg30_per_ti = (xg30_sum / tot_throw).round(3).rename("xG per TI ≤30s")
        xg30_per_game = (xg30_sum / games).round(2).rename("xG per game ≤30s")

        overview = pd.concat(
            [games, tot_throw, avg_delay, lt7, total_delay,
             thrown_cnt, thrown_pct, thrown_per_game,
             retained_cnt, pct_retained, retained_per_game,
             shot30_cnt, shot30_pct, goal30_cnt, goal30_pct, xg30_sum, xg30_per_ti, xg30_per_game],
            axis=1
        ).reset_index()
        overview["Throw-ins per game"] = (overview["Total throw-ins"] / overview["Games"]).round(2)
        overview["Delay per throw-in (s)"] = (overview["Total delay (s)"] / overview["Total throw-ins"]).round(2)

        import altair as alt
        metric = st.selectbox(
            "Choose metric",
            ["Avg. delay (s)", "Delay per throw-in (s)", "Throw-ins per game",
             "Total throw-ins", "Throw-ins <7s", "Total delay (s)",
             "Thrown into box", "% thrown into box", "Thrown into box per game",
             "Retained throw-ins", "Retention %", "Retained per game",
             "TI shots ≤30s", "% TI shots ≤30s", "TI goals ≤30s", "% TI goals ≤30s",
             "TI xG ≤30s", "xG per TI ≤30s", "xG per game ≤30s"]
        )
        overview_sorted = overview.sort_values([metric, "Team"], ascending=[False, True]).reset_index(drop=True)
        chart_df = pd.DataFrame({
            "Team": overview_sorted["Team"],
            "Value": pd.to_numeric(overview_sorted[metric], errors="coerce"),
        }).dropna()
        chart_df["is_FCK"] = chart_df["Team"].apply(lambda t: t in TEAM_ALIASES)
        team_order = overview_sorted["Team"].tolist()
        chart_h = max(300, len(chart_df) * 32)

        chart = (
            alt.Chart(chart_df, height=chart_h, width="container")
              .mark_bar()
              .encode(
                  y=alt.Y("Team:N", sort=team_order, title="Team"),
                  x=alt.X("Value:Q", title=metric),
                  color=alt.condition(alt.datum.is_FCK, alt.value(BRAND["primary"]), alt.value("#A1A1A1")),
                  tooltip=["Team", "Value"]
              )
              .configure_legend(disable=True)
        )
        st.altair_chart(chart, use_container_width=True)

        with st.expander("Raw indkast (alle kampe)"):
            raw_cols = [
                "Round", "Match", "Side", "Third", "Zone", "x", "y", "end_x", "end_y",
                "End zone", "End third", "Thrown into the box", "Ball retention",
                "Period", "Ball out (mm:ss)", "Throw-in (mm:ss)", "Delay (s)", "Team", "Game date",
                "is_outlier", "is_FCK",
                "Seq events", "Seq passes", "Seq duration (s)", "Seq ends with shot", "Seq last type", "Seq last x", "Seq last y",
                "Shot in 30s", "Goal in 30s", "Shot time from TI (s)", "Shot x", "Shot y", "Shot xG (30s)",
                "throwin_event_id", "throwin_team_id", "throwin_time_s", "throwin_period",
            ]
            raw_cols = [c for c in season_df.columns if c in raw_cols]
            st.dataframe(season_df[raw_cols], hide_index=True)

    # ---- Kampe ----
    with tab_matches:
        st.header("Matches")
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
        st.header("Throw-ins per match")
        rounds = list_round_dirs(DATA_BASE)
        if rounds:
            round_choice = st.selectbox("Choose round/s", rounds, format_func=lambda p: p.name)
            rows = collect_round_data(round_choice)
            if rows:
                matches_df = pd.DataFrame(rows)
                match_choice = st.selectbox("Choose game", matches_df["Match"])

                f24_file = matches_df.loc[matches_df["Match"] == match_choice, "F24 file"].values[0]
                f7_file  = matches_df.loc[matches_df["Match"] == match_choice, "F7 file"].values[0]
                f70_file = matches_df.loc[matches_df["Match"] == match_choice, "F70 file"].values[0]

                f24_path = round_choice / f24_file
                f7_path  = (round_choice / f7_file)  if f7_file  != "(mangler)" else None
                f70_path = (round_choice / f70_file) if f70_file != "(mangler)" else None

                df_throw = parse_throwin_delays_from_f24_cached(str(f24_path),
                                                                str(f7_path) if f7_path else None,
                                                                str(f70_path) if f70_path else None,
                                                                SCHEMA_VER)

                if "Thrown into the box" not in df_throw.columns and "End in box" in df_throw.columns:
                    df_throw["Thrown into the box"] = df_throw["End in box"]

                for col, default in [
                    ("Thrown into the box", False),
                    ("end_x", None), ("end_y", None),
                    ("End zone", None), ("End third", None),
                    ("Seq events", None), ("Seq passes", None), ("Seq duration (s)", None),
                    ("Seq ends with shot", None), ("Seq last type", None), ("Seq last x", None), ("Seq last y", None),
                    ("Ball retention", False),
                    ("Shot in 30s", False), ("Goal in 30s", False),
                    ("Shot time from TI (s)", None), ("Shot x", None), ("Shot y", None), ("Shot xG (30s)", 0.0),
                ]:
                    if col not in df_throw.columns:
                        df_throw[col] = default

                if not df_throw.empty:
                    def _to_seconds(mmss):
                        try:
                            m, s = str(mmss).split(":")
                            return int(m) * 60 + int(s)
                        except Exception:
                            return 10**9

                    df_throw["_sort"] = pd.to_numeric(df_throw["Period"], errors="coerce").fillna(0).astype(int) * 10_000 \
                                       + df_throw["Ball out (mm:ss)"].map(_to_seconds)
                    df_throw = df_throw.sort_values("_sort").drop(columns=["_sort"]).reset_index(drop=True)
                    df_throw["Throw-in #"] = range(1, len(df_throw)+1)
                    df_throw["is_FCK"] = df_throw["Team"].apply(lambda t: t in TEAM_ALIASES)
                    df_throw["is_outlier"] = _mark_outliers(df_throw, OUTLIER_THR)

                    # ---------- FILTERS ABOVE GRAPH ----------
                    c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(8)
                    with c1:
                        st.markdown("<div class='filter-title'>Home/Away</div>", unsafe_allow_html=True)
                        side_tog = st.radio(" ", ["All", "Home", "Away"], horizontal=False, key="data_side_filter")
                    with c2:
                        st.markdown("<div class='filter-title'>Period</div>", unsafe_allow_html=True)
                        period_tog = st.radio("  ", ["All", "1", "2"], horizontal=False, key="data_period_filter")
                    with c3:
                        st.markdown("<div class='filter-title'>Delay</div>", unsafe_allow_html=True)
                        delay_tog = st.radio("   ", ["All", "< 7s only"], horizontal=False, key="data_delay_filter")
                    with c4:
                        st.markdown("<div class='filter-title'>Third</div>", unsafe_allow_html=True)
                        third_tog = st.radio("    ", ["All", "First 1/3", "Second 1/3", "Last 1/3"],
                                             horizontal=False, key="data_third_filter")
                    with c5:
                        st.markdown("<div class='filter-title'>Thrown into the box</div>", unsafe_allow_html=True)
                        thrownbox_tog = st.radio("     ", ["All", "Yes", "No"],
                                                 horizontal=False, key="data_thrownbox_filter")
                    with c6:
                        st.markdown("<div class='filter-title'>Ball retention</div>", unsafe_allow_html=True)
                        retention_tog = st.radio("      ", ["All", "Retained (≥7s)", "Lost (<7s)"],
                                                 horizontal=False, key="data_retention_filter")
                    with c7:
                        st.markdown("<div class='filter-title'>Shot ≤30s</div>", unsafe_allow_html=True)
                        shot30_tog = st.radio("       ", ["All", "Yes", "No"], horizontal=False, key="data_shot30_filter")
                    with c8:
                        st.markdown("<div class='filter-title'>Goal ≤30s</div>", unsafe_allow_html=True)
                        goal30_tog = st.radio("        ", ["All", "Yes", "No"], horizontal=False, key="data_goal30_filter")
                    # ----------------------------------------

                    # Filtrering (plot ekskl. outliers)
                    df_plot = df_throw[~df_throw["is_outlier"]].copy()
                    if side_tog != "All":
                        df_plot = df_plot[df_plot["Side"] == side_tog]
                    if period_tog != "All":
                        df_plot = df_plot[pd.to_numeric(df_plot["Period"], errors="coerce") == int(period_tog)]
                    if delay_tog != "All":
                        df_plot = df_plot[pd.to_numeric(df_plot["Delay (s)"], errors="coerce") < 7]
                    if third_tog != "All":
                        df_plot = df_plot[df_plot["Third"] == third_tog]
                    if thrownbox_tog != "All":
                        df_plot = df_plot[df_plot["Thrown into the box"] == (thrownbox_tog == "Yes")]
                    if retention_tog != "All":
                        df_plot = df_plot[df_plot["Ball retention"] == retention_tog.startswith("Retained")]
                    if shot30_tog != "All":
                        df_plot = df_plot[df_plot["Shot in 30s"] == (shot30_tog == "Yes")]
                    if goal30_tog != "All":
                        df_plot = df_plot[df_plot["Goal in 30s"] == (goal30_tog == "Yes")]

                    # Tabel følger relevante filtre
                    df_table = df_throw.copy()
                    if thrownbox_tog != "All":
                        df_table = df_table[df_table["Thrown into the box"] == (thrownbox_tog == "Yes")]
                    if retention_tog != "All":
                        df_table = df_table[df_table["Ball retention"] == retention_tog.startswith("Retained")]
                    if shot30_tog != "All":
                        df_table = df_table[df_table["Shot in 30s"] == (shot30_tog == "Yes")]
                    if goal30_tog != "All":
                        df_table = df_table[df_table["Goal in 30s"] == (goal30_tog == "Yes")]

                    st.subheader(f"Throw ins – {match_choice}")

                    col1, col2 = st.columns([0.8, 1.9])
                    with col1:
                        try:
                            from mplsoccer import Pitch
                            import matplotlib.pyplot as plt
                            import matplotlib.patheffects as pe

                            pitch = Pitch(pitch_type="opta", line_zorder=2,
                                          pitch_color="white", line_color="black")
                            fig, ax = pitch.draw(figsize=(4.6, 3.1))
                            fig.set_dpi(160)  # valgfrit – gør figuren skarpere uden at bruge draw(dpi=…)
                            if df_plot.empty:
                                st.info("Ingen indkast matcher de valgte filtre.")
                            else:
                                def color_for_team(team):
                                    return BRAND["primary"] if team in TEAM_ALIASES else "#C8CDD9"

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

                                    for _, row in sub[mask].iterrows():
                                        ax.text(
                                            float(row["x"]), float(row["y"]), str(int(row["Throw-in #"])),
                                            ha="center", va="center",
                                            fontsize=7, color="white",
                                            zorder=4,
                                            path_effects=[pe.withStroke(linewidth=1.8, foreground="black")]
                                        )

                                handles, labels = ax.get_legend_handles_labels()
                                if labels:
                                    order = sorted(range(len(labels)), key=lambda i: 0 if labels[i] in TEAM_ALIASES else 1)
                                    handles = [handles[i] for i in order]
                                    labels = [labels[i] for i in order]
                                    ax.legend(handles, labels,
                                              loc="upper center", bbox_to_anchor=(0.5, -0.05),
                                              ncol=3, frameon=True, title="Hold")

                            st.pyplot(fig, use_container_width=False, clear_figure=True)
                            st.caption("Circle size = Delay in seconds • Direction of play for both teams = Right")
                        except Exception as e:
                            st.warning(f"Kunne ikke tegne banen: {e}")

                    with col2:
                        display_cols = [
                            "Period", "Ball out (mm:ss)", "Throw-in (mm:ss)",
                            "Delay (s)", "Team", "Side", "Third", "Zone",
                            "x", "y", "end_x", "end_y", "End zone", "End third",
                            "Thrown into the box", "Ball retention",
                            "Seq events", "Seq passes", "Seq duration (s)", "Seq ends with shot", "Seq last type",
                            "Shot in 30s", "Goal in 30s", "Shot time from TI (s)", "Shot x", "Shot y", "Shot xG (30s)",
                            "Game date", "Throw-in #", "is_outlier", "is_FCK",
                            "throwin_event_id", "throwin_team_id", "throwin_time_s", "throwin_period",
                        ]
                        show_cols = [c for c in display_cols if c in df_table.columns]
                        st.dataframe(df_table[show_cols], hide_index=True, height=380)

                        import altair as alt
                        st.subheader("xG (≤30s) per throw-in")
                        df_xg = df_throw.copy()
                        df_xg["Shot xG (30s)"] = pd.to_numeric(df_xg["Shot xG (30s)"], errors="coerce").fillna(0.0)
                        xg_chart = (
                            alt.Chart(df_xg)
                              .mark_bar()
                              .encode(
                                  x=alt.X("Throw-in #:O", title="Throw-in #"),
                                  y=alt.Y("Shot xG (30s):Q", title="xG ≤30s"),
                                  color=alt.condition("datum['Shot in 30s']",
                                                      alt.value(BRAND["primary"]),
                                                      alt.value("#DADDE5")),
                                  tooltip=["Throw-in #","Shot in 30s","Goal in 30s","Shot time from TI (s)","Shot xG (30s)"]
                              )
                              .properties(height=220)
                        )
                        st.altair_chart(xg_chart, use_container_width=True)

    # ---- Comparison ----
    with tab_compare:
        st.header("Comparison")

        round_dirs_all = list_round_dirs(DATA_BASE)
        if not round_dirs_all:
            st.info("Ingen runder fundet.")
            st.stop()

        def _round_num2(p: Path):
            m = re.search(r"R(\d+)$", p.name)
            return int(m.group(1)) if m else None

        round_nums2 = [n for n in (_round_num2(p) for p in round_dirs_all) if n is not None]
        min_r2, max_r2 = min(round_nums2), max(round_nums2)

        st.markdown("<div class='filter-block'><div class='filter-title'>Rounds (comparison)</div></div>", unsafe_allow_html=True)
        sel_min2, sel_max2 = st.slider("   ",
                                       min_value=min_r2, max_value=max_r2,
                                       value=(min_r2, max_r2), step=1, key="cmp_rounds")

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("<div class='filter-title'>Home/Away</div>", unsafe_allow_html=True)
            side_filter2 = st.radio("    ", ["All", "Home", "Away"], horizontal=False, key="cmp_side")
        with c2:
            st.markdown("<div class='filter-title'>Third</div>", unsafe_allow_html=True)
            third_filter2 = st.radio("     ", ["All", "First 1/3", "Second 1/3", "Last 1/3"],
                                     horizontal=False, key="cmp_third")
        with c3:
            st.write("")

        selected_rounds2 = {r for r in range(sel_min2, sel_max2 + 1)}
        round_dirs2 = [p for p in round_dirs_all if _round_num2(p) in selected_rounds2]

        all_rows2 = []
        for round_dir in round_dirs2:
            rows = collect_round_data(round_dir)
            if not rows:
                continue
            df_round = pd.DataFrame(rows)
            for _, r in df_round.iterrows():
                f24_path = round_dir / r["F24 file"]
                f7_path  = (round_dir / r["F7 file"])  if r["F7 file"]  != "(mangler)" else None
                f70_path = (round_dir / r["F70 file"]) if r["F70 file"] != "(mangler)" else None
                df_throw = parse_throwin_delays_from_f24_cached(str(f24_path), str(f7_path) if f7_path else None,
                                                                str(f70_path) if f70_path else None, SCHEMA_VER)
                if not df_throw.empty:
                    df_throw["Round"] = round_dir.name
                    df_throw["Match"] = r["Match"]
                    all_rows2.append(df_throw)

        if not all_rows2:
            st.info("Ingen indkast i det valgte interval.")
            st.stop()

        season_cmp = pd.concat(all_rows2, ignore_index=True)

        if "Thrown into the box" not in season_cmp.columns and "End in box" in season_cmp.columns:
            season_cmp["Thrown into the box"] = season_cmp["End in box"]

        for col, default in [("Thrown into the box", False), ("Ball retention", False),
                             ("Shot in 30s", False), ("Goal in 30s", False), ("Shot xG (30s)", 0.0)]:
            if col not in season_cmp.columns:
                season_cmp[col] = default

        if side_filter2 != "All":
            season_cmp = season_cmp[season_cmp["Side"] == side_filter2]
        if third_filter2 != "All":
            season_cmp = season_cmp[season_cmp["Third"] == third_filter2]

        if season_cmp.empty:
            st.info("Ingen data efter filtre.")
            st.stop()

        season_cmp["Delay (s)"] = pd.to_numeric(season_cmp["Delay (s)"], errors="coerce")
        season_cmp["Shot xG (30s)"] = pd.to_numeric(season_cmp["Shot xG (30s)"], errors="coerce")
        season_cmp["is_outlier"] = _mark_outliers(season_cmp)
        season_cmp_used = season_cmp[~season_cmp["is_outlier"]].copy()

        gcmp = season_cmp_used.groupby("Team", dropna=False)
        games_cmp = gcmp["Match"].nunique().rename("Games")
        tot_throw_cmp = gcmp.size().rename("Total throw-ins")
        avg_delay_cmp = gcmp["Delay (s)"].mean().round(2).rename("Avg. delay (s)")
        lt7_cmp = gcmp.apply(lambda x: (pd.to_numeric(x["Delay (s)"], errors="coerce") < 7).sum()).rename("Throw-ins <7s")
        total_delay_cmp = gcmp["Delay (s)"].sum().round(1).rename("Total delay (s)")

        thrown_cnt_cmp = gcmp.apply(lambda x: x["Thrown into the box"].fillna(False).sum()).rename("Thrown into box")
        thrown_pct_cmp = ((thrown_cnt_cmp / tot_throw_cmp) * 100).round(1).rename("% thrown into box")
        thrown_per_game_cmp = (thrown_cnt_cmp / games_cmp).round(2).rename("Thrown into box per game")

        retained_cnt_cmp = gcmp.apply(lambda x: x["Ball retention"].fillna(False).sum()).rename("Retained throw-ins")
        pct_retained_cmp = ((retained_cnt_cmp / tot_throw_cmp) * 100).round(1).rename("Retention %")
        retained_per_game_cmp = (retained_cnt_cmp / games_cmp).round(2).rename("Retained per game")

        shot30_cnt_cmp = gcmp.apply(lambda x: x["Shot in 30s"].fillna(False).sum()).rename("TI shots ≤30s")
        shot30_pct_cmp = ((shot30_cnt_cmp / tot_throw_cmp) * 100).round(1).rename("% TI shots ≤30s")
        goal30_cnt_cmp = gcmp.apply(lambda x: x["Goal in 30s"].fillna(False).sum()).rename("TI goals ≤30s")
        goal30_pct_cmp = ((goal30_cnt_cmp / tot_throw_cmp) * 100).round(1).rename("% TI goals ≤30s")
        xg30_sum_cmp   = gcmp["Shot xG (30s)"].sum().round(2).rename("TI xG ≤30s")
        xg30_per_ti_cmp = (xg30_sum_cmp / tot_throw_cmp).round(3).rename("xG per TI ≤30s")
        xg30_per_game_cmp = (xg30_sum_cmp / games_cmp).round(2).rename("xG per game ≤30s")

        overview_cmp = pd.concat(
            [games_cmp, tot_throw_cmp, avg_delay_cmp, lt7_cmp, total_delay_cmp,
             thrown_cnt_cmp, thrown_pct_cmp, thrown_per_game_cmp,
             retained_cnt_cmp, pct_retained_cmp, retained_per_game_cmp,
             shot30_cnt_cmp, shot30_pct_cmp, goal30_cnt_cmp, goal30_pct_cmp, xg30_sum_cmp, xg30_per_ti_cmp, xg30_per_game_cmp],
            axis=1
        ).reset_index()
        overview_cmp["Throw-ins per game"] = (overview_cmp["Total throw-ins"] / overview_cmp["Games"]).round(2)
        overview_cmp["Delay per throw-in (s)"] = (overview_cmp["Total delay (s)"] / overview_cmp["Total throw-ins"]).round(2)
        overview_cmp["is_FCK"] = overview_cmp["Team"].apply(lambda t: t in TEAM_ALIASES)

        import altair as alt
        metric_options = [
            "Avg. delay (s)",
            "Delay per throw-in (s)",
            "Throw-ins per game",
            "Total throw-ins",
            "Throw-ins <7s",
            "Total delay (s)",
            "Games",
            "Thrown into box", "% thrown into box", "Thrown into box per game",
            "Retained throw-ins", "Retention %", "Retained per game",
            "TI shots ≤30s", "% TI shots ≤30s", "TI goals ≤30s", "% TI goals ≤30s",
            "TI xG ≤30s", "xG per TI ≤30s", "xG per game ≤30s",
        ]

        d1, d2, d3 = st.columns(3)
        with d1:
            st.markdown("<div class='filter-title'>X-axis</div>", unsafe_allow_html=True)
            x_metric = st.selectbox("        ", metric_options, index=0, key="cmp_x")
        with d2:
            st.markdown("<div class='filter-title'>Y-axis</div>", unsafe_allow_html=True)
            y_metric = st.selectbox("         ", metric_options, index=2, key="cmp_y")
        with d3:
            st.markdown("<div class='filter-title'>Point size</div>", unsafe_allow_html=True)
            size_hint = st.slider("          ", 20, 400, 120, step=10, key="cmp_size")

        plot_df = overview_cmp.copy()
        plot_df["x"] = pd.to_numeric(plot_df[x_metric], errors="coerce")
        plot_df["y"] = pd.to_numeric(plot_df[y_metric], errors="coerce")
        plot_df = plot_df.dropna(subset=["x", "y"])
        plot_df["Size"] = (plot_df["Total throw-ins"].fillna(0) + 1) / (plot_df["Total throw-ins"].fillna(0).max() + 1) * size_hint + 20

        scatter = (
            alt.Chart(plot_df, height=520, width="container")
              .mark_circle()
              .encode(
                  x=alt.X("x:Q", title=x_metric),
                  y=alt.Y("y:Q", title=y_metric),
                  size=alt.Size("Size:Q", legend=None),
                  color=alt.condition(alt.datum.is_FCK, alt.value(BRAND["primary"]), alt.value("#A1A1A1")),
                  tooltip=[
                      alt.Tooltip("Team:N"),
                      alt.Tooltip(f"{x_metric}:Q"),
                      alt.Tooltip(f"{y_metric}:Q"),
                      alt.Tooltip("Total throw-ins:Q"),
                      alt.Tooltip("Games:Q"),
                  ]
              )
        )
        text = (
            alt.Chart(plot_df)
              .mark_text(dy=-8)
              .encode(
                  x="x:Q",
                  y="y:Q",
                  text="Team:N",
                  color=alt.condition(alt.datum.is_FCK, alt.value(BRAND["primary"]), alt.value("#4D4D4D")),
              )
        )
        st.altair_chart(scatter + text, use_container_width=True)
        st.caption("Bemærk: Beregninger i denne fane ekskluderer outliers (delay > 40s), men rå data kan naturligvis indeholde dem.")


# =========================
# Router: vis aktivt modul
# =========================
if module.startswith("Throw-ins"):
    render_throwins_module()
elif module.startswith("Corners"):
    st.subheader("Corners")
    st.info("Kommer snart – strukturen er klar, vi kan koble F24/F70-hændelser for hjørnespark på samme måde.")
elif module.startswith("Goal kicks"):
    st.subheader("Goal kicks")
    st.info("Kommer snart – klar til at blive udfyldt.")
elif module.startswith("Pressing"):
    st.subheader("Pressing")
    st.info("Kommer snart – klar til at blive udfyldt.")
