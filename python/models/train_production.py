
from pathlib import Path

import duckdb
import joblib
from xgboost import XGBRegressor


ROOT = Path(__file__).resolve().parents[2]

DATABASE = ROOT / "database" / "fantasee_forge.duckdb"
MODEL_PATH = ROOT / "models" / "fantasee_forge_xgb_v3_production.joblib"

FEATURES = [
    "fantasy_points_avg_l2",
    "fantasy_points_avg_l4",
    "fantasy_points_avg_l8",
    "targets_avg_l4",
    "receptions_avg_l4",
    "receiving_yards_avg_l4",
    "rushing_attempts_avg_l4",
    "rushing_yards_avg_l4",
    "offense_pct_avg_l4",
    "team_pass_attempts_avg_l4",
    "defense_fpts_allowed_l4",
    "defense_targets_allowed_l4",
    "defense_receiving_yards_allowed_l4",
]

TARGET = "target_fantasy_points"


def main():

    con = duckdb.connect(str(DATABASE), read_only=True)

    try:
        # The upcoming prediction week determines our training cutoff.
        prediction_week = con.execute("""
            SELECT season, week
            FROM features.prediction_week
        """).fetchone()

        if prediction_week is None:
            raise RuntimeError(
                "Prediction week has not been calculated."
            )

        season, week = prediction_week

        print(f"Upcoming prediction week: {season} Week {week}")

        # Only train on games before the prediction week.
        df = con.execute("""
            SELECT *
            FROM features.model_training_v3
            WHERE season < ?
               OR (season = ? AND week < ?)
        """, [season, season, week]).df()

    finally:
        con.close()

    # Match the V3 backtesting row-filtering policy.
    df = df.dropna(
        subset=FEATURES[:10] + [TARGET]
    ).copy()

    if df.empty:
        raise RuntimeError("No production training data available.")

    if df.duplicated(
        ["season", "week", "game_id", "player_id"]
    ).any():
        raise RuntimeError("Duplicate player-game rows found.")

    latest = (
        df[["season", "week"]]
        .drop_duplicates()
        .sort_values(["season", "week"])
        .iloc[-1]
    )

    trained_season = int(latest["season"])
    trained_week = int(latest["week"])

    # For the current regular-season pipeline, require the
    # immediately preceding week to be represented.
    if (
        trained_season == season
        and trained_week != week - 1
    ):
        raise RuntimeError(
            f"Training data is stale. Latest available: "
            f"{trained_season} Week {trained_week}; "
            f"predicting {season} Week {week}."
        )

    print(f"Training through: {trained_season} Week {trained_week}")
    print(f"Training rows: {len(df):,}")

    model = XGBRegressor(
        n_estimators=500,
        max_depth=4,
        learning_rate=0.03,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="reg:squarederror",
        random_state=42,
        n_jobs=-1,
    )

    model.fit(df[FEATURES], df[TARGET])

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

    bundle = {
        "model": model,
        "features": FEATURES,
        "trained_through_season": trained_season,
        "trained_through_week": trained_week,
        "training_rows": len(df),
    }

    joblib.dump(bundle, MODEL_PATH)

    print(f"Production model saved: {MODEL_PATH}")


if __name__ == "__main__":
    main()
