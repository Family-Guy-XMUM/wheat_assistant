import argparse
import multiprocessing
import os
import socket
import sys
import threading
import webbrowser
from pathlib import Path

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
    port = arguments.port
    try:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))
    except OSError:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
    from platformdirs import user_data_dir
    from maizi.runtime_lock import data_directory_lock
    directory = Path(arguments.data_dir or os.getenv("MAIZI_DATA_DIR") or user_data_dir("MaiZi",appauthor=False)).resolve()
    try:
        with data_directory_lock(directory):
            app = create_app(directory, web)
            if not arguments.no_browser:
                threading.Timer(1.2, lambda: webbrowser.open("http://127.0.0.1:" + str(port))).start()
            print("MaiZi is running at http://127.0.0.1:" + str(port), flush=True)
            uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning", access_log=False)
    except ValueError as error:
        raise SystemExit(str(error)) from error

if __name__ == "__main__":
    main()
