"""Password hashing for the offline auth stand-in (SS-34).

Standard-library PBKDF2-HMAC-SHA256. No third-party crypto. Salts are per-user;
salts and hashes are stored hex-encoded in the seed user file.
"""

import hashlib
import hmac
import os

_ALGO = "sha256"
_ITERATIONS = 100_000
_SALT_BYTES = 16


def new_salt() -> str:
    return os.urandom(_SALT_BYTES).hex()


def hash_password(password: str, salt_hex: str) -> str:
    salt = bytes.fromhex(salt_hex)
    digest = hashlib.pbkdf2_hmac(_ALGO, password.encode("utf-8"), salt, _ITERATIONS)
    return digest.hex()


def verify_password(password: str, salt_hex: str, expected_hash_hex: str) -> bool:
    try:
        actual = hash_password(password, salt_hex)
    except ValueError:
        return False
    return hmac.compare_digest(actual, expected_hash_hex)
