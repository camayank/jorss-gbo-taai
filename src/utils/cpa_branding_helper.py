"""
CPA Branding Helper for Report Generation.

Provides utilities to fetch CPA branding and convert it to
formats suitable for PDF generation and HTML reports.
"""

import logging
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


def get_cpa_branding_for_report(cpa_id: str) -> Optional[Dict[str, Any]]:
    """
    Get CPA branding configuration for report generation.

    Args:
        cpa_id: CPA identifier (user_id or slug)

    Returns:
        Dictionary with branding info suitable for report generation,
        or None if not found.

    Usage:
        branding = get_cpa_branding_for_report("john-smith-cpa")
        if branding:
            brand_config = CPABrandConfig(
                firm_name=branding['firm_name'],
                logo_path=branding['logo_path'],
                ...
            )
    """
    try:
        from database.tenant_persistence import get_tenant_persistence
        persistence = get_tenant_persistence()
        cpa_branding = persistence.get_cpa_branding(cpa_id)

        if not cpa_branding:
            logger.debug(f"No branding found for CPA: {cpa_id}")
            return None

        # Convert firm_logo_url to absolute path
        logo_path = None
        if getattr(cpa_branding, 'firm_logo_url', None):
            # Logo URL is relative like /uploads/firm_logos/xxx.png
            relative_path = cpa_branding.firm_logo_url
            if relative_path.startswith('/'):
                relative_path = relative_path[1:]
            logo_path = Path('.') / relative_path
            if not logo_path.exists():
                logger.warning(f"Logo file not found: {logo_path}")
                logo_path = None
            else:
                logo_path = str(logo_path.absolute())

        return {
            'cpa_id': cpa_branding.cpa_id,
            'tenant_id': cpa_branding.tenant_id,
            'firm_name': cpa_branding.display_name or "Tax Advisory",
            'firm_tagline': cpa_branding.tagline,
            'logo_path': logo_path,
            'logo_url': getattr(cpa_branding, 'firm_logo_url', None),
            'advisor_name': cpa_branding.display_name,
            'advisor_credentials': cpa_branding.credentials or [],
            'contact_email': cpa_branding.direct_email,
            'contact_phone': cpa_branding.direct_phone,
            'contact_address': cpa_branding.office_address,
            'accent_color': cpa_branding.accent_color,
            'profile_photo_url': cpa_branding.profile_photo_url,
            'bio': cpa_branding.bio,
            'specializations': cpa_branding.specializations or [],
            'years_experience': cpa_branding.years_experience,
        }

    except ImportError:
        logger.warning("Tenant persistence not available")
        return None
    except Exception as e:
        logger.error(f"Error fetching CPA branding: {e}")
        return None


def create_pdf_brand_config(cpa_id: str):
    """
    Create CPABrandConfig from CPA branding for PDF generation.

    Args:
        cpa_id: CPA identifier

    Returns:
        CPABrandConfig instance, or None if not found

    Usage:
        brand_config = create_pdf_brand_config("john-smith-cpa")
        exporter = AdvisoryPDFExporter(brand_config=brand_config)
    """
    try:
        from export.advisory_pdf_exporter import CPABrandConfig

        branding = get_cpa_branding_for_report(cpa_id)
        if not branding:
            return None

        return CPABrandConfig(
            firm_name=branding['firm_name'],
            firm_tagline=branding['firm_tagline'],
            logo_path=branding['logo_path'],
            advisor_name=branding['advisor_name'],
            advisor_credentials=branding['advisor_credentials'],
            contact_email=branding['contact_email'],
            contact_phone=branding['contact_phone'],
            contact_address=branding['contact_address'],
            primary_color=branding['accent_color'] or "#2c5aa0",
        )

    except ImportError:
        logger.warning("PDF exporter not available")
        return None
    except Exception as e:
        logger.error(f"Error creating brand config: {e}")
        return None


def get_cpa_branding_for_html_report(cpa_id: str) -> Optional[Dict[str, Any]]:
    """
    Get CPA branding in format suitable for Universal Report Engine.

    Args:
        cpa_id: CPA identifier

    Returns:
        Dictionary in format expected by UniversalReportEngine.generate_html_report
    """
    branding = get_cpa_branding_for_report(cpa_id)
    if not branding:
        return None

    # Convert to Universal Report Engine format
    return {
        'firm_name': branding['firm_name'],
        'advisor_name': branding['advisor_name'],
        'credentials': branding['advisor_credentials'],
        'email': branding['contact_email'],
        'phone': branding['contact_phone'],
        'address': branding['contact_address'],
        'primary_color': branding['accent_color'] or "#2563eb",
        'logo_url': branding['logo_url'],
        'tagline': branding['firm_tagline'],
        'preset': 'professional',
    }


def list_cpa_with_branding(tenant_id: Optional[str] = None) -> list:
    """
    List all CPAs with branding configured.

    Args:
        tenant_id: Optional tenant filter

    Returns:
        List of CPA IDs with branding
    """
    try:
        from database.tenant_persistence import get_tenant_persistence
        persistence = get_tenant_persistence()

        # This would require a method on persistence to list all CPAs
        # For now, return empty list
        logger.warning("list_cpa_with_branding not fully implemented")
        return []

    except Exception as e:
        logger.error(f"Error listing CPAs: {e}")
        return []
