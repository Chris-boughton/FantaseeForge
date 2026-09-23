from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
INPUT = (
    ROOT
    / "data"
    / "exports"
    / "predictions.parquet"
)
OUTPUT_DIR = (
    ROOT
    / "website"
    / "data"
)
OUTPUT = OUTPUT_DIR / "predictions.json"

def main():
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )
    df = pd.read_parquet(INPUT)
    columns = [
        "rank",
        "player_display_name",
        "position",
        "team",
        "opponent_team",
        "projection",
        "floor",
        "ceiling",
    ]
    available = [
        c for c in columns
        if c in df.columns
    ]
    df = df[available].copy()
    records = df.to_dict(
        orient="records"
    )
    with open(
        OUTPUT,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            records,
            file,
            indent=2,
            default=str,
        )
    print(
        f"Wrote {len(records):,}players "
        f"to {OUTPUT}"
    )
if __name__ == "__main__":
    main()