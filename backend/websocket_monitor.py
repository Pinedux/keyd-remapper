"""WebSocket endpoint to stream keyd monitor output."""

import asyncio
import os
import platform
import shutil
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])

DEMO_INTERVAL_SECONDS = 2
DEMO_MESSAGE = "keyd monitor requires root privileges. Run app with pkexec or ensure keyd access."


async def _stream_keyd_monitor(websocket: WebSocket) -> None:
    """Try to run keyd monitor and stream lines to the websocket."""
    pkexec_path = shutil.which("pkexec")
    keyd_path = shutil.which("keyd")

    cmd: Optional[list[str]] = None
    if pkexec_path and keyd_path:
        cmd = [pkexec_path, keyd_path, "monitor"]
    elif keyd_path and os.geteuid() == 0:
        cmd = [keyd_path, "monitor"]

    if cmd is None:
        # Demo / fallback mode
        while True:
            await websocket.send_json({"type": "event", "data": DEMO_MESSAGE})
            await asyncio.sleep(DEMO_INTERVAL_SECONDS)
        return

    proc: Optional[asyncio.subprocess.Process] = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        if proc.stdout is None:
            raise RuntimeError("Failed to open stdout pipe")

        while True:
            line_bytes = await proc.stdout.readline()
            if not line_bytes:
                break
            line = line_bytes.decode("utf-8", errors="ignore").rstrip("\n")
            await websocket.send_json({"type": "event", "data": line})
    except asyncio.CancelledError:
        raise
    except Exception:
        # Fallback to demo mode on any error
        while True:
            await websocket.send_json({"type": "event", "data": DEMO_MESSAGE})
            await asyncio.sleep(DEMO_INTERVAL_SECONDS)
    finally:
        if proc is not None and proc.returncode is None:
            try:
                proc.kill()
                await asyncio.wait_for(proc.wait(), timeout=2)
            except Exception:
                pass


@router.websocket("/ws/keyd-monitor")
async def keyd_monitor_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    task: Optional[asyncio.Task] = None
    try:
        task = asyncio.create_task(_stream_keyd_monitor(websocket))
        # Keep the connection alive until client disconnects
        while True:
            # Expecting periodic pings or empty messages from client
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
