from pathlib import Path

import duckdb
import joblib

from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
)
from scipy.stats import spearmanr
from xgboost import XGBRegressor

ROOT = Path(__file__).resolve().parents[2]

DATABASE = ROOT / "database" / "fantasee_forge.duckdb"
MODEL_DIR = ROOT / "models"

MODEL_DIR.mkdir(parents=True, exist_ok=True)

con = duckdb.connect(str(DATABASE))

query = """
SELECT *
FROM features.model_training_clean
WHERE season <= 2025
"""

df = con.execute(query).df()

con.close()

print(f"Total historical rows loaded: {len(df):,}")

FEATURES = [
    "fantasy_points_avg_l2",
    "fantasy_points_avg_l4",
    "fantasy_points_avg_l8",
    "targets_avg_l4",
    "receptions_avg_l4",
    "receiving_yards_avg_l4",
    "rushing_attempts_avg_l4",
    "rushing_yards_avg_l4",
]

TARGET = "target_fantasy_points"

df = df.dropna(
    subset=FEATURES + [TARGET]
)

print(f"Rows after removing missing values: {len(df):,}")

train = df[df["season"] <= 2024].copy()

test = df[df["season"] == 2025].copy()

print()
print("Dataset split")
print("------------------------------")
print(f"Training rows: {len(train):,}")
print(f"Testing rows:  {len(test):,}")
print(f"Training seasons: {train['season'].min()}-{train['season'].max()}")
print(f"Testing season:   {test['season'].min()}")

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

print()
print("Training XGBoost model...")

model.fit(
    X_train,
    y_train,
)

predictions = model.predict(X_test)

test_results = test[
    [
        "player_id",
        "player_display_name",
        "position",
        "season",
        "week",
        "target_fantasy_points",
    ]
].copy()

test_results["prediction"] = predictions

mae = mean_absolute_error(
    y_test,
    predictions,
)
rmse = mean_squared_error(
    y_test,
    predictions,
) ** 0.5

spearman = spearmanr(
    y_test,
    predictions,
).statistic

print(f"Spearman rank correlation: {spearman:.3f}")

print()
print("Performance by position")
print("------------------------------")

for position, group in test_results.groupby("position"):

    position_mae = mean_absolute_error(
        group["target_fantasy_points"],
        group["prediction"],
    )

    position_rmse = mean_squared_error(
        group["target_fantasy_points"],
        group["prediction"],
    ) ** 0.5

    print(
        f"{position}: "
        f"rows={len(group):,}, "
        f"MAE={position_mae:.3f}, "
        f"RMSE={position_rmse:.3f}"
    )

print()
print("Model performance")
print("------------------------------")
print(f"MAE:  {mae:.3f}")
print(f"RMSE: {rmse:.3f}")

model_path = MODEL_DIR / "fantasee_forge_xgb.joblib"

joblib.dump(
    model,
    model_path,
)
print()
print(f"Model saved to:")
print(model_path)