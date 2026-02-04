"""
Tax Configuration Consistency Guard Test.

Ensures all files importing standard deduction values agree with the YAML
source of truth. Acts as a regression firewall against hardcoded tax values
drifting from the config.
"""

import ast
import re
from pathlib import Path

import pytest
import yaml

# Project root
SRC_DIR = Path(__file__).parent.parent / "src"
YAML_CONFIG = SRC_DIR / "config" / "tax_parameters" / "tax_year_2025.yaml"


@pytest.fixture(scope="module")
def yaml_standard_deductions():
    """Load the source-of-truth standard deductions from YAML."""
    with open(YAML_CONFIG, "r") as f:
        config = yaml.safe_load(f)
    return config["standard_deduction"]


class TestStandardDeductionConsistency:
    """Verify no file in src/ contains stale standard deduction values."""

    # The WRONG 2024 values that should NOT appear as standard deductions
    WRONG_VALUES = {
        15000,   # Wrong single/MFS (should be 15750)
        30000,   # Wrong MFJ/QW (should be 31500)
        22500,   # Wrong HOH (should be 23850)
        23625,   # Wrong HOH variant (should be 23850)
    }

    # Files that are allowed to reference these numbers in non-deduction contexts
    ALLOWED_FILES = {
        "tax_year_2022.yaml",
        "tax_year_2023.yaml",
        "tax_year_2024.yaml",
    }

    def test_yaml_has_correct_2025_values(self, yaml_standard_deductions):
        """Verify the YAML source of truth has correct 2025 values."""
        assert yaml_standard_deductions["single"] == 15750
        assert yaml_standard_deductions["married_joint"] == 31500
        assert yaml_standard_deductions["married_separate"] == 15750
        assert yaml_standard_deductions["head_of_household"] == 23850
        assert yaml_standard_deductions["qualifying_widow"] == 31500

    def test_no_wrong_standard_deductions_in_python_files(self):
        """
        Scan all Python files for patterns that look like wrong standard
        deduction assignments.

        Matches patterns like:
          "single": 15000
          'single': 15000
          standard_deduction_single": 15000
          standard_deduction = 15000
        """
        violations = []

        patterns = [
            # Dict-style: "single": 15000 or 'single': 15000
            re.compile(r"""["'](?:single|married_separate)["']\s*:\s*15000\b"""),
            re.compile(r"""["'](?:married_joint|married_filing_jointly|qualifying_widow)["']\s*:\s*30000\b"""),
            re.compile(r"""["'](?:head_of_household)["']\s*:\s*(?:22500|23625)\b"""),
            # Variable-style: standard_deduction_single = 15000
            re.compile(r"""standard_deduction(?:_single|_mfs)\s*[=:]\s*15000\b"""),
            re.compile(r"""standard_deduction(?:_mfj|_joint)\s*[=:]\s*30000\b"""),
            re.compile(r"""standard_deduction(?:_hoh)\s*[=:]\s*(?:22500|23625)\b"""),
            # Ternary or inline: = 15000 if filing_status == 'single' else 30000
            re.compile(r"""=\s*15000\s+if\s+.*(?:filing|status).*else\s+30000"""),
        ]

        for py_file in SRC_DIR.rglob("*.py"):
            if py_file.name in self.ALLOWED_FILES:
                continue

            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
            except (OSError, PermissionError):
                continue

            for i, line in enumerate(content.splitlines(), 1):
                # Skip comments
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue

                for pattern in patterns:
                    if pattern.search(line):
                        rel_path = py_file.relative_to(SRC_DIR)
                        violations.append(f"  {rel_path}:{i}: {stripped[:120]}")

        if violations:
            msg = (
                f"Found {len(violations)} file(s) with stale standard deduction "
                f"values (expected 15750/31500/23850 for 2025):\n"
                + "\n".join(violations)
            )
            pytest.fail(msg)

    def test_tax_year_config_hoh_matches_yaml(self, yaml_standard_deductions):
        """Verify tax_year_config.py HOH matches YAML."""
        config_file = SRC_DIR / "calculator" / "tax_year_config.py"
        content = config_file.read_text(encoding="utf-8")

        # Find HOH value in the std dict
        match = re.search(
            r'"head_of_household"\s*:\s*([\d.]+)',
            content,
        )
        assert match, "Could not find head_of_household in tax_year_config.py"
        hoh_value = float(match.group(1))
        assert hoh_value == float(yaml_standard_deductions["head_of_household"]), (
            f"tax_year_config.py HOH={hoh_value} != YAML HOH={yaml_standard_deductions['head_of_household']}"
        )

    def test_recommendation_constants_use_config(self):
        """Verify recommendation/constants.py imports from config loader."""
        constants_file = SRC_DIR / "web" / "recommendation" / "constants.py"
        if not constants_file.exists():
            pytest.skip("constants.py not found")

        content = constants_file.read_text(encoding="utf-8")

        # Should import from config_loader OR have correct values
        has_import = "tax_config_loader" in content or "get_standard_deductions" in content
        has_wrong = "15000" in content and '"single"' in content

        if has_wrong and not has_import:
            pytest.fail(
                "recommendation/constants.py has hardcoded wrong values "
                "and does not import from config.tax_config_loader"
            )
