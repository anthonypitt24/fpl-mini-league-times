import streamlit as st
import requests
import pandas as pd
import json
import os

# Optional AI
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

st.markdown(
    """
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

    hr {
        margin-top: 25px;
        margin-bottom: 25px;
    }

    </style>
    """,
    unsafe_allow_html=True
)


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
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=15
        )

        response.raise_for_status()

        return response.json()

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
def get_manager_picks(manager_id, gameweek):
    return get_json(
        f"{BASE}/entry/{manager_id}/event/{gameweek}/picks/"
    )


# ============================================================
# CURRENT GAMEWEEK
# ============================================================

def get_current_gameweek(data):

    events = data.get("events", [])

    for event in events:

        if event.get("is_current"):

            return event["id"]

    finished = [
        event["id"]
        for event in events
        if event.get("finished")
    ]

    if finished:
        return max(finished)

    return 1


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

        first_name = player.get(
            "first_name",
            ""
        )

        second_name = player.get(
            "second_name",
            ""
        )

        players[player["id"]] = {
            "name": (
                f"{first_name} {second_name}"
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

            "points": player.get(
                "total_points",
                0
            ),

            "price": player.get(
                "now_cost",
                0
            ) / 10
        }

    return players


# ============================================================
# LEAGUE MANAGERS
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
    gameweek,
    players
):

    manager_id = manager.get(
        "entry"
    )

    if not manager_id:
        return None

    history = get_manager_history(
        manager_id
    )

    picks = get_manager_picks(
        manager_id,
        gameweek
    )

    if not history or not picks:
        return None

    # --------------------------------------------------------
    # Find this Gameweek in history
    # --------------------------------------------------------

    current_history = None

    for event in history.get(
        "current",
        []
    ):

        if event.get(
            "event"
        ) == gameweek:

            current_history = event
            break

    if not current_history:
        return None

    # --------------------------------------------------------
    # Squad
    # --------------------------------------------------------

    squad = picks.get(
        "picks",
        []
    )

    if not squad:
        return None

    starting = [
        player
        for player in squad
        if player.get("position", 0) <= 11
    ]

    bench = [
        player
        for player in squad
        if player.get("position", 0) > 11
    ]

    captain = next(
        (
            player
            for player in squad
            if player.get("is_captain")
        ),
        None
    )

    vice = next(
        (
            player
            for player in squad
            if player.get("is_vice_captain")
        ),
        None
    )

    # --------------------------------------------------------
    # Helpers
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

        stats = player.get(
            "stats",
            {}
        )

        return stats.get(
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

    captain_multiplier = 1

    if captain:
        captain_multiplier = captain.get(
            "multiplier",
            1
        )

    captain_effective = (
        captain_points *
        captain_multiplier
    )

    # --------------------------------------------------------
    # Vice Captain
    # --------------------------------------------------------

    vice_name = player_name(
        vice
    )

    # --------------------------------------------------------
    # Bench
    # --------------------------------------------------------

    bench_points = sum(
        player_points(player)
        for player in bench
    )

    # --------------------------------------------------------
    # Starting XI
    # --------------------------------------------------------

    starting_points = sum(
        player_points(player) *
        player.get("multiplier", 1)
        for player in starting
    )

    starting_names = [
        player_name(player)
        for player in starting
    ]

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
    # Overall rank
    # --------------------------------------------------------

    rank = current_history.get(
        "overall_rank",
        0
    )

    last_rank = current_history.get(
        "last_rank",
        rank
    )

    rank_change = (
        last_rank - rank
    )

    # --------------------------------------------------------
    # Biggest bench regret
    # --------------------------------------------------------

    bench_sorted = sorted(
        bench,
        key=lambda player:
        player_points(player),
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
    # Return
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

        "league_position": manager.get(
            "rank",
            0
        ),

        "gw_points": current_history.get(
            "points",
            0
        ),

        "total_points": current_history.get(
            "total_points",
            0
        ),

        "rank": rank,

        "last_rank": last_rank,

        "rank_change": rank_change,

        "captain": captain_name,

        "captain_points": captain_points,

        "captain_effective": captain_effective,

        "vice": vice_name,

        "bench_points": bench_points,

        "biggest_bench": biggest_bench_name,

        "biggest_bench_points": biggest_bench_points,

        "transfers": transfers,

        "transfer_cost": transfer_cost,

        "starting_points": starting_points,

        "starting_names": starting_names
    }


# ============================================================
# ANALYSE ENTIRE LEAGUE
# ============================================================

def analyse_league(
    league,
    gameweek,
    players
):

    managers = get_all_league_managers(
        league
    )

    analysed = []

    progress = st.progress(0)

    total = len(managers)

    for index, manager in enumerate(
        managers
    ):

        result = analyse_manager(
            manager,
            gameweek,
            players
        )

        if result:
            analysed.append(result)

        progress.progress(
            int(
                (
                    (index + 1) /
                    max(total, 1)
                ) * 100
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
            f"with {points} points. "
            f"Somebody check whether they've "
            f"suddenly started reading the rules."
        )

    if award == "disaster":

        return (
            f"{name} finishes bottom of the "
            f"weekly pile with just {points} "
            f"points. A performance that will "
            f"be quietly described as 'unlucky' "
            f"in the group chat."
        )

    if award == "captain":

        return (
            f"{name} got the captaincy spot on "
            f"with {row['captain']} delivering "
            f"{int(row['captain_effective'])} "
            f"effective captain points. "
            f"Tactical genius."
        )

    if award == "captain_bad":

        return (
            f"{name} trusted {row['captain']} "
            f"as captain and was rewarded with "
            f"{int(row['captain_effective'])} "
            f"effective points. "
            f"Bold. Very bold."
        )

    if award == "bench":

        return (
            f"{name} left "
            f"{int(row['bench_points'])} "
            f"points on the bench. "
            f"That's not squad depth. "
            f"That's self-sabotage."
        )

    if award == "riser":

        return (
            f"{name} climbs "
            f"{abs(int(row['rank_change']))} "
            f"places. Suddenly the title looks "
            f"very interesting."
        )

    if award == "faller":

        return (
            f"{name} drops "
            f"{abs(int(row['rank_change']))} "
            f"places. The less said, the better."
        )

    return ""


# ============================================================
# GEMINI AI REVIEW
# ============================================================

def generate_ai_review(
    league_name,
    gameweek,
    df,
    awards
):

    api_key = None

    try:

        api_key = st.secrets.get(
            "GEMINI_API_KEY"
        )

    except Exception:

        api_key = os.environ.get(
            "GEMINI_API_KEY"
        )

    if not api_key:
        return None

    if not GEMINI_AVAILABLE:
        return None

    try:

        client = genai.Client(
            api_key=api_key
        )

        records = df.to_dict(
            orient="records"
        )

        award_data = {}

        for key, value in awards.items():

            award_data[key] = {
                "name": value["name"],
                "gw_points": int(
                    value["gw_points"]
                ),
                "captain": value["captain"],
                "captain_effective": int(
                    value["captain_effective"]
                ),
                "bench_points": int(
                    value["bench_points"]
                ),
                "rank_change": int(
                    value["rank_change"]
                )
            }

        prompt = f"""
You are the editor of a funny British
fantasy football newspaper covering an
FPL mini-league.

Write a Gameweek {gameweek} review.

League:
{league_name}

Tone:

- funny
- competitive
- cheeky
- football-aware
- British banter
- occasionally savage
- never genuinely cruel
- never discriminatory
- never abusive

Use ONLY the information supplied.

Do not invent scores, players,
transfers or events.

The article should contain:

1. BIG HEADLINE
2. Manager of the Week
3. Disasterclass of the Week
4. Captaincy story
5. Bench Blunder
6. Biggest Riser
7. Biggest Faller
8. Transfer story
9. TITLE RACE
10. WOODEN SPOON WATCH
11. FRAUD WATCH
12. Closing paragraph

If somebody performed well,
give them proper credit.

If somebody performed badly,
make fun of the FPL decisions,
not the person.

Keep the article around
700-1000 words.

LEAGUE DATA:

{json.dumps(records, indent=2)}

AWARDS:

{json.dumps(award_data, indent=2)}
"""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        return response.text

    except Exception as error:

        return (
            "AI review unavailable: "
            f"{error}"
        )


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">📰 THE MINI-LEAGUE TIMES</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    'Where your mates\' FPL mistakes become public knowledge.'
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
# LOAD FPL DATA
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

use_current = st.sidebar.checkbox(
    "Use current Gameweek automatically",
    value=True
)

if use_current:
    gameweek = current_gw
else:
    gameweek = gw_override


# ============================================================
# LOAD LEAGUE
# ============================================================

if league_id:

    league_id_clean = (
        league_id
        .strip()
        .replace("/", "")
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
        league
        .get("league", {})
        .get(
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
    # ANALYSE BUTTON
    # --------------------------------------------------------

    if st.button(
        f"🚀 Analyse Gameweek {gameweek}",
        type="primary",
        use_container_width=True
    ):

        with st.spinner(
            "Analysing every manager..."
        ):

            analysed = analyse_league(
                league,
                gameweek,
                players
            )

        if not analysed:

            st.error(
                "No manager data could be loaded "
                f"for Gameweek {gameweek}."
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
        ] = gameweek


# ============================================================
# DISPLAY RESULTS
# ============================================================

if "league_df" in st.session_state:

    df = st.session_state[
        "league_df"
    ]

    league_name = st.session_state[
        "league_name"
    ]

    gameweek = st.session_state[
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
        <h1>GAMEWEEK {gameweek}</h1>
        <h2>{league_name}</h2>
        </div>
        """,
        unsafe_allow_html=True
    )

    # ========================================================
    # MAIN HEADLINE
    # ========================================================

    winner = awards["manager"]

    st.markdown(
        f"""
        <div class="story">

        <div class="headline">
        🗞️ {winner['name']} TAKES GAMEWEEK HONOURS
        </div>

        <p>
        {int(winner['gw_points'])} points puts
        <b>{winner['name']}</b> at the top of
        the weekly leaderboard.
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
    # MANAGER OF THE WEEK
    # --------------------------------------------------------

    with c1:

        row = awards["manager"]

        st.markdown(
            f"""
            <div class="award">

            <h3>🏆 Manager of the Week</h3>

            <div class="big-number">
            {int(row['gw_points'])}
            </div>

            <b>{row['name']}</b>

            <p>
            {generate_local_banter(
                row,
                "manager"
            )}
            </p>

            </div>
            """,
            unsafe_allow_html=True
        )

    # --------------------------------------------------------
    # DISASTERCLASS
    # --------------------------------------------------------

    with c2:

        row = awards["disaster"]

        st.markdown(
            f"""
            <div class="award">

            <h3>💀 Disasterclass</h3>

            <div class="big-number">
            {int(row['gw_points'])}
            </div>

            <b>{row['name']}</b>

            <p>
            {generate_local_banter(
                row,
                "disaster"
            )}
            </p>

            </div>
            """,
            unsafe_allow_html=True
        )

    # --------------------------------------------------------
    # CAPTAIN KING
    # --------------------------------------------------------

    with c3:

        row = awards["captain"]

        st.markdown(
            f"""
            <div class="award">

            <h3>🎯 Captaincy King</h3>

            <div class="big-number">
            {int(row['captain_effective'])}
            </div>

            <b>{row['name']}</b>

            <p>
            {row['captain']} captaincy
            </p>

            </div>
            """,
            unsafe_allow_html=True
        )

    st.write("")

    # ========================================================
    # SECOND ROW
    # ========================================================

    c1, c2, c3 = st.columns(3)

    # --------------------------------------------------------
    # CAPTAINCY DISASTER
    # --------------------------------------------------------

    with c1:

        row = awards["captain_bad"]

        st.markdown(
            f"""
            <div class="award">

            <h3>🤡 Captaincy Disaster</h3>

            <b>{row['name']}</b>

            <p>
            Captained {row['captain']} for
            {int(row['captain_effective'])}
            effective points.
            </p>

            </div>
            """,
            unsafe_allow_html=True
        )

    # --------------------------------------------------------
    # BENCH BLUNDER
    # --------------------------------------------------------

    with c2:

        row = awards["bench"]

        st.markdown(
            f"""
            <div class="award">

            <h3>🪑 Bench Blunder</h3>

            <div class="big-number">
            {int(row['bench_points'])}
            </div>

            <b>{row['name']}</b>

            <p>
            Points left sitting on the bench.
            </p>

            </div>
            """,
            unsafe_allow_html=True
        )

    # --------------------------------------------------------
    # BIGGEST RISER
    # --------------------------------------------------------

    with c3:

        row = awards["riser"]

        st.markdown(
            f"""
            <div class="award">

            <h3>📈 Biggest Riser</h3>

            <div class="big-number">
            +{int(row['rank_change'])}
            </div>

            <b>{row['name']}</b>

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

    if st.button(
        "📰 Write The Full Newspaper",
        type="primary",
        use_container_width=True
    ):

        with st.spinner(
            "The journalists are preparing the story..."
        ):

            article = generate_ai_review(
                league_name,
                gameweek,
                df,
                awards
            )

        if article:

            st.session_state[
                "article"
            ] = article

        else:

            st.warning(
                "AI isn't configured. "
                "Add GEMINI_API_KEY to enable "
                "the full newspaper."
            )

    if "article" in st.session_state:

        st.markdown(
            '<div class="story">',
            unsafe_allow_html=True
        )

        st.markdown(
            st.session_state[
                "article"
            ]
        )

        st.markdown(
            "</div>",
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
        lambda value:
        f"⬆️ {int(value)}"
        if value > 0
        else (
            f"⬇️ {abs(int(value))}"
            if value < 0
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
        f"GW {gameweek}",
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
        f"**Captain:** {manager['captain']} "
        f"({int(manager['captain_effective'])} "
        f"effective points)"
    )

    st.write(
        f"**Vice Captain:** {manager['vice']}"
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

    worst = awards["disaster"]

    captain_bad = awards[
        "captain_bad"
    ]

    if worst["id"] == captain_bad["id"]:

        st.warning(
            f"🚨 **{worst['name']}** is officially "
            f"on Fraud Watch after finishing the "
            f"week bottom and making a questionable "
            f"captaincy decision."
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


# ============================================================
# WELCOME SCREEN
# ============================================================

else:

    st.markdown(
        """
        ### 👋 Welcome to The Mini-League Times

        Enter your **FPL Classic Mini-League ID**
        in the sidebar and we'll turn your weekly
        FPL results into a full newspaper.

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
        🎙️ AI-written weekly newspaper

        **Enter a league ID to get started.**
        """
    )
