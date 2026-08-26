import streamlit as st
import requests
import pandas as pd
import json
import os
import re
import textwrap
import html as html_lib
from io import BytesIO
from datetime import datetime

# ============================================================
# OPTIONAL PDF SUPPORT
# ============================================================

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import (
        getSampleStyleSheet,
        ParagraphStyle,
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        HRFlowable,
        KeepTogether,
    )
    from reportlab.lib.units import mm

    REPORTLAB_AVAILABLE = True

except Exception:
    REPORTLAB_AVAILABLE = False


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
    page_title="The Mini-League Times",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CONFIG
# ============================================================

BASE = "https://fantasy.premierleague.com/api"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# YOUR THREE MINI-LEAGUES
LEAGUES = {
    "Dad V Lad": "1555183",
    "The Lads": "70818",
    "IMW": "637276",
}

# Use an environment variable if you want to change the model.
GEMINI_MODEL = os.environ.get(
    "GEMINI_MODEL",
    "gemini-2.5-flash"
)


# ============================================================
# VISUAL STYLE
# ============================================================

st.markdown(
    """
<style>

/* ----------------------------------------------------------
   GENERAL
---------------------------------------------------------- */

.block-container {
    padding-top: 1.5rem;
    padding-bottom: 3rem;
    max-width: 1400px;
}

body {
    background: #f4f1e8;
}


/* ----------------------------------------------------------
   NEWSPAPER MASTHEAD
---------------------------------------------------------- */

.newspaper {
    background:
        linear-gradient(
            135deg,
            rgba(255,255,255,0.97),
            rgba(245,241,225,0.98)
        );
    border: 4px solid #111827;
    border-radius: 18px;
    padding: 28px 30px 22px 30px;
    margin-bottom: 18px;
    box-shadow: 0 8px 25px rgba(0,0,0,0.15);
}

.masthead-title {
    font-family: Georgia, serif;
    font-size: 54px;
    line-height: 1;
    font-weight: 900;
    text-align: center;
    color: #111827;
    letter-spacing: -2px;
}

.masthead-subtitle {
    text-align: center;
    font-family: Georgia, serif;
    font-size: 17px;
    color: #555;
    margin-top: 8px;
    font-style: italic;
}

.edition-row {
    border-top: 2px solid #111827;
    border-bottom: 2px solid #111827;
    margin-top: 18px;
    padding: 8px 0;
    display: flex;
    justify-content: space-between;
    font-family: monospace;
    font-size: 13px;
    font-weight: bold;
}


/* ----------------------------------------------------------
   BREAKING NEWS
---------------------------------------------------------- */

.breaking {
    background: #f4c430;
    border: 3px solid #111827;
    border-radius: 12px;
    padding: 13px 18px;
    margin: 15px 0;
    color: #111827;
    font-weight: 900;
    font-size: 16px;
    box-shadow: 0 4px 0 #111827;
}


/* ----------------------------------------------------------
   HERO STORY
---------------------------------------------------------- */

.hero {
    background:
        radial-gradient(
            circle at 85% 20%,
            rgba(255,255,255,0.18) 0,
            rgba(255,255,255,0) 30%
        ),
        linear-gradient(
            135deg,
            #172554,
            #1d4ed8
        );
    color: white;
    border-radius: 18px;
    padding: 30px;
    margin: 18px 0;
    box-shadow: 0 8px 20px rgba(0,0,0,0.2);
    position: relative;
    overflow: hidden;
}

.hero-ball {
    position: absolute;
    right: 35px;
    top: 20px;
    font-size: 90px;
    opacity: 0.18;
}

.hero-kicker {
    font-size: 14px;
    text-transform: uppercase;
    letter-spacing: 2px;
    font-weight: 900;
    opacity: 0.85;
}

.hero-title {
    font-family: Georgia, serif;
    font-size: 38px;
    line-height: 1.05;
    font-weight: 900;
    margin: 8px 0;
    max-width: 850px;
}

.hero-points {
    font-size: 24px;
    font-weight: 900;
}


/* ----------------------------------------------------------
   SECTION TITLES
---------------------------------------------------------- */

.section-title {
    font-family: Georgia, serif;
    font-size: 30px;
    font-weight: 900;
    border-bottom: 4px solid #111827;
    padding-bottom: 7px;
    margin-top: 30px;
    margin-bottom: 18px;
}


/* ----------------------------------------------------------
   AWARD CARDS
---------------------------------------------------------- */

.award-card {
    background: white;
    border: 2px solid #d1d5db;
    border-radius: 16px;
    padding: 20px;
    min-height: 220px;
    margin-bottom: 18px;
    box-shadow: 0 5px 15px rgba(0,0,0,0.08);
}

.award-card.gold {
    border-top: 8px solid #eab308;
}

.award-card.red {
    border-top: 8px solid #ef4444;
}

.award-card.blue {
    border-top: 8px solid #2563eb;
}

.award-card.green {
    border-top: 8px solid #16a34a;
}

.award-card.purple {
    border-top: 8px solid #7c3aed;
}

.award-card.orange {
    border-top: 8px solid #f97316;
}

.award-icon {
    font-size: 34px;
}

.award-title {
    font-family: Georgia, serif;
    font-size: 20px;
    font-weight: 900;
    margin: 6px 0;
}

.award-number {
    font-size: 42px;
    font-weight: 900;
    line-height: 1;
    margin: 10px 0;
}

.award-manager {
    font-size: 19px;
    font-weight: 900;
}

.award-text {
    color: #555;
    margin-top: 8px;
}


/* ----------------------------------------------------------
   PODIUM
---------------------------------------------------------- */

.podium-wrap {
    background: linear-gradient(
        135deg,
        #111827,
        #1f2937
    );
    border-radius: 18px;
    padding: 25px;
    color: white;
    margin: 20px 0;
}

.podium-title {
    font-family: Georgia, serif;
    text-align: center;
    font-size: 28px;
    font-weight: 900;
    margin-bottom: 25px;
}

.podium {
    display: flex;
    align-items: end;
    justify-content: center;
    gap: 12px;
}

.podium-box {
    background: white;
    color: #111827;
    border-radius: 14px 14px 5px 5px;
    padding: 15px;
    text-align: center;
    width: 30%;
}

.podium-first {
    min-height: 230px;
    border-top: 10px solid #facc15;
}

.podium-second {
    min-height: 185px;
    border-top: 10px solid #d1d5db;
}

.podium-third {
    min-height: 150px;
    border-top: 10px solid #b45309;
}

.podium-medal {
    font-size: 35px;
}

.podium-name {
    font-size: 18px;
    font-weight: 900;
}

.podium-points {
    font-size: 27px;
    font-weight: 900;
}


/* ----------------------------------------------------------
   FAN INTERVIEW
---------------------------------------------------------- */

.interview {
    background:
        linear-gradient(
            135deg,
            #fff7ed,
            #ffffff
        );
    border: 3px solid #ea580c;
    border-radius: 18px;
    padding: 24px;
    margin: 20px 0;
    box-shadow: 0 6px 15px rgba(0,0,0,0.08);
}

.interview-header {
    display: flex;
    align-items: center;
    gap: 12px;
    font-family: Georgia, serif;
    font-size: 27px;
    font-weight: 900;
    color: #9a3412;
    border-bottom: 2px solid #fed7aa;
    padding-bottom: 12px;
    margin-bottom: 15px;
}

.interview-person {
    font-size: 20px;
    font-weight: 900;
}

.question {
    font-weight: 900;
    margin-top: 14px;
    color: #9a3412;
}

.answer {
    margin-top: 4px;
    font-family: Georgia, serif;
    font-size: 16px;
    line-height: 1.5;
}


/* ----------------------------------------------------------
   SPECIAL STORIES
---------------------------------------------------------- */

.story-card {
    background: white;
    border-radius: 16px;
    border: 2px solid #d1d5db;
    padding: 22px;
    margin-bottom: 18px;
}

.story-card h3 {
    font-family: Georgia, serif;
    margin-top: 0;
}

.fraud {
    background: linear-gradient(
        135deg,
        #450a0a,
        #991b1b
    );
    color: white;
    border-radius: 18px;
    padding: 25px;
    border: 3px solid #ef4444;
}

.title-race {
    background: linear-gradient(
        135deg,
        #052e16,
        #166534
    );
    color: white;
    border-radius: 18px;
    padding: 25px;
}

.wooden-spoon {
    background: linear-gradient(
        135deg,
        #3f1d0b,
        #92400e
    );
    color: white;
    border-radius: 18px;
    padding: 25px;
}


/* ----------------------------------------------------------
   AI ARTICLE
---------------------------------------------------------- */

.article {
    background: #fffdf5;
    border: 2px solid #111827;
    border-radius: 16px;
    padding: 30px;
    font-family: Georgia, serif;
    line-height: 1.7;
    box-shadow: 0 7px 20px rgba(0,0,0,0.10);
}

.article h1,
.article h2,
.article h3 {
    font-family: Georgia, serif;
    color: #111827;
}

.article h1 {
    font-size: 36px;
}

.article h2 {
    border-bottom: 2px solid #d1d5db;
    padding-bottom: 5px;
}


/* ----------------------------------------------------------
   SMALL STAT CARDS
---------------------------------------------------------- */

.stat-card {
    background: white;
    border-radius: 14px;
    padding: 16px;
    border: 2px solid #e5e7eb;
    text-align: center;
}

.stat-number {
    font-size: 30px;
    font-weight: 900;
}

.stat-label {
    color: #6b7280;
    font-size: 13px;
}


/* ----------------------------------------------------------
   FOOTER
---------------------------------------------------------- */

.footer {
    text-align: center;
    font-family: Georgia, serif;
    color: #666;
    padding: 25px;
    border-top: 3px double #111827;
    margin-top: 35px;
}

</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# SAFE HTML RENDERER
# ============================================================

def render_html(content):
    """
    IMPORTANT:
    Removes accidental indentation from HTML.

    This is what fixes the problem where Streamlit was showing:
    <div class="...">
    instead of actually rendering the design.
    """
    cleaned = textwrap.dedent(str(content)).strip()

    st.markdown(
        cleaned,
        unsafe_allow_html=True,
    )


# ============================================================
# API
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def get_json(url):
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=25,
        )

        response.raise_for_status()
        return response.json()

    except Exception:
        return None


@st.cache_data(ttl=300, show_spinner=False)
def get_bootstrap():
    return get_json(
        f"{BASE}/bootstrap-static/"
    )


@st.cache_data(ttl=300, show_spinner=False)
def get_league_page(
    league_id,
    page,
):
    url = (
        f"{BASE}/leagues-classic/{league_id}/standings/"
        f"?page_new_entries=1"
        f"&page_standings={page}"
        f"&phase=1"
    )

    return get_json(url)


@st.cache_data(ttl=300, show_spinner=False)
def get_manager_history(manager_id):
    return get_json(
        f"{BASE}/entry/{manager_id}/history/"
    )


@st.cache_data(ttl=300, show_spinner=False)
def get_manager_picks(
    manager_id,
    gw,
):
    return get_json(
        f"{BASE}/entry/{manager_id}/event/{gw}/picks/"
    )


@st.cache_data(ttl=300, show_spinner=False)
def get_live_gameweek(gw):
    return get_json(
        f"{BASE}/event/{gw}/live/"
    )


# ============================================================
# HELPERS
# ============================================================

def safe_int(
    value,
    default=0,
):
    try:
        return int(value)
    except Exception:
        return default


def clean_text(text):
    if text is None:
        return ""

    return (
        str(text)
        .replace("\x00", "")
        .strip()
    )


def get_current_gameweek(data):

    if not data:
        return 1

    events = data.get(
        "events",
        [],
    )

    for event in events:

        if event.get("is_current"):
            return safe_int(
                event.get("id"),
                1,
            )

    finished = [
        safe_int(e.get("id"))
        for e in events
        if e.get("finished")
    ]

    return max(
        finished,
        default=1,
    )


def build_player_lookup(data):

    teams = {
        safe_int(t.get("id")):
        t.get("name", "?")
        for t in data.get("teams", [])
    }

    players = {}

    for player in data.get(
        "elements",
        [],
    ):

        pid = safe_int(
            player.get("id")
        )

        players[pid] = {
            "name":
                f"{player.get('first_name', '')} "
                f"{player.get('second_name', '')}".strip(),

            "short_name":
                player.get(
                    "web_name",
                    "?"
                ),

            "team":
                teams.get(
                    safe_int(
                        player.get("team")
                    ),
                    "?"
                ),

            "position":
                player.get(
                    "element_type"
                ),

            "price":
                player.get(
                    "now_cost",
                    0
                ) / 10,

            "total_points":
                safe_int(
                    player.get(
                        "total_points"
                    )
                ),
        }

    return players


def build_live_points(live):

    result = {}

    if not live:
        return result

    for item in live.get(
        "elements",
        []
    ):

        pid = safe_int(
            item.get("id")
        )

        stats = item.get(
            "stats",
            {}
        )

        result[pid] = {
            "points":
                safe_int(
                    stats.get(
                        "total_points"
                    )
                ),

            "minutes":
                safe_int(
                    stats.get(
                        "minutes"
                    )
                ),

            "goals":
                safe_int(
                    stats.get(
                        "goals_scored"
                    )
                ),

            "assists":
                safe_int(
                    stats.get(
                        "assists"
                    )
                ),

            "bonus":
                safe_int(
                    stats.get(
                        "bonus"
                    )
                ),
        }

    return result


def get_all_league_managers(
    league_id
):

    all_results = []

    for page in range(
        1,
        21
    ):

        data = get_league_page(
            league_id,
            page
        )

        if not data:
            break

        results = (
            data
            .get("standings", {})
            .get("results", [])
        )

        if not results:
            break

        all_results.extend(
            results
        )

        if len(results) < 50:
            break

    return all_results


def player_name(
    pick,
    players
):

    if not pick:
        return "Unknown"

    player = players.get(
        safe_int(
            pick.get("element")
        )
    )

    if not player:
        return "Unknown"

    return player["short_name"]


def pick_points(
    pick,
    live_points
):

    if not pick:
        return 0

    pid = safe_int(
        pick.get("element")
    )

    return safe_int(
        live_points
        .get(pid, {})
        .get("points", 0)
    )


def pick_minutes(
    pick,
    live_points
):

    if not pick:
        return 0

    pid = safe_int(
        pick.get("element")
    )

    return safe_int(
        live_points
        .get(pid, {})
        .get("minutes", 0)
    )


# ============================================================
# MANAGER ANALYSIS
# ============================================================

def analyse_manager(
    manager,
    gw,
    players,
    live_points
):

    manager_id = safe_int(
        manager.get("entry")
    )

    history = get_manager_history(
        manager_id
    )

    picks_data = get_manager_picks(
        manager_id,
        gw
    )

    if not history or not picks_data:
        return None

    current_history = None

    for event in history.get(
        "current",
        []
    ):

        if safe_int(
            event.get("event")
        ) == gw:

            current_history = event
            break

    if not current_history:
        return None

    picks = picks_data.get(
        "picks",
        []
    )

    if not picks:
        return None

    starting = [
        p for p in picks
        if safe_int(
            p.get("position")
        ) <= 11
    ]

    bench = [
        p for p in picks
        if safe_int(
            p.get("position")
        ) > 11
    ]

    original_captain = next(
        (
            p for p in picks
            if p.get("is_captain")
        ),
        None
    )

    original_vice = next(
        (
            p for p in picks
            if p.get("is_vice_captain")
        ),
        None
    )

    actual_captain = next(
        (
            p for p in picks
            if safe_int(
                p.get("multiplier")
            ) == 2
        ),
        original_captain
    )

    captain_name = player_name(
        original_captain,
        players
    )

    actual_captain_name = player_name(
        actual_captain,
        players
    )

    captain_raw_points = pick_points(
        original_captain,
        live_points
    )

    captain_effective = (
        pick_points(
            actual_captain,
            live_points
        ) * 2
    )

    captain_minutes = pick_minutes(
        original_captain,
        live_points
    )

    unused_bench = [
        p for p in bench
        if safe_int(
            p.get("multiplier")
        ) == 0
    ]

    bench_points = sum(
        pick_points(
            p,
            live_points
        )
        for p in unused_bench
    )

    biggest_bench = None

    if unused_bench:
        biggest_bench = max(
            unused_bench,
            key=lambda p:
                pick_points(
                    p,
                    live_points
                )
        )

    transfers = safe_int(
        current_history.get(
            "event_transfers"
        )
    )

    transfer_cost = safe_int(
        current_history.get(
            "event_transfers_cost"
        )
    )

    rank = safe_int(
        current_history.get(
            "overall_rank"
        )
    )

    last_rank = safe_int(
        current_history.get(
            "last_rank"
        ),
        rank
    )

    rank_change = (
        last_rank - rank
    )

    gw_points = safe_int(
        current_history.get(
            "points"
        )
    )

    total_points = safe_int(
        current_history.get(
            "total_points"
        )
    )

    calculated_team_points = sum(
        pick_points(
            p,
            live_points
        )
        * max(
            safe_int(
                p.get("multiplier")
            ),
            0
        )
        for p in picks
    )

    return {
        "id": manager_id,

        "name":
            clean_text(
                manager.get(
                    "player_name",
                    "Unknown"
                )
            ),

        "team_name":
            clean_text(
                manager.get(
                    "entry_name",
                    "Unknown"
                )
            ),

        "league_position":
            safe_int(
                manager.get("rank")
            ),

        "gw_points":
            gw_points,

        "total_points":
            total_points,

        "rank":
            rank,

        "last_rank":
            last_rank,

        "rank_change":
            rank_change,

        "captain":
            captain_name,

        "captain_points":
            captain_raw_points,

        "captain_minutes":
            captain_minutes,

        "captain_effective":
            captain_effective,

        "actual_captain":
            actual_captain_name,

        "vice":
            player_name(
                original_vice,
                players
            ),

        "bench_points":
            bench_points,

        "biggest_bench":
            player_name(
                biggest_bench,
                players
            ),

        "biggest_bench_points":
            pick_points(
                biggest_bench,
                live_points
            ) if biggest_bench else 0,

        "transfers":
            transfers,

        "transfer_cost":
            transfer_cost,

        "calculated_team_points":
            calculated_team_points,

        "starting_names": [
            player_name(
                p,
                players
            )
            for p in starting
        ],
    }


def analyse_league(
    managers,
    gw,
    players,
    live_points
):

    analysed = []

    progress = st.progress(0)

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
                 max(total, 1))
                * 100
            )
        )

    progress.empty()

    return analysed


# ============================================================
# AWARDS
# ============================================================

def get_awards(df):

    if df.empty:
        return {}

    return {
        "manager":
            df.loc[
                df["gw_points"].idxmax()
            ],

        "disaster":
            df.loc[
                df["gw_points"].idxmin()
            ],

        "captain":
            df.loc[
                df["captain_effective"].idxmax()
            ],

        "captain_bad":
            df.loc[
                df["captain_effective"].idxmin()
            ],

        "bench":
            df.loc[
                df["bench_points"].idxmax()
            ],

        "riser":
            df.loc[
                df["rank_change"].idxmax()
            ],

        "faller":
            df.loc[
                df["rank_change"].idxmin()
            ],

        "transfer":
            df.loc[
                df["transfers"].idxmax()
            ],
    }


def local_banter(
    row,
    award
):

    name = row["name"]

    points = safe_int(
        row["gw_points"]
    )

    if award == "manager":

        return (
            f"{name} takes Manager of the Week "
            f"with {points} points. "
            f"Somebody check whether they've secretly "
            f"started reading the rules."
        )

    if award == "disaster":

        return (
            f"{name} finishes bottom of the weekly pile "
            f"with just {points} points. "
            f"Expect the words 'unlucky' and 'fixture swing' "
            f"to appear repeatedly in the group chat."
        )

    if award == "captain":

        return (
            f"{name} trusted "
            f"{row['actual_captain']} "
            f"and collected "
            f"{safe_int(row['captain_effective'])} "
            f"effective captain points. "
            f"Tactical genius."
        )

    if award == "captain_bad":

        return (
            f"{name} handed the armband to "
            f"{row['captain']} "
            f"and collected just "
            f"{safe_int(row['captain_effective'])} "
            f"effective points. "
            f"A brave decision. A terrible one, but brave."
        )

    if award == "bench":

        return (
            f"{name} left "
            f"{safe_int(row['bench_points'])} "
            f"points sitting on the bench. "
            f"That's not squad depth. "
            f"That's self-sabotage."
        )

    if award == "riser":

        return (
            f"{name} climbs "
            f"{abs(safe_int(row['rank_change']))} "
            f"places. The title race has just got interesting."
        )

    if award == "faller":

        return (
            f"{name} drops "
            f"{abs(safe_int(row['rank_change']))} "
            f"places. Somebody might want to check "
            f"whether the manager is still awake."
        )

    return ""


# ============================================================
# GEMINI
# ============================================================

def get_gemini_client():

    if not GEMINI_AVAILABLE:
        return None

    api_key = None

    try:
        api_key = st.secrets.get(
            "GEMINI_API_KEY"
        )
    except Exception:
        pass

    if not api_key:
        api_key = os.environ.get(
            "GEMINI_API_KEY"
        )

    if not api_key:
        return None

    try:
        return genai.Client(
            api_key=api_key
        )
    except Exception:
        return None


def generate_ai_review(
    league_name,
    gw,
    df,
    awards
):

    client = get_gemini_client()

    if not client:
        return (
            None,
            "Gemini API key is not configured."
        )

    records = df.to_dict(
        orient="records"
    )

    award_data = {}

    for key, row in awards.items():

        award_data[key] = {
            "name":
                row["name"],

            "team":
                row["team_name"],

            "gw_points":
                safe_int(
                    row["gw_points"]
                ),

            "captain":
                row["captain"],

            "actual_captain":
                row["actual_captain"],

            "captain_effective":
                safe_int(
                    row["captain_effective"]
                ),

            "bench_points":
                safe_int(
                    row["bench_points"]
                ),

            "rank_change":
                safe_int(
                    row["rank_change"]
                ),

            "transfers":
                safe_int(
                    row["transfers"]
                ),
        }

    prompt = f"""
You are the editor of a funny British fantasy football
newspaper called THE MINI-LEAGUE TIMES.

Write the Gameweek {gw} edition for:

{league_name}

IMPORTANT:
Use ONLY the supplied FPL data.

Never invent:
- scores
- players
- managers
- transfers
- ranks
- events

Tone:
- funny
- British football banter
- competitive
- cheeky
- occasionally savage
- never genuinely nasty
- never discriminatory
- attack FPL decisions, not people's personal lives

The newspaper should feel like a proper tabloid sports paper.

Include these sections:

1. BIG FRONT PAGE HEADLINE

A dramatic headline based on the biggest story.

2. MANAGER OF THE WEEK

Praise the winner.

3. DISASTERCLASS

Roast the lowest scorer.

4. CAPTAINCY CORNER

Discuss the best and worst captaincy choices.

5. BENCH BLUNDER

Discuss the manager who left the most unused points
on the bench.

6. THE TITLE RACE

Discuss the top of the league and the points gap.

7. THE BATTLE AT THE BOTTOM

Discuss the bottom of the league.

8. TRANSFER DESK

Discuss the manager who made the most transfers.

9. FRAUD WATCH

Choose a manager only if the supplied data gives you
a genuinely funny FPL reason.

Keep it playful.

10. THE FINAL WHISTLE

Finish with a funny closing paragraph.

11. FAN INTERVIEW

Include a very short fictional supporter interview.

The supporter should be a passionate mini-league fan.

The interview must specifically criticise one manager's
FPL decision-making.

For example:
- terrible captain choice
- leaving points on the bench
- unnecessary transfers
- dropping down the league
- bizarre decision making

The fan interview should be about 150-200 words.

Format the interview like:

### FAN INTERVIEW

**Reporter:** ...

**Fan:** ...

**Reporter:** ...

**Fan:** ...

Use specific real data from the supplied information.

Do NOT pretend the fan is a real person.
Make it obvious that this is a humorous fictional
mini-league supporter.

Write approximately 900-1200 words.

DATA:

{json.dumps(records, ensure_ascii=False, indent=2)}

AWARDS:

{json.dumps(award_data, ensure_ascii=False, indent=2)}
"""

    try:

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )

        text = getattr(
            response,
            "text",
            None
        )

        if not text:
            return (
                None,
                "Gemini returned an empty response."
            )

        return (
            text.strip(),
            None
        )

    except Exception as e:

        return (
            None,
            str(e)
        )


# ============================================================
# FALLBACK FAN INTERVIEW
# ============================================================

def create_fallback_fan_interview(
    df,
    awards
):

    target = awards["disaster"]

    name = target["name"]

    points = safe_int(
        target["gw_points"]
    )

    captain = target["captain"]

    captain_points = safe_int(
        target["captain_effective"]
    )

    bench = safe_int(
        target["bench_points"]
    )

    if bench > captain_points:

        criticism = (
            f"leaving {bench} points on the bench"
        )

    else:

        criticism = (
            f"handing the captaincy to "
            f"{captain}"
        )

    return {
        "target":
            name,

        "intro":
            (
                "This week's fictional supporter has "
                "strong opinions about the tactical "
                "decision-making on display."
            ),

        "qa": [

            (
                "Reporter",
                f"{name} had a difficult week. "
                f"What went wrong?"
            ),

            (
                "Fan",
                f"What went wrong? Pretty much everything. "
                f"They scored only {points} points and somehow "
                f"still looked surprised by the result."
            ),

            (
                "Reporter",
                "What was the biggest tactical mistake?"
            ),

            (
                "Fan",
                f"I'd say {criticism}. "
                f"At this level, you can't just make decisions "
                f"and hope the FPL gods sort it out."
            ),

            (
                "Reporter",
                "Would you trust this manager next week?"
            ),

            (
                "Fan",
                "Trust them? Absolutely. "
                "Trust their decision-making? "
                "That's a completely different question."
            ),
        ]
    }


# ============================================================
# PDF
# ============================================================

def article_to_pdf(
    article,
    league_name,
    gw,
    df,
    awards
):

    if not REPORTLAB_AVAILABLE:
        return None

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "NewspaperTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=25,
        leading=28,
        alignment=TA_CENTER,
        textColor=colors.HexColor(
            "#111827"
        ),
        spaceAfter=6,
    )

    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontSize=11,
        leading=14,
        alignment=TA_CENTER,
        textColor=colors.HexColor(
            "#555555"
        ),
        spaceAfter=12,
    )

    headline_style = ParagraphStyle(
        "Headline",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=19,
        leading=22,
        textColor=colors.HexColor(
            "#111827"
        ),
        spaceBefore=10,
        spaceAfter=8,
    )

    body_style = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontSize=9.5,
        leading=13.5,
        spaceAfter=7,
    )

    story = []

    story.append(
        Paragraph(
            "THE MINI-LEAGUE TIMES",
            title_style
        )
    )

    story.append(
        Paragraph(
            f"GAMEWEEK {gw} • "
            f"{clean_text(league_name)}",
            subtitle_style
        )
    )

    story.append(
        HRFlowable(
            width="100%",
            thickness=3,
            color=colors.HexColor(
                "#111827"
            ),
            spaceBefore=3,
            spaceAfter=12,
        )
    )

    winner = awards["manager"]

    story.append(
        Paragraph(
            html_lib.escape(
                f"{winner['name']} TAKES "
                f"GAMEWEEK HONOURS"
            ),
            headline_style
        )
    )

    story.append(
        Paragraph(
            html_lib.escape(
                f"{safe_int(winner['gw_points'])} points "
                f"puts {winner['name']} top of the "
                f"weekly leaderboard."
            ),
            body_style
        )
    )

    # Award table
    award_rows = [
        [
            "🏆 MANAGER",
            "💀 DISASTER",
            "🎯 CAPTAIN"
        ],
        [
            winner["name"],
            awards["disaster"]["name"],
            awards["captain"]["name"]
        ],
        [
            f"{safe_int(winner['gw_points'])} pts",
            f"{safe_int(awards['disaster']['gw_points'])} pts",
            f"{safe_int(awards['captain']['captain_effective'])} pts"
        ],
    ]

    table = Table(
        award_rows,
        colWidths=[
            58 * mm,
            58 * mm,
            58 * mm
        ]
    )

    table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#111827")
            ),
            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white
            ),
            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                "Helvetica-Bold"
            ),
            (
                "FONTNAME",
                (0, 1),
                (-1, -1),
                "Helvetica-Bold"
            ),
            (
                "FONTSIZE",
                (0, 0),
                (-1, -1),
                9
            ),
            (
                "ALIGN",
                (0, 0),
                (-1, -1),
                "CENTER"
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE"
            ),
            (
                "BACKGROUND",
                (0, 1),
                (-1, -1),
                colors.HexColor("#fffdf5")
            ),
            (
                "BOX",
                (0, 0),
                (-1, -1),
                1,
                colors.HexColor("#111827")
            ),
            (
                "INNERGRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.HexColor("#d1d5db")
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                7
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                7
            ),
        ])
    )

    story.append(
        table
    )

    story.append(
        Spacer(
            1,
            10
        )
    )

    # Convert article
    for raw_line in article.splitlines():

        line = clean_text(
            raw_line
        )

        if not line:
            story.append(
                Spacer(
                    1,
                    4
                )
            )
            continue

        safe = (
            line
            .replace(
                "&",
                "&amp;"
            )
            .replace(
                "<",
                "&lt;"
            )
            .replace(
                ">",
                "&gt;"
            )
        )

        safe = re.sub(
            r"\*\*(.*?)\*\*",
            r"<b>\1</b>",
            safe
        )

        if safe.startswith(
            "### "
        ):

            story.append(
                Paragraph(
                    safe[4:],
                    ParagraphStyle(
                        "H3",
                        parent=styles["Heading3"],
                        fontName="Helvetica-Bold",
                        fontSize=13,
                        textColor=colors.HexColor(
                            "#9a3412"
                        ),
                        spaceBefore=9,
                        spaceAfter=5,
                    )
                )
            )

        elif safe.startswith(
            "## "
        ):

            story.append(
                Paragraph(
                    safe[3:],
                    ParagraphStyle(
                        "H2",
                        parent=styles["Heading2"],
                        fontName="Helvetica-Bold",
                        fontSize=15,
                        textColor=colors.HexColor(
                            "#111827"
                        ),
                        spaceBefore=10,
                        spaceAfter=6,
                    )
                )
            )

        elif safe.startswith(
            "# "
        ):

            story.append(
                Paragraph(
                    safe[2:],
                    headline_style
                )
            )

        else:

            story.append(
                Paragraph(
                    safe,
                    body_style
                )
            )

    # Footer
    story.append(
        Spacer(
            1,
            12
        )
    )

    story.append(
        HRFlowable(
            width="100%",
            thickness=2,
            color=colors.HexColor(
                "#111827"
            )
        )
    )

    story.append(
        Spacer(
            1,
            6
        )
    )

    story.append(
        Paragraph(
            f"The Mini-League Times • "
            f"Official FPL data • "
            f"Gameweek {gw}",
            subtitle_style
        )
    )

    doc.build(
        story
    )

    buffer.seek(0)

    return buffer.getvalue()


def article_to_txt(
    article,
    league_name,
    gw
):

    heading = (
        "THE MINI-LEAGUE TIMES\n"
        f"{league_name} — Gameweek {gw}\n"
        + "=" * 60
        + "\n\n"
    )

    return (
        heading + article
    ).encode(
        "utf-8"
    )


# ============================================================
# SESSION STATE
# ============================================================

if "selected_league" not in st.session_state:

    st.session_state[
        "selected_league"
    ] = "Dad V Lad"


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.markdown(
    "## 📰 Newspaper Settings"
)

selected_league = st.sidebar.selectbox(
    "Choose your mini-league",
    list(LEAGUES.keys()),
    index=list(
        LEAGUES.keys()
    ).index(
        st.session_state[
            "selected_league"
        ]
    ),
)

league_id = LEAGUES[
    selected_league
]

# If league changes, clear previous analysis.
if (
    selected_league
    != st.session_state.get(
        "selected_league"
    )
):

    st.session_state[
        "selected_league"
    ] = selected_league

    for key in [
        "league_df",
        "article",
        "ai_error",
        "fan_interview",
    ]:

        st.session_state.pop(
            key,
            None
        )

    st.rerun()


render_html(
    f"""
    <div class="story-card"
         style="background:#ecfdf5;border-color:#86efac;">
        <h3>📰 {html_lib.escape(selected_league)}</h3>
        <b>League ID:</b> {league_id}
    </div>
    """
)

st.sidebar.markdown(
    "---"
)

st.sidebar.markdown(
    "## ⚙️ Gameweek"
)

gw_override = st.sidebar.number_input(
    "Gameweek",
    min_value=1,
    max_value=38,
    value=1,
)

use_current = st.sidebar.checkbox(
    "Use current Gameweek automatically",
    value=True,
)

if st.sidebar.button(
    "🔄 Clear cached data"
):

    st.cache_data.clear()

    for key in [
        "league_df",
        "article",
        "ai_error",
        "fan_interview",
    ]:

        st.session_state.pop(
            key,
            None
        )

    st.rerun()


# ============================================================
# LOAD BOOTSTRAP
# ============================================================

bootstrap = get_bootstrap()

if not bootstrap:

    st.error(
        "Could not connect to the FPL API."
    )

    st.stop()


players = build_player_lookup(
    bootstrap
)

current_gw = get_current_gameweek(
    bootstrap
)

gw = (
    current_gw
    if use_current
    else int(gw_override)
)


# ============================================================
# NEWSPAPER HEADER
# ============================================================

render_html(
    f"""
    <div class="newspaper">

        <div class="masthead-title">
            THE MINI-LEAGUE TIMES
        </div>

        <div class="masthead-subtitle">
            Where your mates' FPL mistakes become public knowledge
        </div>

        <div class="edition-row">
            <span>EST. 2026</span>
            <span>{html_lib.escape(selected_league)}</span>
            <span>FANTASY FOOTBALL EDITION</span>
        </div>

    </div>
    """
)


render_html(
    f"""
    <div class="breaking">
        ⚽ BREAKING: The {html_lib.escape(selected_league)}
        edition is analysing Gameweek {gw}
        • Official FPL data
    </div>
    """
)


# ============================================================
# LOAD LEAGUE
# ============================================================

with st.spinner(
    f"Loading {selected_league}..."
):

    league = get_league_page(
        league_id,
        1
    )

if not league:

    st.error(
        f"Could not load mini-league "
        f"{league_id}."
    )

    st.stop()


api_league_name = (
    league
    .get("league", {})
    .get(
        "name"
    )
    or selected_league
)

managers = get_all_league_managers(
    league_id
)

if not managers:

    st.error(
        "No managers were found in "
        "this league."
    )

    st.stop()


render_html(
    f"""
    <div class="story-card"
         style="background:#eff6ff;border-color:#2563eb;">

        <h3>
            📰 {html_lib.escape(api_league_name)}
        </h3>

        <b>{len(managers)}</b>
        managers • League ID
        <b>{league_id}</b>

    </div>
    """
)


# ============================================================
# ANALYSE BUTTON
# ============================================================

if st.button(
    f"🚀 ANALYSE {selected_league.upper()} — GAMEWEEK {gw}",
    type="primary",
    use_container_width=True,
):

    with st.spinner(
        "Loading official Gameweek scores..."
    ):

        live = get_live_gameweek(
            gw
        )

    if not live:

        st.error(
            "The FPL live Gameweek data "
            "could not be loaded. "
            "Try again in a few seconds."
        )

        st.stop()

    live_points = build_live_points(
        live
    )

    with st.spinner(
        f"Analysing {len(managers)} managers..."
    ):

        analysed = analyse_league(
            managers,
            gw,
            players,
            live_points
        )

    if not analysed:

        st.error(
            "No manager data could be "
            "loaded for this Gameweek."
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
    ] = api_league_name

    st.session_state[
        "gw"
    ] = gw

    st.session_state[
        "live_loaded"
    ] = True

    st.session_state.pop(
        "article",
        None
    )

    st.session_state.pop(
        "fan_interview",
        None
    )

    st.success(
        f"Analysis complete — "
        f"{len(df)} managers processed."
    )


# ============================================================
# WELCOME SCREEN
# ============================================================

if "league_df" not in st.session_state:

    render_html(
        f"""
        <div class="hero">

            <div class="hero-ball">
                ⚽
            </div>

            <div class="hero-kicker">
                THE MINI-LEAGUE TIMES
            </div>

            <div class="hero-title">
                Welcome to the
                {html_lib.escape(selected_league)}
                newsroom.
            </div>

            <p>
                Your weekly FPL performance is about to
                become public knowledge.
            </p>

            <div class="hero-points">
                GAMEWEEK {gw}
            </div>

        </div>
        """
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        render_html(
            """
            <div class="stat-card">
                <div class="stat-number">🏆</div>
                <div class="stat-label">
                    Manager of the Week
                </div>
            </div>
            """
        )

    with c2:

        render_html(
            """
            <div class="stat-card">
                <div class="stat-number">💀</div>
                <div class="stat-label">
                    Disasterclass
                </div>
            </div>
            """
        )

    with c3:

        render_html(
            """
            <div class="stat-card">
                <div class="stat-number">🎙️</div>
                <div class="stat-label">
                    Fan Interview
                </div>
            </div>
            """
        )

    st.info(
        f"Press **Analyse {selected_league}** above "
        f"to generate the Gameweek {gw} newspaper."
    )

    st.stop()


# ============================================================
# GET DATA
# ============================================================

df = st.session_state[
    "league_df"
]

league_name = st.session_state[
    "league_name"
]

gw = st.session_state[
    "gw"
]

awards = get_awards(
    df
)


# ============================================================
# FRONT PAGE HERO
# ============================================================

winner = awards[
    "manager"
]

render_html(
    f"""
    <div class="hero">

        <div class="hero-ball">
            ⚽
        </div>

        <div class="hero-kicker">
            GAMEWEEK {gw} •
            {html_lib.escape(selected_league)}
        </div>

        <div class="hero-title">
            {html_lib.escape(winner["name"])}
            TAKES GAMEWEEK HONOURS
        </div>

        <p>
            The weekly leaderboard belongs to
            <b>{html_lib.escape(winner["name"])}</b>.
        </p>

        <div class="hero-points">
            {safe_int(winner["gw_points"])} POINTS
        </div>

    </div>
    """
)


# ============================================================
# WEEKLY PODIUM
# ============================================================

st.markdown(
    '<div class="section-title">🏆 THE WEEKLY PODIUM</div>',
    unsafe_allow_html=True
)

weekly = df.sort_values(
    "gw_points",
    ascending=False
).head(3)

if len(weekly) >= 3:

    first = weekly.iloc[0]
    second = weekly.iloc[1]
    third = weekly.iloc[2]

    render_html(
        f"""
        <div class="podium-wrap">

            <div class="podium-title">
                🏆 GAMEWEEK PODIUM
            </div>

            <div class="podium">

                <div class="podium-box podium-second">
                    <div class="podium-medal">🥈</div>
                    <div class="podium-name">
                        {html_lib.escape(second["name"])}
                    </div>
                    <div class="podium-points">
                        {safe_int(second["gw_points"])}
                    </div>
                    <div>points</div>
                </div>

                <div class="podium-box podium-first">
                    <div class="podium-medal">🥇</div>
                    <div class="podium-name">
                        {html_lib.escape(first["name"])}
                    </div>
                    <div class="podium-points">
                        {safe_int(first["gw_points"])}
                    </div>
                    <div>points</div>
                </div>

                <div class="podium-box podium-third">
                    <div class="podium-medal">🥉</div>
                    <div class="podium-name">
                        {html_lib.escape(third["name"])}
                    </div>
                    <div class="podium-points">
                        {safe_int(third["gw_points"])}
                    </div>
                    <div>points</div>
                </div>

            </div>

        </div>
        """
    )


# ============================================================
# AWARDS
# ============================================================

st.markdown(
    '<div class="section-title">🎖️ THE WEEKLY AWARDS</div>',
    unsafe_allow_html=True
)


def award_html(
    icon,
    title,
    row,
    number,
    text,
    colour
):

    return f"""
    <div class="award-card {colour}">

        <div class="award-icon">
            {icon}
        </div>

        <div class="award-title">
            {title}
        </div>

        <div class="award-number">
            {number}
        </div>

        <div class="award-manager">
            {html_lib.escape(row["name"])}
        </div>

        <div class="award-text">
            {html_lib.escape(text)}
        </div>

    </div>
    """


c1, c2, c3 = st.columns(3)

with c1:

    r = awards["manager"]

    render_html(
        award_html(
            "🏆",
            "Manager of the Week",
            r,
            safe_int(
                r["gw_points"]
            ),
            local_banter(
                r,
                "manager"
            ),
            "gold"
        )
    )

with c2:

    r = awards["disaster"]

    render_html(
        award_html(
            "💀",
            "Disasterclass",
            r,
            safe_int(
                r["gw_points"]
            ),
            local_banter(
                r,
                "disaster"
            ),
            "red"
        )
    )

with c3:

    r = awards["captain"]

    render_html(
        award_html(
            "🎯",
            "Captaincy King",
            r,
            safe_int(
                r["captain_effective"]
            ),
            (
                f"{r['actual_captain']} delivered "
                f"the captain double."
            ),
            "blue"
        )
    )


c1, c2, c3 = st.columns(3)

with c1:

    r = awards["captain_bad"]

    render_html(
        award_html(
            "🤡",
            "Captaincy Disaster",
            r,
            safe_int(
                r["captain_effective"]
            ),
            (
                f"Captain: {r['captain']}. "
                f"Effective captain points: "
                f"{safe_int(r['captain_effective'])}."
            ),
            "red"
        )
    )

with c2:

    r = awards["bench"]

    render_html(
        award_html(
            "🪑",
            "Bench Blunder",
            r,
            safe_int(
                r["bench_points"]
            ),
            (
                f"{safe_int(r['bench_points'])} "
                f"unused points left behind."
            ),
            "orange"
        )
    )

with c3:

    r = awards["riser"]

    movement = safe_int(
        r["rank_change"]
    )

    render_html(
        award_html(
            "📈",
            "Biggest Riser",
            r,
            (
                f"+{movement}"
                if movement >= 0
                else str(movement)
            ),
            (
                "Places climbed in the overall "
                "rankings."
            ),
            "green"
        )
    )


# ============================================================
# FAN INTERVIEW
# ============================================================

st.markdown(
    '<div class="section-title">🎙️ FAN INTERVIEW</div>',
    unsafe_allow_html=True
)

fan = create_fallback_fan_interview(
    df,
    awards
)

qa_html = ""

for speaker, answer in fan["qa"]:

    if speaker == "Reporter":

        qa_html += f"""
        <div class="question">
            🎤 {html_lib.escape(answer)}
        </div>
        """

    else:

        qa_html += f"""
        <div class="answer">
            🗣️ {html_lib.escape(answer)}
        </div>
        """

render_html(
    f"""
    <div class="interview">

        <div class="interview-header">
            🎙️ THE MINI-LEAGUE FAN ZONE
        </div>

        <div class="interview-person">
            This week's target:
            {html_lib.escape(fan["target"])}
        </div>

        <p>
            {html_lib.escape(fan["intro"])}
        </p>

        {qa_html}

    </div>
    """
)


# ============================================================
# AI NEWSPAPER
# ============================================================

st.markdown(
    '<div class="section-title">📰 THE FULL NEWSPAPER</div>',
    unsafe_allow_html=True
)

if not GEMINI_AVAILABLE:

    st.warning(
        "The google-genai package is not installed. "
        "Add google-genai to requirements.txt."
    )

else:

    if get_gemini_client():

        st.success(
            f"🤖 Gemini AI connected — {GEMINI_MODEL}"
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

        article, error = generate_ai_review(
            league_name,
            gw,
            df,
            awards
        )

    if article:

        st.session_state[
            "article"
        ] = article

        st.session_state.pop(
            "ai_error",
            None
        )

        st.rerun()

    else:

        st.session_state[
            "ai_error"
        ] = (
            error
            or "Unknown Gemini error."
        )


if "ai_error" in st.session_state:

    st.error(
        "Gemini could not write the newspaper.\n\n"
        f"Error: {st.session_state['ai_error']}\n\n"
        "If this says 429 or 503, try again shortly."
    )


# ============================================================
# SHOW AI ARTICLE
# ============================================================

if "article" in st.session_state:

    article = st.session_state[
        "article"
    ]

    render_html(
        '<div class="article">'
    )

    st.markdown(
        article
    )

    render_html(
        '</div>'
    )

    # --------------------------------------------------------
    # DOWNLOADS
    # --------------------------------------------------------

    st.markdown(
        '<div class="section-title">📥 DOWNLOAD THE NEWSPAPER</div>',
        unsafe_allow_html=True
    )

    txt_data = article_to_txt(
        article,
        league_name,
        gw
    )

    c1, c2 = st.columns(2)

    with c1:

        st.download_button(
            "📄 Download TXT",
            data=txt_data,
            file_name=(
                f"mini_league_times_"
                f"{selected_league.replace(' ', '_')}_"
                f"gw{gw}.txt"
            ),
            mime="text/plain",
            use_container_width=True
        )

    with c2:

        if REPORTLAB_AVAILABLE:

            pdf_data = article_to_pdf(
                article,
                league_name,
                gw,
                df,
                awards
            )

            st.download_button(
                "📰 Download Designed PDF",
                data=pdf_data,
                file_name=(
                    f"mini_league_times_"
                    f"{selected_league.replace(' ', '_')}_"
                    f"gw{gw}.pdf"
                ),
                mime="application/pdf",
                use_container_width=True
            )

        else:

            st.info(
                "Install reportlab to enable the "
                "designed PDF."
            )


# ============================================================
# FRAUD WATCH
# ============================================================

st.markdown(
    '<div class="section-title">🚨 FRAUD WATCH</div>',
    unsafe_allow_html=True
)

worst = awards[
    "disaster"
]

captain_bad = awards[
    "captain_bad"
]

if (
    worst["id"]
    == captain_bad["id"]
):

    render_html(
        f"""
        <div class="fraud">

            <h2>
                🚨 FRAUD WATCH: UNDER INVESTIGATION
            </h2>

            <h1>
                {html_lib.escape(worst["name"])}
            </h1>

            <p>
                Bottom of the week AND captaincy disaster.
                The evidence is mounting.
            </p>

            <p>
                <b>
                    Charges:
                </b>
                questionable decision-making,
                suspicious tactical choices and
                general FPL incompetence.
            </p>

            <p>
                Verdict:
                <b>GUILTY OF BAD FPL MANAGEMENT.</b>
            </p>

        </div>
        """
    )

else:

    render_html(
        """
        <div class="story-card"
             style="background:#ecfdf5;border-color:#22c55e;">

            <h2>🚨 Fraud Watch</h2>

            <p>
                Nobody has earned a full Fraud Watch
                investigation this week.
            </p>

            <b>
                But we're watching...
            </b>

        </div>
        """
    )


# ============================================================
# TITLE RACE
# ============================================================

st.markdown(
    '<div class="section-title">🥊 THE TITLE RACE</div>',
    unsafe_allow_html=True
)

title = df.sort_values(
    "league_position"
).head(5)

title_rows = ""

for _, r in title.iterrows():

    position = safe_int(
        r["league_position"]
    )

    title_rows += f"""
    <div style="
        display:flex;
        justify-content:space-between;
        padding:9px 0;
        border-bottom:1px solid rgba(255,255,255,.2);
    ">
        <span>
            <b>{position}.</b>
            {html_lib.escape(r["name"])}
        </span>

        <b>
            {safe_int(r["total_points"])} pts
        </b>
    </div>
    """

render_html(
    f"""
    <div class="title-race">

        <h2>
            🥊 WHO WANTS THE CROWN?
        </h2>

        {title_rows}

    </div>
    """
)

if len(title) >= 2:

    gap = (
        safe_int(
            title.iloc[0]["total_points"]
        )
        -
        safe_int(
            title.iloc[1]["total_points"]
        )
    )

    st.success(
        f"👑 {title.iloc[0]['name']} leads "
        f"{title.iloc[1]['name']} by "
        f"{gap} points."
    )


# ============================================================
# WOODEN SPOON
# ============================================================

st.markdown(
    '<div class="section-title">🥄 WOODEN SPOON WATCH</div>',
    unsafe_allow_html=True
)

bottom = df.sort_values(
    "league_position",
    ascending=False
).head(3)

bottom_rows = ""

for _, r in bottom.iterrows():

    bottom_rows += f"""
    <div style="
        display:flex;
        justify-content:space-between;
        padding:10px 0;
        border-bottom:1px solid rgba(255,255,255,.2);
    ">

        <span>
            <b>{safe_int(r["league_position"])}.</b>
            {html_lib.escape(r["name"])}
        </span>

        <b>
            {safe_int(r["total_points"])} pts
        </b>

    </div>
    """

render_html(
    f"""
    <div class="wooden-spoon">

        <h2>
            🥄 THE BATTLE NOBODY WANTS TO WIN
        </h2>

        {bottom_rows}

        <p>
            Somebody has to finish last.
            Unfortunately, these three are currently
            volunteering.
        </p>

    </div>
    """
)


# ============================================================
# TRANSFER DESK
# ============================================================

st.markdown(
    '<div class="section-title">💰 TRANSFER DESK</div>',
    unsafe_allow_html=True
)

transfer = awards[
    "transfer"
]

render_html(
    f"""
    <div class="story-card">

        <h2>
            💰 TRANSFER ACTIVITY
        </h2>

        <h3>
            {html_lib.escape(transfer["name"])}
        </h3>

        <p>
            Made
            <b>
                {safe_int(transfer["transfers"])}
            </b>
            transfers this Gameweek.
        </p>

        <p>
            Transfer hit:
            <b>
                -{safe_int(transfer["transfer_cost"])}
            </b>
        </p>

        <p>
            The question is whether this was
            <i>master planning</i>
            or
            <i>panic shopping</i>.
        </p>

    </div>
    """
)


# ============================================================
# LEAGUE TABLE
# ============================================================

st.markdown(
    '<div class="section-title">📊 THE LEAGUE TABLE</div>',
    unsafe_allow_html=True
)

table = df.sort_values(
    "league_position"
).copy()

table["Movement"] = (
    table["rank_change"]
    .apply(
        lambda x:
            f"⬆️ {safe_int(x)}"
            if safe_int(x) > 0
            else (
                f"⬇️ {abs(safe_int(x))}"
                if safe_int(x) < 0
                else "—"
            )
    )
)

display = table[
    [
        "league_position",
        "name",
        "team_name",
        "gw_points",
        "total_points",
        "Movement",
    ]
].copy()

display.columns = [
    "Pos",
    "Manager",
    "Team",
    f"GW {gw}",
    "Total",
    "Movement",
]

st.dataframe(
    display,
    use_container_width=True,
    hide_index=True,
)


# ============================================================
# MANAGER SPOTLIGHT
# ============================================================

st.markdown(
    '<div class="section-title">🔎 MANAGER SPOTLIGHT</div>',
    unsafe_allow_html=True
)

selected_manager = st.selectbox(
    "Choose a manager",
    df["name"].tolist()
)

manager = df[
    df["name"]
    == selected_manager
].iloc[0]


c1, c2, c3, c4 = st.columns(4)

with c1:

    render_html(
        f"""
        <div class="stat-card">

            <div class="stat-number">
                {safe_int(manager["gw_points"])}
            </div>

            <div class="stat-label">
                GAMEWEEK POINTS
            </div>

        </div>
        """
    )

with c2:

    render_html(
        f"""
        <div class="stat-card">

            <div class="stat-number">
                {safe_int(manager["total_points"])}
            </div>

            <div class="stat-label">
                TOTAL POINTS
            </div>

        </div>
        """
    )

with c3:

    render_html(
        f"""
        <div class="stat-card">

            <div class="stat-number">
                🎯
            </div>

            <div class="stat-label">
                {html_lib.escape(manager["captain"])}
            </div>

        </div>
        """
    )

with c4:

    render_html(
        f"""
        <div class="stat-card">

            <div class="stat-number">
                {safe_int(manager["bench_points"])}
            </div>

            <div class="stat-label">
                UNUSED BENCH POINTS
            </div>

        </div>
        """
    )


render_html(
    f"""
    <div class="story-card">

        <h3>
            🧑‍💼 {html_lib.escape(manager["name"])}
        </h3>

        <p>
            <b>Team:</b>
            {html_lib.escape(manager["team_name"])}
        </p>

        <p>
            <b>Captain:</b>
            {html_lib.escape(manager["captain"])}
            ({safe_int(manager["captain_effective"])}
            effective points)
        </p>

        <p>
            <b>Actual captain double:</b>
            {html_lib.escape(manager["actual_captain"])}
        </p>

        <p>
            <b>Vice Captain:</b>
            {html_lib.escape(manager["vice"])}
        </p>

        <p>
            <b>Transfers:</b>
            {safe_int(manager["transfers"])}
            |
            <b>Hit:</b>
            -{safe_int(manager["transfer_cost"])}
        </p>

        <p>
            <b>Biggest bench regret:</b>
            {html_lib.escape(manager["biggest_bench"])}
            ({safe_int(manager["biggest_bench_points"])} points)
        </p>

        <p>
            <b>Starting XI:</b>
            {html_lib.escape(
                ", ".join(
                    manager["starting_names"]
                )
            )}
        </p>

    </div>
    """
)


# ============================================================
# DATA ACCURACY
# ============================================================

with st.expander(
    "🔧 Data accuracy check"
):

    st.caption(
        "The official FPL history score is always used "
        "for the league and newspaper."
    )

    check = df[
        [
            "name",
            "gw_points",
            "calculated_team_points",
            "captain",
            "actual_captain",
            "captain_effective",
            "bench_points",
        ]
    ].copy()

    check["Difference"] = (
        check["gw_points"]
        -
        check["calculated_team_points"]
    )

    st.dataframe(
        check,
        use_container_width=True,
        hide_index=True
    )

    mismatches = check[
        check["Difference"] != 0
    ]

    if mismatches.empty:

        st.success(
            "All reconstructed scores match "
            "the official FPL Gameweek scores."
        )

    else:

        st.warning(
            f"{len(mismatches)} manager(s) have "
            f"a score difference. The official "
            f"FPL history score remains authoritative."
        )


# ============================================================
# FOOTER
# ============================================================

render_html(
    f"""
    <div class="footer">

        📰 <b>THE MINI-LEAGUE TIMES</b>

        <br><br>

        {html_lib.escape(selected_league)}
        • League {league_id}
        • Gameweek {gw}

        <br>

        Official data from the Fantasy Premier League API

        <br><br>

        "Where your mates' FPL mistakes become public knowledge."

    </div>
    """
)
