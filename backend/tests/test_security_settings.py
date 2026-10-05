import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.rate_limit import RateLimited, RateLimiter
from app.schemas.auth import RegisterRequest


def test_production_refuses_a_public_jwt_secret():
    with pytest.raises(ValidationError):
        Settings(environment="production", jwt_secret="")
    with pytest.raises(ValidationError):
        Settings(environment="production", jwt_secret="short-secret")
    ok = Settings(environment="production", jwt_secret="x" * 40)
    assert ok.jwt_secret == "x" * 40
    assert Settings(environment="development", jwt_secret="").jwt_secret == "change-me-in-production"


def test_register_rejects_passwords_bcrypt_cannot_hash():
    with pytest.raises(ValidationError):
        RegisterRequest(email="a@example.com", name="A", password="é" * 40)


def test_rate_limiter_blocks_after_the_limit():
    limiter = RateLimiter()
    for _ in range(3):
        limiter.hit("k", limit=3, window_seconds=60)
    with pytest.raises(RateLimited):
        limiter.hit("k", limit=3, window_seconds=60)
