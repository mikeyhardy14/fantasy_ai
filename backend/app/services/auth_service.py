from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import ConflictError, UnauthorizedError
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User
from app.repositories import UserRepository


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings):
        self.session = session
        self.settings = settings
        self.users = UserRepository(session)

    async def register(self, *, email: str, name: str, password: str) -> tuple[User, str]:
        if await self.users.get_by_email(email):
            raise ConflictError("An account with that email already exists.")
        user = await self.users.create(
            email=email, name=name.strip(), hashed_password=hash_password(password)
        )
        await self.session.commit()
        return user, create_access_token(user.id, self.settings)

    async def login(self, *, email: str, password: str) -> tuple[User, str]:
        user = await self.users.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise UnauthorizedError("Incorrect email or password.")
        return user, create_access_token(user.id, self.settings)

    async def get_user(self, user_id: UUID) -> User | None:
        return await self.users.get_by_id(user_id)
