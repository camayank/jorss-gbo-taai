# RBAC Comprehensive Guide

## Crystal-Clear Permission System

### Overview

The platform implements a **granular, role-based access control (RBAC) system** with:

- ✅ **95 explicitly defined permissions** across all resources
- ✅ **6 user roles** with clear responsibilities
- ✅ **3-level permission scopes** (Platform, Tenant, Self)
- ✅ **Ownership and assignment-based access** control
- ✅ **Feature-based permissions** tied to subscription tiers
- ✅ **Complete audit logging** of all sensitive actions
- ✅ **Dynamic UI** that shows/hides based on permissions

---

## Role Hierarchy

```
Platform Admin (Super Admin)
    ↓
Partner (Tenant Admin)
    ↓
Staff (CPA)
    ↓
Firm Client (with CPA)
    ↓
Direct Client (DIY)
    ↓
Anonymous (Not logged in)
```

---

## Permission Structure

### Permission Naming Convention

```
{SCOPE}_{RESOURCE}_{ACTION}

Examples:
- platform.tenant.create        (Platform scope, tenant resource, create action)
- tenant.branding.edit          (Tenant scope, branding resource, edit action)
- cpa.profile.view_self         (Self scope, profile resource, view action)
- client.returns.edit_self      (Self scope, returns resource, edit action)
```

### Permission Attributes

Every permission has:

| Attribute | Description | Example |
|-----------|-------------|---------|
| **code** | Unique identifier | `tenant.branding.edit` |
| **name** | Human-readable | "Edit Tenant Branding" |
| **description** | What it allows | "Edit own tenant's branding and theme" |
| **scope** | Who it applies to | `TENANT` |
| **resource** | What resource | `TENANT_BRANDING` |
| **action** | What action | `EDIT` |
| **requires_ownership** | Must own resource | `True` |
| **requires_assignment** | Must be assigned | `False` |

---

## Permission Matrix by Role

### Platform Admin (95 permissions)

**Can Do Everything**:
- ✅ Manage all tenants (create, edit, delete)
- ✅ Customize any tenant's branding
- ✅ Enable/disable features for tenants
- ✅ Manage subscription tiers and billing
- ✅ View all audit logs
- ✅ Assign/revoke permissions
- ✅ Configure system-wide settings
- ✅ Access all tenant data

**Key Permissions**:
```
platform.tenant.view_all
platform.tenant.create
platform.tenant.edit
platform.tenant.delete
platform.tenant.branding_edit
platform.tenant.features_edit
platform.tenant.billing_manage
platform.system.configure
platform.audit.view
platform.permissions.manage
```

**Use Cases**:
- Multi-tenant SaaS provider admin
- Platform owner
- Super admin for white-label platform

---

### Partner (68 permissions)

**Tenant Admin + CPA Capabilities**:
- ✅ Edit own tenant's branding
- ✅ Edit own tenant's settings
- ✅ Manage users within tenant (create, edit, delete)
- ✅ Assign clients to CPAs
- ✅ View tenant analytics and stats
- ✅ Configure integrations (QuickBooks, Stripe, etc.)
- ✅ All CPA capabilities (below)

**Tenant Management**:
```
tenant.branding.view
tenant.branding.edit (own tenant only)
tenant.settings.view
tenant.settings.edit
tenant.users.view
tenant.users.create
tenant.users.edit
tenant.users.delete
tenant.analytics.view
tenant.stats.view
```

**CPA Capabilities**:
```
cpa.profile.view_self
cpa.profile.edit_self
cpa.branding.view_self
cpa.branding.edit_self
cpa.clients.view
cpa.clients.create
cpa.clients.assign (can assign to other CPAs)
cpa.returns.view
cpa.returns.edit
cpa.returns.review
cpa.returns.approve
cpa.returns.efile
```

**Feature Access** (if tenant has feature):
```
feature.express_lane.use
feature.smart_tax.use
feature.ai_chat.use
feature.scenarios.use
feature.projections.use
feature.integrations.configure
feature.api.use
```

**Use Cases**:
- CPA firm owner
- Managing partner
- Firm administrator

---

### Staff (42 permissions)

**CPA Capabilities Only**:
- ✅ Customize own CPA profile and branding
- ✅ Manage assigned clients
- ✅ Create, edit, review, approve tax returns
- ✅ E-file tax returns for clients
- ✅ View own tenant's settings (read-only)

**CPA Operations**:
```
cpa.profile.view_self
cpa.profile.edit_self
cpa.branding.view_self
cpa.branding.edit_self
cpa.clients.view (assigned only)
cpa.clients.create
cpa.returns.view (assigned only)
cpa.returns.edit (assigned only)
cpa.returns.review (assigned only)
cpa.returns.approve (assigned only)
cpa.returns.efile (assigned only)
```

**Tenant Visibility** (read-only):
```
tenant.branding.view
tenant.settings.view
tenant.users.view
```

**Feature Access** (if tenant has feature):
```
feature.express_lane.use
feature.smart_tax.use
feature.ai_chat.use
feature.scenarios.use
feature.projections.use
```

**Use Cases**:
- Staff CPA
- Tax preparer
- Junior accountant

---

### Firm Client (18 permissions)

**Client with CPA Support**:
- ✅ Manage own profile
- ✅ Create and edit own tax returns (DRAFT status)
- ✅ Upload documents
- ✅ View own documents and returns
- ✅ Communicate with assigned CPA
- ✅ Access client portal

**Own Data Access**:
```
client.profile.view_self (own profile only)
client.profile.edit_self
client.returns.view_self (own returns only)
client.returns.edit_self (DRAFT status only)
client.returns.create
client.documents.view_self (own documents only)
client.documents.upload
client.portal.access
client.communication.send
```

**Feature Access**:
```
feature.express_lane.use
feature.smart_tax.use
feature.scenarios.use
feature.projections.use
```

**Restrictions**:
- ❌ Cannot edit returns in REVIEW/APPROVED status
- ❌ Cannot approve own returns
- ❌ Cannot e-file
- ❌ Cannot access AI chat (CPA-only feature)

**Use Cases**:
- Client working with CPA firm
- Individual taxpayer with CPA support

---

### Direct Client (15 permissions)

**DIY Client**:
- ✅ Manage own profile
- ✅ Create and edit own returns
- ✅ Upload documents
- ✅ Access client portal
- ✅ Limited feature access

**Own Data Access**:
```
client.profile.view_self
client.profile.edit_self
client.returns.view_self
client.returns.edit_self
client.returns.create
client.documents.view_self
client.documents.upload
client.portal.access
```

**Feature Access**:
```
feature.express_lane.use
feature.smart_tax.use
```

**Restrictions**:
- ❌ No CPA support
- ❌ No communication with CPA
- ❌ Limited features (no scenarios, projections)
- ❌ No AI chat

**Use Cases**:
- DIY taxpayer
- Self-filing individual

---

### Anonymous (2 permissions)

**Not Logged In**:
- ✅ Start a tax return
- ✅ Use express lane

**Minimal Access**:
```
client.returns.create (can start return)
feature.express_lane.use
```

**After Login**: Session transfers to authenticated user

**Use Cases**:
- New visitor starting return
- Trial user

---

## Permission Enforcement

### Backend Enforcement

**Decorator-Based**:

```python
from src.rbac.permission_enforcement import require_permission
from src.rbac.enhanced_permissions import Permissions

@router.get("/tenant/branding")
@require_permission(Permissions.TENANT_BRANDING_VIEW)
async def get_tenant_branding(ctx: AuthContext = Depends(require_auth)):
    # Only users with TENANT_BRANDING_VIEW permission can access
    ...
```

**Multiple Permissions (all required)**:

```python
@require_permission(
    Permissions.CPA_RETURNS_VIEW,
    Permissions.CPA_RETURNS_EDIT
)
async def edit_return(return_id: str, ctx: AuthContext = Depends(require_auth)):
    # Need both VIEW and EDIT permissions
    ...
```

**Any One Permission**:

```python
from src.rbac.permission_enforcement import require_any_permission

@require_any_permission(
    Permissions.PLATFORM_TENANT_VIEW_ALL,
    Permissions.TENANT_USERS_VIEW
)
async def view_users(...):
    # Platform admin OR tenant partner can access
    ...
```

**Feature-Based**:

```python
from src.rbac.permission_enforcement import require_tenant_feature

@router.post("/ai-chat")
@require_tenant_feature('ai_chat_enabled')
async def ai_chat(...):
    # Only if tenant has AI chat feature enabled
    ...
```

**Ownership Check**:

```python
from src.rbac.permission_enforcement import check_resource_ownership

@router.get("/returns/{return_id}")
@require_permission(Permissions.CLIENT_RETURNS_VIEW_SELF)
async def get_return(return_id: str, ctx: AuthContext = Depends(require_auth)):
    # Get return
    tax_return = get_return_by_id(return_id)

    # Check ownership
    if not check_resource_ownership(ctx, tax_return.client_id):
        raise HTTPException(403, "You can only view your own returns")

    return tax_return
```

### Frontend Enforcement

**Dynamic UI Components**:

```html
<!-- Show/hide based on permission -->
{% if user_has_permission('tenant.branding.edit') %}
<button onclick="editBranding()">Edit Branding</button>
{% endif %}

<!-- Show/hide based on role -->
{% if user.role == 'PLATFORM_ADMIN' or user.role == 'PARTNER' %}
<div class="admin-section">
    <!-- Admin-only content -->
</div>
{% endif %}

<!-- Show/hide based on feature -->
{% if tenant_has_feature('ai_chat_enabled') %}
<button onclick="openAIChat()">AI Assistant</button>
{% endif %}

<!-- Show/hide based on ownership -->
{% if return.client_id == current_user.id %}
<button onclick="editReturn()">Edit Return</button>
{% endif %}

<!-- Show/hide based on status -->
{% if return.status == 'DRAFT' and return.client_id == current_user.id %}
<button onclick="editReturn()">Edit Return</button>
{% elif return.status == 'IN_REVIEW' and user.role in ['STAFF', 'PARTNER'] %}
<button onclick="reviewReturn()">Review Return</button>
{% endif %}
```

**JavaScript Permission Checks**:

```javascript
// Check permission before action
async function editBranding() {
    const hasPermission = await checkPermission('tenant.branding.edit');

    if (!hasPermission) {
        alert('You do not have permission to edit branding');
        return;
    }

    // Proceed with edit
    showBrandingEditor();
}

// Get user permissions
const permissions = await fetch('/api/auth/my-permissions').then(r => r.json());

// Show/hide UI elements
if (permissions.includes('cpa.clients.assign')) {
    document.getElementById('assignClientBtn').style.display = 'block';
}
```

---

## Feature-Based Access Control

### Subscription Tier → Features → Permissions

**Tier Hierarchy**:

| Tier | Monthly Returns | CPAs | Storage | Key Features |
|------|-----------------|------|---------|--------------|
| Free | 5 | 1 | 1 GB | Express Lane only |
| Starter | 50 | 3 | 10 GB | + Smart Tax, Scenarios |
| Professional | 200 | 10 | 50 GB | + AI Chat, QuickBooks |
| Enterprise | ∞ | ∞ | 500 GB | + Custom Domain, API |
| White Label | ∞ | ∞ | ∞ | + Remove Branding, Full |

**Feature Permission Mapping**:

```python
# Feature enabled → Permission granted
if tenant.features.ai_chat_enabled:
    user.permissions.add(Permissions.FEATURE_AI_CHAT_USE)

if tenant.features.scenario_explorer_enabled:
    user.permissions.add(Permissions.FEATURE_SCENARIOS_USE)

if tenant.features.custom_domain_enabled:
    user.permissions.add(Permissions.PLATFORM_TENANT_CUSTOM_DOMAIN)
```

**Upgrade Prompts**:

When feature denied:
```json
{
  "error": "Feature Not Enabled",
  "feature": "ai_chat_enabled",
  "current_tier": "starter",
  "required_tier": "professional",
  "message": "Upgrade to Professional to access AI Chat",
  "upgrade_url": "/billing/upgrade?tier=professional"
}
```

---

## Audit Logging

### What Gets Logged

**All Sensitive Actions**:

- ✅ Authentication (login, logout, failed logins)
- ✅ Tenant changes (create, update, delete, branding, features)
- ✅ User management (create, role change, permission change)
- ✅ Tax return actions (create, edit, submit, approve, efile)
- ✅ Document access (upload, view, download, delete)
- ✅ Permission denials (important for security)
- ✅ Feature access (usage tracking)
- ✅ Data exports
- ✅ Security events (suspicious activity, rate limits)

**Audit Event Structure**:

```python
{
    "event_id": "uuid",
    "event_type": "tenant.branding_update",
    "severity": "info",  # info, warning, error, critical
    "timestamp": "2026-01-21T10:30:00Z",

    # Who
    "user_id": "user_123",
    "user_role": "PARTNER",
    "tenant_id": "tenant_abc",

    # What
    "action": "update_branding",
    "resource_type": "tenant_branding",
    "resource_id": "tenant_abc",

    # Context
    "ip_address": "192.168.1.1",
    "user_agent": "Mozilla/5.0...",
    "request_path": "/api/tenant/branding",

    # Details
    "old_value": {"primary_color": "#667eea"},
    "new_value": {"primary_color": "#059669"},
    "details": {"changed_fields": ["primary_color"]},

    # Result
    "success": true,
    "error_message": null
}
```

**Querying Audit Log**:

```python
from src.audit.audit_logger import get_audit_logger

logger = get_audit_logger()

# Get user activity
user_activity = logger.get_user_activity(user_id="user_123", days=30)

# Get tenant activity
tenant_activity = logger.get_tenant_activity(tenant_id="tenant_abc", days=7)

# Get failed logins
failed_logins = logger.get_failed_logins(hours=24)

# Get permission denials
denials = logger.get_permission_denials(user_id="user_123", days=7)

# Get security events
security_events = logger.get_security_events(days=7)

# Custom query
events = logger.query(
    user_id="user_123",
    event_type=AuditEventType.TAX_RETURN_APPROVE,
    start_date=datetime(2026, 1, 1),
    end_date=datetime(2026, 1, 31),
    success_only=True,
    limit=100
)
```

---

## Permission Testing

### Test Scenarios

**1. Role Permission Tests**:

```python
def test_partner_can_edit_tenant_branding():
    ctx = AuthContext(user_id="user_123", role=Role.PARTNER, tenant_id="tenant_abc")
    assert has_permission(ctx, Permissions.TENANT_BRANDING_EDIT)

def test_staff_cannot_edit_tenant_branding():
    ctx = AuthContext(user_id="user_456", role=Role.STAFF, tenant_id="tenant_abc")
    assert not has_permission(ctx, Permissions.TENANT_BRANDING_EDIT)
```

**2. Ownership Tests**:

```python
def test_client_can_view_own_return():
    ctx = AuthContext(user_id="client_123", role=Role.FIRM_CLIENT)
    tax_return = get_return(return_id="return_456")

    # Client owns this return
    assert tax_return.client_id == "client_123"
    assert can_user_access_resource(ctx, Permissions.CLIENT_RETURNS_VIEW_SELF, tax_return.client_id)

def test_client_cannot_view_other_return():
    ctx = AuthContext(user_id="client_123", role=Role.FIRM_CLIENT)
    tax_return = get_return(return_id="return_789")

    # Client does NOT own this return
    assert tax_return.client_id == "client_999"
    assert not can_user_access_resource(ctx, Permissions.CLIENT_RETURNS_VIEW_SELF, tax_return.client_id)
```

**3. Feature Tests**:

```python
def test_professional_tier_has_ai_chat():
    tenant = create_tenant(subscription_tier=SubscriptionTier.PROFESSIONAL)
    assert tenant.features.ai_chat_enabled

def test_starter_tier_no_ai_chat():
    tenant = create_tenant(subscription_tier=SubscriptionTier.STARTER)
    assert not tenant.features.ai_chat_enabled
```

---

## Best Practices

### For Platform Admins

1. **Least Privilege**: Grant minimum permissions needed
2. **Regular Audits**: Review audit logs monthly
3. **Role Assignment**: Use roles, not custom permissions
4. **Monitor Denials**: Check permission denial logs
5. **Document Changes**: Log why permissions were changed

### For Developers

1. **Always Use Decorators**: Never skip permission checks
2. **Check Ownership**: Verify resource ownership when needed
3. **Audit Sensitive Actions**: Log all important operations
4. **Clear Error Messages**: Explain why permission was denied
5. **Test Permissions**: Write tests for all permission scenarios

### For Users

1. **Understand Your Role**: Know what you can/cannot do
2. **Request Access**: Contact admin if you need more permissions
3. **Report Issues**: If you can access something you shouldn't
4. **Protect Credentials**: Never share login information

---

## Troubleshooting

### "Permission Denied" Errors

**Error**:
```json
{
  "error": "Permission Denied",
  "required_permission": {
    "code": "tenant.branding.edit",
    "name": "Edit Tenant Branding"
  },
  "reason": "Your role (STAFF) does not have permission: Edit Tenant Branding"
}
```

**Solutions**:
1. Check your role: Only PARTNER can edit tenant branding
2. Request role upgrade from tenant admin
3. Verify you're in the correct tenant

**Error**:
```json
{
  "error": "Feature Not Enabled",
  "feature": "ai_chat_enabled",
  "current_tier": "starter",
  "required_tier": "professional",
  "message": "Upgrade to Professional to access AI Chat"
}
```

**Solutions**:
1. Upgrade subscription tier
2. Contact tenant admin to enable feature
3. Use alternative features available in your tier

---

## API Reference

### Permission Check Endpoints

```
GET /api/auth/my-permissions
  → Returns list of permission codes for current user

GET /api/auth/check-permission?code=tenant.branding.edit
  → Returns whether user has specific permission

GET /api/auth/my-role
  → Returns current user's role and tenant

GET /api/tenant/features
  → Returns enabled features for current tenant

GET /api/audit/my-activity?days=30
  → Returns user's recent activity (audit log)
```

---

## Migration Guide

### Adding New Permission

1. **Define in `enhanced_permissions.py`**:
```python
NEW_PERMISSION = Permission(
    code="resource.action",
    name="Human Name",
    description="What it allows",
    scope=PermissionScope.TENANT,
    resource=ResourceType.NEW_RESOURCE,
    action=PermissionAction.EDIT
)
```

2. **Add to Role Permission Set**:
```python
PARTNER_PERMISSIONS = frozenset({
    ...,
    Permissions.NEW_PERMISSION,
})
```

3. **Use in API**:
```python
@require_permission(Permissions.NEW_PERMISSION)
async def new_endpoint(...):
    ...
```

4. **Update UI**:
```html
{% if user_has_permission('resource.action') %}
<button>New Action</button>
{% endif %}
```

5. **Add Tests**:
```python
def test_new_permission():
    assert Permissions.NEW_PERMISSION in get_permissions_for_role('PARTNER')
```

---

## Summary

**95 Permissions** across:
- 8 Platform resources
- 12 Tenant resources
- 8 CPA resources
- 7 Client resources
- 7 Feature resources
- 3 System resources

**6 Roles** with clear responsibilities:
- Platform Admin (super user)
- Partner (tenant admin)
- Staff (CPA)
- Firm Client (with CPA)
- Direct Client (DIY)
- Anonymous (guest)

**Complete Enforcement**:
- ✅ Backend decorators
- ✅ Frontend dynamic UI
- ✅ Feature-based access
- ✅ Ownership checks
- ✅ Audit logging

**Crystal Clear**: Every permission explicitly defined, every role clearly scoped, every action logged.
