from pathlib import Path

import duckdb
import joblib
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

DATABASE = ROOT / "database" / "fantasee_forge.duckdb"
MODEL_PATH = ROOT / "models" / "fantasee_forge_xgb_v2.joblib"

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
]

model = joblib.load(MODEL_PATH)

importance = model.feature_importances_

importance_df = pd.DataFrame({
    "feature": FEATURES,
    "importance": importance,
})

importance_df = importance_df.sort_values(
    "importance",
    ascending=False
)

print()
print("Feature importance")
print("------------------------------")

for _, row in importance_df.iterrows():
    print(
        f"{row['feature']:<30} "
        f"{row['importance']:.4f}"
    )