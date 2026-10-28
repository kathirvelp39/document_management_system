
from fastapi import Depends, HTTPException, status

from app.models import User
from app.routes.auth import get_current_user


ROLES = {"admin", "manager", "user", "viewer"}


def require_roles(*allowed_roles: str):
    """Create a reusable dependency to validate user roles."""

    if not allowed_roles:
        raise ValueError("At least one allowed role must be specified")

    invalid_roles = set(allowed_roles) - ROLES

    if invalid_roles:
        raise ValueError(f"Invalid roles: {sorted(invalid_roles)}")

    def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )

        return current_user

    return role_checker


# Admin-only access
require_admin = require_roles("admin")

# Admin and Manager access
require_manager = require_roles("admin", "manager")

# Admin, Manager, and User access
require_user = require_roles("admin", "manager", "user")

# All authenticated roles
require_viewer = require_roles("admin", "manager", "user", "viewer")
