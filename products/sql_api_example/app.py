"""FastAPI product described by the sibling contracts in ``specs/``."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from os import PathLike
from pathlib import Path

from fastapi import FastAPI, HTTPException


def create_app(db_path: str | PathLike[str]) -> FastAPI:
    """Create the API and initialise its SQLite schema."""
    database = Path(db_path)

    with closing(sqlite3.connect(database)) as connection:
        with connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    description TEXT NOT NULL,
                    price DECIMAL NOT NULL
                )
                """
            )

    app = FastAPI()

    @app.get("/articles/{id}")
    def get_article(id: int) -> dict[str, str | float]:
        with closing(sqlite3.connect(database)) as connection:
            connection.row_factory = sqlite3.Row
            article = connection.execute(
                "SELECT description, price FROM articles WHERE id = ?", (id,)
            ).fetchone()

        if article is None:
            raise HTTPException(status_code=404, detail="Article not found")

        return {
            "description": article["description"],
            "price": article["price"],
        }

    return app
