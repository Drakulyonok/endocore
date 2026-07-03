"""Encrypted file storage for :class:`~endocore.orm.fields.FileField`.

Files are written to any directory you choose, **encrypted at rest** with
AES-256-GCM (authenticated encryption). If the storage directory leaks, the
files cannot be read or restored without the separate encryption key — the
plaintext never touches the disk.

Design / security notes:
- Real, vetted crypto only: ``cryptography``'s AES-GCM (no home-grown ciphers).
- A fresh random 96-bit nonce per file; the GCM tag authenticates the data.
- The stored relative path is bound into the ciphertext as additional
  authenticated data (AAD), so a file cannot be swapped or renamed undetected.
- Filenames are random (uuid4) — they leak nothing about the content.
- The key lives in config / ``ENDOCORE_FILE_KEY`` env, never with the files.
- Fail closed: using a FileField without a configured key raises, so nothing is
  ever written in plaintext by accident.
"""

from __future__ import annotations

import base64
import os
import uuid
from pathlib import Path

from endocore.orm.exceptions import ConfigurationError, ORMError

_MAGIC = b"ENC1"
_NONCE_BYTES = 12
_KEY_BYTES = 32  # AES-256


class StorageError(ORMError):
    """A file could not be stored, read, or (most importantly) decrypted."""


def generate_key() -> str:
    """Return a fresh base64 url-safe 256-bit key. Store it somewhere safe."""
    return base64.urlsafe_b64encode(os.urandom(_KEY_BYTES)).decode("ascii")


def _coerce_key(key: str | bytes) -> bytes:
    if isinstance(key, bytes):
        raw = key
    else:
        for decoder in (base64.urlsafe_b64decode, bytes.fromhex):
            try:
                raw = decoder(key)
                break
            except Exception:  # noqa: BLE001 - try the next encoding
                raw = None
        else:
            raw = None
        if raw is None:
            raw = key.encode("utf-8")
    if len(raw) != _KEY_BYTES:
        raise ConfigurationError(
            f"file encryption key must be {_KEY_BYTES} bytes (got {len(raw)}); "
            "use endocore.orm.generate_key()"
        )
    return raw


class EncryptedFileSystemStorage:
    """Stores encrypted blobs under ``root`` (which may be any folder)."""

    def __init__(self, root: str | Path, key: str | bytes) -> None:
        self.root = Path(root).resolve()
        self._key = _coerce_key(key)

    # -- helpers ----------------------------------------------------------

    def _cipher(self):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        return AESGCM(self._key)

    def _abs(self, rel_key: str) -> Path:
        """Resolve a stored key to an absolute path, refusing traversal."""
        target = (self.root / rel_key).resolve()
        if self.root not in target.parents and target != self.root:
            raise StorageError(f"path escapes storage root: {rel_key!r}")
        return target

    def _safe_subdir(self, upload_to: str) -> str:
        parts = [p for p in Path(upload_to or "").parts if p not in ("", ".")]
        if any(p == ".." for p in parts) or (upload_to and Path(upload_to).is_absolute()):
            raise StorageError(f"unsafe upload_to: {upload_to!r}")
        return "/".join(parts)

    # -- API --------------------------------------------------------------

    def save(self, upload_to: str, content: bytes) -> str:
        """Encrypt ``content`` and write it; return the stored relative key."""
        if not isinstance(content, (bytes, bytearray)):
            raise StorageError("file content must be bytes")
        subdir = self._safe_subdir(upload_to)
        rel_key = f"{subdir}/{uuid.uuid4().hex}.enc" if subdir else f"{uuid.uuid4().hex}.enc"

        nonce = os.urandom(_NONCE_BYTES)
        ciphertext = self._cipher().encrypt(nonce, bytes(content), rel_key.encode("utf-8"))

        target = self._abs(rel_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "wb") as fh:
            fh.write(_MAGIC + nonce + ciphertext)
        return rel_key

    def open(self, rel_key: str) -> bytes:
        """Read and decrypt the file at ``rel_key`` (raises if tampered/missing)."""
        target = self._abs(rel_key)
        try:
            blob = target.read_bytes()
        except FileNotFoundError:
            raise StorageError(f"file not found: {rel_key!r}") from None
        if blob[:4] != _MAGIC:
            raise StorageError(f"not an EndoCore encrypted file: {rel_key!r}")
        nonce = blob[4 : 4 + _NONCE_BYTES]
        ciphertext = blob[4 + _NONCE_BYTES :]
        try:
            return self._cipher().decrypt(nonce, ciphertext, rel_key.encode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - InvalidTag etc.
            raise StorageError(f"cannot decrypt {rel_key!r} (wrong key or tampered)") from exc

    def delete(self, rel_key: str) -> None:
        self._abs(rel_key).unlink(missing_ok=True)

    def exists(self, rel_key: str) -> bool:
        return self._abs(rel_key).exists()

    def size(self, rel_key: str) -> int:
        return self._abs(rel_key).stat().st_size

    def path(self, rel_key: str) -> Path:
        return self._abs(rel_key)


_storages: dict[str, EncryptedFileSystemStorage] = {}


def configure_storage(root: str | Path, *, key: str | bytes | None = None,
                      alias: str = "default") -> EncryptedFileSystemStorage:
    """Register the encrypted storage for ``alias`` (default used by FileField).

    ``key`` may be passed directly or via the ``ENDOCORE_FILE_KEY`` env var.
    """
    key = key or os.environ.get("ENDOCORE_FILE_KEY")
    if not key:
        raise ConfigurationError(
            "encrypted file storage requires a key (pass key=... or set "
            "ENDOCORE_FILE_KEY); generate one with endocore.orm.generate_key()"
        )
    storage = EncryptedFileSystemStorage(root, key)
    _storages[alias] = storage
    return storage


def get_storage(alias: str = "default") -> EncryptedFileSystemStorage:
    try:
        return _storages[alias]
    except KeyError:
        raise ConfigurationError(
            f"no file storage configured for alias {alias!r}; call "
            "endocore.orm.configure_storage(root=..., key=...) first"
        ) from None
