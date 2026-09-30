"""Per-user data locations (no third-party dependency)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "360Smart"


def data_dir() -> Path:
    override = os.environ.get("SMART360_HOME")
    if override:
        p = Path(override)
    elif sys.platform == "win32":
        p = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / APP_DIR_NAME
    elif sys.platform == "darwin":
        p = Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    else:
        p = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_DIR_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p


def config_path() -> Path:
    return data_dir() / "config.json"


def cache_path() -> Path:
    return data_dir() / "question_cache.db"


def history_path() -> Path:
    return data_dir() / "history.db"


def log_dir() -> Path:
    p = data_dir() / "logs"
    p.mkdir(exist_ok=True)
    return p


def debug_dir() -> Path:
    p = data_dir() / "debug"
    p.mkdir(exist_ok=True)
    return p
