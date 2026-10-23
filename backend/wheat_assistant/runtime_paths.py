"""Current application paths, with read/write access to existing local data."""
import os
from pathlib import Path

from platformdirs import user_data_dir


def setting(name, default=None):
    return os.getenv("WHEAT_ASSISTANT_" + name) or os.getenv("MAIZI_" + name) or default


def data_directory(explicit=None):
    configured = explicit or setting("DATA_DIR")
    if configured:
        return Path(configured).resolve()
    current = Path(user_data_dir("wheat_assistant", appauthor=False)).resolve()
    legacy = Path(user_data_dir("MaiZi", appauthor=False)).resolve()
    if not any((current / name).is_file() for name in ("wheat_assistant.sqlite", "maizi.sqlite")):
        if (legacy / "maizi.sqlite").is_file():
            return legacy
    return current


def database_path(root):
    current, legacy = Path(root) / "wheat_assistant.sqlite", Path(root) / "maizi.sqlite"
    if current.is_file() and legacy.is_file():
        raise ValueError("Both current and legacy databases exist. Preserve both and choose a separate data directory.")
    return legacy if legacy.is_file() else current
