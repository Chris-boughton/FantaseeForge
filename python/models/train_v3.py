from pathlib import Path

import duckdb
import joblib
import pandas as pd

from xgboost import XGBRegressor

from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
)

from scipy.stats import spearmanr


ROOT = Path(__file__).resolve().parents[2]

DATABASE = ROOT / "database" / "fantasee_forge.duckdb"
MODEL_PATH = ROOT / "models" / "fantasee_forge_xgb_v3.joblib"


# Original V1 features
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

# V2 opportunity features
V2_FEATURES = [
    "offense_pct_avg_l4",
    "team_pass_attempts_avg_l4",
]

# New V3 defensive matchup features
V3_FEATURES = [
    "defense_fpts_allowed_l4",
    "defense_targets_allowed_l4",
    "defense_receiving_yards_allowed_l4",
]

FEATURES = V1_FEATURES + V2_FEATURES + V3_FEATURES

TARGET = "target_fantasy_points"


def main():

    con = duckdb.connect(
        str(DATABASE),
        read_only=True,
    )

    df = con.execute("""
        SELECT *
        FROM features.model_training_v3
        WHERE season <= 2025
    """).df()

    con.close()

    print(f"Historical rows loaded: {len(df):,}")

    df = df.dropna(
        subset=V1_FEATURES + V2_FEATURES + [TARGET]
    ).copy()

    print(f"Rows after filtering: {len(df):,}")

    train = df[df["season"] <= 2024].copy()
    test = df[df["season"] == 2025].copy()

    print("\nDataset split")
    print("------------------------------")
    print(f"Training rows: {len(train):,}")
    print(f"Testing rows:  {len(test):,}")

    X_train = train[FEATURES]
    y_train = train[TARGET]

    X_test = test[FEATURES]
    y_test = test[TARGET]

    model = XGBRegressor(
        n_estimators=500,
        max_depth=4,
        learning_rate=0.03,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="reg:squarederror",
        random_state=42,
    )

    print("\nTraining XGBoost V3 model...")

    model.fit(X_train, y_train)

    predictions = model.predict(X_test)

    mae = mean_absolute_error(y_test, predictions)

    rmse = mean_squared_error(
        y_test,
        predictions,
    ) ** 0.5

    spearman = spearmanr(
        y_test,
        predictions,
    ).statistic

    print("\nModel performance")
    print("------------------------------")
    print(f"MAE:      {mae:.3f}")
    print(f"RMSE:     {rmse:.3f}")
    print(f"Spearman: {spearman:.3f}")

    print("\nPerformance by position")
    print("------------------------------")

    for position in ["QB", "RB", "TE", "WR"]:

        mask = test["position"] == position

        position_mae = mean_absolute_error(
            y_test[mask],
            predictions[mask.to_numpy()],
        )

        position_rmse = mean_squared_error(
            y_test[mask],
            predictions[mask.to_numpy()],
        ) ** 0.5

        print(
            f"{position}: "
            f"rows={mask.sum():,}, "
            f"MAE={position_mae:.3f}, "
            f"RMSE={position_rmse:.3f}"
        )

    importance = pd.DataFrame({
        "feature": FEATURES,
        "importance": model.feature_importances_,
    }).sort_values(
        "importance",
        ascending=False,
    )

    print("\nFeature importance")
    print("------------------------------")
    print(
        importance.to_string(
            index=False,
            float_format=lambda x: f"{x:.4f}",
        )
    )

    MODEL_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    joblib.dump(model, MODEL_PATH)

    print(f"\nModel saved to:\n{MODEL_PATH}")


if __name__ == "__main__":
    main()