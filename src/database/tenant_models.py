"""
Multi-Tenant White-Label Database Models

Supports:
- Platform-level tenants (different CPA firms)
- Sub-branding for individual CPAs within firms
- Hierarchical branding (Platform → Tenant → CPA → Client)
- Custom domains and themes
- Feature flags per tenant
- Billing and subscription management
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
import json


class TenantStatus(Enum):
    """Tenant account status"""
    ACTIVE = "active"
    TRIAL = "trial"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    PENDING_SETUP = "pending_setup"


class SubscriptionTier(Enum):
    """Subscription tiers with different feature access"""
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"
    WHITE_LABEL = "white_label"


class ThemePreset(Enum):
    """Pre-built theme presets"""
    PROFESSIONAL_BLUE = "professional_blue"
    MODERN_GREEN = "modern_green"
    CORPORATE_GRAY = "corporate_gray"
    BOUTIQUE_PURPLE = "boutique_purple"
    CLASSIC_NAVY = "classic_navy"
    CUSTOM = "custom"


@dataclass
class TenantBranding:
    """Complete branding configuration for a tenant"""

    # Identity
    platform_name: str = "Tax Filing Platform"
    company_name: str = "Your CPA Firm"
    tagline: str = "Professional Tax Filing Made Simple"

    # Visual Design
    theme_preset: ThemePreset = ThemePreset.PROFESSIONAL_BLUE
    primary_color: str = "#667eea"
    secondary_color: str = "#764ba2"
    accent_color: str = "#48bb78"

    # Advanced Colors
    text_color: str = "#2d3748"
    background_color: str = "#ffffff"
    sidebar_color: str = "#f7fafc"
    header_color: str = "#ffffff"

    # Typography
    font_family: str = "system-ui, -apple-system, sans-serif"
    heading_font: Optional[str] = None
    font_size_base: str = "16px"

    # Logo & Assets
    logo_url: Optional[str] = None
    logo_dark_url: Optional[str] = None  # For dark mode
    favicon_url: Optional[str] = None
    background_image_url: Optional[str] = None

    # Contact Information
    support_email: str = "support@example.com"
    support_phone: Optional[str] = None
    website_url: Optional[str] = None
    company_address: Optional[str] = None

    # Social Media
    facebook_url: Optional[str] = None
    twitter_url: Optional[str] = None
    linkedin_url: Optional[str] = None

    # Messaging & Claims
    filing_time_claim: str = "3 Minutes"
    security_claim: str = "Bank-level encryption"
    review_claim: str = "CPA Reviewed"
    value_proposition: str = "Fast, Secure, Professional"

    # Legal
    terms_url: Optional[str] = None
    privacy_url: Optional[str] = None

    # SEO
    meta_description: str = "Professional tax filing platform"
    meta_keywords: str = "tax filing, CPA, tax preparation"

    # Custom CSS/JS
    custom_css: Optional[str] = None
    custom_js: Optional[str] = None
    custom_head_html: Optional[str] = None  # For analytics, etc.

    # Email Branding
    email_header_color: Optional[str] = None
    email_footer_text: Optional[str] = None

    # Advanced Options
    show_powered_by: bool = False  # "Powered by [Platform]"
    allow_sub_branding: bool = True  # CPAs can customize

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON storage"""
        return {
            'platform_name': self.platform_name,
            'company_name': self.company_name,
            'tagline': self.tagline,
            'theme_preset': self.theme_preset.value,
            'primary_color': self.primary_color,
            'secondary_color': self.secondary_color,
            'accent_color': self.accent_color,
            'text_color': self.text_color,
            'background_color': self.background_color,
            'sidebar_color': self.sidebar_color,
            'header_color': self.header_color,
            'font_family': self.font_family,
            'heading_font': self.heading_font,
            'font_size_base': self.font_size_base,
            'logo_url': self.logo_url,
            'logo_dark_url': self.logo_dark_url,
            'favicon_url': self.favicon_url,
            'background_image_url': self.background_image_url,
            'support_email': self.support_email,
            'support_phone': self.support_phone,
            'website_url': self.website_url,
            'company_address': self.company_address,
            'facebook_url': self.facebook_url,
            'twitter_url': self.twitter_url,
            'linkedin_url': self.linkedin_url,
            'filing_time_claim': self.filing_time_claim,
            'security_claim': self.security_claim,
            'review_claim': self.review_claim,
            'value_proposition': self.value_proposition,
            'terms_url': self.terms_url,
            'privacy_url': self.privacy_url,
            'meta_description': self.meta_description,
            'meta_keywords': self.meta_keywords,
            'custom_css': self.custom_css,
            'custom_js': self.custom_js,
            'custom_head_html': self.custom_head_html,
            'email_header_color': self.email_header_color,
            'email_footer_text': self.email_footer_text,
            'show_powered_by': self.show_powered_by,
            'allow_sub_branding': self.allow_sub_branding,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TenantBranding':
        """Create from dictionary"""
        if 'theme_preset' in data and isinstance(data['theme_preset'], str):
            data['theme_preset'] = ThemePreset(data['theme_preset'])
        return cls(**data)


@dataclass
class TenantFeatureFlags:
    """Feature flags for tenant-specific features"""

    # Core Features
    express_lane_enabled: bool = True
    smart_tax_enabled: bool = True
    ai_chat_enabled: bool = True
    guided_forms_enabled: bool = True

    # Advanced Features
    scenario_explorer_enabled: bool = True
    tax_projections_enabled: bool = True
    document_vault_enabled: bool = True
    e_signature_enabled: bool = True

    # AI Features
    ai_assistant_enabled: bool = False
    ocr_enabled: bool = True
    intelligent_extraction: bool = True

    # Integration Features
    quickbooks_integration: bool = False
    stripe_integration: bool = True
    plaid_integration: bool = False

    # CPA Features
    cpa_dashboard_enabled: bool = True
    multi_cpa_support: bool = True
    cpa_collaboration: bool = False

    # Client Features
    client_portal_enabled: bool = True
    client_messaging: bool = True
    client_document_upload: bool = True

    # White-Label Features
    custom_domain_enabled: bool = False
    remove_branding: bool = False
    custom_email_templates: bool = False
    api_access_enabled: bool = False

    # Limits
    max_returns_per_month: Optional[int] = None
    max_cpas: Optional[int] = None
    max_clients_per_cpa: Optional[int] = None
    max_storage_gb: Optional[int] = 10

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'express_lane_enabled': self.express_lane_enabled,
            'smart_tax_enabled': self.smart_tax_enabled,
            'ai_chat_enabled': self.ai_chat_enabled,
            'guided_forms_enabled': self.guided_forms_enabled,
            'scenario_explorer_enabled': self.scenario_explorer_enabled,
            'tax_projections_enabled': self.tax_projections_enabled,
            'document_vault_enabled': self.document_vault_enabled,
            'e_signature_enabled': self.e_signature_enabled,
            'ai_assistant_enabled': self.ai_assistant_enabled,
            'ocr_enabled': self.ocr_enabled,
            'intelligent_extraction': self.intelligent_extraction,
            'quickbooks_integration': self.quickbooks_integration,
            'stripe_integration': self.stripe_integration,
            'plaid_integration': self.plaid_integration,
            'cpa_dashboard_enabled': self.cpa_dashboard_enabled,
            'multi_cpa_support': self.multi_cpa_support,
            'cpa_collaboration': self.cpa_collaboration,
            'client_portal_enabled': self.client_portal_enabled,
            'client_messaging': self.client_messaging,
            'client_document_upload': self.client_document_upload,
            'custom_domain_enabled': self.custom_domain_enabled,
            'remove_branding': self.remove_branding,
            'custom_email_templates': self.custom_email_templates,
            'api_access_enabled': self.api_access_enabled,
            'max_returns_per_month': self.max_returns_per_month,
            'max_cpas': self.max_cpas,
            'max_clients_per_cpa': self.max_clients_per_cpa,
            'max_storage_gb': self.max_storage_gb,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TenantFeatureFlags':
        """Create from dictionary"""
        return cls(**data)


@dataclass
class Tenant:
    """
    Main tenant entity representing a CPA firm or organization.
    Each tenant has its own branding, features, and data isolation.
    """

    tenant_id: str
    tenant_name: str

    # Status & Subscription
    status: TenantStatus = TenantStatus.PENDING_SETUP
    subscription_tier: SubscriptionTier = SubscriptionTier.FREE

    # Branding
    branding: TenantBranding = field(default_factory=TenantBranding)

    # Features
    features: TenantFeatureFlags = field(default_factory=TenantFeatureFlags)

    # Custom Domain
    custom_domain: Optional[str] = None
    custom_domain_verified: bool = False

    # Admin Contact
    admin_user_id: Optional[str] = None
    admin_email: str = ""

    # Billing
    stripe_customer_id: Optional[str] = None
    subscription_expires_at: Optional[datetime] = None

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Stats (denormalized for quick access)
    total_returns: int = 0
    total_cpas: int = 0
    total_clients: int = 0
    storage_used_gb: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'tenant_id': self.tenant_id,
            'tenant_name': self.tenant_name,
            'status': self.status.value,
            'subscription_tier': self.subscription_tier.value,
            'branding': self.branding.to_dict(),
            'features': self.features.to_dict(),
            'custom_domain': self.custom_domain,
            'custom_domain_verified': self.custom_domain_verified,
            'admin_user_id': self.admin_user_id,
            'admin_email': self.admin_email,
            'stripe_customer_id': self.stripe_customer_id,
            'subscription_expires_at': self.subscription_expires_at.isoformat() if self.subscription_expires_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'metadata': self.metadata,
            'total_returns': self.total_returns,
            'total_cpas': self.total_cpas,
            'total_clients': self.total_clients,
            'storage_used_gb': self.storage_used_gb,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Tenant':
        """Create from dictionary"""
        # Convert enums
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = TenantStatus(data['status'])
        if 'subscription_tier' in data and isinstance(data['subscription_tier'], str):
            data['subscription_tier'] = SubscriptionTier(data['subscription_tier'])

        # Convert nested objects
        if 'branding' in data and isinstance(data['branding'], dict):
            data['branding'] = TenantBranding.from_dict(data['branding'])
        if 'features' in data and isinstance(data['features'], dict):
            data['features'] = TenantFeatureFlags.from_dict(data['features'])

        # Convert dates
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        if 'subscription_expires_at' in data and isinstance(data['subscription_expires_at'], str):
            data['subscription_expires_at'] = datetime.fromisoformat(data['subscription_expires_at'])

        return cls(**data)


@dataclass
class CPABranding:
    """
    CPA-level branding (sub-branding within a tenant).
    Inherits from tenant branding but can override specific elements.
    """

    cpa_id: str
    tenant_id: str

    # Identity Overrides (optional)
    display_name: Optional[str] = None  # e.g., "John Smith, CPA"
    tagline: Optional[str] = None

    # Visual Overrides
    accent_color: Optional[str] = None  # Can customize accent only

    # Assets
    firm_logo_url: Optional[str] = None  # Firm/CPA logo for reports
    profile_photo_url: Optional[str] = None
    signature_image_url: Optional[str] = None

    # Contact Overrides
    direct_email: Optional[str] = None
    direct_phone: Optional[str] = None
    office_address: Optional[str] = None

    # Bio & Credentials
    bio: Optional[str] = None
    credentials: List[str] = field(default_factory=list)  # ["CPA", "CFP", "EA"]
    years_experience: Optional[int] = None
    specializations: List[str] = field(default_factory=list)

    # Custom Client Portal Message
    welcome_message: Optional[str] = None

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'cpa_id': self.cpa_id,
            'tenant_id': self.tenant_id,
            'display_name': self.display_name,
            'tagline': self.tagline,
            'accent_color': self.accent_color,
            'firm_logo_url': self.firm_logo_url,
            'profile_photo_url': self.profile_photo_url,
            'signature_image_url': self.signature_image_url,
            'direct_email': self.direct_email,
            'direct_phone': self.direct_phone,
            'office_address': self.office_address,
            'bio': self.bio,
            'credentials': self.credentials,
            'years_experience': self.years_experience,
            'specializations': self.specializations,
            'welcome_message': self.welcome_message,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CPABranding':
        """Create from dictionary"""
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        return cls(**data)


# Pre-built theme configurations
THEME_PRESETS = {
    ThemePreset.PROFESSIONAL_BLUE: {
        'primary_color': '#1e3a5f',
        'secondary_color': '#5387c1',
        'accent_color': '#60a5fa',
        'text_color': '#1f2937',
        'background_color': '#ffffff',
        'sidebar_color': '#f3f4f6',
        'header_color': '#ffffff',
    },
    ThemePreset.MODERN_GREEN: {
        'primary_color': '#059669',
        'secondary_color': '#10b981',
        'accent_color': '#34d399',
        'text_color': '#1f2937',
        'background_color': '#ffffff',
        'sidebar_color': '#f0fdf4',
        'header_color': '#ffffff',
    },
    ThemePreset.CORPORATE_GRAY: {
        'primary_color': '#374151',
        'secondary_color': '#6b7280',
        'accent_color': '#9ca3af',
        'text_color': '#111827',
        'background_color': '#ffffff',
        'sidebar_color': '#f9fafb',
        'header_color': '#ffffff',
    },
    ThemePreset.BOUTIQUE_PURPLE: {
        'primary_color': '#0d9488',
        'secondary_color': '#a78bfa',
        'accent_color': '#c4b5fd',
        'text_color': '#1f2937',
        'background_color': '#ffffff',
        'sidebar_color': '#faf5ff',
        'header_color': '#ffffff',
    },
    ThemePreset.CLASSIC_NAVY: {
        'primary_color': '#0c1b2f',
        'secondary_color': '#5387c1',
        'accent_color': '#60a5fa',
        'text_color': '#1f2937',
        'background_color': '#ffffff',
        'sidebar_color': '#eff6ff',
        'header_color': '#ffffff',
    },
}


def apply_theme_preset(branding: TenantBranding, preset: ThemePreset) -> TenantBranding:
    """Apply a pre-built theme preset to branding"""
    if preset == ThemePreset.CUSTOM:
        return branding

    theme_colors = THEME_PRESETS.get(preset, {})

    for key, value in theme_colors.items():
        setattr(branding, key, value)

    branding.theme_preset = preset
    return branding


def get_subscription_features(tier: SubscriptionTier) -> TenantFeatureFlags:
    """Get default feature flags for a subscription tier"""

    if tier == SubscriptionTier.FREE:
        return TenantFeatureFlags(
            express_lane_enabled=True,
            smart_tax_enabled=False,
            ai_chat_enabled=False,
            scenario_explorer_enabled=False,
            tax_projections_enabled=False,
            ai_assistant_enabled=False,
            quickbooks_integration=False,
            custom_domain_enabled=False,
            max_returns_per_month=5,
            max_cpas=1,
            max_clients_per_cpa=10,
            max_storage_gb=1,
        )

    elif tier == SubscriptionTier.STARTER:
        return TenantFeatureFlags(
            express_lane_enabled=True,
            smart_tax_enabled=True,
            ai_chat_enabled=False,
            scenario_explorer_enabled=True,
            tax_projections_enabled=True,
            ai_assistant_enabled=False,
            quickbooks_integration=False,
            custom_domain_enabled=False,
            max_returns_per_month=50,
            max_cpas=3,
            max_clients_per_cpa=50,
            max_storage_gb=10,
        )

    elif tier == SubscriptionTier.PROFESSIONAL:
        return TenantFeatureFlags(
            express_lane_enabled=True,
            smart_tax_enabled=True,
            ai_chat_enabled=True,
            scenario_explorer_enabled=True,
            tax_projections_enabled=True,
            ai_assistant_enabled=True,
            quickbooks_integration=True,
            custom_domain_enabled=False,
            max_returns_per_month=200,
            max_cpas=10,
            max_clients_per_cpa=200,
            max_storage_gb=50,
        )

    elif tier == SubscriptionTier.ENTERPRISE:
        return TenantFeatureFlags(
            express_lane_enabled=True,
            smart_tax_enabled=True,
            ai_chat_enabled=True,
            scenario_explorer_enabled=True,
            tax_projections_enabled=True,
            ai_assistant_enabled=True,
            quickbooks_integration=True,
            plaid_integration=True,
            cpa_collaboration=True,
            custom_domain_enabled=True,
            custom_email_templates=True,
            api_access_enabled=True,
            max_returns_per_month=None,  # Unlimited
            max_cpas=None,  # Unlimited
            max_clients_per_cpa=None,  # Unlimited
            max_storage_gb=500,
        )

    elif tier == SubscriptionTier.WHITE_LABEL:
        return TenantFeatureFlags(
            express_lane_enabled=True,
            smart_tax_enabled=True,
            ai_chat_enabled=True,
            guided_forms_enabled=True,
            scenario_explorer_enabled=True,
            tax_projections_enabled=True,
            document_vault_enabled=True,
            e_signature_enabled=True,
            ai_assistant_enabled=True,
            ocr_enabled=True,
            intelligent_extraction=True,
            quickbooks_integration=True,
            stripe_integration=True,
            plaid_integration=True,
            cpa_dashboard_enabled=True,
            multi_cpa_support=True,
            cpa_collaboration=True,
            client_portal_enabled=True,
            client_messaging=True,
            client_document_upload=True,
            custom_domain_enabled=True,
            remove_branding=True,
            custom_email_templates=True,
            api_access_enabled=True,
            max_returns_per_month=None,  # Unlimited
            max_cpas=None,  # Unlimited
            max_clients_per_cpa=None,  # Unlimited
            max_storage_gb=None,  # Unlimited
        )

    return TenantFeatureFlags()
