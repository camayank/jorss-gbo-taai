"""
Tax Configuration Loader.

Loads tax parameters from YAML configuration files, enabling:
- Easy annual updates without code changes
- Environment-specific overrides
- Audit trail of configuration changes
- AI-assisted configuration suggestions
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

logger = logging.getLogger(__name__)

# Default config directory
CONFIG_DIR = Path(__file__).parent / "tax_parameters"


@dataclass
class ConfigMetadata:
    """Metadata about a configuration file."""
    version: str
    tax_year: int
    effective_date: str
    source: str  # "IRS", "state", "custom"
    irs_references: List[str] = field(default_factory=list)
    last_updated: str = ""
    updated_by: str = ""
    notes: str = ""


@dataclass
class ConfigChange:
    """Record of a configuration change."""
    parameter: str
    old_value: Any
    new_value: Any
    changed_at: str
    changed_by: str
    reason: str
    irs_reference: Optional[str] = None


class TaxConfigLoader:
    """
    Loads and manages tax configuration from YAML files.

    Features:
    - Automatic file discovery by tax year
    - Environment variable overrides
    - Configuration validation
    - Change tracking
    """

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize the config loader.

        Args:
            config_dir: Directory containing YAML config files.
                       Defaults to src/config/tax_parameters/
        """
        self.config_dir = config_dir or CONFIG_DIR
        self._configs: Dict[int, Dict[str, Any]] = {}
        self._metadata: Dict[int, ConfigMetadata] = {}
        self._changes: List[ConfigChange] = []

    def load_config(self, tax_year: int) -> Dict[str, Any]:
        """
        Load configuration for a specific tax year.

        Args:
            tax_year: The tax year to load (e.g., 2025)

        Returns:
            Dictionary of tax parameters
        """
        if tax_year in self._configs:
            return self._configs[tax_year]

        config = self._load_from_files(tax_year)
        config = self._apply_env_overrides(config, tax_year)
        self._validate_config(config, tax_year)

        self._configs[tax_year] = config
        return config

    def _load_from_files(self, tax_year: int) -> Dict[str, Any]:
        """Load configuration from YAML files."""
        config = {}

        # Try to load year-specific config
        year_file = self.config_dir / f"tax_year_{tax_year}.yaml"
        if year_file.exists():
            logger.info(f"Loading tax config from {year_file}")
            with open(year_file, 'r') as f:
                year_config = yaml.safe_load(f)
                if year_config:
                    # Extract metadata
                    if '_metadata' in year_config:
                        self._metadata[tax_year] = ConfigMetadata(**year_config.pop('_metadata'))
                    config.update(year_config)
        else:
            logger.warning(f"No config file found for tax year {tax_year}, using defaults")

        # Load category-specific files that might override
        categories = ['credits', 'deductions', 'income', 'limits', 'rates']
        for category in categories:
            category_file = self.config_dir / f"{category}_{tax_year}.yaml"
            if category_file.exists():
                with open(category_file, 'r') as f:
                    category_config = yaml.safe_load(f)
                    if category_config:
                        config.update(category_config)

        return config

    def _apply_env_overrides(self, config: Dict[str, Any], tax_year: int) -> Dict[str, Any]:
        """Apply environment variable overrides to configuration."""
        # Environment variables like TAX_2025_STANDARD_DEDUCTION_SINGLE=15750
        prefix = f"TAX_{tax_year}_"

        for key, value in os.environ.items():
            if key.startswith(prefix):
                param_name = key[len(prefix):].lower()
                try:
                    # Try to convert to appropriate type
                    if '.' in value:
                        config[param_name] = float(value)
                    elif value.isdigit():
                        config[param_name] = int(value)
                    else:
                        config[param_name] = value
                    logger.info(f"Applied env override: {param_name}={value}")
                except (ValueError, TypeError):
                    logger.warning(f"Could not parse env override: {key}={value}")

        return config

    def _validate_config(self, config: Dict[str, Any], tax_year: int) -> None:
        """Validate configuration for completeness and consistency."""
        required_params = [
            'standard_deduction',
            'ss_wage_base',
            'child_tax_credit_amount',
        ]

        missing = [p for p in required_params if p not in config]
        if missing:
            logger.warning(f"Missing required parameters for {tax_year}: {missing}")

    def get_parameter(
        self,
        param_name: str,
        tax_year: int,
        filing_status: Optional[str] = None,
        default: Any = None
    ) -> Any:
        """
        Get a specific parameter value.

        Args:
            param_name: Name of the parameter
            tax_year: Tax year
            filing_status: Optional filing status for status-specific values
            default: Default value if not found

        Returns:
            Parameter value
        """
        config = self.load_config(tax_year)
        value = config.get(param_name, default)

        # If value is a dict and filing_status provided, get status-specific value
        if isinstance(value, dict) and filing_status:
            return value.get(filing_status, value.get('single', default))

        return value

    def get_all_parameters(self, tax_year: int) -> Dict[str, Any]:
        """Get all parameters for a tax year."""
        return self.load_config(tax_year)

    def get_metadata(self, tax_year: int) -> Optional[ConfigMetadata]:
        """Get metadata for a tax year's configuration."""
        self.load_config(tax_year)  # Ensure loaded
        return self._metadata.get(tax_year)

    def record_change(
        self,
        parameter: str,
        old_value: Any,
        new_value: Any,
        reason: str,
        changed_by: str = "system",
        irs_reference: Optional[str] = None
    ) -> None:
        """Record a configuration change for audit purposes."""
        change = ConfigChange(
            parameter=parameter,
            old_value=old_value,
            new_value=new_value,
            changed_at=datetime.utcnow().isoformat(),
            changed_by=changed_by,
            reason=reason,
            irs_reference=irs_reference
        )
        self._changes.append(change)
        logger.info(f"Config change recorded: {parameter} {old_value} -> {new_value}")

    def get_change_history(self) -> List[ConfigChange]:
        """Get history of configuration changes."""
        return self._changes.copy()

    def compare_years(self, year1: int, year2: int) -> Dict[str, Dict[str, Any]]:
        """
        Compare configuration between two tax years.

        Returns:
            Dictionary with 'added', 'removed', 'changed' keys
        """
        config1 = self.load_config(year1)
        config2 = self.load_config(year2)

        keys1 = set(config1.keys())
        keys2 = set(config2.keys())

        return {
            'added': {k: config2[k] for k in keys2 - keys1},
            'removed': {k: config1[k] for k in keys1 - keys2},
            'changed': {
                k: {'old': config1[k], 'new': config2[k]}
                for k in keys1 & keys2
                if config1[k] != config2[k]
            }
        }


# Global singleton
_config_loader: Optional[TaxConfigLoader] = None


def get_config_loader() -> TaxConfigLoader:
    """Get the global config loader instance."""
    global _config_loader
    if _config_loader is None:
        _config_loader = TaxConfigLoader()
    return _config_loader


@lru_cache(maxsize=10)
def get_tax_parameter(param_name: str, tax_year: int, filing_status: Optional[str] = None) -> Any:
    """
    Convenience function to get a tax parameter.

    This is the recommended way to access tax parameters throughout the codebase.

    Args:
        param_name: Parameter name (e.g., 'standard_deduction', 'child_tax_credit_amount')
        tax_year: Tax year
        filing_status: Optional filing status for status-specific values

    Returns:
        Parameter value

    Example:
        >>> get_tax_parameter('standard_deduction', 2025, 'single')
        15750.0
        >>> get_tax_parameter('child_tax_credit_amount', 2025)
        2000.0
    """
    loader = get_config_loader()
    return loader.get_parameter(param_name, tax_year, filing_status)


def clear_config_cache() -> None:
    """Clear the configuration cache (useful for testing)."""
    get_tax_parameter.cache_clear()
    global _config_loader
    _config_loader = None
