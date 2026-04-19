"""Keyboard detection module for keyd-remapper."""

import re
import subprocess
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/keyboards", tags=["keyboards"])

# Path constants
INPUT_DEVICES_PATH = Path("/proc/bus/input/devices")
KEYD_CONFIG_DIR = Path("/etc/keyd")

# EV bitmask constants
EV_KEY = 0x1
EV_REL = 0x2

EXCLUDED_NAME_KEYWORDS = [
    "mouse", "speaker", "button", "virtual", "qemu", "vbox",
    "headset", "camera", "video", "touchpad", "trackpoint", "webcam",
    "consumer control", "system control", "power", "sleep", "lid",
    "fan", "thermal",
]

KEYWORD_HEURISTICS = ["keyboard", "kbd", "keypad", "corne", "planck", "ergodox"]


class KeyboardInfo(BaseModel):
    id: str
    name: str
    vendor_id: str
    product_id: str
    bus: str
    device_path: str | None
    is_keyd_managed: bool
    device_type: str


def _parse_ev_mask(ev_str: str) -> int:
    """Parse the EV bitmask string into an integer."""
    try:
        return int(ev_str, 16)
    except ValueError:
        return 0


def _parse_input_devices() -> List[dict]:
    """Parse /proc/bus/input/devices and return raw device dicts."""
    if not INPUT_DEVICES_PATH.exists():
        return []

    content = INPUT_DEVICES_PATH.read_text(encoding="utf-8", errors="ignore")
    devices = []
    raw_blocks = re.split(r"\n\n+", content.strip())

    for block in raw_blocks:
        dev = {
            "name": "",
            "bus": "",
            "vendor_id": "",
            "product_id": "",
            "handlers": "",
            "phys": "",
            "sysfs": "",
            "ev": "",
        }
        for line in block.splitlines():
            if line.startswith("N: Name="):
                dev["name"] = line.split("=", 1)[1].strip().strip('"')
            elif line.startswith("I: "):
                bus_match = re.search(r"Bus=([0-9a-fA-F]+)", line)
                vendor_match = re.search(r"Vendor=([0-9a-fA-F]+)", line)
                product_match = re.search(r"Product=([0-9a-fA-F]+)", line)
                dev["bus"] = bus_match.group(1) if bus_match else ""
                dev["vendor_id"] = vendor_match.group(1) if vendor_match else ""
                dev["product_id"] = product_match.group(1) if product_match else ""
            elif line.startswith("H: Handlers="):
                dev["handlers"] = line.split("=", 1)[1].strip()
            elif line.startswith("P: Phys="):
                dev["phys"] = line.split("=", 1)[1].strip()
            elif line.startswith("S: Sysfs="):
                dev["sysfs"] = line.split("=", 1)[1].strip()
            elif line.startswith("B: EV="):
                dev["ev"] = line.split("=", 1)[1].strip()
        devices.append(dev)
    return devices


def _is_excluded_name(name: str) -> bool:
    """Check if device name contains excluded keywords."""
    lower = name.lower()
    return any(kw in lower for kw in EXCLUDED_NAME_KEYWORDS)


def _classify_device(dev: dict) -> str:
    """
    Classify a device as 'keyboard', 'mouse', or 'other'.

    Rules:
      - Must have an event handler.
      - Exclude generic power buttons (0000:0000, 0000:0001).
      - Exclude devices with excluded keywords in name.
      - Parse EV mask. Must have EV_KEY (0x1) to be a keyboard.
      - If EV_REL (0x2) is present and name doesn't clearly contain 'keyboard',
        classify as 'mouse' / exclude from keyboard.
      - Keyword heuristic is a last resort only when EV mask confirms KEY support.
    """
    handlers = dev.get("handlers", "")
    name = dev.get("name", "")
    vid = dev.get("vendor_id", "").lower()
    pid = dev.get("product_id", "").lower()
    ev_str = dev.get("ev", "").strip()

    # Exclude devices with no event handler
    if not any(token.startswith("event") for token in handlers.split()):
        return "other"

    # Exclude generic power buttons
    if (vid == "0000" and pid in ("0000", "0001")) or (vid == "0000" and pid == "0000"):
        return "other"

    # Exclude by name keywords
    if _is_excluded_name(name):
        return "other"

    ev_mask = _parse_ev_mask(ev_str)

    has_key = bool(ev_mask & EV_KEY)
    has_rel = bool(ev_mask & EV_REL)

    if not has_key:
        return "other"

    # If it has REL and name doesn't clearly say keyboard, it's probably a mouse
    if has_rel and "keyboard" not in name.lower():
        return "mouse"

    # Last resort: keyword heuristic only if KEY is supported
    lower_name = name.lower()
    if any(kw in lower_name for kw in KEYWORD_HEURISTICS):
        return "keyboard"

    # If EV mask strongly indicates keyboard (common keyboard mask 120013)
    if "120013" in ev_str.lower():
        return "keyboard"

    # If it has KEY but no clear keyboard indicators, still count it
    # if 'kbd' handler is present
    if "kbd" in handlers.split():
        return "keyboard"

    # Default: if it has KEY support and an event handler, consider it keyboard
    return "keyboard"


def _get_keyd_ids() -> List[str]:
    """Parse all keyd .conf files and return list of ids found in [ids] sections."""
    ids = []
    if not KEYD_CONFIG_DIR.exists():
        return ids

    for conf_file in sorted(KEYD_CONFIG_DIR.glob("*.conf")):
        try:
            content = conf_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        in_ids_section = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("[ids]"):
                in_ids_section = True
                continue
            if stripped.startswith("[") and stripped.endswith("]"):
                in_ids_section = False
                continue
            if in_ids_section and stripped and not stripped.startswith("#"):
                ids.append(stripped.lower())
    return ids


def _run_lsusb() -> dict:
    """Run lsusb and return mapping of (vendor_id, product_id) -> name."""
    mapping = {}
    try:
        result = subprocess.run(
            ["lsusb"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return mapping
        for line in result.stdout.splitlines():
            # Format: Bus 001 Device 002: ID 046d:c52b Logitech, Inc. Unifying Receiver
            match = re.search(r"ID\s+([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\s+(.+)", line)
            if match:
                vid = match.group(1).lower()
                pid = match.group(2).lower()
                name = match.group(3).strip()
                mapping[(vid, pid)] = name
    except Exception:
        pass
    return mapping


def _try_pyusb_name(vendor_id: str, product_id: str) -> str | None:
    """Try to get product string using pyusb."""
    try:
        import usb.core  # type: ignore
        import usb.util  # type: ignore
    except ImportError:
        return None

    try:
        vid = int(vendor_id, 16)
        pid = int(product_id, 16)
        dev = usb.core.find(idVendor=vid, idProduct=pid)
        if dev is None:
            return None
        # Try product string
        product = usb.util.get_string(dev, dev.iProduct)
        if product:
            return product
        manufacturer = usb.util.get_string(dev, dev.iManufacturer)
        if manufacturer:
            return manufacturer
    except Exception:
        pass
    return None


def _find_event_device(handlers: str) -> str | None:
    """Extract event device path from handlers string."""
    for token in handlers.split():
        if token.startswith("event"):
            return f"/dev/input/{token}"
    return None


def detect_keyboards() -> List[KeyboardInfo]:
    """Detect connected input devices and enrich with metadata."""
    raw_devices = _parse_input_devices()
    lsusb_map = _run_lsusb()
    keyd_ids = _get_keyd_ids()

    keyboards = []
    seen_ids = set()

    for dev in raw_devices:
        vid = dev.get("vendor_id", "").lower()
        pid = dev.get("product_id", "").lower()
        bus_num = dev.get("bus", "")

        # Skip entries with no vendor/product
        if not vid or not pid:
            continue

        device_id = f"{vid}:{pid}"
        if device_id in seen_ids:
            continue
        seen_ids.add(device_id)

        device_type = _classify_device(dev)

        name = dev.get("name", "Unknown Device")
        # Try to enrich name
        usb_name = lsusb_map.get((vid, pid))
        if usb_name:
            name = usb_name
        else:
            pyusb_name = _try_pyusb_name(vid, pid)
            if pyusb_name:
                name = pyusb_name

        # Determine bus type string
        bus_type = "usb"
        if bus_num:
            try:
                bus_int = int(bus_num, 16)
                if bus_int == 0x03:
                    bus_type = "usb"
                elif bus_int == 0x01:
                    bus_type = "isa"
                elif bus_int == 0x11:
                    bus_type = "i2c"
                elif bus_int == 0x19:
                    bus_type = "spi"
                else:
                    bus_type = f"bus_{bus_num}"
            except ValueError:
                bus_type = bus_num

        device_path = _find_event_device(dev.get("handlers", ""))

        is_keyd_managed = False
        for kid in keyd_ids:
            if device_id in kid or kid == "*":
                is_keyd_managed = True
                break

        keyboards.append(
            KeyboardInfo(
                id=device_id,
                name=name,
                vendor_id=vid,
                product_id=pid,
                bus=bus_type,
                device_path=device_path,
                is_keyd_managed=is_keyd_managed,
                device_type=device_type,
            )
        )

    return keyboards


@router.get("", response_model=List[KeyboardInfo])
def get_keyboards() -> List[KeyboardInfo]:
    try:
        return detect_keyboards()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
