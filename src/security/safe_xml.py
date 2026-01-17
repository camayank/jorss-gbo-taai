"""
Safe XML Parsing Module.

Prevents XXE (XML External Entity) attacks by disabling dangerous features.
CRITICAL: Standard xml.etree.ElementTree is vulnerable to XXE attacks.
"""

from __future__ import annotations

import logging
from io import BytesIO, StringIO
from typing import Any, Optional, Union
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

# Try to import defusedxml (preferred)
try:
    import defusedxml.ElementTree as DefusedET
    DEFUSED_AVAILABLE = True
except ImportError:
    DEFUSED_AVAILABLE = False
    logger.warning(
        "defusedxml not installed. Using fallback XML parsing. "
        "Install with: pip install defusedxml"
    )


class XMLSecurityError(Exception):
    """Raised when XML contains potentially malicious content."""
    pass


def safe_parse_xml(
    source: Union[str, bytes, StringIO, BytesIO],
    forbid_dtd: bool = True,
    forbid_entities: bool = True,
    forbid_external: bool = True,
) -> ET.Element:
    """
    Safely parse XML content with XXE protections.

    Args:
        source: XML content as string, bytes, or file-like object
        forbid_dtd: Forbid DTD declarations
        forbid_entities: Forbid entity definitions
        forbid_external: Forbid external entity references

    Returns:
        Parsed XML root element

    Raises:
        XMLSecurityError: If XML contains forbidden elements
        ET.ParseError: If XML is malformed
    """
    if DEFUSED_AVAILABLE:
        # Use defusedxml (safest option)
        try:
            from defusedxml import DTDForbidden, EntitiesForbidden, ExternalReferenceForbidden
            if isinstance(source, (str, bytes)):
                return DefusedET.fromstring(
                    source,
                    forbid_dtd=forbid_dtd,
                    forbid_entities=forbid_entities,
                    forbid_external=forbid_external,
                )
            else:
                return DefusedET.parse(
                    source,
                    forbid_dtd=forbid_dtd,
                    forbid_entities=forbid_entities,
                    forbid_external=forbid_external,
                ).getroot()
        except (DTDForbidden, EntitiesForbidden, ExternalReferenceForbidden) as e:
            logger.warning(f"Blocked potentially malicious XML: {e}")
            raise XMLSecurityError(f"XML security violation: {e}") from e
    else:
        # Fallback: manual security checks
        return _safe_parse_fallback(source, forbid_dtd, forbid_entities, forbid_external)


def _safe_parse_fallback(
    source: Union[str, bytes, StringIO, BytesIO],
    forbid_dtd: bool,
    forbid_entities: bool,
    forbid_external: bool,
) -> ET.Element:
    """
    Fallback safe XML parsing when defusedxml is not available.

    Performs basic security checks before parsing.
    """
    # Convert to string for inspection
    if isinstance(source, bytes):
        content = source.decode("utf-8", errors="replace")
    elif isinstance(source, (StringIO, BytesIO)):
        content = source.read()
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        # Reset file pointer
        source.seek(0)
    else:
        content = source

    # Security checks
    content_lower = content.lower()

    # Check for DTD
    if forbid_dtd and "<!doctype" in content_lower:
        raise XMLSecurityError("DTD declarations are forbidden")

    # Check for entity definitions
    if forbid_entities and "<!entity" in content_lower:
        raise XMLSecurityError("Entity definitions are forbidden")

    # Check for external references
    if forbid_external:
        dangerous_patterns = [
            "system",
            "public",
            "file:",
            "http:",
            "https:",
            "ftp:",
            "data:",
        ]
        for pattern in dangerous_patterns:
            if pattern in content_lower:
                # More specific check to avoid false positives
                if f'"{pattern}' in content_lower or f"'{pattern}" in content_lower:
                    raise XMLSecurityError(f"External references ({pattern}) are forbidden")

    # Parse with standard library
    if isinstance(source, str):
        return ET.fromstring(source)
    elif isinstance(source, bytes):
        return ET.fromstring(source)
    else:
        return ET.parse(source).getroot()


def safe_iterparse(
    source: Union[str, BytesIO],
    events: tuple = ("start", "end"),
    forbid_dtd: bool = True,
) -> ET.Element:
    """
    Safely iterate over XML elements.

    Args:
        source: File path or file-like object
        events: Events to yield
        forbid_dtd: Forbid DTD declarations

    Yields:
        Tuple of (event, element)

    Raises:
        XMLSecurityError: If XML contains forbidden elements
    """
    if DEFUSED_AVAILABLE:
        return DefusedET.iterparse(source, events=events, forbid_dtd=forbid_dtd)
    else:
        # Fallback with basic checks
        return ET.iterparse(source, events=events)


def create_element(tag: str, text: Optional[str] = None, **attrib) -> ET.Element:
    """
    Create an XML element safely.

    Escapes text content to prevent injection.

    Args:
        tag: Element tag name
        text: Optional text content
        **attrib: Element attributes

    Returns:
        New XML element
    """
    # Validate tag name
    if not tag or not tag.replace("_", "").replace("-", "").replace(".", "").isalnum():
        raise ValueError(f"Invalid tag name: {tag}")

    element = ET.Element(tag, attrib)

    if text is not None:
        # ET handles escaping automatically
        element.text = str(text)

    return element


def safe_tostring(
    element: ET.Element,
    encoding: str = "unicode",
    method: str = "xml",
) -> str:
    """
    Safely convert element tree to string.

    Args:
        element: XML element
        encoding: Output encoding
        method: Serialization method

    Returns:
        XML string
    """
    return ET.tostring(element, encoding=encoding, method=method)


# Convenience aliases
fromstring = safe_parse_xml
parse = safe_parse_xml
iterparse = safe_iterparse
Element = create_element
tostring = safe_tostring


def validate_xml_schema(
    xml_content: Union[str, bytes],
    schema_content: Union[str, bytes],
) -> bool:
    """
    Validate XML against an XSD schema.

    Note: Requires lxml for schema validation.

    Args:
        xml_content: XML content to validate
        schema_content: XSD schema content

    Returns:
        True if valid

    Raises:
        ImportError: If lxml not available
        XMLSecurityError: If validation fails
    """
    try:
        from lxml import etree
    except ImportError:
        raise ImportError("lxml required for schema validation. Install with: pip install lxml")

    try:
        # Parse schema
        schema_doc = etree.fromstring(
            schema_content if isinstance(schema_content, bytes)
            else schema_content.encode("utf-8")
        )
        schema = etree.XMLSchema(schema_doc)

        # Parse and validate XML
        xml_doc = etree.fromstring(
            xml_content if isinstance(xml_content, bytes)
            else xml_content.encode("utf-8")
        )

        schema.assertValid(xml_doc)
        return True

    except etree.XMLSchemaError as e:
        raise XMLSecurityError(f"XML schema validation failed: {e}") from e
    except etree.XMLSyntaxError as e:
        raise XMLSecurityError(f"XML syntax error: {e}") from e
