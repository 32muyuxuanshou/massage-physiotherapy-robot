"""PyCharm/local entry point for the first-stage demo server."""

from __future__ import annotations

import os
from pathlib import Path

import uvicorn


BACKEND_DIR = Path(__file__).resolve().parent


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def main() -> None:
    # Keep relative paths in backend/.env and SQLite stable regardless of how
    # PyCharm was launched.
    os.chdir(BACKEND_DIR)

    host = os.environ.get("PHYSIOTHERAPY_HOST", "127.0.0.1")
    port = int(os.environ.get("PHYSIOTHERAPY_PORT", "8000"))
    reload_enabled = _env_bool("PHYSIOTHERAPY_RELOAD")

    print(f"Starting first-stage server at http://{host}:{port}")
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload_enabled,
    )


if __name__ == "__main__":
    main()
