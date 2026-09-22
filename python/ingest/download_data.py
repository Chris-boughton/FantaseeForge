from pathlib import Path

import nflreadpy as nfl
from nflreadpy.config import update_config

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
CACHE_DIR = ROOT / ".nflreadpy-cache"
update_config(
    cache_mode="filesystem",
    cache_dir=CACHE_DIR,
    verbose=True,
)

def save_dataset(data, directory, filename):
    directory.mkdir(parents=True, exist_ok=True)

    path = directory / filename

    data.write_parquet(path)

    print(f"Saved {path}")
    print(f"Rows: {data.height:,}")
    print(f"Columns: {data.width}")

def download_seasonal_dataset(loader, directory_name, filename_prefix, seasons):
    for season in seasons:
        print(f"\nDownloading {filename_prefix} {season}...")

        data = loader(seasons=season)

        save_dataset(
            data,
            RAW_DIR / directory_name,
            f"{filename_prefix}_{season}.parquet",
        )

def main():
    seasons = list(range(2019, nfl.get_current_season() + 1))
    
    print(f"Downloading seasons: {seasons}")

    download_seasonal_dataset(
        nfl.load_player_stats,
        "player_stats",
        "player_stats",
        seasons,
    )

    download_seasonal_dataset(
        nfl.load_rosters,
        "rosters",
        "rosters",
        seasons,
    )
    
    download_seasonal_dataset(
        nfl.load_snap_counts,
        "snap_counts",
        "snap_counts",
        seasons,
    )
    
    download_seasonal_dataset(
        nfl.load_injuries,
        "injuries",
        "injuries",
        seasons,
    )

    players = nfl.load_players()
    
    save_dataset(
        players,
        RAW_DIR / "players",
        "players.parquet",
    )
    
    schedules = nfl.load_schedules(seasons=True) 
    
    save_dataset(
        schedules,
        RAW_DIR / "schedules",
        "schedules.parquet",
    )
    
if __name__ == "__main__":
    main()