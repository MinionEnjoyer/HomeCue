"""Optional native SDK probe used to diagnose and recover device enumeration."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class NativeProbeDevice:
    device_id: str
    model: str
    device_type: int
    led_ids: list[int]


def _probe_path() -> Path | None:
    override = os.environ.get("HOMECUE_ICUE_PROBE")
    candidates = [
        Path(override) if override else None,
        Path(getattr(sys, "_MEIPASS", "")) / "homecue-icue-probe.exe",
        Path(sys.executable).resolve().parent / "homecue-icue-probe.exe",
    ]
    return next((candidate for candidate in candidates if candidate and candidate.is_file()), None)


def _sdk_path(probe: Path) -> Path | None:
    candidates = [
        probe.parent / "cuesdk" / "bin" / "iCUESDK.x64_2019.dll",
        probe.parent / "iCUESDK.x64_2019.dll",
    ]
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def enumerate_native_devices(timeout: float = 15.0) -> list[NativeProbeDevice]:
    """Run the official-DLL probe and return its hardware inventory."""
    probe = _probe_path()
    if not probe:
        log.info("Native iCUE diagnostic probe is not bundled in this build")
        return []
    sdk = _sdk_path(probe)
    if not sdk:
        log.warning("Native iCUE diagnostic probe could not locate the bundled Corsair DLL")
        return []
    startupinfo = None
    creationflags = 0
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        creationflags = subprocess.CREATE_NO_WINDOW
    try:
        result = subprocess.run(
            [str(probe), str(sdk)],
            cwd=probe.parent,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )
        payload = json.loads(result.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        log.exception("Native iCUE diagnostic probe failed")
        return []

    devices = [
        NativeProbeDevice(
            device_id=str(item["id"]),
            model=str(item.get("model") or "Unknown"),
            device_type=int(item.get("type", 0)),
            led_ids=[int(led_id) for led_id in item.get("ledIds", [])],
        )
        for item in payload.get("devices", [])
        if item.get("id")
    ]
    log.warning(
        "Native iCUE probe: connected=%s enumeration_error=%s devices=%d exit_code=%d",
        payload.get("connected"),
        payload.get("enumerationError", payload.get("error")),
        len(devices),
        result.returncode,
    )
    return devices
