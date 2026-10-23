"""The renamed application must keep existing local work and locking intact."""
import json
import sqlite3
from contextlib import closing

import pytest

from wheat_assistant import runtime_paths
from wheat_assistant.runtime_lock import data_directory_lock
from wheat_assistant.store import Store


@pytest.fixture()
def paths(tmp_path, monkeypatch):
    for name in ("WHEAT_ASSISTANT_DATA_DIR", "MAIZI_DATA_DIR"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(runtime_paths, "user_data_dir", lambda name, **kwargs: str(tmp_path / name))
    return tmp_path / "wheat_assistant", tmp_path / "MaiZi"


def test_existing_default_data_is_not_hidden_by_an_empty_new_directory(paths):
    current, legacy = paths
    current.mkdir()
    legacy.mkdir()
    (legacy / "maizi.sqlite").touch()
    assert runtime_paths.data_directory() == legacy


def test_current_database_and_explicit_configuration_take_precedence(paths, monkeypatch):
    current, legacy = paths
    for folder, name in ((current, "wheat_assistant.sqlite"), (legacy, "maizi.sqlite")):
        folder.mkdir()
        (folder / name).touch()
    assert runtime_paths.data_directory() == current
    monkeypatch.setenv("MAIZI_DATA_DIR", str(legacy))
    assert runtime_paths.data_directory() == legacy
    monkeypatch.setenv("WHEAT_ASSISTANT_DATA_DIR", str(current))
    assert runtime_paths.data_directory() == current
    assert runtime_paths.data_directory(legacy) == legacy


def test_legacy_database_round_trip_and_verified_backup(tmp_path):
    legacy = tmp_path / "maizi.sqlite"
    payload = {"id": "synthetic-flow", "name": "Saved synthetic flow", "created_at": "2026-10-21"}
    with closing(sqlite3.connect(legacy)) as connection, connection:
        connection.execute("CREATE TABLE entities (id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload JSON NOT NULL, revision INTEGER NOT NULL DEFAULT 1, created TEXT NOT NULL)")
        connection.execute("INSERT INTO entities VALUES (?, ?, ?, ?, ?)", (payload["id"], "flow", json.dumps(payload), 1, payload["created_at"]))
    with Store(tmp_path) as store:
        assert store.get("flow", payload["id"]) == payload
        store.put("flow", payload["id"], {**payload, "name": "Reviewed saved flow"})
    with Store(tmp_path) as reopened:
        assert reopened.get("flow", payload["id"])["name"] == "Reviewed saved flow"
    assert not (tmp_path / "wheat_assistant.sqlite").exists()
    backup = next((tmp_path / "backups").glob("hardening-v2-*/maizi.sqlite"))
    with closing(sqlite3.connect(backup)) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert json.loads(connection.execute("SELECT payload FROM entities").fetchone()[0]) == payload


def test_two_database_names_cannot_silently_select_different_saved_work(tmp_path):
    for name in ("wheat_assistant.sqlite", "maizi.sqlite"):
        (tmp_path / name).touch()
    with pytest.raises(ValueError, match="Both current and legacy databases exist"):
        Store(tmp_path)


def test_legacy_instance_lock_still_rejects_a_second_launcher(tmp_path):
    legacy = tmp_path / ".maizi-instance.lock"
    legacy.touch()
    with data_directory_lock(tmp_path):
        with pytest.raises(ValueError, match="already running"):
            with data_directory_lock(tmp_path):
                pytest.fail("A second instance acquired the legacy data lock")
    assert not (tmp_path / ".wheat_assistant-instance.lock").exists()
