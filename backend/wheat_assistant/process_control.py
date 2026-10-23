"""Own and stop only a subprocess tree created by this invocation."""
from __future__ import annotations

import os
import signal
import subprocess
import time

import psutil


class ManagedProcess:
    def __init__(self, command, **kwargs):
        if os.name == "nt":
            kwargs["creationflags"] = kwargs.get("creationflags", 0) | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        self.process = subprocess.Popen(command, **kwargs)
        self.members: dict[int, float] = {}
        self.inspection_errors: set[str] = set()
        self.family()

    def family(self):
        try:
            if self.process.poll() is None:
                root = psutil.Process(self.process.pid)
                if self.process.pid not in self.members or root.create_time() == self.members[self.process.pid]:
                    for item in [root, *root.children(recursive=True)]:
                        self.members.setdefault(item.pid, item.create_time())
        except psutil.NoSuchProcess:
            pass
        except (psutil.AccessDenied, PermissionError) as exc:
            self.inspection_errors.add(type(exc).__name__)
        live = []
        for pid, created in list(self.members.items()):
            try:
                item = psutil.Process(pid)
                if item.create_time() == created and item.is_running() and item.status() != psutil.STATUS_ZOMBIE:
                    live.append(item)
            except psutil.NoSuchProcess:
                pass
            except (psutil.AccessDenied, PermissionError) as exc:
                self.inspection_errors.add(type(exc).__name__)
        return live

    def stop(self, grace_seconds=10):
        running_at_stop = self.process.poll() is None
        self.family()  # Capture descendants before signalling a redirector/bootloader.
        signal_error = None
        if self.process.poll() is None or self.family():
            try:
                if os.name == "nt":
                    self.process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    os.killpg(self.process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            except OSError as exc:
                signal_error = {"error_type": type(exc).__name__, "os_error": exc.errno,
                                "winerror": getattr(exc, "winerror", None)}
        deadline = time.monotonic() + grace_seconds
        while time.monotonic() < deadline:
            if self.process.poll() is not None and not self.family():
                break
            time.sleep(.05)
        forced = self.process.poll() is None or bool(self.family())
        if forced:
            if os.name != "nt":
                # The new session belongs to this invocation even when the
                # sandbox denies psutil inspection. Kill its group, not merely
                # the wrapper, so denied diagnostics cannot leak a child.
                try:
                    os.killpg(self.process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            # psutil create_time checks prevent a recycled PID from being killed.
            for item in reversed(self.family()):
                try:
                    if item.create_time() == self.members[item.pid]:
                        item.kill()
                except psutil.NoSuchProcess:
                    pass
                except (psutil.AccessDenied, PermissionError) as exc:
                    self.inspection_errors.add(type(exc).__name__)
            if self.process.poll() is None:
                self.process.kill()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.inspection_errors.add("CleanupTimeout")
        cleanup_deadline = time.monotonic() + 5
        while self.family() and time.monotonic() < cleanup_deadline:
            time.sleep(.05)
        remaining = len(self.family())
        exit_code = self.process.poll()
        expected_exit = exit_code in ({0} if os.name == "nt" else {0, -signal.SIGTERM})
        return {"graceful": running_at_stop and expected_exit and not forced and not signal_error and not self.inspection_errors and remaining == 0,
                "running_at_stop": running_at_stop, "expected_exit_code": expected_exit,
                "forced_cleanup": forced, "exit_code": exit_code, "remaining_processes": remaining,
                "children_observed": len([pid for pid in self.members if pid != self.process.pid]),
                "signal": "CTRL_BREAK_EVENT" if os.name == "nt" else "SIGTERM",
                "signal_error": signal_error, "inspection_errors": sorted(self.inspection_errors)}
