"""
Database layer for Softball Scout Stats
Uses SQLite for embedded database storage
"""

import sqlite3
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, date
from contextlib import contextmanager

# Database file location
DB_PATH = Path(__file__).parent / "softball_stats.db"


@contextmanager
def get_db():
    """Context manager for database connections"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Enable dict-like access
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database():
    """Initialize the database schema"""
    with get_db() as conn:
        conn.executescript("""
            -- Age groups table (10U, 12U, 14U, etc.)
            CREATE TABLE IF NOT EXISTS age_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Our teams table (the teams we're tracking stats for)
            CREATE TABLE IF NOT EXISTS our_teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                age_group_id INTEGER NOT NULL,
                location TEXT,
                active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (age_group_id) REFERENCES age_groups(id),
                UNIQUE(name, age_group_id)
            );

            -- Seasons table (now linked to a specific team)
            CREATE TABLE IF NOT EXISTS seasons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                year INTEGER NOT NULL,
                season_type TEXT NOT NULL CHECK(season_type IN ('Spring', 'Fall')),
                team_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (team_id) REFERENCES our_teams(id),
                UNIQUE(year, season_type, team_id)
            );

            -- Teams table (for opponent scouting)
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                location TEXT,
                gamechanger_url TEXT,
                usssa_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Players table (our team's players)
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                jersey_number TEXT,
                bats TEXT CHECK(bats IN ('L', 'R', 'S')),
                throws TEXT CHECK(throws IN ('L', 'R')),
                active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(name, jersey_number)
            );

            -- Games table
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                season_id INTEGER NOT NULL,
                game_date TEXT NOT NULL,
                opponent_name TEXT NOT NULL,
                opponent_team_id INTEGER,
                win_loss TEXT CHECK(win_loss IN ('W', 'L', 'T')),
                runs_for INTEGER,
                runs_against INTEGER,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (season_id) REFERENCES seasons(id),
                FOREIGN KEY (opponent_team_id) REFERENCES teams(id),
                UNIQUE(season_id, game_date, opponent_name, runs_for, runs_against)
            );

            -- Batting stats (per player per game)
            CREATE TABLE IF NOT EXISTS batting_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL,
                player_id INTEGER NOT NULL,
                ab INTEGER DEFAULT 0,
                r INTEGER DEFAULT 0,
                h INTEGER DEFAULT 0,
                rbi INTEGER DEFAULT 0,
                bb INTEGER DEFAULT 0,
                so INTEGER DEFAULT 0,
                hbp INTEGER DEFAULT 0,
                sac INTEGER DEFAULT 0,
                FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE,
                FOREIGN KEY (player_id) REFERENCES players(id),
                UNIQUE(game_id, player_id)
            );

            -- Pitching stats (per player per game)
            CREATE TABLE IF NOT EXISTS pitching_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL,
                player_id INTEGER NOT NULL,
                ip REAL DEFAULT 0,
                h INTEGER DEFAULT 0,
                r INTEGER DEFAULT 0,
                er INTEGER DEFAULT 0,
                k INTEGER DEFAULT 0,
                bb INTEGER DEFAULT 0,
                hbp INTEGER DEFAULT 0,
                pitches INTEGER DEFAULT 0,
                strikes INTEGER DEFAULT 0,
                FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE,
                FOREIGN KEY (player_id) REFERENCES players(id),
                UNIQUE(game_id, player_id)
            );

            -- Create indexes for common queries
            CREATE INDEX IF NOT EXISTS idx_games_season ON games(season_id);
            CREATE INDEX IF NOT EXISTS idx_games_opponent ON games(opponent_team_id);
            CREATE INDEX IF NOT EXISTS idx_batting_game ON batting_stats(game_id);
            CREATE INDEX IF NOT EXISTS idx_batting_player ON batting_stats(player_id);
            CREATE INDEX IF NOT EXISTS idx_pitching_game ON pitching_stats(game_id);
            CREATE INDEX IF NOT EXISTS idx_pitching_player ON pitching_stats(player_id);
        """)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class AgeGroup:
    id: Optional[int]
    name: str
    sort_order: int = 0

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'AgeGroup':
        return cls(id=row['id'], name=row['name'], sort_order=row['sort_order'])


@dataclass
class OurTeam:
    id: Optional[int]
    name: str
    age_group_id: int
    location: Optional[str] = None
    active: bool = True

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'OurTeam':
        return cls(id=row['id'], name=row['name'], age_group_id=row['age_group_id'],
                   location=row['location'], active=bool(row['active']))


@dataclass
class Season:
    id: Optional[int]
    name: str
    year: int
    season_type: str  # 'Spring' or 'Fall'
    team_id: Optional[int] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'Season':
        return cls(id=row['id'], name=row['name'], year=row['year'],
                   season_type=row['season_type'],
                   team_id=row['team_id'] if 'team_id' in row.keys() else None)


@dataclass
class Team:
    id: Optional[int]
    name: str
    location: Optional[str] = None
    gamechanger_url: Optional[str] = None
    usssa_url: Optional[str] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'Team':
        return cls(id=row['id'], name=row['name'], location=row['location'],
                   gamechanger_url=row['gamechanger_url'], usssa_url=row['usssa_url'])


@dataclass
class Player:
    id: Optional[int]
    name: str
    jersey_number: Optional[str] = None
    bats: Optional[str] = None
    throws: Optional[str] = None
    active: bool = True

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'Player':
        return cls(id=row['id'], name=row['name'], jersey_number=row['jersey_number'],
                   bats=row['bats'], throws=row['throws'], active=bool(row['active']))


@dataclass
class Game:
    id: Optional[int]
    season_id: int
    game_date: str
    opponent_name: str
    opponent_team_id: Optional[int] = None
    win_loss: Optional[str] = None
    runs_for: Optional[int] = None
    runs_against: Optional[int] = None
    notes: Optional[str] = None

    @property
    def run_differential(self) -> Optional[int]:
        if self.runs_for is not None and self.runs_against is not None:
            return self.runs_for - self.runs_against
        return None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'Game':
        return cls(id=row['id'], season_id=row['season_id'], game_date=row['game_date'],
                   opponent_name=row['opponent_name'], opponent_team_id=row['opponent_team_id'],
                   win_loss=row['win_loss'], runs_for=row['runs_for'],
                   runs_against=row['runs_against'], notes=row['notes'])


@dataclass
class BattingStats:
    id: Optional[int]
    game_id: int
    player_id: int
    ab: int = 0
    r: int = 0
    h: int = 0
    rbi: int = 0
    bb: int = 0
    so: int = 0
    hbp: int = 0
    sac: int = 0

    @property
    def ba(self) -> float:
        """Batting Average"""
        return self.h / self.ab if self.ab > 0 else 0.0

    @property
    def obp(self) -> float:
        """On-Base Percentage"""
        pa = self.ab + self.bb + self.hbp + self.sac
        return (self.h + self.bb + self.hbp) / pa if pa > 0 else 0.0

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'BattingStats':
        return cls(id=row['id'], game_id=row['game_id'], player_id=row['player_id'],
                   ab=row['ab'], r=row['r'], h=row['h'], rbi=row['rbi'],
                   bb=row['bb'], so=row['so'], hbp=row['hbp'], sac=row['sac'])


@dataclass
class PitchingStats:
    id: Optional[int]
    game_id: int
    player_id: int
    ip: float = 0.0
    h: int = 0
    r: int = 0
    er: int = 0
    k: int = 0
    bb: int = 0
    hbp: int = 0
    pitches: int = 0
    strikes: int = 0

    @property
    def era(self) -> float:
        """ERA (7-inning game for softball)"""
        return (self.er * 7) / self.ip if self.ip > 0 else 0.0

    @property
    def whip(self) -> float:
        """Walks + Hits per Inning Pitched"""
        return (self.bb + self.h) / self.ip if self.ip > 0 else 0.0

    @property
    def k_per_ip(self) -> float:
        """Strikeouts per Inning"""
        return self.k / self.ip if self.ip > 0 else 0.0

    @property
    def bb_per_ip(self) -> float:
        """Walks per Inning"""
        return self.bb / self.ip if self.ip > 0 else 0.0

    @property
    def strike_pct(self) -> float:
        """Strike Percentage"""
        return self.strikes / self.pitches if self.pitches > 0 else 0.0

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'PitchingStats':
        return cls(id=row['id'], game_id=row['game_id'], player_id=row['player_id'],
                   ip=row['ip'], h=row['h'], r=row['r'], er=row['er'], k=row['k'],
                   bb=row['bb'], hbp=row['hbp'], pitches=row['pitches'], strikes=row['strikes'])


# =============================================================================
# AGE GROUP OPERATIONS
# =============================================================================

def get_all_age_groups() -> List[AgeGroup]:
    """Get all age groups, ordered by name ascending"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM age_groups ORDER BY name"
        ).fetchall()
        return [AgeGroup.from_row(row) for row in rows]


def get_age_group(age_group_id: int) -> Optional[AgeGroup]:
    """Get an age group by ID"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM age_groups WHERE id = ?", (age_group_id,)
        ).fetchone()
        return AgeGroup.from_row(row) if row else None


def get_or_create_age_group(name: str, sort_order: int = 0) -> int:
    """Get existing age group or create new one"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM age_groups WHERE name = ?", (name,)
        ).fetchone()
        if row:
            return row['id']
        cursor = conn.execute(
            "INSERT INTO age_groups (name, sort_order) VALUES (?, ?)",
            (name, sort_order)
        )
        return cursor.lastrowid


# =============================================================================
# OUR TEAM OPERATIONS
# =============================================================================

def get_all_our_teams(age_group_id: int = None, active_only: bool = True) -> List[OurTeam]:
    """Get all our teams, optionally filtered by age group"""
    with get_db() as conn:
        if age_group_id:
            if active_only:
                rows = conn.execute(
                    "SELECT * FROM our_teams WHERE age_group_id = ? AND active = 1 ORDER BY name",
                    (age_group_id,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM our_teams WHERE age_group_id = ? ORDER BY name",
                    (age_group_id,)
                ).fetchall()
        else:
            if active_only:
                rows = conn.execute(
                    "SELECT * FROM our_teams WHERE active = 1 ORDER BY name"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM our_teams ORDER BY name"
                ).fetchall()
        return [OurTeam.from_row(row) for row in rows]


def get_our_team(team_id: int) -> Optional[OurTeam]:
    """Get our team by ID"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM our_teams WHERE id = ?", (team_id,)
        ).fetchone()
        return OurTeam.from_row(row) if row else None


def get_or_create_our_team(name: str, age_group_id: int, location: str = None) -> int:
    """Get existing team or create new one"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM our_teams WHERE name = ? AND age_group_id = ?",
            (name, age_group_id)
        ).fetchone()
        if row:
            return row['id']
        cursor = conn.execute(
            "INSERT INTO our_teams (name, age_group_id, location) VALUES (?, ?, ?)",
            (name, age_group_id, location)
        )
        return cursor.lastrowid


def get_seasons_for_team(team_id: int) -> List[Season]:
    """Get all seasons for a specific team"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM seasons
            WHERE team_id = ?
            ORDER BY year DESC,
                     CASE season_type WHEN 'Fall' THEN 1 WHEN 'Spring' THEN 2 END
        """, (team_id,)).fetchall()
        return [Season.from_row(row) for row in rows]


# =============================================================================
# SEASON OPERATIONS
# =============================================================================

def get_all_seasons(team_id: int = None) -> List[Season]:
    """Get all seasons, optionally filtered by team, ordered reverse chronologically"""
    with get_db() as conn:
        if team_id:
            rows = conn.execute("""
                SELECT * FROM seasons
                WHERE team_id = ?
                ORDER BY year DESC,
                         CASE season_type WHEN 'Fall' THEN 1 WHEN 'Spring' THEN 2 END
            """, (team_id,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM seasons
                ORDER BY year DESC,
                         CASE season_type WHEN 'Fall' THEN 1 WHEN 'Spring' THEN 2 END
            """).fetchall()
        return [Season.from_row(row) for row in rows]


def get_season(season_id: int) -> Optional[Season]:
    """Get a season by ID"""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM seasons WHERE id = ?", (season_id,)).fetchone()
        return Season.from_row(row) if row else None


def create_season(name: str, year: int, season_type: str) -> int:
    """Create a new season, returns ID"""
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO seasons (name, year, season_type) VALUES (?, ?, ?)",
            (name, year, season_type)
        )
        return cursor.lastrowid


def get_or_create_season(year: int, season_type: str, team_id: int = None) -> int:
    """Get existing season or create new one, optionally linked to a team"""
    name = f"{season_type} {str(year)[2:]}"  # e.g., "Fall 25"
    with get_db() as conn:
        if team_id:
            row = conn.execute(
                "SELECT id FROM seasons WHERE year = ? AND season_type = ? AND team_id = ?",
                (year, season_type, team_id)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT id FROM seasons WHERE year = ? AND season_type = ? AND team_id IS NULL",
                (year, season_type)
            ).fetchone()
        if row:
            return row['id']
        cursor = conn.execute(
            "INSERT INTO seasons (name, year, season_type, team_id) VALUES (?, ?, ?, ?)",
            (name, year, season_type, team_id)
        )
        return cursor.lastrowid


# =============================================================================
# TEAM OPERATIONS
# =============================================================================

def get_all_teams() -> List[Team]:
    """Get all teams"""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM teams ORDER BY name").fetchall()
        return [Team.from_row(row) for row in rows]


def get_team(team_id: int) -> Optional[Team]:
    """Get a team by ID"""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM teams WHERE id = ?", (team_id,)).fetchone()
        return Team.from_row(row) if row else None


def get_team_by_name(name: str) -> Optional[Team]:
    """Get a team by name"""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM teams WHERE name = ?", (name,)).fetchone()
        return Team.from_row(row) if row else None


def create_team(name: str, location: str = None) -> int:
    """Create a new team, returns ID"""
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO teams (name, location) VALUES (?, ?)",
            (name, location)
        )
        return cursor.lastrowid


def get_or_create_team(name: str, location: str = None) -> int:
    """Get existing team or create new one"""
    team = get_team_by_name(name)
    if team:
        return team.id
    return create_team(name, location)


# =============================================================================
# PLAYER OPERATIONS
# =============================================================================

def get_all_players(active_only: bool = True) -> List[Player]:
    """Get all players"""
    with get_db() as conn:
        if active_only:
            rows = conn.execute("SELECT * FROM players WHERE active = 1 ORDER BY name").fetchall()
        else:
            rows = conn.execute("SELECT * FROM players ORDER BY name").fetchall()
        return [Player.from_row(row) for row in rows]


def get_player(player_id: int) -> Optional[Player]:
    """Get a player by ID"""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM players WHERE id = ?", (player_id,)).fetchone()
        return Player.from_row(row) if row else None


def get_player_by_name(name: str) -> Optional[Player]:
    """Get a player by name"""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM players WHERE name = ?", (name,)).fetchone()
        return Player.from_row(row) if row else None


def create_player(name: str, jersey_number: str = None, bats: str = None, throws: str = None) -> int:
    """Create a new player, returns ID"""
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO players (name, jersey_number, bats, throws) VALUES (?, ?, ?, ?)",
            (name, jersey_number, bats, throws)
        )
        return cursor.lastrowid


def get_or_create_player(name: str, jersey_number: str = None) -> int:
    """Get existing player or create new one"""
    # Clean up name (remove handedness indicators like "(R)")
    clean_name = name.strip()
    if clean_name.endswith(')'):
        # Remove (R), (L), (S) suffix
        import re
        match = re.match(r'^(.+?)\s*\([RLS]\)$', clean_name)
        if match:
            clean_name = match.group(1).strip()

    player = get_player_by_name(clean_name)
    if player:
        return player.id
    return create_player(clean_name, jersey_number)


# =============================================================================
# GAME OPERATIONS
# =============================================================================

def get_games_by_season(season_id: int) -> List[Game]:
    """Get all games for a season"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM games WHERE season_id = ? ORDER BY game_date",
            (season_id,)
        ).fetchall()
        return [Game.from_row(row) for row in rows]


def get_all_games_for_team(team_id: int) -> List[Game]:
    """Get all games across all seasons for a specific team"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT g.* FROM games g
            JOIN seasons s ON g.season_id = s.id
            WHERE s.team_id = ? AND g.opponent_name NOT LIKE '%Totals%'
            ORDER BY g.game_date DESC
        """, (team_id,)).fetchall()
        return [Game.from_row(row) for row in rows]


def get_all_games_for_age_group(age_group_id: int) -> List[Game]:
    """Get all games across all teams in an age group"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT g.* FROM games g
            JOIN seasons s ON g.season_id = s.id
            JOIN our_teams ot ON s.team_id = ot.id
            WHERE ot.age_group_id = ? AND g.opponent_name NOT LIKE '%Totals%'
            ORDER BY g.game_date DESC
        """, (age_group_id,)).fetchall()
        return [Game.from_row(row) for row in rows]


def get_game(game_id: int) -> Optional[Game]:
    """Get a game by ID"""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
        return Game.from_row(row) if row else None


def create_game(season_id: int, game_date: str, opponent_name: str,
                win_loss: str = None, runs_for: int = None, runs_against: int = None,
                opponent_team_id: int = None, notes: str = None) -> int:
    """Create or update a game (upserts based on season, date, opponent, score), returns ID"""
    with get_db() as conn:
        # Check if game already exists for this season, date, opponent, and score
        # Include runs_for and runs_against to handle doubleheaders (same day, same opponent, different scores)
        if runs_for is not None and runs_against is not None:
            existing = conn.execute("""
                SELECT id FROM games
                WHERE season_id = ? AND game_date = ? AND opponent_name = ?
                  AND runs_for = ? AND runs_against = ?
            """, (season_id, game_date, opponent_name, runs_for, runs_against)).fetchone()
        else:
            # For games without scores (like "Season Totals"), match on season+date+opponent
            existing = conn.execute("""
                SELECT id FROM games
                WHERE season_id = ? AND game_date = ? AND opponent_name = ?
            """, (season_id, game_date, opponent_name)).fetchone()

        if existing:
            # Update existing game
            conn.execute("""
                UPDATE games SET win_loss = COALESCE(?, win_loss),
                                 runs_for = COALESCE(?, runs_for),
                                 runs_against = COALESCE(?, runs_against),
                                 opponent_team_id = COALESCE(?, opponent_team_id),
                                 notes = COALESCE(?, notes)
                WHERE id = ?
            """, (win_loss, runs_for, runs_against, opponent_team_id, notes, existing['id']))
            return existing['id']
        else:
            # Insert new game
            cursor = conn.execute("""
                INSERT INTO games (season_id, game_date, opponent_name, opponent_team_id,
                                   win_loss, runs_for, runs_against, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (season_id, game_date, opponent_name, opponent_team_id,
                  win_loss, runs_for, runs_against, notes))
            return cursor.lastrowid


def update_game(game_id: int, win_loss: str = None, runs_for: int = None,
                runs_against: int = None) -> None:
    """Update game results"""
    with get_db() as conn:
        conn.execute("""
            UPDATE games SET win_loss = ?, runs_for = ?, runs_against = ?
            WHERE id = ?
        """, (win_loss, runs_for, runs_against, game_id))


def get_season_record(season_id: int) -> Tuple[int, int, int]:
    """Get W-L-T record for a season"""
    with get_db() as conn:
        row = conn.execute("""
            SELECT
                SUM(CASE WHEN win_loss = 'W' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN win_loss = 'L' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN win_loss = 'T' THEN 1 ELSE 0 END) as ties
            FROM games WHERE season_id = ?
        """, (season_id,)).fetchone()
        return (row['wins'] or 0, row['losses'] or 0, row['ties'] or 0)


# =============================================================================
# BATTING STATS OPERATIONS
# =============================================================================

def add_batting_stats(game_id: int, player_id: int, ab: int = 0, r: int = 0,
                      h: int = 0, rbi: int = 0, bb: int = 0, so: int = 0,
                      hbp: int = 0, sac: int = 0) -> int:
    """Add batting stats for a player in a game"""
    with get_db() as conn:
        cursor = conn.execute("""
            INSERT OR REPLACE INTO batting_stats
            (game_id, player_id, ab, r, h, rbi, bb, so, hbp, sac)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (game_id, player_id, ab, r, h, rbi, bb, so, hbp, sac))
        return cursor.lastrowid


def get_batting_stats_for_game(game_id: int) -> List[Dict]:
    """Get all batting stats for a game with player names"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT bs.*, p.name as player_name, p.jersey_number
            FROM batting_stats bs
            JOIN players p ON bs.player_id = p.id
            WHERE bs.game_id = ?
            ORDER BY p.name
        """, (game_id,)).fetchall()
        return [dict(row) for row in rows]


def get_season_batting_stats(season_id: int) -> List[Dict]:
    """Get aggregated batting stats for a season"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT
                p.id as player_id,
                p.name as player_name,
                p.jersey_number,
                SUM(bs.ab) as ab,
                SUM(bs.r) as r,
                SUM(bs.h) as h,
                SUM(bs.rbi) as rbi,
                SUM(bs.bb) as bb,
                SUM(bs.so) as so,
                SUM(bs.hbp) as hbp,
                SUM(bs.sac) as sac,
                CASE WHEN SUM(bs.ab) > 0 THEN ROUND(CAST(SUM(bs.h) AS FLOAT) / SUM(bs.ab), 3) ELSE 0 END as ba
            FROM batting_stats bs
            JOIN games g ON bs.game_id = g.id
            JOIN players p ON bs.player_id = p.id
            WHERE g.season_id = ?
            GROUP BY p.id
            ORDER BY ba DESC
        """, (season_id,)).fetchall()
        return [dict(row) for row in rows]


# =============================================================================
# PITCHING STATS OPERATIONS
# =============================================================================

def add_pitching_stats(game_id: int, player_id: int, ip: float = 0, h: int = 0,
                       r: int = 0, er: int = 0, k: int = 0, bb: int = 0,
                       hbp: int = 0, pitches: int = 0, strikes: int = 0) -> int:
    """Add pitching stats for a player in a game"""
    with get_db() as conn:
        cursor = conn.execute("""
            INSERT OR REPLACE INTO pitching_stats
            (game_id, player_id, ip, h, r, er, k, bb, hbp, pitches, strikes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (game_id, player_id, ip, h, r, er, k, bb, hbp, pitches, strikes))
        return cursor.lastrowid


def get_pitching_stats_for_game(game_id: int) -> List[Dict]:
    """Get all pitching stats for a game with player names"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT ps.*, p.name as player_name, p.jersey_number
            FROM pitching_stats ps
            JOIN players p ON ps.player_id = p.id
            WHERE ps.game_id = ?
            ORDER BY p.name
        """, (game_id,)).fetchall()
        return [dict(row) for row in rows]


def get_season_pitching_stats(season_id: int) -> List[Dict]:
    """Get aggregated pitching stats for a season"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT
                p.id as player_id,
                p.name as player_name,
                p.jersey_number,
                COUNT(DISTINCT ps.game_id) as app,
                SUM(ps.ip) as ip,
                SUM(ps.h) as h,
                SUM(ps.r) as r,
                SUM(ps.er) as er,
                SUM(ps.k) as k,
                SUM(ps.bb) as bb,
                SUM(ps.hbp) as hbp,
                SUM(ps.pitches) as pitches,
                SUM(ps.strikes) as strikes,
                CASE WHEN SUM(ps.ip) > 0 THEN ROUND((CAST(SUM(ps.er) AS FLOAT) * 7) / SUM(ps.ip), 2) ELSE 0 END as era,
                CASE WHEN SUM(ps.ip) > 0 THEN ROUND((CAST(SUM(ps.bb) + SUM(ps.h) AS FLOAT)) / SUM(ps.ip), 2) ELSE 0 END as whip,
                CASE WHEN SUM(ps.pitches) > 0 THEN ROUND(CAST(SUM(ps.strikes) AS FLOAT) / SUM(ps.pitches), 3) ELSE 0 END as strike_pct
            FROM pitching_stats ps
            JOIN games g ON ps.game_id = g.id
            JOIN players p ON ps.player_id = p.id
            WHERE g.season_id = ?
            GROUP BY p.id
            ORDER BY era ASC
        """, (season_id,)).fetchall()
        return [dict(row) for row in rows]


# =============================================================================
# TEAM SCOUTING QUERIES
# =============================================================================

def get_games_vs_team(team_id: int) -> List[Game]:
    """Get all games against a specific team"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM games WHERE opponent_team_id = ? ORDER BY game_date",
            (team_id,)
        ).fetchall()
        return [Game.from_row(row) for row in rows]


def get_record_vs_team(team_id: int) -> Tuple[int, int, int]:
    """Get W-L-T record against a specific team"""
    with get_db() as conn:
        row = conn.execute("""
            SELECT
                SUM(CASE WHEN win_loss = 'W' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN win_loss = 'L' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN win_loss = 'T' THEN 1 ELSE 0 END) as ties
            FROM games WHERE opponent_team_id = ?
        """, (team_id,)).fetchone()
        return (row['wins'] or 0, row['losses'] or 0, row['ties'] or 0)


# =============================================================================
# DASHBOARD/ANALYTICS QUERIES
# =============================================================================

def get_top_batters(season_id: int, stat: str = 'ba', limit: int = 5) -> List[Dict]:
    """Get top batters for a stat"""
    valid_stats = {'ba': 'ba DESC', 'h': 'h DESC', 'r': 'r DESC', 'rbi': 'rbi DESC', 'ab': 'ab DESC'}
    order = valid_stats.get(stat, 'ba DESC')

    with get_db() as conn:
        rows = conn.execute(f"""
            SELECT
                p.name as player_name,
                SUM(bs.ab) as ab,
                SUM(bs.h) as h,
                SUM(bs.r) as r,
                SUM(bs.rbi) as rbi,
                CASE WHEN SUM(bs.ab) > 0 THEN ROUND(CAST(SUM(bs.h) AS FLOAT) / SUM(bs.ab), 3) ELSE 0 END as ba
            FROM batting_stats bs
            JOIN games g ON bs.game_id = g.id
            JOIN players p ON bs.player_id = p.id
            WHERE g.season_id = ?
            GROUP BY p.id
            HAVING SUM(bs.ab) >= 10
            ORDER BY {order}
            LIMIT ?
        """, (season_id, limit)).fetchall()
        return [dict(row) for row in rows]


def get_top_pitchers(season_id: int, stat: str = 'era', limit: int = 5) -> List[Dict]:
    """Get top pitchers for a stat"""
    valid_stats = {'era': 'era ASC', 'k': 'k DESC', 'ip': 'ip DESC', 'whip': 'whip ASC'}
    order = valid_stats.get(stat, 'era ASC')

    with get_db() as conn:
        rows = conn.execute(f"""
            SELECT
                p.name as player_name,
                SUM(ps.ip) as ip,
                SUM(ps.k) as k,
                SUM(ps.bb) as bb,
                CASE WHEN SUM(ps.ip) > 0 THEN ROUND((CAST(SUM(ps.er) AS FLOAT) * 7) / SUM(ps.ip), 2) ELSE 0 END as era,
                CASE WHEN SUM(ps.ip) > 0 THEN ROUND((CAST(SUM(ps.bb) + SUM(ps.h) AS FLOAT)) / SUM(ps.ip), 2) ELSE 0 END as whip
            FROM pitching_stats ps
            JOIN games g ON ps.game_id = g.id
            JOIN players p ON ps.player_id = p.id
            WHERE g.season_id = ?
            GROUP BY p.id
            HAVING SUM(ps.ip) >= 5
            ORDER BY {order}
            LIMIT ?
        """, (season_id, limit)).fetchall()
        return [dict(row) for row in rows]


def get_season_totals(season_id: int) -> Dict:
    """Get season totals (runs for, runs against, etc.)"""
    with get_db() as conn:
        # Exclude "Season Totals" placeholder games from counts
        row = conn.execute("""
            SELECT
                COUNT(*) as games,
                SUM(CASE WHEN win_loss = 'W' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN win_loss = 'L' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN win_loss = 'T' THEN 1 ELSE 0 END) as ties,
                SUM(runs_for) as total_rf,
                SUM(runs_against) as total_ra
            FROM games
            WHERE season_id = ? AND opponent_name NOT LIKE '%Totals%'
        """, (season_id,)).fetchone()
        return dict(row)


# =============================================================================
# DUPLICATE DETECTION
# =============================================================================

def check_game_exists(season_id: int, game_date: str, opponent_name: str,
                      runs_for: int = None, runs_against: int = None) -> Optional[int]:
    """Check if a game already exists, returns game_id if found"""
    with get_db() as conn:
        if runs_for is not None and runs_against is not None:
            row = conn.execute("""
                SELECT id FROM games
                WHERE season_id = ? AND game_date = ? AND opponent_name = ?
                  AND runs_for = ? AND runs_against = ?
            """, (season_id, game_date, opponent_name, runs_for, runs_against)).fetchone()
        else:
            row = conn.execute("""
                SELECT id FROM games
                WHERE season_id = ? AND game_date = ? AND opponent_name = ?
            """, (season_id, game_date, opponent_name)).fetchone()
        return row['id'] if row else None


def check_season_exists(year: int, season_type: str, team_id: int) -> Optional[int]:
    """Check if a season already exists, returns season_id if found"""
    with get_db() as conn:
        row = conn.execute("""
            SELECT id FROM seasons
            WHERE year = ? AND season_type = ? AND team_id = ?
        """, (year, season_type, team_id)).fetchone()
        return row['id'] if row else None


def get_season_game_count(season_id: int) -> int:
    """Get the number of games in a season"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as count FROM games WHERE season_id = ? AND opponent_name NOT LIKE '%Totals%'",
            (season_id,)
        ).fetchone()
        return row['count'] if row else 0


def get_season_stats_summary(season_id: int) -> Dict:
    """Get a summary of stats in a season for duplicate detection"""
    with get_db() as conn:
        # Count games (excluding Totals rows)
        games_row = conn.execute("""
            SELECT COUNT(*) as games
            FROM games
            WHERE season_id = ? AND opponent_name NOT LIKE '%Totals%'
        """, (season_id,)).fetchone()

        # Count players with stats (including from Totals rows since that's where aggregated stats live)
        stats_row = conn.execute("""
            SELECT
                COUNT(DISTINCT bs.player_id) as batters,
                COUNT(DISTINCT ps.player_id) as pitchers,
                SUM(bs.ab) as total_ab,
                SUM(bs.h) as total_h
            FROM games g
            LEFT JOIN batting_stats bs ON g.id = bs.game_id
            LEFT JOIN pitching_stats ps ON g.id = ps.game_id
            WHERE g.season_id = ?
        """, (season_id,)).fetchone()

        return {
            'games': games_row['games'] if games_row else 0,
            'batters': stats_row['batters'] if stats_row else 0,
            'pitchers': stats_row['pitchers'] if stats_row else 0,
            'total_ab': stats_row['total_ab'] if stats_row else None,
            'total_h': stats_row['total_h'] if stats_row else None
        }


# =============================================================================
# LEAGUE-WIDE (AGE GROUP) QUERIES
# =============================================================================

def get_league_batting_stats(age_group_id: int) -> List[Dict]:
    """Get aggregated batting stats for all teams in an age group"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT
                p.id as player_id,
                p.name as player_name,
                p.jersey_number,
                ot.name as team_name,
                SUM(bs.ab) as ab,
                SUM(bs.r) as r,
                SUM(bs.h) as h,
                SUM(bs.rbi) as rbi,
                SUM(bs.bb) as bb,
                SUM(bs.so) as so,
                SUM(bs.hbp) as hbp,
                SUM(bs.sac) as sac,
                CASE WHEN SUM(bs.ab) > 0 THEN ROUND(CAST(SUM(bs.h) AS FLOAT) / SUM(bs.ab), 3) ELSE 0 END as ba
            FROM batting_stats bs
            JOIN games g ON bs.game_id = g.id
            JOIN seasons s ON g.season_id = s.id
            JOIN our_teams ot ON s.team_id = ot.id
            JOIN players p ON bs.player_id = p.id
            WHERE ot.age_group_id = ?
            GROUP BY p.id, ot.id
            ORDER BY ba DESC
        """, (age_group_id,)).fetchall()
        return [dict(row) for row in rows]


def get_league_pitching_stats(age_group_id: int) -> List[Dict]:
    """Get aggregated pitching stats for all teams in an age group"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT
                p.id as player_id,
                p.name as player_name,
                p.jersey_number,
                ot.name as team_name,
                COUNT(DISTINCT ps.game_id) as app,
                SUM(ps.ip) as ip,
                SUM(ps.h) as h,
                SUM(ps.r) as r,
                SUM(ps.er) as er,
                SUM(ps.k) as k,
                SUM(ps.bb) as bb,
                SUM(ps.hbp) as hbp,
                SUM(ps.pitches) as pitches,
                SUM(ps.strikes) as strikes,
                CASE WHEN SUM(ps.ip) > 0 THEN ROUND((CAST(SUM(ps.er) AS FLOAT) * 7) / SUM(ps.ip), 2) ELSE 0 END as era,
                CASE WHEN SUM(ps.ip) > 0 THEN ROUND((CAST(SUM(ps.bb) + SUM(ps.h) AS FLOAT)) / SUM(ps.ip), 2) ELSE 0 END as whip,
                CASE WHEN SUM(ps.pitches) > 0 THEN ROUND(CAST(SUM(ps.strikes) AS FLOAT) / SUM(ps.pitches), 3) ELSE 0 END as strike_pct
            FROM pitching_stats ps
            JOIN games g ON ps.game_id = g.id
            JOIN seasons s ON g.season_id = s.id
            JOIN our_teams ot ON s.team_id = ot.id
            JOIN players p ON ps.player_id = p.id
            WHERE ot.age_group_id = ?
            GROUP BY p.id, ot.id
            ORDER BY era ASC
        """, (age_group_id,)).fetchall()
        return [dict(row) for row in rows]


def get_league_totals(age_group_id: int) -> Dict:
    """Get aggregate totals across all teams in an age group"""
    with get_db() as conn:
        row = conn.execute("""
            SELECT
                COUNT(DISTINCT ot.id) as teams,
                COUNT(DISTINCT s.id) as seasons,
                COUNT(*) as games,
                SUM(CASE WHEN g.win_loss = 'W' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN g.win_loss = 'L' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN g.win_loss = 'T' THEN 1 ELSE 0 END) as ties,
                SUM(g.runs_for) as total_rf,
                SUM(g.runs_against) as total_ra
            FROM games g
            JOIN seasons s ON g.season_id = s.id
            JOIN our_teams ot ON s.team_id = ot.id
            WHERE ot.age_group_id = ? AND g.opponent_name NOT LIKE '%Totals%'
        """, (age_group_id,)).fetchone()
        return dict(row) if row else {}


def get_league_top_batters(age_group_id: int, stat: str = 'ba', limit: int = 5) -> List[Dict]:
    """Get top batters across all teams in an age group"""
    valid_stats = {'ba': 'ba DESC', 'h': 'h DESC', 'r': 'r DESC', 'rbi': 'rbi DESC', 'ab': 'ab DESC'}
    order = valid_stats.get(stat, 'ba DESC')

    with get_db() as conn:
        rows = conn.execute(f"""
            SELECT
                p.name as player_name,
                ot.name as team_name,
                SUM(bs.ab) as ab,
                SUM(bs.h) as h,
                SUM(bs.r) as r,
                SUM(bs.rbi) as rbi,
                CASE WHEN SUM(bs.ab) > 0 THEN ROUND(CAST(SUM(bs.h) AS FLOAT) / SUM(bs.ab), 3) ELSE 0 END as ba
            FROM batting_stats bs
            JOIN games g ON bs.game_id = g.id
            JOIN seasons s ON g.season_id = s.id
            JOIN our_teams ot ON s.team_id = ot.id
            JOIN players p ON bs.player_id = p.id
            WHERE ot.age_group_id = ?
            GROUP BY p.id, ot.id
            HAVING SUM(bs.ab) >= 10
            ORDER BY {order}
            LIMIT ?
        """, (age_group_id, limit)).fetchall()
        return [dict(row) for row in rows]


def get_league_top_pitchers(age_group_id: int, stat: str = 'era', limit: int = 5) -> List[Dict]:
    """Get top pitchers across all teams in an age group"""
    valid_stats = {'era': 'era ASC', 'k': 'k DESC', 'ip': 'ip DESC', 'whip': 'whip ASC'}
    order = valid_stats.get(stat, 'era ASC')

    with get_db() as conn:
        rows = conn.execute(f"""
            SELECT
                p.name as player_name,
                ot.name as team_name,
                SUM(ps.ip) as ip,
                SUM(ps.k) as k,
                SUM(ps.bb) as bb,
                CASE WHEN SUM(ps.ip) > 0 THEN ROUND((CAST(SUM(ps.er) AS FLOAT) * 7) / SUM(ps.ip), 2) ELSE 0 END as era,
                CASE WHEN SUM(ps.ip) > 0 THEN ROUND((CAST(SUM(ps.bb) + SUM(ps.h) AS FLOAT)) / SUM(ps.ip), 2) ELSE 0 END as whip
            FROM pitching_stats ps
            JOIN games g ON ps.game_id = g.id
            JOIN seasons s ON g.season_id = s.id
            JOIN our_teams ot ON s.team_id = ot.id
            JOIN players p ON ps.player_id = p.id
            WHERE ot.age_group_id = ?
            GROUP BY p.id, ot.id
            HAVING SUM(ps.ip) >= 5
            ORDER BY {order}
            LIMIT ?
        """, (age_group_id, limit)).fetchall()
        return [dict(row) for row in rows]


# =============================================================================
# LEAGUE-WIDE QUERIES WITH SEASON FILTER
# =============================================================================

def get_league_batting_stats_by_season(age_group_id: int, year: int, season_type: str) -> List[Dict]:
    """Get aggregated batting stats for all teams in an age group for a specific season"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT
                p.id as player_id,
                p.name as player_name,
                p.jersey_number,
                ot.name as team_name,
                SUM(bs.ab) as ab,
                SUM(bs.r) as r,
                SUM(bs.h) as h,
                SUM(bs.rbi) as rbi,
                SUM(bs.bb) as bb,
                SUM(bs.so) as so,
                SUM(bs.hbp) as hbp,
                SUM(bs.sac) as sac,
                CASE WHEN SUM(bs.ab) > 0 THEN ROUND(CAST(SUM(bs.h) AS FLOAT) / SUM(bs.ab), 3) ELSE 0 END as ba
            FROM batting_stats bs
            JOIN games g ON bs.game_id = g.id
            JOIN seasons s ON g.season_id = s.id
            JOIN our_teams ot ON s.team_id = ot.id
            JOIN players p ON bs.player_id = p.id
            WHERE ot.age_group_id = ? AND s.year = ? AND s.season_type = ?
            GROUP BY p.id, ot.id
            ORDER BY ba DESC
        """, (age_group_id, year, season_type)).fetchall()
        return [dict(row) for row in rows]


def get_league_pitching_stats_by_season(age_group_id: int, year: int, season_type: str) -> List[Dict]:
    """Get aggregated pitching stats for all teams in an age group for a specific season"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT
                p.id as player_id,
                p.name as player_name,
                p.jersey_number,
                ot.name as team_name,
                COUNT(DISTINCT ps.game_id) as app,
                SUM(ps.ip) as ip,
                SUM(ps.h) as h,
                SUM(ps.r) as r,
                SUM(ps.er) as er,
                SUM(ps.k) as k,
                SUM(ps.bb) as bb,
                SUM(ps.hbp) as hbp,
                SUM(ps.pitches) as pitches,
                SUM(ps.strikes) as strikes,
                CASE WHEN SUM(ps.ip) > 0 THEN ROUND((CAST(SUM(ps.er) AS FLOAT) * 7) / SUM(ps.ip), 2) ELSE 0 END as era,
                CASE WHEN SUM(ps.ip) > 0 THEN ROUND((CAST(SUM(ps.bb) + SUM(ps.h) AS FLOAT)) / SUM(ps.ip), 2) ELSE 0 END as whip,
                CASE WHEN SUM(ps.pitches) > 0 THEN ROUND(CAST(SUM(ps.strikes) AS FLOAT) / SUM(ps.pitches), 3) ELSE 0 END as strike_pct
            FROM pitching_stats ps
            JOIN games g ON ps.game_id = g.id
            JOIN seasons s ON g.season_id = s.id
            JOIN our_teams ot ON s.team_id = ot.id
            JOIN players p ON ps.player_id = p.id
            WHERE ot.age_group_id = ? AND s.year = ? AND s.season_type = ?
            GROUP BY p.id, ot.id
            ORDER BY era ASC
        """, (age_group_id, year, season_type)).fetchall()
        return [dict(row) for row in rows]


def get_league_totals_by_season(age_group_id: int, year: int, season_type: str) -> Dict:
    """Get aggregate totals across all teams in an age group for a specific season"""
    with get_db() as conn:
        row = conn.execute("""
            SELECT
                COUNT(DISTINCT ot.id) as teams,
                COUNT(*) as games,
                SUM(CASE WHEN g.win_loss = 'W' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN g.win_loss = 'L' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN g.win_loss = 'T' THEN 1 ELSE 0 END) as ties,
                SUM(g.runs_for) as total_rf,
                SUM(g.runs_against) as total_ra
            FROM games g
            JOIN seasons s ON g.season_id = s.id
            JOIN our_teams ot ON s.team_id = ot.id
            WHERE ot.age_group_id = ? AND s.year = ? AND s.season_type = ?
                AND g.opponent_name NOT LIKE '%Totals%'
        """, (age_group_id, year, season_type)).fetchone()
        return dict(row) if row else {}


def get_league_top_batters_by_season(age_group_id: int, year: int, season_type: str,
                                      stat: str = 'ba', limit: int = 5) -> List[Dict]:
    """Get top batters across all teams in an age group for a specific season"""
    valid_stats = {'ba': 'ba DESC', 'h': 'h DESC', 'r': 'r DESC', 'rbi': 'rbi DESC', 'ab': 'ab DESC'}
    order = valid_stats.get(stat, 'ba DESC')

    with get_db() as conn:
        rows = conn.execute(f"""
            SELECT
                p.name as player_name,
                ot.name as team_name,
                SUM(bs.ab) as ab,
                SUM(bs.h) as h,
                SUM(bs.r) as r,
                SUM(bs.rbi) as rbi,
                CASE WHEN SUM(bs.ab) > 0 THEN ROUND(CAST(SUM(bs.h) AS FLOAT) / SUM(bs.ab), 3) ELSE 0 END as ba
            FROM batting_stats bs
            JOIN games g ON bs.game_id = g.id
            JOIN seasons s ON g.season_id = s.id
            JOIN our_teams ot ON s.team_id = ot.id
            JOIN players p ON bs.player_id = p.id
            WHERE ot.age_group_id = ? AND s.year = ? AND s.season_type = ?
            GROUP BY p.id, ot.id
            HAVING SUM(bs.ab) >= 10
            ORDER BY {order}
            LIMIT ?
        """, (age_group_id, year, season_type, limit)).fetchall()
        return [dict(row) for row in rows]


def get_league_top_pitchers_by_season(age_group_id: int, year: int, season_type: str,
                                       stat: str = 'era', limit: int = 5) -> List[Dict]:
    """Get top pitchers across all teams in an age group for a specific season"""
    valid_stats = {'era': 'era ASC', 'k': 'k DESC', 'ip': 'ip DESC', 'whip': 'whip ASC'}
    order = valid_stats.get(stat, 'era ASC')

    with get_db() as conn:
        rows = conn.execute(f"""
            SELECT
                p.name as player_name,
                ot.name as team_name,
                SUM(ps.ip) as ip,
                SUM(ps.k) as k,
                SUM(ps.bb) as bb,
                CASE WHEN SUM(ps.ip) > 0 THEN ROUND((CAST(SUM(ps.er) AS FLOAT) * 7) / SUM(ps.ip), 2) ELSE 0 END as era,
                CASE WHEN SUM(ps.ip) > 0 THEN ROUND((CAST(SUM(ps.bb) + SUM(ps.h) AS FLOAT)) / SUM(ps.ip), 2) ELSE 0 END as whip
            FROM pitching_stats ps
            JOIN games g ON ps.game_id = g.id
            JOIN seasons s ON g.season_id = s.id
            JOIN our_teams ot ON s.team_id = ot.id
            JOIN players p ON ps.player_id = p.id
            WHERE ot.age_group_id = ? AND s.year = ? AND s.season_type = ?
            GROUP BY p.id, ot.id
            HAVING SUM(ps.ip) >= 5
            ORDER BY {order}
            LIMIT ?
        """, (age_group_id, year, season_type, limit)).fetchall()
        return [dict(row) for row in rows]


def get_available_seasons_for_age_group(age_group_id: int) -> List[Dict]:
    """Get all unique season year/type combinations for an age group"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT DISTINCT s.year, s.season_type
            FROM seasons s
            JOIN our_teams ot ON s.team_id = ot.id
            WHERE ot.age_group_id = ?
            ORDER BY s.year DESC, s.season_type
        """, (age_group_id,)).fetchall()
        return [dict(row) for row in rows]


# =============================================================================
# TEAM ALL-SEASONS QUERIES
# =============================================================================

def get_team_all_seasons_totals(team_id: int) -> Dict:
    """Get aggregate totals across all seasons for a specific team"""
    with get_db() as conn:
        row = conn.execute("""
            SELECT
                COUNT(*) as games,
                SUM(CASE WHEN g.win_loss = 'W' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN g.win_loss = 'L' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN g.win_loss = 'T' THEN 1 ELSE 0 END) as ties,
                SUM(g.runs_for) as total_rf,
                SUM(g.runs_against) as total_ra
            FROM games g
            JOIN seasons s ON g.season_id = s.id
            WHERE s.team_id = ? AND g.opponent_name NOT LIKE '%Totals%'
        """, (team_id,)).fetchone()
        return dict(row) if row else {}


def get_team_all_seasons_batting(team_id: int) -> List[Dict]:
    """Get aggregated batting stats across all seasons for a specific team"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT
                p.id as player_id,
                p.name as player_name,
                p.jersey_number,
                SUM(bs.ab) as ab,
                SUM(bs.r) as r,
                SUM(bs.h) as h,
                SUM(bs.rbi) as rbi,
                SUM(bs.bb) as bb,
                SUM(bs.so) as so,
                SUM(bs.hbp) as hbp,
                SUM(bs.sac) as sac,
                CASE WHEN SUM(bs.ab) > 0 THEN ROUND(CAST(SUM(bs.h) AS FLOAT) / SUM(bs.ab), 3) ELSE 0 END as ba
            FROM batting_stats bs
            JOIN games g ON bs.game_id = g.id
            JOIN seasons s ON g.season_id = s.id
            JOIN players p ON bs.player_id = p.id
            WHERE s.team_id = ?
            GROUP BY p.id
            ORDER BY ba DESC
        """, (team_id,)).fetchall()
        return [dict(row) for row in rows]


def get_team_all_seasons_pitching(team_id: int) -> List[Dict]:
    """Get aggregated pitching stats across all seasons for a specific team"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT
                p.id as player_id,
                p.name as player_name,
                p.jersey_number,
                COUNT(DISTINCT ps.game_id) as app,
                SUM(ps.ip) as ip,
                SUM(ps.h) as h,
                SUM(ps.r) as r,
                SUM(ps.er) as er,
                SUM(ps.k) as k,
                SUM(ps.bb) as bb,
                SUM(ps.hbp) as hbp,
                SUM(ps.pitches) as pitches,
                SUM(ps.strikes) as strikes,
                CASE WHEN SUM(ps.ip) > 0 THEN ROUND((CAST(SUM(ps.er) AS FLOAT) * 7) / SUM(ps.ip), 2) ELSE 0 END as era,
                CASE WHEN SUM(ps.ip) > 0 THEN ROUND((CAST(SUM(ps.bb) + SUM(ps.h) AS FLOAT)) / SUM(ps.ip), 2) ELSE 0 END as whip,
                CASE WHEN SUM(ps.pitches) > 0 THEN ROUND(CAST(SUM(ps.strikes) AS FLOAT) / SUM(ps.pitches), 3) ELSE 0 END as strike_pct
            FROM pitching_stats ps
            JOIN games g ON ps.game_id = g.id
            JOIN seasons s ON g.season_id = s.id
            JOIN players p ON ps.player_id = p.id
            WHERE s.team_id = ?
            GROUP BY p.id
            ORDER BY era ASC
        """, (team_id,)).fetchall()
        return [dict(row) for row in rows]


def get_team_all_seasons_top_batters(team_id: int, stat: str = 'ba', limit: int = 5) -> List[Dict]:
    """Get top batters across all seasons for a specific team"""
    valid_stats = {'ba': 'ba DESC', 'h': 'h DESC', 'r': 'r DESC', 'rbi': 'rbi DESC', 'ab': 'ab DESC'}
    order = valid_stats.get(stat, 'ba DESC')

    with get_db() as conn:
        rows = conn.execute(f"""
            SELECT
                p.name as player_name,
                SUM(bs.ab) as ab,
                SUM(bs.h) as h,
                SUM(bs.r) as r,
                SUM(bs.rbi) as rbi,
                CASE WHEN SUM(bs.ab) > 0 THEN ROUND(CAST(SUM(bs.h) AS FLOAT) / SUM(bs.ab), 3) ELSE 0 END as ba
            FROM batting_stats bs
            JOIN games g ON bs.game_id = g.id
            JOIN seasons s ON g.season_id = s.id
            JOIN players p ON bs.player_id = p.id
            WHERE s.team_id = ?
            GROUP BY p.id
            HAVING SUM(bs.ab) >= 10
            ORDER BY {order}
            LIMIT ?
        """, (team_id, limit)).fetchall()
        return [dict(row) for row in rows]


def get_team_all_seasons_top_pitchers(team_id: int, stat: str = 'era', limit: int = 5) -> List[Dict]:
    """Get top pitchers across all seasons for a specific team"""
    valid_stats = {'era': 'era ASC', 'k': 'k DESC', 'ip': 'ip DESC', 'whip': 'whip ASC'}
    order = valid_stats.get(stat, 'era ASC')

    with get_db() as conn:
        rows = conn.execute(f"""
            SELECT
                p.name as player_name,
                SUM(ps.ip) as ip,
                SUM(ps.k) as k,
                SUM(ps.bb) as bb,
                CASE WHEN SUM(ps.ip) > 0 THEN ROUND((CAST(SUM(ps.er) AS FLOAT) * 7) / SUM(ps.ip), 2) ELSE 0 END as era,
                CASE WHEN SUM(ps.ip) > 0 THEN ROUND((CAST(SUM(ps.bb) + SUM(ps.h) AS FLOAT)) / SUM(ps.ip), 2) ELSE 0 END as whip
            FROM pitching_stats ps
            JOIN games g ON ps.game_id = g.id
            JOIN seasons s ON g.season_id = s.id
            JOIN players p ON ps.player_id = p.id
            WHERE s.team_id = ?
            GROUP BY p.id
            HAVING SUM(ps.ip) >= 5
            ORDER BY {order}
            LIMIT ?
        """, (team_id, limit)).fetchall()
        return [dict(row) for row in rows]


# Initialize database on import
init_database()