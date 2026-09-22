from pathlib import Path

import duckdb
import joblib
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error
from xgboost import XGBRegressor

ROOT = Path(__file__).resolve().parents[2]

DATABASE = (
    ROOT
    / "database"
    / "fantasee_forge.duckdb"
)

MODEL_DIR = (
    ROOT
    / "data"
    / "processed"
)

MODEL_PATH = (
    MODEL_DIR
    / "fantasee_xgb.joblib"
)

FEATURES = [
    "targets_l2",
    "targets_l4",
    "targets_l8",
    "target_share",
    "snap_share",
    "receptions",
    "receiving_yards_l4",
    "rushing_attempts",
    "rushing_yards_l4",
    "fantasy_points_l2",
    "fantasy_points_l4",
    "fantasy_points_l8",
    "fpts_allowed_l4",
    "targets_allowed_l4",
    "receiving_yards_allowed_l4",
]


def main():

    MODEL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    con = duckdb.connect(str(DATABASE))

    df = con.execute("""
        SELECT *
        FROM features.training_data
    """).fetchdf()

    con.close()

    df = df.dropna(
        subset=FEATURES + ["target_fantasy_points"]
    )

    latest_season = df["season"].max()

    train = df[
        df["season"] < latest_season
    ].copy()

    test = df[
        df["season"] == latest_season
    ].copy()

    X_train = train[FEATURES]
    y_train = train["target_fantasy_points"]
    X_test = test[FEATURES]
    y_test = test["target_fantasy_points"]

    print(
        f"Training rows: {len(train):,}"
    )
    print(
        f"Testing rows: {len(test):,}"
    )
    print(
        f"Training seasons: "
        f"{train['season'].min()}-"
        f"{train['season'].max()}"
    )
    print(
        f"Testing season: "
        f"{latest_season}"
    )

    model = XGBRegressor(
        n_estimators=500,
        max_depth=4,
        learning_rate=0.03,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="reg:squarederror",
        random_state=42,
    )

    print("\nTraining XGBoost model...")
    model.fit(
        X_train,
        y_train,
    )

    predictions = model.predict(
        X_test
    )

    mae = mean_absolute_error(
        y_test,
        predictions,
    )

    rmse = np.sqrt(
        mean_squared_error(
            y_test,
            predictions,
        )
    )

    errors = (
        y_test.to_numpy()
        - predictions
    )

    error_sd = errors.std()

    print(
        f"\nXGBoost MAE: {mae:.3f}"
    )
    print(
        f"XGBoost RMSE: {rmse:.3f}"
    )
    print(
        f"Prediction error SD: {error_sd:.3f}"
    )

    model_bundle = {
        "model": model,
        "error_sd": error_sd,
        "features": FEATURES,
    }

    joblib.dump(
        model_bundle,
        MODEL_PATH,
    )

    print(
        "\nModel saved to:"
    )

    print(
        MODEL_PATH
    )


if __name__ == "__main__":
    main()