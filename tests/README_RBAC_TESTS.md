# RBAC Permission System Test Suite

Comprehensive test suite for the Role-Based Access Control (RBAC) and feature access control systems.

## Overview

This test suite provides complete coverage for:
- Permission definitions and role assignments
- Permission checking logic
- Feature access control and subscription tier enforcement
- Security boundaries and access control
- Performance testing
- Regression testing for known bugs

## Test Files

### `test_rbac_permissions.py`
Tests the core RBAC permission system:
- **Permission Definitions**: Validates permission structure, naming conventions, and immutability
- **Role Permissions**: Verifies correct permission assignments for each role
- **Permission Checking**: Tests ownership, assignment, and permission checking logic
- **Security Boundaries**: Ensures proper isolation between users, tenants, and roles
- **Regression Tests**: Verifies fixes for known bugs (e.g., FIRM_CLIENT edit permission)
- **Performance Tests**: Ensures permission checks are fast (<1ms)

**Test Categories:**
- `TestPermissionDefinitions` - Permission structure validation
- `TestRolePermissions` - Role permission assignments
- `TestPermissionChecking` - Permission checking logic
- `TestPermissionEnforcement` - Decorator integration tests
- `TestSecurityBoundaries` - Security isolation tests
- `TestRegressions` - Bug fix verification
- `TestPerformance` - Performance benchmarks

### `test_feature_access.py`
Tests the feature access control system:
- **Feature Definitions**: Validates feature structure and categorization
- **Subscription Tiers**: Tests tier-based access control
- **Feature Flags**: Tests feature flag enforcement
- **Role Restrictions**: Verifies role-based feature restrictions
- **User Features**: Tests `get_user_features()` and category filtering
- **Admin Management**: Tests enabling/disabling features
- **Integration**: End-to-end feature access scenarios

**Test Categories:**
- `TestFeatureDefinitions` - Feature structure validation
- `TestFeatureAccessChecking` - Access checking logic
- `TestGetUserFeatures` - User feature retrieval
- `TestGetFeaturesByCategory` - Category filtering
- `TestAdminFeatureManagement` - Admin feature controls
- `TestFeatureAccessIntegration` - Integration scenarios
- `TestFeatureAccessPerformance` - Performance benchmarks

## Running Tests

### Run All RBAC Tests
```bash
./scripts/run_rbac_tests.sh
```

This script:
- Runs all RBAC and feature access tests
- Generates coverage reports (terminal + HTML)
- Provides detailed output with color coding
- Exits with error code if any test fails

### Run Specific Test Files
```bash
# Run only permission tests
pytest tests/test_rbac_permissions.py -v

# Run only feature access tests
pytest tests/test_feature_access.py -v

# Run specific test class
pytest tests/test_rbac_permissions.py::TestRolePermissions -v

# Run specific test
pytest tests/test_rbac_permissions.py::TestRegressions::test_firm_client_edit_return_bug_fix -v
```

### Run with Coverage
```bash
# Terminal coverage report
pytest tests/test_rbac_permissions.py --cov=src/rbac --cov-report=term-missing

# HTML coverage report
pytest tests/test_rbac_permissions.py --cov=src/rbac --cov-report=html
# Open htmlcov/index.html in browser
```

### Run in Watch Mode (for development)
```bash
pytest-watch tests/test_rbac_permissions.py
```

## Test Fixtures

The test suite includes pre-configured fixtures for common scenarios:

### User Contexts
- `platform_admin_context` - Platform administrator
- `partner_context` - Tenant partner (admin)
- `staff_context` - Staff member (CPA)
- `firm_client_context` - Firm client
- `direct_client_context` - Direct client (no firm)

### Tenants
- `free_tier_tenant` - Free subscription tier
- `starter_tier_tenant` - Starter subscription tier
- `professional_tier_tenant` - Professional subscription tier
- `enterprise_tier_tenant` - Enterprise subscription tier

### Usage Example
```python
def test_example(platform_admin_context, free_tier_tenant):
    """Test using fixtures"""
    # platform_admin_context is pre-configured
    assert platform_admin_context.role.name == 'PLATFORM_ADMIN'

    # free_tier_tenant has appropriate features enabled
    assert free_tier_tenant.subscription_tier == SubscriptionTier.FREE
```

## Key Test Scenarios

### 1. FIRM_CLIENT Edit Permission (Regression Test)
```python
def test_firm_client_edit_return_bug_fix():
    """
    CRITICAL: Verifies FIRM_CLIENT can edit own returns.
    This was a production bug that blocked clients from editing draft returns.
    """
    client_perms = get_permissions_for_role('FIRM_CLIENT')
    assert Permissions.CLIENT_RETURNS_EDIT_SELF in client_perms
```

### 2. Platform Admin All-Access
```python
def test_platform_admin_has_all_permissions():
    """Platform admin should have all 95 permissions"""
    admin_perms = get_permissions_for_role('PLATFORM_ADMIN')
    assert len(admin_perms) == 95
```

### 3. Subscription Tier Enforcement
```python
@patch('src.rbac.feature_access_control.get_tenant_persistence')
def test_free_tier_blocked_from_ai_chat(mock_persistence, staff_context, free_tenant):
    """Free tier should NOT have AI Chat (requires Professional)"""
    mock_persistence.return_value.get_tenant.return_value = free_tenant
    access = check_feature_access(Features.AI_CHAT, staff_context)

    assert not access["allowed"]
    assert access["upgrade_tier"] == "professional"
```

### 4. Ownership-Based Access
```python
def test_client_cannot_view_other_client_data():
    """Clients should only see their own data"""
    client_perms = get_permissions_for_role('FIRM_CLIENT')

    # Can view own data
    assert has_permission(
        client_perms,
        Permissions.CLIENT_RETURNS_VIEW_SELF,
        user_id="client-001",
        resource_owner_id="client-001"
    )

    # Cannot view other's data
    assert not has_permission(
        client_perms,
        Permissions.CLIENT_RETURNS_VIEW_SELF,
        user_id="client-001",
        resource_owner_id="client-002"
    )
```

## Performance Benchmarks

The test suite includes performance benchmarks to ensure the system scales:

### Permission Checking
- **Target**: < 0.1ms per permission check
- **Test**: 1,000 permission checks should complete in < 100ms

### Role Permission Loading
- **Target**: Cached loading, < 0.1ms per call
- **Test**: 100 role permission loads should complete in < 10ms

### Feature Access Checking
- **Target**: Full feature check < 100ms
- **Test**: 10 full feature checks should complete in < 1s

## Continuous Integration

Add to your CI/CD pipeline:

```yaml
# .github/workflows/tests.yml
name: RBAC Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-asyncio
      - name: Run RBAC tests
        run: ./scripts/run_rbac_tests.sh
      - name: Upload coverage
        uses: codecov/codecov-action@v2
        with:
          files: ./coverage.xml
```

## Adding New Tests

### Test a New Permission
```python
def test_new_permission():
    """Test description"""
    # 1. Define expected behavior
    expected_roles = {'PLATFORM_ADMIN', 'PARTNER'}

    # 2. Check permission exists
    perm = Permissions.NEW_PERMISSION
    assert perm.code == "expected.code"

    # 3. Verify role assignments
    for role_name in expected_roles:
        perms = get_permissions_for_role(role_name)
        assert perm in perms, f"{role_name} should have {perm.name}"

    # 4. Verify unauthorized roles don't have it
    client_perms = get_permissions_for_role('FIRM_CLIENT')
    assert perm not in client_perms
```

### Test a New Feature
```python
@patch('src.rbac.feature_access_control.get_tenant_persistence')
def test_new_feature_access(mock_persistence, staff_context, pro_tenant):
    """Test new feature access requirements"""
    # 1. Setup tenant with feature
    pro_tenant.features.new_feature_enabled = True
    mock_persistence.return_value.get_tenant.return_value = pro_tenant

    # 2. Test access with correct tier
    access = check_feature_access(Features.NEW_FEATURE, staff_context)
    assert access["allowed"]

    # 3. Test access with insufficient tier
    free_tenant = create_free_tenant()  # Helper function
    mock_persistence.return_value.get_tenant.return_value = free_tenant

    access = check_feature_access(Features.NEW_FEATURE, staff_context)
    assert not access["allowed"]
    assert access["upgrade_tier"] == "professional"
```

## Troubleshooting

### Tests Fail Due to Missing Dependencies
```bash
pip install pytest pytest-cov pytest-asyncio
```

### Tests Fail Due to Import Errors
Ensure you're running from the project root:
```bash
cd /path/to/Jorss-Gbo
pytest tests/
```

### Coverage Report Not Generated
```bash
# Explicitly specify coverage report format
pytest tests/ --cov=src/rbac --cov-report=html --cov-report=term
```

### Slow Tests
```bash
# Run tests in parallel
pytest tests/ -n auto  # Requires pytest-xdist
```

## Code Coverage Goals

- **Overall RBAC Coverage**: > 90%
- **Permission Checking**: 100%
- **Feature Access Control**: > 95%
- **Role Assignments**: 100%

Current coverage:
```bash
./scripts/run_rbac_tests.sh
```

## Best Practices

1. **Test Permission Changes**: Always add tests when adding new permissions
2. **Test Role Changes**: Verify role permission sets when modifying roles
3. **Test Security Boundaries**: Add tests for cross-tenant/user access
4. **Test Regressions**: Keep regression tests for fixed bugs
5. **Test Performance**: Benchmark critical permission checks
6. **Mock External Dependencies**: Use `@patch` for database/API calls
7. **Use Descriptive Names**: Test names should explain what they verify
8. **Document Critical Tests**: Add docstrings explaining importance

## Related Documentation

- [RBAC Comprehensive Guide](../docs/RBAC_COMPREHENSIVE_GUIDE.md) - Complete RBAC documentation
- [Permission Matrix](../docs/RBAC_COMPREHENSIVE_GUIDE.md#permission-matrix-by-role) - All permissions by role
- [Feature Catalog](../docs/RBAC_COMPREHENSIVE_GUIDE.md#feature-access-control) - All features and tiers
- [Security Guidelines](../docs/RBAC_COMPREHENSIVE_GUIDE.md#security-best-practices) - Security best practices

## Support

For questions about the test suite:
1. Check test output for detailed error messages
2. Review related test documentation above
3. Check RBAC Comprehensive Guide for system documentation
4. Review test fixtures and examples in test files
