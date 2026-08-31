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
# OPTIONAL PDF
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
        KeepTogether,
    )
    from reportlab.lib.units import mm

    REPORTLAB_AVAILABLE = True

except Exception:
    REPORTLAB_AVAILABLE = False


# ============================================================
# OPTIONAL GEMINI
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
# CONSTANTS
# ============================================================

BASE = "https://fantasy.premierleague.com/api"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/140 Safari/537.36"
    )
}

# ------------------------------------------------------------
# YOUR THREE LEAGUES
# ------------------------------------------------------------

LEAGUES = {
    "Dad V Lad": "1555183",
    "The Lads": "70818",
    "IMW": "637276",
}

# ------------------------------------------------------------
# GEMINI MODELS
#
# 3.6 is currently stable.
# We keep fallbacks so the app is less likely to break if
# Google's model availability changes again.
# ------------------------------------------------------------

GEMINI_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-3.5-flash-lite",
]


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
<style>

/* =========================================================
   GENERAL
   ========================================================= */

.block-container {
    padding-top: 1rem;
    padding-bottom: 3rem;
    max-width: 1450px;
}

body {
    background: #f4f1e8;
}

/* =========================================================
   NEWSPAPER MASTHEAD
   ========================================================= */

.newspaper {
    background:
        linear-gradient(
            135deg,
            #fffdf5 0%,
            #f8f1dc 100%
        );
    border: 3px solid #172033;
    border-radius: 18px;
    padding: 25px 25px 18px 25px;
    box-shadow: 0 8px 0 #172033;
    margin-bottom: 25px;
}

.masthead {
    text-align: center;
    font-family: Georgia, serif;
    font-size: 55px;
    font-weight: 900;
    letter-spacing: 2px;
    color: #172033;
    line-height: 1;
}

.masthead-sub {
    text-align: center;
    font-size: 15px;
    font-weight: 800;
    letter-spacing: 4px;
    color: #c69214;
    margin-top: 8px;
}

.edition-line {
    display: flex;
    justify-content: space-between;
    border-top: 2px solid #172033;
    border-bottom: 2px solid #172033;
    padding: 8px 4px;
    margin-top: 18px;
    font-weight: 800;
    color: #172033;
}

/* =========================================================
   BREAKING NEWS
   ========================================================= */

.breaking {
    background: #d9a928;
    color: #111827;
    border-radius: 10px;
    padding: 13px 18px;
    font-weight: 900;
    margin: 15px 0 25px 0;
    border: 2px solid #172033;
}

/* =========================================================
   FRONT PAGE HERO
   ========================================================= */

.hero {
    background:
        radial-gradient(
            circle at top right,
            rgba(255,255,255,.25),
            transparent 35%
        ),
        linear-gradient(
            135deg,
            #172033,
            #263b61
        );
    color: white;
    border-radius: 18px;
    padding: 30px;
    margin-bottom: 25px;
    border-left: 10px solid #e2b529;
    box-shadow: 0 8px 0 #101827;
}

.hero-kicker {
    color: #e2b529;
    font-weight: 900;
    letter-spacing: 3px;
    font-size: 14px;
}

.hero-title {
    font-family: Georgia, serif;
    font-size: 43px;
    font-weight: 900;
    line-height: 1.05;
    margin: 8px 0;
}

.hero-sub {
    font-size: 18px;
    opacity: .9;
}

/* =========================================================
   SECTION HEADINGS
   ========================================================= */

.section-title {
    font-family: Georgia, serif;
    font-size: 31px;
    font-weight: 900;
    color: #172033;
    border-bottom: 4px solid #d9a928;
    padding-bottom: 8px;
    margin-top: 35px;
    margin-bottom: 20px;
}

/* =========================================================
   CARDS
   ========================================================= */

.card {
    background: #fffdf7;
    border: 2px solid #172033;
    border-radius: 15px;
    padding: 20px;
    min-height: 190px;
    box-shadow: 0 5px 0 #172033;
    margin-bottom: 15px;
}

.card-red {
    border-top: 9px solid #e84c4c;
}

.card-green {
    border-top: 9px solid #2e9d61;
}

.card-gold {
    border-top: 9px solid #d9a928;
}

.card-blue {
    border-top: 9px solid #3976b8;
}

.card-title {
    font-weight: 900;
    font-size: 18px;
    color: #172033;
}

.card-number {
    font-size: 44px;
    font-weight: 900;
    color: #172033;
    line-height: 1;
    margin: 12px 0;
}

.card-name {
    font-size: 19px;
    font-weight: 900;
}

/* =========================================================
   PODIUM
   ========================================================= */

.podium {
    background: #fffdf7;
    border: 2px solid #172033;
    border-radius: 18px;
    padding: 20px;
    text-align: center;
    min-height: 230px;
    box-shadow: 0 6px 0 #172033;
}

.podium-medal {
    font-size: 42px;
}

.podium-name {
    font-size: 21px;
    font-weight: 900;
    color: #172033;
}

.podium-points {
    font-size: 33px;
    font-weight: 900;
    color: #c69214;
}

/* =========================================================
   FAN INTERVIEW
   ========================================================= */

.fan-interview {
    background:
        linear-gradient(
            135deg,
            #fffdf7,
            #f0ead8
        );
    border: 3px solid #172033;
    border-radius: 18px;
    padding: 25px;
    box-shadow: 0 7px 0 #172033;
    margin: 25px 0;
}

.fan-header {
    display: flex;
    gap: 12px;
    align-items: center;
    font-family: Georgia, serif;
    font-size: 28px;
    font-weight: 900;
    color: #172033;
}

.quote {
    font-family: Georgia, serif;
    font-size: 20px;
    line-height: 1.5;
    color: #283448;
    padding: 15px 0;
}

.quote-mark {
    font-size: 55px;
    font-family: Georgia, serif;
    color: #d9a928;
    float: left;
    margin-right: 8px;
}

/* =========================================================
   INVESTIGATION
   ========================================================= */

.investigation {
    background: #24191b;
    color: #fff;
    border-radius: 18px;
    padding: 25px;
    border: 3px solid #e84c4c;
    box-shadow: 0 7px 0 #111;
}

.investigation h2 {
    color: #ff6262;
    font-family: Georgia, serif;
}

/* =========================================================
   STAT STRIP
   ========================================================= */

.stat-strip {
    background: #172033;
    color: white;
    border-radius: 15px;
    padding: 18px;
    margin: 20px 0;
}

.stat-label {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 2px;
    opacity: .7;
}

.stat-value {
    font-size: 30px;
    font-weight: 900;
}

/* =========================================================
   AI ARTICLE
   ========================================================= */

.article {
    background: #fffdf7;
    border: 2px solid #172033;
    border-radius: 18px;
    padding: 30px;
    box-shadow: 0 7px 0 #172033;
}

.article h1,
.article h2,
.article h3 {
    font-family: Georgia, serif;
    color: #172033;
}

.article h2 {
    border-bottom: 2px solid #d9a928;
    padding-bottom: 5px;
}

/* =========================================================
   MINI GRAPHIC
   ========================================================= */

.pitch {
    background:
        linear-gradient(
            90deg,
            rgba(255,255,255,.08) 1px,
            transparent 1px
        ),
        linear-gradient(
            rgba(255,255,255,.08) 1px,
            transparent 1px
        ),
        #26734d;
    background-size: 40px 40px;
    border: 4px solid white;
    border-radius: 14px;
    height: 170px;
    position: relative;
    overflow: hidden;
    margin: 20px 0;
}

.pitch::before {
    content: "";
    position: absolute;
    left: 5%;
    right: 5%;
    top: 10%;
    bottom: 10%;
    border: 3px solid rgba(255,255,255,.7);
}

.pitch::after {
    content: "⚽";
    position: absolute;
    font-size: 65px;
    left: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
}


/* =========================================================
   WHATSAPP-FIRST FRONT PAGE
   ========================================================= */

.whatsapp-edition {
    background: #fffdf7;
    border: 3px solid #172033;
    border-radius: 18px;
    padding: 22px;
    margin: 20px 0 28px 0;
    box-shadow: 0 8px 0 #172033;
}

.wa-kicker {
    font-size: 12px;
    font-weight: 900;
    letter-spacing: 2px;
    color: #c69214;
    text-transform: uppercase;
}

.wa-headline {
    font-family: Georgia, serif;
    font-size: 42px;
    line-height: 1.02;
    font-weight: 900;
    color: #172033;
    margin: 7px 0 8px 0;
}

.wa-subhead {
    font-size: 17px;
    font-weight: 800;
    color: #596273;
    margin-bottom: 18px;
}

.wa-scoreboard {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    margin: 15px 0;
}

.wa-stat {
    background: #172033;
    color: white;
    border-radius: 12px;
    padding: 13px;
    min-height: 92px;
}

.wa-stat-label {
    font-size: 10px;
    letter-spacing: 1.4px;
    text-transform: uppercase;
    opacity: .72;
    font-weight: 900;
}

.wa-stat-value {
    font-size: 26px;
    font-weight: 900;
    margin-top: 5px;
}

.wa-stat-name {
    font-size: 13px;
    font-weight: 800;
    margin-top: 2px;
}

.wa-story-grid {
    display: grid;
    grid-template-columns: 1.15fr .85fr;
    gap: 14px;
    margin-top: 15px;
}

.wa-story {
    background: #f4f1e8;
    border: 2px solid #172033;
    border-radius: 14px;
    padding: 17px;
}

.wa-story.hot {
    background: #24191b;
    color: white;
    border-color: #e84c4c;
}

.wa-story-title {
    font-size: 13px;
    font-weight: 900;
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-bottom: 7px;
}

.wa-story-big {
    font-family: Georgia, serif;
    font-size: 24px;
    line-height: 1.08;
    font-weight: 900;
    margin-bottom: 6px;
}

.wa-story-text {
    font-size: 14px;
    line-height: 1.42;
}

.wa-line {
    background: #d9a928;
    color: #172033;
    border: 2px solid #172033;
    border-radius: 12px;
    padding: 15px 17px;
    margin-top: 14px;
    font-weight: 900;
}

.wa-line-label {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 5px;
}

.wa-line-quote {
    font-family: Georgia, serif;
    font-size: 23px;
    line-height: 1.12;
}

.wa-roast {
    background: #fffdf7;
    border: 3px solid #e84c4c;
    border-radius: 14px;
    padding: 17px;
    margin-top: 14px;
}

.wa-roast-title {
    color: #e84c4c;
    font-size: 12px;
    font-weight: 900;
    letter-spacing: 1.5px;
    text-transform: uppercase;
}

.wa-roast-manager {
    font-family: Georgia, serif;
    color: #172033;
    font-size: 27px;
    font-weight: 900;
    margin: 3px 0;
}

.wa-roast-score {
    font-size: 13px;
    font-weight: 900;
    color: #596273;
}

.wa-roast-copy {
    font-size: 16px;
    line-height: 1.4;
    margin-top: 8px;
}

@media (max-width: 850px) {
    .wa-scoreboard {
        grid-template-columns: repeat(2, 1fr);
    }

    .wa-story-grid {
        grid-template-columns: 1fr;
    }

    .wa-headline {
        font-size: 34px;
    }
}



/* =========================================================
   ULTIMATE PDT NEWSPAPER
   ========================================================= */

.pdt-front {
    background: #fffdf7;
    border: 3px solid #172033;
    border-radius: 4px;
    padding: 18px;
    margin: 12px 0 25px 0;
    box-shadow: 7px 7px 0 #172033;
}

.pdt-mastline {
    display: flex;
    justify-content: space-between;
    align-items: end;
    border-bottom: 5px solid #172033;
    padding-bottom: 8px;
    margin-bottom: 10px;
}

.pdt-kicker {
    font-size: 11px;
    font-weight: 900;
    letter-spacing: 2px;
    text-transform: uppercase;
}

.pdt-date {
    font-size: 10px;
    font-weight: 800;
    opacity: .7;
}

.pdt-main-headline {
    font-family: Georgia, serif;
    font-size: 45px;
    line-height: .98;
    font-weight: 900;
    text-transform: uppercase;
    margin: 12px 0 8px 0;
    color: #172033;
}

.pdt-deck {
    font-size: 17px;
    line-height: 1.25;
    font-weight: 800;
    color: #4e596b;
    border-bottom: 1px solid #172033;
    padding-bottom: 13px;
}

.pdt-hero {
    margin-top: 14px;
    background: #172033;
    color: white;
    padding: 18px;
    border-radius: 4px;
}

.pdt-hero-number {
    font-family: Georgia, serif;
    font-size: 58px;
    font-weight: 900;
    line-height: .9;
}

.pdt-hero-label {
    font-size: 11px;
    letter-spacing: 1.5px;
    font-weight: 900;
    text-transform: uppercase;
    opacity: .75;
}

.pdt-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-top: 12px;
}

.pdt-card {
    border: 2px solid #172033;
    padding: 14px;
    background: #f2eee2;
}

.pdt-card.red {
    background: #2a1b1e;
    color: white;
    border-color: #d74c4c;
}

.pdt-card.gold {
    background: #d9a928;
}

.pdt-card-title {
    font-size: 11px;
    font-weight: 900;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    margin-bottom: 5px;
}

.pdt-card-name {
    font-family: Georgia, serif;
    font-size: 25px;
    font-weight: 900;
    line-height: 1.02;
}

.pdt-card-score {
    font-size: 14px;
    font-weight: 900;
    margin: 6px 0;
}

.pdt-card-copy {
    font-size: 14px;
    line-height: 1.35;
}

.pdt-line {
    margin-top: 12px;
    border: 3px solid #172033;
    padding: 13px;
    background: #d9a928;
}

.pdt-line-title {
    font-size: 10px;
    letter-spacing: 1.5px;
    font-weight: 900;
    text-transform: uppercase;
}

.pdt-line-copy {
    font-family: Georgia, serif;
    font-size: 23px;
    font-weight: 900;
    line-height: 1.08;
    margin-top: 4px;
}

.pdt-roast-section {
    margin-top: 26px;
    border-top: 5px solid #172033;
    padding-top: 10px;
}

.pdt-roast-heading {
    font-family: Georgia, serif;
    font-size: 30px;
    font-weight: 900;
    text-transform: uppercase;
}

.pdt-roast {
    border-left: 6px solid #d74c4c;
    padding: 12px 16px;
    margin: 13px 0;
    background: #faf7ef;
}

.pdt-roast h3 {
    margin: 0 0 5px 0;
    font-family: Georgia, serif;
    font-size: 22px;
}

.pdt-roast p {
    margin: 0;
    font-size: 15px;
    line-height: 1.5;
}

@media (max-width: 750px) {
    .pdt-grid {
        grid-template-columns: 1fr;
    }

    .pdt-main-headline {
        font-size: 35px;
    }

    .pdt-hero-number {
        font-size: 48px;
    }
}

/* =========================================================
   FOOTER
   ========================================================= */

.footer {
    text-align: center;
    font-family: Georgia, serif;
    color: #596273;
    padding: 30px 0;
    border-top: 2px solid #c9c1aa;
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
def get_league_page(league_id, page):
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
def get_manager_picks(manager_id, gw):
    return get_json(
        f"{BASE}/entry/{manager_id}/event/{gw}/picks/"
    )


@st.cache_data(ttl=300, show_spinner=False)
def get_live_gameweek(gw):
    return get_json(
        f"{BASE}/event/{gw}/live/"
    )


# ============================================================
# GENERAL HELPERS
# ============================================================

def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def clean_text(value):
    if value is None:
        return ""

    return (
        str(value)
        .replace("\x00", "")
        .strip()
    )


def get_current_gameweek(data):

    if not data:
        return 1

    events = data.get("events", [])

    for event in events:

        if event.get("is_current"):
            return safe_int(event.get("id"), 1)

    finished = [
        safe_int(e.get("id"))
        for e in events
        if e.get("finished")
    ]

    return max(finished) if finished else 1


# ============================================================
# PLAYER DATA
# ============================================================

def build_player_lookup(data):

    teams = {
        safe_int(team.get("id")):
            team.get("name", "?")
        for team in data.get("teams", [])
    }

    players = {}

    for player in data.get("elements", []):

        pid = safe_int(player.get("id"))

        players[pid] = {
            "name": (
                f"{player.get('first_name', '')} "
                f"{player.get('second_name', '')}"
            ).strip(),

            "short_name":
                player.get("web_name", "?"),

            "team":
                teams.get(
                    safe_int(player.get("team")),
                    "?"
                ),

            "position":
                safe_int(player.get("element_type")),

            "price":
                player.get("now_cost", 0) / 10,

            "total_points":
                safe_int(player.get("total_points")),
        }

    return players


def build_live_points(live):

    result = {}

    if not live:
        return result

    for item in live.get("elements", []):

        pid = safe_int(item.get("id"))
        stats = item.get("stats", {})

        result[pid] = {
            "points":
                safe_int(stats.get("total_points")),

            "minutes":
                safe_int(stats.get("minutes")),

            "goals":
                safe_int(stats.get("goals_scored")),

            "assists":
                safe_int(stats.get("assists")),

            "bonus":
                safe_int(stats.get("bonus")),
        }

    return result


def player_name(pick, players):

    if not pick:
        return "Unknown"

    player = players.get(
        safe_int(pick.get("element"))
    )

    if player:
        return player["short_name"]

    return "Unknown"


def pick_points(pick, live_points):

    if not pick:
        return 0

    pid = safe_int(
        pick.get("element")
    )

    return safe_int(
        live_points.get(pid, {}).get(
            "points",
            0
        )
    )


# ============================================================
# LEAGUE MANAGERS
# ============================================================

def get_all_league_managers(league_id):

    results_all = []

    for page in range(1, 21):

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

        results_all.extend(results)

        if len(results) < 50:
            break

    return results_all


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

    captain_points = pick_points(
        original_captain,
        live_points
    )

    actual_captain_points = pick_points(
        actual_captain,
        live_points
    )

    captain_effective = (
        actual_captain_points * 2
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

    calculated_points = sum(
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

        "id":
            manager_id,

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
            captain_points,

        "actual_captain":
            actual_captain_name,

        "captain_effective":
            captain_effective,

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
            (
                pick_points(
                    biggest_bench,
                    live_points
                )
                if biggest_bench
                else 0
            ),

        "transfers":
            transfers,

        "transfer_cost":
            transfer_cost,

        "calculated_team_points":
            calculated_points,

        "starting_names":
            [
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
            analysed.append(result)

        progress.progress(
            int(
                ((i + 1)
                / max(total, 1))
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

    try:
        return genai.Client(
            api_key=api_key
        )

    except Exception:
        return None


# ============================================================
# AI REQUEST WITH MODEL FALLBACKS
# ============================================================

def ask_gemini(prompt):

    client = get_gemini_client()

    if not client:
        return None, "Gemini API key is not configured."

    errors = []

    for model in GEMINI_MODELS:

        try:

            response = client.models.generate_content(
                model=model,
                contents=prompt,
            )

            text = getattr(
                response,
                "text",
                None
            )

            if text:

                return (
                    text.strip(),
                    None,
                    model
                )

        except Exception as e:

            errors.append(
                f"{model}: {str(e)}"
            )

            continue

    return (
        None,
        "All Gemini models failed:\n\n"
        + "\n".join(errors),
        None
    )


# ============================================================
# AI NEWSPAPER
# ============================================================

def generate_ai_review(
    league_name,
    gw,
    df,
    awards
):
    records = df.to_dict(orient="records")

    prompt = f"""
You are the chief writer of THE MINI-LEAGUE TIMES, a fictional FPL
tabloid written for a WhatsApp group of friends.

This edition must be FUNNY, SAVAGE and ENTERTAINING, but the actual
FPL data must always be accurate.

LEAGUE:
{league_name}

GAMEWEEK:
{gw}

DATA:
{json.dumps(records, ensure_ascii=False, indent=2)}

EDITORIAL RULES
================
1. Roast the MANAGER'S FPL DECISIONS, not their real life.
2. Be genuinely savage. These are friends who WANT proper banter.
3. The worse the captaincy, transfer, benching or team selection,
   the harder you should go.
4. Never invent factual events, scores, players, transfers or quotes.
5. You may use ridiculous fictional comparisons, metaphors and
   exaggerated newspaper language.
6. Do NOT repeatedly use:
   "brave", "unlucky", "tactical genius", "cup of tea",
   "absolute scenes", "keep tinkering", "cry for help".
7. Avoid generic AI-sounding phrases.
8. Every manager's roast should have a different voice or joke.
9. Vary the comedy format between:
   tabloid scandal, football pundit, courtroom, police report,
   VAR decision, disciplinary hearing, corporate review,
   transfer-market analysis, mock documentary, press conference,
   election result, crime report, obituary, reality TV,
   breaking news, cooking show, weather report, etc.
10. Do NOT mention the comedy format. Just write it naturally.
11. Do not insult appearance, family, health, protected characteristics,
    relationships, employment or other real-life circumstances.

THE MOST IMPORTANT PART:
The newsletter has TWO layers.

LAYER A = FAST VISUAL COPY
Short pieces that appear on the front page.

LAYER B = THE WRITTEN NEWSPAPER
Proper, funny 100-150 word roasts that people will actually read and
copy into the WhatsApp group.

Return EXACTLY the following headings.

# HEADLINE
A huge 6-12 word tabloid headline based on the actual Gameweek.

# DECK
One catchy sentence.

# FRONT_PAGE_BLURB
40-70 words summarising the biggest story.

# KING_VISUAL
One sentence, maximum 25 words.

# DISASTER_VISUAL
One savage sentence, maximum 25 words.

# CAPTAIN_VISUAL
One savage sentence, maximum 25 words.

# BENCH_VISUAL
One savage sentence, maximum 25 words.

# ROAST_1
The best/winning manager.
100-140 words. Praise them while finding a funny way to make them
unbearable.

# ROAST_2
The biggest disaster manager.
100-160 words. This should be the most savage roast of the edition.

# ROAST_3
The worst captaincy decision.
80-130 words. Use the actual captain and points.

# ROAST_4
The worst bench decision.
80-130 words. Use actual bench points and players supplied.

# ROAST_5
Another genuinely funny manager/event from the data.
80-130 words. Choose something DIFFERENT from the previous four.

# LEAGUE_GOSSIP
60-100 words. 2-4 short fictional newspaper gossip bullets based on
REAL FPL events/data. Make them feel like ridiculous tabloid gossip.
Clearly fictional banter, not claims about real life.

# TITLE_RACE
50-80 words.

# WOODEN_SPOON
50-80 words.

# LINE_OF_THE_WEEK
One killer sentence suitable for copying directly into WhatsApp.

# SIGN_OFF
One fresh one-line signoff. Never use a standard motivational cliché.

LENGTH:
Approximately 750-950 words total.

QUALITY CONTROL:
- Use names exactly as supplied.
- Check all numbers against DATA before writing.
- Never claim someone captained a player unless the data says so.
- Never invent a transfer.
- Never invent a league position.
- If a category has no interesting event, choose another interesting event
  from the supplied data instead of inventing one.
"""

    result, error, model = ask_gemini(prompt)
    return result, error, model


# ============================================================
# FAN INTERVIEW
# ============================================================

def generate_fan_interview(
    league_name,
    gw,
    df,
    awards
):

    records = df.to_dict(
        orient="records"
    )

    worst = awards["disaster"]

    prompt = f"""

You are writing a short funny football-fan interview for a British
fantasy football newspaper.

League:
{league_name}

Gameweek:
{gw}

The fan is a fictional passionate supporter of this mini-league.

The fan has been asked to comment on the manager:
{worst["name"]}

Relevant data:

{json.dumps(worst.to_dict(), ensure_ascii=False, indent=2)}

The fan should particularly criticise poor FPL decision making.

Keep it playful rather than genuinely abusive.

Return EXACTLY this format:

FAN NAME: [funny fictional fan name]

Q: What did you make of {worst["name"]}'s Gameweek?
A: [answer]

Q: What was their biggest mistake?
A: [answer]

Q: Would you trust them to manage your club?
A: [answer]

Q: Final message for {worst["name"]}?
A: [one funny sentence]

Do not use HTML.
Do not use Markdown.
Do not invent statistics.
"""

    text, error, model = ask_gemini(
        prompt
    )

    return text, error, model


# ============================================================
# SAFE MARKDOWN
# ============================================================

def clean_ai_markdown(text):

    if not text:
        return ""

    # Remove accidental code fences.
    text = re.sub(
        r"```(?:markdown|md)?",
        "",
        text,
        flags=re.I
    )

    text = text.replace(
        "```",
        ""
    )

    # Remove HTML tags if Gemini ignores instruction.
    text = re.sub(
        r"<[^>]+>",
        "",
        text
    )

    return text.strip()


# ============================================================
# FAN INTERVIEW PARSER
# ============================================================

def parse_fan_interview(text):

    if not text:
        return {}

    text = clean_ai_markdown(
        text
    )

    result = {
        "fan": "Anonymous Supporter",
        "q1": "",
        "a1": "",
        "q2": "",
        "a2": "",
        "q3": "",
        "a3": "",
        "q4": "",
        "a4": "",
    }

    fan = re.search(
        r"FAN NAME:\s*(.*)",
        text,
        re.I
    )

    if fan:
        result["fan"] = fan.group(1).strip()

    matches = re.findall(
        r"Q:\s*(.*?)\s*A:\s*(.*?)(?=\s*Q:|$)",
        text,
        flags=re.I | re.S
    )

    for i, (q, a) in enumerate(
        matches[:4],
        start=1
    ):

        result[f"q{i}"] = q.strip()
        result[f"a{i}"] = a.strip()

    return result


# ============================================================
# LOCAL BANter
# ============================================================

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
            f"{name} wins Manager of the Week with {points} points. "
            "Annoyingly, the idiot appears to know what they're doing."
        )

    if award == "disaster":
        return (
            f"{name} bottoms out on {points} points. "
            "The FPL equivalent of turning up for five-a-side "
            "and forgetting your boots."
        )

    if award == "captain":
        return (
            f"{name} captained {row['actual_captain']} for "
            f"{safe_int(row['captain_effective'])} effective points. "
            "For one glorious week, the spreadsheets have worked."
        )

    if award == "captain_bad":
        return (
            f"{name} gave the armband to {row['captain']} and got "
            f"{safe_int(row['captain_effective'])} effective points. "
            "That wasn't a differential. That was a cry for help."
        )

    if award == "bench":
        return (
            f"{name} left {safe_int(row['bench_points'])} points "
            "on the bench. The substitutes appear to have been "
            "better at FPL than their manager."
        )

    if award == "riser":
        movement = safe_int(row["rank_change"])
        return (
            f"{name} climbs {abs(movement)} places. "
            "Someone has briefly discovered the secret of scoring points."
        )

    if award == "faller":
        movement = safe_int(row["rank_change"])
        return (
            f"{name} falls {abs(movement)} places. "
            "The title charge has encountered a rather large speed bump."
        )

    return ""


# ============================================================
# PDF
# ============================================================

def article_to_pdf(
    article,
    league_name,
    gw
):

    if not REPORTLAB_AVAILABLE:
        return None

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=17 * mm,
        leftMargin=17 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()

    masthead = ParagraphStyle(
        "Masthead",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=25,
        leading=29,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#172033"),
        spaceAfter=4,
    )

    subtitle = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontSize=10,
        leading=13,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#c69214"),
        spaceAfter=12,
    )

    heading = ParagraphStyle(
        "HeadingCustom",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=colors.HexColor("#172033"),
        spaceBefore=10,
        spaceAfter=6,
    )

    body = ParagraphStyle(
        "BodyCustom",
        parent=styles["BodyText"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#283448"),
        spaceAfter=7,
    )

    story = []

    story.append(
        Paragraph(
            "THE MINI-LEAGUE TIMES",
            masthead
        )
    )

    story.append(
        Paragraph(
            f"GAMEWEEK {gw} • {html.escape(league_name)}",
            subtitle
        )
    )

    # Gold divider.
    divider = Table(
        [[""]],
        colWidths=[175 * mm],
        rowHeights=[3 * mm],
    )

    divider.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    colors.HexColor("#d9a928"),
                ),
            ]
        )
    )

    story.append(divider)
    story.append(
        Spacer(1, 8)
    )

    for raw_line in article.splitlines():

        line = clean_text(
            raw_line
        )

        if not line:
            story.append(
                Spacer(1, 3)
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
                    heading
                )
            )

        elif safe.startswith(
            "## "
        ):

            story.append(
                Paragraph(
                    safe[3:],
                    heading
                )
            )

        elif safe.startswith(
            "# "
        ):

            story.append(
                Paragraph(
                    safe[2:],
                    heading
                )
            )

        else:

            safe = re.sub(
                r"\*\*(.*?)\*\*",
                r"<b>\1</b>",
                safe
            )

            story.append(
                Paragraph(
                    safe,
                    body
                )
            )

    doc.build(story)

    buffer.seek(0)

    return buffer.getvalue()


def article_to_txt(
    article,
    league_name,
    gw
):

    heading = (
        "THE MINI-LEAGUE TIMES\n"
        f"Gameweek {gw} — {league_name}\n"
        + "=" * 60
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

st.markdown(
    """
<div class="newspaper">

<div class="masthead">
📰 THE MINI-LEAGUE TIMES
</div>

<div class="masthead-sub">
WHERE YOUR MATES' FPL MISTAKES BECOME PUBLIC KNOWLEDGE
</div>

<div class="edition-line">
<span>⚽ FANTASY FOOTBALL EDITION</span>
<span>EST. 2026</span>
<span>🗞️ WEEKLY EDITION</span>
</div>

</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title(
    "📰 Newspaper Settings"
)

st.sidebar.markdown(
    "### Choose your mini-league"
)

selected_league = st.sidebar.selectbox(
    "Mini-league",
    list(LEAGUES.keys()),
)

LEAGUE_ID = LEAGUES[
    selected_league
]

st.sidebar.success(
    f"{selected_league}\n\n"
    f"League ID: {LEAGUE_ID}"
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

if st.sidebar.button(
    "🔄 Clear cached data",
    use_container_width=True
):

    st.cache_data.clear()

    for key in [
        "league_df",
        "article",
        "fan_interview",
        "ai_error",
        "fan_error",
    ]:

        st.session_state.pop(
            key,
            None
        )

    st.rerun()


# ============================================================
# LOAD FPL
# ============================================================

bootstrap = get_bootstrap()

if not bootstrap:

    st.error(
        "❌ Could not connect to the official FPL API."
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
<div class="breaking">
⚽ BREAKING: The <b>{selected_league}</b> edition
is analysing <b>Gameweek {gw}</b> • Official FPL data
</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# LOAD LEAGUE
# ============================================================

with st.spinner(
    f"Loading {selected_league}..."
):

    league = get_league_page(
        LEAGUE_ID,
        1
    )

if not league:

    st.error(
        f"❌ Could not load {selected_league}."
    )

    st.stop()

league_name = (
    league
    .get("league", {})
    .get("name")
    or selected_league
)

managers = get_all_league_managers(
    LEAGUE_ID
)

if not managers:

    st.error(
        "No managers were found in this league."
    )

    st.stop()


# ============================================================
# LEAGUE INFO
# ============================================================

st.markdown(
    f"""
<div class="stat-strip">

<div style="display:flex;justify-content:space-around;text-align:center;">

<div>
<div class="stat-label">League</div>
<div class="stat-value">{html.escape(league_name)}</div>
</div>

<div>
<div class="stat-label">Managers</div>
<div class="stat-value">{len(managers)}</div>
</div>

<div>
<div class="stat-label">Gameweek</div>
<div class="stat-value">{gw}</div>
</div>

</div>

</div>
""",
    unsafe_allow_html=True,
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
        "Loading official FPL Gameweek scores..."
    ):

        live = get_live_gameweek(
            gw
        )

    if not live:

        st.error(
            "The FPL live Gameweek data could not be loaded."
        )

        st.stop()

    live_points = build_live_points(
        live
    )

    with st.spinner(
        "Analysing every manager..."
    ):

        analysed = analyse_league(
            managers,
            gw,
            players,
            live_points
        )

    if not analysed:

        st.error(
            "No manager data could be loaded for this Gameweek."
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
        "selected_league"
    ] = selected_league

    # Clear previous newspaper when changing analysis.
    st.session_state.pop(
        "article",
        None
    )

    st.session_state.pop(
        "fan_interview",
        None
    )

    st.success(
        f"Analysis complete — {len(df)} managers processed."
    )


# ============================================================
# WAITING SCREEN
# ============================================================

if (
    "league_df" not in st.session_state
    or st.session_state.get(
        "selected_league"
    ) != selected_league
):

    st.markdown(
        """
<div class="hero">

<div class="hero-kicker">
THE FRONT PAGE
</div>

<div class="hero-title">
Your weekly FPL humiliation starts here.
</div>

<div class="hero-sub">
Choose a mini-league, analyse the Gameweek,
then let the newspaper decide who is a genius
and who needs their FPL licence revoked.
</div>

</div>
""",
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        st.markdown(
            """
<div class="card card-gold">

<div class="card-title">
🏆 WEEKLY AWARDS
</div>

<p>
Manager of the Week<br>
Disasterclass<br>
Captaincy King<br>
Bench Blunder<br>
Biggest Riser
</p>

</div>
""",
            unsafe_allow_html=True,
        )

    with c2:

        st.markdown(
            """
<div class="card card-blue">

<div class="card-title">
🎙️ FAN INTERVIEW
</div>

<p>
A fictional supporter gives
their completely unbiased opinion
on the week's worst management.
</p>

</div>
""",
            unsafe_allow_html=True,
        )

    with c3:

        st.markdown(
            """
<div class="card card-red">

<div class="card-title">
🚨 FRAUD WATCH
</div>

<p>
Someone is going to be investigated.
Someone is going to regret their
captaincy decision.
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
GAMEWEEK {gw} • {html.escape(league_name)}
</div>

<div class="hero-title">
🚨 {html.escape(winner["name"])}
STEALS THE FRONT PAGE
</div>

<div class="hero-sub">
A huge <b>{safe_int(winner["gw_points"])} points</b>
puts {html.escape(winner["name"])}
top of the Gameweek standings.
</div>

</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# ULTIMATE PDT NEWSPAPER FRONT PAGE
# ============================================================

def make_visual_roast(row, kind):
    name = html.escape(str(row["name"]))
    pts = safe_int(row["gw_points"])

    if kind == "disaster":
        return (
            f"{name} scored {pts}. The FPL equivalent of "
            "walking into a pub quiz and answering every question with confidence."
        )

    if kind == "captain":
        cap = html.escape(str(row["captain"]))
        cappts = safe_int(row["captain_effective"])
        return (
            f"{name} trusted {cap} for {cappts} effective points. "
            "The armband has requested legal representation."
        )

    bench = safe_int(row["bench_points"])
    return (
        f"{name} left {bench} points on the bench. "
        "Their substitutes have formally applied for the manager's job."
    )


# The headline is generated from the data-driven story when the AI article
# exists; otherwise use a rotating tabloid headline.
headline_pool = [
    "FPL CRISIS: SOMEONE HAS BEEN MAKING DECISIONS AGAIN",
    "POINTS WERE SCORED. DIGNITY WAS NOT.",
    "THE MINI-LEAGUE HAS QUESTIONS — LOTS OF QUESTIONS",
    "FPL POLICE CALLED AFTER ANOTHER CAPTAINCY DISASTER",
    "ONE MAN WON. EVERYONE ELSE NEEDS A RECOUNT.",
]

headline = headline_pool[
    (gw * 7 + len(league_name)) % len(headline_pool)
]

worst = awards["disaster"]
bench_bad = awards["bench"]
captain_bad = awards["captain_bad"]

st.markdown(
    f"""
<div class="pdt-front">

<div class="pdt-mastline">
<div class="pdt-kicker">THE MINI-LEAGUE TIMES</div>
<div class="pdt-date">GAMEWEEK {gw} • {html.escape(league_name)}</div>
</div>

<div class="pdt-main-headline">{headline}</div>

<div class="pdt-deck">
The weekly dispatch of glory, stupidity, questionable armbands and points
left sitting around doing absolutely nothing.
</div>

<div class="pdt-hero">
<div class="pdt-hero-label">🥇 GAMEWEEK KING</div>
<div class="pdt-hero-number">{safe_int(winner["gw_points"])}</div>
<div style="font-size:24px;font-weight:900;">
{html.escape(str(winner["name"]))}
</div>
<div style="margin-top:6px;font-size:14px;">
Captain: {html.escape(str(winner["actual_captain"]))} •
{safe_int(winner["captain_effective"])} effective points
</div>
</div>

<div class="pdt-grid">

<div class="pdt-card red">
<div class="pdt-card-title">💀 Disasterclass</div>
<div class="pdt-card-name">{html.escape(str(worst["name"]))}</div>
<div class="pdt-card-score">{safe_int(worst["gw_points"])} POINTS</div>
<div class="pdt-card-copy">{make_visual_roast(worst, "disaster")}</div>
</div>

<div class="pdt-card">
<div class="pdt-card-title">🤡 Captaincy Criminal</div>
<div class="pdt-card-name">{html.escape(str(captain_bad["name"]))}</div>
<div class="pdt-card-score">
{html.escape(str(captain_bad["captain"]))} •
{safe_int(captain_bad["captain_points"])} PTS
</div>
<div class="pdt-card-copy">{make_visual_roast(captain_bad, "captain")}</div>
</div>

<div class="pdt-card gold">
<div class="pdt-card-title">🪑 Bench Crime</div>
<div class="pdt-card-name">{html.escape(str(bench_bad["name"]))}</div>
<div class="pdt-card-score">{safe_int(bench_bad["bench_points"])} POINTS BENCHED</div>
<div class="pdt-card-copy">{make_visual_roast(bench_bad, "bench")}</div>
</div>

<div class="pdt-card">
<div class="pdt-card-title">🔥 The Big Story</div>
<div class="pdt-card-name">BRUNO CHANGES EVERYTHING</div>
<div class="pdt-card-copy">
The biggest haul of the week gets the biggest headline. Somebody will be
insufferable in the group chat.
</div>
</div>

</div>

<div class="pdt-line">
<div class="pdt-line-title">📸 LINE OF THE WEEK</div>
<div class="pdt-line-copy">
"{html.escape(str(worst["name"]))} didn't have a bad Gameweek. They produced next week's content."
</div>
</div>

</div>
""",
    unsafe_allow_html=True,
)

# Written newspaper roasts remain deliberately below the visual front page.
st.markdown(
    """
<div class="pdt-roast-section">
<div class="pdt-roast-heading">🔥 The Written Roasts</div>
</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# WEEKLY PODIUM
# ============================================================

st.markdown(
    '<div class="section-title">🏆 THE WEEKLY PODIUM</div>',
    unsafe_allow_html=True,
)

podium = df.sort_values(
    "gw_points",
    ascending=False
).head(3)

medals = [
    "🥇",
    "🥈",
    "🥉",
]

cols = st.columns(3)

for i, (_, row) in enumerate(
    podium.iterrows()
):

    with cols[i]:

        st.markdown(
            f"""
<div class="podium">

<div class="podium-medal">
{medals[i]}
</div>

<div class="podium-name">
{html.escape(row["name"])}
</div>

<div>
{html.escape(row["team_name"])}
</div>

<div class="podium-points">
{safe_int(row["gw_points"])}
</div>

<div>
points
</div>

</div>
""",
            unsafe_allow_html=True,
        )


# ============================================================
# AWARDS
# ============================================================

st.markdown(
    '<div class="section-title">📰 THE WEEKLY AWARDS</div>',
    unsafe_allow_html=True,
)


def award_card(
    title,
    emoji,
    row,
    number,
    text,
    colour
):

    st.markdown(
        f"""
<div class="card {colour}">

<div class="card-title">
{emoji} {title}
</div>

<div class="card-number">
{number}
</div>

<div class="card-name">
{html.escape(row["name"])}
</div>

<p>
{text}
</p>

</div>
""",
        unsafe_allow_html=True,
    )


c1, c2, c3 = st.columns(3)

with c1:

    r = awards["manager"]

    award_card(
        "Manager of the Week",
        "🏆",
        r,
        safe_int(
            r["gw_points"]
        ),
        local_banter(
            r,
            "manager"
        ),
        "card-green",
    )

with c2:

    r = awards["disaster"]

    award_card(
        "Disasterclass",
        "💀",
        r,
        safe_int(
            r["gw_points"]
        ),
        local_banter(
            r,
            "disaster"
        ),
        "card-red",
    )

with c3:

    r = awards["captain"]

    award_card(
        "Captaincy King",
        "🎯",
        r,
        safe_int(
            r["captain_effective"]
        ),
        (
            f"{r['actual_captain']} "
            "received the captain double."
        ),
        "card-gold",
    )


c1, c2, c3 = st.columns(3)

with c1:

    r = awards["captain_bad"]

    award_card(
        "Captaincy Disaster",
        "🤡",
        r,
        safe_int(
            r["captain_effective"]
        ),
        (
            f"Captain: "
            f"{r['captain']}. "
            f"A decision that will be "
            f"discussed for some time."
        ),
        "card-red",
    )

with c2:

    r = awards["bench"]

    award_card(
        "Bench Blunder",
        "🪑",
        r,
        safe_int(
            r["bench_points"]
        ),
        (
            "Unused bench points left behind. "
            "The manager may want to sit down."
        ),
        "card-gold",
    )

with c3:

    r = awards["riser"]

    movement = safe_int(
        r["rank_change"]
    )

    award_card(
        "Biggest Riser",
        "📈",
        r,
        (
            f"+{movement}"
            if movement >= 0
            else movement
        ),
        (
            "A serious move up the table."
        ),
        "card-blue",
    )


# ============================================================
# FAN INTERVIEW
# ============================================================

st.markdown(
    '<div class="section-title">🎙️ THE FAN INTERVIEW</div>',
    unsafe_allow_html=True,
)

if st.button(
    "🎙️ GET THE FAN'S VERDICT",
    use_container_width=True
):

    with st.spinner(
        "Finding a suitably angry supporter..."
    ):

        interview, error, model = (
            generate_fan_interview(
                league_name,
                gw,
                df,
                awards
            )
        )

    if interview:

        st.session_state[
            "fan_interview"
        ] = interview

        st.session_state.pop(
            "fan_error",
            None
        )

    else:

        st.session_state[
            "fan_error"
        ] = error

        st.session_state.pop(
            "fan_interview",
            None
        )


if "fan_error" in st.session_state:

    st.error(
        st.session_state[
            "fan_error"
        ]
    )


if "fan_interview" in st.session_state:

    fan = parse_fan_interview(
        st.session_state[
            "fan_interview"
        ]
    )

    st.markdown(
        f"""
<div class="fan-interview">

<div class="fan-header">
🎙️ {html.escape(fan["fan"])}
</div>

<div style="color:#697386;margin-bottom:15px;">
EXCLUSIVE MINI-LEAGUE TIMES INTERVIEW
</div>

<div class="quote">
<span class="quote-mark">“</span>
<b>{html.escape(fan["a1"])}</b>
</div>

<hr>

<p>
<b>Q:</b> {html.escape(fan["q2"])}
</p>

<div class="quote">
“{html.escape(fan["a2"])}”
</div>

<p>
<b>Q:</b> {html.escape(fan["q3"])}
</p>

<div class="quote">
“{html.escape(fan["a3"])}”
</div>

<p>
<b>Q:</b> {html.escape(fan["q4"])}
</p>

<div class="quote">
“{html.escape(fan["a4"])}”
</div>

</div>
""",
        unsafe_allow_html=True,
    )


# ============================================================
# MANAGER UNDER INVESTIGATION
# ============================================================

st.markdown(
    '<div class="section-title">🚨 MANAGER UNDER INVESTIGATION</div>',
    unsafe_allow_html=True,
)

investigate = awards[
    "captain_bad"
]

st.markdown(
    f"""
<div class="investigation">

<h2>
🚨 {html.escape(investigate["name"])}
</h2>

<p>
The Mini-League Times disciplinary committee has opened
an investigation into <b>{html.escape(investigate["name"])}</b>.
</p>

<p>
<b>Captain:</b>
{html.escape(investigate["captain"])}
</p>

<p>
<b>Effective captain points:</b>
{safe_int(investigate["captain_effective"])}
</p>

<p>
<b>Verdict:</b>
The manager has been ordered to explain themselves
to absolutely nobody.
</p>

</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# AI NEWSPAPER
# ============================================================

st.markdown(
    '<div class="section-title">📰 THE WEEKLY ROAST</div>',
    unsafe_allow_html=True,
)

if not GEMINI_AVAILABLE:

    st.warning(
        "Gemini is not installed. Add "
        "`google-genai` to requirements.txt."
    )

else:

    if get_gemini_client():

        st.success(
            "🤖 Gemini AI is connected. "
            "The app will automatically try the current "
            "Gemini models if one is unavailable."
        )

    else:

        st.warning(
            "Gemini API key not found. "
            "Add GEMINI_API_KEY to Streamlit Secrets."
        )


if st.button(
    "🔥 WRITE THE PDT ROAST",
    type="primary",
    use_container_width=True
):

    with st.spinner(
        "The journalists are sharpening the knives..."
    ):

        article, error, model = (
            generate_ai_review(
                league_name,
                gw,
                df,
                awards
            )
        )

    if article:

        st.session_state[
            "article"
        ] = clean_ai_markdown(
            article
        )

        st.session_state[
            "ai_model"
        ] = model

        st.session_state.pop(
            "ai_error",
            None
        )

        st.rerun()

    else:

        st.session_state[
            "ai_error"
        ] = error


if "ai_error" in st.session_state:

    st.error(
        "❌ Gemini could not write the newspaper.\n\n"
        + st.session_state[
            "ai_error"
        ]
    )


if "article" in st.session_state:

    model_used = st.session_state.get(
        "ai_model",
        ""
    )

    raw_article = st.session_state["article"]

    def extract_section(blob, heading):
        pattern = rf"(?ms)^#\s*{re.escape(heading)}\s*$\n(.*?)(?=^#\s|\Z)"
        match = re.search(pattern, blob)
        return match.group(1).strip() if match else ""

    headline_ai = extract_section(raw_article, "HEADLINE")
    deck_ai = extract_section(raw_article, "DECK")
    front_ai = extract_section(raw_article, "FRONT_PAGE_BLURB")
    line_ai = extract_section(raw_article, "LINE_OF_THE_WEEK")
    signoff_ai = extract_section(raw_article, "SIGN_OFF")

    st.markdown(
        f"""
<div class="pdt-roast">
<h3>{html.escape(headline_ai or "THE WEEKLY ROAST")}</h3>
<p><strong>{html.escape(deck_ai)}</strong></p>
<p style="margin-top:10px;">{html.escape(front_ai)}</p>
</div>
""",
        unsafe_allow_html=True,
    )

    roast_sections = [
        ("🥇 KING OF THE WEEK", "ROAST_1"),
        ("💀 DISASTERCLASS", "ROAST_2"),
        ("🤡 CAPTAINCY CRIMINAL", "ROAST_3"),
        ("🪑 BENCH CRIME", "ROAST_4"),
        ("🎪 ANOTHER WEEKLY CASUALTY", "ROAST_5"),
        ("🗞️ LEAGUE GOSSIP", "LEAGUE_GOSSIP"),
        ("🏆 TITLE RACE", "TITLE_RACE"),
        ("🥄 WOODEN SPOON", "WOODEN_SPOON"),
    ]

    for title, key in roast_sections:
        body = extract_section(raw_article, key)
        if body:
            st.markdown(
                f"""
<div class="pdt-roast">
<h3>{title}</h3>
<p>{html.escape(body).replace(chr(10), "<br>")}</p>
</div>
""",
                unsafe_allow_html=True,
            )

    if line_ai:
        st.markdown(
            f"""
<div class="pdt-line">
<div class="pdt-line-title">📸 LINE OF THE WEEK</div>
<div class="pdt-line-copy">"{html.escape(line_ai)}"</div>
</div>
""",
            unsafe_allow_html=True,
        )

    if signoff_ai:
        st.markdown(
            f"""
<div class="pdt-roast">
<p><strong>{html.escape(signoff_ai)}</strong></p>
</div>
""",
            unsafe_allow_html=True,
        )

    # ------------------------------------------------------------
    # DOWNLOAD THE WRITTEN NEWSPAPER
    # ------------------------------------------------------------
    # The PDF contains the full written roast, not just the visual
    # front page. This is deliberately placed immediately after the
    # article so it is easy to find after generating the edition.
    pdf_bytes = article_to_pdf(
        raw_article,
        league_name,
        gw
    )

    txt_bytes = article_to_txt(
        raw_article,
        league_name,
        gw
    )

    st.markdown(
        """
<div class="pdt-roast-section">
<div class="pdt-roast-heading">📥 SAVE THE EDITION</div>
</div>
""",
        unsafe_allow_html=True,
    )

    dl1, dl2 = st.columns(2)

    with dl1:
        if pdf_bytes:
            st.download_button(
                "📄 DOWNLOAD FULL PDF",
                data=pdf_bytes,
                file_name=(
                    f"mini_league_times_gw_{gw}.pdf"
                ),
                mime="application/pdf",
                use_container_width=True,
            )
        else:
            st.warning(
                "PDF export is unavailable because ReportLab "
                "is not installed."
            )

    with dl2:
        st.download_button(
            "📝 DOWNLOAD WRITE-UP",
            data=txt_bytes,
            file_name=(
                f"mini_league_times_gw_{gw}.txt"
            ),
            mime="text/plain",
            use_container_width=True,
        )

    if model_used:
        st.caption(f"Written with {model_used}")


# ============================================================
# LEAGUE TABLE
# ============================================================

st.markdown(
    '<div class="section-title">📊 THE LEAGUE TABLE</div>',
    unsafe_allow_html=True,
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
# TITLE RACE
# ============================================================

st.markdown(
    '<div class="section-title">🥊 THE TITLE RACE</div>',
    unsafe_allow_html=True,
)

title = df.sort_values(
    "league_position"
).head(5)

for _, row in title.iterrows():

    st.write(
        f"**{safe_int(row['league_position'])}. "
        f"{row['name']}** — "
        f"{safe_int(row['total_points'])} points"
    )

if len(title) >= 2:

    gap = (
        safe_int(
            title.iloc[1]["total_points"]
        )
        -
        safe_int(
            title.iloc[0]["total_points"]
        )
    )

    st.info(
        f"🥊 **{title.iloc[0]['name']}** leads "
        f"**{title.iloc[1]['name']}** by "
        f"**{gap} points**."
    )


# ============================================================
# WOODEN SPOON
# ============================================================

st.markdown(
    '<div class="section-title">🥄 WOODEN SPOON WATCH</div>',
    unsafe_allow_html=True,
)

bottom = df.sort_values(
    "league_position",
    ascending=False
).head(3)

for _, row in bottom.iterrows():

    st.write(
        f"**{safe_int(row['league_position'])}. "
        f"{row['name']}** — "
        f"{safe_int(row['total_points'])} points"
    )


# ============================================================
# FRAUD WATCH
# ============================================================

st.markdown(
    '<div class="section-title">🚨 FRAUD WATCH</div>',
    unsafe_allow_html=True,
)

worst = awards[
    "disaster"
]

captain_bad = awards[
    "captain_bad"
]

if (
    worst["id"]
    ==
    captain_bad["id"]
):

    st.error(
        f"🚨 **{worst['name']}** has earned "
        f"a full Fraud Watch investigation after "
        f"a bottom-of-the-table Gameweek and a "
        f"captaincy disaster."
    )

else:

    st.warning(
        "Nobody has earned a full Fraud Watch "
        "investigation this week. Yet."
    )


# ============================================================
# MANAGER SPOTLIGHT
# ============================================================

st.markdown(
    '<div class="section-title">🔎 MANAGER SPOTLIGHT</div>',
    unsafe_allow_html=True,
)

selected_manager = st.selectbox(
    "Choose a manager",
    df["name"].tolist()
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
        manager["gw_points"]
    )
)

c2.metric(
    "Total",
    safe_int(
        manager["total_points"]
    )
)

c3.metric(
    "Captain",
    manager["captain"]
)

c4.metric(
    "Bench",
    safe_int(
        manager["bench_points"]
    )
)

st.write(
    f"**Actual captain double:** "
    f"{manager['actual_captain']}"
)

st.write(
    f"**Vice Captain:** "
    f"{manager['vice']}"
)

st.write(
    f"**Transfers:** "
    f"{safe_int(manager['transfers'])} "
    f"| **Hit:** "
    f"-{safe_int(manager['transfer_cost'])}"
)

st.write(
    f"**Biggest unused bench regret:** "
    f"{manager['biggest_bench']} "
    f"({safe_int(manager['biggest_bench_points'])} points)"
)

st.write(
    "**Starting XI:** "
    + ", ".join(
        manager["starting_names"]
    )
)


# ============================================================
# DATA CHECK
# ============================================================

with st.expander(
    "🔧 Data accuracy check"
):

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
            "a reconstructed-score difference. "
            "The official FPL history score remains "
            "the source of truth."
        )


# ============================================================
# FOOTER
# ============================================================

st.markdown(
    f"""
<div class="footer">

📰 THE MINI-LEAGUE TIMES

<br>

{html.escape(league_name)}
• Gameweek {gw}
• League ID {LEAGUE_ID}

<br><br>

Official FPL data • Built for competitive banter

</div>
""",
    unsafe_allow_html=True,
)
