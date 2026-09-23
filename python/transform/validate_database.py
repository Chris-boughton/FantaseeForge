from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / "database" / "fantasee_forge.duckdb"


con = duckdb.connect(str(DATABASE))


def check_table(table_name):
    result = con.execute(
        f"SELECT COUNT(*) FROM {table_name}"
    ).fetchone()

    count = result[0]

    print(f"{table_name}: {count:,} rows")

    if count == 0:
        raise ValueError(f"{table_name} is empty!")


tables = [
    "staging.player_game",
]


for table in tables:
    check_table(table)


print("Database validation passed.")

con.close()