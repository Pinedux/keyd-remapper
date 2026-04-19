#!/usr/bin/env python3
"""
Standalone entry point for PyInstaller.
Packages the backend + frontend into a single executable.
"""

import os
import sys
import threading
import time
import webbrowser


def get_resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def start_backend() -> None:
    """Start the FastAPI backend server."""
    os.environ.setdefault("KEYD_PORT", "8474")
    backend_dir = get_resource_path("backend")
    frontend_dir = get_resource_path("frontend")
    os.environ["KEYD_FRONTEND_DIR"] = frontend_dir

    sys.path.insert(0, backend_dir)
    import main as backend_main
    import uvicorn

    uvicorn.run(
        backend_main.app,
        host="127.0.0.1",
        port=int(os.environ["KEYD_PORT"]),
        reload=False,
        log_level="info",
        access_log=False,
    )


def wait_for_backend(url: str = "http://127.0.0.1:8474/api/health", timeout: float = 30.0) -> bool:
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def main() -> None:
    backend_thread = threading.Thread(target=start_backend, daemon=True)
    backend_thread.start()

    print("Starting Keyd Remapper backend...")
    if not wait_for_backend():
        print("Backend failed to start within 30 seconds.")
        sys.exit(1)

    print("Backend ready. Opening http://127.0.0.1:8474 in your default browser...")
    webbrowser.open("http://127.0.0.1:8474", new=2)

    try:
        while backend_thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")


if __name__ == "__main__":
    main()
