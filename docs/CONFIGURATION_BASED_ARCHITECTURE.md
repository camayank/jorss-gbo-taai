# Configuration-Based Architecture

## Overview

The Unified Tax Filing Platform is designed to be **100% configuration-based** with **zero hardcoded values**. This enables:

- ✅ **White-label deployment** for any CPA firm
- ✅ **Multi-tenant support** (one codebase, many brands)
- ✅ **Easy customization** without code changes
- ✅ **Rapid deployment** with environment variables or JSON configs

---

## Architecture Principles

### 1. No Hardcoded Business Logic

❌ **Bad** (Hardcoded):
```python
if company_name == "CA4CPA GLOBAL LLC":
    enable_premium_features()
```

✅ **Good** (Configuration-driven):
```python
if config.features.premium_enabled:
    enable_premium_features()
```

### 2. Branding via Configuration

❌ **Bad** (Hardcoded):
```html
<title>CA4CPA Tax Platform</title>
<h1>File Your Taxes with CA4CPA</h1>
```

✅ **Good** (Template variables):
```html
<title>{{ branding.platform_name }}</title>
<h1>File Your Taxes with {{ branding.company_name }}</h1>
```

### 3. Colors via Variables

❌ **Bad** (Hardcoded):
```css
.button {
    background: #667eea;
}
```

✅ **Good** (Template variables):
```css
.button {
    background: {{ branding.primary_color }};
}
```

### 4. Features via Flags

❌ **Bad** (Hardcoded):
```python
if True:  # Always enabled
    show_scenarios()
```

✅ **Good** (Feature flags):
```python
if is_enabled("scenarios_integration"):
    show_scenarios()
```

---

## Configuration Layers

The platform uses a **layered configuration system**:

```
┌─────────────────────────────────────────┐
│  1. JSON Config File (Highest Priority) │  <- BRANDING_CONFIG_PATH
├─────────────────────────────────────────┤
│  2. Environment Variables               │  <- export PLATFORM_NAME="..."
├─────────────────────────────────────────┤
│  3. .env File                           │  <- Standard dotenv
├─────────────────────────────────────────┤
│  4. Default Values (Fallback)           │  <- BrandingConfig defaults
└─────────────────────────────────────────┘
```

### Priority Example

```bash
# Default
PLATFORM_NAME="Tax Filing Platform"

# Override via .env
# .env file:
PLATFORM_NAME="TaxPro Online"

# Override via environment (highest priority)
export PLATFORM_NAME="My Custom Tax Platform"

# Result: "My Custom Tax Platform"
```

---

## Configuration Categories

### 1. Branding Configuration

**File**: `src/config/branding.py`

**Configurable Elements**:
- Platform name and tagline
- Company name and contact info
- Primary and secondary colors
- Logo and favicon URLs
- Feature claims (filing time, security, review process)
- Legal links (terms, privacy)
- Custom CSS/JS

**Usage**:
```python
from src.config.branding import get_branding_config

config = get_branding_config()
print(config.platform_name)  # Your configured name
print(config.primary_color)  # Your brand color
```

**Template Usage**:
```html
<title>{{ branding.platform_name }}</title>
<style>
    .btn { background: {{ branding.primary_color }}; }
</style>
```

### 2. Feature Flags

**File**: `src/config/feature_flags.py`

**Configurable Features**:
- Unified filing system (on/off)
- Database persistence (on/off)
- New landing page (on/off)
- Old workflows (backward compatibility)
- Scenario explorer integration
- AI chat features
- Express lane workflow

**Usage**:
```python
from src.config.feature_flags import is_enabled

if is_enabled("unified_filing_enabled"):
    use_unified_flow()
else:
    use_legacy_flow()
```

### 3. Database Configuration

**Environment Variables**:
```bash
DATABASE_PATH="./data/tax_returns.db"
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10
SESSION_EXPIRY_HOURS=24
```

### 4. Security Configuration

**Environment Variables**:
```bash
JWT_SECRET_KEY="your-secret-key"
JWT_ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_SECONDS=28800
CORS_ORIGINS="http://localhost:3000"
```

### 5. Application Configuration

**Environment Variables**:
```bash
HOST="0.0.0.0"
PORT=8000
ENVIRONMENT="production"
DEBUG=false
WORKERS=4
LOG_LEVEL="INFO"
```

---

## Deployment Scenarios

### Scenario 1: Single CPA Firm

**Setup**:
```bash
# .env file
PLATFORM_NAME="Smith Tax Services"
COMPANY_NAME="Smith & Associates, CPAs"
BRAND_PRIMARY_COLOR="#059669"
SUPPORT_EMAIL="support@smithtax.com"
```

**Result**: Platform branded for Smith Tax Services.

---

### Scenario 2: White-Label Reseller

**Setup**: Use JSON configs per client

```bash
# Client 1
export BRANDING_CONFIG_PATH=/configs/client1.json
python -m src.web.app --port 8001

# Client 2
export BRANDING_CONFIG_PATH=/configs/client2.json
python -m src.web.app --port 8002
```

**Result**: Same codebase, different branding per client.

---

### Scenario 3: Multi-Tenant SaaS

**Setup**: Domain-based tenant resolution

```python
# In src/web/app.py
TENANT_CONFIGS = {
    "firm1.taxpro.com": load_config("/configs/firm1.json"),
    "firm2.taxpro.com": load_config("/configs/firm2.json"),
}

@app.middleware("http")
async def resolve_tenant(request, call_next):
    host = request.headers.get("host")
    request.state.branding = TENANT_CONFIGS.get(host)
    return await call_next(request)
```

**Result**: Automatic branding based on domain.

---

### Scenario 4: Enterprise Internal

**Setup**:
```bash
PLATFORM_NAME="Internal Tax Processing"
COMPANY_NAME="Acme Corporation"
BRAND_PRIMARY_COLOR="#374151"
SECURITY_CLAIM="Internal Use Only"
REVIEW_CLAIM="Finance Department Review"
```

**Result**: Enterprise-focused internal branding.

---

## Configuration Files

### Core Configuration Files

| File | Purpose | Configurable? |
|------|---------|---------------|
| `.env` | Environment variables | ✅ Yes - copy from `.env.example` |
| `.env.example` | Template with all options | 📖 Reference only |
| `branding_config.json` | Branding settings | ✅ Yes - generate from template |
| `src/config/branding.py` | Branding configuration class | ⚙️ Code (no changes needed) |
| `src/config/feature_flags.py` | Feature flag system | ⚙️ Code (no changes needed) |

### Template Files (Auto-inject branding)

| File | Branding Variables Used |
|------|------------------------|
| `src/web/templates/landing.html` | ✅ All (name, colors, logo, claims) |
| `src/web/templates/file.html` | ✅ All (name, colors, custom CSS/JS) |
| `src/web/templates/results.html` | ✅ All (name, colors, custom CSS/JS) |

### App Routes (Inject branding)

| Route | Injects Branding? |
|-------|-------------------|
| `/landing` | ✅ Yes |
| `/file` | ✅ Yes |
| `/results` | ✅ Yes |
| All others | 🔧 Add as needed |

---

## Adding New Configurable Elements

### Example: Add Company Phone to Footer

**Step 1**: Add to BrandingConfig

```python
# src/config/branding.py

@dataclass
class BrandingConfig:
    # ... existing fields ...
    company_phone: Optional[str] = None
    show_phone_in_footer: bool = True
```

**Step 2**: Add to Environment Loader

```python
# src/config/branding.py

def load_branding_from_env():
    return BrandingConfig(
        # ... existing fields ...
        company_phone=os.getenv('COMPANY_PHONE'),
        show_phone_in_footer=os.getenv('SHOW_PHONE_FOOTER', 'true').lower() == 'true'
    )
```

**Step 3**: Update Templates

```html
<!-- src/web/templates/landing.html -->
<footer>
    {% if branding.show_phone_in_footer and branding.company_phone %}
    <p>Call us: {{ branding.company_phone }}</p>
    {% endif %}
</footer>
```

**Step 4**: Add to .env.example

```bash
# .env.example
COMPANY_PHONE="1-800-TAX-HELP"
SHOW_PHONE_FOOTER=true
```

**Done!** Now phone number is configurable.

---

## Testing Configuration

### Test Different Branding Configs

```bash
# Test config 1
export BRANDING_CONFIG_PATH=./test_configs/firm1.json
python -m src.web.app &
sleep 2
curl http://localhost:8000/landing | grep "Firm 1 Name"

# Test config 2
export BRANDING_CONFIG_PATH=./test_configs/firm2.json
export PORT=8001
python -m src.web.app &
sleep 2
curl http://localhost:8001/landing | grep "Firm 2 Name"
```

### Verify Environment Variables

```python
# test_config.py
from src.config.branding import get_branding_config

config = get_branding_config()
print(f"Platform: {config.platform_name}")
print(f"Company: {config.company_name}")
print(f"Primary Color: {config.primary_color}")
print(f"Support Email: {config.support_email}")

# Run
python test_config.py
```

Expected output:
```
Platform: TaxPro Online
Company: Smith & Associates, CPAs
Primary Color: #059669
Support Email: support@taxpro.com
```

---

## Migration from Hardcoded Values

### Before (Hardcoded - ❌)

```python
# Old code
platform_name = "CA4CPA GLOBAL LLC"

# Old template
<title>CA4CPA Tax Platform</title>
<style>
    .btn { background: #667eea; }
</style>
```

### After (Configuration-based - ✅)

```python
# New code
from src.config.branding import get_branding_config
config = get_branding_config()
platform_name = config.platform_name

# New template
<title>{{ branding.platform_name }}</title>
<style>
    .btn { background: {{ branding.primary_color }}; }
</style>
```

### Migration Checklist

- [x] Remove all hardcoded "CA4CPA" references
- [x] Remove all hardcoded color values (#667eea, #764ba2)
- [x] Remove all hardcoded company names
- [x] Replace with template variables
- [x] Create branding.py configuration system
- [x] Create .env.example with all options
- [x] Update app.py to inject branding into templates
- [x] Create BRANDING_CONFIGURATION.md documentation
- [x] Add branding step to DEPLOYMENT_GUIDE.md

---

## Best Practices

### ✅ DO

- **Store configs in version control** (except production secrets)
- **Use .env.example** to document all options
- **Default to sensible values** (don't require 50 env vars)
- **Validate configuration** on startup
- **Log configuration** (sanitized) for debugging
- **Test with multiple configs** before deployment
- **Document new config options** when adding features

### ❌ DON'T

- **Hardcode business logic** ("if company == 'X'")
- **Hardcode styling** (colors, fonts, sizes)
- **Hardcode text** (company names, messages)
- **Mix config and code** (keep config files separate)
- **Commit production secrets** (.env with real keys)
- **Require complex setup** (make defaults work)

---

## Validation

### Startup Validation

```python
# src/web/app.py startup

from src.config.branding import get_branding_config

config = get_branding_config()

# Validate required fields
assert config.platform_name, "PLATFORM_NAME is required"
assert config.company_name, "COMPANY_NAME is required"
assert config.support_email, "SUPPORT_EMAIL is required"
assert config.primary_color.startswith("#"), "BRAND_PRIMARY_COLOR must be hex"

print(f"✓ Branding configured for: {config.company_name}")
```

### Runtime Validation

```python
def validate_color(color: str) -> bool:
    """Ensure color is valid hex"""
    import re
    return bool(re.match(r'^#[0-9A-Fa-f]{6}$', color))

assert validate_color(config.primary_color), "Invalid primary color"
```

---

## Examples in Production

### Example 1: Small CPA Firm

```bash
PLATFORM_NAME="QuickTax Pro"
COMPANY_NAME="Johnson Tax Services"
BRAND_PRIMARY_COLOR="#10b981"
SUPPORT_EMAIL="help@johnsontax.com"
FILING_TIME_CLAIM="5 Minutes"
```

### Example 2: Large Enterprise

```bash
PLATFORM_NAME="Enterprise Tax Platform"
COMPANY_NAME="Global Tax Solutions LLC"
BRAND_PRIMARY_COLOR="#1e40af"
BRAND_LOGO_URL="https://cdn.globaltax.com/logo.svg"
SUPPORT_EMAIL="enterprise@globaltax.com"
FILING_TIME_CLAIM="10 Minutes"
SECURITY_CLAIM="SOC 2 Type II + GDPR Compliant"
CUSTOM_CSS_PATH="https://cdn.globaltax.com/custom.css"
```

### Example 3: Self-Hosted

```bash
PLATFORM_NAME="Internal Tax System"
COMPANY_NAME="Acme Corp Finance Dept"
BRAND_PRIMARY_COLOR="#6b7280"
SUPPORT_EMAIL="financeIT@acme.com"
FILING_TIME_CLAIM="Fast"
SECURITY_CLAIM="Internal Network Only"
```

---

## Benefits of Configuration-Based Architecture

1. **Rapid Deployment**: Deploy for new client in minutes, not weeks
2. **Code Reusability**: One codebase serves infinite brands
3. **Easy Maintenance**: Update branding without code changes
4. **A/B Testing**: Test different messaging/colors easily
5. **White-Labeling**: Resell platform under any brand
6. **Compliance**: Easily adjust for regional requirements
7. **Scalability**: Multi-tenant architecture ready

---

## Future Enhancements

### Planned Configuration Additions

- [ ] Theme presets (light, dark, high-contrast)
- [ ] Localization/i18n configuration
- [ ] Custom email templates via config
- [ ] PDF branding (letterhead, footer)
- [ ] Custom tax rules by jurisdiction
- [ ] Pricing tiers via configuration
- [ ] Integration configurations (Stripe, QuickBooks, etc.)

### Advanced Multi-Tenancy

```python
# Future: Database-driven tenant configs

class TenantConfig(BaseModel):
    tenant_id: str
    branding: BrandingConfig
    features: FeatureFlagConfig
    integrations: IntegrationConfig

# Load from database
tenant = get_tenant_by_domain(request.host)
branding = tenant.branding
```

---

## Conclusion

The Unified Tax Filing Platform is **100% configuration-driven** with:

- ✅ Zero hardcoded values
- ✅ Full white-label support
- ✅ Easy deployment for any CPA firm
- ✅ Multi-tenant ready
- ✅ Extensive documentation

**Next Steps**:
1. Copy `.env.example` to `.env`
2. Configure branding for your firm
3. Deploy and test
4. See [`docs/BRANDING_CONFIGURATION.md`](./BRANDING_CONFIGURATION.md) for full details
