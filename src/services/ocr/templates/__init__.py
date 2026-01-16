"""
OCR Templates - Field extraction templates for tax documents.
"""

from ..field_extractor import (
    FieldTemplate,
    FieldType,
    create_w2_templates,
    create_1099_int_templates,
    create_1099_div_templates,
    create_1099_nec_templates,
    create_1099_misc_templates,
    get_templates_for_document,
    DOCUMENT_TEMPLATES,
)

__all__ = [
    "FieldTemplate",
    "FieldType",
    "create_w2_templates",
    "create_1099_int_templates",
    "create_1099_div_templates",
    "create_1099_nec_templates",
    "create_1099_misc_templates",
    "get_templates_for_document",
    "DOCUMENT_TEMPLATES",
]
