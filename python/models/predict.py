
from pathlib import Path
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

EXPORT_DIR.mkdir(parents=True, exist_ok=True)
WEBSITE_DIR.mkdir(parents=True, exist_ok=True)


def publish_website_predictions(payload, website_path):
    """
    Validate and atomically publish predictions.json.

    The existing website file is only replaced after the
    complete JSON payload has been written successfully.
    """

    website_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    predictions = payload.get("predictions", [])

    if not predictions:
        raise RuntimeError(
            "Refusing to publish empty predictions."
        )

    if payload.get("player_count") != len(predictions):
        raise RuntimeError(
            "Prediction count does not match payload."
        )

    if type(payload.get("season")) is not int:
        raise RuntimeError(
            "Invalid prediction season."
        )

    if type(payload.get("week")) is not int:
        raise RuntimeError(
            "Invalid prediction week."
        )

    if not 1 <= payload["week"] <= 18:
        raise RuntimeError(
            "Prediction week is outside the regular season."
        )

    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            prefix=".predictions_",
            dir=website_path.parent,
            delete=False
        ) as tmp:

            json.dump(
                payload,
                tmp,
                indent=2,
                allow_nan=False
            )

            tmp.flush()
            os.fsync(tmp.fileno())

            temp_path = Path(tmp.name)

        # Atomic replacement on the same filesystem.
        os.replace(temp_path, website_path)

        print("Website predictions published successfully.")

    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def main():

    # --------------------------------------------------
    # 1. Load upcoming prediction features
    # --------------------------------------------------

    con = duckdb.connect(
        str(DB_PATH),
        read_only=True
    )

    try:
        prediction_week = con.execute("""
            SELECT season, week
            FROM features.prediction_week
        """).fetchone()

        if prediction_week is None:
            raise RuntimeError(
                "No upcoming prediction week found."
            )

        season, week = prediction_week

        df = con.execute("""
            SELECT *
            FROM features.upcoming_player_features
            WHERE season = ?
              AND week = ?
        """, [season, week]).df()

    finally:
        con.close()

    print(
        f"Generating predictions for {season} Week {week}"
    )
    print(
        f"Upcoming players loaded: {len(df)}"
    )

    if df.empty:
        raise RuntimeError(
            "No upcoming player features found."
        )

    # --------------------------------------------------
    # 2. Load production model
    # --------------------------------------------------

    bundle = joblib.load(MODEL_PATH)

    model = bundle["model"]
    features = bundle["features"]

    trained_season = bundle.get(
        "trained_through_season"
    )

    trained_week = bundle.get(
        "trained_through_week"
    )

    # Ensure training cutoff metadata exists.
    if trained_season is None or trained_week is None:
        raise RuntimeError(
            "Production model is missing training cutoff metadata."
        )

    trained_season = int(trained_season)
    trained_week = int(trained_week)

    season = int(season)
    week = int(week)

    # Prevent training data overlapping prediction week.
    if trained_season > season or (
        trained_season == season
        and trained_week >= week
    ):
        raise RuntimeError(
            "Model training cutoff overlaps the prediction week. "
            "Possible data leakage."
        )

    # Ensure model is trained through previous week.
    if (
        trained_season == season
        and trained_week != week - 1
    ):
        raise RuntimeError(
            f"Model is stale: trained through Week {trained_week}, "
            f"but predicting Week {week}."
        )

    print(
        f"Model trained through: "
        f"{trained_season} Week {trained_week}"
    )

    # --------------------------------------------------
    # 3. Validate model features
    # --------------------------------------------------

    missing_columns = [
        col for col in features
        if col not in df.columns
    ]

    if missing_columns:
        raise RuntimeError(
            f"Missing model features: {missing_columns}"
        )

    # First ten features are mandatory.
    # Defensive matchup features may contain missing values.
    required_features = features[:10]

    eligible = df.dropna(
        subset=required_features
    ).copy()

    excluded = df.loc[
        ~df.index.isin(eligible.index)
    ].copy()

    print(
        f"Players eligible: {len(eligible)}"
    )
    print(
        f"Players excluded: {len(excluded)}"
    )

    if eligible.empty:
        raise RuntimeError(
            "No eligible players to predict."
        )

    # --------------------------------------------------
    # 4. Generate predictions
    # --------------------------------------------------

    X = eligible[features]

    predictions = np.asarray(
        model.predict(X),
        dtype=float
    )

    if not np.isfinite(predictions).all():
        raise RuntimeError(
            "Model generated NaN or infinite predictions. "
            "Refusing to publish."
        )

    eligible["projection"] = np.round(
        np.maximum(predictions, 0),
        2
    )

    eligible = eligible.sort_values(
        "projection",
        ascending=False
    ).reset_index(drop=True)

    eligible["rank"] = np.arange(
        1,
        len(eligible) + 1
    )

    # --------------------------------------------------
    # 5. Prepare output
    # --------------------------------------------------

    output_columns = [
        "rank",
        "season",
        "week",
        "game_id",
        "player_id",
        "player_display_name",
        "position",
        "team",
        "opponent_team",
        "is_home",
        "gameday",
        "gametime",
        "projection",
    ]

    output = eligible[output_columns].copy()

    records = json.loads(
        output.to_json(
            orient="records",
            date_format="iso"
        )
    )

    payload = {
        "season": season,
        "week": week,
        "model": "V3",
        "trained_through_season": trained_season,
        "trained_through_week": trained_week,
        "player_count": len(records),
        "predictions": records,
    }

    # --------------------------------------------------
    # 6. Define export paths
    # --------------------------------------------------

    parquet_path = (
        EXPORT_DIR /
        f"predictions_{season}_week{week}.parquet"
    )

    json_path = (
        EXPORT_DIR /
        f"predictions_{season}_week{week}.json"
    )

    website_path = (
        WEBSITE_DIR /
        "predictions.json"
    )

    excluded_path = (
        EXPORT_DIR /
        f"predictions_{season}_week{week}_excluded.csv"
    )

    # --------------------------------------------------
    # 7. Export prediction files
    # --------------------------------------------------

    output.to_parquet(
        parquet_path,
        index=False
    )

    with json_path.open(
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            payload,
            f,
            indent=2,
            allow_nan=False
        )

    excluded.to_csv(
        excluded_path,
        index=False
    )

    # --------------------------------------------------
    # 8. Atomically publish website JSON
    # --------------------------------------------------

    publish_website_predictions(
        payload,
        website_path
    )

    # --------------------------------------------------
    # 9. Display results
    # --------------------------------------------------

    print("\nTop 20 projections:")
    print(
        output.head(20).to_string(
            index=False
        )
    )

    print(
        f"\nSaved Parquet: {parquet_path}"
    )
    print(
        f"Saved JSON: {json_path}"
    )
    print(
        f"Saved website JSON: {website_path}"
    )
    print(
        f"Saved excluded report: {excluded_path}"
    )


if __name__ == "__main__":
    main()
