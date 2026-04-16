"""Home Assistant REST API client for controlling lights."""

from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error

log = logging.getLogger(__name__)


class HomeAssistantClient:
    """Calls Home Assistant REST API to control light entities."""

    def __init__(self, url: str, token: str) -> None:
        self._url = url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def set_light_color(
        self, entity_id: str, r: int, g: int, b: int, brightness: int
    ) -> None:
        """Turn on a light (or light group) with the given RGB color and brightness."""
        data = {
            "entity_id": entity_id,
            "rgb_color": [r, g, b],
            "brightness": brightness,
        }
        self._call_service("light/turn_on", data)

    def turn_off_lights(self, entity_id: str) -> None:
        """Turn off a light or light group entity."""
        data = {"entity_id": entity_id}
        self._call_service("light/turn_off", data)

    def _call_service(self, service: str, data: dict) -> None:
        """POST to /api/services/<domain>/<service>."""
        url = f"{self._url}/api/services/{service}"
        body = json.dumps(data).encode("utf-8")

        req = urllib.request.Request(url, data=body, headers=self._headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status >= 400:
                    log.error("HA API error %d for %s", resp.status, service)
        except urllib.error.HTTPError as e:
            log.error("HA API HTTP %d for %s: %s", e.code, service, e.reason)
        except urllib.error.URLError as e:
            log.error("HA API connection error for %s: %s", service, e.reason)
        except Exception:
            log.exception("HA API unexpected error for %s", service)
