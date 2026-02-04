# White-Labeling System - Complete Guide

## Overview

The platform features a **robust multi-tenant white-labeling system** that enables:

- ✅ **Platform Admins** to manage multiple CPA firms with independent branding
- ✅ **CPAs** to customize their personal profile within their firm's theme
- ✅ **Complete isolation** between tenants (data, branding, features)
- ✅ **Flexible deployment** (shared domain, subdomains, or custom domains)
- ✅ **Subscription-based features** with automatic enforcement
- ✅ **Live theme preview** and real-time customization

---

## Architecture

### Three-Level Branding Hierarchy

```
Platform Level
    ↓
Tenant Level (CPA Firm)
    ↓
CPA Level (Individual CPA)
    ↓
Client View
```

**Inheritance Rules**:
1. Tenant branding overrides platform defaults
2. CPA branding overrides tenant branding (limited scope)
3. Client sees merged branding based on assigned CPA

---

## For Platform Admins

### Managing Tenants

**Access**: Platform Admin Dashboard at `/admin/tenants`

#### 1. Creating a New Tenant

**Via UI**:
1. Click "➕ Create New Tenant"
2. Enter tenant details:
   - **Tenant Name**: Company name (e.g., "Smith Tax Services")
   - **Admin Email**: Primary admin contact
   - **Subscription Tier**: Free, Starter, Professional, Enterprise, White Label
   - **Theme Preset**: Choose pre-built theme or custom colors

**Via API**:
```bash
curl -X POST /api/admin/tenants/ \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_name": "Smith Tax Services",
    "admin_email": "admin@smithtax.com",
    "subscription_tier": "professional",
    "theme_preset": "professional_blue",
    "company_name": "Smith & Associates, CPAs",
    "platform_name": "SmithTax Online",
    "primary_color": "#059669"
  }'
```

**Response**:
```json
{
  "tenant_id": "tenant_abc123def456",
  "tenant_name": "Smith Tax Services",
  "status": "active",
  "subscription_tier": "professional",
  "branding": { ... },
  "features": { ... }
}
```

#### 2. Customizing Tenant Branding

**Configurable Elements**:

| Category | Fields |
|----------|---------|
| **Identity** | Platform Name, Company Name, Tagline |
| **Visual** | Theme Preset, Primary Color, Secondary Color, Accent Color |
| **Typography** | Font Family, Heading Font, Base Font Size |
| **Assets** | Logo URL, Dark Logo, Favicon, Background Image |
| **Contact** | Support Email, Phone, Website, Address |
| **Social** | Facebook, Twitter, LinkedIn |
| **Messaging** | Filing Time Claim, Security Claim, Review Claim |
| **Legal** | Terms URL, Privacy URL |
| **Advanced** | Custom CSS, Custom JS, Custom HTML |

**Example - Update Branding**:
```bash
curl -X PATCH /api/admin/tenants/tenant_abc123/branding \
  -H "Content-Type: application/json" \
  -d '{
    "platform_name": "SmithTax Online",
    "company_name": "Smith & Associates, CPAs",
    "primary_color": "#059669",
    "secondary_color": "#10b981",
    "logo_url": "/uploads/smith-logo.svg",
    "support_email": "support@smithtax.com",
    "filing_time_claim": "5 Minutes"
  }'
```

#### 3. Managing Features & Limits

**Feature Flags by Tier**:

| Feature | Free | Starter | Professional | Enterprise | White Label |
|---------|------|---------|--------------|------------|-------------|
| Express Lane | ✅ | ✅ | ✅ | ✅ | ✅ |
| Smart Tax | ❌ | ✅ | ✅ | ✅ | ✅ |
| AI Chat | ❌ | ❌ | ✅ | ✅ | ✅ |
| Scenario Explorer | ❌ | ✅ | ✅ | ✅ | ✅ |
| Tax Projections | ❌ | ✅ | ✅ | ✅ | ✅ |
| QuickBooks Integration | ❌ | ❌ | ✅ | ✅ | ✅ |
| Custom Domain | ❌ | ❌ | ❌ | ✅ | ✅ |
| Remove Branding | ❌ | ❌ | ❌ | ❌ | ✅ |
| Max Returns/Month | 5 | 50 | 200 | ∞ | ∞ |
| Max CPAs | 1 | 3 | 10 | ∞ | ∞ |
| Storage (GB) | 1 | 10 | 50 | 500 | ∞ |

**Update Features**:
```bash
curl -X PATCH /api/admin/tenants/tenant_abc123/features \
  -H "Content-Type: application/json" \
  -d '{
    "ai_chat_enabled": true,
    "scenario_explorer_enabled": true,
    "quickbooks_integration": true,
    "max_returns_per_month": 500,
    "max_cpas": 20,
    "max_storage_gb": 100
  }'
```

#### 4. Custom Domains

**Setup Process**:

1. **Add Domain**:
```bash
curl -X POST /api/admin/tenants/tenant_abc123/custom-domain \
  -d "domain=tax.smithassociates.com"
```

**Response**:
```json
{
  "verification_token": "tax-verify-a1b2c3d4e5f6",
  "instructions": "Add TXT record: tax-domain-verification=tax-verify-a1b2c3d4e5f6"
}
```

2. **Client adds DNS TXT record**:
```
Host: tax.smithassociates.com
Type: TXT
Value: tax-domain-verification=tax-verify-a1b2c3d4e5f6
```

3. **Verify Domain**:
```bash
curl -X POST /api/admin/tenants/tenant_abc123/custom-domain/tax.smithassociates.com/verify
```

4. **Add CNAME record** (after verification):
```
Host: tax.smithassociates.com
Type: CNAME
Value: platform.yourdomain.com
```

#### 5. Monitoring Usage

**Get Tenant Stats**:
```bash
curl /api/admin/tenants/tenant_abc123/stats
```

**Response**:
```json
{
  "usage": {
    "returns": 127,
    "cpas": 8,
    "clients": 456,
    "storage_gb": 34.5
  },
  "limits": {
    "returns_per_month": 200,
    "max_cpas": 10,
    "max_storage_gb": 50
  },
  "utilization": {
    "returns_percent": 63.5,
    "cpas_percent": 80.0,
    "storage_percent": 69.0
  }
}
```

#### 6. Managing Tenant Status

**Statuses**:
- `active` - Fully operational
- `trial` - Trial period
- `suspended` - Suspended for non-payment
- `cancelled` - Cancelled subscription
- `pending_setup` - Initial setup incomplete

**Update Status**:
```bash
curl -X PATCH /api/admin/tenants/tenant_abc123/status \
  -d "status=suspended"
```

---

## For CPAs

### Customizing Your Profile

**Access**: CPA Branding Settings at `/cpa/branding`

CPAs can customize their personal branding within the firm's theme:

#### What CPAs Can Customize

| Category | Customizable | Notes |
|----------|--------------|-------|
| Display Name | ✅ | e.g., "John Smith, CPA" |
| Tagline | ✅ | e.g., "Your Trusted Tax Advisor" |
| Accent Color | ✅ | Personal accent color within theme |
| Profile Photo | ✅ | Shown in client portal |
| Signature | ✅ | For documents |
| Bio | ✅ | Professional background |
| Credentials | ✅ | CPA, CFP, EA, etc. |
| Experience | ✅ | Years of experience |
| Specializations | ✅ | Individual Tax, Business Tax, etc. |
| Contact Info | ✅ | Direct email, phone, office address |
| Welcome Message | ✅ | Client portal greeting |

**What CPAs Cannot Override**:
- Platform name
- Company name
- Primary/secondary colors (can only customize accent)
- Logo/favicon
- Core messaging

#### Via UI

1. Go to **Settings** → **My Branding**
2. Update personal information
3. Upload profile photo and signature
4. Add credentials and specializations
5. Set custom accent color
6. Preview changes in real-time
7. Click **Save Changes**

#### Via API

```bash
curl -X PATCH /api/cpa/branding/my-branding \
  -H "Content-Type: application/json" \
  -d '{
    "display_name": "John Smith, CPA",
    "tagline": "Tax Planning Specialist",
    "bio": "Helping clients optimize their tax strategy for over 15 years.",
    "credentials": ["CPA", "CFP"],
    "years_experience": 15,
    "specializations": ["Individual Tax", "Tax Planning"],
    "direct_email": "jsmith@smithtax.com",
    "direct_phone": "(555) 123-4567",
    "welcome_message": "Welcome! I'm excited to help you with your tax needs this year.",
    "accent_color": "#059669"
  }'
```

**Upload Profile Photo**:
```bash
curl -X POST /api/cpa/branding/my-branding/profile-photo \
  -F "file=@profile.jpg"
```

---

## Technical Implementation

### Database Schema

#### Tenants Table

```sql
CREATE TABLE tenants (
    tenant_id TEXT PRIMARY KEY,
    tenant_name TEXT NOT NULL,
    status TEXT NOT NULL,
    subscription_tier TEXT NOT NULL,
    branding JSON NOT NULL,
    features JSON NOT NULL,
    custom_domain TEXT,
    custom_domain_verified INTEGER DEFAULT 0,
    admin_user_id TEXT,
    admin_email TEXT NOT NULL,
    stripe_customer_id TEXT,
    subscription_expires_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata JSON,
    total_returns INTEGER DEFAULT 0,
    total_cpas INTEGER DEFAULT 0,
    total_clients INTEGER DEFAULT 0,
    storage_used_gb REAL DEFAULT 0.0
);
```

#### CPA Branding Table

```sql
CREATE TABLE cpa_branding (
    cpa_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    display_name TEXT,
    tagline TEXT,
    accent_color TEXT,
    profile_photo_url TEXT,
    signature_image_url TEXT,
    direct_email TEXT,
    direct_phone TEXT,
    office_address TEXT,
    bio TEXT,
    credentials JSON,
    years_experience INTEGER,
    specializations JSON,
    welcome_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE
);
```

### Tenant Resolution

**Automatic tenant detection** via middleware:

1. **URL Parameter**: `?tenant_id=xxx`
2. **Header**: `X-Tenant-ID: xxx`
3. **Custom Domain**: `tax.yourfirm.com` → lookup tenant
4. **Subdomain**: `yourfirm.platform.com` → lookup tenant
5. **Default**: Fallback tenant

**Example Request Flow**:
```
Client Request: https://tax.smithassociates.com/landing
    ↓
Middleware: Resolve tenant from domain
    ↓
Tenant: "Smith Tax Services" (tenant_abc123)
    ↓
Inject Branding: Smith's colors, logo, messaging
    ↓
Template Render: Branded landing page
    ↓
Response: Fully white-labeled page
```

### Branding Injection

**All templates automatically receive branding**:

```html
<!-- Templates have access to: -->
<title>{{ branding.platform_name }}</title>

<style>
    :root {
        --primary-color: {{ branding.primary_color }};
        --secondary-color: {{ branding.secondary_color }};
        --accent-color: {{ branding.accent_color }};
    }
</style>

{% if branding.logo_url %}
<img src="{{ branding.logo_url }}" alt="{{ branding.company_name }}">
{% endif %}

<p>{{ branding.tagline }}</p>
<a href="mailto:{{ branding.support_email }}">Contact Us</a>
```

### Feature Flag Enforcement

**Backend enforcement**:

```python
from src.web.tenant_middleware import require_tenant_feature

@app.post("/api/ai-chat")
@require_tenant_feature('ai_chat_enabled')
async def ai_chat_endpoint(request: Request):
    # Only accessible if tenant has AI chat enabled
    ...
```

**Frontend conditional rendering**:

```html
{% if branding.features.scenario_explorer_enabled %}
<button onclick="openScenarios()">Explore Scenarios</button>
{% endif %}
```

---

## Deployment Scenarios

### Scenario 1: Single Shared Domain

**Setup**: All tenants on `platform.com` differentiated by URL param or subdomain

```
https://platform.com/?tenant_id=smith-tax
https://smithtax.platform.com
https://johnsoncpa.platform.com
```

**Configuration**: No DNS changes needed

### Scenario 2: Custom Domains (White Label)

**Setup**: Each tenant has their own domain

```
https://tax.smithassociates.com
https://taxservices.johnsoncpa.com
```

**Requirements**:
- DNS TXT record for verification
- DNS CNAME record pointing to platform
- SSL certificate (automatic with Cloudflare/AWS)

### Scenario 3: Hybrid

**Setup**: Default shared domain + optional custom domains for premium tenants

```
Standard: https://platform.com/?tenant_id=basic-firm
Premium: https://tax.premiumfirm.com
```

---

## Best Practices

### For Platform Admins

1. **Consistent Naming**: Use clear tenant IDs (e.g., `smith-tax-services`)
2. **Monitor Usage**: Set up alerts for tenants approaching limits
3. **Regular Backups**: Backup tenant configurations before major changes
4. **Test Customizations**: Preview branding before deploying to production
5. **Document Changes**: Log all tenant configuration changes
6. **Security**: Regularly audit tenant access and permissions

### For CPA Firms (Tenants)

1. **Brand Guidelines**: Maintain consistent brand identity
2. **Logo Quality**: Use SVG for logos (scales perfectly)
3. **Color Accessibility**: Ensure sufficient contrast (WCAG AA)
4. **Professional Photos**: Use high-quality profile photos
5. **Keep Contact Current**: Update support email/phone regularly
6. **Test Client View**: Regularly check what clients see

### For CPAs

1. **Professional Image**: Use professional headshot
2. **Clear Credentials**: List all relevant certifications
3. **Helpful Bio**: Focus on expertise and client benefits
4. **Welcoming Message**: Personalize client portal greeting
5. **Keep Updated**: Update specializations as you grow

---

## API Reference

### Admin Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/admin/tenants/` | Create tenant |
| GET | `/api/admin/tenants/` | List tenants |
| GET | `/api/admin/tenants/{id}` | Get tenant details |
| PATCH | `/api/admin/tenants/{id}/branding` | Update branding |
| PATCH | `/api/admin/tenants/{id}/features` | Update features |
| PATCH | `/api/admin/tenants/{id}/status` | Update status |
| GET | `/api/admin/tenants/{id}/stats` | Get usage stats |
| POST | `/api/admin/tenants/{id}/custom-domain` | Add custom domain |
| POST | `/api/admin/tenants/{id}/custom-domain/{domain}/verify` | Verify domain |
| DELETE | `/api/admin/tenants/{id}` | Delete tenant |

### CPA Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/cpa/branding/my-branding` | Get my branding |
| PATCH | `/api/cpa/branding/my-branding` | Update my branding |
| POST | `/api/cpa/branding/my-branding/profile-photo` | Upload photo |
| POST | `/api/cpa/branding/my-branding/signature` | Upload signature |
| GET | `/api/cpa/branding/{cpa_id}` | Get CPA branding (public) |
| DELETE | `/api/cpa/branding/my-branding` | Reset to defaults |

---

## Troubleshooting

### Issue: Branding Not Appearing

**Cause**: Tenant not resolved correctly

**Solution**:
1. Check tenant exists: `GET /api/admin/tenants/{id}`
2. Verify domain mapping if using custom domain
3. Check browser console for errors
4. Clear cache and hard refresh (Ctrl+Shift+R)

### Issue: Features Not Working

**Cause**: Feature not enabled for tenant's subscription tier

**Solution**:
1. Check tenant features: `GET /api/admin/tenants/{id}/features`
2. Upgrade subscription tier if needed
3. Manually enable feature: `PATCH /api/admin/tenants/{id}/features`

### Issue: Custom Domain Not Working

**Cause**: DNS not configured or not verified

**Solution**:
1. Verify DNS TXT record exists: `dig TXT tax.example.com`
2. Wait for DNS propagation (up to 48 hours)
3. Verify domain: `POST /api/admin/tenants/{id}/custom-domain/{domain}/verify`
4. Check CNAME record points to platform

### Issue: CPA Cannot Customize Branding

**Cause**: Tenant disabled sub-branding

**Solution**:
1. Check tenant setting: `allow_sub_branding`
2. Enable in tenant branding config
3. Verify CPA has STAFF or PARTNER role

---

## Migration Guide

### From Single-Tenant to Multi-Tenant

1. **Create Default Tenant**:
```python
from src.database.tenant_persistence import get_tenant_persistence
from src.database.tenant_models import Tenant, TenantBranding

# Create default tenant
tenant = Tenant(
    tenant_id="default",
    tenant_name="Default Tenant",
    branding=TenantBranding(
        platform_name="Tax Filing Platform",
        company_name="Your CPA Firm"
    )
)

persistence = get_tenant_persistence()
persistence.create_tenant(tenant)
```

2. **Update Middleware**:
```python
from src.web.tenant_middleware import TenantResolutionMiddleware

app.add_middleware(TenantResolutionMiddleware, default_tenant_id="default")
```

3. **Test Existing Functionality**: Ensure all features work with default tenant

4. **Create New Tenants**: Add additional tenants as needed

---

## Security Considerations

1. **Tenant Isolation**: All queries filtered by `tenant_id`
2. **Permission Checks**: Users can only access their tenant's data
3. **Rate Limiting**: Per-tenant rate limits based on subscription
4. **Data Encryption**: All sensitive data encrypted at rest
5. **Audit Logging**: Track all tenant configuration changes
6. **Domain Verification**: Prevent domain hijacking
7. **File Upload Security**: Validate all uploaded assets

---

## Future Enhancements

- [ ] Multi-language support per tenant
- [ ] Custom email templates per tenant
- [ ] Tenant-specific tax rules/jurisdictions
- [ ] White-label mobile apps
- [ ] Tenant analytics dashboard
- [ ] Auto-scaling based on tenant usage
- [ ] Tenant backup/restore
- [ ] Tenant cloning for franchises

---

## Support

For white-labeling assistance:
- **Documentation**: This file
- **Admin Dashboard**: `/admin/tenants`
- **API Docs**: Automatically generated at `/docs`
- **Example Configs**: See `src/database/tenant_models.py`

**Platform Admin Contact**: Contact your platform administrator for tenant setup assistance.
