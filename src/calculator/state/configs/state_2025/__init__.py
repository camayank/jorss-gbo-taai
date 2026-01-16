"""State tax calculators for tax year 2025.

This module contains comprehensive tax calculators for all 41 states
(plus DC) with state income tax. States without income tax (AK, FL, NV,
SD, TX, WA, WY, TN, NH) are handled separately by the registry.
"""

# Import all state calculators to register them with the registry
from calculator.state.configs.state_2025 import california
from calculator.state.configs.state_2025 import new_york
from calculator.state.configs.state_2025 import illinois
from calculator.state.configs.state_2025 import pennsylvania
from calculator.state.configs.state_2025 import new_jersey
from calculator.state.configs.state_2025 import ohio
from calculator.state.configs.state_2025 import georgia
from calculator.state.configs.state_2025 import north_carolina
from calculator.state.configs.state_2025 import michigan
from calculator.state.configs.state_2025 import virginia
from calculator.state.configs.state_2025 import massachusetts
from calculator.state.configs.state_2025 import arizona
from calculator.state.configs.state_2025 import colorado
from calculator.state.configs.state_2025 import minnesota
from calculator.state.configs.state_2025 import maryland
from calculator.state.configs.state_2025 import wisconsin
from calculator.state.configs.state_2025 import indiana
from calculator.state.configs.state_2025 import alabama
from calculator.state.configs.state_2025 import arkansas
from calculator.state.configs.state_2025 import connecticut
from calculator.state.configs.state_2025 import delaware
from calculator.state.configs.state_2025 import district_of_columbia
from calculator.state.configs.state_2025 import hawaii
from calculator.state.configs.state_2025 import idaho
from calculator.state.configs.state_2025 import iowa
from calculator.state.configs.state_2025 import kansas
from calculator.state.configs.state_2025 import kentucky
from calculator.state.configs.state_2025 import louisiana
from calculator.state.configs.state_2025 import maine
from calculator.state.configs.state_2025 import mississippi
from calculator.state.configs.state_2025 import missouri
from calculator.state.configs.state_2025 import montana
from calculator.state.configs.state_2025 import nebraska
from calculator.state.configs.state_2025 import new_mexico
from calculator.state.configs.state_2025 import north_dakota
from calculator.state.configs.state_2025 import oklahoma
from calculator.state.configs.state_2025 import oregon
from calculator.state.configs.state_2025 import rhode_island
from calculator.state.configs.state_2025 import south_carolina
from calculator.state.configs.state_2025 import utah
from calculator.state.configs.state_2025 import vermont
from calculator.state.configs.state_2025 import west_virginia

__all__ = [
    # High population states
    "california",
    "new_york",
    "illinois",
    "pennsylvania",
    "ohio",
    "georgia",
    "north_carolina",
    "michigan",
    "new_jersey",
    "virginia",
    "massachusetts",
    "arizona",
    "colorado",
    "minnesota",
    "maryland",
    "wisconsin",
    "indiana",
    # Remaining states alphabetically
    "alabama",
    "arkansas",
    "connecticut",
    "delaware",
    "district_of_columbia",
    "hawaii",
    "idaho",
    "iowa",
    "kansas",
    "kentucky",
    "louisiana",
    "maine",
    "mississippi",
    "missouri",
    "montana",
    "nebraska",
    "new_mexico",
    "north_dakota",
    "oklahoma",
    "oregon",
    "rhode_island",
    "south_carolina",
    "utah",
    "vermont",
    "west_virginia",
]
