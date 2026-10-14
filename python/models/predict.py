from pathlib import Path
import argparse
import json
import os
import tempfile

import duckdb
import joblib
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "database" / "fantasee_forge.duckdb"
MODEL_PATH = ROOT / "models" / "fantasee_forge_xgb_v3_production.joblib"
EXPORT_DIR = ROOT / "data" / "exports"
WEBSITE_DIR = ROOT / "website" / "data"
MIN_PLAYER_COVERAGE = 0.90


def validate_prediction_payload(payload):
    """Check payload consistency before exporting or publishing."""
    predictions = payload.get("predictions", [])
    if not predictions:
        raise RuntimeError("Refusing to publish empty predictions.")
    if payload.get("player_count") != len(predictions):
        raise RuntimeError("Prediction count does not match payload.")
    if type(payload.get("season")) is not int:
        raise RuntimeError("Invalid prediction season.")
    if type(payload.get("week")) is not int:
        raise RuntimeError("Invalid prediction week.")
    if not 1 <= payload["week"] <= 18:
        raise RuntimeError("Prediction week is outside the regular season.")
    # Fail early if JSON cannot be serialized strictly.
    json.dumps(payload, allow_nan=False)


def publish_website_predictions(payload, website_path):
    """Validate and atomically publish predictions.json."""
    validate_prediction_payload(payload)
    website_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            prefix=".predictions_",
            dir=website_path.parent,
            delete=False,
        ) as tmp:
            json.dump(payload, tmp, indent=2, allow_nan=False)
            tmp.flush()
            os.fsync(tmp.fileno())
            temp_path = Path(tmp.name)
        os.replace(temp_path, website_path)
        print("Website predictions published successfully.")
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate and validate predictions without writing prediction files.",
    )
    args = parser.parse_args()

    # 1. Load upcoming prediction features.
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        prediction_week = con.execute("""
            SELECT season, week
            FROM features.prediction_week
        """).fetchone()
        if prediction_week is None:
            raise RuntimeError("No upcoming prediction week found.")
        season, week = map(int, prediction_week)
        df = con.execute("""
            SELECT *
            FROM features.upcoming_player_features
            WHERE season = ? AND week = ?
        """, [season, week]).df()
    finally:
        con.close()

    print(f"Generating predictions for {season} Week {week}")
    print(f"Upcoming players loaded: {len(df)}")
    if df.empty:
        raise RuntimeError("No upcoming player features found.")
    if df["player_id"].duplicated().any():
        duplicates = df.loc[
            df["player_id"].duplicated(keep=False),
            ["player_id", "player_display_name"],
        ]
        raise RuntimeError(
            "Duplicate players in upcoming features:\n"
            + duplicates.to_string(index=False)
        )

    # 2. Load the production model and validate its training cutoff.
    bundle = joblib.load(MODEL_PATH)
    model = bundle["model"]
    features = bundle["features"]
    trained_season = bundle.get("trained_through_season")
    trained_week = bundle.get("trained_through_week")
    if trained_season is None or trained_week is None:
        raise RuntimeError("Production model is missing training cutoff metadata.")
    trained_season = int(trained_season)
    trained_week = int(trained_week)
    if trained_season > season or (
        trained_season == season and trained_week >= week
    ):
        raise RuntimeError(
            "Model training cutoff overlaps the prediction week. Possible data leakage."
        )
    if trained_season == season and trained_week != week - 1:
        raise RuntimeError(
            f"Model is stale: trained through Week {trained_week}, "
            f"but predicting Week {week}."
        )
    print(f"Model trained through: {trained_season} Week {trained_week}")

    # 3. Validate model features and player coverage.
    missing_columns = [col for col in features if col not in df.columns]
    if missing_columns:
        raise RuntimeError(f"Missing model features: {missing_columns}")
    required_features = features[:10]
    eligible = df.dropna(subset=required_features).copy()
    excluded = df.loc[~df.index.isin(eligible.index)].copy()
    coverage = len(eligible) / len(df)
    print(f"Players eligible: {len(eligible)}")
    print(f"Players excluded: {len(excluded)}")
    print(f"Prediction coverage: {coverage:.1%}")
    if eligible.empty:
        raise RuntimeError("No eligible players to predict.")
    if coverage < MIN_PLAYER_COVERAGE:
        raise RuntimeError(
            f"Prediction coverage too low: {coverage:.1%}. "
            f"Minimum required: {MIN_PLAYER_COVERAGE:.0%}. "
            "Refusing to publish incomplete predictions."
        )

    # 4. Generate predictions.
    X = eligible[features]
    predictions = np.asarray(model.predict(X), dtype=float)
    if not np.isfinite(predictions).all():
        raise RuntimeError(
            "Model generated NaN or infinite predictions. Refusing to publish."
        )
    eligible["projection"] = np.round(np.maximum(predictions, 0), 2)
    eligible = eligible.sort_values(
        "projection", ascending=False
    ).reset_index(drop=True)
    eligible["rank"] = np.arange(1, len(eligible) + 1)

    # 5. Prepare and validate output.
    output_columns = [
        "rank", "season", "week", "game_id", "player_id",
        "player_display_name", "position", "team", "opponent_team",
        "is_home", "gameday", "gametime", "projection",
    ]
    output = eligible[output_columns].copy()
    records = json.loads(output.to_json(orient="records", date_format="iso"))
    payload = {
        "season": season,
        "week": week,
        "model": "V3",
        "trained_through_season": trained_season,
        "trained_through_week": trained_week,
        "player_count": len(records),
        "predictions": records,
    }
    validate_prediction_payload(payload)

    print("\nTop 20 projections:")
    print(output.head(20).to_string(index=False))

    # Dry run stops before directory creation or any file write.
    if args.dry_run:
        print("\n=== DRY RUN COMPLETE ===")
        print(f"Season: {season}; Week: {week}")
        print(f"Predictions generated: {len(records)}")
        print(f"Players excluded: {len(excluded)}")
        print(f"Prediction coverage: {coverage:.1%}")
        print("No prediction files were written.")
        print("Existing website predictions were preserved.")
        return

    # 6. Export prediction files and publish website JSON.
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    parquet_path = EXPORT_DIR / f"predictions_{season}_week{week}.parquet"
    json_path = EXPORT_DIR / f"predictions_{season}_week{week}.json"
    website_path = WEBSITE_DIR / "predictions.json"
    excluded_path = EXPORT_DIR / f"predictions_{season}_week{week}_excluded.csv"

    output.to_parquet(parquet_path, index=False)
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, allow_nan=False)
    excluded.to_csv(excluded_path, index=False)
    publish_website_predictions(payload, website_path)

    print(f"\nSaved Parquet: {parquet_path}")
    print(f"Saved JSON: {json_path}")
    print(f"Saved website JSON: {website_path}")
    print(f"Saved excluded report: {excluded_path}")


if __name__ == "__main__":
    main()
