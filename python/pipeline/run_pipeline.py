
from pathlib import Path
from datetime import date
import argparse
import os
import subprocess
import sys
import json
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

        dry_run   - Predictions generated without publication.

    Also works locally, where GITHUB_OUTPUT is not defined.

    """

    if status not in {"published", "skipped", "dry_run"}:

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

    from datetime import datetime

    from zoneinfo import ZoneInfo

    nfl_today = datetime.now(

        ZoneInfo("America/New_York")

    ).date()

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

        print(f"Current NFL date (Eastern): {nfl_today}")

        if scheduled == 0:

            raise RuntimeError(

                "No games found for the prediction week."

            )

        if first_date is None:

            raise RuntimeError(

                "Prediction week has no valid start date."

            )

        if scored > 0:

            raise DataNotReadyError(

                "Prediction week has already started. "

                "Existing predictions will be preserved."

            )

        if first_date <= nfl_today:

            raise DataNotReadyError(

                "Prediction week begins today or has already begun. "

                "Existing predictions will be preserved."

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

def run_predictions(dry_run=False):
    print("\n=== Generating predictions ===", flush=True)

    command = [
        sys.executable,
        str(ROOT / "python" / "models" / "predict.py"),
    ]

    if dry_run:
        command.append("--dry-run")

    subprocess.run(command, cwd=ROOT, check=True)


def predictions_already_published(season, week):

    predictions_path = ROOT / "website/data/predictions.json"

    if not predictions_path.exists():

        return False

    with predictions_path.open("r", encoding="utf-8") as file:

        data = json.load(file)

    return (

        data.get("season") == season

        and data.get("week") == week

        and isinstance(data.get("predictions"), list)

        and len(data["predictions"]) > 0

    )

def check_existing_publication():

    predictions_path = ROOT / "website/data/predictions.json"

    if not predictions_path.exists() or not DB_PATH.exists():

        return

    with predictions_path.open("r", encoding="utf-8") as file:

        data = json.load(file)

    season = data.get("season")

    week = data.get("week")

    if not isinstance(season, int) or not isinstance(week, int):

        return

    con = duckdb.connect(str(DB_PATH), read_only=True)

    try:

        result = con.execute("""

            SELECT

                MAX(TRY_CAST(gameday AS DATE))

            FROM raw.schedules

            WHERE season = ?

              AND week = ?

              AND game_type = 'REG'

        """, [season, week]).fetchone()

        last_game_date = result[0]

    finally:

        con.close()

    if last_game_date is None:

        return

    from datetime import datetime

    from zoneinfo import ZoneInfo

    nfl_today = datetime.now(

        ZoneInfo("America/New_York")

    ).date()

    if nfl_today <= last_game_date:

        raise DataNotReadyError(

            f"Predictions for {season} Week {week} "

            "are already published."

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

    parser.add_argument(

        "--force-refresh",

        action="store_true",

        help="Allow regeneration of already published predictions.",

    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and generate predictions without publishing files.",
    )

    args = parser.parse_args()

    print("=== Fantasee Forge Prediction Pipeline ===")

    if args.test_skip:

        raise DataNotReadyError(

            "Simulated incomplete NFL data for testing."

        )

    if not args.force_refresh and not args.full_refresh and not args.dry_run:

        check_existing_publication()

    if args.full_refresh:

        run_script("python/ingest/download_data.py")

        run_script("python/ingest/load_raw_data.py")

        run_script("python/transform/build_database.py")

    select_prediction_week()

    con = duckdb.connect(str(DB_PATH), read_only=True)

    try:

        season, week = con.execute("""

            SELECT season, week

            FROM features.prediction_week

        """).fetchone()

    finally:

        con.close()

    if week == 1:

        raise DataNotReadyError(

            "Week 1 predictions require a verified pregame roster snapshot. "

            "Existing predictions will be preserved."

        )

    if (

        not args.force_refresh

        and not args.dry_run

        and predictions_already_published(season, week)

    ):

        raise DataNotReadyError(

            f"Predictions for {season} Week {week} "

            "have already been published."

    )

    validate_training_data()

    validate_prediction_week()

    run_sql_pipeline()

    if args.full_refresh:

        run_script("python/models/train_production.py")

    run_predictions(dry_run=args.dry_run)

    if args.dry_run:
        report_pipeline_status("dry_run")
        print("\n=== Pipeline dry run completed successfully ===")
    else:
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
