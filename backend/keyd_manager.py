"""keyd installation and configuration management."""

import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/keyd", tags=["keyd"])

KEYD_CONFIG_DIR = Path("/etc/keyd")
KEYD_CONFIG_PATH = KEYD_CONFIG_DIR / "default.conf"
DEFAULT_CONFIG = """# keyd default configuration
# Add your device ids below and define layers/remaps.

[ids]
*

[main]
"""


class KeydStatus(BaseModel):
    installed: bool
    active: bool
    version: str | None
    config_path: str


class InstallResult(BaseModel):
    success: bool
    message: str


class ConfigPayload(BaseModel):
    content: str


class ConfigResult(BaseModel):
    content: str
    exists: bool


class WriteConfigResult(BaseModel):
    success: bool


class ReloadResult(BaseModel):
    success: bool
    output: str
    error: str


class KeyListResult(BaseModel):
    keys: List[str]


class ConfigInfo(BaseModel):
    name: str
    device_id: str | None
    content_preview: str


class DeviceConfigPayload(BaseModel):
    device_id: str
    content: str


def _which(cmd: str) -> str | None:
    return shutil.which(cmd)


def _run(cmd: List[str], timeout: int = 30, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=check)


def _detect_distro() -> str | None:
    """Detect Linux distro family from /etc/os-release."""
    os_release = Path("/etc/os-release")
    if not os_release.exists():
        return None
    try:
        content = os_release.read_text(encoding="utf-8", errors="ignore")
        id_match = re.search(r'^ID\s*=\s*"?([^"\n]+)"?', content, re.MULTILINE)
        id_like_match = re.search(r'^ID_LIKE\s*=\s*"?([^"\n]+)"?', content, re.MULTILINE)
        distro_id = id_match.group(1).lower() if id_match else ""
        id_like = id_like_match.group(1).lower() if id_like_match else ""
        if distro_id in {"arch", "manjaro", "endeavouros", "artix", "cachyos"} or "arch" in id_like:
            return "arch"
        if distro_id in {"debian", "ubuntu", "linuxmint", "pop", "elementary", "zorin", "kali", "raspbian"} or "debian" in id_like:
            return "debian"
        if distro_id in {"fedora", "rhel", "centos", "rocky", "almalinux", "nobara"} or "fedora" in id_like or "rhel" in id_like:
            return "fedora"
        return None
    except Exception:
        return None


def _sanitize_device_id(device_id: str) -> str:
    """Sanitize a device id (vid:pid) into a safe filename."""
    return re.sub(r"[^0-9a-fA-F]", "_", device_id)


def _extract_first_device_id(content: str) -> str | None:
    """Extract the first non-wildcard device id from an [ids] section."""
    in_ids = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("[ids]"):
            in_ids = True
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            in_ids = False
            continue
        if in_ids and stripped and not stripped.startswith("#"):
            if stripped != "*":
                return stripped
    return None


@router.get("/status", response_model=KeydStatus)
def get_status() -> KeydStatus:
    """Return keyd installation and service status."""
    installed = False
    version = None
    active = False

    keyd_path = _which("keyd")
    if keyd_path:
        installed = True
        try:
            proc = _run(["keyd", "--version"])
            if proc.returncode == 0:
                version = proc.stdout.strip().splitlines()[0].strip()
            else:
                version = "unknown"
        except Exception:
            version = "unknown"

    # Check systemd service status
    try:
        proc = _run(["systemctl", "is-active", "keyd"])
        active = proc.stdout.strip() == "active"
    except Exception:
        active = False

    return KeydStatus(
        installed=installed,
        active=active,
        version=version,
        config_path=str(KEYD_CONFIG_DIR),
    )


@router.post("/install", response_model=InstallResult)
def install_keyd() -> InstallResult:
    """Install keyd using the system package manager via pkexec."""
    keyd_path = _which("keyd")
    if keyd_path:
        return InstallResult(success=True, message="keyd is already installed.")

    if platform.system() != "Linux":
        raise HTTPException(status_code=400, detail="Installation is only supported on Linux.")

    distro = _detect_distro()
    if distro == "arch":
        cmd = ["pkexec", "pacman", "-S", "--noconfirm", "keyd"]
    elif distro == "debian":
        cmd = ["pkexec", "apt", "install", "-y", "keyd"]
    elif distro == "fedora":
        cmd = ["pkexec", "dnf", "install", "-y", "keyd"]
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported or unknown distribution: {distro or 'unknown'}. Please install keyd manually.",
        )

    try:
        proc = _run(cmd, timeout=120)
        if proc.returncode == 0:
            return InstallResult(success=True, message="keyd installed successfully.")
        return InstallResult(
            success=False,
            message=f"Installation failed (exit {proc.returncode}): {proc.stderr or proc.stdout}",
        )
    except subprocess.TimeoutExpired:
        return InstallResult(success=False, message="Installation timed out.")
    except Exception as exc:
        return InstallResult(success=False, message=str(exc))


@router.post("/activate", response_model=KeydStatus)
def activate_keyd() -> KeydStatus:
    """Enable and start the keyd systemd service."""
    try:
        proc = _run(["pkexec", "systemctl", "enable", "keyd", "--now"], timeout=30)
        if proc.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to activate keyd: {proc.stderr or proc.stdout}",
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return get_status()


# Backward-compatible endpoints

@router.get("/config", response_model=ConfigResult)
def get_config() -> ConfigResult:
    """Read the current keyd default configuration file."""
    if KEYD_CONFIG_PATH.exists():
        try:
            content = KEYD_CONFIG_PATH.read_text(encoding="utf-8", errors="ignore")
            return ConfigResult(content=content, exists=True)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ConfigResult(content=DEFAULT_CONFIG, exists=False)


@router.post("/config", response_model=WriteConfigResult)
def write_config(payload: ConfigPayload) -> WriteConfigResult:
    """Write configuration to /etc/keyd/default.conf using pkexec tee."""
    return _write_config_file("default", payload.content)


# Multi-device configuration endpoints

@router.get("/configs", response_model=List[ConfigInfo])
def list_configs() -> List[ConfigInfo]:
    """List all keyd configuration files."""
    configs = []
    if not KEYD_CONFIG_DIR.exists():
        return configs

    for conf_file in sorted(KEYD_CONFIG_DIR.glob("*.conf")):
        name = conf_file.stem
        try:
            content = conf_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            content = ""
        preview = content[:200]
        device_id = _extract_first_device_id(content)
        configs.append(
            ConfigInfo(
                name=name,
                device_id=device_id,
                content_preview=preview,
            )
        )
    return configs


@router.get("/config/{name}", response_model=ConfigResult)
def get_named_config(name: str) -> ConfigResult:
    """Read a specific keyd configuration file."""
    conf_path = KEYD_CONFIG_DIR / f"{name}.conf"
    if conf_path.exists():
        try:
            content = conf_path.read_text(encoding="utf-8", errors="ignore")
            return ConfigResult(content=content, exists=True)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ConfigResult(content="", exists=False)


@router.post("/config/{name}", response_model=WriteConfigResult)
def write_named_config(name: str, payload: ConfigPayload) -> WriteConfigResult:
    """Write configuration to a specific keyd configuration file."""
    return _write_config_file(name, payload.content)


@router.delete("/config/{name}", response_model=WriteConfigResult)
def delete_named_config(name: str) -> WriteConfigResult:
    """Delete a specific keyd configuration file."""
    if platform.system() != "Linux":
        raise HTTPException(status_code=400, detail="Only supported on Linux.")

    if name == "default":
        raise HTTPException(status_code=400, detail="Cannot delete the default configuration.")

    conf_path = KEYD_CONFIG_DIR / f"{name}.conf"
    if not conf_path.exists():
        return WriteConfigResult(success=True)

    try:
        proc = _run(["pkexec", "rm", str(conf_path)], timeout=15)
        if proc.returncode == 0:
            return WriteConfigResult(success=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete config: {proc.stderr or proc.stdout}",
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/apply-device", response_model=WriteConfigResult)
def apply_device_config(payload: DeviceConfigPayload) -> WriteConfigResult:
    """Create or overwrite a config file named after the sanitized device_id."""
    if platform.system() != "Linux":
        raise HTTPException(status_code=400, detail="Only supported on Linux.")

    sanitized = _sanitize_device_id(payload.device_id)
    if not sanitized:
        raise HTTPException(status_code=400, detail="Invalid device_id.")

    content = payload.content
    # Prepend [ids] section if not already present
    if "[ids]" not in content:
        content = f"[ids]\n{payload.device_id}\n\n" + content

    return _write_config_file(sanitized, content)


def _write_config_file(name: str, content: str) -> WriteConfigResult:
    """Internal helper to write a config file using pkexec tee."""
    if platform.system() != "Linux":
        raise HTTPException(status_code=400, detail="Only supported on Linux.")

    conf_path = KEYD_CONFIG_DIR / f"{name}.conf"
    try:
        # Ensure directory exists
        proc = _run(["pkexec", "mkdir", "-p", str(KEYD_CONFIG_DIR)], timeout=15)
        if proc.returncode != 0 and "File exists" not in (proc.stderr or ""):
            return WriteConfigResult(success=False)

        proc = subprocess.run(
            ["pkexec", "tee", str(conf_path)],
            input=content,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if proc.returncode == 0:
            return WriteConfigResult(success=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to write config: {proc.stderr or proc.stdout}",
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/reload", response_model=ReloadResult)
def reload_keyd() -> ReloadResult:
    """Reload keyd configuration."""
    try:
        proc = _run(["pkexec", "keyd", "reload"], timeout=15)
        return ReloadResult(
            success=proc.returncode == 0,
            output=proc.stdout.strip(),
            error=proc.stderr.strip(),
        )
    except Exception as exc:
        return ReloadResult(success=False, output="", error=str(exc))


# Hardcoded comprehensive fallback key list
_FALLBACK_KEYS: List[str] = [
    # Letters
    "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m",
    "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z",
    # Numbers
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "0",
    # Function keys
    "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
    "f13", "f14", "f15", "f16", "f17", "f18", "f19", "f20", "f21", "f22", "f23", "f24",
    # Modifiers
    "leftcontrol", "rightcontrol", "leftshift", "rightshift",
    "leftalt", "rightalt", "leftmeta", "rightmeta",
    "control", "shift", "alt", "meta",
    # Special
    "esc", "escape", "enter", "return", "space", "tab",
    "backspace", "delete", "insert", "home", "end",
    "pageup", "pagedown", "print", "scrolllock", "pause",
    # Arrows
    "up", "down", "left", "right",
    # Numpad
    "kp0", "kp1", "kp2", "kp3", "kp4", "kp5", "kp6", "kp7", "kp8", "kp9",
    "kpenter", "kpplus", "kpminus", "kpmultiply", "kpdivide", "kpdecimal",
    # Lock keys
    "capslock", "numlock",
    # Media
    "mute", "volumedown", "volumeup", "playpause", "nextsong", "previoussong",
    # Mouse emulation (keyd specific)
    "mouseleft", "mouseright", "mousemiddle", "mousescrollup", "mousescrolldown",
    # Layers
    "layer", "swap", "oneshot", "tap",
    # Misc
    "compose", "sysrq", "break", "menu",
    # International
    "grave", "minus", "equal", "leftbrace", "rightbrace", "backslash",
    "semicolon", "apostrophe", "comma", "dot", "slash",
]


@router.get("/keys", response_model=KeyListResult)
def list_keys() -> KeyListResult:
    """Return valid keyd key names."""
    if _which("keyd"):
        try:
            proc = _run(["keyd", "list-keys"], timeout=10)
            if proc.returncode == 0:
                keys = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
                return KeyListResult(keys=keys)
        except Exception:
            pass
    return KeyListResult(keys=_FALLBACK_KEYS)
