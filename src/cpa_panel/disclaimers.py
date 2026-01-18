"""
CPA Panel Disclaimers and Compliance Statements

CRITICAL: This module centralizes all regulatory disclaimers required
for CPA professional services. These must be displayed on relevant
outputs to protect both CPAs and the platform.

Platform Type: TAX ADVISORY PREPARATION SUPPORT
NOT an e-filing platform. CPAs file through their own channels.
"""

from typing import Dict, Any
from datetime import datetime


class PlatformDisclaimers:
    """
    Centralized disclaimers for CPA panel compliance.

    All outputs that could be confused with e-filing services
    or that contain tax advice must include appropriate disclaimers.
    """

    # ==========================================================================
    # P1: NON-EFILING ADVISORY PLATFORM DISCLAIMER
    # ==========================================================================
    ADVISORY_PLATFORM_DISCLAIMER = (
        "IMPORTANT: This platform provides tax advisory preparation support "
        "for licensed CPAs and tax professionals. It is NOT an e-filing service. "
        "Tax returns prepared using this platform must be filed through the "
        "CPA's chosen IRS-authorized e-file provider or via paper filing. "
        "The platform does not transmit returns to the IRS or any state tax authority."
    )

    EFILING_CLARIFICATION = (
        "This system assists with tax analysis, computation verification, "
        "and advisory insights. It does NOT:\n"
        "• Submit returns electronically to the IRS\n"
        "• Generate e-file authorization forms (8879)\n"
        "• Provide Modernized e-File (MeF) transmission\n"
        "• Act as an Electronic Return Originator (ERO)\n"
        "\n"
        "CPAs must use their own e-filing solution for IRS submission."
    )

    # ==========================================================================
    # P3: IRS CIRCULAR 230 DISCLAIMER
    # ==========================================================================
    CIRCULAR_230_DISCLAIMER = (
        "IRS Circular 230 Disclosure: To ensure compliance with requirements "
        "imposed by the IRS, we inform you that any U.S. federal tax advice "
        "contained in this communication (including any attachments) is not "
        "intended or written to be used, and cannot be used, for the purpose "
        "of (i) avoiding penalties under the Internal Revenue Code or "
        "(ii) promoting, marketing, or recommending to another party any "
        "transaction or matter addressed herein."
    )

    # ==========================================================================
    # PROFESSIONAL RESPONSIBILITY
    # ==========================================================================
    PROFESSIONAL_RESPONSIBILITY = (
        "The licensed CPA retains full professional responsibility for:\n"
        "• Verifying all data and calculations\n"
        "• Making all tax position determinations\n"
        "• Signing and filing the return through authorized channels\n"
        "• Compliance with Treasury Circular 230 requirements\n"
        "• Client engagement terms and representations\n"
        "• Maintaining required work papers and documentation"
    )

    # ==========================================================================
    # LIMITATION OF LIABILITY
    # ==========================================================================
    LIMITATION_OF_LIABILITY = (
        "This platform provides computational support and analysis tools. "
        "All tax advice and professional judgments remain the sole responsibility "
        "of the licensed CPA. The platform does not guarantee the accuracy of "
        "IRS regulations, does not provide legal advice, and is not responsible "
        "for positions taken on filed returns."
    )

    # ==========================================================================
    # DATA ACCURACY DISCLAIMER
    # ==========================================================================
    DATA_ACCURACY = (
        "Tax computations are based on data provided by the taxpayer or CPA. "
        "The CPA is responsible for verifying the accuracy and completeness "
        "of all input data. Estimated values should be confirmed before filing."
    )

    # ==========================================================================
    # YEAR-SPECIFIC DISCLAIMER
    # ==========================================================================
    @staticmethod
    def get_tax_year_disclaimer(tax_year: int = 2025) -> str:
        """Get tax year specific disclaimer."""
        return (
            f"Tax calculations are based on {tax_year} tax law as of the "
            f"platform's knowledge date. Tax law may change, and the CPA "
            f"should verify current rules apply to the specific situation."
        )

    # ==========================================================================
    # FULL DISCLAIMER PACKAGE
    # ==========================================================================
    @classmethod
    def get_full_disclaimer_package(cls, tax_year: int = 2025) -> Dict[str, str]:
        """Get all disclaimers as a package for comprehensive display."""
        return {
            "platform_type": "TAX ADVISORY PREPARATION SUPPORT (NOT E-FILING)",
            "advisory_platform": cls.ADVISORY_PLATFORM_DISCLAIMER,
            "efiling_clarification": cls.EFILING_CLARIFICATION,
            "circular_230": cls.CIRCULAR_230_DISCLAIMER,
            "professional_responsibility": cls.PROFESSIONAL_RESPONSIBILITY,
            "limitation_of_liability": cls.LIMITATION_OF_LIABILITY,
            "data_accuracy": cls.DATA_ACCURACY,
            "tax_year_notice": cls.get_tax_year_disclaimer(tax_year),
            "generated_at": datetime.utcnow().isoformat(),
        }

    @classmethod
    def get_report_footer(cls, tax_year: int = 2025) -> str:
        """Get standard footer for all generated reports."""
        return (
            f"\n{'='*60}\n"
            f"TAX ADVISORY PREPARATION SUPPORT - NOT AN E-FILING SERVICE\n"
            f"{'='*60}\n\n"
            f"{cls.ADVISORY_PLATFORM_DISCLAIMER}\n\n"
            f"{cls.CIRCULAR_230_DISCLAIMER}\n\n"
            f"Tax Year: {tax_year} | Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n"
        )


class ClientFacingDisclaimers:
    """Disclaimers for client-facing outputs."""

    CLIENT_ADVISORY_NOTICE = (
        "This analysis has been prepared by your tax professional using "
        "professional-grade tax preparation software. The final tax return "
        "will be prepared, reviewed, and filed by your CPA through "
        "IRS-authorized channels."
    )

    ESTIMATE_DISCLAIMER = (
        "The figures shown are estimates based on information provided. "
        "Final tax amounts may differ based on additional information, "
        "tax law changes, or IRS adjustments. Consult with your CPA "
        "before making financial decisions based on these estimates."
    )

    NOT_LEGAL_ADVICE = (
        "This information is provided for tax preparation purposes only "
        "and does not constitute legal, investment, or financial planning advice. "
        "Consult appropriate professionals for specific guidance."
    )
