"""
Platform Billing Configuration - Payment collection settings for platform fees.

The platform collects subscription fees from CPAs through:
1. Stripe (for automated recurring billing)
2. Mercury bank account (for wire/ACH transfers)
3. Indian bank account (for international transfers)

CPAs collect client payments through their own Stripe Connect accounts.
Platform fees are automatically deducted as application fees.
"""

import os
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


class PaymentMethod(str, Enum):
    """Supported payment methods for platform fees."""
    STRIPE = "stripe"
    BANK_TRANSFER_US = "bank_transfer_us"  # Mercury
    BANK_TRANSFER_INDIA = "bank_transfer_india"
    MANUAL = "manual"


@dataclass
class BankAccountConfig:
    """Bank account configuration for manual transfers."""
    account_name: str
    bank_name: str
    account_number_last4: str  # Only last 4 for display
    routing_number: Optional[str] = None  # US only
    ifsc_code: Optional[str] = None  # India only
    swift_code: Optional[str] = None
    currency: str = "USD"
    country: str = "US"


class PlatformBillingConfig:
    """
    Platform billing configuration.

    Manages payment collection settings for subscription fees.
    """

    def __init__(self):
        self._load_config()

    def _load_config(self):
        """Load configuration from environment variables."""
        # Stripe configuration (for automated billing)
        self.stripe_enabled = bool(os.environ.get("STRIPE_SECRET_KEY"))
        self.stripe_publishable_key = os.environ.get("STRIPE_PUBLISHABLE_KEY")
        self.stripe_secret_key = os.environ.get("STRIPE_SECRET_KEY")
        self.stripe_webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")

        # Platform fee settings
        self.platform_fee_percent = float(os.environ.get("PLATFORM_FEE_PERCENT", "2.9"))
        self.platform_fee_fixed = float(os.environ.get("PLATFORM_FEE_FIXED", "0.30"))

        # Mercury bank account (US)
        self.mercury_enabled = bool(os.environ.get("MERCURY_ACCOUNT_NUMBER"))
        self.mercury_config = BankAccountConfig(
            account_name=os.environ.get("MERCURY_ACCOUNT_NAME", "Jorss-Gbo Platform"),
            bank_name="Mercury",
            account_number_last4=os.environ.get("MERCURY_ACCOUNT_LAST4", "****"),
            routing_number=os.environ.get("MERCURY_ROUTING_NUMBER"),
            currency="USD",
            country="US",
        )

        # Indian bank account
        self.india_bank_enabled = bool(os.environ.get("INDIA_BANK_IFSC"))
        self.india_bank_config = BankAccountConfig(
            account_name=os.environ.get("INDIA_BANK_ACCOUNT_NAME", "Jorss-Gbo India"),
            bank_name=os.environ.get("INDIA_BANK_NAME", "HDFC Bank"),
            account_number_last4=os.environ.get("INDIA_BANK_ACCOUNT_LAST4", "****"),
            ifsc_code=os.environ.get("INDIA_BANK_IFSC"),
            swift_code=os.environ.get("INDIA_BANK_SWIFT"),
            currency="INR",
            country="IN",
        )

    def get_available_payment_methods(self) -> list:
        """Get list of available payment methods."""
        methods = []

        if self.stripe_enabled:
            methods.append({
                "method": PaymentMethod.STRIPE.value,
                "name": "Credit/Debit Card",
                "description": "Pay securely with Stripe",
                "automated": True,
            })

        if self.mercury_enabled:
            methods.append({
                "method": PaymentMethod.BANK_TRANSFER_US.value,
                "name": "Bank Transfer (US)",
                "description": "Wire or ACH transfer to Mercury account",
                "automated": False,
                "bank_details": {
                    "bank_name": self.mercury_config.bank_name,
                    "account_name": self.mercury_config.account_name,
                    "account_last4": self.mercury_config.account_number_last4,
                },
            })

        if self.india_bank_enabled:
            methods.append({
                "method": PaymentMethod.BANK_TRANSFER_INDIA.value,
                "name": "Bank Transfer (India)",
                "description": "NEFT/RTGS/IMPS transfer",
                "automated": False,
                "bank_details": {
                    "bank_name": self.india_bank_config.bank_name,
                    "account_name": self.india_bank_config.account_name,
                    "account_last4": self.india_bank_config.account_number_last4,
                    "ifsc": self.india_bank_config.ifsc_code,
                },
            })

        # Always include manual option
        methods.append({
            "method": PaymentMethod.MANUAL.value,
            "name": "Manual Payment",
            "description": "Contact us for custom payment arrangements",
            "automated": False,
        })

        return methods

    def get_bank_transfer_details(self, method: PaymentMethod) -> Optional[Dict[str, Any]]:
        """Get full bank transfer details for invoice payment."""
        if method == PaymentMethod.BANK_TRANSFER_US and self.mercury_enabled:
            return {
                "bank_name": self.mercury_config.bank_name,
                "account_name": self.mercury_config.account_name,
                "account_number": os.environ.get("MERCURY_ACCOUNT_NUMBER", "Contact admin"),
                "routing_number": self.mercury_config.routing_number,
                "swift_code": "MABORNUS1",  # Mercury's SWIFT
                "currency": "USD",
                "country": "United States",
                "instructions": [
                    "Include your CPA ID in the transfer memo",
                    "Allow 1-3 business days for processing",
                    "Email receipt to billing@jorss-gbo.com",
                ],
            }

        if method == PaymentMethod.BANK_TRANSFER_INDIA and self.india_bank_enabled:
            return {
                "bank_name": self.india_bank_config.bank_name,
                "account_name": self.india_bank_config.account_name,
                "account_number": os.environ.get("INDIA_BANK_ACCOUNT_NUMBER", "Contact admin"),
                "ifsc_code": self.india_bank_config.ifsc_code,
                "swift_code": self.india_bank_config.swift_code,
                "currency": "INR",
                "country": "India",
                "instructions": [
                    "Include your CPA ID in the transfer remarks",
                    "Use current USD-INR exchange rate",
                    "Share payment screenshot via email",
                ],
            }

        return None

    def calculate_platform_fee(self, amount: float) -> Dict[str, float]:
        """Calculate platform fee for a transaction."""
        fee_percent = amount * (self.platform_fee_percent / 100)
        fee_fixed = self.platform_fee_fixed
        total_fee = round(fee_percent + fee_fixed, 2)
        net_amount = round(amount - total_fee, 2)

        return {
            "gross_amount": amount,
            "fee_percent": round(fee_percent, 2),
            "fee_fixed": fee_fixed,
            "total_fee": total_fee,
            "net_amount": net_amount,
            "fee_description": f"{self.platform_fee_percent}% + ${fee_fixed}",
        }

    def get_subscription_tiers(self) -> list:
        """Get platform subscription tiers for CPAs."""
        return [
            {
                "tier": "starter",
                "name": "Starter",
                "price_monthly": 99,
                "price_annual": 990,
                "features": {
                    "leads_per_month": 25,
                    "team_members": 1,
                    "white_label": False,
                    "priority_support": False,
                    "api_access": False,
                },
            },
            {
                "tier": "professional",
                "name": "Professional",
                "price_monthly": 199,
                "price_annual": 1990,
                "features": {
                    "leads_per_month": 100,
                    "team_members": 5,
                    "white_label": True,
                    "priority_support": False,
                    "api_access": True,
                },
            },
            {
                "tier": "enterprise",
                "name": "Enterprise",
                "price_monthly": 499,
                "price_annual": 4990,
                "features": {
                    "leads_per_month": "unlimited",
                    "team_members": "unlimited",
                    "white_label": True,
                    "priority_support": True,
                    "api_access": True,
                    "custom_domain": True,
                },
            },
        ]


# Singleton instance
_config: Optional[PlatformBillingConfig] = None


def get_platform_billing_config() -> PlatformBillingConfig:
    """Get platform billing configuration singleton."""
    global _config
    if _config is None:
        _config = PlatformBillingConfig()
    return _config
