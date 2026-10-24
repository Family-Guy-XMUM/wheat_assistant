"""A failing test stays failed while its published receipt excludes private data."""
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from wheat_assistant.runtime_environment import child_environment

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = "SYNTHETIC_PRIVATE_DETAIL_8325"


@pytest.mark.parametrize("body,phase", [
    ("import pytest\n@pytest.mark.parametrize('n',[1],ids=['" + PRIVATE + "'])\ndef test_failure(n):\n    assert False, '" + PRIVATE + "'\n", "call"),
    ("import pytest\n@pytest.fixture\ndef broken():\n    raise RuntimeError('" + PRIVATE + "')\ndef test_failure(broken): pass\n", "setup"),
    ("raise RuntimeError('" + PRIVATE + "')\n", "collection"),
    ("def test_ok(): pass\n", None),
])
def test_real_pytest_receipt_preserves_outcome_without_private_details(tmp_path, body, phase):
    source, receipt = tmp_path / "test_synthetic.py", tmp_path / "safe.json"
    source.write_text(body, encoding="utf-8")
    environment = child_environment()
    environment.update(PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
    completed = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
        "-p", "scripts.pytest_evidence", "--rootdir", str(tmp_path), "--confcutdir", str(tmp_path),
        "--safe-report", str(receipt), str(source)], cwd=ROOT, env=environment,
        capture_output=True, timeout=30)
    raw = receipt.read_text(encoding="utf-8")
    result = json.loads(raw)
    assert result["completed"] and result["exit_code"] == completed.returncode
    assert result["passed"] is (phase is None)
    assert PRIVATE not in raw and str(Path.home()) not in raw and str(tmp_path) not in raw
    if phase:
        assert completed.returncode != 0
        assert any(failure["phase"] == phase for failure in result["failures"])
        assert all(frame["file"] in {"test_synthetic.py", "<external>"}
                   for failure in result["failures"] for frame in failure["frames"])
    else:
        assert result["counts"]["passed"] == 1


def test_cache_loss_handles_windows_readonly_without_weakening_production(tmp_path, monkeypatch, lose_cache):
    root = tmp_path / "cache"
    root.mkdir()
    blob = root / "synthetic.csv"
    blob.write_bytes(b"sku,quantity\nS1,1\n")
    blob.chmod(stat.S_IREAD)
    real_unlink, blocked = os.unlink, []

    def windows_unlink(path, *, dir_fd=None):
        mode = os.stat(path, dir_fd=dir_fd).st_mode
        if not mode & stat.S_IWUSR:
            blocked.append(True)
            raise PermissionError("synthetic Windows read-only file")
        return real_unlink(path, dir_fd=dir_fd)

    monkeypatch.setattr(os, "unlink", windows_unlink)
    lose_cache(root)
    assert blocked and not root.exists()


def test_cache_loss_does_not_ignore_unrelated_permission_failures(tmp_path, monkeypatch, lose_cache):
    root = tmp_path / "cache"
    root.mkdir()
    blob = root / "synthetic.csv"
    blob.write_bytes(b"synthetic")
    blob.chmod(stat.S_IREAD | stat.S_IWRITE)

    def denied(*args, **kwargs):
        raise PermissionError("synthetic ACL denial")

    monkeypatch.setattr(os, "unlink", denied)
    with pytest.raises(PermissionError):
        lose_cache(root)
    assert blob.exists()
