from datetime import UTC, datetime, timedelta
from uuid import UUID

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import BACKEND_DIR, Settings
from app.core.errors import UnauthorizedError


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: UUID, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_expire_minutes)).timestamp()),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> UUID:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Session expired. Please sign in again.") from exc
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Invalid authentication token.") from exc
    if payload.get("type") != "access" or "sub" not in payload:
        raise UnauthorizedError("Invalid authentication token.")
    try:
        return UUID(payload["sub"])
    except ValueError as exc:
        raise UnauthorizedError("Invalid authentication token.") from exc


def resolve_credentials_key(settings: Settings) -> str | None:
    """Return the Fernet key, generating a local one in development.

    Production must set CREDENTIALS_KEY. Tests pass a key explicitly so they
    never write a file. The generated key lives in backend/.credentials_key,
    which is gitignored.
    """
    if settings.credentials_key and settings.credentials_key.strip():
        return settings.credentials_key.strip()
    path = BACKEND_DIR / ".credentials_key"
    if path.is_file():
        stored = path.read_text(encoding="utf-8").strip()
        if stored:
            return stored
    if settings.environment != "development":
        return None
    key = Fernet.generate_key().decode()
    path.write_text(key + "\n", encoding="utf-8")
    return key


class CredentialCipher:
    """Symmetric encryption for provider credentials.

    Used for the Sleeper account token and, later, OAuth tokens.
    """

    def __init__(self, key: str | None):
        self._fernet = Fernet(key.encode()) if key else None

    @property
    def enabled(self) -> bool:
        return self._fernet is not None

    def encrypt(self, plaintext: str) -> str:
        if not self._fernet:
            raise RuntimeError("CREDENTIALS_KEY is not configured; cannot store credentials.")
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        if not self._fernet:
            raise RuntimeError("CREDENTIALS_KEY is not configured; cannot read credentials.")
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise RuntimeError("Stored credentials could not be decrypted.") from exc
