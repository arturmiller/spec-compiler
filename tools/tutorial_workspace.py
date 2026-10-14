"""Create a fresh practice product without changing versioned reference products."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = {"sql-api": "sql_api_example", "kfw": "kfw_458_eligibility", "cloud": "cloud_access_compliance"}


def create(example: str, root: Path = ROOT) -> Path:
    source = root / "products" / EXAMPLES[example]
    destination = root / "products" / ("tutorial_" + EXAMPLES[example])
    if destination.exists():
        raise ValueError(f"Practice product already exists: {destination}. Nothing was overwritten.")
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns(
        ".venv", "__pycache__", ".pytest_cache", ".cache", "*.pyc", "*.sqlite3", "generated", "tests", "README.md",
    ))
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("example", choices=EXAMPLES)
    args = parser.parse_args()
    try:
        print(create(args.example).relative_to(ROOT).as_posix())
    except ValueError as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
