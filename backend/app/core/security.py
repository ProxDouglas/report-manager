import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError

PASSWORD_MIN_LENGTH = 12
password_hasher = PasswordHasher()


def validate_password_policy(password: str) -> None:
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"A senha deve possuir pelo menos {PASSWORD_MIN_LENGTH} caracteres.")
    if password.lower() == password or password.upper() == password:
        raise ValueError("A senha deve combinar letras maiúsculas e minúsculas.")
    if not any(character.isdigit() for character in password):
        raise ValueError("A senha deve possuir pelo menos um número.")


def hash_password(password: str) -> str:
    validate_password_policy(password)
    return password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (InvalidHash, VerificationError, VerifyMismatchError):
        return False


def new_session_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def constant_time_equals(left: str, right: str) -> bool:
    return hmac.compare_digest(left, right)
