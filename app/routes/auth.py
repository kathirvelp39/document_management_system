
import logging

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from redis.exceptions import RedisError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.redis_client import redis_client
from app.schemas import TokenResponse, UserLogin, UserRegister, UserResponse
from app.security import (
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    hash_password,
    verify_password,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])
bearer_scheme = HTTPBearer()

LOGIN_RATE_LIMIT = 5
LOGIN_RATE_WINDOW_SECONDS = 60


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Validate JWT and return the active authenticated user."""
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )
        username = payload.get("sub")

        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    user = db.scalar(select(User).where(User.username == username))

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    user_data: UserRegister,
    db: Session = Depends(get_db),
):
    """Register a new user."""
    existing_user = db.scalar(
        select(User).where(
            or_(
                User.username == user_data.username,
                User.email == str(user_data.email),
            )
        )
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already registered",
        )

    user = User(
        username=user_data.username,
        email=str(user_data.email),
        hashed_password=hash_password(user_data.password),
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        logger.exception("User registration failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to register user",
        ) from None

    return user


@router.post("/login", response_model=TokenResponse)
def login_user(
    login_data: UserLogin,
    request: Request,
    db: Session = Depends(get_db),
):
    """Authenticate a user with Redis-backed login rate limiting."""
    client_ip = request.client.host if request.client else "unknown"
    rate_limit_key = f"login_attempts:{client_ip}"

    try:
        attempts = redis_client.incr(rate_limit_key)

        if attempts == 1:
            redis_client.expire(rate_limit_key, LOGIN_RATE_WINDOW_SECONDS)

        if attempts > LOGIN_RATE_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts. Try again in 60 seconds.",
            )

    except RedisError:
        logger.exception("Redis unavailable during login rate limiting")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Login service temporarily unavailable",
        ) from None

    user = db.scalar(
        select(User).where(User.username == login_data.username)
    )

    if (
        user is None
        or not verify_password(login_data.password, user.hashed_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    try:
        redis_client.delete(rate_limit_key)
    except RedisError:
        logger.warning("Could not reset login attempts for IP %s", client_ip)

    return {
        "access_token": create_access_token(user.username),
        "token_type": "bearer",
    }


@router.get("/me", response_model=UserResponse)
def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    """Return the authenticated user's profile."""
    return current_user
