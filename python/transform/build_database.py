from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]

DATABASE = ROOT / "database" / "fantasee_forge.duckdb"
SQL_DIR = ROOT / "sql"

con = duckdb.connect(str(DATABASE))

def run_sql_file(path):
    """Read and execute a SQL file."""
    
    print(f"Running SQL: {path}")
    
    sql = path.read_text(encoding="utf-8")
    
    con.execute(sql)

print("Creating schemas...")

con.execute("""
    CREATE SCHEMA IF NOT EXISTS raw;
    CREATE SCHEMA IF NOT EXISTS staging;
    CREATE SCHEMA IF NOT EXISTS features;
    CREATE SCHEMA IF NOT EXISTS marts;
""")

for sql_file in sorted((SQL_DIR / "staging").glob("*.sql")):
    run_sql_file(sql_file)

for sql_file in sorted((SQL_DIR / "features").glob("*.sql")):
    run_sql_file(sql_file)

for sql_file in sorted((SQL_DIR / "marts").glob("*.sql")):
    run_sql_file(sql_file)

con.close()

print("Database build complete.")