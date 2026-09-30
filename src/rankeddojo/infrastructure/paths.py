from __future__ import annotations

import os
import sys
from pathlib import Path


APP_DIR_NAME = "rankeddojo"

# Pre-migration data directory name (see infrastructure/data_dir_migration.py).
# Never reused for anything new; kept only so the legacy directory can still be
# located and migrated on an existing install.
LEGACY_APP_DIR_NAME = "exam-trainer"


def _config_root_for(app_dir_name: str) -> Path:
    if sys.platform == "win32":
        base_path = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base_path / app_dir_name

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / app_dir_name

    base_path = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base_path / app_dir_name


def user_config_dir() -> Path:
    return _config_root_for(APP_DIR_NAME)


def legacy_user_config_dir() -> Path:
    """The pre-migration data directory (see infrastructure/data_dir_migration.py)."""
    return _config_root_for(LEGACY_APP_DIR_NAME)


def app_config_file_path() -> Path:
    return user_config_dir() / "config.json"


def app_database_file_path() -> Path:
    return user_config_dir() / "trainer.sqlite3"


def managed_packs_dir() -> Path:
    return user_config_dir() / "packs"


def user_themes_dir() -> Path:
    return user_config_dir() / "themes"


def user_plugins_dir() -> Path:
    return user_config_dir() / "plugins"


def bundled_sample_packs_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "examples" / "packs"
    return Path(__file__).resolve().parents[3] / "examples" / "packs"
