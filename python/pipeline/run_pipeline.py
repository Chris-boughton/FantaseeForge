
from pathlib import Path
from datetime import date
import argparse
import os
import subprocess
import sys

import duckdb


class DataNotReadyError(Exception):
    """Expected condition: NFL data is not ready for publication."""
    pass


ROOT = Path(__file__).resolve().parents[2]

DB_PATH = ROOT / "database" / "fantasee_forge.duckdb"

SQL_FILES = [
    "sql/features/upcoming_player_pool.sql",
    "sql/features/upcoming_player_features.sql",
]


def report_pipeline_status(status):
    """
    Report pipeline outcome to GitHub Actions.

    Valid statuses:
        published - New predictions were generated.
        skipped   - NFL data was not ready.

    Also works locally, where GITHUB_OUTPUT is not defined.
    """
    if status not in {"published", "skipped"}:
        raise ValueError(f"Invalid pipeline status: {status}")

    print(f"\nPipeline status: {status}", flush=True)

    github_output = os.environ.get("GITHUB_OUTPUT")

    if github_output:
        with open(github_output, "a", encoding="utf-8") as output:
            output.write(f"status={status}\n")


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
                "No previous-week schedule found. "
                "Check the NFL schedules table and prediction-week selection."
            )

        if scored != scheduled:
            raise DataNotReadyError(
                f"Previous NFL week is incomplete: "
                f"{scored}/{scheduled} games have scores."
            )

        if with_stats != scheduled:
            raise DataNotReadyError(
                f"Player statistics are incomplete: "
                f"{with_stats}/{scheduled} games have player statistics."
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
            raise DataNotReadyError(
                "Prediction week has already started. "
                "Skipping weekly prediction update."
            )

        if first_date is None:
            raise RuntimeError(
                "Prediction week has no valid start date."
            )

        if first_date <= date.today():
            raise DataNotReadyError(
                "Prediction week begins today or has already begun. "
                "Skipping weekly prediction update."
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
            raise DataNotReadyError(
                "No future NFL prediction week is currently available."
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
            str(ROOT / "python" / "models" / "predict.py"),
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

    parser.add_argument(
        "--test-skip",
        action="store_true",
        help="Test skip handling without modifying predictions or database.",
    )

    args = parser.parse_args()

    print("=== Fantasee Forge Prediction Pipeline ===")

    if args.test_skip:
        raise DataNotReadyError(
            "Simulated incomplete NFL data for testing."
        )

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

    report_pipeline_status("published")

    print("\n=== Pipeline completed successfully ===")


if __name__ == "__main__":
    try:
        main()

    except DataNotReadyError as exc:
        print(f"\nSKIPPED: {exc}")
        print("Existing website predictions have not been changed.")

        report_pipeline_status("skipped")

        raise SystemExit(0)
