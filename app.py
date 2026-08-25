import streamlit as st
import requests
import pandas as pd
import json
import os
import re
from io import BytesIO
from datetime import datetime

# Optional PDF support
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.units import mm
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

# Optional Gemini AI
try:
    from google import genai
    GEMINI_AVAILABLE = True
except Exception:
    GEMINI_AVAILABLE = False


# ============================================================
# CONFIG
# ============================================================

st.set_page_config(
    page_title="FPL Mini-League Times",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE = "https://fantasy.premierleague.com/api"
LEAGUE_ID = "637276"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# Current stable model. The old gemini-2.5-flash-lite model in the
# previous script is no longer available to new users.
GEMINI_MODEL = "gemini-3.5-flash-lite"


# ============================================================
# STYLE
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
    margin-bottom: 25px;
}
.story {
    background: rgba(127,127,127,.10);
    padding: 20px;
    border-radius: 12px;
    margin-bottom: 15px;
}
.headline {
    font-size: 30px;
    font-weight: 900;
    line-height: 1.1;
}
.award {
    border: 1px solid rgba(127,127,127,.45);
    border-radius: 12px;
    padding: 18px;
    min-height: 180px;
}
.big-number {
    font-size: 42px;
    font-weight: 900;
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# API
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def get_json(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


@st.cache_data(ttl=300, show_spinner=False)
def get_bootstrap():
    return get_json(f"{BASE}/bootstrap-static/")


@st.cache_data(ttl=300, show_spinner=False)
def get_league_page(league_id, page):
    url = (
        f"{BASE}/leagues-classic/{league_id}/standings/"
        f"?page_new_entries=1&page_standings={page}&phase=1"
    )
    return get_json(url)


@st.cache_data(ttl=300, show_spinner=False)
def get_manager_history(manager_id):
    return get_json(f"{BASE}/entry/{manager_id}/history/")


@st.cache_data(ttl=300, show_spinner=False)
def get_manager_picks(manager_id, gw):
    return get_json(f"{BASE}/entry/{manager_id}/event/{gw}/picks/")


@st.cache_data(ttl=300, show_spinner=False)
def get_live_gameweek(gw):
    return get_json(f"{BASE}/event/{gw}/live/")


# ============================================================
# HELPERS
# ============================================================

def get_current_gameweek(data):
    events = data.get("events", [])

    for event in events:
        if event.get("is_current"):
            return int(event["id"])

    finished = [int(e["id"]) for e in events if e.get("finished")]
    return max(finished) if finished else 1


def build_player_lookup(data):
    teams = {
        int(t["id"]): t["name"]
        for t in data.get("teams", [])
    }

    players = {}

    for p in data.get("elements", []):
        pid = int(p["id"])
        players[pid] = {
            "name": f'{p.get("first_name", "")} {p.get("second_name", "")}'.strip(),
            "short_name": p.get("web_name", "?"),
            "team": teams.get(int(p.get("team", 0)), "?"),
            "position": p.get("element_type"),
            "price": p.get("now_cost", 0) / 10,
            "total_points": p.get("total_points", 0),
        }

    return players


def build_live_points(live):
    result = {}

    if not live:
        return result

    for item in live.get("elements", []):
        pid = int(item.get("id"))
        stats = item.get("stats", {})
        result[pid] = {
            "points": int(stats.get("total_points", 0)),
            "minutes": int(stats.get("minutes", 0)),
            "goals": int(stats.get("goals_scored", 0)),
            "assists": int(stats.get("assists", 0)),
            "bonus": int(stats.get("bonus", 0)),
        }

    return result


def get_all_league_managers(league_id):
    all_results = []

    # Classic leagues normally return 50 managers per page.
    # We fetch several pages so larger leagues are not silently truncated.
    for page in range(1, 21):
        data = get_league_page(league_id, page)

        if not data:
            break

        results = data.get("standings", {}).get("results", [])
        if not results:
            break

        all_results.extend(results)

        if len(results) < 50:
            break

    return all_results


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def player_name(pick, players):
    if not pick:
        return "Unknown"
    p = players.get(safe_int(pick.get("element")))
    return p["short_name"] if p else "Unknown"


def pick_points(pick, live_points):
    if not pick:
        return 0
    pid = safe_int(pick.get("element"))
    return safe_int(live_points.get(pid, {}).get("points", 0))


def pick_minutes(pick, live_points):
    if not pick:
        return 0
    pid = safe_int(pick.get("element"))
    return safe_int(live_points.get(pid, {}).get("minutes", 0))


def clean_text(text):
    if text is None:
        return ""
    return str(text).replace("\x00", "").strip()


# ============================================================
# MANAGER ANALYSIS
# ============================================================

def analyse_manager(manager, gw, players, live_points):
    manager_id = safe_int(manager.get("entry"))

    history = get_manager_history(manager_id)
    picks_data = get_manager_picks(manager_id, gw)

    if not history or not picks_data:
        return None

    current_history = None
    for event in history.get("current", []):
        if safe_int(event.get("event")) == gw:
            current_history = event
            break

    # If a future/unstarted GW is selected, there may not be a history row.
    if not current_history:
        return None

    picks = picks_data.get("picks", [])
    if not picks:
        return None

    starting = [p for p in picks if safe_int(p.get("position")) <= 11]
    bench = [p for p in picks if safe_int(p.get("position")) > 11]

    original_captain = next(
        (p for p in picks if p.get("is_captain")),
        None,
    )
    original_vice = next(
        (p for p in picks if p.get("is_vice_captain")),
        None,
    )

    # FPL's returned multiplier reflects the actual result after
    # captaincy/auto-substitution. A multiplier of 2 identifies the
    # player who actually received the double captain points.
    actual_captain = next(
        (p for p in picks if safe_int(p.get("multiplier")) == 2),
        original_captain,
    )

    captain_name = player_name(original_captain, players)
    captain_raw_points = pick_points(original_captain, live_points)
    captain_minutes = pick_minutes(original_captain, live_points)

    actual_captain_name = player_name(actual_captain, players)
    actual_captain_points = pick_points(actual_captain, live_points)
    captain_effective = actual_captain_points * 2

    # Unused bench = bench players whose multiplier is zero.
    # This avoids incorrectly counting auto-substituted players as
    # points "left on the bench".
    unused_bench = [
        p for p in bench
        if safe_int(p.get("multiplier")) == 0
    ]

    bench_points = sum(
        pick_points(p, live_points)
        for p in unused_bench
    )

    biggest_bench = None
    if unused_bench:
        biggest_bench = max(
            unused_bench,
            key=lambda p: pick_points(p, live_points),
        )

    transfers = safe_int(current_history.get("event_transfers"))
    transfer_cost = safe_int(current_history.get("event_transfers_cost"))

    rank = safe_int(current_history.get("overall_rank"))
    last_rank = safe_int(current_history.get("last_rank"), rank)

    # Positive = improved overall rank.
    rank_change = last_rank - rank

    gw_points = safe_int(current_history.get("points"))
    total_points = safe_int(current_history.get("total_points"))

    # Calculate the actual points represented by the picks as a sanity check.
    calculated_team_points = sum(
        pick_points(p, live_points) * max(safe_int(p.get("multiplier")), 0)
        for p in picks
    )

    return {
        "id": manager_id,
        "name": clean_text(manager.get("player_name", "Unknown")),
        "team_name": clean_text(manager.get("entry_name", "Unknown")),
        "league_position": safe_int(manager.get("rank")),
        "gw_points": gw_points,
        "total_points": total_points,
        "rank": rank,
        "last_rank": last_rank,
        "rank_change": rank_change,

        "captain": captain_name,
        "captain_points": captain_raw_points,
        "captain_minutes": captain_minutes,
        "captain_effective": captain_effective,
        "actual_captain": actual_captain_name,

        "vice": player_name(original_vice, players),

        "bench_points": bench_points,
        "biggest_bench": player_name(biggest_bench, players),
        "biggest_bench_points": (
            pick_points(biggest_bench, live_points)
            if biggest_bench else 0
        ),

        "transfers": transfers,
        "transfer_cost": transfer_cost,

        "calculated_team_points": calculated_team_points,

        "starting_names": [
            player_name(p, players) for p in starting
        ],
    }


def analyse_league(managers, gw, players, live_points):
    analysed = []
    progress = st.progress(0)

    total = len(managers)

    for i, manager in enumerate(managers):
        result = analyse_manager(
            manager,
            gw,
            players,
            live_points,
        )

        if result:
            analysed.append(result)

        progress.progress(int(((i + 1) / max(total, 1)) * 100))

    progress.empty()
    return analysed


# ============================================================
# AWARDS
# ============================================================

def get_awards(df):
    if df.empty:
        return {}

    return {
        "manager": df.loc[df["gw_points"].idxmax()],
        "disaster": df.loc[df["gw_points"].idxmin()],
        "captain": df.loc[df["captain_effective"].idxmax()],
        "captain_bad": df.loc[df["captain_effective"].idxmin()],
        "bench": df.loc[df["bench_points"].idxmax()],
        "riser": df.loc[df["rank_change"].idxmax()],
        "faller": df.loc[df["rank_change"].idxmin()],
        "transfer": df.loc[df["transfers"].idxmax()],
    }


def local_banter(row, award):
    name = row["name"]
    points = safe_int(row["gw_points"])

    if award == "manager":
        return f"{name} takes Manager of the Week with {points} points. Somebody check whether they've suddenly started reading the rules."

    if award == "disaster":
        return f"{name} finishes bottom of the weekly pile with just {points} points. A performance that will be described as 'unlucky' in the group chat."

    if award == "captain":
        return (
            f"{name} got the captaincy spot on with "
            f"{row['actual_captain']} delivering "
            f"{safe_int(row['captain_effective'])} effective points. Tactical genius."
        )

    if award == "captain_bad":
        return (
            f"{name} trusted {row['captain']} as captain and got "
            f"{safe_int(row['captain_effective'])} effective points. Bold. Very bold."
        )

    if award == "bench":
        return (
            f"{name} left {safe_int(row['bench_points'])} points "
            f"unused on the bench. That's not squad depth. That's self-sabotage."
        )

    if award == "riser":
        return (
            f"{name} climbs {abs(safe_int(row['rank_change']))} places. "
            f"Suddenly the title looks very interesting."
        )

    if award == "faller":
        return (
            f"{name} drops {abs(safe_int(row['rank_change']))} places. "
            f"The less said, the better."
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
        api_key = st.secrets.get("GEMINI_API_KEY")
    except Exception:
        pass

    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        return None

    return genai.Client(api_key=api_key)


def generate_ai_review(league_name, gw, df, awards):
    client = get_gemini_client()

    if not client:
        return None, "Gemini API key is not configured."

    records = df.to_dict(orient="records")

    award_data = {}
    for key, row in awards.items():
        award_data[key] = {
            "name": row["name"],
            "team": row["team_name"],
            "gw_points": safe_int(row["gw_points"]),
            "captain": row["captain"],
            "actual_captain": row["actual_captain"],
            "captain_effective": safe_int(row["captain_effective"]),
            "bench_points": safe_int(row["bench_points"]),
            "rank_change": safe_int(row["rank_change"]),
            "transfers": safe_int(row["transfers"]),
        }

    prompt = f"""
You are the editor of a funny British fantasy football newspaper.

Write the Gameweek {gw} edition of:

THE MINI-LEAGUE TIMES
{league_name}

Use ONLY the supplied FPL data. Never invent a score, player,
transfer, rank or event.

Tone:
- funny
- competitive
- cheeky
- British football banter
- occasionally savage
- never genuinely cruel
- never discriminatory
- make fun of FPL decisions, not people's personal lives or identities

Include:

1. A big newspaper headline.
2. Manager of the Week.
3. Disasterclass of the Week.
4. Captaincy story.
5. Bench Blunder.
6. Biggest Riser.
7. Biggest Faller.
8. Transfer story.
9. Title Race.
10. Wooden Spoon Watch.
11. Fraud Watch.
12. A closing paragraph.

For Fraud Watch, only call someone a fraud when the supplied data
actually gives you a funny FPL reason. Keep it playful.

Mention specific managers and players from the data.

The weekly points in "gw_points" are the official manager Gameweek
points. The "bench_points" figure is ONLY unused bench points, so do
not describe auto-substituted players as bench points left behind.

Write around 900-1200 words with clear headings.

LEAGUE DATA:
{json.dumps(records, ensure_ascii=False, indent=2)}

AWARDS:
{json.dumps(award_data, ensure_ascii=False, indent=2)}
"""

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )

        text = getattr(response, "text", None)

        if not text:
            return None, "Gemini returned an empty response."

        return text.strip(), None

    except Exception as e:
        return None, str(e)


# ============================================================
# DOWNLOADS
# ============================================================

def article_to_pdf(article, league_name, gw):
    if not REPORTLAB_AVAILABLE:
        return None

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "TitleCustom",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontSize=22,
        leading=27,
        spaceAfter=10,
    )

    body_style = ParagraphStyle(
        "BodyCustom",
        parent=styles["BodyText"],
        fontSize=10.5,
        leading=15,
        spaceAfter=8,
    )

    story = [
        Paragraph("THE MINI-LEAGUE TIMES", title_style),
        Paragraph(
            f"Gameweek {gw} — {clean_text(league_name)}",
            ParagraphStyle(
                "Sub",
                parent=styles["Heading2"],
                alignment=TA_CENTER,
            ),
        ),
        Spacer(1, 8),
    ]

    # Basic Markdown-to-ReportLab conversion.
    for raw_line in article.splitlines():
        line = clean_text(raw_line)

        if not line:
            story.append(Spacer(1, 5))
            continue

        safe = (
            line.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
        )

        if safe.startswith("### "):
            story.append(
                Paragraph(
                    safe[4:],
                    styles["Heading3"],
                )
            )
        elif safe.startswith("## "):
            story.append(
                Paragraph(
                    safe[3:],
                    styles["Heading2"],
                )
            )
        elif safe.startswith("# "):
            story.append(
                Paragraph(
                    safe[2:],
                    styles["Heading1"],
                )
            )
        else:
            safe = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", safe)
            story.append(Paragraph(safe, body_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def article_to_txt(article, league_name, gw):
    heading = (
        "THE MINI-LEAGUE TIMES\n"
        f"Gameweek {gw} — {league_name}\n"
        + "=" * 60
        + "\n\n"
    )
    return (heading + article).encode("utf-8")


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">📰 THE MINI-LEAGUE TIMES</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="subtitle">"Where your mates\' FPL mistakes become public knowledge."</div>',
    unsafe_allow_html=True,
)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.header("⚙️ League Setup")

st.sidebar.success(f"League ID: {LEAGUE_ID}")

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

if st.sidebar.button("🔄 Clear cached data"):
    st.cache_data.clear()
    st.session_state.pop("league_df", None)
    st.session_state.pop("article", None)
    st.rerun()


# ============================================================
# LOAD FPL
# ============================================================

bootstrap = get_bootstrap()

if not bootstrap:
    st.error("Could not connect to the FPL API.")
    st.stop()

players = build_player_lookup(bootstrap)
current_gw = get_current_gameweek(bootstrap)
gw = current_gw if use_current else int(gw_override)

st.info(f"FPL currently reports Gameweek **{current_gw}**. Analysing **Gameweek {gw}**.")


# ============================================================
# LOAD LEAGUE
# ============================================================

with st.spinner("Loading mini-league..."):
    league = get_league_page(LEAGUE_ID, 1)

if not league:
    st.error(f"Could not load FPL mini-league {LEAGUE_ID}.")
    st.stop()

league_name = (
    league.get("league", {}).get("name")
    or "FPL Mini-League"
)

managers = get_all_league_managers(LEAGUE_ID)

if not managers:
    st.error("No managers were found in the league.")
    st.stop()

st.success(
    f"Loaded **{league_name}** — **{len(managers)} managers**."
)


# ============================================================
# ANALYSE BUTTON
# ============================================================

if st.button(
    f"🚀 Analyse Gameweek {gw}",
    type="primary",
    use_container_width=True,
):
    with st.spinner("Loading official Gameweek player scores..."):
        live = get_live_gameweek(gw)

    if not live:
        st.error(
            "The FPL live Gameweek data could not be loaded. "
            "Try again in a few seconds."
        )
        st.stop()

    live_points = build_live_points(live)

    with st.spinner("Analysing every manager..."):
        analysed = analyse_league(
            managers,
            gw,
            players,
            live_points,
        )

    if not analysed:
        st.error(
            "No manager data could be loaded for this Gameweek. "
            "If the Gameweek has not started, try again once managers "
            "have Gameweek data."
        )
        st.stop()

    df = pd.DataFrame(analysed)

    st.session_state["league_df"] = df
    st.session_state["league_name"] = league_name
    st.session_state["gw"] = gw
    st.session_state["live_loaded"] = True

    st.success(
        f"Analysis complete — {len(df)} managers processed."
    )


# ============================================================
# DISPLAY
# ============================================================

if "league_df" not in st.session_state:
    st.markdown("---")
    st.markdown(
        f"""
        ### 👋 Welcome to The Mini-League Times

        Your league **{league_name}** is hard-coded into this app.

        **League ID:** {LEAGUE_ID}

        Press **Analyse Gameweek** above to generate:

        🏆 Manager of the Week  
        💀 Disasterclass  
        🎯 Captaincy King & Disaster  
        🪑 Unused Bench Blunder  
        📈 Biggest Riser  
        📉 Biggest Faller  
        💰 Transfer analysis  
        🚨 Fraud Watch  
        🥊 Title Race  
        🥄 Wooden Spoon Watch  
        🎙️ Gemini-written newspaper  
        📥 Downloadable newspaper
        """
    )
    st.stop()


df = st.session_state["league_df"]
league_name = st.session_state["league_name"]
gw = st.session_state["gw"]

awards = get_awards(df)


# ============================================================
# NEWSPAPER HEADER
# ============================================================

st.markdown("---")

st.markdown(
    f"""
    <div style="text-align:center">
        <h1>GAMEWEEK {gw}</h1>
        <h2>{league_name}</h2>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# HEADLINE
# ============================================================

winner = awards["manager"]

st.markdown(
    f"""
    <div class="story">
        <div class="headline">
            🗞️ {winner["name"]} TAKES GAMEWEEK HONOURS
        </div>
        <p>
            <b>{safe_int(winner["gw_points"])} points</b> puts
            <b>{winner["name"]}</b> top of the weekly leaderboard.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# AWARDS
# ============================================================

st.subheader("🏆 The Weekly Awards")

c1, c2, c3 = st.columns(3)

with c1:
    r = awards["manager"]
    st.markdown(
        f"""
        <div class="award">
            <h3>🏆 Manager of the Week</h3>
            <div class="big-number">{safe_int(r["gw_points"])}</div>
            <b>{r["name"]}</b>
            <p>{local_banter(r, "manager")}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c2:
    r = awards["disaster"]
    st.markdown(
        f"""
        <div class="award">
            <h3>💀 Disasterclass</h3>
            <div class="big-number">{safe_int(r["gw_points"])}</div>
            <b>{r["name"]}</b>
            <p>{local_banter(r, "disaster")}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c3:
    r = awards["captain"]
    st.markdown(
        f"""
        <div class="award">
            <h3>🎯 Captaincy King</h3>
            <div class="big-number">{safe_int(r["captain_effective"])}</div>
            <b>{r["name"]}</b>
            <p>{r["actual_captain"]} actually received the captain double.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

c1, c2, c3 = st.columns(3)

with c1:
    r = awards["captain_bad"]
    st.markdown(
        f"""
        <div class="award">
            <h3>🤡 Captaincy Disaster</h3>
            <b>{r["name"]}</b>
            <p>
                Original captain: <b>{r["captain"]}</b><br>
                Effective captain points: <b>{safe_int(r["captain_effective"])}</b>
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c2:
    r = awards["bench"]
    st.markdown(
        f"""
        <div class="award">
            <h3>🪑 Bench Blunder</h3>
            <div class="big-number">{safe_int(r["bench_points"])}</div>
            <b>{r["name"]}</b>
            <p>Unused bench points actually left behind.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c3:
    r = awards["riser"]
    movement = safe_int(r["rank_change"])
    st.markdown(
        f"""
        <div class="award">
            <h3>📈 Biggest Riser</h3>
            <div class="big-number">{'+' if movement >= 0 else ''}{movement}</div>
            <b>{r["name"]}</b>
            <p>Overall rank movement this Gameweek.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# AI NEWSPAPER
# ============================================================

st.markdown("---")
st.subheader("🎙️ The Weekly Review")

if not GEMINI_AVAILABLE:
    st.warning(
        "The google-genai package is not installed. "
        "Add google-genai to requirements.txt."
    )
else:
    if get_gemini_client():
        st.success(
            f"Gemini AI is connected — using {GEMINI_MODEL}."
        )
    else:
        st.warning(
            "Gemini AI is not connected. Add GEMINI_API_KEY "
            "to Streamlit Secrets."
        )

if st.button(
    "📰 WRITE THE FULL NEWSPAPER",
    type="primary",
    use_container_width=True,
):
    with st.spinner("The journalists are writing the newspaper..."):
        article, error = generate_ai_review(
            league_name,
            gw,
            df,
            awards,
        )

    if article:
        st.session_state["article"] = article
        st.session_state.pop("ai_error", None)
        st.rerun()
    else:
        st.session_state["ai_error"] = error or "Unknown Gemini error."


if "ai_error" in st.session_state:
    st.error(
        "Gemini could not write the newspaper.\n\n"
        f"Error: {st.session_state['ai_error']}\n\n"
        "If this says 429 or 503, try the button again shortly."
    )


if "article" in st.session_state:
    article = st.session_state["article"]

    st.markdown(
        '<div class="story">',
        unsafe_allow_html=True,
    )
    st.markdown(article)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("### 📥 Download Newspaper")

    txt_data = article_to_txt(
        article,
        league_name,
        gw,
    )

    st.download_button(
        "📄 Download Newspaper (.txt)",
        data=txt_data,
        file_name=f"mini_league_times_gw{gw}.txt",
        mime="text/plain",
        use_container_width=True,
    )

    if REPORTLAB_AVAILABLE:
        pdf_data = article_to_pdf(
            article,
            league_name,
            gw,
        )

        st.download_button(
            "📰 Download Newspaper (.pdf)",
            data=pdf_data,
            file_name=f"mini_league_times_gw{gw}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    else:
        st.info(
            "PDF support is not installed. Add reportlab to requirements.txt "
            "to enable the PDF download."
        )


# ============================================================
# LEAGUE TABLE
# ============================================================

st.markdown("---")
st.subheader("📊 The League Table")

table = df.sort_values(
    "league_position"
).copy()

table["Movement"] = table["rank_change"].apply(
    lambda x: f"⬆️ {safe_int(x)}"
    if safe_int(x) > 0
    else (
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

st.markdown("---")
st.subheader("🔎 Manager Spotlight")

selected = st.selectbox(
    "Choose a manager",
    df["name"].tolist(),
)

manager = df[df["name"] == selected].iloc[0]

c1, c2, c3, c4 = st.columns(4)

c1.metric("GW Points", safe_int(manager["gw_points"]))
c2.metric("Total", safe_int(manager["total_points"]))
c3.metric("Captain", manager["captain"])
c4.metric("Unused Bench", safe_int(manager["bench_points"]))

st.write(
    f"**Captain:** {manager['captain']} "
    f"({safe_int(manager['captain_effective'])} effective points)"
)

st.write(f"**Actual captain double:** {manager['actual_captain']}")
st.write(f"**Vice Captain:** {manager['vice']}")
st.write(
    f"**Transfers:** {safe_int(manager['transfers'])} "
    f"| **Hit:** -{safe_int(manager['transfer_cost'])}"
)
st.write(
    f"**Biggest unused bench regret:** "
    f"{manager['biggest_bench']} "
    f"({safe_int(manager['biggest_bench_points'])} points)"
)
st.write(
    "**Starting XI:** " + ", ".join(manager["starting_names"])
)


# ============================================================
# DATA SANITY CHECK
# ============================================================

with st.expander("🔧 Data accuracy check"):
    st.caption(
        "This compares the official FPL manager Gameweek score with "
        "the score reconstructed from the returned picks."
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
        check["gw_points"] -
        check["calculated_team_points"]
    )

    st.dataframe(
        check,
        use_container_width=True,
        hide_index=True,
    )

    mismatches = check[check["Difference"] != 0]

    if mismatches.empty:
        st.success(
            "All reconstructed team scores match the official "
            "FPL Gameweek scores."
        )
    else:
        st.warning(
            f"{len(mismatches)} manager(s) have a score difference. "
            "This can happen with special FPL scoring situations; "
            "the official FPL history score is always used for the "
            "league and weekly rankings."
        )


# ============================================================
# FRAUD WATCH
# ============================================================

st.markdown("---")
st.subheader("🚨 Fraud Watch")

worst = awards["disaster"]
captain_bad = awards["captain_bad"]

if worst["id"] == captain_bad["id"]:
    st.warning(
        f"🚨 **{worst['name']}** is officially on Fraud Watch after "
        f"finishing bottom of the week and suffering a captaincy "
        f"disaster."
    )
else:
    st.info(
        "Nobody has earned a full Fraud Watch investigation this week. Yet."
    )


# ============================================================
# TITLE RACE
# ============================================================

st.markdown("---")
st.subheader("🥊 The Title Race")

title = df.sort_values(
    "league_position"
).head(5)

for _, r in title.iterrows():
    st.write(
        f"**{safe_int(r['league_position'])}. {r['name']}** — "
        f"{safe_int(r['total_points'])} points"
    )

if len(title) >= 2:
    gap = (
        safe_int(title.iloc[0]["total_points"])
        - safe_int(title.iloc[1]["total_points"])
    )

    st.info(
        f"🥊 **{title.iloc[0]['name']}** leads "
        f"**{title.iloc[1]['name']}** by **{gap} points**."
    )


# ============================================================
# WOODEN SPOON
# ============================================================

st.subheader("🥄 Wooden Spoon Watch")

bottom = df.sort_values(
    "league_position",
    ascending=False,
).head(3)

for _, r in bottom.iterrows():
    st.write(
        f"**{safe_int(r['league_position'])}. {r['name']}** — "
        f"{safe_int(r['total_points'])} points"
    )


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")
st.caption(
    f"FPL Mini-League Times • League {LEAGUE_ID} • "
    f"Gameweek {gw} • Data from the official FPL API"
)
