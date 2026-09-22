from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / "database" / "fantasee_forge.duckdb"

def main():
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DATABASE))
    print("Creating schemas")
    con.execute("""
        CREATE SCHEMA IF NOT EXISTS raw;
        CREATE SCHEMA IF NOT EXISTS staging;
        CREATE SCHEMA IF NOT EXISTS features;
        CREATE SCHEMA IF NOT EXISTS marts;
    """)

    print("Loading raw player stats")
    con.execute("""
        CREATE OR REPLACE TABLE raw.player_stats AS
        SELECT * 
        FROM read_parquet('data/raw/player_stats/*.parquet');
    """)
    
    print("Loading raw snap counts")
    con.execute("""
        CREATE OR REPLACE TABLE raw.snap_counts AS
        SELECT *
        FROM read_parquet('data/raw/snap_counts/*.parquet');
    """)
    
    print("Loading raw rosters")
    con.execute("""
        CREATE OR REPLACE TABLE raw.rosters AS
        SELECT *
        FROM read_parquet('data/raw/rosters/*.parquet');
    """)

    print("Loading raw injuries")
    con.execute("""
        CREATE OR REPLACE TABLE raw.injuries AS
        SELECT *
        FROM read_parquet('data/raw/injuries/*.parquet',
                          union_by_name=True);
    """)
    
    print("Loading raw players")
    con.execute("""
        CREATE OR REPLACE TABLE raw.players AS
        SELECT *
        FROM read_parquet('data/raw/players/players.parquet');
    """)
    
    print("Loading raw schedules")
    con.execute("""
        CREATE OR REPLACE TABLE raw.schedules AS
        SELECT *
        FROM read_parquet('data/raw/schedules/schedules.parquet');
    """)
    
    print("Database built")
    print(
        con.execute("""
            SELECT
                COUNT(*) AS rows
            FROM raw.player_stats
        """).fetchdf()
    )
    con.close()

if __name__ == "__main__":
    main()