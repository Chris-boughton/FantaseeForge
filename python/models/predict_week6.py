
from pathlib import Path

import duckdb
import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

DATABASE = ROOT / "database" / "fantasee_forge.duckdb"
MODEL_PATH = ROOT / "models" / "fantasee_forge_xgb_v3_production.joblib"

EXPORT_DIR = ROOT / "data" / "exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

# Load the production model and its exact feature list.
bundle = joblib.load(MODEL_PATH)

model = bundle["model"]
features = bundle["features"]

print(
    "Model trained through:",
    bundle["trained_through_season"],
    "Week",
    bundle["trained_through_week"],
)

# Load upcoming player-game features.
con = duckdb.connect(str(DATABASE), read_only=True)

df = con.execute("""
    SELECT *
    FROM features.upcoming_player_features
    WHERE season = 2026
      AND week = 6
""").df()

con.close()

print(f"Upcoming players loaded: {len(df):,}")

if df.empty:
    raise ValueError("No upcoming players found.")

if df["player_id"].duplicated().any():
    raise ValueError("Duplicate player IDs detected.")

missing_columns = [
    col for col in features
    if col not in df.columns
]

if missing_columns:
    raise ValueError(
        f"Missing feature columns: {missing_columns}"
    )

# Match the training data's first-ten-feature completeness rule.
required_features = features[:10]

eligible = df.dropna(
    subset=required_features
).copy()

excluded = df.loc[
    ~df.index.isin(eligible.index)
].copy()

print(f"Players eligible for prediction: {len(eligible):,}")
print(f"Players excluded for missing history: {len(excluded):,}")

if eligible.empty:
    raise ValueError("No players have sufficient model features.")

# V3 supports missing defensive values via XGBoost.
X = eligible[features]

eligible["projection"] = model.predict(X)

# Fantasy points can theoretically be negative, but the
# public-facing projection is floored at zero.
eligible["projection"] = np.maximum(
    eligible["projection"],
    0,
)

eligible["projection"] = eligible["projection"].round(2)

eligible = eligible.sort_values(
    "projection",
    ascending=False,
).reset_index(drop=True)

eligible.insert(
    0,
    "rank",
    np.arange(1, len(eligible) + 1),
)

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

predictions = eligible[output_columns]

parquet_path = EXPORT_DIR / "predictions_week6.parquet"
json_path = EXPORT_DIR / "predictions_week6.json"

predictions.to_parquet(
    parquet_path,
    index=False,
)

predictions.to_json(
    json_path,
    orient="records",
    indent=2,
)

print("\nTop 20 Week 6 projections:")
print(
    predictions.head(20).to_string(index=False)
)

print(f"\nSaved: {parquet_path}")
print(f"Saved: {json_path}")

if not excluded.empty:
    excluded_path = EXPORT_DIR / "predictions_week6_excluded.csv"

    excluded[
        [
            "player_id",
            "player_display_name",
            "position",
            "team",
        ]
    ].to_csv(
        excluded_path,
        index=False,
    )

    print(f"Excluded player report: {excluded_path}")
