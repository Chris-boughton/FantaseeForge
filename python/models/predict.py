from pathlib import Path

import duckdb
import joblib

ROOT = Path(__file__).resolve().parents[2]

DATABASE = (
    ROOT
    / "database"
    / "fantasee_forge.duckdb"
)

MODEL_PATH = (
    ROOT
    / "data"
    / "processed"
    / "fantasee_xgb.joblib"
)


def main():

    model_bundle = joblib.load(
        MODEL_PATH
    )

    model = model_bundle["model"]
    error_sd = model_bundle["error_sd"]
    features = model_bundle["features"]

    print(
        f"Historical prediction error SD: "
        f"{error_sd:.3f}"
    )

    con = duckdb.connect(
        str(DATABASE)
    )

    latest = con.execute("""
        SELECT
            season,
            week
        FROM features.player_rolling
        GROUP BY season, week
        ORDER BY season DESC, week DESC
        LIMIT 1
    """).fetchdf()

    season = int(
        latest["season"].iloc[0]
    )

    week = int(
        latest["week"].iloc[0]
    )

    print(
        f"Latest available data: "
        f"{season} Week {week}"
    )

    predictions = con.execute("""
        SELECT *
        FROM features.player_rolling
        WHERE season = ?
          AND week = ?
    """, [season, week]).fetchdf()

    defense = con.execute("""
        SELECT *
        FROM features.defense_position_rolling
        WHERE season = ?
          AND week = ?
    """, [season, week]).fetchdf()

    con.close()

    predictions = predictions.merge(
        defense[
            [
                "season",
                "week",
                "defense_team",
                "position",
                "fpts_allowed_l4",
                "targets_allowed_l4",
                "receiving_yards_allowed_l4",
            ]
        ],
        left_on=[
            "season",
            "week",
            "opponent_team",
            "position",
        ],
        right_on=[
            "season",
            "week",
            "defense_team",
            "position",
        ],
        how="left",
    )

    predictions = predictions.dropna(
        subset=features
    ).copy()

    print(
        f"Players with complete features: "
        f"{len(predictions):,}"
    )

    predictions["projection"] = model.predict(
        predictions[features]
    )

    # Fantasy points cannot be negative
    predictions["projection"] = (
        predictions["projection"]
        .clip(lower=0)
    )

    # ==================================================
    # 9. CALCULATE FLOOR
    # ==================================================

    predictions["floor"] = (
        predictions["projection"]
        - error_sd
    ).clip(lower=0)

    # ==================================================
    # 10. CALCULATE CEILING
    # ==================================================

    predictions["ceiling"] = (
        predictions["projection"]
        + error_sd
    )

    predictions["rank"] = (
        predictions["projection"]
        .rank(
            ascending=False,
            method="min",
        )
    )

    predictions = predictions.sort_values(
        "projection",
        ascending=False,
    )

    output = (
        ROOT
        / "data"
        / "exports"
    )

    output.mkdir(
        parents=True,
        exist_ok=True,
    )

    predictions.to_parquet(
        output / "predictions.parquet",
        index=False,
    )

    predictions.to_json(
        output / "predictions.json",
        orient="records",
    )

    print(
        f"\nGenerated "
        f"{len(predictions):,} predictions."
    )
    print(
        f"Using ±{error_sd:.3f} "
        f"historical prediction error SD."
    )
    print(
        "\nPrediction columns:"
    )
    print(
        "projection = expected fantasy points"
    )
    print(
        "floor      = projection - 1 SD"
    )
    print(
        "ceiling    = projection + 1 SD"
    )


if __name__ == "__main__":
    main()