from pathlib import Path

import duckdb
import joblib
import pandas as pd

from sklearn.metrics import mean_absolute_error, mean_squared_error
from scipy.stats import spearmanr


ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / "database" / "fantasee_forge.duckdb"
MODEL_DIR = ROOT / "models"

V1_FEATURES = [
    "fantasy_points_avg_l2",
    "fantasy_points_avg_l4",
    "fantasy_points_avg_l8",
    "targets_avg_l4",
    "receptions_avg_l4",
    "receiving_yards_avg_l4",
    "rushing_attempts_avg_l4",
    "rushing_yards_avg_l4",
]

V2_FEATURES = V1_FEATURES + [
    "offense_pct_avg_l4",
    "team_pass_attempts_avg_l4",
]

TARGET = "target_fantasy_points"

KEYS = [
    "season",
    "week",
    "game_id",
    "player_id",
]


def main():

    con = duckdb.connect(
        str(DATABASE),
        read_only=True,
    )

    # V2 includes the V1 features and additional usage features.
    df = con.execute("""
        SELECT *
        FROM features.model_training_v2_clean
        WHERE season = 2025
    """).df()

    con.close()

    df = df.dropna(
        subset=V2_FEATURES + [TARGET]
    ).copy()

    if df.empty:
        raise ValueError("No eligible 2025 test rows found.")

    if df.duplicated(KEYS).any():
        raise ValueError("Duplicate player-game keys found.")

    print(f"Common test rows: {len(df):,}")

    models = {
        "V1": joblib.load(
            MODEL_DIR / "fantasee_forge_xgb.joblib"
        ),
        "V2": joblib.load(
            MODEL_DIR / "fantasee_forge_xgb_v2.joblib"
        ),
    }

    predictions = {
        "Baseline": df["fantasy_points_avg_l4"].to_numpy(),
        "V1": models["V1"].predict(df[V1_FEATURES]),
        "V2": models["V2"].predict(df[V2_FEATURES]),
    }

    results = []

    for name, pred in predictions.items():

        mae = mean_absolute_error(df[TARGET], pred)

        rmse = mean_squared_error(
            df[TARGET], pred
        ) ** 0.5

        spearman = spearmanr(
            df[TARGET], pred
        ).statistic

        results.append({
            "model": name,
            "rows": len(df),
            "mae": mae,
            "rmse": rmse,
            "spearman": spearman,
        })

    summary = pd.DataFrame(results)

    print("\nFair model comparison")
    print("------------------------------")
    print(
        summary.to_string(
            index=False,
            float_format=lambda x: f"{x:.3f}",
        )
    )

    print("\nPerformance by position")
    print("------------------------------")

    for position in sorted(df["position"].unique()):

        mask = df["position"] == position

        print(f"\n{position} — {mask.sum():,} players/games")

        for name, pred in predictions.items():

            mae = mean_absolute_error(
                df.loc[mask, TARGET],
                pred[mask.to_numpy()],
            )

            print(f"{name}: MAE={mae:.3f}")


if __name__ == "__main__":
    main()