"""Minimal child environments shared by the worker and release verification."""
from __future__ import annotations

import ntpath
import os
from collections.abc import Mapping

_KEYS = ("PATH", "SystemRoot", "WINDIR", "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL")


def child_environment(environ: Mapping[str, str] | None = None, *, native: bool = False,
                      windows: bool | None = None) -> dict[str, str]:
    parent = os.environ if environ is None else environ
    windows = os.name == "nt" if windows is None else windows
    if windows:
        # os.environ enumerates uppercase names on Windows. A normal dict may
        # contain vendor/test mixed-case names, so compare both consistently.
        normalized = {key.upper(): value for key, value in parent.items()}
        result = {key: normalized[key.upper()] for key in _KEYS if key.upper() in normalized}
        root = result.get("SystemRoot", "")
        if not root.strip() or not ntpath.isabs(root):
            raise ValueError("Windows SystemRoot is missing or invalid; restore the system environment before starting wheat_assistant")
        if native:
            result["PATH"] = ntpath.join(root, "System32")
    else:
        result = {key: parent[key] for key in _KEYS if key in parent}
        if native:
            result["PATH"] = "/usr/bin:/bin"
    result["PYTHONUTF8"] = "1"
    return result
