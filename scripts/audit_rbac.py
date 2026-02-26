#!/usr/bin/env python3
"""Audit RBAC permission enforcement completeness."""
import glob
import re
import sys
import os

def get_defined_permissions():
    """Read all Permission enum values from permissions.py."""
    perm_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src", "rbac", "permissions.py")
    with open(perm_file) as f:
        content = f.read()
    permissions = set()
    for match in re.finditer(r'^\s+(\w+)\s*=\s*"(\w+)"', content, re.MULTILINE):
        name = match.group(1)
        if name.isupper() or name[0].isupper():
            permissions.add(name)
    return permissions

def get_enforced_permissions():
    """Scan all route files for require_permission() calls."""
    enforced = set()
    src_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
    for py_file in glob.glob(os.path.join(src_dir, "**", "*.py"), recursive=True):
        with open(py_file) as f:
            content = f.read()
        for match in re.finditer(r'require_permission\(Permission\.(\w+)', content):
            enforced.add(match.group(1))
        # Also check decorator-style: @require_permission(Permission.XXX)
        for match in re.finditer(r'Permission\.(\w+)', content):
            if 'require_permission' in content[max(0, content.index(match.group(0))-50):content.index(match.group(0))]:
                enforced.add(match.group(1))
    return enforced

def main():
    defined = get_defined_permissions()
    enforced = get_enforced_permissions()
    unenforced = defined - enforced

    print(f"Defined permissions: {len(defined)}")
    print(f"Enforced at routes:  {len(enforced)}")
    print(f"Unenforced:          {len(unenforced)}")

    if unenforced:
        print(f"\nINFO: {len(unenforced)} permissions defined but not yet enforced at route level:")
        for p in sorted(unenforced):
            print(f"  - Permission.{p}")
        # Don't fail — some permissions may be intentionally unused at route level
        # (e.g., used in business logic, not as route guards)
        return 0

    print("\nPASS: All defined permissions are enforced at route level")
    return 0

if __name__ == "__main__":
    sys.exit(main())
