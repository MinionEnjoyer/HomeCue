"""iCUE lighting profile management via the CgSDK (Game Integration SDK)."""

from __future__ import annotations

import ctypes
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

# Common iCUE install paths to search for the CgSDK DLL
_CGSDK_DLL_NAME = "CGSDK.x64_2015.dll"
_ICUE_SEARCH_PATHS = [
    r"C:\Program Files\Corsair\CORSAIR iCUE 5 Software",
    r"C:\Program Files\Corsair\CORSAIR iCUE 4 Software",
    r"C:\Program Files (x86)\Corsair\CORSAIR iCUE 5 Software",
    r"C:\Program Files (x86)\Corsair\CORSAIR iCUE 4 Software",
]

# Default GameSdkEffects directory
_DEFAULT_PROFILES_PATH = r"C:\ProgramData\Corsair\CUE5\GameSdkEffects\HomeCue"

# Profile name constraints: CgSDK requires a-z, A-Z, 0-9, underscore only
_GAME_NAME = "HomeCue"


def _find_cgsdk_dll() -> str | None:
    """Search for the CgSDK DLL in common iCUE install locations."""
    for search_dir in _ICUE_SEARCH_PATHS:
        dll_path = os.path.join(search_dir, _CGSDK_DLL_NAME)
        if os.path.isfile(dll_path):
            return dll_path

    # Try PATH / system directories
    try:
        ctypes.cdll.LoadLibrary(_CGSDK_DLL_NAME)
        return _CGSDK_DLL_NAME
    except OSError:
        pass

    return None


class ProfileManager:
    """Manages iCUE lighting profiles via the CgSDK.

    Profiles are .cueprofile files exported from iCUE (Lighting Effects only)
    and placed in the GameSdkEffects directory. This class uses the CgSDK DLL
    to activate/deactivate them by name.
    """

    def __init__(self, profiles_path: str | None = None) -> None:
        self._profiles_path = Path(profiles_path or _DEFAULT_PROFILES_PATH)
        self._dll: ctypes.CDLL | None = None
        self._active_profile: str | None = None
        self._initialized = False

    def initialize(self) -> bool:
        """Load the CgSDK DLL and register as a game. Returns True on success."""
        dll_path = _find_cgsdk_dll()
        if not dll_path:
            log.error(
                "CgSDK DLL (%s) not found. Profile switching unavailable. "
                "Ensure iCUE is installed.",
                _CGSDK_DLL_NAME,
            )
            return False

        try:
            self._dll = ctypes.cdll.LoadLibrary(dll_path)
            log.info("Loaded CgSDK from %s", dll_path)
        except OSError:
            log.exception("Failed to load CgSDK DLL from %s", dll_path)
            return False

        # Set up function signatures
        self._dll.CgSdkSetGame.argtypes = [ctypes.c_char_p]
        self._dll.CgSdkSetGame.restype = ctypes.c_bool
        self._dll.CgSdkSetState.argtypes = [ctypes.c_char_p]
        self._dll.CgSdkSetState.restype = ctypes.c_bool
        self._dll.CgSdkClearState.argtypes = [ctypes.c_char_p]
        self._dll.CgSdkClearState.restype = ctypes.c_bool
        self._dll.CgSdkClearAllStates.argtypes = []
        self._dll.CgSdkClearAllStates.restype = ctypes.c_bool

        # Register as a "game" with iCUE
        result = self._dll.CgSdkSetGame(_GAME_NAME.encode())
        if not result:
            log.error("CgSdkSetGame failed. Is iCUE running with SDK enabled?")
            return False

        # Ensure the profiles directory exists
        self._profiles_path.mkdir(parents=True, exist_ok=True)

        # Create/update priorities.cfg
        self._update_priorities_cfg()

        self._initialized = True
        log.info(
            "Profile manager initialized. Profiles directory: %s",
            self._profiles_path,
        )
        return True

    def available_profiles(self) -> list[str]:
        """Return list of available profile names (filenames without extension)."""
        if not self._profiles_path.exists():
            return []

        profiles = []
        for f in sorted(self._profiles_path.glob("*.cueprofile")):
            profiles.append(f.stem)

        return profiles

    def activate(self, profile_name: str) -> bool:
        """Activate a lighting profile by name. Deactivates any current profile first."""
        if not self._initialized or not self._dll:
            log.error("Profile manager not initialized")
            return False

        if profile_name not in self.available_profiles():
            log.error("Profile '%s' not found in %s", profile_name, self._profiles_path)
            return False

        # Deactivate current profile
        if self._active_profile and self._active_profile != profile_name:
            self._dll.CgSdkClearState(self._active_profile.encode())

        result = self._dll.CgSdkSetState(profile_name.encode())
        if result:
            self._active_profile = profile_name
            log.info("Activated profile: %s", profile_name)
        else:
            log.error("CgSdkSetState failed for profile: %s", profile_name)

        return result

    def deactivate(self) -> bool:
        """Deactivate the current profile, returning to iCUE's default."""
        if not self._initialized or not self._dll:
            return False

        result = self._dll.CgSdkClearAllStates()
        if result:
            log.info("Deactivated profile: %s", self._active_profile)
            self._active_profile = None
        else:
            log.error("CgSdkClearAllStates failed")

        return result

    @property
    def active_profile(self) -> str | None:
        """The currently active profile name, or None if using iCUE default."""
        return self._active_profile

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def _update_priorities_cfg(self) -> None:
        """Create or update the priorities.cfg file for all available profiles."""
        profiles = self.available_profiles()
        if not profiles:
            return

        cfg_path = self._profiles_path / "priorities.cfg"
        lines = []
        for i, name in enumerate(profiles):
            # All profiles at priority 128+ (above iCUE's default of 127)
            lines.append(f"{name}={128 + i}")

        cfg_path.write_text("\n".join(lines), encoding="utf-8")
        log.debug("Updated priorities.cfg with %d profiles", len(profiles))
