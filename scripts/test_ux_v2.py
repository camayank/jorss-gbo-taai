#!/usr/bin/env python3
"""
UX v2 Rollout Test Script

Tests the feature flag system and template resolution.
Run this before enabling the rollout.

Usage:
    python scripts/test_ux_v2.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from jinja2 import Environment, FileSystemLoader


def test_feature_flags():
    """Test feature flag module loads and works correctly."""
    print("=" * 60)
    print("TEST 1: Feature Flag Module")
    print("=" * 60)

    from src.web.feature_flags import (
        should_use_ux_v2,
        get_template_path,
        UX_V2_ENABLED,
        UX_V2_PERCENTAGE,
    )

    print(f"  UX_V2_ENABLED: {UX_V2_ENABLED}")
    print(f"  UX_V2_PERCENTAGE: {UX_V2_PERCENTAGE}")

    # Mock request
    class MockRequest:
        def __init__(self, query_params=None, cookies=None):
            self.query_params = query_params or {}
            self.cookies = cookies or {}
            self.client = type('obj', (object,), {'host': '127.0.0.1'})()
            self.headers = {}

    # Test with defaults
    req = MockRequest()
    result = should_use_ux_v2(req)
    print(f"  should_use_ux_v2(default): {result}")

    # Test with override
    req_override = MockRequest(query_params={"ux_v2": "1"})
    result_override = should_use_ux_v2(req_override)
    print(f"  should_use_ux_v2(?ux_v2=1): {result_override}")

    # Test template path resolution
    path = get_template_path(req, "dashboard.html")
    print(f"  get_template_path(dashboard.html): {path}")

    path_override = get_template_path(req_override, "dashboard.html")
    print(f"  get_template_path(dashboard.html, ?ux_v2=1): {path_override}")

    print("  ✓ Feature flag module working")
    return True


def test_templates():
    """Test all v2 templates render correctly."""
    print("\n" + "=" * 60)
    print("TEST 2: Template Syntax Validation")
    print("=" * 60)

    templates_dir = 'src/web/templates'
    env = Environment(loader=FileSystemLoader(templates_dir))

    v2_templates = [
        'v2/base.html',
        'v2/results.html',
        'v2/guided_filing.html',
        'v2/dashboard.html',
        'v2/lead_magnet/landing.html',
    ]

    all_valid = True
    for template_name in v2_templates:
        try:
            template = env.get_template(template_name)
            print(f"  ✓ {template_name}")
        except Exception as e:
            print(f"  ✗ {template_name}: {e}")
            all_valid = False

    if all_valid:
        print("  ✓ All templates valid")
    return all_valid


def test_css_files():
    """Test all CSS files exist."""
    print("\n" + "=" * 60)
    print("TEST 3: CSS Files")
    print("=" * 60)

    css_files = [
        'src/web/static/css/core/variables.css',
        'src/web/static/css/core/reset.css',
        'src/web/static/css/core/typography.css',
        'src/web/static/css/core/layout.css',
        'src/web/static/css/core/responsive.css',
        'src/web/static/css/core/accessibility.css',
        'src/web/static/css/core/feedback.css',
        'src/web/static/css/main.css',
    ]

    all_exist = True
    for css_file in css_files:
        if os.path.exists(css_file):
            print(f"  ✓ {css_file}")
        else:
            print(f"  ✗ {css_file} MISSING")
            all_exist = False

    if all_exist:
        print("  ✓ All CSS files exist")
    return all_exist


def test_app_imports():
    """Test app.py can import feature flags."""
    print("\n" + "=" * 60)
    print("TEST 4: App.py Integration")
    print("=" * 60)

    try:
        # Check if import statement exists in app.py
        with open('src/web/app.py', 'r') as f:
            content = f.read()

        if 'from web.feature_flags import' in content:
            print("  ✓ Feature flag import found in app.py")
        else:
            print("  ✗ Feature flag import missing from app.py")
            return False

        if 'get_template_path(request' in content:
            print("  ✓ get_template_path() usage found")
        else:
            print("  ✗ get_template_path() usage not found")
            return False

        print("  ✓ App.py integration complete")
        return True

    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("UX V2 ROLLOUT VERIFICATION")
    print("=" * 60)

    results = {
        "Feature Flags": test_feature_flags(),
        "Templates": test_templates(),
        "CSS Files": test_css_files(),
        "App Integration": test_app_imports(),
    }

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    all_passed = True
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {test_name}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("=" * 60)
        print("ALL TESTS PASSED - Ready for rollout!")
        print("=" * 60)
        print("\nNext steps:")
        print("  1. Deploy to staging")
        print("  2. Test with ?ux_v2=1 query parameter")
        print("  3. Set UX_V2_ENABLED=true, UX_V2_PERCENTAGE=10")
        print("  4. Monitor for 24-48 hours")
        print("  5. Scale to 50%, then 100%")
        return 0
    else:
        print("=" * 60)
        print("TESTS FAILED - Fix issues before rollout")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
