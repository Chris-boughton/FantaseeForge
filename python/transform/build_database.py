from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / "database" / "fantasee_forge.duckdb"
SQL_DIR = ROOT / "sql"

SQL_FILES = [
    "staging/player_game.sql",
    "features/player_rolling.sql",
    "features/player_opportunity.sql",
    "features/model_training.sql",
    "features/model_training_clean.sql",
    "features/model_training_v2.sql",
    "features/model_training_v2_clean.sql",
    "features/defense_matchup_v3.sql",
    "features/model_training_v3.sql",
]


def main():
    con = duckdb.connect(str(DATABASE))

    try:
        con.execute("BEGIN TRANSACTION")

        for schema in ["raw", "staging", "features", "marts"]:
            con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

        for filename in SQL_FILES:
            path = SQL_DIR / filename

            if not path.exists():
                raise FileNotFoundError(path)

            print(f"Running: {filename}")
            con.execute(path.read_text(encoding="utf-8"))

        con.execute("COMMIT")
        print("Database build complete.")

    except Exception:
        con.execute("ROLLBACK")
        raise

    finally:
        con.close()


if __name__ == "__main__":
    main()