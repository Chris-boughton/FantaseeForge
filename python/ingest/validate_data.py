from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / "database" / "fantasee_forge.duckdb"
REQUIRED_PLAYER_COLUMNS = [
    "player_id",
    "season",
    "week",
    "game_id",
    "team",
    "opponent_team",
    "position",
    "targets",
    "receptions",
    "receiving_yards",
]

def main():
    con = duckdb.connect(str(DATABASE))
    columns = con.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'raw'
            AND table_name = 'player_stats'
    """).fetchdf()
    
    available = set(
        columns["column_name"]
    )
    
    missing = [
        column
        for column in REQUIRED_PLAYER_COLUMNS
        if column not in available
    ]

    if missing:
        raise RuntimeError(
            "Missing required player-stat columns: " + ", ".join(missing)
        )
    
    row_count = con.execute("""
        SELECT COUNT(*)
        FROM raw.player_stats
    """).fetchone()[0]
    
    if row_count == 0:
        raise RuntimeError(
            "raw.player_stats contains zero rows."
        )
    
    duplicate_games = con.execute("""
        SELECT 
            COUNT(*) AS total_rows,
            COUNT(DISTINCT game_id) AS games
        FROM raw.player_stats
    """).fetchone()
    
    print(f"Player stat rows: {row_count:,}")
    print( f"Distinct games: {duplicate_games[1]:,}" )
    print("Validation passed.")
    con.close()

if __name__ == "__main__":
    main()