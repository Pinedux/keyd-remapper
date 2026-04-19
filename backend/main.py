"""Keyd Remapper FastAPI backend application."""

import mimetypes
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse

import keyboard_detector
import keyd_manager
import firmware_searcher
import websocket_monitor

# Project paths
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
INDEX_HTML = FRONTEND_DIR / "index.html"

app = FastAPI(title="keyd-remapper backend", version="0.1.0")

# CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(keyboard_detector.router)
app.include_router(keyd_manager.router)
app.include_router(firmware_searcher.router)
app.include_router(websocket_monitor.router)


@app.on_event("startup")
def startup_event() -> None:
    port = os.getenv("KEYD_PORT", "8474")
    print(f"Keyd Remapper backend running on http://127.0.0.1:{port}")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/{path:path}", response_model=None)
def spa_fallback(request: Request, path: str) -> HTMLResponse | FileResponse:
    """Serve static files or index.html for SPA client-side routing."""
    # Try to serve an existing static file from the frontend directory
    if path:
        file_path = FRONTEND_DIR / path
        if file_path.is_file():
            media_type, _ = mimetypes.guess_type(str(file_path))
            return FileResponse(file_path, media_type=media_type or "text/plain")

    # Fallback to index.html for SPA routes
    if INDEX_HTML.exists():
        content = INDEX_HTML.read_text(encoding="utf-8", errors="ignore")
        return HTMLResponse(content=content)

    # Minimal fallback when frontend build is missing
    return HTMLResponse(
        content="""<!DOCTYPE html>
<html>
<head><title>keyd-remapper</title></head>
<body>
  <h1>keyd-remapper</h1>
  <p>Frontend build not found. API is available at /api/</p>
</body>
</html>"""
    )


def main() -> None:
    import uvicorn

    port = int(os.getenv("KEYD_PORT", "8474"))
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
