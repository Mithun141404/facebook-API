"""
Fernet-based encryption helpers for storing Facebook access tokens securely at rest.
Tokens are encrypted before being written to the DB and decrypted when read.
"""
import base64
import logging

from cryptography.fernet import Fernet, InvalidToken

from config import settings

_logger = logging.getLogger(__name__)


def _get_fernet() -> Fernet | None:
    """Return a Fernet instance using the configured key, or None if not set."""
    key = settings.token_encrypt_key
    if not key:
        _logger.warning("TOKEN_ENCRYPT_KEY not set — tokens stored as plaintext.")
        return None
    try:
        return Fernet(key.encode())
    except Exception as exc:
        _logger.error("Invalid TOKEN_ENCRYPT_KEY: %s", exc)
        return None


def encrypt_token(plain_token: str) -> str:
    """Encrypt a plaintext token. Returns ciphertext or plaintext if key not set."""
    fernet = _get_fernet()
    if fernet is None:
        return plain_token
    return fernet.encrypt(plain_token.encode()).decode()


def decrypt_token(stored_token: str) -> str:
    """Decrypt a stored token. Returns plaintext or the raw value if decryption fails."""
    fernet = _get_fernet()
    if fernet is None:
        return stored_token
    try:
        return fernet.decrypt(stored_token.encode()).decode()
    except InvalidToken:
        # Might be an unencrypted legacy token — return as-is
        _logger.warning("Token decryption failed — returning raw value.")
        return stored_token
