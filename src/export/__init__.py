"""Export and Import Module.

Professional-grade export and import functionality for:
- CPA/EA professional tax software formats
- IRS e-filing XML formats
- PDF generation for print and filing
- Prior year return import
- Client data exchange formats
"""

from export.professional_formats import (
    ProfessionalExporter,
    ExportFormat,
    ExportResult,
)
from export.irs_efile import (
    IRSEFileGenerator,
    MeF_XML_Generator,
    StateEFileGenerator,
)
from export.pdf_generator import (
    TaxReturnPDFGenerator,
    WorkpaperGenerator,
)
from export.data_importer import (
    DataImporter,
    PriorYearImporter,
    BulkImporter,
)
from export.computation_statement import (
    TaxComputationStatement,
    AssumptionCategory,
    Assumption,
    ComputationLine,
    ComputationSection,
)
from export.draft_return import (
    DraftReturnGenerator,
    CompletionStatus,
    MissingItem,
    ScheduleRequirement,
    generate_complete_draft_package,
)

__all__ = [
    # Professional formats
    "ProfessionalExporter",
    "ExportFormat",
    "ExportResult",
    # IRS e-file
    "IRSEFileGenerator",
    "MeF_XML_Generator",
    "StateEFileGenerator",
    # PDF generation
    "TaxReturnPDFGenerator",
    "WorkpaperGenerator",
    # Data import
    "DataImporter",
    "PriorYearImporter",
    "BulkImporter",
    # Computation statement (Big4 level)
    "TaxComputationStatement",
    "AssumptionCategory",
    "Assumption",
    "ComputationLine",
    "ComputationSection",
    # Draft return generation
    "DraftReturnGenerator",
    "CompletionStatus",
    "MissingItem",
    "ScheduleRequirement",
    "generate_complete_draft_package",
]
