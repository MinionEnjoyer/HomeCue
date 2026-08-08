"""Home Assistant companion for encrypted, one-time HomeCue provisioning."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PAIRING_PORT = 8098
INGRESS_PORT = 8099
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
PAIRING_TTL = 10 * 60
PBKDF2_ROUNDS = 200_000


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


@dataclass
class Challenge:
    salt: bytes
    expires_at: float
    failures: int = 0


class PairingManager:
    """Owns the rotating pairing code and short-lived challenges."""

    def __init__(self, bundle: dict, now: Callable[[], float] = time.time) -> None:
        self.bundle = bundle
        self.now = now
        self.code = self._new_code()
        self.code_expires_at = now() + PAIRING_TTL
        self.challenges: dict[str, Challenge] = {}
        self.lock = threading.Lock()

    @staticmethod
    def _new_code() -> str:
        raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(16))
        return "-".join(raw[index:index + 4] for index in range(0, 16, 4))

    def _rotate_if_needed(self) -> None:
        if self.now() >= self.code_expires_at:
            self.code = self._new_code()
            self.code_expires_at = self.now() + PAIRING_TTL
            self.challenges.clear()

    def create_challenge(self) -> dict:
        with self.lock:
            self._rotate_if_needed()
            challenge_id = secrets.token_urlsafe(24)
            salt = secrets.token_bytes(16)
            self.challenges[challenge_id] = Challenge(salt, self.code_expires_at)
            return {
                "challengeId": challenge_id,
                "salt": _b64(salt),
                "expiresIn": max(0, int(self.code_expires_at - self.now())),
                "iterations": PBKDF2_ROUNDS,
            }

    def complete(self, challenge_id: str, proof: str) -> dict:
        with self.lock:
            self._rotate_if_needed()
            challenge = self.challenges.get(challenge_id)
            if challenge is None or self.now() >= challenge.expires_at:
                raise ValueError("Pairing challenge expired")
            if challenge.failures >= 5:
                del self.challenges[challenge_id]
                raise ValueError("Too many pairing attempts")

            key = hashlib.pbkdf2_hmac(
                "sha256", self.code.replace("-", "").upper().encode(), challenge.salt,
                PBKDF2_ROUNDS, dklen=32,
            )
            expected = hmac.new(key, challenge_id.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, proof.lower()):
                challenge.failures += 1
                raise ValueError("Pairing code was not accepted")

            nonce = secrets.token_bytes(12)
            ciphertext = AESGCM(key).encrypt(
                nonce, json.dumps(self.bundle, separators=(",", ":")).encode(),
                challenge_id.encode(),
            )
            del self.challenges[challenge_id]
            self.code = self._new_code()
            self.code_expires_at = self.now() + PAIRING_TTL
            return {"nonce": _b64(nonce), "ciphertext": _b64(ciphertext)}

    def display(self) -> tuple[str, int]:
        with self.lock:
            self._rotate_if_needed()
            return self.code, max(0, int(self.code_expires_at - self.now()))


class PairingHandler(BaseHTTPRequestHandler):
    manager: PairingManager

    def _json(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._json(200, {"ready": True})
        elif self.path == "/api/challenge":
            self._json(200, self.manager.create_challenge())
        else:
            self._json(404, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/pair":
            self._json(404, {"error": "Not found"})
            return
        try:
            length = min(int(self.headers.get("Content-Length", "0")), 4096)
            body = json.loads(self.rfile.read(length))
            result = self.manager.complete(str(body["challengeId"]), str(body["proof"]))
            self._json(200, result)
        except (KeyError, TypeError, json.JSONDecodeError):
            self._json(400, {"error": "Invalid pairing request"})
        except ValueError as error:
            self._json(403, {"error": str(error)})

    def log_message(self, _format: str, *_args: object) -> None:
        return


class IngressHandler(BaseHTTPRequestHandler):
    manager: PairingManager

    def do_GET(self) -> None:  # noqa: N802
        code, seconds = self.manager.display()
        html = f"""<!doctype html><html><head><meta name=viewport content='width=device-width'>
<style>body{{font:16px system-ui;background:#07101c;color:#e9f2ff;display:grid;place-items:center;min-height:90vh}}
main{{max-width:560px;padding:38px;background:#0d1929;border:1px solid #24384f;border-radius:18px;text-align:center}}
h1{{margin-top:0}}code{{display:block;font-size:26px;letter-spacing:.12em;color:#5de0ff;margin:28px 0}}
p{{color:#9bb0c7;line-height:1.6}}</style></head><body><main><h1>Pair HomeCue</h1>
<p>Open HomeCue on Windows, choose <strong>Automatic setup</strong>, and enter this one-time code.</p>
<code>{code}</code><p>The code expires in about {max(1, seconds // 60)} minute(s) and changes after it is used.</p>
</main></body></html>""".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(html)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def build_bundle() -> dict:
    return {
        "mqttPort": int(os.environ.get("HOMECUE_MQTT_PORT", "1883")),
        "mqttUsername": os.environ.get("HOMECUE_MQTT_USERNAME", ""),
        "mqttPassword": os.environ.get("HOMECUE_MQTT_PASSWORD", ""),
        "mqttTls": os.environ.get("HOMECUE_MQTT_TLS", "false").lower() == "true",
        "discoveryPrefix": "homeassistant",
    }


def main() -> None:
    manager = PairingManager(build_bundle())
    PairingHandler.manager = manager
    IngressHandler.manager = manager
    ingress = ThreadingHTTPServer(("0.0.0.0", INGRESS_PORT), IngressHandler)
    threading.Thread(target=ingress.serve_forever, daemon=True).start()
    print("HomeCue companion ready; open its Home Assistant Web UI for a pairing code", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PAIRING_PORT), PairingHandler).serve_forever()


if __name__ == "__main__":
    main()
