"""
Softball Scout Stats - Streamlit App

A simple web UI for managing softball scouting statistics.
Allows coaches to:
- Create new scouting sheets
- Add game data from CSV exports
- View aggregated batting stats
- Download updated Excel files
"""

import streamlit as st
import pandas as pd
from io import BytesIO
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import re


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class PlayerGameStats:
    player_name: str
    ab: int = 0
    r: int = 0
    h: int = 0
    rbi: int = 0
    bb: int = 0
    so: int = 0


@dataclass
class AggregatedStats:
    player_name: str
    ab: int = 0
    r: int = 0
    h: int = 0
    rbi: int = 0
    bb: int = 0
    so: int = 0
    
    @property
    def ba(self) -> float:
        return self.h / self.ab if self.ab > 0 else 0.0


# =============================================================================
# STYLES
# =============================================================================

HEADER_FONT = Font(bold=True, size=11)
SUBHEADER_FONT = Font(bold=True, size=10)
DATA_FONT = Font(size=10)
CENTER = Alignment(horizontal='center', vertical='center')
LEFT = Alignment(horizontal='left', vertical='center')
RIGHT = Alignment(horizontal='right', vertical='center')

THIN_BORDER = Border(
    left=Side(style='thin'),
    right=Side(style='thin'),
    top=Side(style='thin'),
    bottom=Side(style='thin')
)

HEADER_FILL = PatternFill(start_color="DDDDDD", end_color="DDDDDD", fill_type="solid")


# =============================================================================
# CSV PARSING
# =============================================================================

def parse_game_csv(csv_content: bytes) -> Tuple[List[PlayerGameStats], List[str]]:
    """
    Parse a game CSV into player stats.
    Returns (player_stats, warnings)
    """
    import csv
    from io import StringIO
    
    content = csv_content.decode('utf-8')
    reader = csv.DictReader(StringIO(content))
    
    players = []
    warnings = []
    
    # Figure out column mapping from headers
    fieldnames = reader.fieldnames or []
    
    # Try to find columns (case-insensitive)
    # First try exact match, then substring match
    def find_column(options: List[str]) -> Optional[str]:
        # First: exact match (case-insensitive)
        for opt in options:
            for field in fieldnames:
                if opt.lower() == field.lower().strip():
                    return field
        # Second: substring match for longer option strings only
        for opt in options:
            if len(opt) > 2:  # Only do substring for longer strings
                for field in fieldnames:
                    if opt.lower() in field.lower():
                        return field
        return None

    name_col = find_column(['player', 'name'])
    ab_col = find_column(['ab', 'at bat'])
    r_col = find_column(['r', 'runs', 'run'])
    h_col = find_column(['h', 'hits', 'hit'])
    rbi_col = find_column(['rbi'])
    bb_col = find_column(['bb', 'walk', 'walks'])
    so_col = find_column(['so', 'k', 'strikeout', 'strikeouts'])
    
    if not name_col:
        warnings.append("Could not find Player/Name column")
        return [], warnings
    
    for row in reader:
        try:
            name = row.get(name_col, '').strip()
            if not name:
                continue
            
            def get_int(col: Optional[str]) -> int:
                if not col:
                    return 0
                val = row.get(col, '').strip()
                return int(val) if val else 0
            
            stats = PlayerGameStats(
                player_name=name,
                ab=get_int(ab_col),
                r=get_int(r_col),
                h=get_int(h_col),
                rbi=get_int(rbi_col),
                bb=get_int(bb_col),
                so=get_int(so_col)
            )
            players.append(stats)
        except Exception as e:
            warnings.append(f"Could not parse row: {e}")
    
    return players, warnings


# =============================================================================
# EXCEL OPERATIONS
# =============================================================================

def create_new_workbook(team_name: str, location: str = "") -> Workbook:
    """Create a new scouting workbook with proper structure"""
    wb = Workbook()
    ws = wb.active
    ws.title = sanitize_sheet_name(team_name)
    
    setup_team_sheet(ws, team_name, location)
    return wb


def sanitize_sheet_name(name: str) -> str:
    """Make a valid Excel sheet name"""
    # Remove invalid characters
    name = re.sub(r'[\\/*?:\[\]]', '', name)
    # Truncate to 31 chars
    return name[:31]


def setup_team_sheet(ws, team_name: str, location: str = ""):
    """Set up the structure of a team sheet"""
    # Team header info
    ws['A1'] = f"TEAM NAME: {team_name}"
    ws['A1'].font = HEADER_FONT
    
    if location:
        ws['A2'] = f"LOCATION: {location}"
    
    ws['A3'] = "GAMECHANGER:"
    ws['A4'] = "USSSA:"
    
    # Games tracked (will update as games are added)
    ws['A6'] = "GAMES TRACKED: 0"
    ws['A6'].font = HEADER_FONT
    
    # Section headers (row 8)
    ws['A8'] = "GAME RESULTS"
    ws['A8'].font = HEADER_FONT
    ws['G8'] = "BATTING STATS"
    ws['G8'].font = HEADER_FONT
    
    # Column headers (row 9)
    game_headers = ['DATE', 'OPPONENT']
    for col, header in enumerate(game_headers, start=1):
        cell = ws.cell(row=9, column=col, value=header)
        cell.font = SUBHEADER_FONT
        cell.alignment = CENTER
        cell.fill = HEADER_FILL
        cell.border = THIN_BORDER
    
    batting_headers = ['#', 'PLAYER', 'AB', 'R', 'H', 'RBI', 'BB', 'SO', 'BA']
    for col_offset, header in enumerate(batting_headers):
        col = 7 + col_offset  # Start at column G
        cell = ws.cell(row=9, column=col, value=header)
        cell.font = SUBHEADER_FONT
        cell.alignment = CENTER
        cell.fill = HEADER_FILL
        cell.border = THIN_BORDER
    
    # Set column widths
    ws.column_dimensions['A'].width = 12
    ws.column_dimensions['B'].width = 30
    ws.column_dimensions['G'].width = 5
    ws.column_dimensions['H'].width = 25
    for col in ['I', 'J', 'K', 'L', 'M', 'N', 'O']:
        ws.column_dimensions[col].width = 8


def get_teams_from_workbook(wb: Workbook) -> List[str]:
    """Get list of team names (sheet names) from workbook"""
    return wb.sheetnames


def parse_existing_games(ws) -> List[Tuple[str, str]]:
    """Parse existing games from a team sheet"""
    games = []
    row = 10  # Data starts at row 10
    
    while True:
        date = ws.cell(row=row, column=1).value
        opponent = ws.cell(row=row, column=2).value
        
        if not date and not opponent:
            break
        
        if date or opponent:
            games.append((str(date or ''), str(opponent or '')))
        
        row += 1
    
    return games


def parse_existing_batting_stats(ws) -> Dict[str, AggregatedStats]:
    """Parse existing batting stats from a team sheet"""
    stats = {}
    row = 10  # Data starts at row 10
    
    while True:
        player_name = ws.cell(row=row, column=8).value  # Column H
        
        if not player_name or player_name == "TOTALS":
            break
        
        def get_int(col: int) -> int:
            val = ws.cell(row=row, column=col).value
            return int(val) if val else 0
        
        stats[player_name] = AggregatedStats(
            player_name=player_name,
            ab=get_int(9),   # Column I
            r=get_int(10),   # Column J
            h=get_int(11),   # Column K
            rbi=get_int(12), # Column L
            bb=get_int(13),  # Column M
            so=get_int(14)   # Column N
        )
        
        row += 1
    
    return stats


def add_game_to_sheet(ws, game_date: str, opponent: str, player_stats: List[PlayerGameStats]):
    """Add a new game's data to a team sheet and recalculate aggregates"""
    
    # Get existing games to find where to add the new one
    existing_games = parse_existing_games(ws)
    
    # Get existing batting stats
    existing_batting = parse_existing_batting_stats(ws)
    
    # Add new game to list
    new_game_row = 10 + len(existing_games)
    ws.cell(row=new_game_row, column=1, value=game_date).border = THIN_BORDER
    ws.cell(row=new_game_row, column=2, value=opponent).border = THIN_BORDER
    
    # Update games tracked count
    ws['A6'] = f"GAMES TRACKED: {len(existing_games) + 1}"
    ws['A6'].font = HEADER_FONT
    
    # Merge new stats with existing
    for player in player_stats:
        name = player.player_name
        if name in existing_batting:
            existing_batting[name].ab += player.ab
            existing_batting[name].r += player.r
            existing_batting[name].h += player.h
            existing_batting[name].rbi += player.rbi
            existing_batting[name].bb += player.bb
            existing_batting[name].so += player.so
        else:
            existing_batting[name] = AggregatedStats(
                player_name=name,
                ab=player.ab,
                r=player.r,
                h=player.h,
                rbi=player.rbi,
                bb=player.bb,
                so=player.so
            )
    
    # Sort by BA descending
    sorted_players = sorted(existing_batting.values(), key=lambda x: x.ba, reverse=True)
    
    # Clear existing batting data (rows 10+, columns G-O)
    for row in range(10, 100):  # Clear plenty of rows
        for col in range(7, 16):
            ws.cell(row=row, column=col).value = None
            ws.cell(row=row, column=col).border = Border()
    
    # Re-write headers
    batting_headers = ['#', 'PLAYER', 'AB', 'R', 'H', 'RBI', 'BB', 'SO', 'BA']
    for col_offset, header in enumerate(batting_headers):
        col = 7 + col_offset
        cell = ws.cell(row=9, column=col, value=header)
        cell.font = SUBHEADER_FONT
        cell.alignment = CENTER
        cell.fill = HEADER_FILL
        cell.border = THIN_BORDER
    
    # Write sorted player stats
    for row_offset, player in enumerate(sorted_players):
        row = 10 + row_offset
        
        ws.cell(row=row, column=7, value=row_offset + 1).border = THIN_BORDER  # #
        ws.cell(row=row, column=8, value=player.player_name).border = THIN_BORDER
        ws.cell(row=row, column=9, value=player.ab).border = THIN_BORDER
        ws.cell(row=row, column=10, value=player.r).border = THIN_BORDER
        ws.cell(row=row, column=11, value=player.h).border = THIN_BORDER
        ws.cell(row=row, column=12, value=player.rbi).border = THIN_BORDER
        ws.cell(row=row, column=13, value=player.bb).border = THIN_BORDER
        ws.cell(row=row, column=14, value=player.so).border = THIN_BORDER
        
        ba_cell = ws.cell(row=row, column=15, value=player.ba)
        ba_cell.border = THIN_BORDER
        ba_cell.number_format = '0.000000'
        
        # Alignment
        for col in [7, 9, 10, 11, 12, 13, 14]:
            ws.cell(row=row, column=col).alignment = CENTER
        ws.cell(row=row, column=15).alignment = RIGHT
    
    # Totals row
    totals_row = 10 + len(sorted_players)
    total_ab = sum(p.ab for p in sorted_players)
    total_r = sum(p.r for p in sorted_players)
    total_h = sum(p.h for p in sorted_players)
    total_rbi = sum(p.rbi for p in sorted_players)
    total_bb = sum(p.bb for p in sorted_players)
    total_so = sum(p.so for p in sorted_players)
    team_ba = total_h / total_ab if total_ab > 0 else 0
    
    ws.cell(row=totals_row, column=8, value="TOTALS").font = Font(bold=True)
    ws.cell(row=totals_row, column=9, value=total_ab)
    ws.cell(row=totals_row, column=10, value=total_r)
    ws.cell(row=totals_row, column=11, value=total_h)
    ws.cell(row=totals_row, column=12, value=total_rbi)
    ws.cell(row=totals_row, column=13, value=total_bb)
    ws.cell(row=totals_row, column=14, value=total_so)
    
    ba_cell = ws.cell(row=totals_row, column=15, value=team_ba)
    ba_cell.number_format = '0.000000'
    
    for col in range(7, 16):
        cell = ws.cell(row=totals_row, column=col)
        cell.font = Font(bold=True, size=10)
        cell.border = THIN_BORDER


def workbook_to_bytes(wb: Workbook) -> bytes:
    """Convert workbook to bytes for download"""
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


# =============================================================================
# STREAMLIT APP
# =============================================================================

def main():
    st.set_page_config(
        page_title="Softball Scout Stats",
        page_icon="🥎",
        layout="wide"
    )
    
    st.title("🥎 Softball Scout Stats")
    st.markdown("*Manage scouting statistics for opponent teams*")
    
    # Initialize session state
    if 'workbook' not in st.session_state:
        st.session_state.workbook = None
    if 'workbook_name' not in st.session_state:
        st.session_state.workbook_name = "scouting_stats.xlsx"
    
    # Sidebar for mode selection
    st.sidebar.header("Getting Started")
    
    mode = st.sidebar.radio(
        "Choose an option:",
        ["Create New Sheet", "Update Existing Sheet"]
    )
    
    if mode == "Create New Sheet":
        handle_create_new()
    else:
        handle_update_existing()


def handle_create_new():
    """Handle creating a new scouting sheet"""
    st.header("Create New Scouting Sheet")
    
    with st.form("new_sheet_form"):
        team_name = st.text_input("Team Name *", placeholder="e.g., PA Chaos 12U Taranto")
        location = st.text_input("Location", placeholder="e.g., Garnett Valley, PA")
        
        submitted = st.form_submit_button("Create Sheet")
        
        if submitted:
            if not team_name:
                st.error("Team name is required")
            else:
                wb = create_new_workbook(team_name, location)
                st.session_state.workbook = wb
                st.session_state.workbook_name = f"{sanitize_sheet_name(team_name)}_scouting.xlsx"
                st.success(f"Created new scouting sheet for {team_name}")
    
    # Show current workbook status and allow adding games
    if st.session_state.workbook:
        st.divider()
        show_workbook_interface()


def handle_update_existing():
    """Handle updating an existing scouting sheet"""
    st.header("Update Existing Sheet")
    
    uploaded_file = st.file_uploader(
        "Upload your existing scouting Excel file",
        type=['xlsx'],
        help="Upload the .xlsx file you want to update"
    )
    
    if uploaded_file:
        try:
            wb = load_workbook(BytesIO(uploaded_file.getvalue()))
            st.session_state.workbook = wb
            st.session_state.workbook_name = uploaded_file.name
            st.success(f"Loaded: {uploaded_file.name}")
        except Exception as e:
            st.error(f"Error loading file: {e}")
            return
    
    if st.session_state.workbook:
        st.divider()
        show_workbook_interface()


def show_workbook_interface():
    """Show the main interface for working with a loaded workbook"""
    wb = st.session_state.workbook
    
    # Team selection
    teams = get_teams_from_workbook(wb)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Teams in Workbook")
        selected_team = st.selectbox("Select a team:", teams)
    
    with col2:
        st.subheader("Add New Team")
        with st.form("add_team_form"):
            new_team_name = st.text_input("Team Name")
            new_team_location = st.text_input("Location")
            add_team = st.form_submit_button("Add Team")
            
            if add_team and new_team_name:
                sheet_name = sanitize_sheet_name(new_team_name)
                if sheet_name not in wb.sheetnames:
                    ws = wb.create_sheet(title=sheet_name)
                    setup_team_sheet(ws, new_team_name, new_team_location)
                    st.success(f"Added team: {new_team_name}")
                    st.rerun()
                else:
                    st.warning("Team already exists")
    
    if selected_team:
        st.divider()
        show_team_interface(selected_team)
    
    # Download button
    st.divider()
    st.subheader("Download Updated File")
    
    excel_bytes = workbook_to_bytes(wb)
    st.download_button(
        label="📥 Download Excel File",
        data=excel_bytes,
        file_name=st.session_state.workbook_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def show_team_interface(team_name: str):
    """Show interface for a specific team"""
    wb = st.session_state.workbook
    ws = wb[team_name]
    
    st.subheader(f"📋 {team_name}")
    
    # Show existing games
    existing_games = parse_existing_games(ws)
    if existing_games:
        st.write(f"**Games tracked:** {len(existing_games)}")
        with st.expander("View game list"):
            for date, opponent in existing_games:
                st.write(f"• {date} vs. {opponent}")
    else:
        st.info("No games tracked yet")
    
    # Show current stats
    existing_stats = parse_existing_batting_stats(ws)
    if existing_stats:
        st.write("**Current Batting Stats:**")
        
        # Convert to dataframe for display
        stats_data = []
        for player in sorted(existing_stats.values(), key=lambda x: x.ba, reverse=True):
            stats_data.append({
                'Player': player.player_name,
                'AB': player.ab,
                'R': player.r,
                'H': player.h,
                'RBI': player.rbi,
                'BB': player.bb,
                'SO': player.so,
                'BA': f"{player.ba:.3f}"
            })
        
        df = pd.DataFrame(stats_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Add new game
    st.divider()
    st.subheader("➕ Add Game Data")
    
    with st.form("add_game_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            game_date = st.text_input("Game Date *", placeholder="e.g., 9/6")
        
        with col2:
            opponent = st.text_input("Opponent *", placeholder="e.g., NJ Vipers 12U White")
        
        csv_file = st.file_uploader(
            "Upload Game CSV *",
            type=['csv'],
            help="CSV with columns: Player, AB, R, H, RBI, BB (optional), SO"
        )
        
        add_game = st.form_submit_button("Add Game")
        
        if add_game:
            if not game_date or not opponent:
                st.error("Game date and opponent are required")
            elif not csv_file:
                st.error("Please upload a CSV file")
            else:
                # Parse CSV
                player_stats, warnings = parse_game_csv(csv_file.getvalue())
                
                if warnings:
                    for w in warnings:
                        st.warning(w)
                
                if player_stats:
                    # Add game to sheet
                    add_game_to_sheet(ws, game_date, opponent, player_stats)
                    st.success(f"Added game: {game_date} vs. {opponent} ({len(player_stats)} players)")
                    st.rerun()
                else:
                    st.error("No player data found in CSV")


if __name__ == "__main__":
    main()
