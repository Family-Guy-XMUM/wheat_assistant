"""Test-owned cache loss, including Windows read-only blob semantics."""
import os
import shutil
import stat
from pathlib import Path

import pytest


@pytest.fixture
def lose_cache(tmp_path):
    def remove(cache_root):
        root = Path(cache_root).resolve()
        if root == tmp_path.resolve() or not root.is_relative_to(tmp_path.resolve()):
            raise ValueError("Cache-loss simulation must stay inside its test directory")

        def clear_readonly(function, filename, error):
            path = Path(filename)
            if (not isinstance(error, PermissionError) or function not in {os.unlink, os.rmdir}
                    or path.is_symlink() or not path.resolve().is_relative_to(root)):
                raise error
            mode = path.stat().st_mode
            if mode & stat.S_IWUSR:
                raise error
            path.chmod(mode | stat.S_IWUSR)
            function(filename)

        shutil.rmtree(root, onexc=clear_readonly)
        assert not root.exists(), "The cache must actually be lost before recovery is tested"

    return remove
