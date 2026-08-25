import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import json
import os
import io
import re

# ============================================================
# OPTIONAL GEMINI AI
# ============================================================

try:
    from google import genai
    GEMINI_AVAILABLE = True
except Exception:
    GEMINI_AVAILABLE = False

# ============================================================
# OPTIONAL PDF
# ============================================================

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        PageBreak
    )
    from reportlab.lib.units import mm

    REPORTLAB_AVAILABLE = True

except Exception:
    REPORTLAB_AVAILABLE = False


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
    color: #666;
    margin-bottom: 30px;
}

.headline {
    font-size: 30px;
    font-weight: 900;
    line-height: 1.1;
}

.story {
    background: #f7f7f7;
    padding: 20px;
    border-radius: 12px;
    margin-bottom: 15px;
}

.award {
    border: 1px solid #ddd;
    border-radius: 12px;
    padding: 18px;
    min-height: 170px;
}

.big-number {
    font-size: 42px;
    font-weight: 900;
}

.small-muted {
    color: #777;
    font-size: 14px;
}

.download-box {
    padding: 20px;
    border: 1px solid #ddd;
    border-radius: 12px;
    margin-top: 20px;
    margin-bottom: 20px;
}

hr {
    margin-top: 25px;
    margin-bottom: 25px;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# CONSTANTS
# ============================================================

BASE = "https://fantasy.premierleague.com/api"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


# ============================================================
# API HELPERS
# ============================================================

@st.cache_data(ttl=300)
def get_json(url):

    try:

        r = requests.get(
            url,
            headers=HEADERS,
            timeout=15
        )

        r.raise_for_status()

        return r.json()

    except Exception:

        return None


@st.cache_data(ttl=300)
def get_bootstrap():

    return get_json(
        f"{BASE}/bootstrap-static/"
    )


@st.cache_data(ttl=300)
def get_league(league_id):

    url = (
        f"{BASE}/leagues-classic/{league_id}/standings/"
        f"?page_new_entries=1"
        f"&page_standings=1"
        f"&phase=1"
    )

    return get_json(url)


@st.cache_data(ttl=300)
def get_manager_history(manager_id):

    return get_json(
        f"{BASE}/entry/{manager_id}/history/"
    )


@st.cache_data(ttl=300)
def get_manager_picks(manager_id, gw):

    return get_json(
        f"{BASE}/entry/{manager_id}/event/{gw}/picks/"
    )


@st.cache_data(ttl=300)
def get_manager_info(manager_id):

    return get_json(
        f"{BASE}/entry/{manager_id}/"
    )


# ============================================================
# FIND CURRENT GAMEWEEK
# ============================================================

def get_current_gameweek(data):

    events = data.get(
        "events",
        []
    )

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
# PLAYER LOOKUP
# ============================================================

def build_player_lookup(data):

    teams = {

        t["id"]: t["name"]

        for t in data.get(
            "teams",
            []
        )

    }

    players = {}

    for p in data.get(
        "elements",
        []
    ):

        first = p.get(
            "first_name",
            ""
        )

        second = p.get(
            "second_name",
            ""
        )

        players[p["id"]] = {

            "name":
                f"{first} {second}".strip(),

            "short_name":
                p.get(
                    "web_name",
                    ""
                ),

            "team":
                teams.get(
                    p.get("team"),
                    "?"
                ),

            "position":
                p.get(
                    "element_type"
                ),

            "points":
                p.get(
                    "total_points",
                    0
                ),

            "price":
                p.get(
                    "now_cost",
                    0
                ) / 10
        }

    return players


# ============================================================
# MINI LEAGUE DATA
# ============================================================

def get_all_league_managers(league):

    standings = league.get(
        "standings",
        {}
    )

    return standings.get(
        "results",
        []
    )


# ============================================================
# MANAGER ANALYSIS
# ============================================================

def analyse_manager(
    manager,
    gw,
    players
):

    manager_id = manager["entry"]

    history = get_manager_history(
        manager_id
    )

    picks = get_manager_picks(
        manager_id,
        gw
    )

    if not history:

        return None

    current_history = None

    for event in history.get(
        "current",
        []
    ):

        if event.get("event") == gw:

            current_history = event

            break

    if not current_history:

        return None

    if not picks:

        return None

    squad = picks.get(
        "picks",
        []
    )

    # --------------------------------------------------------
    # Starting XI
    # --------------------------------------------------------

    starting = [

        p

        for p in squad

        if p.get(
            "position",
            0
        ) <= 11
    ]

    # --------------------------------------------------------
    # Bench
    # --------------------------------------------------------

    bench = [

        p

        for p in squad

        if p.get(
            "position",
            0
        ) > 11
    ]

    # --------------------------------------------------------
    # Captain
    # --------------------------------------------------------

    captain = next(

        (
            p

            for p in squad

            if p.get(
                "is_captain"
            )
        ),

        None
    )

    # --------------------------------------------------------
    # Vice
    # --------------------------------------------------------

    vice = next(

        (
            p

            for p in squad

            if p.get(
                "is_vice_captain"
            )
        ),

        None
    )

    # --------------------------------------------------------
    # Helpers
    # --------------------------------------------------------

    def player_name(p):

        if not p:

            return "Unknown"

        return players.get(

            p.get("element"),

            {}

        ).get(

            "short_name",

            "Unknown"
        )

    def player_points(p):

        if not p:

            return 0

        return p.get(
            "stats",
            {}
        ).get(
            "total_points",
            0
        )

    # --------------------------------------------------------
    # Captain
    # --------------------------------------------------------

    captain_name = player_name(
        captain
    )

    captain_points = player_points(
        captain
    )

    captain_multiplier = (

        captain.get(
            "multiplier",
            1
        )

        if captain

        else 1
    )

    captain_effective = (

        captain_points
        *
        captain_multiplier
    )

    # --------------------------------------------------------
    # Bench
    # --------------------------------------------------------

    bench_points = sum(

        player_points(p)

        for p in bench
    )

    # --------------------------------------------------------
    # Starting XI
    # --------------------------------------------------------

    starting_points = sum(

        player_points(p)

        *
        p.get(
            "multiplier",
            1
        )

        for p in starting
    )

    # --------------------------------------------------------
    # Transfers
    # --------------------------------------------------------

    transfers = current_history.get(
        "event_transfers",
        0
    )

    transfer_cost = current_history.get(
        "event_transfers_cost",
        0
    )

    # --------------------------------------------------------
    # Overall Rank
    # --------------------------------------------------------

    rank = current_history.get(
        "overall_rank",
        0
    )

    last_rank = current_history.get(
        "last_rank",
        rank
    )

    # --------------------------------------------------------
    # League Position
    # --------------------------------------------------------

    league_position = manager.get(
        "rank",
        0
    )

    # --------------------------------------------------------
    # Biggest Bench Regret
    # --------------------------------------------------------

    bench_sorted = sorted(

        bench,

        key=lambda x:
            player_points(x),

        reverse=True
    )

    biggest_bench = (

        bench_sorted[0]

        if bench_sorted

        else None
    )

    biggest_bench_name = player_name(
        biggest_bench
    )

    biggest_bench_points = player_points(
        biggest_bench
    )

    # --------------------------------------------------------
    # Starting XI Names
    # --------------------------------------------------------

    starting_names = [

        player_name(p)

        for p in starting
    ]

    # --------------------------------------------------------
    # Return
    # --------------------------------------------------------

    return {

        "id":
            manager_id,

        "name":
            manager.get(
                "player_name",
                "Unknown"
            ),

        "team_name":
            manager.get(
                "entry_name",
                "Unknown"
            ),

        "league_position":
            league_position,

        "gw_points":
            current_history.get(
                "points",
                0
            ),

        "total_points":
            current_history.get(
                "total_points",
                0
            ),

        "rank":
            rank,

        "last_rank":
            last_rank,

        "rank_change":
            last_rank - rank,

        "captain":
            captain_name,

        "captain_points":
            captain_points,

        "captain_effective":
            captain_effective,

        "vice":
            player_name(vice),

        "bench_points":
            bench_points,

        "biggest_bench":
            biggest_bench_name,

        "biggest_bench_points":
            biggest_bench_points,

        "transfers":
            transfers,

        "transfer_cost":
            transfer_cost,

        "starting_points":
            starting_points,

        "starting_names":
            starting_names
    }


# ============================================================
# ANALYSE ENTIRE LEAGUE
# ============================================================

def analyse_league(
    league,
    gw,
    players
):

    managers = get_all_league_managers(
        league
    )

    analysed = []

    progress = st.progress(
        0
    )

    total = len(
        managers
    )

    for i, manager in enumerate(
        managers
    ):

        result = analyse_manager(

            manager,
            gw,
            players
        )

        if result:

            analysed.append(
                result
            )

        progress.progress(

            int(

                ((i + 1)
                /
                max(total, 1))
                *
                100
            )
        )

    progress.empty()

    return analysed


# ============================================================
# AWARDS
# ============================================================

def get_awards(df):

    awards = {}

    if df.empty:

        return awards

    awards["manager"] = df.loc[
        df["gw_points"].idxmax()
    ]

    awards["disaster"] = df.loc[
        df["gw_points"].idxmin()
    ]

    awards["captain"] = df.loc[
        df["captain_effective"].idxmax()
    ]

    awards["captain_bad"] = df.loc[
        df["captain_effective"].idxmin()
    ]

    awards["bench"] = df.loc[
        df["bench_points"].idxmax()
    ]

    awards["riser"] = df.loc[
        df["rank_change"].idxmax()
    ]

    awards["faller"] = df.loc[
        df["rank_change"].idxmin()
    ]

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
            f"with {points} points. Somebody check "
            f"whether they've suddenly started reading "
            f"the rules."
        )

    if award == "disaster":

        return (

            f"{name} finishes bottom of the weekly "
            f"pile with just {points} points. A performance "
            f"that will be quietly described as "
            f"'unlucky' in the group chat."
        )

    if award == "captain":

        return (

            f"{name} got the captaincy spot on with "
            f"{row['captain']} delivering "
            f"{row['captain_effective']} effective "
            f"captain points. Tactical genius."
        )

    if award == "captain_bad":

        return (

            f"{name} trusted {row['captain']} as captain "
            f"and was rewarded with "
            f"{row['captain_effective']} effective points. "
            f"Bold. Very bold."
        )

    if award == "bench":

        return (

            f"{name} left {row['bench_points']} points "
            f"on the bench. That's not squad depth. "
            f"That's self-sabotage."
        )

    if award == "riser":

        return (

            f"{name} climbs "
            f"{abs(int(row['rank_change']))} places. "
            f"Suddenly the title looks very interesting."
        )

    if award == "faller":

        return (

            f"{name} drops "
            f"{abs(int(row['rank_change']))} places. "
            f"The less said, the better."
        )

    return ""


# ============================================================
# GEMINI API KEY
# ============================================================

def get_gemini_key():

    # Streamlit Cloud Secrets
    try:

        if "GEMINI_API_KEY" in st.secrets:

            return st.secrets[
                "GEMINI_API_KEY"
            ]

    except Exception:

        pass

    # Local environment
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
    awards
):

    api_key = get_gemini_key()

    if not api_key:

        return None, (
            "GEMINI_API_KEY has not been configured."
        )

    if not GEMINI_AVAILABLE:

        return None, (
            "The google-genai package is not installed."
        )

    # --------------------------------------------------------
    # Create Gemini client
    # --------------------------------------------------------

    try:

        client = genai.Client(
            api_key=api_key
        )

    except Exception as e:

        return None, (
            f"Could not connect to Gemini: {e}"
        )

    # --------------------------------------------------------
    # Convert data
    # --------------------------------------------------------

    records = df.to_dict(
        orient="records"
    )

    award_data = {}

    for key, value in awards.items():

        award_data[key] = {

            "name":
                value["name"],

            "gw_points":
                int(
                    value["gw_points"]
                ),

            "captain":
                value["captain"],

            "captain_effective":
                int(
                    value[
                        "captain_effective"
                    ]
                ),

            "bench_points":
                int(
                    value[
                        "bench_points"
                    ]
                ),

            "rank_change":
                int(
                    value[
                        "rank_change"
                    ]
                ),

            "transfers":
                int(
                    value[
                        "transfers"
                    ]
                ),

            "transfer_cost":
                int(
                    value[
                        "transfer_cost"
                    ]
                )
        }

    # --------------------------------------------------------
    # Prompt
    # --------------------------------------------------------

    prompt = f"""
You are the editor of a funny British fantasy football
newspaper covering an FPL mini-league.

Write a Gameweek {gw} newspaper for:

{league_name}

The tone should be:

- funny
- competitive
- cheeky
- football-aware
- British banter
- occasionally savage
- never genuinely cruel
- never discriminatory
- never abusive

IMPORTANT:

Use ONLY the information supplied below.

Do NOT invent:

- scores
- players
- transfers
- captain choices
- league positions
- events
- injuries
- fixtures
- results

If information is not provided, do not pretend you know it.

The newspaper should contain:

1. BIG NEWSPAPER HEADLINE

2. MANAGER OF THE WEEK

Explain who won the Gameweek and why.

3. DISASTERCLASS OF THE WEEK

Give the bottom performer some cheeky FPL banter.

4. CAPTAINCY STORY

Discuss the best and worst captain decisions.

5. BENCH BLUNDER

Identify the biggest points left on the bench.

6. BIGGEST RISER

Discuss the biggest overall-rank improvement.

7. BIGGEST FALLER

Discuss the biggest fall.

8. TRANSFER STORY

Discuss the manager who made the most transfers.
Mention transfer hits if relevant.

9. TITLE RACE

Discuss the current top of the mini-league.

10. WOODEN SPOON WATCH

Discuss the bottom of the league.

11. FRAUD WATCH

Pick out a questionable FPL decision if the data supports it.

12. MANAGER SPOTLIGHTS

Mention several managers, not just the winner.

13. CLOSING COLUMN

Finish with a funny prediction or warning for the next Gameweek.

The newspaper should feel like a proper British football
newspaper covering a group of mates.

Use headings.

Use manager names naturally.

Praise managers who genuinely performed well.

If someone did badly, make fun of their FPL decisions,
not their personal characteristics.

Aim for approximately 900-1200 words.

LEAGUE DATA:

{json.dumps(records, indent=2)}

AWARDS:

{json.dumps(award_data, indent=2)}
"""

    # --------------------------------------------------------
    # Call Gemini
    # --------------------------------------------------------

    try:

        response = client.models.generate_content(

            model="gemini-3.7-flash",

            contents=prompt
        )

        article = getattr(
            response,
            "text",
            None
        )

        if not article:

            return None, (
                "Gemini returned an empty response."
            )

        return article, None

    except Exception as e:

        return None, (
            f"Gemini error: {e}"
        )


# ============================================================
# CREATE PDF
# ============================================================

def create_newspaper_pdf(
    article,
    league_name,
    gw
):

    if not REPORTLAB_AVAILABLE:

        return None

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(

        buffer,

        pagesize=A4,

        rightMargin=18 * mm,

        leftMargin=18 * mm,

        topMargin=18 * mm,

        bottomMargin=18 * mm
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(

        "NewspaperTitle",

        parent=styles["Title"],

        alignment=TA_CENTER,

        fontSize=24,

        leading=28,

        spaceAfter=8
    )

    subtitle_style = ParagraphStyle(

        "Subtitle",

        parent=styles["Normal"],

        alignment=TA_CENTER,

        fontSize=11,

        leading=15,

        spaceAfter=18
    )

    heading_style = ParagraphStyle(

        "Heading",

        parent=styles["Heading2"],

        fontSize=16,

        leading=20,

        spaceBefore=12,

        spaceAfter=7
    )

    body_style = ParagraphStyle(

        "Body",

        parent=styles["BodyText"],

        fontSize=10.5,

        leading=15,

        spaceAfter=8
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
            f"Gameweek {gw} — {league_name}",
            subtitle_style
        )
    )

    story.append(
        Spacer(
            1,
            5
        )
    )

    # --------------------------------------------------------
    # Clean article
    # --------------------------------------------------------

    lines = article.splitlines()

    for line in lines:

        line = line.strip()

        if not line:

            story.append(
                Spacer(
                    1,
                    4
                )
            )

            continue

        # Markdown headings
        if line.startswith(
            "### "
        ):

            text = line[4:]

            story.append(
                Paragraph(
                    text,
                    heading_style
                )
            )

        elif line.startswith(
            "## "
        ):

            text = line[3:]

            story.append(
                Paragraph(
                    text,
                    heading_style
                )
            )

        elif line.startswith(
            "# "
        ):

            text = line[2:]

            story.append(
                Paragraph(
                    text,
                    heading_style
                )
            )

        else:

            # Basic markdown cleanup
            text = line

            text = re.sub(
                r"\*\*(.*?)\*\*",
                r"<b>\1</b>",
                text
            )

            text = text.replace(
                "&",
                "&amp;"
            )

            # Restore HTML bold entities
            text = text.replace(
                "&lt;b&gt;",
                "<b>"
            )

            text = text.replace(
                "&lt;/b&gt;",
                "</b>"
            )

            story.append(
                Paragraph(
                    text,
                    body_style
                )
            )

    doc.build(
        story
    )

    buffer.seek(0)

    return buffer.getvalue()


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
    "⚙️ League Setup"
)

league_id = st.sidebar.text_input(

    "Classic Mini-League ID",

    placeholder="e.g. 123456"
)

gw_override = st.sidebar.number_input(

    "Gameweek",

    min_value=1,

    max_value=38,

    value=1
)

st.sidebar.caption(
    "Find the ID in the FPL mini-league URL."
)


# ============================================================
# LOAD FPL BASE DATA
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


# ============================================================
# GAMEWEEK SELECTION
# ============================================================

st.info(
    f"FPL currently reports Gameweek "
    f"**{current_gw}**."
)

use_gw = st.sidebar.checkbox(

    "Use current Gameweek automatically",

    value=True
)

gw = (

    current_gw

    if use_gw

    else gw_override
)


# ============================================================
# LOAD LEAGUE
# ============================================================

if league_id:

    league_id_clean = (

        league_id
        .strip()
        .replace(
            "/",
            ""
        )
    )

    with st.spinner(
        "Loading mini-league..."
    ):

        league = get_league(
            league_id_clean
        )

    if not league:

        st.error(
            "I couldn't find that mini-league. "
            "Check the league ID."
        )

        st.stop()

    league_name = (

        league.get(
            "league",
            {}
        ).get(
            "name",
            "FPL Mini-League"
        )
    )

    st.success(
        f"Loaded **{league_name}**"
    )

    standings = get_all_league_managers(
        league
    )

    if not standings:

        st.warning(
            "No managers were found."
        )

        st.stop()

    # --------------------------------------------------------
    # Analyse button
    # --------------------------------------------------------

    if st.button(

        f"🚀 Analyse Gameweek {gw}",

        type="primary",

        use_container_width=True
    ):

        with st.spinner(
            "Analysing every manager..."
        ):

            analysed = analyse_league(

                league,

                gw,

                players
            )

        if not analysed:

            st.error(

                "No manager data could be loaded "
                "for this Gameweek."
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

        # Clear previous newspaper
        st.session_state.pop(
            "article",
            None
        )


# ============================================================
# DISPLAY ANALYSIS
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

        </div>
        """,

        unsafe_allow_html=True
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

        {int(winner['gw_points'])} points puts

        <b>{winner['name']}</b>

        at the top of the weekly leaderboard.

        </p>

        </div>
        """,

        unsafe_allow_html=True
    )

    # ========================================================
    # WEEKLY AWARDS
    # ========================================================

    st.subheader(
        "🏆 The Weekly Awards"
    )

    c1, c2, c3 = st.columns(3)

    # --------------------------------------------------------
    # Manager
    # --------------------------------------------------------

    with c1:

        r = awards[
            "manager"
        ]

        st.markdown(

            f"""
            <div class="award">

            <h3>
            🏆 Manager of the Week
            </h3>

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
    # Disaster
    # --------------------------------------------------------

    with c2:

        r = awards[
            "disaster"
        ]

        st.markdown(

            f"""
            <div class="award">

            <h3>
            💀 Disasterclass
            </h3>

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
    # Captain
    # --------------------------------------------------------

    with c3:

        r = awards[
            "captain"
        ]

        st.markdown(

            f"""
            <div class="award">

            <h3>
            🎯 Captaincy King
            </h3>

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
    # Captain Disaster
    # --------------------------------------------------------

    with c1:

        r = awards[
            "captain_bad"
        ]

        st.markdown(

            f"""
            <div class="award">

            <h3>
            🤡 Captaincy Disaster
            </h3>

            <b>{r['name']}</b>

            <p>

            Captained {r['captain']}
            for {int(r['captain_effective'])}
            points.

            </p>

            </div>
            """,

            unsafe_allow_html=True
        )

    # --------------------------------------------------------
    # Bench
    # --------------------------------------------------------

    with c2:

        r = awards[
            "bench"
        ]

        st.markdown(

            f"""
            <div class="award">

            <h3>
            🪑 Bench Blunder
            </h3>

            <div class="big-number">
            {int(r['bench_points'])}
            </div>

            <b>{r['name']}</b>

            <p>
            Points left sitting on the bench.
            </p>

            </div>
            """,

            unsafe_allow_html=True
        )

    # --------------------------------------------------------
    # Riser
    # --------------------------------------------------------

    with c3:

        r = awards[
            "riser"
        ]

        st.markdown(

            f"""
            <div class="award">

            <h3>
            📈 Biggest Riser
            </h3>

            <div class="big-number">
            +{int(r['rank_change'])}
            </div>

            <b>{r['name']}</b>

            <p>
            The comeback is underway.
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

    api_key_exists = bool(
        get_gemini_key()
    )

    if not api_key_exists:

        st.warning(
            "Gemini is not connected yet. "
            "Add GEMINI_API_KEY to Streamlit Secrets."
        )

    elif not GEMINI_AVAILABLE:

        st.error(
            "Gemini package is missing. "
            "Add google-genai to requirements.txt."
        )

    else:

        st.success(
            "🤖 Gemini AI is connected."
        )

        if st.button(

            "📰 WRITE THE FULL NEWSPAPER",

            type="primary",

            use_container_width=True
        ):

            with st.spinner(

                "🖊️ The journalists are writing "
                "the Gameweek newspaper..."
            ):

                article, error = generate_ai_review(

                    league_name,

                    gw,

                    df,

                    awards
                )

            if error:

                st.error(
                    error
                )

            elif article:

                st.session_state[
                    "article"
                ] = article

                st.success(
                    "📰 Newspaper written!"
                )

    # ========================================================
    # DISPLAY NEWSPAPER
    # ========================================================

    if "article" in st.session_state:

        article = st.session_state[
            "article"
        ]

        st.markdown("---")

        st.markdown(
            "## 📰 THE MINI-LEAGUE TIMES"
        )

        st.caption(
            f"Gameweek {gw} • {league_name}"
        )

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

        # ====================================================
        # DOWNLOAD NEWSPAPER
        # ====================================================

        st.markdown(
            '<div class="download-box">',
            unsafe_allow_html=True
        )

        st.subheader(
            "📥 Download & Share"
        )

        st.write(
            "Save the newspaper and send it to "
            "your FPL group chat."
        )

        # ----------------------------------------------------
        # TXT DOWNLOAD
        # ----------------------------------------------------

        filename_base = (

            f"FPL_Mini_League_Times_"
            f"GW{gw}"
        )

        st.download_button(

            label="📄 Download Newspaper (TXT)",

            data=article,

            file_name=
                filename_base
                + ".txt",

            mime="text/plain",

            use_container_width=True
        )

        # ----------------------------------------------------
        # PDF DOWNLOAD
        # ----------------------------------------------------

        if REPORTLAB_AVAILABLE:

            pdf_data = create_newspaper_pdf(

                article,

                league_name,

                gw
            )

            if pdf_data:

                st.download_button(

                    label="📰 Download Newspaper (PDF)",

                    data=pdf_data,

                    file_name=
                        filename_base
                        + ".pdf",

                    mime="application/pdf",

                    use_container_width=True
                )

        else:

            st.info(
                "PDF download requires reportlab. "
                "Add reportlab to requirements.txt."
            )

        st.markdown(
            '</div>',
            unsafe_allow_html=True
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

    table["Movement"] = table[
        "rank_change"
    ].apply(

        lambda x:

        f"⬆️ {int(x)}"

        if x > 0

        else (

            f"⬇️ {abs(int(x))}"

            if x < 0

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

            "Movement"
        ]
    ].copy()

    display.columns = [

        "Pos",

        "Manager",

        "Team",

        f"GW {gw}",

        "Total",

        "Movement"
    ]

    st.dataframe(

        display,

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

        int(
            manager["gw_points"]
        )
    )

    c2.metric(

        "Total",

        int(
            manager["total_points"]
        )
    )

    c3.metric(

        "Captain",

        manager["captain"]
    )

    c4.metric(

        "Bench",

        int(
            manager["bench_points"]
        )
    )

    st.write(

        f"**Captain:** "
        f"{manager['captain']} "
        f"("
        f"{int(manager['captain_effective'])}"
        f" effective points)"
    )

    st.write(

        f"**Vice Captain:** "
        f"{manager['vice']}"
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
        f"("
        f"{int(manager['biggest_bench_points'])}"
        f" points)"
    )

    st.write(

        "**Starting XI:** "
        +
        ", ".join(
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

    if worst["id"] == captain_bad["id"]:

        st.warning(

            f"🚨 **{worst['name']}** is officially "
            f"on Fraud Watch after finishing the week "
            f"bottom and making a questionable captaincy "
            f"decision."
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

    for _, r in title.iterrows():

        st.write(

            f"**{int(r['league_position'])}. "
            f"{r['name']}** — "
            f"{int(r['total_points'])} points"
        )

    if len(title) >= 2:

        gap = (

            int(
                title.iloc[0][
                    "total_points"
                ]
            )

            -

            int(
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

    for _, r in bottom.iterrows():

        st.write(

            f"**{int(r['league_position'])}. "
            f"{r['name']}** — "
            f"{int(r['total_points'])} points"
        )


# ============================================================
# WELCOME SCREEN
# ============================================================

else:

    st.markdown(

        """
        ### 👋 Welcome to The Mini-League Times

        Enter your **FPL Classic Mini-League ID** in the
        sidebar and we'll turn your weekly FPL results into
        a full newspaper.

        You'll get:

        🏆 Manager of the Week

        💀 Disasterclass

        🎯 Captaincy Awards

        🪑 Bench Blunders

        📈 Biggest Risers

        📉 Biggest Fallers

        💰 Transfer analysis

        🚨 Fraud Watch

        🥊 Title Race

        🥄 Wooden Spoon Watch

        🔎 Manager Spotlight

        🤖 Gemini AI-written newspaper

        📄 Downloadable newspaper

        📰 Shareable PDF

        **Enter a league ID to get started.**
        """
    )
