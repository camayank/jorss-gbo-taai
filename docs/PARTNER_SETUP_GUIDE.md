# White-Label Partner Setup Guide

## For Sales, Support & Product Teams

**Version:** 1.0
**Last Updated:** January 2026

---

## Table of Contents

1. [Overview](#overview)
2. [Current Setup Process (Manual)](#current-setup-process-manual)
3. [Step-by-Step Partner Onboarding](#step-by-step-partner-onboarding)
4. [Branding Configuration](#branding-configuration)
5. [What Partners Get](#what-partners-get)
6. [Current Limitations](#current-limitations)
7. [Development Roadmap](#development-roadmap)
8. [FAQ for Sales Team](#faq-for-sales-team)

---

## Overview

### What is White-Label?

White-label allows accounting firms, tax software resellers, and industry partners to offer our Tax Decision Intelligence Platform under their own brand.

### Current Capability Summary

| Feature | Status | Notes |
|---------|--------|-------|
| Partner account creation | ✅ Ready | Admin Panel → Partners |
| Revenue share tracking | ✅ Ready | Configurable 0-50% |
| Firm assignment to partner | ✅ Ready | Via partner_id |
| Firm branding (colors) | ✅ Ready | Primary/secondary colors |
| Logo support | ⚠️ URL only | No upload, must host externally |
| Custom domain | ⚠️ Manual | Requires DNS/SSL setup |
| Partner self-service portal | ❌ Not built | Partners use admin panel |
| Branding inheritance | ❌ Not built | Each firm configured separately |

---

## Current Setup Process (Manual)

### Time Required: 30-45 minutes per partner

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     CURRENT PARTNER SETUP FLOW                          │
│                                                                         │
│  PLATFORM ADMIN                         PARTNER                         │
│  ─────────────────                      ───────                         │
│                                                                         │
│  1. Create partner account              (Waits)                         │
│         ↓                                                               │
│  2. Get branding assets ←───────────── Sends logo, colors, domain      │
│         ↓                                                               │
│  3. Host logo externally               (Waits)                         │
│         ↓                                                               │
│  4. Create firm(s) under partner       (Waits)                         │
│         ↓                                                               │
│  5. Configure firm branding            (Waits)                         │
│         ↓                                                               │
│  6. Create admin user ──────────────→  Receives credentials            │
│         ↓                                                               │
│  7. Configure custom domain            Points DNS                       │
│     (if Enterprise)                           ↓                         │
│         ↓                               Confirms working                │
│  8. Verify & handoff ───────────────→  Partner live!                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step Partner Onboarding

### Prerequisites Checklist

Before starting, collect from the partner:

- [ ] Company name (legal name for billing)
- [ ] Primary contact name and email
- [ ] Domain name (if custom domain desired)
- [ ] Logo file (PNG/SVG, min 200x200px)
- [ ] Brand colors (primary and secondary hex codes)
- [ ] Agreed revenue share percentage
- [ ] Subscription tier (Professional or Enterprise)

---

### Step 1: Create Partner Account

**Location:** Admin Panel → Partners → Add Partner

1. Navigate to `/admin` and log in as platform admin
2. Click "Partners" in the sidebar
3. Click "+ Add Partner" button
4. Fill in the form:

| Field | Description | Example |
|-------|-------------|---------|
| Partner Name | Display name | "TaxPro Solutions" |
| Domain | Partner's domain | "taxpro.com" |
| Contact Email | Primary contact | "admin@taxpro.com" |
| Revenue Share % | Commission rate | 15 |

5. Click "Add Partner"
6. Note the `partner_id` from the partners list

**API Alternative:**
```bash
curl -X POST "https://api.taxflow.com/api/v1/admin/partners" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "TaxPro Solutions",
    "domain": "taxpro.com",
    "contact_email": "admin@taxpro.com",
    "revenue_share_percent": 15
  }'
```

---

### Step 2: Host Partner Logo

**Current Limitation:** Logo must be hosted externally (no upload feature yet)

**Options:**

1. **Use partner's existing CDN/website**
   - Ask partner for logo URL: `https://taxpro.com/assets/logo.png`

2. **Host on our CDN (if available)**
   - Upload to S3/CloudFront bucket
   - Generate public URL

3. **Use logo hosting service**
   - Cloudinary, imgbb, or similar
   - Generate permanent URL

**Logo Requirements:**
- Format: PNG or SVG (transparent background preferred)
- Minimum size: 200x200px
- Maximum file size: 500KB
- Aspect ratio: Square or horizontal (not vertical)

---

### Step 3: Create Firm Under Partner

**Location:** Admin Panel → Firms → Add Firm

1. Click "Firms" in the sidebar
2. Click "+ Add Firm" button
3. Fill in the form:

| Field | Description | Example |
|-------|-------------|---------|
| Firm Name | CPA firm name | "Smith & Associates CPA" |
| Legal Name | For billing | "Smith Associates LLC" |
| Email | Firm contact | "office@smithcpa.com" |
| Subscription Tier | Plan level | Professional |
| Partner | Select partner | "TaxPro Solutions" |

4. Click "Create Firm"
5. Note the `firm_id`

---

### Step 4: Configure Firm Branding

**Location:** Admin Panel → Firms → [Select Firm] → Settings

**Or via API:**
```bash
curl -X PUT "https://api.taxflow.com/api/v1/admin/firms/{firm_id}/settings/branding" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "primary_color": "#2563eb",
    "secondary_color": "#1e40af",
    "logo_url": "https://taxpro.com/assets/logo.png",
    "email_signature": "Powered by TaxPro Solutions",
    "welcome_message": "Welcome to TaxPro Tax Intelligence",
    "disclaimer_text": "Advisory services provided by TaxPro Solutions."
  }'
```

**Branding Fields:**

| Field | Purpose | Example |
|-------|---------|---------|
| `primary_color` | Main brand color (buttons, links) | `#2563eb` |
| `secondary_color` | Accent color | `#1e40af` |
| `logo_url` | Header logo | `https://...` |
| `email_signature` | Footer in emails | "Powered by TaxPro" |
| `welcome_message` | Client portal greeting | "Welcome to TaxPro" |
| `disclaimer_text` | Legal disclaimer | "Advisory by TaxPro" |

---

### Step 5: Create Firm Admin User

**Location:** Admin Panel → Users → Add User

1. Click "Users" in the sidebar
2. Click "+ Add User" button
3. Fill in the form:

| Field | Value |
|-------|-------|
| Email | partner's admin email |
| First Name | Admin's first name |
| Last Name | Admin's last name |
| Firm | Select the firm created |
| Role | Firm Admin |

4. Click "Create User"
5. System sends invitation email with password setup link

**Communicate to Partner:**
- Login URL: `https://app.taxflow.com/login` (or custom domain)
- Username: Their email
- Password: Set via email link

---

### Step 6: Custom Domain Setup (Enterprise Only)

**Requirements:**
- Enterprise subscription tier
- Partner owns the domain
- DNS access

**Process:**

1. **Partner adds DNS records:**
   ```
   Type: CNAME
   Name: app (or desired subdomain)
   Value: custom.taxflow.com
   TTL: 300
   ```

2. **Platform admin configures:**
   - Add domain to SSL certificate
   - Configure routing in load balancer
   - Update firm settings with custom domain

3. **Verification:**
   - Wait for DNS propagation (up to 48 hours)
   - Test: `https://app.taxpro.com` should load

**Current Limitation:** This is a manual DevOps process. No self-service.

---

### Step 7: Final Verification Checklist

Before handoff to partner, verify:

- [ ] Partner can log in to admin panel
- [ ] Branding appears correctly (logo, colors)
- [ ] Partner can create/manage clients
- [ ] Partner can access CPA panel features
- [ ] Custom domain works (if applicable)
- [ ] Email templates show correct branding
- [ ] Partner understands their dashboard

---

## Branding Configuration

### Where Branding Appears

| Location | Branded Elements |
|----------|-----------------|
| Login page | Logo, primary color |
| CPA Dashboard | Logo in header, primary color for buttons |
| Client Portal | Logo, welcome message, colors |
| Email notifications | Logo, email signature, disclaimer |
| PDF reports | Logo, firm name (planned) |

### Color Guidelines

```
PRIMARY COLOR: Main interactive elements
├── Buttons (primary action)
├── Links
├── Active states
├── Progress indicators
└── Headers

SECONDARY COLOR: Supporting elements
├── Hover states
├── Borders/accents
├── Secondary buttons
└── Icons
```

### Testing Branding

After configuration, test in:
1. **CPA Panel** (`/cpa`) - Check header logo, button colors
2. **Client Portal** (`/`) - Check welcome message, colors
3. **Print view** - Generate report, verify logo appears

---

## What Partners Get

### By Subscription Tier

| Feature | Professional | Enterprise |
|---------|:------------:|:----------:|
| White-label branding | ✅ | ✅ |
| Custom colors | ✅ | ✅ |
| Logo placement | ✅ | ✅ |
| Custom domain | ❌ | ✅ |
| API access | ❌ | ✅ |
| Revenue share dashboard | ✅ | ✅ |
| Multiple firms | Up to 5 | Unlimited |
| Dedicated support | ❌ | ✅ |

### Partner Revenue Share

Partners receive commission on subscription revenue from firms under them:

```
Monthly Partner Revenue = Sum(Firm MRR) × Revenue Share %

Example:
- 10 firms × $299/month average = $2,990 MRR
- 15% revenue share
- Partner receives: $448.50/month
```

Tracked in: Admin Panel → Partners → [Partner] → Revenue

---

## Current Limitations

### What We Can't Do Yet

| Limitation | Workaround | Priority |
|------------|------------|----------|
| **No logo upload** | Host externally, provide URL | High |
| **No branding preview** | Test in staging first | Medium |
| **No partner self-service** | Platform admin does setup | High |
| **No branding inheritance** | Configure each firm manually | Medium |
| **No automated custom domain** | Manual DevOps process | Low |
| **PDFs not branded** | Generic reports only | Medium |
| **No partner dashboard** | Use admin panel metrics | Medium |

### Common Issues

1. **Logo not appearing**
   - Check URL is publicly accessible
   - Verify CORS headers allow embedding
   - Check image format (PNG/SVG only)

2. **Colors not applying**
   - Clear browser cache
   - Verify hex format: `#RRGGBB`
   - Check firm settings saved successfully

3. **Custom domain not working**
   - DNS propagation takes up to 48 hours
   - Verify CNAME record is correct
   - Check SSL certificate includes domain

---

## Development Roadmap

### What Needs to Be Built

#### Phase 1: Quick Wins (1-2 weeks)

| Feature | Effort | Impact |
|---------|--------|--------|
| **Logo upload** | 2 days | High - Removes external hosting need |
| **Branding preview** | 1 day | Medium - Better UX |
| **Partner setup wizard** | 2 days | High - Guided onboarding |
| **This documentation** | Done | High - Sales enablement |

**Logo Upload Implementation:**
```
Required:
1. Add file input to firm settings
2. Backend endpoint: POST /api/v1/admin/firms/{id}/logo
3. S3/storage integration for file storage
4. Serve via CDN with caching
5. Update branding_logo_url automatically
```

**Branding Preview Implementation:**
```
Required:
1. Preview panel in settings page
2. Live color picker with instant preview
3. Sample components showing branding
4. "Apply" vs "Preview" modes
```

#### Phase 2: Partner Experience (2-4 weeks)

| Feature | Effort | Impact |
|---------|--------|--------|
| **Partner portal** | 1 week | High - Self-service |
| **Branding inheritance** | 3 days | Medium - Efficiency |
| **Partner onboarding wizard** | 3 days | High - Conversion |
| **Partner revenue dashboard** | 2 days | Medium - Transparency |

**Partner Portal Scope:**
```
Separate login for partners with:
├── Dashboard (firms, revenue, metrics)
├── Firm management (add/edit firms)
├── Branding settings (applies to all firms)
├── User management (for their firms)
├── Billing/invoices
└── Support tickets
```

#### Phase 3: Enterprise Features (4-8 weeks)

| Feature | Effort | Impact |
|---------|--------|--------|
| **Automated custom domains** | 1 week | High - Enterprise sales |
| **Branded PDF reports** | 1 week | Medium - Professional output |
| **Partner API** | 1 week | Medium - Integrations |
| **SSO/SAML for partners** | 1 week | Low - Enterprise requirement |

---

## FAQ for Sales Team

### Pre-Sales Questions

**Q: How quickly can we onboard a new partner?**
> Currently: 30-45 minutes with platform admin assistance.
> With planned improvements: 5-10 minutes self-service.

**Q: Can partners use their own domain?**
> Yes, with Enterprise tier. Requires manual DNS setup (24-48 hours).

**Q: What branding can be customized?**
> Logo, primary/secondary colors, welcome messages, email signatures, disclaimers.
> NOT customizable yet: Full CSS themes, layout changes, feature toggles.

**Q: Do partners see our branding anywhere?**
> No. With proper branding setup, end-users only see partner's brand.
> Exception: Browser tab title shows "TaxFlow" (configurable in Enterprise).

**Q: What's the minimum commitment?**
> Professional tier: $299/month per firm, minimum 1 firm.
> Enterprise tier: $599/month, includes custom domain.

### Technical Questions

**Q: Can partners integrate with their existing systems?**
> Enterprise tier includes API access. Professional does not.

**Q: Is data isolated between partners?**
> Yes. Complete multi-tenant isolation. Partners cannot see other partners' data.

**Q: Can we demo white-label to prospects?**
> Yes. Create a demo partner account with their branding. Takes ~15 minutes.

### Objection Handling

**"Setup seems complicated"**
> We handle all technical setup. Partner just provides logo and colors.
> Roadmap includes self-service portal for faster onboarding.

**"We need our own domain"**
> Available in Enterprise tier. We handle SSL and routing.

**"What if we need custom features?"**
> Enterprise includes dedicated support and custom development options.

---

## Appendix: Quick Reference

### API Endpoints for Partner Management

```
Partners:
GET    /api/v1/admin/partners              List all partners
POST   /api/v1/admin/partners              Create partner
GET    /api/v1/admin/partners/{id}         Get partner details
PUT    /api/v1/admin/partners/{id}         Update partner
GET    /api/v1/admin/partners/{id}/firms   List partner's firms

Firm Branding:
GET    /api/v1/admin/firms/{id}/settings           Get all settings
PUT    /api/v1/admin/firms/{id}/settings/branding  Update branding
```

### Branding Color Presets

For quick setup, suggest these tested color combinations:

| Style | Primary | Secondary |
|-------|---------|-----------|
| Professional Blue | `#2563eb` | `#1e40af` |
| Corporate Green | `#059669` | `#047857` |
| Modern Purple | `#7c3aed` | `#6d28d9` |
| Trust Navy | `#1e3a5f` | `#0f172a` |
| Warm Orange | `#ea580c` | `#c2410c` |

---

*Document maintained by Product Team. For questions, contact product@taxflow.com*
