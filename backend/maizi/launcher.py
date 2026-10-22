import argparse
import multiprocessing
import os
import signal
import socket
import sys
import threading
import webbrowser
from pathlib import Path
from maizi.local_network import bind_loopback


def open_listener(port, strict=False):
    listener = socket.socket()
    try:
        bind_loopback(listener, port)
        listener.listen(128)
        return listener
    except OSError:
        listener.close()
        if strict:
            raise SystemExit("The requested local port is unavailable; stop the existing listener or choose another port.")
        listener = socket.socket()
        try:
            bind_loopback(listener, 0)
            listener.listen(128)
            return listener
        except BaseException:
            listener.close()
            raise

def main():
    multiprocessing.freeze_support()
    if "--worker" in sys.argv:
        from maizi.worker import main as worker
        index = sys.argv.index("--worker")
        worker(sys.argv[index + 1:])
        return
    from dotenv import load_dotenv
    configuration_root = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2]
    load_dotenv(configuration_root / ".env", override=False)
    parser = argparse.ArgumentParser(description="Start the local MaiZi web application")
    parser.add_argument("--port", type=int, default=int(os.getenv("MAIZI_PORT", "8765")))
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--strict-port", action="store_true", help="Fail if the requested port is unavailable")
    parser.add_argument("--data-dir")
    arguments = parser.parse_args()
    from maizi.api import create_app
    import uvicorn
    web = None
    if getattr(sys, "frozen", False):
        web = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "web"
        # Local runtime configuration is separate from the signed/bundled code.
        from dotenv import load_dotenv
        load_dotenv(Path(sys.executable).parent / ".env", override=False)
    from platformdirs import user_data_dir
    from maizi.runtime_lock import data_directory_lock
    directory = Path(arguments.data_dir or os.getenv("MAIZI_DATA_DIR") or user_data_dir("MaiZi",appauthor=False)).resolve()
    try:
        # Reserve the actual listening socket through startup. Uvicorn receives
        # this same socket; there is no probe-close-rebind gap.
        with open_listener(arguments.port, arguments.strict_port) as listener, data_directory_lock(directory):
            port = listener.getsockname()[1]
            app = create_app(directory, web)
            timer = None
            previous_break = None
            server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, backlog=128, log_level="warning", access_log=False))
            try:
                if os.name == "nt" and hasattr(signal, "SIGBREAK"):
                    # Uvicorn replays a captured signal after lifespan shutdown.
                    # An explicit handler makes a completed CTRL_BREAK shutdown
                    # return 0 rather than invoke the CRT default termination.
                    previous_break = signal.signal(signal.SIGBREAK, lambda *_: setattr(server, "should_exit", True))
                if not arguments.no_browser:
                    timer = threading.Timer(1.2, lambda: webbrowser.open("http://127.0.0.1:" + str(port)))
                    timer.daemon = True
                    timer.start()
                print("MaiZi is running at http://127.0.0.1:" + str(port), flush=True)
                server.run(sockets=[listener])
                if not server.started:
                    raise SystemExit("MaiZi could not finish startup. Check the local startup error and retry.")
            except KeyboardInterrupt:
                pass
            finally:
                if timer:
                    timer.cancel()
                if previous_break is not None:
                    signal.signal(signal.SIGBREAK, previous_break)
                app.state.store.close()
    except ValueError as error:
        raise SystemExit(str(error)) from error

if __name__ == "__main__":
    main()
