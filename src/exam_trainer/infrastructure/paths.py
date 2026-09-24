from __future__ import annotations

import os
import sys
from pathlib import Path


APP_DIR_NAME = "exam-trainer"


def user_config_dir() -> Path:
    if sys.platform == "win32":
        base_path = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base_path / APP_DIR_NAME

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME

    base_path = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base_path / APP_DIR_NAME


def app_config_file_path() -> Path:
    return user_config_dir() / "config.json"


def app_database_file_path() -> Path:
    return user_config_dir() / "trainer.sqlite3"


def managed_packs_dir() -> Path:
    return user_config_dir() / "packs"


def bundled_sample_packs_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "examples" / "packs"
    return Path(__file__).resolve().parents[3] / "examples" / "packs"

