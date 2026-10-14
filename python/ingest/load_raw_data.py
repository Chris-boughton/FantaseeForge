from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parents[2]

DATABASE = ROOT / "database" / "fantasee_forge.duckdb"
RAW_DIR = ROOT / "data" / "raw"
DATASETS = {
    "player_stats": "player_stats/player_stats_*.parquet",
    "rosters": "rosters/rosters_*.parquet",
    "rosters_weekly": "rosters_weekly/rosters_weekly_*.parquet",
    "snap_counts": "snap_counts/snap_counts_*.parquet",
    "injuries": "injuries/injuries_*.parquet",
    "players": "players/players.parquet",
    "schedules": "schedules/schedules.parquet",
}


def main():
    DATABASE.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(DATABASE))

    try:
        con.execute("BEGIN TRANSACTION")
        con.execute("CREATE SCHEMA IF NOT EXISTS raw")

        for table_name, pattern in DATASETS.items():
            files = sorted(RAW_DIR.glob(pattern))

            if not files:
                raise FileNotFoundError(
                    f"No Parquet files found for {table_name}: {pattern}"
                )

            print(f"\nLoading raw.{table_name}")
            print(f"Parquet files: {len(files)}")

            file_paths = [
                str(path.resolve()) for path in files
            ]

            # DuckDB accepts a list of Parquet files.
            con.execute(
                f"""
                CREATE OR REPLACE TABLE raw.{table_name} AS
                SELECT *
                FROM read_parquet(?, union_by_name=true)
                """,
                [file_paths],
            )

            result = con.execute(
                f"""
                SELECT COUNT(*)
                FROM raw.{table_name}
                """
            ).fetchone()

            print(f"Rows loaded: {result[0]:,}")

        con.execute("COMMIT")
        print("\nRaw data load complete.")

    except Exception:
        con.execute("ROLLBACK")
        raise

    finally:
        con.close()


if __name__ == "__main__":
    main()