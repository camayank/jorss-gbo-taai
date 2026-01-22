"""
Branding and Platform Configuration

All platform-specific branding, naming, and visual elements are configured here.
This allows the platform to be white-labeled for different CPA firms without code changes.

Usage:
    from config.branding import get_branding_config

    config = get_branding_config()
    # Use config.platform_name, config.primary_color, etc.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, Optional
import json


@dataclass
class BrandingConfig:
    """Configuration for platform branding and appearance"""

    # Platform Identity
    platform_name: str = "Tax Advisory Platform"
    company_name: str = "Professional Tax Advisory"
    tagline: str = "CPA-Grade Tax Analysis & Optimization"
    firm_credentials: str = "Comprehensive Tax Advisory Services"

    # Visual Branding
    primary_color: str = "#3b82f6"
    secondary_color: str = "#2563eb"
    accent_color: str = "#f59e0b"  # For highlights, badges, etc.
    logo_url: Optional[str] = None
    favicon_url: Optional[str] = None

    # Contact Information
    support_email: str = "support@example.com"
    support_phone: Optional[str] = None
    website_url: Optional[str] = None

    # Features & Messaging
    filing_time_claim: str = "Comprehensive Analysis"
    security_claim: str = "Bank-level encryption"
    review_claim: str = "CPA-Grade Analysis"

    # Trust Badges Configuration
    show_encryption_badge: bool = True
    encryption_level: str = "256-bit"
    show_cpa_badge: bool = False
    cpa_credentials: str = "CPA Verified"
    show_soc2_badge: bool = False
    soc2_type: str = "SOC 2 Type II"
    show_aicpa_badge: bool = False
    show_gdpr_badge: bool = True

    # Legal
    terms_url: Optional[str] = None
    privacy_url: Optional[str] = None
    company_address: Optional[str] = None

    # SEO & Meta
    meta_description: str = "Get professional tax advisory services with comprehensive analysis, optimization strategies, and CPA-grade recommendations"
    meta_keywords: str = "tax advisory, tax optimization, CPA tax analysis, tax planning, tax savings"

    # Custom CSS/Styles (for advanced customization)
    custom_css: Optional[str] = None
    custom_js: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for template rendering"""
        return {
            'platform_name': self.platform_name,
            'company_name': self.company_name,
            'tagline': self.tagline,
            'firm_credentials': self.firm_credentials,
            'primary_color': self.primary_color,
            'secondary_color': self.secondary_color,
            'accent_color': self.accent_color,
            'logo_url': self.logo_url,
            'favicon_url': self.favicon_url,
            'support_email': self.support_email,
            'support_phone': self.support_phone,
            'website_url': self.website_url,
            'filing_time_claim': self.filing_time_claim,
            'security_claim': self.security_claim,
            'review_claim': self.review_claim,
            'show_encryption_badge': self.show_encryption_badge,
            'encryption_level': self.encryption_level,
            'show_cpa_badge': self.show_cpa_badge,
            'cpa_credentials': self.cpa_credentials,
            'show_soc2_badge': self.show_soc2_badge,
            'soc2_type': self.soc2_type,
            'show_aicpa_badge': self.show_aicpa_badge,
            'show_gdpr_badge': self.show_gdpr_badge,
            'terms_url': self.terms_url,
            'privacy_url': self.privacy_url,
            'company_address': self.company_address,
            'meta_description': self.meta_description,
            'meta_keywords': self.meta_keywords,
            'custom_css': self.custom_css,
            'custom_js': self.custom_js,
        }


def load_branding_from_env() -> BrandingConfig:
    """Load branding configuration from environment variables"""
    return BrandingConfig(
        platform_name=os.getenv('PLATFORM_NAME', 'Tax Advisory Platform'),
        company_name=os.getenv('COMPANY_NAME', 'Professional Tax Advisory'),
        tagline=os.getenv('PLATFORM_TAGLINE', 'CPA-Grade Tax Analysis & Optimization'),
        firm_credentials=os.getenv('FIRM_CREDENTIALS', 'Comprehensive Tax Advisory Services'),

        primary_color=os.getenv('BRAND_PRIMARY_COLOR', '#3b82f6'),
        secondary_color=os.getenv('BRAND_SECONDARY_COLOR', '#2563eb'),
        accent_color=os.getenv('BRAND_ACCENT_COLOR', '#f59e0b'),
        logo_url=os.getenv('BRAND_LOGO_URL'),
        favicon_url=os.getenv('BRAND_FAVICON_URL'),

        support_email=os.getenv('SUPPORT_EMAIL', 'support@example.com'),
        support_phone=os.getenv('SUPPORT_PHONE'),
        website_url=os.getenv('COMPANY_WEBSITE'),

        filing_time_claim=os.getenv('FILING_TIME_CLAIM', 'Comprehensive Analysis'),
        security_claim=os.getenv('SECURITY_CLAIM', 'Bank-level encryption'),
        review_claim=os.getenv('REVIEW_CLAIM', 'CPA-Grade Analysis'),

        show_encryption_badge=os.getenv('SHOW_ENCRYPTION_BADGE', 'true').lower() == 'true',
        encryption_level=os.getenv('ENCRYPTION_LEVEL', '256-bit'),
        show_cpa_badge=os.getenv('SHOW_CPA_BADGE', 'false').lower() == 'true',
        cpa_credentials=os.getenv('CPA_CREDENTIALS', 'CPA Verified'),
        show_soc2_badge=os.getenv('SHOW_SOC2_BADGE', 'false').lower() == 'true',
        soc2_type=os.getenv('SOC2_TYPE', 'SOC 2 Type II'),
        show_aicpa_badge=os.getenv('SHOW_AICPA_BADGE', 'false').lower() == 'true',
        show_gdpr_badge=os.getenv('SHOW_GDPR_BADGE', 'true').lower() == 'true',

        terms_url=os.getenv('TERMS_URL'),
        privacy_url=os.getenv('PRIVACY_URL'),
        company_address=os.getenv('COMPANY_ADDRESS'),

        meta_description=os.getenv('META_DESCRIPTION', 'Get professional tax advisory services with comprehensive analysis, optimization strategies, and CPA-grade recommendations'),
        meta_keywords=os.getenv('META_KEYWORDS', 'tax advisory, tax optimization, CPA tax analysis, tax planning, tax savings'),

        custom_css=os.getenv('CUSTOM_CSS_PATH'),
        custom_js=os.getenv('CUSTOM_JS_PATH'),
    )


def load_branding_from_file(config_path: str) -> BrandingConfig:
    """Load branding configuration from JSON file"""
    try:
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        return BrandingConfig(**config_data)
    except FileNotFoundError:
        print(f"Warning: Branding config file not found at {config_path}. Using defaults.")
        return BrandingConfig()
    except json.JSONDecodeError as e:
        print(f"Warning: Invalid JSON in branding config: {e}. Using defaults.")
        return BrandingConfig()


# Global branding instance (loaded once at startup)
_branding_config: Optional[BrandingConfig] = None


def get_branding_config() -> BrandingConfig:
    """
    Get the global branding configuration.

    Priority order:
    1. JSON config file (if BRANDING_CONFIG_PATH is set)
    2. Environment variables
    3. Default values
    """
    global _branding_config

    if _branding_config is None:
        config_path = os.getenv('BRANDING_CONFIG_PATH')

        if config_path:
            _branding_config = load_branding_from_file(config_path)
        else:
            _branding_config = load_branding_from_env()

    return _branding_config


def reset_branding_config():
    """Reset cached branding config (useful for testing)"""
    global _branding_config
    _branding_config = None


# Example branding configurations for different deployment scenarios

EXAMPLE_CONFIGS = {
    "ca4cpa": {
        "platform_name": "CA4CPA Tax Platform",
        "company_name": "CA4CPA GLOBAL LLC",
        "tagline": "Enterprise Tax Solutions",
        "primary_color": "#1e40af",
        "secondary_color": "#7c3aed",
        "support_email": "support@ca4cpa.com",
        "filing_time_claim": "5 Minutes",
        "security_claim": "Enterprise-grade security",
        "review_claim": "Multi-tier CPA Review"
    },

    "generic_cpa": {
        "platform_name": "TaxPro Online",
        "company_name": "Your CPA Firm Name",
        "tagline": "Simple, Fast, Professional",
        "primary_color": "#059669",
        "secondary_color": "#0891b2",
        "support_email": "help@taxpro.com",
        "filing_time_claim": "3 Minutes",
        "security_claim": "Bank-level encryption",
        "review_claim": "CPA Reviewed"
    },

    "boutique_firm": {
        "platform_name": "Elite Tax Services",
        "company_name": "Smith & Associates, CPAs",
        "tagline": "Personalized Tax Excellence",
        "primary_color": "#991b1b",
        "secondary_color": "#92400e",
        "support_email": "concierge@elitetax.com",
        "support_phone": "1-800-ELITE-TX",
        "filing_time_claim": "10 Minutes",
        "security_claim": "SOC 2 Type II Certified",
        "review_claim": "Partner-level Review"
    },

    "self_hosted": {
        "platform_name": "Tax Return System",
        "company_name": "Internal Use",
        "tagline": "Internal Tax Processing Platform",
        "primary_color": "#374151",
        "secondary_color": "#6b7280",
        "support_email": "it@company.com",
        "filing_time_claim": "Fast Filing",
        "security_claim": "Secure Processing",
        "review_claim": "Quality Assured"
    }
}


def create_example_config_file(config_type: str = "generic_cpa", output_path: str = "branding_config.json"):
    """
    Create an example branding configuration file.

    Args:
        config_type: One of the EXAMPLE_CONFIGS keys
        output_path: Where to write the config file
    """
    if config_type not in EXAMPLE_CONFIGS:
        raise ValueError(f"Unknown config type. Choose from: {list(EXAMPLE_CONFIGS.keys())}")

    with open(output_path, 'w') as f:
        json.dump(EXAMPLE_CONFIGS[config_type], f, indent=2)

    print(f"Created example config at {output_path}")
    print(f"To use: export BRANDING_CONFIG_PATH={output_path}")


if __name__ == "__main__":
    # CLI for creating example configs
    import sys

    if len(sys.argv) > 1:
        config_type = sys.argv[1]
        output_path = sys.argv[2] if len(sys.argv) > 2 else "branding_config.json"
        create_example_config_file(config_type, output_path)
    else:
        print("Usage: python branding.py <config_type> [output_path]")
        print(f"Available config types: {list(EXAMPLE_CONFIGS.keys())}")
        print("\nExample:")
        print("  python branding.py ca4cpa ./config/ca4cpa_branding.json")
