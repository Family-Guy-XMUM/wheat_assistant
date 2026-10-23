"""Hold an OS lock so desktop launchers cannot open one data directory twice."""
import os
from contextlib import contextmanager
from pathlib import Path

@contextmanager
def data_directory_lock(root: Path):
    root.mkdir(parents=True,exist_ok=True)
    legacy = root / ".maizi-instance.lock"
    lock_file = legacy if legacy.exists() or (root / "maizi.sqlite").is_file() else root / ".wheat_assistant-instance.lock"
    handle=lock_file.open("a+b")
    try:
        handle.seek(0,2)
        if handle.tell()==0:
            handle.write(b"0");handle.flush()
        handle.seek(0)
        try:
            if os.name=="nt":
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as error:
            raise ValueError("wheat_assistant is already running for this data directory. Stop its server console before starting again.") from error
        try:
            yield
        finally:
            handle.seek(0)
            if os.name=="nt":
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(),fcntl.LOCK_UN)
    finally:
        handle.close()
