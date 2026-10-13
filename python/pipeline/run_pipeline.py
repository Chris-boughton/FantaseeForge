
from pathlib import Path
import subprocess
import sys
import duckdb
import argparse

ROOT = Path(__file__).resolve().parents[2]

DB_PATH = ROOT / "database" / "fantasee_forge.duckdb"

SQL_FILES = [
    "sql/features/upcoming_player_pool.sql",
    "sql/features/upcoming_player_features.sql",
]

def run_script(relative_path):
    print(f"\n=== Running {relative_path} ===", flush=True)

    subprocess.run(
        [sys.executable, str(ROOT / relative_path)],
        cwd=ROOT,
        check=True,
    )

def validate_training_data():
    print("\n=== Validating historical game completeness ===")

    con = duckdb.connect(str(DB_PATH), read_only=True)

    try:
        result = con.execute("""
            WITH prediction AS (
                SELECT season, week
                FROM features.prediction_week
            ),
            previous_week AS (
                SELECT
                    s.season,
                    s.week
                FROM raw.schedules s
                CROSS JOIN prediction p
                WHERE s.game_type = 'REG'
                  AND (
                      s.season < p.season
                      OR (
                          s.season = p.season
                          AND s.week < p.week
                      )
                  )
                GROUP BY s.season, s.week
                ORDER BY s.season DESC, s.week DESC
                LIMIT 1
            ),
            scheduled AS (
                SELECT
                    s.game_id,
                    s.home_score,
                    s.away_score
                FROM raw.schedules s
                INNER JOIN previous_week pw
                    ON s.season = pw.season
                   AND s.week = pw.week
                WHERE s.game_type = 'REG'
            ),
            player_games AS (
                SELECT DISTINCT game_id
                FROM staging.player_game
            )
            SELECT
                COUNT(*) AS scheduled_games,
                COUNT(*) FILTER (
                    WHERE s.home_score IS NOT NULL
                      AND s.away_score IS NOT NULL
                ) AS games_with_scores,
                COUNT(*) FILTER (
                    WHERE pg.game_id IS NOT NULL
                ) AS games_with_player_stats
            FROM scheduled s
            LEFT JOIN player_games pg
                ON s.game_id = pg.game_id
        """).fetchone()

        scheduled, scored, with_stats = result

        print(f"Scheduled games: {scheduled}")
        print(f"Games with scores: {scored}")
        print(f"Games with player statistics: {with_stats}")

        if scheduled == 0:
            raise RuntimeError(
                "No previous-week schedule found."
            )

        if scored != scheduled:
            raise RuntimeError(
                "Previous NFL week is not fully completed."
            )

        if with_stats != scheduled:
            raise RuntimeError(
                "Player statistics are missing for "
                "one or more completed games."
            )

        print("Historical game completeness validation passed.")

    finally:
        con.close()


def validate_prediction_week():
    print("\n=== Validating prediction week ===")

    con = duckdb.connect(str(DB_PATH), read_only=True)

    try:
        result = con.execute("""
            SELECT
                COUNT(*) AS scheduled_games,
                COUNT(*) FILTER (
                    WHERE s.home_score IS NOT NULL
                       OR s.away_score IS NOT NULL
                ) AS games_with_scores,
                MIN(TRY_CAST(s.gameday AS DATE)) AS first_game_date
            FROM raw.schedules s
            INNER JOIN features.prediction_week pw
                ON s.season = pw.season
               AND s.week = pw.week
            WHERE s.game_type = 'REG'
        """).fetchone()

        scheduled, scored, first_date = result

        print(f"Scheduled games: {scheduled}")
        print(f"Games with scores: {scored}")
        print(f"First game date: {first_date}")

        if scheduled == 0:
            raise RuntimeError(
                "No games found for the prediction week."
            )

        if scored > 0:
            raise RuntimeError(
                "Prediction week has already started. "
                "Refusing to regenerate weekly predictions."
            )

        if first_date is None or first_date <= __import__("datetime").date.today():
            raise RuntimeError(
                "Prediction week begins today or has already begun. "
                "Refusing to regenerate predictions."
            )

        print("Prediction week validation passed.")

    finally:
        con.close()


def select_prediction_week():
    print("\n=== Selecting prediction week ===")

    path = ROOT / "sql/features/prediction_week.sql"

    con = duckdb.connect(str(DB_PATH))

    try:
        con.execute("BEGIN TRANSACTION")
        con.execute(path.read_text(encoding="utf-8"))

        result = con.execute("""
            SELECT season, week, first_game_date
            FROM features.prediction_week
        """).fetchone()

        if result is None:
            raise RuntimeError(
                "No upcoming NFL prediction week found."
            )

        season, week, first_game_date = result

        con.execute("COMMIT")

        print(
            f"Selected: {season} Week {week}, "
            f"starting {first_game_date}"
        )

    except Exception:
        con.execute("ROLLBACK")
        raise

    finally:
        con.close()

def run_sql_pipeline():
    print("\n=== Building upcoming prediction features ===")

    con = duckdb.connect(str(DB_PATH))

    try:
        con.execute("BEGIN TRANSACTION")

        for relative_path in SQL_FILES:
            path = ROOT / relative_path

            print(f"Running: {relative_path}", flush=True)

            sql = path.read_text(encoding="utf-8")
            con.execute(sql)

        result = con.execute("""
            SELECT
                season,
                week,
                COUNT(*) AS players,
                COUNT(DISTINCT player_id) AS unique_players
            FROM features.upcoming_player_features
            GROUP BY season, week
        """).fetchall()

        if len(result) != 1:
            raise RuntimeError(
                f"Expected one prediction week, got {result}"
            )

        season, week, players, unique_players = result[0]

        if players == 0 or players != unique_players:
            raise RuntimeError(
                "Feature validation failed: empty or duplicate players."
            )

        con.execute("COMMIT")

        print(
            f"Features ready: {season} Week {week}, "
            f"{players} players"
        )

    except Exception:
        con.execute("ROLLBACK")
        raise

    finally:
        con.close()


def run_predictions():
    print("\n=== Generating predictions ===", flush=True)

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "python" / "models" / "predict.py")
        ],
        cwd=ROOT,
        check=True,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--full-refresh",
        action="store_true",
        help="Download, load, rebuild and retrain before predicting.",
    )
    args = parser.parse_args()

    print("=== Fantasee Forge Prediction Pipeline ===")

    if args.full_refresh:
        run_script("python/ingest/download_data.py")
        run_script("python/ingest/load_raw_data.py")
        run_script("python/transform/build_database.py")

    select_prediction_week()
    validate_training_data()
    validate_prediction_week()
    run_sql_pipeline()
    
    if args.full_refresh:
        run_script("python/models/train_production.py")

    run_predictions()

    print("\n=== Pipeline completed successfully ===")


if __name__ == "__main__":
    main()
