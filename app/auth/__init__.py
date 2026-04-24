"""Authentication and authorization module."""
from app.auth.jwt_handler import JWTHandler
from app.auth.rbac import Role, check_permission, require_role

__all__ = ["JWTHandler", "Role", "check_permission", "require_role"]
