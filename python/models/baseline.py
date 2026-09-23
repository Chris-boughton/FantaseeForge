from pathlib import Path

import duckdb

from sklearn.metrics import mean_absolute_error, mean_squared_error

ROOT = Path(__file__).resolve().parents[2]

DATABASE = ROOT / "database" / "fantasee_forge.duckdb"

con = duckdb.connect(str(DATABASE))

df = con.execute("""
    SELECT
        fantasy_points_avg_l4,
        target_fantasy_points
    FROM features.model_training_clean

    WHERE season = 2025

      AND fantasy_points_avg_l4 IS NOT NULL

      AND target_fantasy_points IS NOT NULL
""").df()


con.close()

predictions = df["fantasy_points_avg_l4"]

actual = df["target_fantasy_points"]

mae = mean_absolute_error(
    actual,
    predictions,
)

rmse = mean_squared_error(
    actual,
    predictions,
) ** 0.5

print("Baseline performance")
print("------------------------------")

print(f"Rows: {len(df):,}")

print(f"MAE:  {mae:.3f}")

print(f"RMSE: {rmse:.3f}")