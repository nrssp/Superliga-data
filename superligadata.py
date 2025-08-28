import re
from collections import defaultdict
from pathlib import Path
import pandas as pd
import streamlit as st
import xml.etree.ElementTree as ET
from contextlib import contextmanager
import unicodedata
import base64

# --- Dropbox sync (folder -> zip) --------------------------------------------
import os, io, zipfile, requests

REMOTE_DROPBOX_FOLDER = os.getenv(
    "DROPBOX_FOLDER_URL",
    "https://www.dropbox.com/scl/fo/qm6y55m4o9u1y357vni7e/ADRY08n0Ugs9yzttqKge_kE?rlkey=n9l1rbo2y7cq4es6w3ykh64ct&st=bi4fdp6c&dl=0"
).replace("dl=0", "dl=1")  # force direct download

LOCAL_CACHE = Path("./data").resolve()

LOGO_DROPBOX_FOLDER = "https://www.dropbox.com/scl/fo/s869q2kb2jwn3zvsgts88/ACMNFC5T62ltbtIKbk4zsFg?dl=1"
LOGO_CACHE = (LOCAL_CACHE / "logos").resolve()

def _download_dropbox_folder_zip(folder_url: str, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    r = requests.get(folder_url, timeout=120)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        zf.extractall(out_dir)

@st.cache_resource(show_spinner=False)
def _ensure_logos_synced(folder_url: str = LOGO_DROPBOX_FOLDER, out_dir: Path = LOGO_CACHE) -> Path | None:
    try:
        if not out_dir.exists() or not any(out_dir.iterdir()):
            _download_dropbox_folder_zip(folder_url, out_dir)
        return out_dir
    except Exception:
        return None

# Bootstrap cache once if empty
if not LOCAL_CACHE.exists() or not any(LOCAL_CACHE.iterdir()):
    try:
        _download_dropbox_folder_zip(REMOTE_DROPBOX_FOLDER, LOCAL_CACHE)
    except Exception:
        pass

def _find_rounds_base(root: Path) -> Path | None:
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

DEFAULT_BASE_FROM_CACHE = _find_rounds_base(LOCAL_CACHE)

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

# Skal være første Streamlit-kald i appen
st.set_page_config(page_title=APP_TITLE, page_icon=PAGE_ICON, layout="wide")

# === Player photos (Dropbox sync) ============================================
PLAYER_PHOTO_URLS = "https://www.dropbox.com/scl/fo/suiphvo7fv8ibegjomubm/AOakYVyH_ri3WF3OD0A9UJo?rlkey=xeulwe99avd9m1vzip0jw9r0z&st=4zkyp7so&dl=1"

PLAYER_PHOTO_CACHE = (LOCAL_CACHE / "player_photos").resolve()
PLAYER_PHOTO_ROOT: Path | None = None  # lazy init


@st.cache_resource(show_spinner=False)
def _ensure_player_photos_synced(urls_csv: str, out_dir: Path = PLAYER_PHOTO_CACHE) -> Path | None:
    """Downloader hver Dropbox-mappe (via delbart link) som zip og pakker ud i out_dir."""
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        if any(out_dir.rglob("*.*")):
            return out_dir
        urls = [u.strip().replace("dl=0", "dl=1") for u in urls_csv.split(",") if u.strip()]
        if not urls:
            return None
        for u in urls:
            _download_dropbox_folder_zip(u, out_dir)
        return out_dir
    except zipfile.BadZipFile:
        st.warning("Spillerfoto-zip var korrupt. Tjek at linket er et delbart mappe-link med dl=1.")
        return None
    except Exception:
        return None

def _get_player_photo_root() -> Path | None:
    global PLAYER_PHOTO_ROOT
    if PLAYER_PHOTO_ROOT is not None:
        return PLAYER_PHOTO_ROOT
    root = _ensure_player_photos_synced(PLAYER_PHOTO_URLS)
    if root is None:
        env_fallback = os.getenv("PLAYER_PHOTO_ROOT", "")
        root = Path(env_fallback).expanduser() if env_fallback else None
    PLAYER_PHOTO_ROOT = root
    return PLAYER_PHOTO_ROOT

# map team-navne -> mappenavne (slugs) i "Player photos"
_TEAM_TO_SLUG = {
    "agf": "agf", "agf aarhus": "agf",
    "brøndby if": "brondby-if", "brondby if": "brondby-if", "brøndby": "brondby-if", "brondby": "brondby-if",
    "fc københavn": "f-c-kobenhavn", "f.c. københavn": "f-c-kobenhavn", "fc copenhagen": "f-c-kobenhavn",
    "københavn": "f-c-kobenhavn", "copenhagen": "f-c-kobenhavn", "fck": "f-c-kobenhavn",
    "fc fredericia": "fc-fredericia",
    "fc midtjylland": "fc-midtjylland",
    "fc nordsjælland": "fc-nordsjaelland", "fc nordsjaelland": "fc-nordsjaelland",
    "ob": "ob", "odense boldklub": "ob",
    "randers fc": "randers-fc", "randers": "randers-fc",
    "silkeborg if": "silkeborg-if", "silkeborg": "silkeborg-if",
    "sønderjyske fodbold": "sonderjyske-fodbold", "sonderjyske fodbold": "sonderjyske-fodbold", "sønderjyske": "sonderjyske-fodbold",
    "viborg ff": "viborg-ff", "viborg": "viborg-ff",
    "vejle boldklub": "vejle-boldklub", "vejle bk": "vejle-boldklub", "vejle": "vejle-boldklub",
}

def _norm(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = (s.replace("Æ", "Ae").replace("Ø", "O").replace("Å", "Aa")
           .replace("æ", "ae").replace("ø", "o").replace("å", "aa"))
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
    s = re.sub(r"\s+", " ", s)
    return s

def _team_to_slug(team: str) -> str | None:
    key = _norm(team)
    return _TEAM_TO_SLUG.get(key, key.replace(" ", "-") if key else None)

@st.cache_resource(show_spinner=False)
def build_player_photo_index(root: Path | None = None) -> dict[tuple[str, str], str]:
    """
    Returnerer {(team_slug, norm_player_name): dataurl}.
    Læser .png/.jpg/.jpeg/.webp i hver klub-mappe under PLAYER_PHOTO_ROOT.
    """
    if root is None:
        root = _get_player_photo_root()  # trigger sync
    idx: dict[tuple[str, str], str] = {}
    if not root or not Path(root).exists():
        return idx
    for team_dir in Path(root).iterdir():
        if not team_dir.is_dir():
            continue
        team_slug = team_dir.name
        for p in team_dir.rglob("*"):
            if p.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
                continue
            norm_name = _norm(p.stem)
            try:
                b = p.read_bytes()
                if p.suffix.lower() == ".png":
                    mime = "image/png"
                elif p.suffix.lower() in (".jpg", ".jpeg"):
                    mime = "image/jpeg"
                else:
                    mime = "image/webp"
                dataurl = f"data:{mime};base64,{base64.b64encode(b).decode('ascii')}"
                idx[(team_slug, norm_name)] = dataurl
            except Exception:
                pass
    return idx

def get_player_photo_dataurl(team: str, player: str, index: dict[tuple[str,str], str]) -> str | None:
    slug = _team_to_slug(team)
    if not slug:
        return None
    key = (slug, _norm(player))
    if key in index:
        return index[key]
    norm_p = _norm(player)  # fallback: navnematch på tværs af klubber
    for (sl, np), val in index.items():
        if np == norm_p:
            return val
    return None

@st.cache_resource(show_spinner=False)
def _build_logo_dataurl_map(logo_dir: Path) -> dict[str, str]:
    """Byg map over logoer (robust: original, normaliseret, slug)."""
    m = {}
    if not logo_dir or not logo_dir.exists():
        return m
    for p in logo_dir.rglob("*.png"):
        try:
            b64 = base64.b64encode(p.read_bytes()).decode("ascii")
            dataurl = f"data:image/png;base64,{b64}"
            stem = p.stem
            m[stem] = dataurl
            m[_norm(stem)] = dataurl
            slug = _team_to_slug(stem)
            if slug:
                m[slug] = dataurl
        except Exception:
            pass
    return m

def _logo_lookup(logo_map: dict[str,str], team: str) -> str | None:
    """Find logo-dataurl robust: eksakt, normaliseret, eller slug-match."""
    if not logo_map or not team:
        return None
    if team in logo_map:
        return logo_map[team]
    team_norm = _norm(team)
    team_slug = _team_to_slug(team) or team_norm.replace(" ", "-")
    best = None
    for k, v in logo_map.items():
        if k == team:
            return v
        if _norm(k) == team_norm:
            best = best or v
            continue
        slug_k = _team_to_slug(k) or _norm(k).replace(" ", "-")
        if slug_k == team_slug:
            best = best or v
    return best

TEAM_ALIASES = {
    "FC København", "F.C. København", "FC Copenhagen", "F.C. Copenhagen",
    "København", "Copenhagen"
}

# === Module switcher ===
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

# =========================
# Global CSS (kort + ens højde)
# =========================
st.markdown(f"""
<style>
/* ========== App base / brand ========== */
.stApp {{ 
  background: linear-gradient(180deg, {BRAND["bg"]} 0%, #FFFFFF 100%); 
  color: {BRAND["text"]}; 
}}
/* Head / header bar */
.fck-header {{ 
  display:flex; align-items:center; gap:12px; 
  padding:10px 14px; margin-bottom:8px;
  border-radius:14px; background:{BRAND["white"]}; 
  border:1px solid {BRAND["grey"]}33; 
  box-shadow:0 4px 14px rgba(0,0,0,0.04); 
}}
.fck-header h1 {{ font-size:1.25rem; line-height:1.2; margin:0; }}
.fck-kicker {{ 
  color:{BRAND["muted"]}; font-weight:600; letter-spacing:.02em; 
  text-transform:uppercase; font-size:.8rem; 
}}

/* ========== Sidebar ========== */
section[data-testid="stSidebar"] .stHeading, 
.stSidebar h2, .stSidebar h3 {{ color:{BRAND["primary"]}; }}

/* ========== Form controls / radios ========== */
[data-baseweb="button-group"] button, 
.stRadio [role="radiogroup"] > label {{ border-radius:999px!important; }}
.stRadio label span {{ 
  padding:2px 8px!important; line-height:1.25!important; 
  border-radius:999px!important; border:1px solid {BRAND["grey"]}33; 
  font-size:.88rem; 
}}
.stRadio label div[role="radio"][aria-checked="true"]+span {{ 
  background:{BRAND["primary"]}; color:#fff; border-color:{BRAND["primary"]}; 
}}

.stButton>button {{ 
  border-radius:12px; border:1px solid {BRAND["primary"]}; 
  background:{BRAND["primary"]}; color:#fff; 
}}
.stButton>button:hover {{ filter:brightness(.95); }}

/* Badges */
.badge {{ 
  display:inline-block; padding:2px 8px; border-radius:999px; 
  font-size:.75rem; font-weight:600;
  border:1px solid {BRAND["grey"]}; color:{BRAND["muted"]}; 
}}

/* ========== DataFrame / tables ========== */
[data-testid="stDataFrame"] thead th {{ 
  background:{BRAND["primary"]}!important; color:#fff!important; 
}}
[data-testid="stDataFrame"] tbody td {{ font-size:.92rem; }}

/* ========== Layout / equal heights ========== */
/* Gør kolonner og deres børn til flex, så kort strækker sig */
[data-testid="stHorizontalBlock"],
[data-testid="stVerticalBlock"] {{ 
  display:flex!important; align-items:stretch!important; 
}}
[data-testid="stHorizontalBlock"] [data-testid="column"],
[data-testid="stHorizontalBlock"] [data-testid="column"]>div {{ 
  display:flex!important; flex-direction:column!important; 
  align-items:stretch!important; 
}}
/* Standard kort-min-højde for ens højde */
.equal-height {{ 
  display:flex; flex-direction:column; 
  min-height:180px; height:auto; 
}}
@media (max-width:1100px) {{
  .equal-height {{ min-height:unset; }}
}}

/* ========== Filter cards (ikke-collapsible) ========== */
.filter-card {{
  padding:8px 12px; margin-bottom:10px; 
  border-radius:12px; background:#fff;
  border:1px solid {BRAND["primary"]}33; 
  box-shadow:0 2px 6px rgba(0,0,0,0.04);
}}
.filter-title {{
  font-weight:700; font-size:.9rem; margin-bottom:6px; 
  color:{BRAND["text"]};
}}

/* ========== Top 3 cards ========== */
.top3-wrap {{ display:flex; gap:12px; margin:6px 0 14px; }}
.top3-card {{
  flex:1 1 0; display:flex; align-items:center; gap:10px;
  padding:12px; border-radius:14px;
  background:{BRAND["white"]}; border:1px solid {BRAND["grey"]}33;
  box-shadow:0 4px 14px rgba(0,0,0,.04);
  min-height:160px;
}}
.top3-rank {{ font-weight:900; font-size:1.15rem; color:{BRAND["primary"]}; width:32px; text-align:center; }}
.top3-img > img {{
  width:80px; height:120px; border-radius:12px; object-fit:cover; background:#fff;
  border:1px solid {BRAND["grey"]}33;
}}
.top3-meta {{ display:flex; flex-direction:column; line-height:1.25; }}
.top3-name {{ font-weight:800; }}
.top3-team {{ font-size:.9rem; opacity:.8; }}
.top3-value {{ margin-left:auto; font-weight:800; }}
@media (max-width:1000px) {{
  .top3-wrap {{ flex-direction:column; }}
}}

/* ========== Spillerikoner grid/cards ========== */
.player-grid {{ 
  display:grid; grid-template-columns:repeat(auto-fill, minmax(170px, 1fr)); 
  gap:14px; 
}}
.player-card {{
  display:flex; flex-direction:column; align-items:center; gap:8px;
  padding:12px; border-radius:14px; background:#fff;
  border:1px solid {BRAND["primary"]}33; 
  box-shadow:0 4px 14px rgba(0,0,0,0.04);
}}
.player-img {{ 
  width:92px; height:92px; border-radius:16px; object-fit:cover; 
  background:#fff; border:1px solid #e6e8ef; 
}}
.player-initials {{
  width:92px; height:92px; border-radius:16px; display:flex; 
  align-items:center; justify-content:center;
  font-weight:900; font-size:28px; color:{BRAND["primary"]}; 
  background:#EEF2FF; border:1px solid #e6e8ef;
}}
.player-name {{ font-weight:800; text-align:center; line-height:1.1; }}
.player-team {{ font-size:.85rem; opacity:.75; text-align:center; }}
.player-meta {{ font-size:.8rem; opacity:.85; }}

/* ========== Tuning af expanders (hvis de forekommer andre steder) ========== */
[data-testid="stExpander"] {{ 
  background:rgba(0,0,0,0.06); border-radius:12px!important; margin-bottom:10px; 
}}
[data-testid="stExpander"]>details>summary {{ 
  background:transparent!important; padding:8px 12px!important; 
  border-bottom:none!important; outline:none!important; 
}}
[data-testid="stExpander"] summary svg, 
[data-testid="stExpander"] summary::-webkit-details-marker {{ display:none!important; }}
[data-testid="stExpander"] .st-expanderHeader p {{ 
  margin:0; font-weight:800; text-decoration:underline; color:{BRAND["text"]}; 
}}
[data-testid="stExpander"] .st-expanderContent {{ 
  padding:8px 12px 12px!important; overflow:visible!important; 
}}
</style>
""", unsafe_allow_html=True)



# “Filter card” helper (ikke-collapsible, men med kort-baggrund)
@contextmanager
def filter_card(title: str):
    st.markdown(
        f"""
        <div class="filter-card">
          <div class="filter-title">{title}</div>
        """,
        unsafe_allow_html=True
    )
    yield
    st.markdown("</div>", unsafe_allow_html=True)


# =========================
# Sidebar: Indstillinger
# =========================
st.sidebar.subheader("Indstillinger")
if st.sidebar.button("🔄 Sync data from Dropbox"):
    try:
        _download_dropbox_folder_zip(REMOTE_DROPBOX_FOLDER, LOCAL_CACHE)
        st.success("Synkroniseret fra Dropbox.")
        st.rerun()
    except Exception as e:
        st.error(f"Sync fejlede: {e}")

if st.sidebar.button("🔄 Sync player photos"):
    try:
        st.cache_resource.clear()  # ryd cache så vi henter igen
        _ensure_player_photos_synced(PLAYER_PHOTO_URLS)
        st.success("Spillerfotos synkroniseret.")
        st.rerun()
    except Exception as e:
        st.error(f"Sync af spillerfotos fejlede: {e}")

DATA_BASE = os.getenv("FCK_DATA_BASE") or (str(DEFAULT_BASE_FROM_CACHE) if DEFAULT_BASE_FROM_CACHE else "/Volumes/10eren-Analyse/[8] Data/Superliga Data 25/26")
_base = Path(DATA_BASE).expanduser()
if not _base.exists():
    st.error("Data-mappe ikke tilgængelig. Brug 'Sync data from Dropbox' eller sæt FCK_DATA_BASE.")
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

def build_player_map_from_f7(f7_path: Path) -> dict[str, str]:
    """
    Map: player_id (uID; også uden 'p' prefix) -> spillerens navn.
    """
    out = {}
    try:
        root = ET.parse(str(f7_path)).getroot()
        for team in root.findall(".//Team"):
            for p in team.findall("Player"):
                pid = (p.attrib.get("uID") or p.attrib.get("uid") or "").strip()
                person = p.find("PersonName")
                first = (person.findtext("First") or "").strip() if person is not None else ""
                known = (person.findtext("Known") or "").strip() if person is not None else ""
                last  = (person.findtext("Last")  or person.findtext("FamilyName") or "").strip() if person is not None else ""
                name = known if known else (" ".join(x for x in [first, last] if x).strip() or first or last or "")
                if not name:
                    name = "Unknown"
                if pid:
                    out[pid] = name
                    if len(pid) > 1 and pid[1:].isdigit():
                        out[pid[1:]] = name
    except Exception:
        pass
    return out

def build_xg_map_from_f70(f70_path: Path):
    """Opta F70 xG (qualifier_id=321) -> event_id -> xG."""
    xg_map: dict[str, float] = {}
    try:
        if not f70_path or not Path(f70_path).exists():
            return xg_map
        root = ET.parse(str(f70_path)).getroot()
        game = root.find(".//Game")
        if game is None:
            return xg_map
        for ev in game.findall("Event"):
            eid = ev.attrib.get("id")
            if not eid:
                continue
            for q in ev.findall("Q"):
                if q.attrib.get("qualifier_id") == "321":
                    try:
                        xg_map[str(eid)] = float(q.attrib.get("value", "0"))
                    except Exception:
                        pass
                    break
    except Exception:
        pass
    return xg_map

# --- Pitch dims + distance helper --------------------------------------------
PITCH_LENGTH_M = 105.0
PITCH_WIDTH_M  = 68.0

def _distance_m(x1, y1, x2, y2, length=PITCH_LENGTH_M, width=PITCH_WIDTH_M):
    """Euclidisk afstand (meter) mellem to Opta-koordinater (0..100)."""
    try:
        if None in (x1, y1, x2, y2):
            return None
        dx_m = (float(x2) - float(x1)) / 100.0 * float(length)
        dy_m = (float(y2) - float(y1)) / 100.0 * float(width)
        return round((dx_m**2 + dy_m**2) ** 0.5, 2)
    except Exception:
        return None
# -----------------------------------------------------------------------------


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
        player_id = ev.attrib.get("player_id", "")
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
            "player_id": player_id,
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

def _compute_throwin_delays(events, player_name_map=None):
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

                # distance i meter
                dist_m = _distance_m(nxt.get("x"), nxt.get("y"), end_x, end_y)

                taker_id = nxt.get("player_id", "")
                taker = player_name_map.get(taker_id, taker_id) if player_name_map else taker_id
                if not taker:
                    taker = "Unknown"

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
                    "Thrown into the box": end_in_box,
                    "Distance (m)": dist_m,
                    "is_FCK": _is_fck(nxt["team_name"]),
                    "throwin_event_id": nxt.get("event_id", ""),
                    "throwin_team_id": nxt.get("team_id", ""),
                    "throwin_time_s": nxt.get("time_s", None),
                    "throwin_period": nxt.get("period_id", None),
                    "Taker id": taker_id,
                    "Taker": taker,
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
OUTLIER_THR = 40
BALL_RETENTION_THR_S = 7.0
SCHEMA_VER = 12  # cache-bust
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
    player_map = {}
    if f7_path and f7_path.exists():
        name_map, side_map = build_team_maps_from_f7(f7_path)
        player_map = build_player_map_from_f7(f7_path)

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
        base_rows = _compute_throwin_delays(events, player_name_map=player_map)

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
    # NY: Tilføj “Spillerikoner”-fane
    tab_superliga, tab_Comparison, tab_individuals, tab_icons, tab_data, tab_matches = st.tabs(
        ["Throw in overview", "Comparison", "Individuals", "Spillerikoner", "Throw in Data", "Matches"]
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
        with filter_card("Rounds"):
            sel_min, sel_max = st.slider(" ",
                                         min_value=min_r, max_value=max_r,
                                         value=(min_r, max_r), step=1, key="ov_rounds")

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1:
            with filter_card("Home/Away"):
                side_filter = st.radio(" ", ["All", "Home", "Away"], horizontal=False, key="superliga_side_filter")
        with c2:
            with filter_card("Third"):
                third_filter = st.radio("  ", ["All", "First 1/3", "Second 1/3", "Last 1/3"],
                                        horizontal=False, key="superliga_third_filter")
        with c3:
            with filter_card("Thrown into the box"):
                thrown_box_filter = st.radio("   ", ["All", "Yes", "No"], horizontal=False, key="superliga_thrownbox_filter")
        with c4:
            with filter_card("Ball retention (≥7s)"):
                retention_filter = st.radio("    ", ["All", "Retained", "Lost"], horizontal=False, key="superliga_retention_filter")
        with c5:
            with filter_card("Shot ≤30s"):
                shot30_filter = st.radio("     ", ["All", "Yes", "No"], horizontal=False, key="superliga_shot30_filter")
        with c6:
            with filter_card("Goal ≤30s"):
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
            ("Distance (m)", None),
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

        shot30_cnt = g.apply(lambda x: x["Shot in 30s"].fillna(False).sum()).rename("Shots ≤30s")
        shot30_pct = ((shot30_cnt / tot_throw) * 100).round(1).rename("% Shots ≤30s")
        goal30_cnt = g.apply(lambda x: x["Goal in 30s"].fillna(False).sum()).rename("Goals ≤30s")
        goal30_pct = ((goal30_cnt / tot_throw) * 100).round(1).rename("% Goals ≤30s")
        xg30_sum   = g["Shot xG (30s)"].sum().round(2).rename("xG ≤30s")
        xg30_per_ti = (xg30_sum / tot_throw).round(3).rename("xG per ≤30s")
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
             "Shots ≤30s", "% Shots ≤30s", "Goals ≤30s", "% Goals ≤30s",
             "xG ≤30s", "xG per ≤30s", "xG per game ≤30s"]
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
                "Distance (m)",
                "Period", "Ball out (mm:ss)", "Throw-in (mm:ss)", "Delay (s)", "Team", "Game date",
                "is_outlier", "is_FCK",
                "Seq events", "Seq passes", "Seq duration (s)", "Seq ends with shot", "Seq last type", "Seq last x", "Seq last y",
                "Shot in 30s", "Goal in 30s", "Shot time from TI (s)", "Shot x", "Shot y", "Shot xG (30s)",
                "throwin_event_id", "throwin_team_id", "throwin_time_s", "throwin_period",
            ]
            raw_cols = [c for c in season_df.columns if c in raw_cols]
            st.dataframe(season_df[raw_cols], hide_index=True)

         # ---- Comparison ----
    with tab_Comparison:
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

        with filter_card("Rounds (comparison)"):
            sel_min2, sel_max2 = st.slider("   ",
                                           min_value=min_r2, max_value=max_r2,
                                           value=(min_r2, max_r2), step=1, key="cmp_rounds")

        c1, c2 = st.columns(2)
        with c1:
            with filter_card("Home/Away"):
                side_filter2 = st.radio("    ", ["All", "Home", "Away"], horizontal=False, key="cmp_side")
        with c2:
            with filter_card("Third"):
                third_filter2 = st.radio("     ", ["All", "First 1/3", "Second 1/3", "Last 1/3"],
                                         horizontal=False, key="cmp_third")

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
                df_throw = parse_throwin_delays_from_f24_cached(
                    str(f24_path),
                    str(f7_path) if f7_path else None,
                    str(f70_path) if f70_path else None,
                    SCHEMA_VER
                )
                if not df_throw.empty:
                    df_throw["Round"] = round_dir.name
                    df_throw["Match"] = r["Match"]
                    all_rows2.append(df_throw)

        if not all_rows2:
            st.info("Ingen indkast i det valgte interval.")
            st.stop()

        season_cmp = pd.concat(all_rows2, ignore_index=True)

        # Sikr kolonner
        if "Thrown into the box" not in season_cmp.columns and "End in box" in season_cmp.columns:
            season_cmp["Thrown into the box"] = season_cmp["End in box"]
        for col, default in [
            ("Thrown into the box", False), ("Ball retention", False),
            ("Shot in 30s", False), ("Goal in 30s", False),
            ("Shot xG (30s)", 0.0), ("Distance (m)", None)
        ]:
            if col not in season_cmp.columns:
                season_cmp[col] = default

        # Filtre
        if side_filter2 != "All":
            season_cmp = season_cmp[season_cmp["Side"] == side_filter2]
        if third_filter2 != "All":
            season_cmp = season_cmp[season_cmp["Third"] == third_filter2]

        if season_cmp.empty:
            st.info("Ingen data efter filtre.")
            st.stop()

        # Rens tal + outliers
        season_cmp["Delay (s)"] = pd.to_numeric(season_cmp["Delay (s)"], errors="coerce")
        season_cmp["Shot xG (30s)"] = pd.to_numeric(season_cmp["Shot xG (30s)"], errors="coerce")
        season_cmp["is_outlier"] = _mark_outliers(season_cmp)
        season_cmp_used = season_cmp[~season_cmp["is_outlier"]].copy()

        # Aggreger pr. hold
        gcmp = season_cmp_used.groupby("Team", dropna=False)
        games_cmp = gcmp["Match"].nunique().rename("Games")
        tot_throw_cmp = gcmp.size().rename("Total throw-ins")
        avg_delay_cmp = gcmp["Delay (s)"].mean().rename("Avg. delay (s)")
        lt7_cmp = gcmp.apply(lambda x: (pd.to_numeric(x["Delay (s)"], errors="coerce") < 7).sum()).rename("Throw-ins <7s")
        total_delay_cmp = gcmp["Delay (s)"].sum().rename("Total delay (s)")

        thrown_cnt_cmp = gcmp.apply(lambda x: x["Thrown into the box"].fillna(False).sum()).rename("Thrown into box")
        thrown_pct_cmp = ((thrown_cnt_cmp / tot_throw_cmp) * 100).rename("% thrown into box")
        thrown_per_game_cmp = (thrown_cnt_cmp / games_cmp).rename("Thrown into box per game")

        retained_cnt_cmp = gcmp.apply(lambda x: x["Ball retention"].fillna(False).sum()).rename("Retained throw-ins")
        pct_retained_cmp = ((retained_cnt_cmp / tot_throw_cmp) * 100).rename("Retention %")
        retained_per_game_cmp = (retained_cnt_cmp / games_cmp).rename("Retained per game")

        shot30_cnt_cmp = gcmp.apply(lambda x: x["Shot in 30s"].fillna(False).sum()).rename("TI shots ≤30s")
        shot30_pct_cmp = ((shot30_cnt_cmp / tot_throw_cmp) * 100).rename("% TI shots ≤30s")
        goal30_cnt_cmp = gcmp.apply(lambda x: x["Goal in 30s"].fillna(False).sum()).rename("TI goals ≤30s")
        goal30_pct_cmp = ((goal30_cnt_cmp / tot_throw_cmp) * 100).rename("% TI goals ≤30s")
        xg30_sum_cmp   = gcmp["Shot xG (30s)"].sum().rename("TI xG ≤30s")
        xg30_per_ti_cmp = (xg30_sum_cmp / tot_throw_cmp).rename("xG per TI ≤30s")
        xg30_per_game_cmp = (xg30_sum_cmp / games_cmp).rename("xG per game ≤30s")

        overview_cmp = pd.concat(
            [games_cmp, tot_throw_cmp, avg_delay_cmp, lt7_cmp, total_delay_cmp,
             thrown_cnt_cmp, thrown_pct_cmp, thrown_per_game_cmp,
             retained_cnt_cmp, pct_retained_cmp, retained_per_game_cmp,
             shot30_cnt_cmp, shot30_pct_cmp, goal30_cnt_cmp, goal30_pct_cmp,
             xg30_sum_cmp, xg30_per_ti_cmp, xg30_per_game_cmp],
            axis=1
        ).reset_index()

        # Afledte kolonner
        overview_cmp["Throw-ins per game"] = (overview_cmp["Total throw-ins"] / overview_cmp["Games"])
        overview_cmp["Delay per throw-in (s)"] = (overview_cmp["Total delay (s)"] / overview_cmp["Total throw-ins"])

        # Fjern dublette kolonner og tving til numerisk
        overview_cmp = overview_cmp.loc[:, ~overview_cmp.columns.duplicated()].copy()
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
        for col in metric_options:
            if col in overview_cmp.columns:
                overview_cmp[col] = pd.to_numeric(overview_cmp[col], errors="coerce")

        overview_cmp["is_FCK"] = overview_cmp["Team"].apply(lambda t: t in TEAM_ALIASES)

        # ==== GitHub RAW logos via Altair mark_image ====
        import altair as alt
        from urllib.parse import quote

        # Base to your GitHub repo (raw)
        GH_RAW_BASE = "https://raw.githubusercontent.com/nrssp/Superliga-data/main/Logos"

        # Alias (hvis Opta-navn != filnavn)
        TEAM_LOGO_ALIAS = {
            "FC Copenhagen": "FC København",
            "F.C. København": "FC København",
            "København": "FC København",
            "Brondby": "Brøndby IF",
            "Nordsjaelland": "FC Nordsjælland",
            "OB": "Odense Boldklub",
            "Sonderjyske": "SønderjyskE",
            "Lyngby": "Lyngby BK",
            "Randers": "Randers FC",
            "Vejle": "Vejle BK",
            "Viborg": "Viborg FF",
            "AGF": "AGF Aarhus",
            # tilføj flere hvis du støder på afvigelser
        }

        def to_logo_name(team: str) -> str:
            # Brug alias hvis vi har et; ellers team-strengen som er
            return TEAM_LOGO_ALIAS.get(team, team)

        def gh_logo_url(team: str) -> str | None:
            """
            Bygger en URL til GitHub raw:
              https://raw.githubusercontent.com/nrssp/Superliga-data/main/Logos/<filnavn>.png
            Husk at URL-encode (mellemrum, æ/ø/å osv.).
            """
            if not isinstance(team, str) or not team:
                return None
            fname = f"{to_logo_name(team)}.png"
            return f"{GH_RAW_BASE}/{quote(fname, safe='')}"

        # ---- Select axes ----
        d1, d2 = st.columns(2)
        with d1:
            with filter_card("X-axis"):
                x_metric = st.selectbox("        ", metric_options, index=0, key="cmp_x")
        with d2:
            with filter_card("Y-axis"):
                y_metric = st.selectbox("         ", metric_options, index=2, key="cmp_y")

        # Byg plot-datasæt
        plot_df = overview_cmp.loc[:, ~overview_cmp.columns.duplicated()].copy()
        plot_df = plot_df[plot_df["Games"] > 0]
        plot_df["x"] = pd.to_numeric(plot_df[x_metric], errors="coerce")
        plot_df["y"] = pd.to_numeric(plot_df[y_metric], errors="coerce")
        plot_df["logo_url"] = plot_df["Team"].map(gh_logo_url)
        plot_df = plot_df.dropna(subset=["x", "y", "logo_url"])

        if plot_df.empty:
            st.info("Ingen gyldige datapunkter for de valgte akser/filtre.")
            st.stop()

        # Median-linjer
        avg_x = float(plot_df["x"].mean())
        avg_y = float(plot_df["y"].mean())
        rule_x = alt.Chart(pd.DataFrame({"x": [avg_x]})).mark_rule(strokeDash=[4,2], color="#888").encode(x="x:Q")
        rule_y = alt.Chart(pd.DataFrame({"y": [avg_y]})).mark_rule(strokeDash=[4,2], color="#888").encode(y="y:Q")

        # Logoer som punkter
        chart = (
            alt.Chart(plot_df, height=520, width="container")
              .mark_image(width=20, height=20)
              .encode(
                  x=alt.X("x:Q", title=x_metric),
                  y=alt.Y("y:Q", title=y_metric),
                  url="logo_url:N",
                  tooltip=["Team", x_metric, y_metric, "Total throw-ins", "Games"],
              )
        )

        st.altair_chart(chart + rule_x + rule_y, use_container_width=True)

        # Lille tabel under grafen
        _show_cols = ["Team", x_metric, y_metric, "Total throw-ins", "Games"]
        _show_cols = [c for c in _show_cols if c in plot_df.columns]
        st.dataframe(
            plot_df[_show_cols].sort_values(by=[x_metric, y_metric], ascending=False).head(30),
            hide_index=True
        )



    # ---- Individuals (spillere) ----

    with tab_individuals:
        st.header("Player throw-in information")

        round_dirs_all = list_round_dirs(DATA_BASE)
        if not round_dirs_all:
            st.stop()

        def _round_num_ind(p: Path):
            m = re.search(r"R(\d+)$", p.name)
            return int(m.group(1)) if m else None

        round_nums_ind = [n for n in (_round_num_ind(p) for p in round_dirs_all) if n is not None]
        min_ri, max_ri = min(round_nums_ind), max(round_nums_ind)

        with filter_card("Rounds"):
            sel_min_i, sel_max_i = st.slider("     ",
                                             min_value=min_ri, max_value=max_ri,
                                             value=(min_ri, max_ri), step=1, key="ind_rounds")

        # Filters
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1:
            with filter_card("Home/Away"):
                side_i = st.radio(" ", ["All", "Home", "Away"], horizontal=False, key="ind_side")
        with c2:
            with filter_card("Third"):
                third_i = st.radio("  ", ["All", "First 1/3", "Second 1/3", "Last 1/3"], horizontal=False, key="ind_third")
        with c3:
            with filter_card("Thrown into the box"):
                box_i = st.radio("   ", ["All", "Yes", "No"], horizontal=False, key="ind_box")
        with c4:
            with filter_card("Ball retention (≥7s)"):
                ret_i = st.radio("    ", ["All", "Retained", "Lost"], horizontal=False, key="ind_ret")
        with c5:
            with filter_card("Shot ≤30s"):
                shot_i = st.radio("     ", ["All", "Yes", "No"], horizontal=False, key="ind_shot")
        with c6:
            with filter_card("Goal ≤30s"):
                goal_i = st.radio("      ", ["All", "Yes", "No"], horizontal=False, key="ind_goal")

        selected_rounds_i = {r for r in range(sel_min_i, sel_max_i + 1)}
        round_dirs_i = [p for p in round_dirs_all if _round_num_ind(p) in selected_rounds_i]

        all_rows_i = []
        for round_dir in round_dirs_i:
            rows = collect_round_data(round_dir)
            if not rows:
                continue
            df_round = pd.DataFrame(rows)
            for _, r in df_round.iterrows():
                f24_path = round_dir / r["F24 file"]
                f7_path  = (round_dir / r["F7 file"])  if r["F7 file"]  != "(mangler)" else None
                f70_path = (round_dir / r["F70 file"]) if r["F70 file"] != "(mangler)" else None
                df_throw = parse_throwin_delays_from_f24_cached(
                    str(f24_path), str(f7_path) if f7_path else None, str(f70_path) if f70_path else None, SCHEMA_VER
                )
                if not df_throw.empty:
                    df_throw["Round"] = round_dir.name
                    df_throw["Match"] = r["Match"]
                    all_rows_i.append(df_throw)

        if not all_rows_i:
            st.info("Ingen indkast i det valgte interval.")
            st.stop()

        indiv_df = pd.concat(all_rows_i, ignore_index=True)

        if "Thrown into the box" not in indiv_df.columns and "End in box" in indiv_df.columns:
            indiv_df["Thrown into the box"] = indiv_df["End in box"]
        if "Taker" not in indiv_df.columns:
            indiv_df["Taker"] = indiv_df.get("Taker id", "").fillna("").replace({"": "Unknown"})
        if "Distance (m)" not in indiv_df.columns:
            indiv_df["Distance (m)"] = None

        if side_i != "All":
            indiv_df = indiv_df[indiv_df["Side"] == side_i]
        if third_i != "All":
            indiv_df = indiv_df[indiv_df["Third"] == third_i]
        if box_i != "All":
            indiv_df = indiv_df[indiv_df["Thrown into the box"] == (box_i == "Yes")]
        if ret_i != "All":
            indiv_df = indiv_df[indiv_df["Ball retention"] == (ret_i == "Retained")]
        if shot_i != "All":
            indiv_df = indiv_df[indiv_df["Shot in 30s"] == (shot_i == "Yes")]
        if goal_i != "All":
            indiv_df = indiv_df[indiv_df["Goal in 30s"] == (goal_i == "Yes")]

        if indiv_df.empty:
            st.info("Ingen indkast efter valgte filtre.")
            st.stop()

        indiv_df["Delay (s)"] = pd.to_numeric(indiv_df["Delay (s)"], errors="coerce")
        indiv_df["Shot xG (30s)"] = pd.to_numeric(indiv_df["Shot xG (30s)"], errors="coerce").fillna(0.0)
        indiv_df["Distance (m)"] = pd.to_numeric(indiv_df["Distance (m)"], errors="coerce")
        indiv_df["is_outlier"] = _mark_outliers(indiv_df)
        indiv_used = indiv_df[~indiv_df["is_outlier"]].copy()
        indiv_used["is_FCK"] = indiv_used["Team"].apply(lambda t: t in TEAM_ALIASES)

        gpi = indiv_used.groupby(["Team", "Taker"], dropna=False)
        games_pi = gpi["Match"].nunique().rename("Games")
        tot_ti_pi = gpi.size().rename("Total throw-ins")
        avg_delay_pi = gpi["Delay (s)"].mean().round(2).rename("Avg. delay (s)")
        lt7_pi = gpi.apply(lambda x: (pd.to_numeric(x["Delay (s)"], errors="coerce") < 7).sum()).rename("Throw-ins <7s")
        total_delay_pi = gpi["Delay (s)"].sum().round(1).rename("Total delay (s)")

        box_cnt_pi = gpi.apply(lambda x: x["Thrown into the box"].fillna(False).sum()).rename("Thrown into box")
        box_pct_pi = ((box_cnt_pi / tot_ti_pi) * 100).round(1).rename("% thrown into box")

        ret_cnt_pi = gpi.apply(lambda x: x["Ball retention"].fillna(False).sum()).rename("Retained throw-ins")
        ret_pct_pi = ((ret_cnt_pi / tot_ti_pi) * 100).round(1).rename("Retention %")

        shot_cnt_pi = gpi.apply(lambda x: x["Shot in 30s"].fillna(False).sum()).rename("Shots ≤30s")
        shot_pct_pi = ((shot_cnt_pi / tot_ti_pi) * 100).round(1).rename("% Shots ≤30s")
        goal_cnt_pi = gpi.apply(lambda x: x["Goal in 30s"].fillna(False).sum()).rename("Goals ≤30s")
        goal_pct_pi = ((goal_cnt_pi / tot_ti_pi) * 100).round(1).rename("% Goals ≤30s")
        xg_sum_pi   = gpi["Shot xG (30s)"].sum().round(2).rename("xG ≤30s")
        xg_per_ti_pi = (xg_sum_pi / tot_ti_pi).round(3).rename("xG per ≤30s")

        # Distance-metrics
        avg_dist_pi  = gpi["Distance (m)"].mean().round(2).rename("Avg. distance (m)")
        max_dist_pi  = gpi["Distance (m)"].max().round(2).rename("Max distance (m)")
        sum_dist_pi  = gpi["Distance (m)"].sum().round(1).rename("Total distance (m)")

        overview_pi = pd.concat(
            [games_pi, tot_ti_pi, avg_delay_pi, lt7_pi, total_delay_pi,
             box_cnt_pi, box_pct_pi,
             ret_cnt_pi, ret_pct_pi,
             shot_cnt_pi, shot_pct_pi, goal_cnt_pi, goal_pct_pi,
             xg_sum_pi, xg_per_ti_pi,
             avg_dist_pi, max_dist_pi, sum_dist_pi],
            axis=1
        ).reset_index().rename(columns={"Team": "Team", "Taker": "Player"})
        # Label bevares som "Player — Team" for unikhed, men vi viser kun Player via labelExpr
        overview_pi["Label"] = overview_pi["Player"].fillna("Unknown") + " — " + overview_pi["Team"].fillna("Unknown")
        overview_pi["is_FCK"] = overview_pi["Team"].apply(lambda t: t in TEAM_ALIASES)

        # --- NYT: slider for minimum antal kast pr. spiller ---
        max_ti = int(overview_pi["Total throw-ins"].max()) if not overview_pi.empty else 1
        default_min = 3 if max_ti >= 3 else max_ti
        min_ti = st.slider(
            "Minimum throw-ins",
            min_value=1,
            max_value=max_ti,
            value=default_min,
            step=1,
            key="ind_min_ti"
        )
        overview_pi = overview_pi[overview_pi["Total throw-ins"] >= min_ti]

        # Hvis intet matcher, vis besked og stop resten af fanen
        if overview_pi.empty:
            st.info(f"No players with at least {min_ti} throw-ins after filters.")
            st.stop()

        import altair as alt
        metric_ind = st.selectbox(
            "Choose metric",
            ["Total throw-ins", "Avg. delay (s)", "Throw-ins <7s", "Total delay (s)",
             "Thrown into box", "% thrown into box",
             "Retained throw-ins", "Retention %",
             "Shots ≤30s", "% Shots ≤30s", "Goals ≤30s", "% Goals ≤30s",
             "xG ≤30s", "xG per ≤30s", "Games",
             "Avg. distance (m)", "Max distance (m)", "Total distance (m)"],
            index=0
        )

        # Sortér efter valgt metric (faldende) – bruges både til Top 3 og bar-chart
        overview_pi_sorted = overview_pi.sort_values(
            [metric_ind, "Player", "Team"],
            ascending=[False, True, True]
        ).reset_index(drop=True)

        # --- TOP 3 KORT (følger filtre + valgt metric) -------------------------------
        # Byg indeks for logos (fallback) og spillerfotos
        _logo_dir = _ensure_logos_synced()
        _logo_map = _build_logo_dataurl_map(_logo_dir) if _logo_dir else {}
        _photo_index = build_player_photo_index()

        def _fmt_value(v):
            try:
                f = float(v)
                return f"{f:.0f}" if abs(f - round(f)) < 1e-9 else f"{f:.2f}"
            except Exception:
                return str(v)

        top3_df = overview_pi_sorted.head(3).copy()
        if not top3_df.empty:
            st.markdown("#### Top 3")
            cols = st.columns(len(top3_df))
            for i, ((_, row), col) in enumerate(zip(top3_df.iterrows(), cols), start=1):
                player = row.get("Player", "Unknown")
                team   = row.get("Team", "—")
                value  = _fmt_value(row.get(metric_ind))

                st.markdown("""
<style>
.top3-card { margin-bottom: 0; }
</style>
""", unsafe_allow_html=True)


                # → først prøv spillerfoto, ellers klublogo (robust lookup)
                img = get_player_photo_dataurl(team, player, _photo_index) or _logo_lookup(_logo_map, team)

                with col:
                    st.markdown(
                        f"""
                        <div class="top3-card">
                          <div class="top3-rank">#{i}</div>
                          <div class="top3-img">{f'<img src="{img}"/>' if img else ''}</div>
                          <div class="top3-meta">
                            <div class="top3-name">{player}</div>
                            <div class="top3-team">{team}</div>
                          </div>
                          <div class="top3-value">{value}</div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    
        # ---------------------------------------------------------------------------    

        # Bar-chart (bevarer din eksisterende logik)
        chart_df_pi = pd.DataFrame({
            "Label": overview_pi_sorted["Label"],
            "Value": pd.to_numeric(overview_pi_sorted[metric_ind], errors="coerce"),
            "is_FCK": overview_pi_sorted["is_FCK"]
        }).dropna(subset=["Value"])
        taker_order = overview_pi_sorted["Label"].tolist()
        chart_h_pi = max(320, len(chart_df_pi) * 28)

        chart_pi = (
            alt.Chart(chart_df_pi, height=chart_h_pi, width="container")
              .mark_bar()
              .encode(
                  y=alt.Y(
                      "Label:N",
                      sort=taker_order,
                      title="Player",
                      axis=alt.Axis(labelExpr="split(datum.label, ' — ')[0]")
                  ),
                  x=alt.X("Value:Q", title=metric_ind),
                  color=alt.condition(alt.datum.is_FCK, alt.value(BRAND["primary"]), alt.value("#A1A1A1")),
                  tooltip=["Label", "Value"]
              )
              .configure_legend(disable=True)
        )
        st.altair_chart(chart_pi, use_container_width=True)

        with st.expander("Players – full table"):
            show_cols_pi = ["Player", "Team", "Games", "Total throw-ins", "Avg. delay (s)", "Throw-ins <7s",
                            "Thrown into box", "% thrown into box",
                            "Retained throw-ins", "Retention %",
                            "Shots ≤30s", "% Shots ≤30s", "Goals ≤30s", "% Goals ≤30s",
                            "xG ≤30s", "xG per ≤30s",
                            "Avg. distance (m)", "Max distance (m)", "Total distance (m)",
                            "Total delay (s)"]
            show_cols_pi = [c for c in show_cols_pi if c in overview_pi_sorted.columns]
            st.dataframe(overview_pi_sorted[show_cols_pi], hide_index=True)

        # ---- NY: Spillerikoner ---------------------------------------------------
    with tab_icons:
        st.header("Spillerikoner")

        # 1) Hent data (samme approach som Individuals-tab)
        round_dirs_all = list_round_dirs(DATA_BASE)
        if not round_dirs_all:
            st.info("Ingen runder fundet.")
            st.stop()

        all_rows_icons = []
        for round_dir in round_dirs_all:
            rows = collect_round_data(round_dir)
            if not rows:
                continue
            df_round = pd.DataFrame(rows)
            for _, r in df_round.iterrows():
                f24_path = round_dir / r["F24 file"]
                f7_path  = (round_dir / r["F7 file"])  if r["F7 file"]  != "(mangler)" else None
                f70_path = (round_dir / r["F70 file"]) if r["F70 file"] != "(mangler)" else None
                df_throw = parse_throwin_delays_from_f24_cached(
                    str(f24_path), str(f7_path) if f7_path else None, str(f70_path) if f70_path else None, SCHEMA_VER
                )
                if not df_throw.empty:
                    all_rows_icons.append(df_throw)

        if not all_rows_icons:
            st.info("Ingen indkast fundet.")
            st.stop()

        icons_df = pd.concat(all_rows_icons, ignore_index=True)

        # Sikr kolonner
        if "Taker" not in icons_df.columns:
            icons_df["Taker"] = icons_df.get("Taker id", "").fillna("").replace({"": "Unknown"})
        icons_df["Team"] = icons_df["Team"].fillna("Unknown")
        icons_df["Taker"] = icons_df["Taker"].fillna("Unknown")

        # Hold-liste
        teams_sorted = sorted(t for t in icons_df["Team"].dropna().unique())

        # 2) Hold-filter
        team_sel = st.selectbox("Vælg hold", ["(Alle)"] + teams_sorted, index=0, key="icons_team")

        df_filt = icons_df.copy()
        if team_sel != "(Alle)":
            df_filt = df_filt[df_filt["Team"] == team_sel]

        # 3) Aggreger pr. (Team, Taker) for kortmetadata
        g = df_filt.groupby(["Team", "Taker"], dropna=False)
        meta = g.agg(
            ti=("Taker", "size"),
            avg_delay=("Delay (s)", lambda s: pd.to_numeric(s, errors="coerce").mean()),
            thrown_box=("Thrown into the box", lambda s: pd.Series(s).fillna(False).sum())
        ).reset_index()

        meta["avg_delay"] = pd.to_numeric(meta["avg_delay"], errors="coerce").round(2)
        meta["thrown_box"] = pd.to_numeric(meta["thrown_box"], errors="coerce").astype("Int64")


        if meta.empty:
            st.info("Ingen spillere matcher filtrene.")
            st.stop()

        # 4) Billedkilder
        _logo_dir = _ensure_logos_synced()
        _logo_map = _build_logo_dataurl_map(_logo_dir) if _logo_dir else {}
        _photo_index = build_player_photo_index()

        def _initials(name: str) -> str:
            parts = [p for p in _norm(name).split(" ") if p]
            return "".join(s[0].upper() for s in parts[:2]) or "?"

        # Sorter (f.eks. flest kast først)
        meta = meta.sort_values(["Team", "ti", "Taker"], ascending=[True, False, True]).reset_index(drop=True)

        # 5) Render – hvis "(Alle)", vis gruppevis per hold
        def render_grid(df_team: pd.DataFrame, team_name: str | None):
            st.markdown(f"#### {team_name}" if team_name else "#### Spillere")
            st.markdown("<div class='player-grid'>", unsafe_allow_html=True)
            for _, row in df_team.iterrows():
                team = row["Team"]
                player = row["Taker"] or "Unknown"
                img = get_player_photo_dataurl(team, player, _photo_index) or _logo_lookup(_logo_map, team)

                if img:
                    img_html = f'<img class="player-img" src="{img}" />'
                else:
                    img_html = f'<div class="player-initials">{_initials(player)}</div>'

                card_html = f"""
                <div class="player-card">
                  {img_html}
                  <div class="player-name">{player}</div>
                  <div class="player-team">{team}</div>
                  <div class="player-meta">Throw-ins: <b>{int(row['ti'])}</b> · Avg delay: <b>{row['avg_delay'] if pd.notna(row['avg_delay']) else '—'} s</b></div>
                </div>
                """
                st.markdown(card_html, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        if team_sel == "(Alle)":
            for team in teams_sorted:
                df_team = meta[meta["Team"] == team]
                if not df_team.empty:
                    render_grid(df_team, team)
        else:
            render_grid(meta, team_sel)

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
        st.header("Throw-in data")
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

                df_throw = parse_throwin_delays_from_f24_cached(
                    str(f24_path),
                    str(f7_path) if f7_path else None,
                    str(f70_path) if f70_path else None,
                    SCHEMA_VER
                )

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
                    ("Distance (m)", None),
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

                    df_throw["_sort"] = (
                        pd.to_numeric(df_throw["Period"], errors="coerce").fillna(0).astype(int) * 10_000
                        + df_throw["Ball out (mm:ss)"].map(_to_seconds)
                    )
                    df_throw = df_throw.sort_values("_sort").drop(columns=["_sort"]).reset_index(drop=True)
                    df_throw["Throw-in #"] = range(1, len(df_throw) + 1)
                    df_throw["is_FCK"] = df_throw["Team"].apply(lambda t: t in TEAM_ALIASES)
                    df_throw["is_outlier"] = _mark_outliers(df_throw, OUTLIER_THR)

                    # ---------- FILTERS ABOVE GRAPH ----------
                    c1, c2, c3, c4, c5, c6 = st.columns(6)
                    with c1:
                        with filter_card("Home/Away"):
                            side_tog = st.radio(" ", ["All", "Home", "Away"], horizontal=False, key="data_side_filter")
                    with c2:
                        with filter_card("Third"):
                            third_tog = st.radio("  ", ["All", "First 1/3", "Second 1/3", "Last 1/3"],
                                                horizontal=False, key="data_third_filter")
                    with c3:
                        with filter_card("Thrown into the box"):
                            thrownbox_tog = st.radio("   ", ["All", "Yes", "No"], horizontal=False, key="data_thrownbox_filter")
                    with c4:
                        with filter_card("Ball retention (≥7s)"):
                            retention_tog = st.radio("    ", ["All", "Retained", "Lost"], horizontal=False, key="data_retention_filter")
                    with c5:
                        with filter_card("Shot ≤30s"):
                            shot30_tog = st.radio("     ", ["All", "Yes", "No"], horizontal=False, key="data_shot30_filter")
                    with c6:
                        with filter_card("Goal ≤30s"):
                            goal30_tog = st.radio("      ", ["All", "Yes", "No"], horizontal=False, key="data_goal30_filter")

                    # plot/dataframes baseret på filtre
                    df_plot = df_throw.copy()
                    if side_tog != "All":
                        df_plot = df_plot[df_plot["Side"] == side_tog]
                    if third_tog != "All":
                        df_plot = df_plot[df_plot["Third"] == third_tog]
                    if thrownbox_tog != "All":
                        df_plot = df_plot[df_plot["Thrown into the box"] == (thrownbox_tog == "Yes")]
                    if retention_tog != "All":
                        df_plot = df_plot[df_plot["Ball retention"] == (retention_tog == "Retained")]
                    if shot30_tog != "All":
                        df_plot = df_plot[df_plot["Shot in 30s"] == (shot30_tog == "Yes")]
                    if goal30_tog != "All":
                        df_plot = df_plot[df_plot["Goal in 30s"] == (goal30_tog == "Yes")]

                    df_table = df_plot.copy()

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
                            fig.set_dpi(160)
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
                            "Delay (s)", "Team", "Taker", "Side", "Third", "Zone",
                            "x", "y", "end_x", "end_y", "End zone", "End third",
                            "Distance (m)",
                            "Thrown into the box", "Ball retention",
                            "Seq events", "Seq passes", "Seq duration (s)", "Seq ends with shot", "Seq last type",
                            "Shot in 30s", "Goal in 30s", "Shot time from TI (s)", "Shot x", "Shot y", "Shot xG (30s)",
                            "Game date", "Throw-in #", "is_outlier", "is_FCK",
                            "throwin_event_id", "throwin_team_id", "throwin_time_s", "throwin_period",
                        ]
                        show_cols = [c for c in display_cols if c in df_table.columns]
                        st.dataframe(df_table[show_cols], hide_index=True, height=380)



# =========================
# Router
# =========================

def _collect_roster_from_f7(f7_path: Path) -> list[dict]:
    """
    Læs hele truppen fra en F7: returner rækker med Team, Player, PlayerID.
    """
    rows = []
    try:
        root = ET.parse(str(f7_path)).getroot()
        for team_el in root.findall(".//Team"):
            # Holdnavn
            tname = None
            name_el = team_el.find("Name")
            if name_el is not None and (name_el.text or "").strip():
                tname = name_el.text.strip()
            if not tname:
                tname = team_el.attrib.get("TeamName", "") or "Unknown"

            for p in team_el.findall("Player"):
                pid = (p.attrib.get("uID") or p.attrib.get("uid") or "").strip()
                person = p.find("PersonName")
                first = (person.findtext("First") or "").strip() if person is not None else ""
                known = (person.findtext("Known") or "").strip() if person is not None else ""
                last  = (person.findtext("Last")  or person.findtext("FamilyName") or "").strip() if person is not None else ""
                pname = known if known else (" ".join(x for x in [first, last] if x).strip() or first or last or "")
                if not pname:
                    pname = "Unknown"
                rows.append({"Team": tname, "Player": pname, "PlayerID": pid})
    except Exception:
        pass
    return rows


if module.startswith("Throw-ins"):
    render_throwins_module()
elif module.startswith("Shots"):
    st.subheader("Shots")
    st.info("Under development")
else:
    st.info("Vælg et modul i venstremenuen.")