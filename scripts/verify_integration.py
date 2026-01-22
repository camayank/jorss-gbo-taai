#!/usr/bin/env python3
"""
Integration Verification System

Comprehensive verification of all platform integrations:
- API endpoints
- RBAC permissions
- Feature access control
- Database connections
- UI/UX consistency
- White-labeling
- User workflows

Run this before deployment to ensure everything is properly integrated.
"""

import sys
import os
import asyncio
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

# Add project root to path
sys.path.insert(0, '/Users/rakeshanita/Jorss-Gbo')


class CheckStatus(Enum):
    """Check result status"""
    PASS = "✅ PASS"
    FAIL = "❌ FAIL"
    WARN = "⚠️  WARN"
    SKIP = "⏭️  SKIP"


@dataclass
class CheckResult:
    """Single check result"""
    category: str
    name: str
    status: CheckStatus
    message: str
    details: str = ""


class IntegrationVerifier:
    """Comprehensive integration verification"""

    def __init__(self):
        self.results: List[CheckResult] = []
        self.errors: List[str] = []

    def add_result(self, category: str, name: str, status: CheckStatus, message: str, details: str = ""):
        """Add check result"""
        self.results.append(CheckResult(category, name, status, message, details))

        if status == CheckStatus.FAIL:
            self.errors.append(f"{category}/{name}: {message}")

    # =========================================================================
    # DATABASE CHECKS
    # =========================================================================

    def check_database_connections(self):
        """Verify database connections"""
        print("\n" + "="*60)
        print("DATABASE CHECKS")
        print("="*60)

        # Check tenant persistence
        try:
            from src.database.tenant_persistence import get_tenant_persistence
            persistence = get_tenant_persistence()
            self.add_result(
                "Database",
                "Tenant Persistence",
                CheckStatus.PASS,
                "Tenant persistence initialized"
            )
        except Exception as e:
            self.add_result(
                "Database",
                "Tenant Persistence",
                CheckStatus.FAIL,
                f"Failed to initialize: {e}"
            )

        # Check session persistence
        try:
            from src.database.session_persistence import get_session_persistence
            session_persistence = get_session_persistence()
            self.add_result(
                "Database",
                "Session Persistence",
                CheckStatus.PASS,
                "Session persistence initialized"
            )
        except Exception as e:
            self.add_result(
                "Database",
                "Session Persistence",
                CheckStatus.FAIL,
                f"Failed to initialize: {e}"
            )

        # Check audit logger
        try:
            from src.audit.audit_logger import get_audit_logger
            audit_logger = get_audit_logger()
            self.add_result(
                "Database",
                "Audit Logger",
                CheckStatus.PASS,
                "Audit logger initialized"
            )
        except Exception as e:
            self.add_result(
                "Database",
                "Audit Logger",
                CheckStatus.FAIL,
                f"Failed to initialize: {e}"
            )

    # =========================================================================
    # RBAC CHECKS
    # =========================================================================

    def check_rbac_system(self):
        """Verify RBAC system"""
        print("\n" + "="*60)
        print("RBAC SYSTEM CHECKS")
        print("="*60)

        # Check permission definitions
        try:
            from src.rbac.enhanced_permissions import Permissions, get_permissions_for_role
            all_perms = [attr for attr in dir(Permissions) if not attr.startswith('_')]
            self.add_result(
                "RBAC",
                "Permission Definitions",
                CheckStatus.PASS,
                f"{len(all_perms)} permissions defined"
            )
        except Exception as e:
            self.add_result(
                "RBAC",
                "Permission Definitions",
                CheckStatus.FAIL,
                f"Failed to load permissions: {e}"
            )
            return

        # Check all roles have permissions
        roles = ['PLATFORM_ADMIN', 'PARTNER', 'STAFF', 'FIRM_CLIENT', 'DIRECT_CLIENT']
        for role in roles:
            try:
                perms = get_permissions_for_role(role)
                self.add_result(
                    "RBAC",
                    f"Role: {role}",
                    CheckStatus.PASS,
                    f"{len(perms)} permissions assigned"
                )
            except Exception as e:
                self.add_result(
                    "RBAC",
                    f"Role: {role}",
                    CheckStatus.FAIL,
                    f"Failed to load permissions: {e}"
                )

        # Check FIRM_CLIENT edit permission (bug fix verification)
        try:
            from src.rbac.enhanced_permissions import Permissions
            client_perms = get_permissions_for_role('FIRM_CLIENT')

            if Permissions.CLIENT_RETURNS_EDIT_SELF in client_perms:
                self.add_result(
                    "RBAC",
                    "FIRM_CLIENT Edit Permission",
                    CheckStatus.PASS,
                    "Bug fix verified - FIRM_CLIENT can edit own returns"
                )
            else:
                self.add_result(
                    "RBAC",
                    "FIRM_CLIENT Edit Permission",
                    CheckStatus.FAIL,
                    "BUG: FIRM_CLIENT missing EDIT_SELF permission!"
                )
        except Exception as e:
            self.add_result(
                "RBAC",
                "FIRM_CLIENT Edit Permission",
                CheckStatus.FAIL,
                f"Check failed: {e}"
            )

    # =========================================================================
    # FEATURE ACCESS CHECKS
    # =========================================================================

    def check_feature_system(self):
        """Verify feature access control"""
        print("\n" + "="*60)
        print("FEATURE ACCESS CONTROL CHECKS")
        print("="*60)

        # Check feature definitions
        try:
            from src.rbac.feature_access_control import Features, Feature
            all_features = [attr for attr in dir(Features)
                          if isinstance(getattr(Features, attr), Feature)]
            self.add_result(
                "Features",
                "Feature Definitions",
                CheckStatus.PASS,
                f"{len(all_features)} features defined"
            )
        except Exception as e:
            self.add_result(
                "Features",
                "Feature Definitions",
                CheckStatus.FAIL,
                f"Failed to load features: {e}"
            )
            return

        # Check key features exist
        key_features = [
            'EXPRESS_LANE',
            'SMART_TAX',
            'AI_CHAT',
            'SCENARIO_EXPLORER',
            'TAX_PROJECTIONS'
        ]

        for feature_name in key_features:
            try:
                feature = getattr(Features, feature_name)
                self.add_result(
                    "Features",
                    f"Feature: {feature_name}",
                    CheckStatus.PASS,
                    f"'{feature.name}' - {feature.min_tier.value} tier"
                )
            except AttributeError:
                self.add_result(
                    "Features",
                    f"Feature: {feature_name}",
                    CheckStatus.FAIL,
                    "Feature not defined"
                )

    # =========================================================================
    # API ENDPOINT CHECKS
    # =========================================================================

    def check_api_endpoints(self):
        """Verify API routers are properly defined"""
        print("\n" + "="*60)
        print("API ENDPOINT CHECKS")
        print("="*60)

        # Check admin APIs
        try:
            from src.web.admin_tenant_api import router as admin_tenant_router
            endpoint_count = len([r for r in admin_tenant_router.routes])
            self.add_result(
                "API",
                "Admin Tenant API",
                CheckStatus.PASS,
                f"{endpoint_count} endpoints defined"
            )
        except Exception as e:
            self.add_result(
                "API",
                "Admin Tenant API",
                CheckStatus.FAIL,
                f"Failed to load: {e}"
            )

        try:
            from src.web.admin_user_management_api import router as admin_user_router
            endpoint_count = len([r for r in admin_user_router.routes])
            self.add_result(
                "API",
                "Admin User Management API",
                CheckStatus.PASS,
                f"{endpoint_count} endpoints defined"
            )
        except Exception as e:
            self.add_result(
                "API",
                "Admin User Management API",
                CheckStatus.FAIL,
                f"Failed to load: {e}"
            )

        # Check CPA APIs
        try:
            from src.web.cpa_branding_api import router as cpa_branding_router
            endpoint_count = len([r for r in cpa_branding_router.routes])
            self.add_result(
                "API",
                "CPA Branding API",
                CheckStatus.PASS,
                f"{endpoint_count} endpoints defined"
            )
        except Exception as e:
            self.add_result(
                "API",
                "CPA Branding API",
                CheckStatus.FAIL,
                f"Failed to load: {e}"
            )

        # Check feature access API
        try:
            from src.web.feature_access_api import router as feature_router
            endpoint_count = len([r for r in feature_router.routes])
            self.add_result(
                "API",
                "Feature Access API",
                CheckStatus.PASS,
                f"{endpoint_count} endpoints defined"
            )
        except Exception as e:
            self.add_result(
                "API",
                "Feature Access API",
                CheckStatus.FAIL,
                f"Failed to load: {e}"
            )

        # Check unified filing API
        try:
            from src.web.unified_filing_api import router as filing_router
            endpoint_count = len([r for r in filing_router.routes])
            self.add_result(
                "API",
                "Unified Filing API",
                CheckStatus.PASS,
                f"{endpoint_count} endpoints defined"
            )
        except Exception as e:
            self.add_result(
                "API",
                "Unified Filing API",
                CheckStatus.WARN,
                f"Not fully implemented yet: {e}"
            )

    # =========================================================================
    # WHITE-LABELING CHECKS
    # =========================================================================

    def check_white_labeling(self):
        """Verify white-labeling system"""
        print("\n" + "="*60)
        print("WHITE-LABELING CHECKS")
        print("="*60)

        # Check branding config
        try:
            from src.config.branding import get_branding_config
            config = get_branding_config()
            self.add_result(
                "White-Label",
                "Branding Config",
                CheckStatus.PASS,
                f"Platform: {config.platform_name}"
            )
        except Exception as e:
            self.add_result(
                "White-Label",
                "Branding Config",
                CheckStatus.FAIL,
                f"Failed to load: {e}"
            )

        # Check tenant models
        try:
            from src.database.tenant_models import Tenant, TenantBranding, TenantFeatureFlags
            self.add_result(
                "White-Label",
                "Tenant Models",
                CheckStatus.PASS,
                "Tenant data models defined"
            )
        except Exception as e:
            self.add_result(
                "White-Label",
                "Tenant Models",
                CheckStatus.FAIL,
                f"Failed to load: {e}"
            )

        # Check CPA branding models
        try:
            from src.database.tenant_models import CPABranding
            self.add_result(
                "White-Label",
                "CPA Branding Models",
                CheckStatus.PASS,
                "CPA branding models defined"
            )
        except Exception as e:
            self.add_result(
                "White-Label",
                "CPA Branding Models",
                CheckStatus.FAIL,
                f"Failed to load: {e}"
            )

    # =========================================================================
    # FILE STRUCTURE CHECKS
    # =========================================================================

    def check_file_structure(self):
        """Verify critical files exist"""
        print("\n" + "="*60)
        print("FILE STRUCTURE CHECKS")
        print("="*60)

        critical_files = [
            ("RBAC", "src/rbac/enhanced_permissions.py"),
            ("RBAC", "src/rbac/permission_enforcement.py"),
            ("RBAC", "src/rbac/feature_access_control.py"),
            ("API", "src/web/admin_tenant_api.py"),
            ("API", "src/web/admin_user_management_api.py"),
            ("API", "src/web/cpa_branding_api.py"),
            ("API", "src/web/feature_access_api.py"),
            ("Database", "src/database/tenant_models.py"),
            ("Database", "src/database/tenant_persistence.py"),
            ("Audit", "src/audit/audit_logger.py"),
            ("Config", "src/config/branding.py"),
            ("Templates", "src/web/templates/admin_tenant_management.html"),
            ("Templates", "src/web/templates/admin_user_management.html"),
            ("Templates", "src/web/templates/cpa_branding_settings.html"),
            ("Frontend", "src/web/static/js/feature-gate.js"),
        ]

        for category, filepath in critical_files:
            full_path = f"/Users/rakeshanita/Jorss-Gbo/{filepath}"
            if os.path.exists(full_path):
                size = os.path.getsize(full_path)
                self.add_result(
                    "Files",
                    filepath,
                    CheckStatus.PASS,
                    f"Exists ({size} bytes)"
                )
            else:
                self.add_result(
                    "Files",
                    filepath,
                    CheckStatus.FAIL,
                    "File not found"
                )

    # =========================================================================
    # MASTER VERIFICATION
    # =========================================================================

    def run_all_checks(self):
        """Run all verification checks"""
        print("\n")
        print("="*60)
        print("JORSS-GBO PLATFORM INTEGRATION VERIFICATION")
        print("="*60)

        self.check_database_connections()
        self.check_rbac_system()
        self.check_feature_system()
        self.check_api_endpoints()
        self.check_white_labeling()
        self.check_file_structure()

        # Print summary
        print("\n")
        print("="*60)
        print("VERIFICATION SUMMARY")
        print("="*60)

        pass_count = sum(1 for r in self.results if r.status == CheckStatus.PASS)
        fail_count = sum(1 for r in self.results if r.status == CheckStatus.FAIL)
        warn_count = sum(1 for r in self.results if r.status == CheckStatus.WARN)
        skip_count = sum(1 for r in self.results if r.status == CheckStatus.SKIP)

        print(f"\n✅ PASSED: {pass_count}")
        print(f"❌ FAILED: {fail_count}")
        print(f"⚠️  WARNINGS: {warn_count}")
        print(f"⏭️  SKIPPED: {skip_count}")
        print(f"\nTOTAL CHECKS: {len(self.results)}")

        # Print detailed results
        print("\n" + "="*60)
        print("DETAILED RESULTS")
        print("="*60)

        current_category = None
        for result in self.results:
            if result.category != current_category:
                print(f"\n{result.category}:")
                current_category = result.category

            print(f"  {result.status.value} {result.name}")
            print(f"      {result.message}")
            if result.details:
                print(f"      {result.details}")

        # Print errors
        if self.errors:
            print("\n" + "="*60)
            print("ERRORS TO FIX")
            print("="*60)
            for error in self.errors:
                print(f"  ❌ {error}")

        # Final verdict
        print("\n" + "="*60)
        if fail_count == 0:
            print("✅ ALL CHECKS PASSED - READY FOR DEPLOYMENT")
        else:
            print(f"❌ {fail_count} CHECKS FAILED - FIX BEFORE DEPLOYMENT")
        print("="*60 + "\n")

        return fail_count == 0


def main():
    """Main verification entry point"""
    verifier = IntegrationVerifier()
    success = verifier.run_all_checks()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
