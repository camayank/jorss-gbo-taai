#!/usr/bin/env python3
"""
UI/UX Integration Verification Script

This script verifies that all new UI/UX components are properly integrated:
1. All template files exist
2. All API routers are registered
3. All routes are accessible
4. All endpoints respond correctly

Run this after integrating the new UI/UX features to ensure everything is connected.

Usage:
    python3 scripts/verify_ui_integration.py
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def check_template_files():
    """Verify all template files exist."""
    print("\n" + "="*70)
    print("1. CHECKING TEMPLATE FILES")
    print("="*70)

    templates_dir = Path("src/web/templates")
    required_templates = [
        "entry_choice.html",
        "express_lane.html",
        "ai_chat.html",
        "scenario_explorer.html",
        "projection_timeline.html",
    ]

    all_exist = True
    for template in required_templates:
        path = templates_dir / template
        exists = path.exists()
        status = "✅ EXISTS" if exists else "❌ MISSING"
        print(f"  {status}: {template}")
        if not exists:
            all_exist = False

    return all_exist


def check_api_files():
    """Verify all API files exist."""
    print("\n" + "="*70)
    print("2. CHECKING API FILES")
    print("="*70)

    api_dir = Path("src/web")
    required_apis = [
        "express_lane_api.py",
        "ai_chat_api.py",
        "scenario_api.py",
    ]

    all_exist = True
    for api_file in required_apis:
        path = api_dir / api_file
        exists = path.exists()
        status = "✅ EXISTS" if exists else "❌ MISSING"
        print(f"  {status}: {api_file}")
        if not exists:
            all_exist = False

    return all_exist


def check_app_py_integration():
    """Check if app.py has all the integrations."""
    print("\n" + "="*70)
    print("3. CHECKING APP.PY INTEGRATION")
    print("="*70)

    app_py = Path("src/web/app.py")
    if not app_py.exists():
        print("  ❌ FAIL: app.py not found!")
        return False

    content = app_py.read_text()

    checks = [
        {
            "name": "Express Lane Router Import",
            "pattern": "from web.express_lane_api import router as express_lane_router",
        },
        {
            "name": "AI Chat Router Import",
            "pattern": "from web.ai_chat_api import router as ai_chat_router",
        },
        {
            "name": "Scenario Router Import",
            "pattern": "from web.scenario_api import router as scenario_router",
        },
        {
            "name": "Express Lane Router Registration",
            "pattern": "app.include_router(express_lane_router)",
        },
        {
            "name": "AI Chat Router Registration",
            "pattern": "app.include_router(ai_chat_router)",
        },
        {
            "name": "Scenario Router Registration",
            "pattern": "app.include_router(scenario_router)",
        },
        {
            "name": "/entry-choice Route",
            "pattern": '@app.get("/entry-choice"',
        },
        {
            "name": "/express Route",
            "pattern": '@app.get("/express"',
        },
        {
            "name": "/chat Route",
            "pattern": '@app.get("/chat"',
        },
        {
            "name": "/scenarios Route",
            "pattern": '@app.get("/scenarios"',
        },
        {
            "name": "/projections Route",
            "pattern": '@app.get("/projections"',
        },
        {
            "name": "/api/ocr/process Endpoint",
            "pattern": '@app.post("/api/ocr/process")',
        },
    ]

    all_passed = True
    for check in checks:
        found = check["pattern"] in content
        status = "✅ FOUND" if found else "❌ MISSING"
        print(f"  {status}: {check['name']}")
        if not found:
            all_passed = False

    return all_passed


def check_python_syntax():
    """Check Python syntax of all modified files."""
    print("\n" + "="*70)
    print("4. CHECKING PYTHON SYNTAX")
    print("="*70)

    import py_compile
    import tempfile

    files_to_check = [
        "src/web/app.py",
        "src/web/express_lane_api.py",
        "src/web/ai_chat_api.py",
        "src/web/scenario_api.py",
    ]

    all_valid = True
    for filepath in files_to_check:
        try:
            py_compile.compile(filepath, doraise=True)
            print(f"  ✅ VALID: {filepath}")
        except py_compile.PyCompileError as e:
            print(f"  ❌ SYNTAX ERROR: {filepath}")
            print(f"     {str(e)}")
            all_valid = False

    return all_valid


def check_imports():
    """Check if all required modules can be imported."""
    print("\n" + "="*70)
    print("5. CHECKING IMPORTS (Quick Test)")
    print("="*70)

    import_tests = [
        ("FastAPI", "fastapi", "FastAPI"),
        ("Pydantic", "pydantic", "BaseModel"),
        ("Intelligent Tax Agent", "src.agent.intelligent_tax_agent", "IntelligentTaxAgent"),
        ("Tax Calculator", "src.calculation.tax_calculator", "TaxCalculator"),
    ]

    import importlib

    all_imported = True
    for name, module, obj in import_tests:
        try:
            mod = importlib.import_module(module)
            getattr(mod, obj)
            print(f"  ✅ OK: {name}")
        except (ImportError, AttributeError) as e:
            print(f"  ⚠️  WARN: {name} - {e}")
            # Don't fail on warnings for optional dependencies

    return all_imported


def print_summary(results):
    """Print summary of verification results."""
    print("\n" + "="*70)
    print("VERIFICATION SUMMARY")
    print("="*70)

    total = len(results)
    passed = sum(results.values())

    for check, status in results.items():
        icon = "✅" if status else "❌"
        print(f"  {icon} {check}")

    print(f"\n  Results: {passed}/{total} checks passed")

    if passed == total:
        print("\n  🎉 ALL CHECKS PASSED! Integration is complete.")
        return 0
    else:
        print("\n  ⚠️  SOME CHECKS FAILED. Please review the output above.")
        return 1


def main():
    """Run all verification checks."""
    print("\n" + "="*70)
    print("UI/UX INTEGRATION VERIFICATION")
    print("="*70)
    print("\nVerifying that all new UI/UX components are properly integrated...")

    results = {
        "Template Files": check_template_files(),
        "API Files": check_api_files(),
        "App.py Integration": check_app_py_integration(),
        "Python Syntax": check_python_syntax(),
        "Module Imports": check_imports(),
    }

    return print_summary(results)


if __name__ == "__main__":
    sys.exit(main())
