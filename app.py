import streamlit as st
import requests
import pandas as pd
import json
import os
import time
from datetime import datetime
from collections import defaultdict

# ============================================================
# OPTIONAL GEMINI AI
# ============================================================

try:
    from google import genai
    GEMINI_AVAILABLE = True
except Exception:
    GEMINI_AVAILABLE = False


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="FPL Mini-League Times",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# STYLING
# ============================================================

st.markdown("""
<style>

.main-title {
    font-size: 48px;
    font-weight: 900;
    text-align: center;
    margin-bottom: 0;
}

.subtitle {
    text-align: center;
    font-size: 18px;
    color: #777;
    margin-bottom: 30px;
}

.headline {
    font-size: 30px;
    font-weight: 900;
    line-height: 1.1;
}

.story {
    background: #f7f7f7;
    padding: 22px;
    border-radius: 12px;
    margin-bottom: 15px;
}

.award {
    border: 1px solid #ddd;
    border-radius: 12px;
    padding: 18px;
    min-height: 190px;
}

.big-number {
    font-size: 42px;
    font-weight: 900;
}

.small-muted {
    color: #777;
    font-size: 14px;
}

.warning-box {
    padding: 15px;
    border-radius: 10px;
    background: #fff3cd;
    border: 1px solid #ffe69c;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# CONSTANTS
# ============================================================

BASE = "https://fantasy.premierleague.com/api"

# YOUR MINI-LEAGUE
LEAGUE_ID = "637276"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120 Safari/537.36"
    ),
    "Accept": "application/json"
}


# ============================================================
# API HELPER
# ============================================================

@st.cache_data(ttl=120)
def get_json(url):

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        response.raise_for_status()

        return response.json()

    except Exception:
        return None


# ============================================================
# FPL DATA
# ============================================================

@st.cache_data(ttl=300)
def get_bootstrap():

    return get_json(
        f"{BASE}/bootstrap-static/"
    )


@st.cache_data(ttl=300)
def get_league():

    return get_json(
        f"{BASE}/leagues-classic/{LEAGUE_ID}/standings/"
        f"?page_new_entries=1"
        f"&page_standings=1"
        f"&phase=1"
    )


@st.cache_data(ttl=300)
def get_manager_history(manager_id):

    return get_json(
        f"{BASE}/entry/{manager_id}/history/"
    )


@st.cache_data(ttl=120)
def get_manager_picks(manager_id, gw):

    return get_json(
        f"{BASE}/entry/{manager_id}/event/{gw}/picks/"
    )


@st.cache_data(ttl=120)
def get_live_gameweek(gw):

    return get_json(
        f"{BASE}/event/{gw}/live/"
    )


@st.cache_data(ttl=300)
def get_fixtures(gw):

    return get_json(
        f"{BASE}/fixtures/?event={gw}"
    )


# ============================================================
# CURRENT GAMEWEEK
# ============================================================

def get_current_gameweek(data):

    if not data:
        return 1

    events = data.get("events", [])

    for event in events:

        if event.get("is_current"):
            return event["id"]

    finished = [
        e["id"]
        for e in events
        if e.get("finished")
    ]

    if finished:
        return max(finished)

    return 1


# ============================================================
# GAMEWEEK STATUS
# ============================================================

def get_gameweek_status(data, gw):

    if not data:
        return "Unknown"

    for event in data.get("events", []):

        if event.get("id") == gw:

            if event.get("finished"):
                return "Finished"

            if event.get("data_checked"):
                return "Data checked"

            if event.get("is_current"):
                return "LIVE"

            if event.get("is_next"):
                return "Upcoming"

    return "Unknown"


# ============================================================
# PLAYER LOOKUP
# ============================================================

def build_player_lookup(data):

    teams = {
        team["id"]: team["name"]
        for team in data.get("teams", [])
    }

    players = {}

    for player in data.get("elements", []):

        players[player["id"]] = {

            "name": (
                f"{player.get('first_name', '')} "
                f"{player.get('second_name', '')}"
            ).strip(),

            "short_name": player.get(
                "web_name",
                "Unknown"
            ),

            "team": teams.get(
                player.get("team"),
                "Unknown"
            ),

            "position": player.get(
                "element_type"
            ),

            "price": (
                player.get("now_cost", 0) / 10
            ),

            "total_points": player.get(
                "total_points",
                0
            )
        }

    return players


# ============================================================
# LIVE PLAYER POINTS
# ============================================================

def build_live_points(live_data):

    points = {}

    if not live_data:
        return points

    for player in live_data.get(
        "elements",
        []
    ):

        player_id = player.get("id")

        stats = player.get(
            "stats",
            {}
        )

        points[player_id] = {

            "total_points": stats.get(
                "total_points",
                0
            ),

            "minutes": stats.get(
                "minutes",
                0
            ),

            "goals": stats.get(
                "goals_scored",
                0
            ),

            "assists": stats.get(
                "assists",
                0
            ),

            "bonus": stats.get(
                "bonus",
                0
            ),

            "bps": stats.get(
                "bps",
                0
            )
        }

    return points


# ============================================================
# FIXTURE STATUS
# ============================================================

def get_fixture_status(fixtures):

    if not fixtures:
        return {
            "finished": False,
            "started": False
        }

    started = any(
        fixture.get("started")
        for fixture in fixtures
    )

    finished = all(
        fixture.get("finished")
        for fixture in fixtures
    )

    return {
        "started": started,
        "finished": finished
    }


# ============================================================
# GET MANAGERS
# ============================================================

def get_all_league_managers(league):

    if not league:
        return []

    standings = league.get(
        "standings",
        {}
    )

    return standings.get(
        "results",
        []
    )


# ============================================================
# FIND HISTORY FOR GAMEWEEK
# ============================================================

def get_history_for_gw(history, gw):

    if not history:
        return None

    for row in history.get(
        "current",
        []
    ):

        if row.get("event") == gw:
            return row

    return None


# ============================================================
# MANAGER ANALYSIS
# ============================================================

def analyse_manager(
    manager,
    gw,
    players,
    live_points
):

    manager_id = manager.get(
        "entry"
    )

    if not manager_id:
        return None

    # --------------------------------------------------------
    # HISTORY
    # --------------------------------------------------------

    history = get_manager_history(
        manager_id
    )

    history_row = get_history_for_gw(
        history,
        gw
    )

    # --------------------------------------------------------
    # PICKS
    # --------------------------------------------------------

    picks_data = get_manager_picks(
        manager_id,
        gw
    )

    if not picks_data:
        return None

    picks = picks_data.get(
        "picks",
        []
    )

    # --------------------------------------------------------
    # FPL OFFICIAL GAMEWEEK DATA
    # --------------------------------------------------------

    entry_history = picks_data.get(
        "entry_history",
        {}
    )

    # Prefer picks entry history.
    # Fall back to manager history.
    if not entry_history:
        entry_history = (
            history_row
            if history_row
            else {}
        )

    # --------------------------------------------------------
    # OFFICIAL FPL POINTS
    # --------------------------------------------------------

    gw_points = entry_history.get(
        "points",
        0
    )

    total_points = entry_history.get(
        "total_points",
        0
    )

    transfer_count = entry_history.get(
        "event_transfers",
        0
    )

    transfer_cost = entry_history.get(
        "event_transfers_cost",
        0
    )

    overall_rank = entry_history.get(
        "overall_rank",
        0
    )

    previous_overall_rank = entry_history.get(
        "last_rank",
        overall_rank
    )

    # --------------------------------------------------------
    # MINI LEAGUE POSITION
    # --------------------------------------------------------

    league_position = manager.get(
        "rank",
        0
    )

    # --------------------------------------------------------
    # STARTERS / BENCH
    # --------------------------------------------------------

    starting = [
        player
        for player in picks
        if player.get("position", 0) <= 11
    ]

    bench = [
        player
        for player in picks
        if player.get("position", 0) > 11
    ]

    # --------------------------------------------------------
    # CAPTAIN
    # --------------------------------------------------------

    captain = next(
        (
            player
            for player in picks
            if player.get("is_captain")
        ),
        None
    )

    vice = next(
        (
            player
            for player in picks
            if player.get("is_vice_captain")
        ),
        None
    )

    # --------------------------------------------------------
    # PLAYER HELPERS
    # --------------------------------------------------------

    def player_name(player):

        if not player:
            return "Unknown"

        player_id = player.get(
            "element"
        )

        return players.get(
            player_id,
            {}
        ).get(
            "short_name",
            "Unknown"
        )

    def player_points(player):

        if not player:
            return 0

        player_id = player.get(
            "element"
        )

        live = live_points.get(
            player_id,
            {}
        )

        return live.get(
            "total_points",
            0
        )

    # --------------------------------------------------------
    # CAPTAIN POINTS
    # --------------------------------------------------------

    captain_name = player_name(
        captain
    )

    captain_raw_points = player_points(
        captain
    )

    captain_multiplier = (
        captain.get(
            "multiplier",
            2
        )
        if captain
        else 1
    )

    captain_effective = (
        captain_raw_points *
        captain_multiplier
    )

    # --------------------------------------------------------
    # VICE
    # --------------------------------------------------------

    vice_name = player_name(
        vice
    )

    vice_points = player_points(
        vice
    )

    # --------------------------------------------------------
    # BENCH
    # --------------------------------------------------------

    bench_points_calculated = sum(
        player_points(player)
        for player in bench
    )

    # FPL's own bench figure is preferred.
    official_bench_points = entry_history.get(
        "points_on_bench",
        bench_points_calculated
    )

    if official_bench_points is None:
        official_bench_points = bench_points_calculated

    # --------------------------------------------------------
    # BIGGEST BENCH REGRET
    # --------------------------------------------------------

    bench_details = []

    for player in bench:

        pts = player_points(
            player
        )

        bench_details.append(
            (
                pts,
                player_name(player)
            )
        )

    bench_details.sort(
        reverse=True
    )

    if bench_details:

        biggest_bench_points = (
            bench_details[0][0]
        )

        biggest_bench_name = (
            bench_details[0][1]
        )

    else:

        biggest_bench_points = 0
        biggest_bench_name = "None"

    # --------------------------------------------------------
    # STARTING XI PLAYER POINTS
    # --------------------------------------------------------

    starting_points = sum(
        player_points(player) *
        player.get("multiplier", 1)
        for player in starting
    )

    # --------------------------------------------------------
    # STARTING NAMES
    # --------------------------------------------------------

    starting_names = [
        player_name(player)
        for player in starting
    ]

    # --------------------------------------------------------
    # CHIP
    # --------------------------------------------------------

    active_chip = picks_data.get(
        "active_chip"
    )

    # --------------------------------------------------------
    # RANK MOVEMENT
    #
    # Positive = moved up
    # Negative = moved down
    # --------------------------------------------------------

    rank_change = 0

    if (
        previous_overall_rank
        and overall_rank
    ):

        rank_change = (
            previous_overall_rank
            - overall_rank
        )

    # --------------------------------------------------------
    # RETURN
    # --------------------------------------------------------

    return {

        "id": manager_id,

        "name": manager.get(
            "player_name",
            "Unknown"
        ),

        "team_name": manager.get(
            "entry_name",
            "Unknown"
        ),

        "league_position": league_position,

        "gw_points": int(
            gw_points or 0
        ),

        "total_points": int(
            total_points or 0
        ),

        "overall_rank": int(
            overall_rank or 0
        ),

        "previous_overall_rank": int(
            previous_overall_rank or 0
        ),

        "rank_change": int(
            rank_change
        ),

        "captain": captain_name,

        "captain_raw": int(
            captain_raw_points
        ),

        "captain_effective": int(
            captain_effective
        ),

        "vice": vice_name,

        "vice_points": int(
            vice_points
        ),

        "bench_points": int(
            official_bench_points
        ),

        "bench_points_calculated": int(
            bench_points_calculated
        ),

        "biggest_bench": (
            biggest_bench_name
        ),

        "biggest_bench_points": int(
            biggest_bench_points
        ),

        "transfers": int(
            transfer_count or 0
        ),

        "transfer_cost": int(
            transfer_cost or 0
        ),

        "starting_points": int(
            starting_points
        ),

        "starting_names": (
            starting_names
        ),

        "active_chip": (
            active_chip or "None"
        )
    }


# ============================================================
# ANALYSE WHOLE LEAGUE
# ============================================================

def analyse_league(
    league,
    gw,
    players,
    live_points
):

    managers = get_all_league_managers(
        league
    )

    analysed = []

    progress = st.progress(
        0
    )

    total = len(managers)

    for i, manager in enumerate(
        managers
    ):

        result = analyse_manager(
            manager,
            gw,
            players,
            live_points
        )

        if result:

            analysed.append(
                result
            )

        progress.progress(
            int(
                ((i + 1) /
                max(total, 1)) *
                100
            )
        )

        # Be gentle on the API
        time.sleep(0.08)

    progress.empty()

    return analysed


# ============================================================
# AWARDS
# ============================================================

def get_awards(df):

    awards = {}

    if df.empty:
        return awards

    # --------------------------------------------------------
    # MANAGER OF WEEK
    # --------------------------------------------------------

    awards["manager"] = df.loc[
        df["gw_points"].idxmax()
    ]

    # --------------------------------------------------------
    # DISASTER
    # --------------------------------------------------------

    awards["disaster"] = df.loc[
        df["gw_points"].idxmin()
    ]

    # --------------------------------------------------------
    # CAPTAIN KING
    # --------------------------------------------------------

    awards["captain"] = df.loc[
        df["captain_effective"].idxmax()
    ]

    # --------------------------------------------------------
    # CAPTAIN DISASTER
    # --------------------------------------------------------

    awards["captain_bad"] = df.loc[
        df["captain_effective"].idxmin()
    ]

    # --------------------------------------------------------
    # BENCH BLUNDER
    # --------------------------------------------------------

    # Only count actual bench mistakes.
    # Bench Boost = not a blunder.
    non_bb = df[
        df["active_chip"] != "bboost"
    ]

    if not non_bb.empty:

        awards["bench"] = non_bb.loc[
            non_bb["bench_points"].idxmax()
        ]

    else:

        awards["bench"] = df.iloc[0]

    # --------------------------------------------------------
    # BIGGEST OVERALL FPL RISER
    # --------------------------------------------------------

    awards["riser"] = df.loc[
        df["rank_change"].idxmax()
    ]

    # --------------------------------------------------------
    # BIGGEST OVERALL FPL FALLER
    # --------------------------------------------------------

    awards["faller"] = df.loc[
        df["rank_change"].idxmin()
    ]

    # --------------------------------------------------------
    # MOST TRANSFERS
    # --------------------------------------------------------

    awards["transfer"] = df.loc[
        df["transfers"].idxmax()
    ]

    return awards


# ============================================================
# LOCAL BANTER
# ============================================================

def generate_local_banter(
    row,
    award
):

    name = row["name"]

    points = int(
        row["gw_points"]
    )

    if award == "manager":

        return (
            f"{name} takes Manager of the Week "
            f"with {points} points. "
            f"Somebody check whether they've "
            f"suddenly started reading the rules."
        )

    if award == "disaster":

        return (
            f"{name} finishes bottom of the "
            f"weekly pile with just {points} points. "
            f"A performance that will be quietly "
            f"described as 'unlucky' in the group chat."
        )

    if award == "captain":

        return (
            f"{name} got the captaincy spot on. "
            f"{row['captain']} delivered "
            f"{row['captain_effective']} effective "
            f"captain points. Tactical genius."
        )

    if award == "captain_bad":

        return (
            f"{name} trusted {row['captain']} "
            f"as captain and got just "
            f"{row['captain_effective']} effective "
            f"points. Bold. Very bold."
        )

    if award == "bench":

        return (
            f"{name} left "
            f"{row['bench_points']} points "
            f"on the bench. That's not squad depth. "
            f"That's self-sabotage."
        )

    if award == "riser":

        movement = abs(
            int(row["rank_change"])
        )

        if movement == 0:

            return (
                f"{name} didn't move overall "
                f"this week."
            )

        return (
            f"{name} climbs "
            f"{movement} places overall. "
            f"The comeback is underway."
        )

    if award == "faller":

        movement = abs(
            int(row["rank_change"])
        )

        if movement == 0:

            return (
                f"{name} survived the week "
                f"without an overall rank drop."
            )

        return (
            f"{name} drops "
            f"{movement} places overall. "
            f"The less said, the better."
        )

    return ""


# ============================================================
# GEMINI KEY
# ============================================================

def get_gemini_key():

    try:

        key = st.secrets.get(
            "GEMINI_API_KEY"
        )

        if key:
            return key

    except Exception:
        pass

    return os.environ.get(
        "GEMINI_API_KEY"
    )


# ============================================================
# GEMINI NEWSPAPER
# ============================================================

def generate_ai_review(
    league_name,
    gw,
    df,
    awards,
    status
):

    api_key = get_gemini_key()

    if not api_key:

        return (
            "Gemini API key not found."
        )

    if not GEMINI_AVAILABLE:

        return (
            "The Google Gemini package is not installed."
        )

    # --------------------------------------------------------
    # SEND CLEAN DATA TO AI
    # --------------------------------------------------------

    records = []

    for _, row in df.iterrows():

        records.append({

            "manager": row["name"],

            "team": row["team_name"],

            "league_position": int(
                row["league_position"]
            ),

            "gameweek_points": int(
                row["gw_points"]
            ),

            "total_points": int(
                row["total_points"]
            ),

            "captain": row["captain"],

            "captain_points": int(
                row["captain_raw"]
            ),

            "captain_effective": int(
                row["captain_effective"]
            ),

            "bench_points": int(
                row["bench_points"]
            ),

            "transfers": int(
                row["transfers"]
            ),

            "transfer_cost": int(
                row["transfer_cost"]
            ),

            "overall_rank_change": int(
                row["rank_change"]
            ),

            "chip": row["active_chip"]
        })

    # --------------------------------------------------------
    # AWARD DATA
    # --------------------------------------------------------

    award_data = {}

    for key, row in awards.items():

        award_data[key] = {

            "manager": row["name"],

            "gameweek_points": int(
                row["gw_points"]
            ),

            "captain": row["captain"],

            "captain_effective": int(
                row["captain_effective"]
            ),

            "bench_points": int(
                row["bench_points"]
            ),

            "rank_change": int(
                row["rank_change"]
            )
        }

    # --------------------------------------------------------
    # PROMPT
    # --------------------------------------------------------

    prompt = f"""
You are the editor of a funny British fantasy
football newspaper covering an FPL mini-league.

NEWSPAPER:
THE MINI-LEAGUE TIMES

LEAGUE:
{league_name}

GAMEWEEK:
{gw}

GAMEWEEK STATUS:
{status}

Write a funny, competitive weekly newspaper.

STYLE:

- British football banter
- witty
- cheeky
- entertaining
- occasionally savage
- praise good decisions
- mock bad FPL decisions
- never genuinely abusive
- never discriminatory
- never invent facts

VERY IMPORTANT:

Use ONLY the supplied data.

Do NOT invent:
- player scores
- transfers
- captain points
- league positions
- injuries
- fixtures
- goals
- assists
- events

If the data does not tell you something,
do not pretend it happened.

The article should contain:

# THE BIG HEADLINE

A funny newspaper-style headline.

## MANAGER OF THE WEEK

Praise the best Gameweek performer.

## DISASTERCLASS OF THE WEEK

Mock the lowest scorer.

## CAPTAINCY CORNER

Discuss the best and worst captain decisions.

## BENCH BLUNDER

Identify the manager who left the most points
on the bench.

## THE TITLE RACE

Discuss the current mini-league leaders.

## THE WOODEN SPOON

Discuss the managers at the bottom.

## FRAUD WATCH

Pick one or two managers whose decisions
deserve some friendly suspicion.

## TRANSFER DESK

Discuss notable transfer activity.

## RISERS AND FALLERS

Discuss significant overall rank movements
where useful.

## FINAL WHISTLE

End with a funny closing paragraph.

The article should be approximately
700-1000 words.

Remember:

The joke should be about FPL decisions,
not people's personal characteristics.

DATA:

{json.dumps(records, indent=2)}

AWARDS:

{json.dumps(award_data, indent=2)}
"""

    # --------------------------------------------------------
    # CALL GEMINI
    # --------------------------------------------------------

    try:

        client = genai.Client(
            api_key=api_key
        )

        # Flash-Lite is fast and cost-efficient.
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt
        )

        if response and response.text:

            return response.text

        return (
            "Gemini returned no newspaper text."
        )

    except Exception as e:

        error_text = str(e)

        return (
            "Gemini could not write the newspaper.\n\n"
            f"Error: {error_text}\n\n"
            "If this says 429 or 503, try the button "
            "again in a few seconds."
        )


# ============================================================
# NEWSPAPER DOWNLOAD
# ============================================================

def create_download_text(
    league_name,
    gw,
    article
):

    timestamp = datetime.now().strftime(
        "%d/%m/%Y %H:%M"
    )

    text = f"""
============================================================
THE MINI-LEAGUE TIMES
============================================================

{league_name}

GAMEWEEK {gw}

Generated: {timestamp}

------------------------------------------------------------

{article}

------------------------------------------------------------

THE MINI-LEAGUE TIMES
Where your mates' FPL mistakes become public knowledge.

============================================================
"""

    return text


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">'
    '📰 THE MINI-LEAGUE TIMES'
    '</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    '"Where your mates\' FPL mistakes become public knowledge."'
    '</div>',
    unsafe_allow_html=True
)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.header(
    "⚙️ Mini-League"
)

st.sidebar.success(
    f"League ID: {LEAGUE_ID}"
)

st.sidebar.caption(
    "This league is permanently built into the app."
)

# ------------------------------------------------------------
# LOAD BASE DATA
# ------------------------------------------------------------

bootstrap = get_bootstrap()

if not bootstrap:

    st.error(
        "❌ Could not connect to the FPL API."
    )

    st.stop()


players = build_player_lookup(
    bootstrap
)

current_gw = get_current_gameweek(
    bootstrap
)

status_current = get_gameweek_status(
    bootstrap,
    current_gw
)

# ------------------------------------------------------------
# GAMEWEEK SELECTION
# ------------------------------------------------------------

st.sidebar.subheader(
    "Gameweek"
)

use_current = st.sidebar.checkbox(
    "Use current Gameweek",
    value=True
)

manual_gw = st.sidebar.number_input(
    "Choose Gameweek",
    min_value=1,
    max_value=38,
    value=current_gw
)

gw = (
    current_gw
    if use_current
    else manual_gw
)

status = get_gameweek_status(
    bootstrap,
    gw
)

# ------------------------------------------------------------
# STATUS
# ------------------------------------------------------------

if status == "Finished":

    st.sidebar.success(
        f"GW {gw}: Finished"
    )

elif status == "LIVE":

    st.sidebar.warning(
        f"GW {gw}: LIVE"
    )

elif status == "Data checked":

    st.sidebar.success(
        f"GW {gw}: Data checked"
    )

else:

    st.sidebar.info(
        f"GW {gw}: {status}"
    )


# ============================================================
# LOAD LEAGUE
# ============================================================

league = get_league()

if not league:

    st.error(
        "❌ Could not load mini-league 637276."
    )

    st.stop()


league_name = league.get(
    "league",
    {}
).get(
    "name",
    "FPL Mini-League"
)

st.success(
    f"Loaded **{league_name}**"
)


# ============================================================
# MANAGER COUNT
# ============================================================

managers = get_all_league_managers(
    league
)

st.sidebar.info(
    f"👥 Managers found: {len(managers)}"
)


if not managers:

    st.error(
        "No managers were found in this league."
    )

    st.stop()


# ============================================================
# ANALYSE BUTTON
# ============================================================

if st.button(
    f"🚀 Analyse Gameweek {gw}",
    type="primary",
    use_container_width=True
):

    with st.spinner(
        f"Getting FPL data for Gameweek {gw}..."
    ):

        live_data = get_live_gameweek(
            gw
        )

        live_points = build_live_points(
            live_data
        )

        analysed = analyse_league(
            league,
            gw,
            players,
            live_points
        )

    if not analysed:

        st.error(
            "❌ No manager data could be loaded."
        )

        st.stop()

    df = pd.DataFrame(
        analysed
    )

    st.session_state[
        "league_df"
    ] = df

    st.session_state[
        "league_name"
    ] = league_name

    st.session_state[
        "gw"
    ] = gw

    st.session_state[
        "status"
    ] = status

    # Clear old article when new GW analysed
    if "article" in st.session_state:

        del st.session_state[
            "article"
        ]

    st.success(
        f"Analysis complete — {len(df)} managers analysed."
    )


# ============================================================
# DISPLAY
# ============================================================

if "league_df" in st.session_state:

    df = st.session_state[
        "league_df"
    ]

    league_name = st.session_state[
        "league_name"
    ]

    gw = st.session_state[
        "gw"
    ]

    status = st.session_state[
        "status"
    ]

    awards = get_awards(
        df
    )

    # ========================================================
    # NEWSPAPER HEADER
    # ========================================================

    st.markdown("---")

    st.markdown(
        f"""
        <div style="text-align:center">
        <h1>GAMEWEEK {gw}</h1>
        <h2>{league_name}</h2>
        <p>{status}</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # ========================================================
    # DATA WARNING
    # ========================================================

    if status == "LIVE":

        st.warning(
            "⚠️ This Gameweek is still LIVE. "
            "Points, bonus and automatic substitutions "
            "may still change. Run the analysis again "
            "after the Gameweek finishes for the final version."
        )

    # ========================================================
    # HEADLINE
    # ========================================================

    winner = awards[
        "manager"
    ]

    st.markdown(
        f"""
        <div class="story">
        <div class="headline">
        🗞️ {winner['name']} TAKES GAMEWEEK HONOURS
        </div>
        <p>
        <b>{int(winner['gw_points'])}</b> points puts
        <b>{winner['name']}</b> at the top of the
        weekly leaderboard.
        </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # ========================================================
    # AWARDS
    # ========================================================

    st.subheader(
        "🏆 The Weekly Awards"
    )

    c1, c2, c3 = st.columns(3)

    # --------------------------------------------------------
    # MANAGER
    # --------------------------------------------------------

    with c1:

        r = awards["manager"]

        st.markdown(
            f"""
            <div class="award">
            <h3>🏆 Manager of the Week</h3>

            <div class="big-number">
            {int(r['gw_points'])}
            </div>

            <b>{r['name']}</b>

            <p>
            {generate_local_banter(
                r,
                "manager"
            )}
            </p>

            </div>
            """,
            unsafe_allow_html=True
        )

    # --------------------------------------------------------
    # DISASTER
    # --------------------------------------------------------

    with c2:

        r = awards["disaster"]

        st.markdown(
            f"""
            <div class="award">
            <h3>💀 Disasterclass</h3>

            <div class="big-number">
            {int(r['gw_points'])}
            </div>

            <b>{r['name']}</b>

            <p>
            {generate_local_banter(
                r,
                "disaster"
            )}
            </p>

            </div>
            """,
            unsafe_allow_html=True
        )

    # --------------------------------------------------------
    # CAPTAIN
    # --------------------------------------------------------

    with c3:

        r = awards["captain"]

        st.markdown(
            f"""
            <div class="award">
            <h3>🎯 Captaincy King</h3>

            <div class="big-number">
            {int(r['captain_effective'])}
            </div>

            <b>{r['name']}</b>

            <p>
            {r['captain']} captaincy
            </p>

            </div>
            """,
            unsafe_allow_html=True
        )

    st.write("")

    c1, c2, c3 = st.columns(3)

    # --------------------------------------------------------
    # CAPTAIN DISASTER
    # --------------------------------------------------------

    with c1:

        r = awards[
            "captain_bad"
        ]

        st.markdown(
            f"""
            <div class="award">
            <h3>🤡 Captaincy Disaster</h3>

            <b>{r['name']}</b>

            <p>
            Captained {r['captain']}
            for {int(r['captain_effective'])}
            effective points.
            </p>

            </div>
            """,
            unsafe_allow_html=True
        )

    # --------------------------------------------------------
    # BENCH
    # --------------------------------------------------------

    with c2:

        r = awards[
            "bench"
        ]

        st.markdown(
            f"""
            <div class="award">
            <h3>🪑 Bench Blunder</h3>

            <div class="big-number">
            {int(r['bench_points'])}
            </div>

            <b>{r['name']}</b>

            <p>
            Points left sitting on the bench.
            </p>

            <p>
            Biggest regret:
            <b>{r['biggest_bench']}</b>
            ({int(r['biggest_bench_points'])})
            </p>

            </div>
            """,
            unsafe_allow_html=True
        )

    # --------------------------------------------------------
    # RISER
    # --------------------------------------------------------

    with c3:

        r = awards[
            "riser"
        ]

        movement = int(
            r["rank_change"]
        )

        st.markdown(
            f"""
            <div class="award">
            <h3>📈 Biggest Riser</h3>

            <div class="big-number">
            {movement:+d}
            </div>

            <b>{r['name']}</b>

            <p>
            Overall FPL rank movement.
            </p>

            </div>
            """,
            unsafe_allow_html=True
        )

    # ========================================================
    # AI NEWSPAPER
    # ========================================================

    st.markdown("---")

    st.subheader(
        "🎙️ The Weekly Review"
    )

    if get_gemini_key():

        st.success(
            "🤖 Gemini AI is connected."
        )

    else:

        st.warning(
            "Gemini AI is not connected. "
            "Add GEMINI_API_KEY to Streamlit Secrets."
        )

    if st.button(
        "📰 WRITE THE FULL NEWSPAPER",
        type="primary",
        use_container_width=True
    ):

        with st.spinner(
            "🖋️ The journalists are writing..."
        ):

            article = generate_ai_review(
                league_name,
                gw,
                df,
                awards,
                status
            )

        if article:

            st.session_state[
                "article"
            ] = article

    # --------------------------------------------------------
    # ARTICLE
    # --------------------------------------------------------

    if "article" in st.session_state:

        article = st.session_state[
            "article"
        ]

        st.markdown(
            '<div class="story">',
            unsafe_allow_html=True
        )

        st.markdown(
            article
        )

        st.markdown(
            '</div>',
            unsafe_allow_html=True
        )

        # ----------------------------------------------------
        # DOWNLOAD
        # ----------------------------------------------------

        download_text = create_download_text(
            league_name,
            gw,
            article
        )

        st.download_button(
            label="📥 Download Newspaper",
            data=download_text,
            file_name=(
                f"Mini-League-Times-GW-{gw}.txt"
            ),
            mime="text/plain",
            use_container_width=True
        )

        st.caption(
            "You can open the downloaded file and "
            "share it in WhatsApp, Messenger, email, etc."
        )

    # ========================================================
    # LEAGUE TABLE
    # ========================================================

    st.markdown("---")

    st.subheader(
        "📊 The League Table"
    )

    table = df.sort_values(
        "league_position"
    ).copy()

    display = table[
        [
            "league_position",
            "name",
            "team_name",
            "gw_points",
            "total_points"
        ]
    ].copy()

    display.columns = [
        "Pos",
        "Manager",
        "Team",
        f"GW {gw}",
        "Total"
    ]

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # WEEKLY LEADERBOARD
    # ========================================================

    st.subheader(
        "⚡ Gameweek Leaderboard"
    )

    weekly = df.sort_values(
        "gw_points",
        ascending=False
    ).copy()

    weekly_display = weekly[
        [
            "name",
            "team_name",
            "gw_points",
            "captain",
            "captain_effective"
        ]
    ].copy()

    weekly_display.columns = [
        "Manager",
        "Team",
        "GW Points",
        "Captain",
        "Captain Points"
    ]

    st.dataframe(
        weekly_display,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # MANAGER SPOTLIGHT
    # ========================================================

    st.markdown("---")

    st.subheader(
        "🔎 Manager Spotlight"
    )

    selected = st.selectbox(
        "Choose a manager",
        df["name"].tolist()
    )

    manager = df[
        df["name"] == selected
    ].iloc[0]

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "GW Points",
        int(manager["gw_points"])
    )

    c2.metric(
        "Total",
        int(manager["total_points"])
    )

    c3.metric(
        "Captain",
        manager["captain"]
    )

    c4.metric(
        "Bench",
        int(manager["bench_points"])
    )

    st.write(
        f"**Captain:** "
        f"{manager['captain']} "
        f"({int(manager['captain_raw'])} raw / "
        f"{int(manager['captain_effective'])} effective)"
    )

    st.write(
        f"**Vice Captain:** "
        f"{manager['vice']} "
        f"({int(manager['vice_points'])} points)"
    )

    st.write(
        f"**Transfers:** "
        f"{int(manager['transfers'])} "
        f"| **Hit:** "
        f"-{int(manager['transfer_cost'])}"
    )

    st.write(
        f"**Biggest bench regret:** "
        f"{manager['biggest_bench']} "
        f"({int(manager['biggest_bench_points'])} points)"
    )

    st.write(
        f"**Chip:** "
        f"{manager['active_chip']}"
    )

    st.write(
        "**Starting XI:** "
        + ", ".join(
            manager["starting_names"]
        )
    )

    # ========================================================
    # FRAUD WATCH
    # ========================================================

    st.markdown("---")

    st.subheader(
        "🚨 Fraud Watch"
    )

    worst = awards[
        "disaster"
    ]

    captain_bad = awards[
        "captain_bad"
    ]

    bench = awards[
        "bench"
    ]

    fraud_names = []

    if worst["gw_points"] <= (
        df["gw_points"].median()
        - 15
    ):

        fraud_names.append(
            worst["name"]
        )

    if (
        captain_bad["captain_effective"]
        <= 4
    ):

        if captain_bad["name"] not in fraud_names:

            fraud_names.append(
                captain_bad["name"]
            )

    if (
        bench["bench_points"]
        >= 10
    ):

        if bench["name"] not in fraud_names:

            fraud_names.append(
                bench["name"]
            )

    if fraud_names:

        st.warning(
            "🚨 Fraud Watch: "
            + ", ".join(
                fraud_names
            )
            + " — the committee is investigating."
        )

    else:

        st.info(
            "Nobody has earned a full Fraud Watch "
            "investigation this week. Yet."
        )

    # ========================================================
    # TITLE RACE
    # ========================================================

    st.markdown("---")

    st.subheader(
        "🥊 The Title Race"
    )

    title = df.sort_values(
        "league_position"
    ).head(5)

    for _, row in title.iterrows():

        st.write(
            f"**{int(row['league_position'])}. "
            f"{row['name']}** — "
            f"{int(row['total_points'])} points"
        )

    if len(title) >= 2:

        gap = (
            int(title.iloc[0]["total_points"])
            -
            int(title.iloc[1]["total_points"])
        )

        st.info(
            f"🥊 **{title.iloc[0]['name']}** leads "
            f"**{title.iloc[1]['name']}** by "
            f"**{gap} points**."
        )

    # ========================================================
    # WOODEN SPOON
    # ========================================================

    st.subheader(
        "🥄 Wooden Spoon Watch"
    )

    bottom = df.sort_values(
        "league_position",
        ascending=False
    ).head(3)

    for _, row in bottom.iterrows():

        st.write(
            f"**{int(row['league_position'])}. "
            f"{row['name']}** — "
            f"{int(row['total_points'])} points"
        )

    # ========================================================
    # DATA CHECK
    # ========================================================

    st.markdown("---")

    st.subheader(
        "🔧 Data Check"
    )

    st.write(
        "This section is here so you can spot "
        "anything strange before trusting the newspaper."
    )

    check = df[
        [
            "name",
            "gw_points",
            "captain",
            "captain_raw",
            "captain_effective",
            "bench_points",
            "transfers",
            "transfer_cost"
        ]
    ].copy()

    check.columns = [
        "Manager",
        "GW Points",
        "Captain",
        "Captain Raw",
        "Captain Effective",
        "Bench Points",
        "Transfers",
        "Hit"
    ]

    st.dataframe(
        check,
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# WELCOME SCREEN
# ============================================================

else:

    st.markdown(
        """
        ### 👋 Welcome to The Mini-League Times

        Your FPL league is already built into the app.

        **League ID:** 637276

        Enter nothing — just choose the Gameweek and
        press **Analyse Gameweek**.

        You'll get:

        🏆 Manager of the Week  
        💀 Disasterclass  
        🎯 Captaincy King  
        🤡 Captaincy Disaster  
        🪑 Bench Blunder  
        📈 Biggest Riser  
        📉 Biggest Faller  
        💰 Transfer analysis  
        🚨 Fraud Watch  
        🥊 Title Race  
        🥄 Wooden Spoon Watch  
        🎙️ AI-written newspaper  
        📥 Downloadable newspaper

        The AI newspaper uses your actual FPL data and
        is instructed not to invent scores or events.
        """
    )
