"""
Your Company Virtual Office - Key Encryption

Encrypts API keys at rest using Windows DPAPI (Data Protection API).
Only the Windows user who encrypted the keys can decrypt them.

On first boot: reads plaintext from API Keys/*.txt, encrypts, stores
encrypted versions in data/keys.enc, deletes plaintext files.

On Linux/dev: falls back to base64 encoding (not secure - dev only).
"""

import base64
import json
import sys
from pathlib import Path


def _get_data_dir() -> Path:
    """Return the runtime data dir - works in both dev and frozen EXE."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "data"
    return Path(__file__).resolve().parent.parent / "data"


def _get_key_dir() -> Path:
    """Return the runtime API Keys dir - works in both dev and frozen EXE."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "API Keys"
    return Path(__file__).resolve().parent.parent / "API Keys"


def _get_enc_path() -> Path:
    return _get_data_dir() / "keys.enc"


_IS_WINDOWS = False
try:
    import win32crypt
    _IS_WINDOWS = True
except ImportError:
    pass


def _dpapi_encrypt(data: bytes) -> bytes:
    """Encrypt bytes with Windows DPAPI."""
    if _IS_WINDOWS:
        _, encrypted = win32crypt.CryptProtectData(
            data, "YourCoVO", None, None, None, 0
        )
        return encrypted
    # Fallback: base64 (dev only, not secure)
    return base64.b64encode(data)


def _dpapi_decrypt(data: bytes) -> bytes:
    """Decrypt bytes with Windows DPAPI."""
    if _IS_WINDOWS:
        _, decrypted = win32crypt.CryptUnprotectData(data, None, None, None, 0)
        return decrypted
    # Fallback: base64
    return base64.b64decode(data)


def store_keys(keys: dict):
    """Encrypt and store API keys. keys = {name: value}."""
    data_dir = _get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    enc_path = _get_enc_path()
    payload = json.dumps(keys).encode("utf-8")
    encrypted = _dpapi_encrypt(payload)
    # Store as base64 text so it's filesystem-safe
    enc_path.write_text(base64.b64encode(encrypted).decode("ascii"))


def load_keys() -> dict:
    """Load and decrypt stored API keys. Returns {name: value}."""
    enc_path = _get_enc_path()
    if enc_path.exists():
        try:
            encrypted = base64.b64decode(enc_path.read_text())
            decrypted = _dpapi_decrypt(encrypted)
            return json.loads(decrypted.decode("utf-8"))
        except Exception:
            pass

    # No encrypted store - try plaintext migration
    return _migrate_plaintext()


def _migrate_plaintext() -> dict:
    """Read plaintext API keys, encrypt, store, return.

    On Windows: also deletes the plaintext files after encryption.
    On Linux: keeps plaintext (dev environment).
    """
    KEY_MAP = {
        "Claude API": "ANTHROPIC_API_KEY",
        "OpenAI API": "OPENAI_API_KEY",
        "Gemini API": "GOOGLE_API_KEY",
        "FRED API":   "FRED_API_KEY",
    }

    key_dir = _get_key_dir()
    keys = {}
    found_any = False

    for filename, env_name in KEY_MAP.items():
        txt_path = key_dir / f"{filename}.txt"
        if txt_path.exists():
            val = txt_path.read_text().strip()
            if val:
                keys[env_name] = val
                found_any = True

    if found_any:
        # Encrypt and store
        store_keys(keys)

        # On Windows, remove plaintext files
        if _IS_WINDOWS:
            for filename in KEY_MAP:
                txt_path = key_dir / f"{filename}.txt"
                if txt_path.exists():
                    txt_path.unlink()

    return keys


def is_encrypted() -> bool:
    """Check if keys are stored in encrypted form."""
    return _get_enc_path().exists()


def has_plaintext() -> bool:
    """Check if plaintext key files still exist (security concern)."""
    KEY_MAP = {
        "Claude API": "ANTHROPIC_API_KEY",
        "OpenAI API": "OPENAI_API_KEY",
        "Gemini API": "GOOGLE_API_KEY",
        "FRED API":   "FRED_API_KEY",
    }
    key_dir = _get_key_dir()
    for filename in KEY_MAP:
        if (key_dir / f"{filename}.txt").exists():
            return True
    return False
