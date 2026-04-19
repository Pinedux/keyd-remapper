#!/usr/bin/env python3
"""
Keyd Remapper Desktop Launcher
Alternative to Tauri: uses pywebview to open the local FastAPI backend
in a native desktop window.
"""

import os
import sys
import threading
import time
from pathlib import Path

# Add backend to path
BACKEND_DIR = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

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

def wait_for_backend(url: str = "http://127.0.0.1:8474/api/health", timeout: float = 30.0) -> bool:
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

def main() -> None:
    """Launch the desktop application."""
    try:
        import webview
    except ImportError:
        print("pywebview is not installed.")
        print("Install it with: pip install pywebview")
        sys.exit(1)

    # Start backend in background thread
    backend_thread = threading.Thread(target=start_backend, daemon=True)
    backend_thread.start()

    print("Starting Keyd Remapper backend...")
    if not wait_for_backend():
        print("Backend failed to start within 30 seconds.")
        sys.exit(1)

    print("Backend ready. Opening desktop window...")
    window = webview.create_window(
        "Keyd Remapper",
        "http://127.0.0.1:8474",
        width=1200,
        height=800,
        resizable=True,
        min_size=(800, 600),
    )
    webview.start(debug=False)

if __name__ == "__main__":
    main()
