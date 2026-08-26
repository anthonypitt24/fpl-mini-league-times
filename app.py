import streamlit as st
import requests
import pandas as pd
import json
import os
import re
import html
from io import BytesIO
from datetime import datetime

# ============================================================
# OPTIONAL PDF SUPPORT
# ============================================================

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import (
        getSampleStyleSheet,
        ParagraphStyle,
    )
    from reportlab.lib.enums import TA_CENTER
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        HRFlowable,
    )
    from reportlab.lib import colors
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


# ============================================================
# YOUR THREE LEAGUES
# ============================================================

LEAGUES = {
    "Dad V Lad": "1555183",
    "The Lads": "70818",
    "IMW": "637276",
}


# ============================================================
# GEMINI MODEL
# ============================================================

GEMINI_MODEL = "gemini-3.5-flash-lite"


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
<style>

html, body, [class*="css"] {
    font-family: Georgia, "Times New Roman", serif;
}

/* MAIN PAGE */

.main {
    background-color: #f7f4ec;
}

.block-container {
    padding-top: 1rem;
    padding-bottom: 4rem;
    max-width: 1400px;
}


/* NEWSPAPER MASTHEAD */

.masthead {
    background:
        radial-gradient(circle at top left, rgba(255,255,255,.16), transparent 35%),
        linear-gradient(135deg, #111111, #252525);
    color: white;
    padding: 28px 25px 20px 25px;
    border-radius: 18px;
    margin-bottom: 15px;
    border-bottom: 7px solid #d4af37;
    box-shadow: 0 8px 25px rgba(0,0,0,.18);
}

.masthead-title {
    text-align: center;
    font-family: Georgia, "Times New Roman", serif;
    font-size: 58px;
    font-weight: 900;
    letter-spacing: -3px;
    line-height: 1;
}

.masthead-subtitle {
    text-align: center;
    font-size: 17px;
    margin-top: 10px;
    opacity: .85;
    letter-spacing: 1px;
}

.edition-row {
    display: flex;
    justify-content: space-between;
    border-top: 1px solid rgba(255,255,255,.25);
    margin-top: 20px;
    padding-top: 10px;
    font-family: Arial, sans-serif;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 1px;
}


/* TICKER */

.ticker {
    background: #d4af37;
    color: #111;
    padding: 9px 15px;
    border-radius: 8px;
    font-family: Arial, sans-serif;
    font-weight: 800;
    margin-bottom: 18px;
}


/* HERO */

.hero {
    background:
        linear-gradient(
            135deg,
            rgba(255,255,255,.96),
            rgba(235,235,225,.96)
        );
    border: 1px solid #ccc;
    border-radius: 18px;
    padding: 30px;
    margin-bottom: 22px;
    box-shadow: 0 7px 20px rgba(0,0,0,.08);
}

.hero-kicker {
    font-family: Arial, sans-serif;
    font-size: 13px;
    font-weight: 800;
    letter-spacing: 2px;
    text-transform: uppercase;
}

.hero-headline {
    font-size: 42px;
    font-weight: 900;
    line-height: 1.05;
    margin: 8px 0;
}

.hero-score {
    font-family: Arial, sans-serif;
    font-size: 20px;
    font-weight: 800;
}


/* SECTION HEADERS */

.section-title {
    border-top: 4px solid #111;
    border-bottom: 2px solid #111;
    padding: 9px 0;
    margin: 28px 0 18px 0;
    font-size: 25px;
    font-weight: 900;
    text-transform: uppercase;
    letter-spacing: .5px;
}


/* CARDS */

.card {
    background: rgba(255,255,255,.90);
    border: 1px solid #d2d2d2;
    border-radius: 15px;
    padding: 20px;
    min-height: 190px;
    box-shadow: 0 4px 12px rgba(0,0,0,.06);
}

.card-dark {
    background: #171717;
    color: white;
    border-radius: 15px;
    padding: 22px;
    min-height: 190px;
}

.card-title {
    font-family: Arial, sans-serif;
    font-size: 13px;
    font-weight: 900;
    text-transform: uppercase;
    letter-spacing: 1px;
}

.card-number {
    font-family: Arial, sans-serif;
    font-size: 46px;
    font-weight: 900;
    line-height: 1;
    margin: 10px 0;
}

.card-manager {
    font-size: 20px;
    font-weight: 900;
}

.card-text {
    font-size: 14px;
    line-height: 1.45;
}


/* PODIUM */

.podium-card {
    text-align: center;
    background: white;
    border: 1px solid #ccc;
    border-radius: 15px;
    padding: 18px;
    box-shadow: 0 5px 15px rgba(0,0,0,.07);
}

.podium-place {
    font-family: Arial, sans-serif;
    font-size: 38px;
    font-weight: 900;
}

.podium-name {
    font-size: 21px;
    font-weight: 900;
}

.podium-points {
    font-family: Arial, sans-serif;
    font-size: 15px;
}


/* FAN INTERVIEW */

.interview {
    background:
        linear-gradient(
            135deg,
            #ffffff,
            #efefef
        );
    border-left: 7px solid #111;
    padding: 24px;
    border-radius: 5px 15px 15px 5px;
    box-shadow: 0 5px 15px rgba(0,0,0,.07);
}

.interviewer {
    font-family: Arial, sans-serif;
    font-size: 12px;
    text-transform: uppercase;
    font-weight: 900;
    letter-spacing: 1px;
}

.question {
    font-size: 18px;
    font-weight: 900;
    margin-top: 12px;
}

.answer {
    font-size: 17px;
    line-height: 1.5;
    margin: 7px 0 15px 0;
}

.fan-rating {
    font-family: Arial, sans-serif;
    font-size: 24px;
    font-weight: 900;
}


/* QUOTE */

.quote-box {
    background: #111;
    color: white;
    padding: 25px;
    border-radius: 15px;
    font-size: 21px;
    font-style: italic;
    line-height: 1.45;
}

.quote-author {
    font-family: Arial, sans-serif;
    font-size: 12px;
    font-style: normal;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 15px;
    opacity: .7;
}


/* FORM GUIDE */

.form-hot {
    border-left: 6px solid #1b7f3a;
    background: #eef8f1;
    padding: 15px;
    border-radius: 8px;
}

.form-cold {
    border-left: 6px solid #a33;
    background: #fff0f0;
    padding: 15px;
    border-radius: 8px;
}


/* TABLE */

.newspaper-table {
    background: white;
    border-radius: 12px;
    padding: 8px;
}


/* BIG NUMBER */

.big-stat {
    font-family: Arial, sans-serif;
    font-size: 50px;
    font-weight: 900;
}


/* FOOTER */

.footer {
    text-align: center;
    font-family: Arial, sans-serif;
    font-size: 11px;
    color: #777;
    padding: 25px 0;
    border-top: 1px solid #ccc;
}


/* SIDEBAR */

section[data-testid="stSidebar"] {
    background: #eeeae0;
}

</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# API HELPERS
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def get_json(url):
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20,
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
        f"{BASE}/leagues-classic/"
        f"{league_id}/standings/"
        f"?page_new_entries=1"
        f"&page_standings={page}"
        f"&phase=1"
    )

    return get_json(url)


@st.cache_data(ttl=300, show_spinner=False)
def get_manager_history(
    manager_id,
):
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
def get_live_gameweek(
    gw,
):
    return get_json(
        f"{BASE}/event/{gw}/live/"
    )


# ============================================================
# GENERAL HELPERS
# ============================================================

def safe_int(
    value,
    default=0,
):
    try:
        return int(value)
    except Exception:
        return default


def clean_text(
    text,
):
    if text is None:
        return ""

    return str(text).replace(
        "\x00",
        "",
    ).strip()


def get_current_gameweek(
    data,
):
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


# ============================================================
# PLAYER LOOKUP
# ============================================================

def build_player_lookup(
    data,
):
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

        player_id = safe_int(
            player.get("id")
        )

        players[player_id] = {
            "name":
                f'{player.get("first_name", "")} '
                f'{player.get("second_name", "")}'.strip(),

            "short_name":
                player.get(
                    "web_name",
                    "?",
                ),

            "team":
                teams.get(
                    safe_int(
                        player.get("team")
                    ),
                    "?",
                ),

            "position":
                safe_int(
                    player.get(
                        "element_type"
                    )
                ),

            "price":
                safe_int(
                    player.get(
                        "now_cost"
                    )
                ) / 10,

            "total_points":
                safe_int(
                    player.get(
                        "total_points"
                    )
                ),
        }

    return players


# ============================================================
# LIVE POINTS
# ============================================================

def build_live_points(
    live,
):
    result = {}

    if not live:
        return result

    for item in live.get(
        "elements",
        [],
    ):

        player_id = safe_int(
            item.get("id")
        )

        stats = item.get(
            "stats",
            {},
        )

        result[player_id] = {
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


# ============================================================
# LOAD ALL LEAGUE MANAGERS
# ============================================================

def get_all_league_managers(
    league_id,
):

    all_results = []

    for page in range(
        1,
        21,
    ):

        data = get_league_page(
            league_id,
            page,
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


# ============================================================
# PICK HELPERS
# ============================================================

def player_name(
    pick,
    players,
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
    live_points,
):

    if not pick:
        return 0

    player_id = safe_int(
        pick.get("element")
    )

    return safe_int(
        live_points
        .get(
            player_id,
            {},
        )
        .get(
            "points",
            0,
        )
    )


def pick_minutes(
    pick,
    live_points,
):

    if not pick:
        return 0

    player_id = safe_int(
        pick.get("element")
    )

    return safe_int(
        live_points
        .get(
            player_id,
            {},
        )
        .get(
            "minutes",
            0,
        )
    )


# ============================================================
# MANAGER ANALYSIS
# ============================================================

def analyse_manager(
    manager,
    gw,
    players,
    live_points,
):

    manager_id = safe_int(
        manager.get("entry")
    )

    history = get_manager_history(
        manager_id
    )

    picks_data = get_manager_picks(
        manager_id,
        gw,
    )

    if not history or not picks_data:
        return None

    current_history = None

    for event in history.get(
        "current",
        [],
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
        [],
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
        None,
    )

    original_vice = next(
        (
            p for p in picks
            if p.get(
                "is_vice_captain"
            )
        ),
        None,
    )

    actual_captain = next(
        (
            p for p in picks
            if safe_int(
                p.get("multiplier")
            ) == 2
        ),
        original_captain,
    )

    captain_name = player_name(
        original_captain,
        players,
    )

    actual_captain_name = player_name(
        actual_captain,
        players,
    )

    captain_raw_points = pick_points(
        original_captain,
        live_points,
    )

    actual_captain_points = pick_points(
        actual_captain,
        live_points,
    )

    captain_effective = (
        actual_captain_points * 2
    )

    captain_minutes = pick_minutes(
        original_captain,
        live_points,
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
            live_points,
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
                    live_points,
                ),
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
        rank,
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
            live_points,
        )
        * max(
            safe_int(
                p.get("multiplier")
            ),
            0,
        )
        for p in picks
    )

    return {

        "id":
            manager_id,

        "name":
            clean_text(
                manager.get(
                    "player_name",
                    "Unknown",
                )
            ),

        "team_name":
            clean_text(
                manager.get(
                    "entry_name",
                    "Unknown",
                )
            ),

        "league_position":
            safe_int(
                manager.get(
                    "rank"
                )
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
                players,
            ),

        "bench_points":
            bench_points,

        "biggest_bench":
            player_name(
                biggest_bench,
                players,
            ),

        "biggest_bench_points":
            (
                pick_points(
                    biggest_bench,
                    live_points,
                )
                if biggest_bench
                else 0
            ),

        "transfers":
            transfers,

        "transfer_cost":
            transfer_cost,

        "calculated_team_points":
            calculated_team_points,

        "starting_names":
            [
                player_name(
                    p,
                    players,
                )
                for p in starting
            ],
    }


# ============================================================
# ANALYSE LEAGUE
# ============================================================

def analyse_league(
    managers,
    gw,
    players,
    live_points,
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
            live_points,
        )

        if result:
            analysed.append(
                result
            )

        progress.progress(
            int(
                (
                    (i + 1)
                    / max(total, 1)
                )
                * 100
            )
        )

    progress.empty()

    return analysed


# ============================================================
# AWARDS
# ============================================================

def get_awards(
    df,
):

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
                df[
                    "captain_effective"
                ].idxmax()
            ],

        "captain_bad":
            df.loc[
                df[
                    "captain_effective"
                ].idxmin()
            ],

        "bench":
            df.loc[
                df[
                    "bench_points"
                ].idxmax()
            ],

        "riser":
            df.loc[
                df[
                    "rank_change"
                ].idxmax()
            ],

        "faller":
            df.loc[
                df[
                    "rank_change"
                ].idxmin()
            ],

        "transfer":
            df.loc[
                df[
                    "transfers"
                ].idxmax()
            ],
    }


# ============================================================
# BANter
# ============================================================

def local_banter(
    row,
    award,
):

    name = row["name"]

    points = safe_int(
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
            f"A performance that will definitely "
            f"be blamed on 'bad luck'."
        )

    if award == "captain":

        return (
            f"{name} got the captaincy spot on. "
            f"{row['actual_captain']} delivered "
            f"{safe_int(row['captain_effective'])} "
            f"effective points."
        )

    if award == "captain_bad":

        return (
            f"{name} trusted {row['captain']} "
            f"as captain and got "
            f"{safe_int(row['captain_effective'])} "
            f"effective points. "
            f"Bold. Very bold."
        )

    if award == "bench":

        return (
            f"{name} left "
            f"{safe_int(row['bench_points'])} "
            f"points unused on the bench. "
            f"That's not squad depth. "
            f"That's self-sabotage."
        )

    if award == "riser":

        return (
            f"{name} climbs "
            f"{abs(safe_int(row['rank_change']))} "
            f"places. Suddenly the title race "
            f"looks very interesting."
        )

    if award == "faller":

        return (
            f"{name} drops "
            f"{abs(safe_int(row['rank_change']))} "
            f"places. The less said, the better."
        )

    return ""


# ============================================================
# GEMINI CLIENT
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

    return genai.Client(
        api_key=api_key
    )


# ============================================================
# AI NEWSPAPER
# ============================================================

def generate_ai_review(
    league_name,
    gw,
    df,
    awards,
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
                    row[
                        "captain_effective"
                    ]
                ),

            "bench_points":
                safe_int(
                    row[
                        "bench_points"
                    ]
                ),

            "biggest_bench":
                row[
                    "biggest_bench"
                ],

            "biggest_bench_points":
                safe_int(
                    row[
                        "biggest_bench_points"
                    ]
                ),

            "rank_change":
                safe_int(
                    row[
                        "rank_change"
                    ]
                ),

            "transfers":
                safe_int(
                    row[
                        "transfers"
                    ]
                ),

            "transfer_cost":
                safe_int(
                    row[
                        "transfer_cost"
                    ]
                ),
        }


    prompt = f"""
You are the editor of a hilarious British
fantasy football newspaper.

NEWSPAPER:
THE MINI-LEAGUE TIMES

LEAGUE:
{league_name}

GAMEWEEK:
{gw}

Write a fun, competitive newspaper using
ONLY the supplied FPL data.

IMPORTANT:
Never invent a score.
Never invent a player.
Never invent a transfer.
Never invent a manager decision.
Never claim a real person said something
unless it is clearly labelled as fictional
newspaper banter.

The tone should be:

- British football banter
- funny
- competitive
- cheeky
- occasionally savage
- never genuinely nasty
- never discriminatory
- attack FPL decisions, not people's
personal lives or identities

Create the following sections:

1. BIG FRONT PAGE HEADLINE

Give the Gameweek a dramatic headline.

2. THE BIG STORY

Explain what happened at the top of the
Gameweek leaderboard.

3. MANAGER OF THE WEEK

Praise the winner.

4. DISASTERCLASS OF THE WEEK

Make fun of the lowest scorer.

5. CAPTAINCY CORNER

Compare the best and worst captain decisions.

6. BENCH OF SHAME

Highlight the manager who left the most
unused points on the bench.

7. THE TITLE RACE

Discuss the top of the league and whether
the leader looks safe.

8. HOT FORM

Identify managers whose combination of
weekly points and rank movement suggests
they are on the rise.

9. COLD FORM

Identify managers who appear to be struggling.

10. FRAUD WATCH

Choose one manager only if the supplied data
gives a genuinely funny FPL reason.

11. VAR INVESTIGATION

Pick the most questionable FPL decision
from the supplied data.

12. FAN INTERVIEW

This is VERY IMPORTANT.

Create a short fictional interview with
a passionate fan of ONE manager whose
decision-making deserves criticism.

The interview should contain:

REPORTER:
A question about the manager's decision.

FAN:
A funny answer.

REPORTER:
A second question.

FAN:
A second funny answer.

Then give:

VERDICT:
[1 to 5 stars]

The fan interview must be clearly presented
as newspaper-style fictional banter.

Base it on actual supplied data such as:
- poor captain
- bench points
- transfer activity
- poor weekly score
- rank fall

Do NOT invent events.

13. OFFICIAL EXCUSE OF THE WEEK

Create a funny fictional excuse that the
manager could supposedly use.

Clearly label it as fictional banter.

14. BACK PAGE

Finish with one final funny story.

Make the whole article feel like a proper
football newspaper rather than an AI report.

Use short paragraphs and strong headings.

Aim for approximately 1200-1600 words.

LEAGUE DATA:
{json.dumps(
    records,
    ensure_ascii=False,
    indent=2
)}

AWARDS:
{json.dumps(
    award_data,
    ensure_ascii=False,
    indent=2
)}
"""

    try:

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )

        text = getattr(
            response,
            "text",
            None,
        )

        if not text:

            return (
                None,
                "Gemini returned an empty response."
            )

        return (
            text.strip(),
            None,
        )

    except Exception as e:

        return (
            None,
            str(e),
        )


# ============================================================
# PDF
# ============================================================

def article_to_pdf(
    article,
    league_name,
    gw,
):

    if not REPORTLAB_AVAILABLE:
        return None

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "NewspaperTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
        fontSize=25,
        leading=28,
        spaceAfter=6,
    )

    subtitle_style = ParagraphStyle(
        "NewspaperSubtitle",
        parent=styles["Heading2"],
        alignment=TA_CENTER,
        fontSize=12,
        leading=15,
        spaceAfter=12,
    )

    body_style = ParagraphStyle(
        "NewspaperBody",
        parent=styles["BodyText"],
        fontSize=9.8,
        leading=14,
        spaceAfter=7,
    )

    heading_style = ParagraphStyle(
        "NewspaperHeading",
        parent=styles["Heading2"],
        fontSize=15,
        leading=18,
        spaceBefore=10,
        spaceAfter=6,
    )

    story = []

    story.append(
        Paragraph(
            "THE MINI-LEAGUE TIMES",
            title_style,
        )
    )

    story.append(
        Paragraph(
            f"Gameweek {gw} • "
            f"{html.escape(league_name)}",
            subtitle_style,
        )
    )

    story.append(
        HRFlowable(
            width="100%",
            thickness=2,
            spaceBefore=3,
            spaceAfter=10,
        )
    )

    for raw_line in article.splitlines():

        line = clean_text(
            raw_line
        )

        if not line:
            story.append(
                Spacer(
                    1,
                    4,
                )
            )
            continue

        safe = html.escape(
            line
        )

        if safe.startswith(
            "### "
        ):

            story.append(
                Paragraph(
                    safe[4:],
                    heading_style,
                )
            )

        elif safe.startswith(
            "## "
        ):

            story.append(
                Paragraph(
                    safe[3:],
                    heading_style,
                )
            )

        elif safe.startswith(
            "# "
        ):

            story.append(
                Paragraph(
                    safe[2:],
                    heading_style,
                )
            )

        else:

            safe = re.sub(
                r"\*\*(.*?)\*\*",
                r"<b>\1</b>",
                safe,
            )

            story.append(
                Paragraph(
                    safe,
                    body_style,
                )
            )

    doc.build(
        story
    )

    buffer.seek(0)

    return buffer.getvalue()


# ============================================================
# TXT
# ============================================================

def article_to_txt(
    article,
    league_name,
    gw,
):

    heading = (
        "THE MINI-LEAGUE TIMES\n"
        f"{league_name}\n"
        f"GAMEWEEK {gw}\n"
        + "=" * 65
        + "\n\n"
    )

    return (
        heading + article
    ).encode(
        "utf-8"
    )


# ============================================================
# MASTHEAD
# ============================================================

selected_league_name = st.session_state.get(
    "selected_league",
    "Dad V Lad",
)

selected_league_id = LEAGUES[
    selected_league_name
]


st.markdown(
    f"""
    <div class="masthead">

        <div class="masthead-title">
            THE MINI-LEAGUE TIMES
        </div>

        <div class="masthead-subtitle">
            WHERE YOUR MATES' FPL MISTAKES BECOME PUBLIC KNOWLEDGE
        </div>

        <div class="edition-row">
            <span>EST. 2026</span>
            <span>{selected_league_name}</span>
            <span>FANTASY FOOTBALL EDITION</span>
        </div>

    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.markdown(
    "## 📰 Newspaper Settings"
)

st.sidebar.markdown(
    "### Choose your mini-league"
)


league_choice = st.sidebar.selectbox(
    "Mini-League",
    list(LEAGUES.keys()),
    index=list(
        LEAGUES.keys()
    ).index(
        selected_league_name
    ),
)


if (
    league_choice
    != st.session_state.get(
        "selected_league"
    )
):

    st.session_state[
        "selected_league"
    ] = league_choice

    st.session_state.pop(
        "league_df",
        None,
    )

    st.session_state.pop(
        "article",
        None,
    )

    st.session_state.pop(
        "ai_error",
        None,
    )

    st.rerun()


league_id = LEAGUES[
    league_choice
]


st.sidebar.success(
    f"**{league_choice}**\n\n"
    f"League ID: `{league_id}`"
)


st.sidebar.markdown("---")

st.sidebar.markdown(
    "### ⚙️ Gameweek"
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


st.sidebar.markdown("---")

if st.sidebar.button(
    "🔄 Clear Cached Data",
    use_container_width=True,
):

    st.cache_data.clear()

    st.session_state.pop(
        "league_df",
        None,
    )

    st.session_state.pop(
        "article",
        None,
    )

    st.rerun()


# ============================================================
# LOAD FPL
# ============================================================

bootstrap = get_bootstrap()

if not bootstrap:

    st.error(
        "Could not connect to the official FPL API."
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


st.markdown(
    f"""
    <div class="ticker">
        ⚽ BREAKING: The {selected_league_name}
        edition is analysing Gameweek {gw}
        • Official FPL data
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# LOAD SELECTED LEAGUE
# ============================================================

with st.spinner(
    f"Loading {selected_league_name}..."
):

    league = get_league_page(
        league_id,
        1,
    )


if not league:

    st.error(
        f"Could not load FPL mini-league "
        f"{league_id}."
    )

    st.stop()


league_name = (
    league
    .get("league", {})
    .get(
        "name"
    )
    or selected_league_name
)


managers = get_all_league_managers(
    league_id
)


if not managers:

    st.error(
        "No managers were found "
        "in this league."
    )

    st.stop()


st.info(
    f"📰 **{league_name}** • "
    f"**{len(managers)} managers** • "
    f"League ID **{league_id}**"
)


# ============================================================
# ANALYSE BUTTON
# ============================================================

if st.button(
    f"🚀 ANALYSE {selected_league_name.upper()} "
    f"— GAMEWEEK {gw}",
    type="primary",
    use_container_width=True,
):

    with st.spinner(
        "Loading official Gameweek player scores..."
    ):

        live = get_live_gameweek(
            gw
        )


    if not live:

        st.error(
            "The FPL live Gameweek data "
            "could not be loaded. "
            "Try again shortly."
        )

        st.stop()


    live_points = build_live_points(
        live
    )


    with st.spinner(
        f"Analysing all {len(managers)} managers..."
    ):

        analysed = analyse_league(
            managers,
            gw,
            players,
            live_points,
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
    ] = league_name

    st.session_state[
        "gw"
    ] = gw

    st.session_state[
        "league_id"
    ] = league_id

    st.session_state[
        "live_loaded"
    ] = True


    st.session_state.pop(
        "article",
        None,
    )


    st.success(
        f"Analysis complete — "
        f"{len(df)} managers processed."
    )


# ============================================================
# WELCOME
# ============================================================

if "league_df" not in st.session_state:

    st.markdown(
        """
        <div class="hero">

            <div class="hero-kicker">
                Welcome to the newsroom
            </div>

            <div class="hero-headline">
                Your mates have made their FPL decisions.
                Now they have to answer for them.
            </div>

            <div class="hero-score">
                Choose a league and hit Analyse Gameweek
                to produce the next edition.
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


    c1, c2, c3 = st.columns(3)

    with c1:

        st.markdown(
            """
            <div class="card">

                <div class="card-title">
                    🏆 Awards
                </div>

                <div class="card-manager">
                    Manager of the Week
                </div>

                <p>
                    Captaincy King, Disasterclass,
                    Bench Blunder and more.
                </p>

            </div>
            """,
            unsafe_allow_html=True,
        )


    with c2:

        st.markdown(
            """
            <div class="card">

                <div class="card-title">
                    🎙️ Banter
                </div>

                <div class="card-manager">
                    Fan Interview
                </div>

                <p>
                    A fictional supporter gets
                    the microphone and starts
                    asking serious questions.
                </p>

            </div>
            """,
            unsafe_allow_html=True,
        )


    with c3:

        st.markdown(
            """
            <div class="card">

                <div class="card-title">
                    📰 Newspaper
                </div>

                <div class="card-manager">
                    Full Edition
                </div>

                <p>
                    Gemini turns the week's
                    FPL chaos into a proper
                    football newspaper.
                </p>

            </div>
            """,
            unsafe_allow_html=True,
        )


    st.stop()


# ============================================================
# RESTORE DATA
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

league_id = st.session_state[
    "league_id"
]


awards = get_awards(
    df
)


# ============================================================
# FRONT PAGE
# ============================================================

winner = awards[
    "manager"
]


st.markdown(
    f"""
    <div class="hero">

        <div class="hero-kicker">
            GAMEWEEK {gw} • FRONT PAGE
        </div>

        <div class="hero-headline">
            🏆 {winner["name"]}
            OWNS GAMEWEEK {gw}
        </div>

        <div class="hero-score">
            {safe_int(winner["gw_points"])}
            points puts {winner["name"]}
            top of the weekly leaderboard.
        </div>

        <p>
            <b>{winner["team_name"]}</b>
            • League position:
            <b>{safe_int(winner["league_position"])}</b>
        </p>

    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# PODIUM
# ============================================================

st.markdown(
    '<div class="section-title">🏆 The Weekly Podium</div>',
    unsafe_allow_html=True,
)


weekly = df.sort_values(
    "gw_points",
    ascending=False,
).head(3)


podium_cols = st.columns(3)

podium_emojis = [
    "🥇",
    "🥈",
    "🥉",
]


for i, (_, row) in enumerate(
    weekly.iterrows()
):

    with podium_cols[i]:

        st.markdown(
            f"""
            <div class="podium-card">

                <div class="podium-place">
                    {podium_emojis[i]}
                </div>

                <div class="podium-name">
                    {row["name"]}
                </div>

                <div class="podium-points">
                    {safe_int(row["gw_points"])}
                    points
                </div>

            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# WEEKLY AWARDS
# ============================================================

st.markdown(
    '<div class="section-title">🏅 The Weekly Awards</div>',
    unsafe_allow_html=True,
)


c1, c2, c3 = st.columns(3)


with c1:

    r = awards[
        "manager"
    ]

    st.markdown(
        f"""
        <div class="card">

            <div class="card-title">
                🏆 Manager of the Week
            </div>

            <div class="card-number">
                {safe_int(r["gw_points"])}
            </div>

            <div class="card-manager">
                {r["name"]}
            </div>

            <div class="card-text">
                {local_banter(r, "manager")}
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


with c2:

    r = awards[
        "disaster"
    ]

    st.markdown(
        f"""
        <div class="card">

            <div class="card-title">
                💀 Disasterclass
            </div>

            <div class="card-number">
                {safe_int(r["gw_points"])}
            </div>

            <div class="card-manager">
                {r["name"]}
            </div>

            <div class="card-text">
                {local_banter(r, "disaster")}
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


with c3:

    r = awards[
        "captain"
    ]

    st.markdown(
        f"""
        <div class="card">

            <div class="card-title">
                🎯 Captaincy King
            </div>

            <div class="card-number">
                {safe_int(r["captain_effective"])}
            </div>

            <div class="card-manager">
                {r["name"]}
            </div>

            <div class="card-text">
                {r["actual_captain"]}
                actually delivered the captain
                double.
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


c1, c2, c3 = st.columns(3)


with c1:

    r = awards[
        "captain_bad"
    ]

    st.markdown(
        f"""
        <div class="card">

            <div class="card-title">
                🤡 Captaincy Disaster
            </div>

            <div class="card-manager">
                {r["name"]}
            </div>

            <div class="card-text">

                Captain:
                <b>{r["captain"]}</b>

                <br><br>

                Effective points:
                <b>
                    {safe_int(
                        r["captain_effective"]
                    )}
                </b>

            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


with c2:

    r = awards[
        "bench"
    ]

    st.markdown(
        f"""
        <div class="card">

            <div class="card-title">
                🪑 Bench of Shame
            </div>

            <div class="card-number">
                {safe_int(r["bench_points"])}
            </div>

            <div class="card-manager">
                {r["name"]}
            </div>

            <div class="card-text">
                Unused points left behind.
                <br>
                Biggest regret:
                <b>{r["biggest_bench"]}</b>
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


with c3:

    r = awards[
        "faller"
    ]

    movement = safe_int(
        r["rank_change"]
    )

    st.markdown(
        f"""
        <div class="card">

            <div class="card-title">
                📉 Biggest Faller
            </div>

            <div class="card-number">
                {abs(movement)}
            </div>

            <div class="card-manager">
                {r["name"]}
            </div>

            <div class="card-text">
                Overall rank movement.
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# TITLE RACE
# ============================================================

st.markdown(
    '<div class="section-title">🥊 The Title Race</div>',
    unsafe_allow_html=True,
)


title = df.sort_values(
    "league_position"
).head(5)


for _, row in title.iterrows():

    position = safe_int(
        row["league_position"]
    )

    total = safe_int(
        row["total_points"]
    )

    st.progress(
        max(
            0.01,
            min(
                1.0,
                total /
                max(
                    safe_int(
                        title.iloc[0][
                            "total_points"
                        ]
                    ),
                    1,
                ),
            ),
        ),
        text=(
            f"{position}. "
            f"{row['name']} — "
            f"{total} points"
        ),
    )


if len(title) >= 2:

    gap = (
        safe_int(
            title.iloc[0][
                "total_points"
            ]
        )
        -
        safe_int(
            title.iloc[1][
                "total_points"
            ]
        )
    )

    st.info(
        f"🥊 **{title.iloc[0]['name']}** "
        f"leads **{title.iloc[1]['name']}** "
        f"by **{gap} points**."
    )


# ============================================================
# HOT / COLD FORM
# ============================================================

st.markdown(
    '<div class="section-title">🔥 Form Guide</div>',
    unsafe_allow_html=True,
)


form_hot = df.sort_values(
    [
        "rank_change",
        "gw_points",
    ],
    ascending=False,
).head(3)


form_cold = df.sort_values(
    [
        "rank_change",
        "gw_points",
    ],
    ascending=True,
).head(3)


c1, c2 = st.columns(2)


with c1:

    st.markdown(
        "### 🔥 HOT"
    )

    for _, row in form_hot.iterrows():

        st.markdown(
            f"""
            <div class="form-hot">

                <b>{row["name"]}</b>

                <br>

                {safe_int(row["gw_points"])}
                GW points

                •
                {'+' if safe_int(row["rank_change"]) >= 0 else ''}
                {safe_int(row["rank_change"])}
                rank movement

            </div>

            <br>
            """,
            unsafe_allow_html=True,
        )


with c2:

    st.markdown(
        "### 🧊 COLD"
    )

    for _, row in form_cold.iterrows():

        st.markdown(
            f"""
            <div class="form-cold">

                <b>{row["name"]}</b>

                <br>

                {safe_int(row["gw_points"])}
                GW points

                •
                {safe_int(row["rank_change"])}
                rank movement

            </div>

            <br>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# FRAUD WATCH
# ============================================================

st.markdown(
    '<div class="section-title">🚨 Fraud Watch</div>',
    unsafe_allow_html=True,
)


worst = awards[
    "disaster"
]

captain_bad = awards[
    "captain_bad"
]

bench_bad = awards[
    "bench"
]


fraud_candidates = []


if worst["gw_points"] == df[
    "gw_points"
].min():

    fraud_candidates.append(
        worst
    )


if (
    captain_bad[
        "captain_effective"
    ]
    <= 4
):

    fraud_candidates.append(
        captain_bad
    )


if (
    bench_bad[
        "bench_points"
    ]
    >= 8
):

    fraud_candidates.append(
        bench_bad
    )


if fraud_candidates:

    fraud = fraud_candidates[0]

    st.markdown(
        f"""
        <div class="card-dark">

            <div class="card-title">
                🚨 UNDER INVESTIGATION
            </div>

            <div class="card-number">
                {fraud["name"]}
            </div>

            <div class="card-text">

                The Mini-League Times
                editorial team has opened an
                investigation following a
                suspicious FPL decision.

                <br><br>

                Captain:
                <b>{fraud["captain"]}</b>

                <br>

                GW points:
                <b>{safe_int(fraud["gw_points"])}</b>

                <br>

                Bench points:
                <b>{safe_int(fraud["bench_points"])}</b>

            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )

else:

    st.info(
        "Nobody has earned a full Fraud Watch investigation this week. Yet."
    )


# ============================================================
# WOODEN SPOON
# ============================================================

st.markdown(
    '<div class="section-title">🥄 Wooden Spoon Watch</div>',
    unsafe_allow_html=True,
)


bottom = df.sort_values(
    "league_position",
    ascending=False,
).head(3)


c1, c2, c3 = st.columns(3)


for i, (_, row) in enumerate(
    bottom.iterrows()
):

    with [
        c1,
        c2,
        c3,
    ][i]:

        st.markdown(
            f"""
            <div class="card">

                <div class="card-title">
                    Position
                    {safe_int(
                        row["league_position"]
                    )}
                </div>

                <div class="card-manager">
                    {row["name"]}
                </div>

                <div class="card-number">
                    {safe_int(
                        row["total_points"]
                    )}
                </div>

                <div class="card-text">
                    Total points
                </div>

            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# AI NEWSPAPER
# ============================================================

st.markdown(
    '<div class="section-title">📰 The Full Newspaper</div>',
    unsafe_allow_html=True,
)


if not GEMINI_AVAILABLE:

    st.warning(
        "The google-genai package is not installed. "
        "Add google-genai to requirements.txt."
    )

else:

    if get_gemini_client():

        st.success(
            f"Gemini AI connected — {GEMINI_MODEL}"
        )

    else:

        st.warning(
            "Gemini AI is not connected. "
            "Add GEMINI_API_KEY to Streamlit Secrets."
        )


if st.button(
    "📰 WRITE THIS WEEK'S NEWSPAPER",
    type="primary",
    use_container_width=True,
):

    with st.spinner(
        "The journalists are arguing over the headlines..."
    ):

        article, error = generate_ai_review(
            league_name,
            gw,
            df,
            awards,
        )


    if article:

        st.session_state[
            "article"
        ] = article

        st.session_state.pop(
            "ai_error",
            None,
        )

        st.rerun()

    else:

        st.session_state[
            "ai_error"
        ] = (
            error
            or
            "Unknown Gemini error."
        )


if "ai_error" in st.session_state:

    st.error(
        "Gemini could not write the newspaper.\n\n"
        f"Error: {st.session_state['ai_error']}"
    )


# ============================================================
# DISPLAY AI NEWSPAPER
# ============================================================

if "article" in st.session_state:

    article = st.session_state[
        "article"
    ]


    st.markdown(
        """
        <div class="card">
        """,
        unsafe_allow_html=True,
    )


    st.markdown(
        article
    )


    st.markdown(
        "</div>",
        unsafe_allow_html=True,
    )


    # ========================================================
    # DOWNLOADS
    # ========================================================

    st.markdown(
        "### 📥 Download Edition"
    )


    txt_data = article_to_txt(
        article,
        league_name,
        gw,
    )


    d1, d2 = st.columns(2)


    with d1:

        st.download_button(
            "📄 Download TXT",
            data=txt_data,
            file_name=(
                f"mini_league_times_"
                f"{league_name.replace(' ', '_')}_"
                f"gw{gw}.txt"
            ),
            mime="text/plain",
            use_container_width=True,
        )


    with d2:

        if REPORTLAB_AVAILABLE:

            pdf_data = article_to_pdf(
                article,
                league_name,
                gw,
            )


            st.download_button(
                "📰 Download PDF",
                data=pdf_data,
                file_name=(
                    f"mini_league_times_"
                    f"{league_name.replace(' ', '_')}_"
                    f"gw{gw}.pdf"
                ),
                mime="application/pdf",
                use_container_width=True,
            )

        else:

            st.info(
                "Add reportlab to requirements.txt "
                "to enable PDF downloads."
            )


# ============================================================
# LEAGUE TABLE
# ============================================================

st.markdown(
    '<div class="section-title">📊 The League Table</div>',
    unsafe_allow_html=True,
)


table = df.sort_values(
    "league_position"
).copy()


table[
    "Movement"
] = table[
    "rank_change"
].apply(

    lambda x:
        f"⬆️ {safe_int(x)}"
        if safe_int(x) > 0

        else
        (
            f"⬇️ {abs(safe_int(x))}"
            if safe_int(x) < 0
            else "—"
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
    '<div class="section-title">🔎 Manager Spotlight</div>',
    unsafe_allow_html=True,
)


selected_manager = st.selectbox(
    "Choose a manager",
    df[
        "name"
    ].tolist(),
)


manager = df[
    df["name"]
    ==
    selected_manager
].iloc[0]


c1, c2, c3, c4 = st.columns(4)


c1.metric(
    "GW Points",
    safe_int(
        manager[
            "gw_points"
        ]
    ),
)


c2.metric(
    "Total",
    safe_int(
        manager[
            "total_points"
        ]
    ),
)


c3.metric(
    "Captain",
    manager[
        "captain"
    ],
)


c4.metric(
    "Unused Bench",
    safe_int(
        manager[
            "bench_points"
        ]
    ),
)


st.markdown(
    f"""
    **Captain:** {manager["captain"]}

    **Actual captain double:**
    {manager["actual_captain"]}

    **Effective captain points:**
    {safe_int(manager["captain_effective"])}

    **Vice Captain:**
    {manager["vice"]}

    **Transfers:**
    {safe_int(manager["transfers"])}

    **Transfer Hit:**
    -{safe_int(manager["transfer_cost"])}

    **Biggest unused bench regret:**
    {manager["biggest_bench"]}
    ({safe_int(manager["biggest_bench_points"])} points)

    **Starting XI:**
    {", ".join(manager["starting_names"])}
    """
)


# ============================================================
# DATA ACCURACY CHECK
# ============================================================

with st.expander(
    "🔧 Data Accuracy Check"
):

    st.caption(
        "This compares the official FPL Gameweek "
        "score with the score reconstructed from "
        "the returned picks."
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


    check[
        "Difference"
    ] = (
        check[
            "gw_points"
        ]
        -
        check[
            "calculated_team_points"
        ]
    )


    st.dataframe(
        check,
        use_container_width=True,
        hide_index=True,
    )


    mismatches = check[
        check[
            "Difference"
        ] != 0
    ]


    if mismatches.empty:

        st.success(
            "All reconstructed team scores "
            "match the official FPL Gameweek scores."
        )

    else:

        st.warning(
            f"{len(mismatches)} manager(s) have "
            "a score difference. The official "
            "FPL history score is always used "
            "for league rankings."
        )


# ============================================================
# FOOTER
# ============================================================

today = datetime.now().strftime(
    "%d %B %Y"
)


st.markdown(
    f"""
    <div class="footer">

        THE MINI-LEAGUE TIMES

        • {league_name}

        • Gameweek {gw}

        • League ID {league_id}

        • {today}

        <br><br>

        Official FPL data • Newspaper banter generated with AI

    </div>
    """,
    unsafe_allow_html=True,
)
