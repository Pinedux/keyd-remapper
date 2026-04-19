#!/usr/bin/env python3
"""
Keyd Remapper Desktop Launcher
Launches the FastAPI backend and opens the UI in a native window (pywebview)
or falls back to the system default web browser.
"""

import argparse
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

# Add backend to path
BACKEND_DIR = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

URL = "http://127.0.0.1:8474"


def start_backend() -> None:
    """Start the FastAPI backend server in a background thread."""
    os.environ.setdefault("KEYD_PORT", "8474")
    import uvicorn
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=int(os.environ["KEYD_PORT"]),
        reload=False,
        log_level="info",
        access_log=False,
    )


def wait_for_backend(url: str = f"{URL}/api/health", timeout: float = 30.0) -> bool:
    """Poll the backend until it is ready."""
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


def open_browser() -> None:
    """Open the system default browser."""
    print(f"Opening {URL} in your default browser...")
    webbrowser.open(URL, new=2)  # new=2 -> new tab


def open_pywebview() -> bool:
    """Try to open a native desktop window with pywebview."""
    try:
        import webview
    except ImportError:
        return False

    try:
        window = webview.create_window(
            "Keyd Remapper",
            URL,
            width=1200,
            height=800,
            resizable=True,
            min_size=(800, 600),
        )
        webview.start(debug=False)
        return True
    except Exception as exc:
        print(f"[pywebview] Could not load native window: {exc}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch Keyd Remapper")
    parser.add_argument(
        "--browser", action="store_true", help="Force opening in the system web browser"
    )
    args = parser.parse_args()

    # Start backend in background thread
    backend_thread = threading.Thread(target=start_backend, daemon=True)
    backend_thread.start()

    print("Starting Keyd Remapper backend...")
    if not wait_for_backend():
        print("Backend failed to start within 30 seconds.")
        sys.exit(1)

    print("Backend ready.")

    if args.browser:
        open_browser()
    else:
        success = open_pywebview()
        if not success:
            print("\nNative window unavailable (GTK/Qt libraries missing).")
            print("Falling back to your default web browser...\n")
            open_browser()

    # Keep the main thread alive while backend runs
    try:
        while backend_thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")


if __name__ == "__main__":
    main()
