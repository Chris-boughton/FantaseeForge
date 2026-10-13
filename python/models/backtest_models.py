from pathlib import Path

import duckdb
import pandas as pd

from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from scipy.stats import spearmanr


ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / "database" / "fantasee_forge.duckdb"

V1 = [
    "fantasy_points_avg_l2",
    "fantasy_points_avg_l4",
    "fantasy_points_avg_l8",
    "targets_avg_l4",
    "receptions_avg_l4",
    "receiving_yards_avg_l4",
    "rushing_attempts_avg_l4",
    "rushing_yards_avg_l4",
]

V2 = V1 + [
    "offense_pct_avg_l4",
    "team_pass_attempts_avg_l4",
]

V3 = V2 + [
    "defense_fpts_allowed_l4",
    "defense_targets_allowed_l4",
    "defense_receiving_yards_allowed_l4",
]

MODELS = {
    "Baseline": None,
    "V1": V1,
    "V2": V2,
    "V3": V3,
}

TARGET = "target_fantasy_points"

KEYS = [
    "season",
    "week",
    "game_id",
    "player_id",
]


def main():

    con = duckdb.connect(str(DATABASE), read_only=True)

    df = con.execute("""
        SELECT *
        FROM features.model_training_v3
        WHERE season BETWEEN 2019 AND 2025
    """).df()

    con.close()

    # Ensure all models use the same observations.
    df = df.dropna(
        subset=V2 + [TARGET]
    ).copy()

    if df.duplicated(KEYS).any():
        raise ValueError("Duplicate player-game keys detected.")

    results = []

    for test_season in [2022, 2023, 2024, 2025]:

        train = df[df["season"] < test_season].copy()
        test = df[df["season"] == test_season].copy()

        if train.empty or test.empty:
            raise ValueError(
                f"Missing data for test season {test_season}"
            )

        print(f"\nTesting season: {test_season}")
        print(f"Training rows: {len(train):,}")
        print(f"Testing rows:  {len(test):,}")

        for name, features in MODELS.items():

            if name == "Baseline":
                predictions = (
                    test["fantasy_points_avg_l4"].to_numpy()
                )

            else:
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

                model.fit(
                    train[features],
                    train[TARGET],
                )

                predictions = model.predict(
                    test[features]
                )

            mae = mean_absolute_error(
                test[TARGET],
                predictions,
            )

            rmse = mean_squared_error(
                test[TARGET],
                predictions,
            ) ** 0.5

            spearman = spearmanr(
                test[TARGET],
                predictions,
            ).statistic

            results.append({
                "season": test_season,
                "model": name,
                "rows": len(test),
                "mae": mae,
                "rmse": rmse,
                "spearman": spearman,
            })

            print(
                f"{name}: "
                f"MAE={mae:.3f}, "
                f"RMSE={rmse:.3f}, "
                f"Spearman={spearman:.3f}"
            )

    results_df = pd.DataFrame(results)

    print("\nOverall average performance")
    print("------------------------------")

    summary = (
        results_df
        .groupby("model")[["mae", "rmse", "spearman"]]
        .mean()
        .sort_values("mae")
    )

    print(summary.round(3).to_string())

    output = ROOT / "data" / "exports"
    output.mkdir(parents=True, exist_ok=True)

    results_df.to_csv(
        output / "model_backtest_results.csv",
        index=False,
    )

    print("\nSaved model_backtest_results.csv")


if __name__ == "__main__":
    main()