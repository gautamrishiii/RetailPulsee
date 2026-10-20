ROLE_PERMISSIONS = {
    "Admin": {"*"},
    "Analyst": {
        "overview",
        "inventory",
        "forecasting",
        "segmentation",
    },
    "Viewer": {
        "overview",
        "inventory",
        "forecasting",
        "segmentation",
    },
}

def has_permission(user, permission):
    """Check whether a user role grants a specific permission."""
    if not user or not isinstance(user, dict):
        return False

    role = user.get("role")
    permissions = ROLE_PERMISSIONS.get(role, set())
    return "*" in permissions or permission in permissions

def require_permission(user, permission):
    """Raise an error if a user lacks the requested permission."""
    if not has_permission(user, permission):
        raise PermissionError("You do not have permission to perform this action.")
    return True
