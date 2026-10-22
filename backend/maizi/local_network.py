"""Probe loopback ports using the platform's listener reuse semantics."""
import os
import socket


def bind_loopback(probe, port):
    if os.name != "nt":
        # asyncio's POSIX listener also enables this: TIME_WAIT is not a live
        # listener and must not force a new port after a graceful restart.
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    elif hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        # Windows SO_REUSEADDR can share an active listener; never enable it.
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    probe.bind(("127.0.0.1", port))
