from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from fastapi import Depends
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, UnauthorizedError
from app.core.security import decode_token, hash_api_key
from app.database import async_session
from app.models.api_key import ApiKey
from app.models.stock import Stock
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    api_key: str | None = Depends(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> User:
    # Try API key auth first (if header starts with sp_)
    if api_key and api_key.startswith("sp_"):
        return await _authenticate_api_key(api_key, db)

    # Fall back to JWT
    if token:
        return await _authenticate_jwt(token, db)

    raise UnauthorizedError()


async def _authenticate_jwt(token: str, db: AsyncSession) -> User:
    """Authenticate via JWT Bearer token."""
    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        raise UnauthorizedError()

    user_id = payload.get("sub")
    if user_id is None:
        raise UnauthorizedError()

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise UnauthorizedError()

    return user


async def _authenticate_api_key(raw_key: str, db: AsyncSession) -> User:
    """Authenticate via X-API-Key header."""
    key_hash = hash_api_key(raw_key)
    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash)
    )
    api_key_obj = result.scalar_one_or_none()

    if api_key_obj is None or not api_key_obj.is_active:
        raise UnauthorizedError()

    if api_key_obj.expires_at and api_key_obj.expires_at < datetime.now(timezone.utc):
        raise UnauthorizedError()

    # Update last_used_at
    api_key_obj.last_used_at = datetime.now(timezone.utc)

    # Load the user
    user_result = await db.execute(select(User).where(User.id == api_key_obj.user_id))
    user = user_result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise UnauthorizedError()

    return user


async def get_stock_by_ticker(ticker: str, db: AsyncSession) -> Stock:
    """Look up a stock by ticker (case-insensitive). Raises NotFoundError if missing."""
    from sqlalchemy import func

    result = await db.execute(select(Stock).where(func.upper(Stock.ticker) == ticker.upper()))
    stock = result.scalar_one_or_none()
    if not stock:
        raise NotFoundError(f"Stock {ticker} not found")
    return stock


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        from app.core.exceptions import ForbiddenError

        raise ForbiddenError()
    return user
