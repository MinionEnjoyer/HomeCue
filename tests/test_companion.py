import hashlib
import hmac
import importlib.util
import sys
from pathlib import Path

import pytest
import yaml
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


SPEC = importlib.util.spec_from_file_location(
    "homecue_companion", Path(__file__).parents[1] / "homecue-addon" / "server.py"
)
companion = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = companion
SPEC.loader.exec_module(companion)


def test_addon_manifest_grants_mqtt_service_access():
    manifest_path = Path(__file__).parents[1] / "homecue-addon" / "config.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    assert manifest["hassio_api"] is True
    assert "mqtt:need" in manifest["services"]


def _proof(manager, challenge):
    salt = companion.base64.urlsafe_b64decode(challenge["salt"] + "==")
    key = hashlib.pbkdf2_hmac(
        "sha256", manager.code.replace("-", "").encode(), salt,
        challenge["iterations"], dklen=32,
    )
    proof = hmac.new(key, challenge["challengeId"].encode(), hashlib.sha256).hexdigest()
    return key, proof


def test_pairing_encrypts_bundle_and_rotates_code():
    bundle = {"mqttPort": 1883, "mqttUsername": "addons", "mqttPassword": "secret"}
    manager = companion.PairingManager(bundle)
    original_code = manager.code
    challenge = manager.create_challenge()
    key, proof = _proof(manager, challenge)

    envelope = manager.complete(challenge["challengeId"], proof)
    nonce = companion.base64.urlsafe_b64decode(envelope["nonce"] + "==")
    ciphertext = companion.base64.urlsafe_b64decode(envelope["ciphertext"] + "==")
    plaintext = AESGCM(key).decrypt(nonce, ciphertext, challenge["challengeId"].encode())

    assert companion.json.loads(plaintext) == bundle
    assert manager.code != original_code


def test_pairing_rejects_wrong_or_reused_proof():
    manager = companion.PairingManager({"mqttPassword": "secret"})
    challenge = manager.create_challenge()
    _, proof = _proof(manager, challenge)
    with pytest.raises(ValueError, match="not accepted"):
        manager.complete(challenge["challengeId"], "00" * 32)
    manager.complete(challenge["challengeId"], proof)
    with pytest.raises(ValueError, match="expired"):
        manager.complete(challenge["challengeId"], proof)


def test_expired_code_invalidates_existing_challenges():
    clock = [1000.0]
    manager = companion.PairingManager({}, now=lambda: clock[0])
    challenge = manager.create_challenge()
    _, proof = _proof(manager, challenge)
    clock[0] += companion.PAIRING_TTL + 1
    with pytest.raises(ValueError, match="expired"):
        manager.complete(challenge["challengeId"], proof)
