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
KEYD_CONFIG_PATH = Path("/etc/keyd/default.conf")


class KeyboardInfo(BaseModel):
    id: str
    name: str
    vendor_id: str
    product_id: str
    bus: str
    device_path: str | None
    is_keyd_managed: bool


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


def _is_keyboard_device(dev: dict) -> bool:
    """Determine if a device entry represents a keyboard."""
    ev = dev.get("ev", "").lower()
    if "120013" in ev:
        return True
    handlers = dev.get("handlers", "")
    if "kbd" in handlers.split():
        return True
    if "event" in handlers:
        # Heuristic: if it has a name that looks like a keyboard
        name = dev.get("name", "").lower()
        keyboard_keywords = ["keyboard", "kbd", "keypad", "corne", "planck", "ergodox"]
        if any(kw in name for kw in keyboard_keywords):
            return True
    return False


def _get_keyd_ids() -> List[str]:
    """Parse keyd default.conf and return list of ids in the [ids] section."""
    if not KEYD_CONFIG_PATH.exists():
        return []
    try:
        content = KEYD_CONFIG_PATH.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    ids = []
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
    """Detect connected keyboards and enrich with metadata."""
    raw_devices = _parse_input_devices()
    lsusb_map = _run_lsusb()
    keyd_ids = _get_keyd_ids()

    keyboards = []
    seen_ids = set()

    for dev in raw_devices:
        if not _is_keyboard_device(dev):
            continue

        vid = dev.get("vendor_id", "").lower()
        pid = dev.get("product_id", "").lower()
        bus_num = dev.get("bus", "")

        # Skip entries with no vendor/product unless they have kbd handler
        if not vid or not pid:
            continue

        device_id = f"{vid}:{pid}"
        if device_id in seen_ids:
            continue
        seen_ids.add(device_id)

        name = dev.get("name", "Unknown Keyboard")
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
            )
        )

    return keyboards


@router.get("", response_model=List[KeyboardInfo])
def get_keyboards() -> List[KeyboardInfo]:
    try:
        return detect_keyboards()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
