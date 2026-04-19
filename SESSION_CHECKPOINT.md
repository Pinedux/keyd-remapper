# Session Checkpoint

**Date:** 2026-04-19
**Session ID:** c0d047344194dfe223e4b7455467165d

## Project State

- **Version:** v1.0.1
- **Release:** https://github.com/Pinedux/keyd-remapper/releases/tag/v1.0.1
- **Git commit:** `0ee6fc1`

## What was built

Keyd Remapper — an open-source Linux desktop application for keyboard detection, firmware search, and key remapping using `keyd`.

### Architecture
- **Backend:** Python FastAPI (`backend/`)
- **Frontend:** Vanilla JS SPA (`frontend/`)
- **Desktop shell:** Tauri v2 (`src-tauri/`) + PyInstaller standalone (`launch.py`, `pyinstaller_entry.py`)
- **Distribution:** AppImage (17 MB), `.deb`, `.rpm`

### Features implemented
1. Smart keyboard detection via `/proc/bus/input/devices` + `lsusb` + EV bitmask parsing (filters mice, power buttons, speakers, virtual devices).
2. Per-device keyd configuration (multiple `.conf` files in `/etc/keyd/`).
3. Enhanced firmware search (QMK Configurator API, VIAL, GitHub, generic fallback).
4. Live WebSocket monitor for keyd events with auto-reconnect.
5. keyd install/activate/reload management via `pkexec`.
6. Dark-themed responsive web UI with device-type badges and multi-config editor.

### Files created / heavily modified
- `backend/main.py`
- `backend/keyboard_detector.py`
- `backend/keyd_manager.py`
- `backend/firmware_searcher.py`
- `backend/websocket_monitor.py`
- `frontend/js/app.js`
- `frontend/css/style.css`
- `frontend/index.html`
- `src-tauri/src/main.rs`
- `src-tauri/tauri.conf.json`
- `launch.py`
- `pyinstaller_entry.py`

## How to resume

```bash
cd /home/pinedux/Descargas/corne/keyd-remapper
source .venv/bin/activate
python backend/main.py          # dev mode
# OR
python3 launch.py --browser     # pywebview mode
# OR
npx tauri dev                   # Tauri mode
```

## Release artifact

The latest AppImage is attached to GitHub Release v1.0.1.
