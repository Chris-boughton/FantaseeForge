from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_project_directories_exist():
    required = [
        ROOT / "data",
        ROOT / "python",
        ROOT / "database",
        ROOT / "website",
    ]
    for path in required:
        assert path.exists()