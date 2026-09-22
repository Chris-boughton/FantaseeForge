from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parents[1]

DATABASE = ROOT / "database" / "fantasee_forge.duckdb"

def test_features_exist():
    con = duckdb.connect(
        str(DATABASE),
        read_only=True,
    )
    count = con.execute("""
        SELECT COUNT(*)
        FROM features.training_data
    """).fetchone()[0]
    con.close()
    
    assert count > 0