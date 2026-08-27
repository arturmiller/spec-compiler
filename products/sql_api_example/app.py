"""FastAPI product described by the sibling contracts in ``specs/``."""

from __future__ import annotations

import sqlite3
from contextlib import closing
import os
from os import PathLike
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field


class Article(BaseModel):
    """HTTP representation chosen by this reference implementation."""

    model_config = ConfigDict(extra="forbid")

    description: Annotated[str, Field(min_length=1)]
    price: Annotated[float, Field(gt=0, lt=1_000_000)]


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

    @app.get("/articles/{id}", response_model=Article)
    def get_article(id: int) -> Article:
        with closing(sqlite3.connect(database)) as connection:
            connection.row_factory = sqlite3.Row
            article = connection.execute(
                "SELECT description, price FROM articles WHERE id = ?", (id,)
            ).fetchone()

        if article is None:
            raise HTTPException(status_code=404, detail="Article not found")

        return Article(description=article["description"], price=article["price"])

    return app


def main() -> None:
    """Run the example through values declared by its product manifest."""
    import uvicorn

    database_path = os.environ["DATABASE_PATH"]
    host = os.environ["HOST"]
    port = int(os.environ["PORT"])
    uvicorn.run(create_app(database_path), host=host, port=port)


if __name__ == "__main__":
    main()
