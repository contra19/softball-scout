"""
Softball Scout Stats - Streamlit App (v2)

A comprehensive softball statistics management app with:
- Season tracking (batting, pitching, game results)
- Team scouting
- Player analytics and comparisons
- Excel import/export
"""

import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
import tempfile
import os
import hashlib
import extra_streamlit_components as stx
import database as db
from import_excel import import_workbook
from import_csv import import_gamechanger_csv, parse_filename_for_game_info


# =============================================================================
# PAGE CONFIG
# =============================================================================

st.set_page_config(
    page_title="Softball Scout Stats",
    page_icon="🥎",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =============================================================================
# AUTHENTICATION
# =============================================================================

# Cookie manager for persistent login
@st.cache_resource
def get_cookie_manager():
    return stx.CookieManager()

def generate_auth_token(password: str) -> str:
    """Generate a hash token for the password to store in cookie."""
    return hashlib.sha256(password.encode()).hexdigest()

def check_password():
    """Returns True if the user has entered the correct password.
    Uses cookies to persist authentication across page refreshes.
    """
    cookie_manager = get_cookie_manager()
    correct_password = st.secrets.get("password", "softball")
    expected_token = generate_auth_token(correct_password)

    def password_entered():
        """Checks whether the password entered is correct."""
        st.session_state["login_attempted"] = True
        entered_password = st.session_state.get("password", "")
        if entered_password == correct_password:
            st.session_state["authenticated"] = True
            # Set cookie for 30 days
            cookie_manager.set("auth_token", expected_token, expires_at=datetime.now() + timedelta(days=30))
            del st.session_state["password"]  # Don't store password
        else:
            st.session_state["authenticated"] = False

    # First run - initialize state
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
        st.session_state["login_attempted"] = False

    # Check for existing auth cookie
    if not st.session_state["authenticated"]:
        auth_cookie = cookie_manager.get("auth_token")
        if auth_cookie == expected_token:
            st.session_state["authenticated"] = True

    if not st.session_state["authenticated"]:
        st.title("🥎 Softball Scout Stats")
        st.write("Please enter the password to access the app.")
        st.text_input(
            "Password",
            type="password",
            key="password",
            on_change=password_entered
        )
        # Only show error if a login was actually attempted and failed
        if st.session_state.get("login_attempted") and not st.session_state["authenticated"]:
            st.error("Incorrect password")
        return False

    return True


# =============================================================================
# DIALOG DEFINITIONS
# =============================================================================

@st.dialog("Add Game")
def add_game_dialog():
    """Dialog for adding a new game"""
    if not st.session_state.get('current_season_id'):
        st.warning("No season selected")
        return

    season_id = st.session_state.current_season_id

    st.subheader("Game Information")
    col1, col2 = st.columns(2)
    with col1:
        game_date = st.text_input("Game Date *", placeholder="e.g., 9/6")
        opponent = st.text_input("Opponent *", placeholder="e.g., NJ Vipers 12U")
    with col2:
        win_loss = st.selectbox("Result", ["", "W", "L", "T"])
        rf_col, ra_col = st.columns(2)
        with rf_col:
            runs_for = st.number_input("Runs For", min_value=0, value=0)
        with ra_col:
            runs_against = st.number_input("Runs Against", min_value=0, value=0)

    if st.button("Save Game", type="primary"):
        if not game_date or not opponent:
            st.error("Game date and opponent are required")
            return

        db.create_game(
            season_id=season_id,
            game_date=game_date,
            opponent_name=opponent,
            win_loss=win_loss if win_loss else None,
            runs_for=runs_for if runs_for > 0 else None,
            runs_against=runs_against if runs_against > 0 else None
        )
        st.success(f"Game added: {game_date} vs {opponent}")
        st.rerun()


@st.dialog("Add Player")
def add_player_dialog():
    """Dialog for adding a new player"""
    st.subheader("Player Information")

    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Name *")
        jersey = st.text_input("Jersey #")
    with col2:
        bats = st.selectbox("Bats", ["", "R", "L", "S"])
        throws = st.selectbox("Throws", ["", "R", "L"])

    if st.button("Save Player", type="primary"):
        if not name:
            st.error("Name is required")
            return

        db.create_player(name, jersey if jersey else None,
                        bats if bats else None, throws if throws else None)
        st.success(f"Added player: {name}")
        st.rerun()


@st.dialog("Add Opponent Team")
def add_opponent_team_dialog():
    """Dialog for adding an opponent team for scouting"""
    st.subheader("Team Information")

    name = st.text_input("Team Name *")
    location = st.text_input("Location")

    if st.button("Save Team", type="primary"):
        if not name:
            st.error("Team name is required")
            return

        db.create_team(name, location if location else None)
        st.success(f"Added team: {name}")
        st.rerun()


@st.dialog("Add Age Group")
def add_age_group_dialog():
    """Dialog for adding an age group"""
    st.subheader("Age Group")

    name = st.text_input("Name *", placeholder="e.g., 12U, 10U, 14U")

    if st.button("Save Age Group", type="primary"):
        if not name:
            st.error("Name is required")
            return

        db.get_or_create_age_group(name)
        st.success(f"Added age group: {name}")
        st.rerun()


@st.dialog("Add Our Team")
def add_our_team_dialog():
    """Dialog for adding one of our teams"""
    st.subheader("Team Information")

    age_groups = db.get_all_age_groups()
    if not age_groups:
        st.warning("Create an age group first")
        return

    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Team Name *", placeholder="e.g., PA Chaos Taranto")
        location = st.text_input("Location", placeholder="e.g., Pennsylvania")
    with col2:
        ag_options = {ag.name: ag.id for ag in age_groups}
        selected_ag = st.selectbox("Age Group *", options=list(ag_options.keys()))

    if st.button("Save Team", type="primary"):
        if not name or not selected_ag:
            st.error("Name and age group are required")
            return

        age_group_id = ag_options[selected_ag]
        db.get_or_create_our_team(name, age_group_id, location if location else None)
        st.success(f"Added team: {name}")
        st.rerun()


@st.dialog("Import Excel", width="large")
def import_excel_dialog():
    """Dialog for importing Excel data"""
    st.write("""
    Import data from an existing Excel workbook in the coach's format.
    This will import seasons, games, and player stats.
    """)

    uploaded_file = st.file_uploader("Upload Excel file", type=['xlsx'])

    if uploaded_file and st.button("Import Data", type="primary"):
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name

        try:
            with st.spinner("Importing..."):
                results = import_workbook(tmp_path, verbose=False)

            st.success("Import completed!")
            st.write(f"- Sheets processed: {results['sheets_processed']}")
            st.write(f"- Games imported: {results['total_games']}")
            st.write(f"- Batting records: {results['total_batting']}")
            st.write(f"- Pitching records: {results['total_pitching']}")

            if st.button("Close"):
                st.rerun()

        except Exception as e:
            st.error(f"Import failed: {e}")
            import traceback
            st.code(traceback.format_exc())

        finally:
            os.unlink(tmp_path)


@st.dialog("Import GameChanger CSV", width="large")
def import_gamechanger_dialog():
    """Dialog for importing GameChanger CSV files"""
    if not st.session_state.get('current_season_id'):
        st.warning("Please select a season first from the sidebar.")
        return

    season_id = st.session_state.current_season_id
    season = db.get_season(season_id)
    if not season:
        st.error("Selected season not found")
        return

    st.info(f"Importing to: **{season.season_type} {season.year}**")

    st.write("""
    Upload GameChanger CSV exports. Name files like `game1_sep6_vipers.csv`
    to auto-detect date and opponent.
    """)

    uploaded_files = st.file_uploader(
        "Upload CSV file(s)",
        type=['csv'],
        accept_multiple_files=True,
        key="gc_csv_dialog"
    )

    if uploaded_files:
        file_info = []
        for f in uploaded_files:
            info = parse_filename_for_game_info(f.name)
            file_info.append({
                'file': f,
                'name': f.name,
                'game_date': info.get('game_date') or 'Unknown',
                'opponent': info.get('opponent') or f.name.replace('.csv', '')
            })

        preview_df = pd.DataFrame([{
            'File': fi['name'],
            'Date': fi['game_date'],
            'Opponent': fi['opponent']
        } for fi in file_info])
        st.dataframe(preview_df, width='stretch', hide_index=True)

        col1, col2 = st.columns(2)
        with col1:
            override_date = st.text_input("Override Date", placeholder="Leave blank for auto")
        with col2:
            override_opponent = st.text_input("Override Opponent", placeholder="Leave blank for auto")

        if st.button("Import Games", type="primary"):
            total_stats = 0
            games_created = 0

            for fi in file_info:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
                    tmp.write(fi['file'].getvalue())
                    tmp_path = tmp.name

                try:
                    game_date = override_date if override_date else fi['game_date']
                    opponent = override_opponent if override_opponent else fi['opponent']

                    result = import_gamechanger_csv(
                        tmp_path, season_id,
                        game_date=game_date, opponent=opponent, verbose=False
                    )

                    if result['game_id']:
                        games_created += 1
                        total_stats += result['stats_imported']
                        st.success(f"Imported: {game_date} vs {opponent}")

                except Exception as e:
                    st.error(f"Error: {fi['name']}: {e}")

                finally:
                    os.unlink(tmp_path)

            st.divider()
            st.success(f"Created {games_created} game(s) with {total_stats} player stats.")
            if st.button("Close"):
                st.rerun()


# =============================================================================
# SIDEBAR NAVIGATION
# =============================================================================

def render_sidebar():
    """Render the sidebar navigation with hierarchical selectors"""
    st.sidebar.title("🥎 Softball Scout")

    # Age Group selector
    age_groups = db.get_all_age_groups()
    if age_groups:
        age_group_options = {ag.name: ag.id for ag in age_groups}
        selected_age_group = st.sidebar.selectbox(
            "Age Group",
            options=list(age_group_options.keys()),
            key="selected_age_group"
        )
        st.session_state.current_age_group_id = age_group_options.get(selected_age_group)
    else:
        st.sidebar.info("No age groups yet. Go to Setup.")
        st.session_state.current_age_group_id = None

    # Team selector (filtered by age group) - with "All Teams" option
    if st.session_state.get('current_age_group_id'):
        teams = db.get_all_our_teams(age_group_id=st.session_state.current_age_group_id)
        if teams:
            # Build options list with "All Teams" first
            team_names = ["All Teams"] + [t.name for t in teams]
            team_id_map = {t.name: t.id for t in teams}

            selected_team = st.sidebar.selectbox(
                "Team",
                options=team_names,
                key="selected_team"
            )

            if selected_team == "All Teams":
                st.session_state.current_team_id = None
            else:
                st.session_state.current_team_id = team_id_map.get(selected_team)
        else:
            st.sidebar.info("No teams in this age group.")
            st.session_state.current_team_id = None
    else:
        st.session_state.current_team_id = None

    # Season selector - with "All Seasons" option
    if st.session_state.get('current_age_group_id'):
        # Get available seasons based on team selection
        if st.session_state.get('current_team_id'):
            # Specific team selected - show that team's seasons
            team_seasons = db.get_all_seasons(team_id=st.session_state.current_team_id)
            season_names = ["All Seasons"] + [f"{s.season_type} {s.year}" for s in team_seasons]
            season_id_map = {f"{s.season_type} {s.year}": s.id for s in team_seasons}
        else:
            # "All Teams" selected - show unique season types for the age group
            age_group_seasons = db.get_available_seasons_for_age_group(
                st.session_state.current_age_group_id)
            season_names = ["All Seasons"] + [f"{s['season_type']} {s['year']}" for s in age_group_seasons]
            # For "All Teams", store (year, season_type) tuple
            season_id_map = {f"{s['season_type']} {s['year']}": (s['year'], s['season_type'])
                            for s in age_group_seasons}

        if len(season_names) > 1:  # More than just "All Seasons"
            selected_season = st.sidebar.selectbox(
                "Season",
                options=season_names,
                key="selected_season"
            )

            if selected_season == "All Seasons":
                st.session_state.current_season_id = None
                st.session_state.current_season_info = None
            else:
                value = season_id_map.get(selected_season)
                if isinstance(value, tuple):
                    # "All Teams" mode - store tuple
                    st.session_state.current_season_id = None
                    st.session_state.current_season_info = value  # (year, season_type)
                else:
                    # Specific team mode - store season id
                    st.session_state.current_season_id = value
                    st.session_state.current_season_info = None
        else:
            st.sidebar.info("No seasons yet.")
            st.session_state.current_season_id = None
            st.session_state.current_season_info = None
    else:
        st.session_state.current_season_id = None
        st.session_state.current_season_info = None

    st.sidebar.divider()

    # Navigation
    page = st.sidebar.radio(
        "Navigation",
        ["Dashboard", "Games", "Players", "Teams", "Setup"],
        key="nav_page"
    )

    return page


# =============================================================================
# DASHBOARD PAGE
# =============================================================================

def render_dashboard():
    """Main dashboard based on sidebar Team/Season selections"""
    st.title("📊 Dashboard")

    if not st.session_state.get('current_age_group_id'):
        st.warning("No age group selected. Go to Setup to import data or create an age group.")
        return

    age_group_id = st.session_state.current_age_group_id
    age_group = db.get_age_group(age_group_id)

    if not age_group:
        st.error("Age group not found")
        return

    # Get current selections from sidebar
    team_id = st.session_state.get('current_team_id')  # None = "All Teams"
    season_id = st.session_state.get('current_season_id')  # None if "All Seasons" or "All Teams" mode
    season_info = st.session_state.get('current_season_info')  # (year, type) tuple for "All Teams" mode

    # Determine what to display based on selections
    if team_id is None:
        # "All Teams" selected - show league-wide stats
        render_league_dashboard(age_group, season_info)
    else:
        # Specific team selected
        render_team_dashboard(team_id, season_id)


def render_league_dashboard(age_group, season_info):
    """League-wide dashboard showing stats across all teams in the age group.

    Args:
        age_group: The age group object
        season_info: Either (year, season_type) tuple for specific season, or None for all seasons
    """
    if season_info:
        year, season_type = season_info
        st.header(f"{age_group.name} League - {season_type} {year}")
        # Get stats for specific season
        totals = db.get_league_totals_by_season(age_group.id, year, season_type)
        batting_stats = db.get_league_batting_stats_by_season(age_group.id, year, season_type)
        pitching_stats = db.get_league_pitching_stats_by_season(age_group.id, year, season_type)
        top_batters = db.get_league_top_batters_by_season(age_group.id, year, season_type, 'ba', limit=5)
        top_pitchers = db.get_league_top_pitchers_by_season(age_group.id, year, season_type, 'era', limit=5)
    else:
        st.header(f"{age_group.name} League - All Seasons")
        # Get stats across all seasons
        totals = db.get_league_totals(age_group.id)
        batting_stats = db.get_league_batting_stats(age_group.id)
        pitching_stats = db.get_league_pitching_stats(age_group.id)
        top_batters = db.get_league_top_batters(age_group.id, 'ba', limit=5)
        top_pitchers = db.get_league_top_pitchers(age_group.id, 'era', limit=5)

    if not totals or not totals.get('games'):
        st.info("No stats available for this selection yet.")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Teams", totals.get('teams') or 0)
    with col2:
        st.metric("Games", totals.get('games') or 0)
    with col3:
        st.metric("Players", len(batting_stats) if batting_stats else 0)

    st.divider()

    # Two columns: Batting and Pitching leaders
    col_bat, col_pitch = st.columns(2)

    with col_bat:
        st.subheader("🏏 Top Batters (BA)")
        if top_batters:
            df = pd.DataFrame(top_batters)
            df = df[['player_name', 'team_name', 'ab', 'h', 'r', 'rbi', 'ba']]
            df.columns = ['Player', 'Team', 'AB', 'H', 'R', 'RBI', 'BA']
            st.dataframe(df, width='stretch', hide_index=True)
        else:
            st.info("No batting stats yet (min 10 AB)")

    with col_pitch:
        st.subheader("⚾ Top Pitchers (ERA)")
        if top_pitchers:
            df = pd.DataFrame(top_pitchers)
            df = df[['player_name', 'team_name', 'ip', 'k', 'bb', 'era', 'whip']]
            df.columns = ['Player', 'Team', 'IP', 'K', 'BB', 'ERA', 'WHIP']
            st.dataframe(df, width='stretch', hide_index=True)
        else:
            st.info("No pitching stats yet (min 5 IP)")

    st.divider()

    # Full batting stats
    st.subheader("📋 All Batting Stats")
    if batting_stats:
        df = pd.DataFrame(batting_stats)
        df = df[['player_name', 'team_name', 'jersey_number', 'ab', 'r', 'h', 'rbi', 'bb', 'so', 'ba']]
        df.columns = ['Player', 'Team', '#', 'AB', 'R', 'H', 'RBI', 'BB', 'SO', 'BA']
        st.dataframe(df, width='stretch', hide_index=True)

        total_ab = sum(s['ab'] or 0 for s in batting_stats)
        total_r = sum(s['r'] or 0 for s in batting_stats)
        total_h = sum(s['h'] or 0 for s in batting_stats)
        total_rbi = sum(s['rbi'] or 0 for s in batting_stats)
        total_bb = sum(s['bb'] or 0 for s in batting_stats)
        total_so = sum(s['so'] or 0 for s in batting_stats)
        league_ba = total_h / total_ab if total_ab > 0 else 0

        st.write(f"**League Totals:** {total_ab} AB, {total_r} R, {total_h} H, "
                 f"{total_rbi} RBI, {total_bb} BB, {total_so} SO, {league_ba:.3f} BA")

    st.divider()

    # Full pitching stats
    st.subheader("📋 All Pitching Stats")
    if pitching_stats:
        df = pd.DataFrame(pitching_stats)
        df = df[['player_name', 'team_name', 'jersey_number', 'app', 'ip', 'h', 'r', 'k', 'bb', 'era', 'whip', 'strike_pct']]
        df.columns = ['Player', 'Team', '#', 'APP', 'IP', 'H', 'R', 'K', 'BB', 'ERA', 'WHIP', 'S%']
        df['S%'] = df['S%'].apply(lambda x: f"{x:.1%}" if x else "0.0%")
        st.dataframe(df, width='stretch', hide_index=True)


def render_team_dashboard(team_id, season_id):
    """Team-specific dashboard showing stats for a specific team.

    Args:
        team_id: The team ID
        season_id: The season ID, or None for all seasons
    """
    team = db.get_our_team(team_id)
    if not team:
        st.error("Team not found")
        return

    if season_id:
        # Specific season selected
        season = db.get_season(season_id)
        if not season:
            st.error("Season not found")
            return
        st.header(f"{team.name} - {season.season_type} {season.year}")
        totals = db.get_season_totals(season_id)
        batting_stats = db.get_season_batting_stats(season_id)
        pitching_stats = db.get_season_pitching_stats(season_id)
        top_batters = db.get_top_batters(season_id, 'ba', limit=5)
        top_pitchers = db.get_top_pitchers(season_id, 'era', limit=5)
    else:
        # "All Seasons" selected - aggregate across all seasons for this team
        st.header(f"{team.name} - All Seasons")
        totals = db.get_team_all_seasons_totals(team_id)
        batting_stats = db.get_team_all_seasons_batting(team_id)
        pitching_stats = db.get_team_all_seasons_pitching(team_id)
        top_batters = db.get_team_all_seasons_top_batters(team_id, 'ba', limit=5)
        top_pitchers = db.get_team_all_seasons_top_pitchers(team_id, 'era', limit=5)

    if not totals or not totals.get('games'):
        st.info("No stats available for this selection yet.")
        return

    wins = totals.get('wins') or 0
    losses = totals.get('losses') or 0
    ties = totals.get('ties') or 0

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Games", totals.get('games') or 0)
    with col2:
        record = f"{wins}-{losses}" + (f"-{ties}" if ties else "")
        st.metric("Record", record)
    with col3:
        win_pct = wins / (wins + losses) if (wins + losses) > 0 else 0
        st.metric("Win %", f"{win_pct:.3f}")
    with col4:
        st.metric("Runs For", totals.get('total_rf') or 0)
    with col5:
        st.metric("Runs Against", totals.get('total_ra') or 0)

    st.divider()

    # Two columns: Batting and Pitching leaders
    col_bat, col_pitch = st.columns(2)

    with col_bat:
        st.subheader("🏏 Top Batters (BA)")
        if top_batters:
            df = pd.DataFrame(top_batters)
            df = df[['player_name', 'ab', 'h', 'r', 'rbi', 'ba']]
            df.columns = ['Player', 'AB', 'H', 'R', 'RBI', 'BA']
            st.dataframe(df, width='stretch', hide_index=True)
        else:
            st.info("No batting stats yet")

    with col_pitch:
        st.subheader("⚾ Top Pitchers (ERA)")
        if top_pitchers:
            df = pd.DataFrame(top_pitchers)
            df = df[['player_name', 'ip', 'k', 'bb', 'era', 'whip']]
            df.columns = ['Player', 'IP', 'K', 'BB', 'ERA', 'WHIP']
            st.dataframe(df, width='stretch', hide_index=True)
        else:
            st.info("No pitching stats yet")

    st.divider()

    # Full batting stats
    st.subheader("📋 Full Batting Stats")
    if batting_stats:
        df = pd.DataFrame(batting_stats)
        df = df[['player_name', 'jersey_number', 'ab', 'r', 'h', 'rbi', 'bb', 'so', 'ba']]
        df.columns = ['Player', '#', 'AB', 'R', 'H', 'RBI', 'BB', 'SO', 'BA']
        st.dataframe(df, width='stretch', hide_index=True)

        total_ab = sum(s['ab'] or 0 for s in batting_stats)
        total_r = sum(s['r'] or 0 for s in batting_stats)
        total_h = sum(s['h'] or 0 for s in batting_stats)
        total_rbi = sum(s['rbi'] or 0 for s in batting_stats)
        total_bb = sum(s['bb'] or 0 for s in batting_stats)
        total_so = sum(s['so'] or 0 for s in batting_stats)
        team_ba = total_h / total_ab if total_ab > 0 else 0

        st.write(f"**Team Totals:** {total_ab} AB, {total_r} R, {total_h} H, "
                 f"{total_rbi} RBI, {total_bb} BB, {total_so} SO, {team_ba:.3f} BA")

    st.divider()

    # Full pitching stats
    st.subheader("📋 Full Pitching Stats")
    if pitching_stats:
        df = pd.DataFrame(pitching_stats)
        df = df[['player_name', 'jersey_number', 'app', 'ip', 'h', 'r', 'k', 'bb', 'era', 'whip', 'strike_pct']]
        df.columns = ['Player', '#', 'APP', 'IP', 'H', 'R', 'K', 'BB', 'ERA', 'WHIP', 'S%']
        df['S%'] = df['S%'].apply(lambda x: f"{x:.1%}" if x else "0.0%")
        st.dataframe(df, width='stretch', hide_index=True)


# =============================================================================
# GAMES PAGE
# =============================================================================

def render_games():
    """View all games for the season with add button"""
    st.title("📅 Games")

    team_id = st.session_state.get('current_team_id')
    season_id = st.session_state.get('current_season_id')

    # Determine if we can edit (specific team AND specific season required)
    can_edit = team_id is not None and season_id is not None

    if can_edit:
        # Action buttons at top (only when specific team+season selected)
        col1, col2, _ = st.columns([1, 1, 4])
        with col1:
            if st.button("➕ Add Game", width='stretch'):
                add_game_dialog()
        with col2:
            if st.button("📥 Import CSV", width='stretch'):
                import_gamechanger_dialog()
        st.divider()

    # Determine which games to show
    if season_id:
        # Specific season - show games for that season
        games = db.get_games_by_season(season_id)
        if not games:
            st.info("No games yet." + (" Click 'Add Game' or 'Import CSV' to add games." if can_edit else ""))
            return
    elif team_id:
        # Specific team but All Seasons - show all games for that team
        st.info("Showing all games across all seasons for this team.")
        games = db.get_all_games_for_team(team_id)
        if not games:
            st.info("No games found for this team.")
            return
    else:
        # All Teams - show all games for the age group
        age_group_id = st.session_state.get('current_age_group_id')
        if not age_group_id:
            st.warning("No age group selected.")
            return
        st.info("Showing all games across all teams. Select a specific team and season to add/edit games.")
        games = db.get_all_games_for_age_group(age_group_id)
        if not games:
            st.info("No games found.")
            return

    # Games table
    games_data = []
    for g in games:
        diff = g.run_differential
        diff_str = f"+{diff}" if diff and diff > 0 else str(diff) if diff else ""
        games_data.append({
            'Date': g.game_date or '',
            'Opponent': g.opponent_name or '',
            'W/L': g.win_loss or '',
            'RF': str(g.runs_for) if g.runs_for is not None else '',
            'RA': str(g.runs_against) if g.runs_against is not None else '',
            'Diff': diff_str,
            'game_id': g.id
        })

    df = pd.DataFrame(games_data)
    st.dataframe(
        df[['Date', 'Opponent', 'W/L', 'RF', 'RA', 'Diff']],
        width='stretch',
        hide_index=True
    )

    # Select game to view details
    st.divider()
    st.subheader("Game Details")

    game_options = {f"{g.game_date} vs {g.opponent_name}": g.id for g in games}
    selected_game = st.selectbox("Select a game", options=list(game_options.keys()))

    if selected_game:
        selected_game_id = game_options.get(selected_game)
        if selected_game_id:
            render_game_details(selected_game_id)


def render_game_details(game_id: int):
    """Show details for a specific game"""
    game = db.get_game(game_id)
    if not game:
        return

    st.write(f"**{game.game_date} vs {game.opponent_name}**")
    if game.win_loss:
        result = "Win" if game.win_loss == 'W' else "Loss" if game.win_loss == 'L' else "Tie"
        st.write(f"Result: {result} ({game.runs_for}-{game.runs_against})")

    # Batting stats for this game
    batting = db.get_batting_stats_for_game(game_id)
    if batting:
        st.write("**Batting:**")
        df = pd.DataFrame(batting)
        df = df[['player_name', 'ab', 'r', 'h', 'rbi', 'bb', 'so']]
        df.columns = ['Player', 'AB', 'R', 'H', 'RBI', 'BB', 'SO']
        st.dataframe(df, width='stretch', hide_index=True)

    # Pitching stats for this game
    pitching = db.get_pitching_stats_for_game(game_id)
    if pitching:
        st.write("**Pitching:**")
        df = pd.DataFrame(pitching)
        df = df[['player_name', 'ip', 'h', 'r', 'k', 'bb', 'pitches', 'strikes']]
        df.columns = ['Player', 'IP', 'H', 'R', 'K', 'BB', 'P', 'S']
        st.dataframe(df, width='stretch', hide_index=True)


# =============================================================================
# PLAYERS PAGE
# =============================================================================

def render_players():
    """View and manage players"""
    st.title("👥 Players")

    team_id = st.session_state.get('current_team_id')

    # Only show add button when specific team is selected
    if team_id is not None:
        if st.button("➕ Add Player"):
            add_player_dialog()
        st.divider()
    else:
        st.info("Showing all players. Select a specific team to add players.")
        st.divider()

    players = db.get_all_players(active_only=False)

    if players:
        players_data = [{
            'Name': p.name,
            'Jersey #': p.jersey_number or '',
            'Bats': p.bats or '',
            'Throws': p.throws or '',
            'Active': '✓' if p.active else ''
        } for p in players]

        df = pd.DataFrame(players_data)
        st.dataframe(df, width='stretch', hide_index=True)
    else:
        st.info("No players yet." + (" Click 'Add Player' to add one." if team_id else ""))


# =============================================================================
# TEAMS PAGE (Opponent Scouting)
# =============================================================================

def render_teams():
    """View and manage opponent teams for scouting"""
    st.title("🏆 Teams (Opponent Scouting)")

    team_id = st.session_state.get('current_team_id')

    # Only show add button when specific team is selected
    if team_id is not None:
        if st.button("➕ Add Opponent Team"):
            add_opponent_team_dialog()
        st.divider()
    else:
        st.info("Showing all opponent teams. Select a specific team to add opponents.")
        st.divider()

    teams = db.get_all_teams()

    if teams:
        teams_data = []
        for t in teams:
            wins, losses, ties = db.get_record_vs_team(t.id)
            record = f"{wins}-{losses}" + (f"-{ties}" if ties else "")
            teams_data.append({
                'Team': t.name,
                'Location': t.location or '',
                'Record vs': record
            })

        df = pd.DataFrame(teams_data)
        st.dataframe(df, width='stretch', hide_index=True)
    else:
        st.info("No opponent teams yet." + (" Click 'Add Opponent Team' to add one." if team_id else ""))


# =============================================================================
# SETUP PAGE
# =============================================================================

def render_setup():
    """Setup page for managing age groups, teams, imports, and exports"""
    st.title("⚙️ Setup & Data")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Age Groups", "Our Teams", "Import Excel", "Import GameChanger", "Export"
    ])

    with tab1:
        render_age_groups_setup()

    with tab2:
        render_our_teams_setup()

    with tab3:
        render_excel_import()

    with tab4:
        render_gamechanger_import()

    with tab5:
        render_export()


def render_age_groups_setup():
    """Manage age groups"""
    st.subheader("Age Groups")

    if st.button("➕ Add Age Group", key="add_ag_btn"):
        add_age_group_dialog()

    st.divider()

    age_groups = db.get_all_age_groups()

    if age_groups:
        ag_data = [{'Name': ag.name} for ag in age_groups]
        df = pd.DataFrame(ag_data)
        st.dataframe(df, width='stretch', hide_index=True)
    else:
        st.info("No age groups yet. Click 'Add Age Group' to create one.")


def render_our_teams_setup():
    """Manage our teams"""
    st.subheader("Our Teams")

    age_groups = db.get_all_age_groups()
    if not age_groups:
        st.warning("Create an age group first before adding teams.")
        return

    if st.button("➕ Add Team", key="add_team_btn"):
        add_our_team_dialog()

    st.divider()

    teams = db.get_all_our_teams(active_only=False)

    if teams:
        teams_data = []
        for t in teams:
            ag = db.get_age_group(t.age_group_id)
            teams_data.append({
                'Name': t.name,
                'Age Group': ag.name if ag else 'Unknown',
                'Location': t.location or '',
                'Active': 'Yes' if t.active else 'No'
            })
        df = pd.DataFrame(teams_data)
        st.dataframe(df, width='stretch', hide_index=True)
    else:
        st.info("No teams yet. Click 'Add Team' to create one.")


def render_excel_import():
    """Import from coach's Excel workbook"""
    st.subheader("Import from Excel")

    # Check for previous import results
    if st.session_state.get('excel_import_results'):
        results = st.session_state.excel_import_results

        # Show appropriate message based on what happened
        if results.get('duplicates_updated', 0) > 0:
            st.info(f"Import completed! Found existing data - {results.get('duplicates_updated', 0)} record(s) were updated.")
        else:
            st.success("Import completed successfully!")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Sheets Processed", results['sheets_processed'])
        with col2:
            st.metric("Games Imported", results['total_games'])
        with col3:
            st.metric("Batting Records", results['total_batting'])
        with col4:
            st.metric("Pitching Records", results['total_pitching'])

        if results.get('errors'):
            st.warning("Some errors occurred:")
            for err in results['errors']:
                st.write(f"- {err}")

        if st.button("Import Another File", key="clear_excel_import"):
            del st.session_state.excel_import_results
            st.rerun()
        return

    st.write("""
    Import data from an existing Excel workbook in the coach's format.
    This will import:
    - Seasons, games, and results
    - Batting stats (AB, R, H, RBI, BB, SO)
    - Pitching stats (IP, H, R, K, BB, HBP, Pitches, Strikes)

    **Note:** If data already exists for a season, it will be updated (not duplicated).
    """)

    # Show existing data summary
    seasons = db.get_all_seasons()
    if seasons:
        with st.expander("View existing data in database"):
            for season in seasons:
                if season.id is not None:
                    summary = db.get_season_stats_summary(season.id)
                    games = summary.get('games') or 0
                    batters = summary.get('batters') or 0
                    if games > 0:
                        st.write(f"- **{season.season_type} {season.year}**: {games} games, {batters} players")

    uploaded_file = st.file_uploader("Upload Excel file (.xlsx)", type=['xlsx'], key="excel_import")

    if uploaded_file:
        st.info(f"Selected: **{uploaded_file.name}**")

        if st.button("Import Data", type="primary", key="import_excel_page_btn"):
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp.name

            try:
                with st.spinner("Importing data..."):
                    results = import_workbook(tmp_path, verbose=False)

                st.session_state.excel_import_results = results
                st.rerun()

            except Exception as e:
                st.error(f"Import failed: {e}")
                import traceback
                st.code(traceback.format_exc())

            finally:
                os.unlink(tmp_path)


def render_gamechanger_import():
    """Import from GameChanger CSV exports"""
    st.subheader("Import from GameChanger")

    # Check for previous import results
    if st.session_state.get('gc_import_results'):
        results = st.session_state.gc_import_results
        st.success(f"Import completed! Created {results['games_created']} game(s) with {results['total_stats']} player stats.")

        if results.get('errors'):
            st.warning("Some errors occurred:")
            for err in results['errors']:
                st.write(f"- {err}")

        if st.button("Import More Files", key="clear_gc_import"):
            del st.session_state.gc_import_results
            st.rerun()
        return

    if not st.session_state.get('current_season_id'):
        st.warning("Please select a season from the sidebar before importing.")
        return

    season_id = st.session_state.current_season_id
    season = db.get_season(season_id)
    if not season:
        st.error("Selected season not found")
        return

    st.info(f"Importing to: **{season.season_type} {season.year}**")

    st.write("""
    Upload GameChanger CSV exports. The import supports:
    - **Batting stats**: AB, R, H, RBI, BB, SO

    **Tip:** Name files like `game1_sep6_vipers.csv` to auto-detect date and opponent.
    """)

    uploaded_files = st.file_uploader(
        "Upload CSV file(s)",
        type=['csv'],
        accept_multiple_files=True,
        key="gc_csv_page"
    )

    if uploaded_files:
        # Preview file info
        file_info = []
        for f in uploaded_files:
            info = parse_filename_for_game_info(f.name)
            file_info.append({
                'file': f,
                'name': f.name,
                'game_date': info.get('game_date') or 'Unknown',
                'opponent': info.get('opponent') or f.name.replace('.csv', '')
            })

        st.write("**Files to import:**")
        preview_df = pd.DataFrame([{
            'File': fi['name'],
            'Date (auto)': fi['game_date'],
            'Opponent (auto)': fi['opponent']
        } for fi in file_info])
        st.dataframe(preview_df, width='stretch', hide_index=True)

        st.write("**Override (optional):**")
        col1, col2 = st.columns(2)
        with col1:
            override_date = st.text_input("Override Date", placeholder="Leave blank for auto", key="gc_date_override")
        with col2:
            override_opponent = st.text_input("Override Opponent", placeholder="Leave blank for auto", key="gc_opp_override")

        if st.button("Import Games", type="primary", key="import_gc_page_btn"):
            total_stats = 0
            games_created = 0
            errors = []

            progress = st.progress(0)
            status = st.empty()

            for idx, fi in enumerate(file_info):
                status.text(f"Importing {fi['name']}...")

                with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
                    tmp.write(fi['file'].getvalue())
                    tmp_path = tmp.name

                try:
                    game_date = override_date if override_date else fi['game_date']
                    opponent = override_opponent if override_opponent else fi['opponent']

                    result = import_gamechanger_csv(
                        tmp_path, season_id,
                        game_date=game_date, opponent=opponent, verbose=False
                    )

                    if result['game_id']:
                        games_created += 1
                        total_stats += result['stats_imported']
                    if result.get('errors'):
                        errors.extend(result['errors'])

                except Exception as e:
                    errors.append(f"{fi['name']}: {e}")

                finally:
                    os.unlink(tmp_path)

                progress.progress((idx + 1) / len(file_info))

            status.empty()
            progress.empty()

            # Store results and rerun to refresh sidebar
            st.session_state.gc_import_results = {
                'games_created': games_created,
                'total_stats': total_stats,
                'errors': errors
            }
            st.rerun()


def render_export():
    """Export data to various formats"""
    st.subheader("Export Data")

    if not st.session_state.get('current_season_id'):
        st.warning("Please select a season from the sidebar to export.")
        return

    season_id = st.session_state.current_season_id
    season = db.get_season(season_id)
    if not season:
        st.error("Selected season not found")
        return

    st.write(f"Export data for: **{season.season_type} {season.year}**")

    st.write("---")

    st.write("**Export to Excel**")
    st.write("Generate an Excel workbook in the coach's format with games, batting, and pitching stats.")

    if st.button("Generate Excel Export", type="primary"):
        with st.spinner("Generating export..."):
            excel_data = generate_excel_export(season_id)

        filename = f"{season.season_type}_{season.year}_stats.xlsx"
        st.download_button(
            label="📥 Download Excel File",
            data=excel_data,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


# =============================================================================
# EXCEL EXPORT
# =============================================================================

def generate_excel_export(season_id: int) -> bytes:
    """Generate Excel export in coach's format"""
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill

    wb = Workbook()
    ws = wb.active

    season = db.get_season(season_id)
    ws.title = season.name

    header_font = Font(bold=True, size=11)
    subheader_font = Font(bold=True, size=10)
    center = Alignment(horizontal='center', vertical='center')
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )
    header_fill = PatternFill(start_color="DDDDDD", end_color="DDDDDD", fill_type="solid")

    ws['A1'] = f"TEAM NAME: PA Chaos 12U Taranto"
    ws['A1'].font = header_font

    wins, losses, ties = db.get_season_record(season_id)
    record = f"{wins}-{losses}" + (f"-{ties}" if ties else "")
    ws['A6'] = f"{season.season_type.upper()} {season.year} RECORD: {record}"
    ws['A6'].font = header_font

    ws['A8'] = "GAME RESULTS"
    ws['G8'] = "PITCHING STATS"
    ws['Y8'] = "BATTING STATS"

    game_headers = ['DATE/OPP', 'W/L', 'RF', 'RA', 'DIFF']
    for col, header in enumerate(game_headers, start=1):
        cell = ws.cell(row=9, column=col, value=header)
        cell.font = subheader_font
        cell.alignment = center
        cell.fill = header_fill
        cell.border = thin_border

    pitch_headers = ['#', 'PLAYER', 'APP', 'IP', 'H', 'R', 'K', 'BB', 'HBP', 'P', 'S', 'S%']
    for col_offset, header in enumerate(pitch_headers):
        cell = ws.cell(row=9, column=7+col_offset, value=header)
        cell.font = subheader_font
        cell.alignment = center
        cell.fill = header_fill
        cell.border = thin_border

    bat_headers = ['#', 'PLAYER', 'AB', 'R', 'H', 'RBI', 'BB', 'SO', 'BA']
    for col_offset, header in enumerate(bat_headers):
        cell = ws.cell(row=9, column=25+col_offset, value=header)
        cell.font = subheader_font
        cell.alignment = center
        cell.fill = header_fill
        cell.border = thin_border

    games = db.get_games_by_season(season_id)
    batting_stats = db.get_season_batting_stats(season_id)
    pitching_stats = db.get_season_pitching_stats(season_id)

    max_rows = max(len(games), len(batting_stats), len(pitching_stats))

    for row_idx in range(max_rows):
        row = 10 + row_idx

        if row_idx < len(games):
            g = games[row_idx]
            ws.cell(row=row, column=1, value=f"{g.game_date} vs {g.opponent_name}")
            ws.cell(row=row, column=2, value=g.win_loss or '')
            ws.cell(row=row, column=3, value=g.runs_for or '')
            ws.cell(row=row, column=4, value=g.runs_against or '')
            diff = g.run_differential
            ws.cell(row=row, column=5, value=diff if diff else '')

        if row_idx < len(pitching_stats):
            p = pitching_stats[row_idx]
            ws.cell(row=row, column=7, value=p.get('jersey_number', ''))
            ws.cell(row=row, column=8, value=p['player_name'])
            ws.cell(row=row, column=9, value=p.get('app', 0))
            ws.cell(row=row, column=10, value=p.get('ip', 0))
            ws.cell(row=row, column=11, value=p.get('h', 0))
            ws.cell(row=row, column=12, value=p.get('r', 0))
            ws.cell(row=row, column=13, value=p.get('k', 0))
            ws.cell(row=row, column=14, value=p.get('bb', 0))
            ws.cell(row=row, column=15, value=p.get('hbp', 0))
            ws.cell(row=row, column=16, value=p.get('pitches', 0))
            ws.cell(row=row, column=17, value=p.get('strikes', 0))
            ws.cell(row=row, column=18, value=p.get('strike_pct', 0))

        if row_idx < len(batting_stats):
            b = batting_stats[row_idx]
            ws.cell(row=row, column=25, value=b.get('jersey_number', ''))
            ws.cell(row=row, column=26, value=b['player_name'])
            ws.cell(row=row, column=27, value=b.get('ab', 0))
            ws.cell(row=row, column=28, value=b.get('r', 0))
            ws.cell(row=row, column=29, value=b.get('h', 0))
            ws.cell(row=row, column=30, value=b.get('rbi', 0))
            ws.cell(row=row, column=31, value=b.get('bb', 0))
            ws.cell(row=row, column=32, value=b.get('so', 0))
            ws.cell(row=row, column=33, value=b.get('ba', 0))

    ws.column_dimensions['A'].width = 35
    ws.column_dimensions['H'].width = 20
    ws.column_dimensions['Z'].width = 20

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Main application entry point"""
    # Check password first
    if not check_password():
        return

    db.init_database()

    page = render_sidebar()

    if page == "Dashboard":
        render_dashboard()
    elif page == "Games":
        render_games()
    elif page == "Players":
        render_players()
    elif page == "Teams":
        render_teams()
    elif page == "Setup":
        render_setup()


if __name__ == "__main__":
    main()