"""
Import tool for GameChanger CSV exports
Maps the obscure column names to our database schema
"""

import csv
import re
from typing import Dict, Optional
from pathlib import Path
from database import (
    get_or_create_player, create_game, add_batting_stats,
    get_or_create_season, get_db
)


# GameChanger CSV column mapping
# The column names are obscure but map to standard batting stats
COLUMN_MAP = {
    'BoxScoreComponents__playerName': 'player_name',
    'ag-cell': 'ab',      # At Bats
    'ag-cell 2': 'r',     # Runs
    'ag-cell 3': 'h',     # Hits
    'ag-cell 4': 'rbi',   # RBI
    'ag-cell 5': 'bb',    # Walks (may be missing)
    'ag-cell 6': 'so',    # Strikeouts
}


def parse_filename_for_game_info(filename: str) -> Dict:
    """
    Extract game info from filename pattern like:
    game1_sep6_vipers.csv -> {game_num: 1, date: '9/6', opponent: 'vipers'}

    Returns dict with game_date, opponent, or None values if can't parse
    """
    info = {
        'game_date': None,
        'opponent': None,
        'game_num': None
    }

    # Extract just the filename without path and extension
    name = Path(filename).stem

    # Try to match pattern: game{num}_{month}{day}_{opponent}
    match = re.match(r'game(\d+)_([a-z]+)(\d+)_(.+)', name, re.IGNORECASE)
    if match:
        info['game_num'] = int(match.group(1))
        month_str = match.group(2).lower()
        day = match.group(3)
        info['opponent'] = match.group(4).replace('_', ' ').title()

        # Convert month abbreviation to number
        months = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
            'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
            'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }
        month_num = months.get(month_str[:3], None)
        if month_num:
            info['game_date'] = f"{month_num}/{day}"

    return info


def safe_int(val) -> int:
    """Safely convert value to int"""
    if val is None or val == '':
        return 0
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0


def import_gamechanger_csv(
    file_path: str,
    season_id: int,
    game_date: Optional[str] = None,
    opponent: Optional[str] = None,
    verbose: bool = True
) -> Dict:
    """
    Import a GameChanger batting stats CSV file.

    Args:
        file_path: Path to the CSV file
        season_id: ID of the season to add the game to
        game_date: Game date (e.g., "9/6"). If None, parsed from filename
        opponent: Opponent name. If None, parsed from filename
        verbose: Print progress info

    Returns:
        Dict with import results
    """
    results = {
        'file': file_path,
        'game_id': None,
        'stats_imported': 0,
        'errors': []
    }

    # Try to extract game info from filename if not provided
    if not game_date or not opponent:
        file_info = parse_filename_for_game_info(file_path)
        if not game_date:
            game_date = file_info.get('game_date')
        if not opponent:
            opponent = file_info.get('opponent')

    if not game_date:
        game_date = "Unknown"
    if not opponent:
        opponent = Path(file_path).stem

    if verbose:
        print(f"Importing: {file_path}")
        print(f"  Game: {game_date} vs. {opponent}")

    # Read the CSV
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception as e:
        results['errors'].append(f"Failed to read CSV: {e}")
        return results

    if not rows:
        results['errors'].append("CSV file is empty")
        return results

    # Detect column mapping based on what's in the header
    header = rows[0].keys() if rows else []
    col_map = {}
    for csv_col, our_col in COLUMN_MAP.items():
        if csv_col in header:
            col_map[csv_col] = our_col

    if verbose:
        print(f"  Detected columns: {list(col_map.values())}")

    # Calculate team totals for runs
    total_runs = sum(safe_int(row.get('ag-cell 2', 0)) for row in rows)

    # Create the game
    game_id = create_game(
        season_id=season_id,
        game_date=game_date,
        opponent_name=opponent,
        runs_for=total_runs,
        notes=f"Imported from GameChanger: {Path(file_path).name}"
    )
    results['game_id'] = game_id

    # Import each player's stats
    for row in rows:
        player_name = row.get('BoxScoreComponents__playerName', '').strip()
        if not player_name:
            continue

        # Get or create player
        player_id = get_or_create_player(player_name)

        # Extract stats
        ab = safe_int(row.get('ag-cell', 0))
        r = safe_int(row.get('ag-cell 2', 0))
        h = safe_int(row.get('ag-cell 3', 0))
        rbi = safe_int(row.get('ag-cell 4', 0))
        bb = safe_int(row.get('ag-cell 5', 0))  # May be 0 if column missing
        so = safe_int(row.get('ag-cell 6', 0))

        # Add batting stats
        add_batting_stats(
            game_id=game_id,
            player_id=player_id,
            ab=ab,
            r=r,
            h=h,
            rbi=rbi,
            bb=bb,
            so=so
        )
        results['stats_imported'] += 1

    if verbose:
        print(f"  Imported {results['stats_imported']} player stats")

    return results


def import_multiple_csvs(
    file_paths: list,
    season_id: int,
    verbose: bool = True
) -> Dict:
    """
    Import multiple GameChanger CSV files for a season.

    Args:
        file_paths: List of CSV file paths
        season_id: ID of the season
        verbose: Print progress info

    Returns:
        Dict with combined import results
    """
    all_results = {
        'files_processed': 0,
        'total_games': 0,
        'total_stats': 0,
        'errors': [],
        'details': []
    }

    for file_path in file_paths:
        result = import_gamechanger_csv(file_path, season_id, verbose=verbose)
        all_results['details'].append(result)
        all_results['files_processed'] += 1

        if result['game_id']:
            all_results['total_games'] += 1
        all_results['total_stats'] += result['stats_imported']
        all_results['errors'].extend(result['errors'])

    if verbose:
        print(f"\n{'='*50}")
        print("IMPORT SUMMARY")
        print('='*50)
        print(f"Files processed: {all_results['files_processed']}")
        print(f"Games created: {all_results['total_games']}")
        print(f"Total stats: {all_results['total_stats']}")
        if all_results['errors']:
            print(f"Errors: {len(all_results['errors'])}")

    return all_results


if __name__ == "__main__":
    import sys
    from glob import glob

    # Default: import all test CSVs
    if len(sys.argv) > 1:
        # If season_id provided as first arg
        season_id = int(sys.argv[1])
        files = sys.argv[2:] if len(sys.argv) > 2 else glob("test-data/game*.csv")
    else:
        # Use season 1 (Fall 2025) and find game CSVs
        season_id = 1
        files = glob("test-data/game*.csv")

    if not files:
        print("No CSV files found to import")
        sys.exit(1)

    print(f"Importing {len(files)} CSV files to season {season_id}")
    print()

    results = import_multiple_csvs(files, season_id)