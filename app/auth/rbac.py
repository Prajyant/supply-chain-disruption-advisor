"""Role-based access control (RBAC) module."""
from enum import Enum
from typing import Callable, Optional
from functools import wraps
from fastapi import HTTPException, status


class Role(str, Enum):
    """User roles for RBAC."""
    ADMIN = "admin"
    BUYER = "buyer"
    VIEWER = "viewer"


# Permission matrix
PERMISSIONS = {
    Role.ADMIN: {
        "ingest": True,
        "view_risks": True,
        "chat": True,
        "graph": True,
        "settings": True,
    },
    Role.BUYER: {
        "ingest": True,
        "view_risks": True,
        "chat": True,
        "graph": True,
        "settings": False,
    },
    Role.VIEWER: {
        "ingest": False,
        "view_risks": True,
        "chat": True,
        "graph": True,
        "settings": False,
    },
}


def check_permission(role: Role, permission: str) -> bool:
    """Check if a role has a specific permission.

    Args:
        role: The user's role
        permission: The permission to check

    Returns:
        True if the role has the permission
    """
    role_perms = PERMISSIONS.get(role, {})
    return role_perms.get(permission, False)


def require_role(*allowed_roles: Role) -> Callable:
    """Decorator to require specific roles for access.

    Args:
        *allowed_roles: Roles that are allowed access

    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get user role from kwargs (set by auth dependency)
            user_role = kwargs.get("user_role")
            if not user_role:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            if user_role not in allowed_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required roles: {[r.value for r in allowed_roles]}",
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_permission(permission: str) -> Callable:
    """Decorator to require a specific permission.

    Args:
        permission: The permission required

    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get user role from kwargs (set by auth dependency)
            user_role = kwargs.get("user_role")
            if not user_role:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            if not check_permission(user_role, permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required permission: {permission}",
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator


# Sample users database (in production, use a real database)
# Using simple password comparison for demo - in production use bcrypt
USERS = {
    "admin": {
        "id": "1",
        "username": "admin",
        "password": "password",
        "role": Role.ADMIN,
    },
    "buyer": {
        "id": "2",
        "username": "buyer",
        "password": "password",
        "role": Role.BUYER,
    },
    "viewer": {
        "id": "3",
        "username": "viewer",
        "password": "password",
        "role": Role.VIEWER,
    },
}


def get_user(username: str) -> Optional[dict]:
    """Get a user by username.

    Args:
        username: The username

    Returns:
        User dictionary or None
    """
    return USERS.get(username)


def authenticate_user(username: str, password: str) -> Optional[dict]:
    """Authenticate a user.

    Args:
        username: The username
        password: The password

    Returns:
        User dictionary if authenticated, None otherwise
    """
    user = get_user(username)
    if not user:
        return None

    # Simple password comparison for demo
    if user.get("password") != password:
        return None

    return user
