# Branding Configuration Guide

## Overview

The platform is fully white-labelable and supports configuration-based branding without code changes. All platform-specific branding, naming, colors, and messaging can be customized via environment variables or a JSON configuration file.

## Quick Start

### Option 1: Environment Variables (Recommended for Production)

Set environment variables before starting the application:

```bash
export PLATFORM_NAME="TaxPro Online"
export COMPANY_NAME="Smith & Associates, CPAs"
export PLATFORM_TAGLINE="Professional Tax Filing Made Simple"
export BRAND_PRIMARY_COLOR="#059669"
export BRAND_SECONDARY_COLOR="#0891b2"
export SUPPORT_EMAIL="support@taxpro.com"
```

Then start the application:
```bash
python -m src.web.app
```

### Option 2: JSON Configuration File (Recommended for Development)

1. **Create a branding configuration file:**

```bash
python -m src.config.branding generic_cpa ./branding_config.json
```

Available templates:
- `generic_cpa` - Generic CPA firm branding
- `ca4cpa` - CA4CPA example configuration
- `boutique_firm` - Boutique CPA firm branding
- `self_hosted` - Internal use branding

2. **Point to your configuration file:**

```bash
export BRANDING_CONFIG_PATH=./branding_config.json
python -m src.web.app
```

3. **Customize the JSON file:**

```json
{
  "platform_name": "Your Platform Name",
  "company_name": "Your CPA Firm",
  "tagline": "Your Custom Tagline",
  "primary_color": "#667eea",
  "secondary_color": "#764ba2",
  "support_email": "support@yourfirm.com",
  "filing_time_claim": "3 Minutes",
  "security_claim": "Bank-level encryption",
  "review_claim": "CPA Reviewed"
}
```

---

## Configuration Options

### Identity & Naming

| Variable | Default | Description | Example |
|----------|---------|-------------|---------|
| `PLATFORM_NAME` | "Tax Filing Platform" | Platform/product name | "TaxPro Online" |
| `COMPANY_NAME` | "Your CPA Firm" | Legal company name | "Smith & Associates, CPAs" |
| `PLATFORM_TAGLINE` | "Professional Tax Filing Made Simple" | Marketing tagline | "Fast, Accurate, Professional" |

### Visual Branding

| Variable | Default | Description | Example |
|----------|---------|-------------|---------|
| `BRAND_PRIMARY_COLOR` | "#667eea" | Primary brand color (hex) | "#059669" |
| `BRAND_SECONDARY_COLOR` | "#764ba2" | Secondary/accent color (hex) | "#0891b2" |
| `BRAND_LOGO_URL` | None | URL to company logo | "/static/logo.png" |
| `BRAND_FAVICON_URL` | None | URL to favicon | "/static/favicon.ico" |

**Color Usage:**
- Primary color: Main buttons, progress bars, links, active states
- Secondary color: Gradients, hover states, accents

### Contact Information

| Variable | Default | Description | Example |
|----------|---------|-------------|---------|
| `SUPPORT_EMAIL` | "support@example.com" | Customer support email | "help@yourfirm.com" |
| `SUPPORT_PHONE` | None | Support phone number | "1-800-TAX-HELP" |
| `COMPANY_WEBSITE` | None | Company website URL | "https://yourfirm.com" |
| `COMPANY_ADDRESS` | None | Physical address | "123 Main St, City, ST 12345" |

### Feature Claims & Messaging

| Variable | Default | Description | Example |
|----------|---------|-------------|---------|
| `FILING_TIME_CLAIM` | "3 Minutes" | How long filing takes | "5 Minutes" |
| `SECURITY_CLAIM` | "Bank-level encryption" | Security messaging | "SOC 2 Type II Certified" |
| `REVIEW_CLAIM` | "CPA Reviewed" | Review process claim | "Partner-level Review" |

### SEO & Meta Tags

| Variable | Default | Description | Example |
|----------|---------|-------------|---------|
| `META_DESCRIPTION` | "File your taxes quickly..." | Page meta description | "Enterprise tax solutions..." |
| `META_KEYWORDS` | "tax filing, CPA..." | SEO keywords | "tax prep, professional..." |

### Legal Links

| Variable | Default | Description | Example |
|----------|---------|-------------|---------|
| `TERMS_URL` | None | Terms of service URL | "/legal/terms" |
| `PRIVACY_URL` | None | Privacy policy URL | "/legal/privacy" |

### Advanced Customization

| Variable | Default | Description | Example |
|----------|---------|-------------|---------|
| `CUSTOM_CSS_PATH` | None | Custom CSS file URL | "/static/custom.css" |
| `CUSTOM_JS_PATH` | None | Custom JavaScript URL | "/static/custom.js" |

---

## Example Configurations

### Example 1: Generic CPA Firm

```bash
# .env file
PLATFORM_NAME="TaxPro Online"
COMPANY_NAME="Your CPA Firm Name"
PLATFORM_TAGLINE="Simple, Fast, Professional"
BRAND_PRIMARY_COLOR="#059669"
BRAND_SECONDARY_COLOR="#0891b2"
SUPPORT_EMAIL="help@taxpro.com"
SUPPORT_PHONE="1-800-TAX-PRO"
FILING_TIME_CLAIM="3 Minutes"
SECURITY_CLAIM="Bank-level encryption"
REVIEW_CLAIM="CPA Reviewed"
```

### Example 2: Boutique Firm

```json
{
  "platform_name": "Elite Tax Services",
  "company_name": "Smith & Associates, CPAs",
  "tagline": "Personalized Tax Excellence",
  "primary_color": "#991b1b",
  "secondary_color": "#92400e",
  "logo_url": "/static/logo-elite.png",
  "support_email": "concierge@elitetax.com",
  "support_phone": "1-800-ELITE-TX",
  "filing_time_claim": "10 Minutes",
  "security_claim": "SOC 2 Type II Certified",
  "review_claim": "Partner-level Review",
  "terms_url": "/legal/terms",
  "privacy_url": "/legal/privacy",
  "company_address": "100 Wall Street, New York, NY 10005"
}
```

### Example 3: Enterprise Deployment

```bash
# Production .env
PLATFORM_NAME="Enterprise Tax Platform"
COMPANY_NAME="Global Tax Solutions LLC"
PLATFORM_TAGLINE="Enterprise-grade tax processing"
BRAND_PRIMARY_COLOR="#1e40af"
BRAND_SECONDARY_COLOR="#7c3aed"
BRAND_LOGO_URL="https://cdn.yourdomain.com/logo.svg"
BRAND_FAVICON_URL="https://cdn.yourdomain.com/favicon.ico"
SUPPORT_EMAIL="enterprise@globaltax.com"
SUPPORT_PHONE="+1-855-TAX-CORP"
FILING_TIME_CLAIM="5 Minutes"
SECURITY_CLAIM="Enterprise-grade security"
REVIEW_CLAIM="Multi-tier CPA Review"
CUSTOM_CSS_PATH="https://cdn.yourdomain.com/custom.css"
CUSTOM_JS_PATH="https://cdn.yourdomain.com/analytics.js"
META_DESCRIPTION="Enterprise tax filing platform for businesses of all sizes"
TERMS_URL="https://www.globaltax.com/terms"
PRIVACY_URL="https://www.globaltax.com/privacy"
COMPANY_WEBSITE="https://www.globaltax.com"
```

---

## Configuration Priority

The branding system loads configuration in this order (highest priority first):

1. **JSON config file** (if `BRANDING_CONFIG_PATH` is set)
2. **Environment variables** (individual overrides)
3. **Default values** (fallback)

Example:
```bash
# Use JSON for most settings
export BRANDING_CONFIG_PATH=./branding_config.json

# Override specific values via environment
export SUPPORT_EMAIL="support@newdomain.com"
export BRAND_PRIMARY_COLOR="#ff0000"

# Result: JSON config used, but email and color overridden
```

---

## Creating Custom Branding Configs

### Method 1: Generate from Template

```bash
# Generate a template configuration
python -m src.config.branding generic_cpa ./my_branding.json

# Edit the file
nano ./my_branding.json

# Use it
export BRANDING_CONFIG_PATH=./my_branding.json
```

### Method 2: Write from Scratch

Create `branding_config.json`:

```json
{
  "platform_name": "My Tax Platform",
  "company_name": "My CPA Firm",
  "tagline": "Your taxes, simplified",
  "primary_color": "#4f46e5",
  "secondary_color": "#7c3aed",
  "logo_url": "/static/my-logo.png",
  "support_email": "support@mycpafirm.com"
}
```

All fields are optional - unspecified fields use defaults.

---

## Logo & Favicon Guidelines

### Logo Requirements

- **Format**: SVG (preferred), PNG, or WebP
- **Dimensions**: Max width 200px, height auto-scaled
- **Background**: Transparent or white
- **Location**: Place in `/src/web/static/` directory
- **Usage**: Set `BRAND_LOGO_URL="/static/your-logo.svg"`

**Example:**
```bash
# Add logo to static directory
cp company-logo.svg /Users/rakeshanita/Jorss-Gbo/src/web/static/

# Configure in .env
export BRAND_LOGO_URL="/static/company-logo.svg"
```

### Favicon Requirements

- **Format**: ICO (preferred), PNG 32x32
- **Location**: Place in `/src/web/static/` directory
- **Usage**: Set `BRAND_FAVICON_URL="/static/favicon.ico"`

---

## Custom CSS & JavaScript

For advanced customization beyond colors and text:

### Custom CSS

Create `/src/web/static/custom.css`:

```css
/* Override specific styles */
.hero {
    background: url('/static/custom-bg.jpg');
}

.cta-button {
    border-radius: 4px !important; /* Square buttons */
    text-transform: uppercase;
}

/* Add custom fonts */
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap');

body {
    font-family: 'Poppins', sans-serif !important;
}
```

Configure:
```bash
export CUSTOM_CSS_PATH="/static/custom.css"
```

### Custom JavaScript

Create `/src/web/static/custom.js`:

```javascript
// Add custom analytics
window.addEventListener('DOMContentLoaded', () => {
    // Your custom tracking code
    console.log('Custom branding loaded');
});

// Override default behavior
function customFilingStarted() {
    // Custom event tracking
}
```

Configure:
```bash
export CUSTOM_JS_PATH="/static/custom.js"
```

---

## Testing Branding Configuration

### 1. Verify Configuration Loaded

```python
from src.config.branding import get_branding_config

config = get_branding_config()
print(f"Platform Name: {config.platform_name}")
print(f"Primary Color: {config.primary_color}")
print(f"Support Email: {config.support_email}")
```

### 2. Preview in Browser

```bash
# Start app with your config
export BRANDING_CONFIG_PATH=./my_branding.json
python -m src.web.app

# Visit http://localhost:8000/landing
```

### 3. Test Multiple Brands

```bash
# Test brand A
export BRANDING_CONFIG_PATH=./brand_a.json
python -m src.web.app &

# Test brand B (different port)
export BRANDING_CONFIG_PATH=./brand_b.json
export PORT=8001
python -m src.web.app &

# Compare at:
# - http://localhost:8000/landing (Brand A)
# - http://localhost:8001/landing (Brand B)
```

---

## Deployment Checklist

Before deploying with custom branding:

- [ ] All required variables set (at minimum: `PLATFORM_NAME`, `COMPANY_NAME`, `SUPPORT_EMAIL`)
- [ ] Logo and favicon files uploaded to `/static/` directory
- [ ] Logo URL and favicon URL configured correctly
- [ ] Primary and secondary colors match brand guidelines
- [ ] Tested all pages: `/landing`, `/file`, `/results`
- [ ] Mobile responsiveness verified
- [ ] Custom CSS/JS tested (if used)
- [ ] Legal links configured (terms, privacy) if required
- [ ] Support email tested and monitored
- [ ] Analytics tracking configured (if custom JS used)

---

## Troubleshooting

### Issue: Changes Not Appearing

**Cause**: Configuration cached in memory

**Solution**: Restart the application
```bash
# Kill and restart
pkill -f "python.*src.web.app"
python -m src.web.app
```

Or force cache reset:
```python
from src.config.branding import reset_branding_config
reset_branding_config()
```

### Issue: Colors Not Showing

**Cause**: Invalid hex color format

**Solution**: Ensure colors start with `#` and are 6 digits:
```bash
# Wrong
export BRAND_PRIMARY_COLOR="667eea"

# Correct
export BRAND_PRIMARY_COLOR="#667eea"
```

### Issue: Logo Not Displaying

**Cause**: Incorrect file path or missing file

**Solution**:
1. Verify file exists: `ls src/web/static/your-logo.png`
2. Check path starts with `/static/`: `BRAND_LOGO_URL="/static/your-logo.png"`
3. Verify file permissions: `chmod 644 src/web/static/your-logo.png`

### Issue: JSON Config Ignored

**Cause**: Environment variable not set or file not found

**Solution**:
```bash
# Verify path is absolute or relative to working directory
export BRANDING_CONFIG_PATH="$(pwd)/branding_config.json"

# Check file exists
cat $BRANDING_CONFIG_PATH
```

---

## Best Practices

1. **Use JSON configs for development**, environment variables for production
2. **Store branding configs in version control** (except production credentials)
3. **Document custom CSS/JS** if used for future maintainers
4. **Test mobile responsiveness** after color changes
5. **Use SVG logos** when possible for scalability
6. **Keep color contrast accessible** (WCAG AA minimum)
7. **Version your branding configs**: `branding_v1.json`, `branding_v2.json`
8. **Use CDN for logos** in production for performance

---

## Multi-Tenant Setup

To support multiple CPA firms on one deployment:

```python
# In src/web/app.py (advanced customization)

from src.config.branding import BrandingConfig

# Map domains to branding configs
TENANT_BRANDING = {
    "firm1.taxpro.com": BrandingConfig(
        platform_name="Firm 1 Tax",
        company_name="First CPA Firm",
        primary_color="#059669"
    ),
    "firm2.taxpro.com": BrandingConfig(
        platform_name="Firm 2 Tax",
        company_name="Second CPA Firm",
        primary_color="#dc2626"
    )
}

# Middleware to inject tenant-specific branding
@app.middleware("http")
async def tenant_branding_middleware(request: Request, call_next):
    host = request.headers.get("host", "").split(":")[0]
    tenant_config = TENANT_BRANDING.get(host)

    if tenant_config:
        request.state.branding = tenant_config

    return await call_next(request)
```

---

## Support

For branding configuration assistance:
- Check examples in `src/config/branding.py`
- Review generated templates: `python -m src.config.branding <template_name>`
- Test configuration: `python -c "from src.config.branding import get_branding_config; print(get_branding_config().to_dict())"`

For technical issues, see main documentation or contact platform support.
