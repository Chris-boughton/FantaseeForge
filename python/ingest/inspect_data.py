from pathlib import Path
import polars as pl

ROOT = Path(__file__).resolve().parents[2]

files = [
    ROOT / "data/raw/player_stats/player_stats_2026.parquet",
    ROOT / "data/raw/snap_counts/snap_counts_2026.parquet",
]

for path in files:
    print("\n" + "=" * 80)
    print(path)
    print("=" * 80)
    df = pl.read_parquet(path)
    print(f"Rows: {df.height:,}")
    print(f"Columns: {df.width}")
    print("\nColumns:")
    print(df.columns)
    print("\nFirst five rows:")
    print(df.head())