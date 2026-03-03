"""
Shared UI role constants — single source of truth for page-level access control.

Derives from the canonical RBAC role definitions in src/rbac/roles.py.
"""

from rbac.roles import PLATFORM_ROLES, FIRM_ROLES, CLIENT_ROLES, Role

# Admin UI roles: platform-level roles that can access /admin pages.
# Uses the string values so page-auth helpers can compare against raw JWT claims.
# Includes legacy alias "admin" for backward compatibility.
ADMIN_UI_ROLES = frozenset(r.value for r in PLATFORM_ROLES) | {"admin"}

# CPA UI roles: firm-level roles for /cpa pages.
# Includes legacy aliases for backward compatibility.
CPA_UI_ROLES = frozenset(r.value for r in FIRM_ROLES) | {"cpa", "preparer", "accountant"}

# Client UI roles: client-level roles for /client pages.
# Includes legacy aliases for backward compatibility.
CLIENT_UI_ROLES = frozenset(r.value for r in CLIENT_ROLES) | {"client", "taxpayer", "user"}
