from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import get_settings

# KMS abstraction.
# In dev the "master" material lives in a local key file that is auto-generated.
# In production this module's load path would be backed by Vault / cloud KMS.
# Each key_version has a 32-byte data key (for AES-256-GCM) and a 32-byte token key (for HMAC).

_KEYFILE = "keys.json"


class KeyManager:
    def __init__(self, key_dir: str) -> None:
        self._dir = Path(key_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / _KEYFILE
        self._keys: dict[int, dict[str, bytes]] = {}
        self._active_version: int = 1
        self._load_or_create()

    def _load_or_create(self) -> None:
        if self._path.exists():
            raw = json.loads(self._path.read_text())
            self._active_version = int(raw["active_version"])
            for v, keys in raw["versions"].items():
                self._keys[int(v)] = {
                    "data": base64.b64decode(keys["data"]),
                    "token": base64.b64decode(keys["token"]),
                }
            return
        # auto-generate version 1 in dev
        self._keys[1] = {"data": os.urandom(32), "token": os.urandom(32)}
        self._active_version = 1
        self._persist()

    def _persist(self) -> None:
        payload = {
            "active_version": self._active_version,
            "versions": {
                str(v): {
                    "data": base64.b64encode(k["data"]).decode(),
                    "token": base64.b64encode(k["token"]).decode(),
                }
                for v, k in self._keys.items()
            },
        }
        self._path.write_text(json.dumps(payload))
        try:
            os.chmod(self._path, 0o600)
        except OSError:
            pass

    @property
    def active_version(self) -> int:
        return self._active_version

    def versions(self) -> list[int]:
        return sorted(self._keys.keys(), reverse=True)

    def data_key(self, version: int) -> bytes:
        return self._keys[version]["data"]

    def token_key(self, version: int) -> bytes:
        return self._keys[version]["token"]

    def rotate(self) -> int:
        new_version = max(self._keys.keys()) + 1
        self._keys[new_version] = {"data": os.urandom(32), "token": os.urandom(32)}
        self._active_version = new_version
        self._persist()
        return new_version


_manager: KeyManager | None = None


def get_key_manager() -> KeyManager:
    global _manager
    if _manager is None:
        _manager = KeyManager(get_settings().key_dir)
    return _manager


def encrypt(plaintext: str, aad: str, version: int | None = None) -> str:
    """AES-256-GCM. aad binds the ciphertext to a record id. Returns base64 'v:nonce:ct'."""
    km = get_key_manager()
    v = km.active_version if version is None else version
    aes = AESGCM(km.data_key(v))
    nonce = os.urandom(12)
    ct = aes.encrypt(nonce, plaintext.encode("utf-8"), aad.encode("utf-8"))
    blob = base64.b64encode(nonce + ct).decode("ascii")
    return f"{v}:{blob}"


def decrypt(ciphertext: str, aad: str) -> str:
    km = get_key_manager()
    v_str, blob = ciphertext.split(":", 1)
    v = int(v_str)
    raw = base64.b64decode(blob)
    nonce, ct = raw[:12], raw[12:]
    aes = AESGCM(km.data_key(v))
    return aes.decrypt(nonce, ct, aad.encode("utf-8")).decode("utf-8")


def token(normalised_value: str, version: int | None = None) -> str:
    """HMAC-SHA256 keyed token for exact matching. Prefixed with key version."""
    km = get_key_manager()
    v = km.active_version if version is None else version
    mac = hmac.new(km.token_key(v), normalised_value.encode("utf-8"), hashlib.sha256)
    return f"{v}:{mac.hexdigest()}"


def token_all_versions(normalised_value: str) -> list[str]:
    """Tokens under active and previous versions, for lookups during rotation."""
    km = get_key_manager()
    out = []
    for v in km.versions():
        mac = hmac.new(km.token_key(v), normalised_value.encode("utf-8"), hashlib.sha256)
        out.append(f"{v}:{mac.hexdigest()}")
    return out


def keyed_blocking_key(normalised_value: str, version: int | None = None) -> str:
    """Keyed (HMAC) blocking key so the DB never stores plaintext name-derived keys."""
    km = get_key_manager()
    v = km.active_version if version is None else version
    mac = hmac.new(km.token_key(v), ("blk:" + normalised_value).encode("utf-8"), hashlib.sha256)
    return mac.hexdigest()[:24]


def last4(value: str) -> str:
    return value[-4:] if len(value) >= 4 else value
