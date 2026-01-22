"""
Secure Logger - Automatic PII Sanitization for All Logs

Wraps Python's standard logging to automatically sanitize sensitive data:
- SSN, EIN, Tax IDs
- Credit cards, bank accounts
- Email addresses (partial redaction)
- Phone numbers
- API keys, tokens
- IP addresses
- Names, addresses (when detected)

CRITICAL: Prevents PII exposure in logs (GDPR, CCPA, HIPAA compliance).

Usage:
    from security.secure_logger import get_logger

    logger = get_logger(__name__)
    logger.info(f"Processing return for SSN 123-45-6789")
    # Logs: Processing return for SSN [SSN-REDACTED]
"""

import logging
import re
from typing import Any, Dict, Optional
from .data_sanitizer import get_sanitizer, DataSanitizer


class SanitizingLogFilter(logging.Filter):
    """
    Logging filter that sanitizes log messages before output.

    Automatically redacts PII from all log messages, arguments, and exceptions.
    """

    def __init__(self, sanitizer: Optional[DataSanitizer] = None):
        """
        Initialize filter with sanitizer.

        Args:
            sanitizer: DataSanitizer instance (creates one if not provided)
        """
        super().__init__()
        self.sanitizer = sanitizer or get_sanitizer()

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Sanitize the log record before it's emitted.

        Args:
            record: LogRecord to sanitize

        Returns:
            True (always allow the record, just sanitize it first)
        """
        # Sanitize the main message
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            record.msg = self.sanitizer.sanitize_string(record.msg)

        # Sanitize arguments (for %s, %d formatting)
        if hasattr(record, 'args') and record.args:
            if isinstance(record.args, dict):
                record.args = self.sanitizer.sanitize_dict(record.args)
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    self.sanitizer.sanitize_value(arg) for arg in record.args
                )
            else:
                record.args = self.sanitizer.sanitize_value(record.args)

        # Sanitize exception info
        if record.exc_info and record.exc_text:
            record.exc_text = self.sanitizer.sanitize_string(record.exc_text)

        # Sanitize any custom fields in the record
        for key in dir(record):
            if not key.startswith('_') and key not in ['msg', 'args', 'exc_info', 'exc_text']:
                value = getattr(record, key, None)
                if isinstance(value, str):
                    setattr(record, key, self.sanitizer.sanitize_string(value))

        return True


class SecureLogger(logging.LoggerAdapter):
    """
    Logger adapter that automatically sanitizes all log messages.

    Drop-in replacement for standard Python logger with automatic PII redaction.
    """

    def __init__(self, logger: logging.Logger, extra: Optional[Dict[str, Any]] = None):
        """
        Initialize secure logger.

        Args:
            logger: Underlying Python logger
            extra: Extra fields to include in log records
        """
        super().__init__(logger, extra or {})
        self.sanitizer = get_sanitizer()

        # Add sanitizing filter if not already present
        if not any(isinstance(f, SanitizingLogFilter) for f in logger.filters):
            logger.addFilter(SanitizingLogFilter(self.sanitizer))

    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """
        Process log message before passing to underlying logger.

        Args:
            msg: Log message
            kwargs: Keyword arguments

        Returns:
            Tuple of (processed_msg, processed_kwargs)
        """
        # Add extra fields from adapter
        extra = self.extra.copy()

        # Sanitize any extra fields being added
        if 'extra' in kwargs:
            kwargs['extra'] = self.sanitizer.sanitize_dict(kwargs['extra'])

        # Merge with adapter's extra fields
        if extra:
            if 'extra' not in kwargs:
                kwargs['extra'] = {}
            kwargs['extra'].update(extra)

        return msg, kwargs


# Global logger registry
_loggers: Dict[str, SecureLogger] = {}


def get_logger(name: str, extra: Optional[Dict[str, Any]] = None) -> SecureLogger:
    """
    Get a secure logger instance with automatic PII sanitization.

    This is the main entry point for getting loggers throughout the application.

    Args:
        name: Logger name (typically __name__)
        extra: Extra fields to include in all log records

    Returns:
        SecureLogger instance with automatic PII redaction

    Example:
        logger = get_logger(__name__)
        logger.info("User logged in", extra={'user_id': 'user123'})
        logger.warning(f"Failed login for SSN: 123-45-6789")
        # Output: Failed login for SSN: [SSN-REDACTED]
    """
    if name not in _loggers:
        base_logger = logging.getLogger(name)
        _loggers[name] = SecureLogger(base_logger, extra)

    return _loggers[name]


def configure_secure_logging(
    level: int = logging.INFO,
    format_string: Optional[str] = None,
    add_console: bool = True,
    add_file: bool = False,
    file_path: Optional[str] = None,
):
    """
    Configure secure logging for the entire application.

    Call this once at application startup to set up secure logging globally.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: Log format string (uses default if not provided)
        add_console: If True, add console handler
        add_file: If True, add file handler
        file_path: Path to log file (required if add_file=True)

    Example:
        from security.secure_logger import configure_secure_logging

        configure_secure_logging(
            level=logging.INFO,
            add_console=True,
            add_file=True,
            file_path='/var/log/tax_app.log'
        )
    """
    # Default format with timestamp, level, logger name, message
    if format_string is None:
        format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    formatter = logging.Formatter(format_string)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Add sanitizing filter to root logger
    if not any(isinstance(f, SanitizingLogFilter) for f in root_logger.filters):
        root_logger.addFilter(SanitizingLogFilter())

    # Clear existing handlers
    root_logger.handlers.clear()

    # Add console handler
    if add_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # Add file handler
    if add_file:
        if not file_path:
            raise ValueError("file_path required when add_file=True")

        file_handler = logging.FileHandler(file_path)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def sanitize_log_message(message: str) -> str:
    """
    Manually sanitize a log message.

    Useful for one-off sanitization without using the logger.

    Args:
        message: Message to sanitize

    Returns:
        Sanitized message with PII redacted

    Example:
        safe_msg = sanitize_log_message("User SSN: 123-45-6789")
        print(safe_msg)  # User SSN: [SSN-REDACTED]
    """
    return get_sanitizer().sanitize_string(message)


def sanitize_exception(exc: Exception) -> str:
    """
    Sanitize exception message and traceback.

    Args:
        exc: Exception to sanitize

    Returns:
        Sanitized exception string
    """
    import traceback

    # Get full traceback
    tb_str = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))

    # Sanitize it
    return get_sanitizer().sanitize_string(tb_str)


# Convenience functions for common logging patterns
def log_user_action(logger: SecureLogger, action: str, user_id: str, details: Optional[Dict] = None):
    """
    Log a user action with automatic sanitization.

    Args:
        logger: SecureLogger instance
        action: Action description
        user_id: User identifier (will be sanitized if it's PII)
        details: Additional details (will be sanitized)
    """
    sanitized_details = get_sanitizer().sanitize_dict(details) if details else {}
    logger.info(
        f"User action: {action}",
        extra={
            'user_id': user_id,
            'action': action,
            'details': sanitized_details
        }
    )


def log_security_event(
    logger: SecureLogger,
    event_type: str,
    severity: str,
    details: Optional[Dict] = None
):
    """
    Log a security event with high priority.

    Args:
        logger: SecureLogger instance
        event_type: Type of security event
        severity: Event severity (INFO, WARNING, ERROR, CRITICAL)
        details: Event details (will be sanitized)
    """
    sanitized_details = get_sanitizer().sanitize_dict(details) if details else {}

    level = getattr(logging, severity.upper(), logging.WARNING)
    logger.log(
        level,
        f"SECURITY: {event_type}",
        extra={
            'event_type': event_type,
            'severity': severity,
            'details': sanitized_details
        }
    )


def log_data_access(
    logger: SecureLogger,
    resource: str,
    user_id: str,
    action: str,
    success: bool = True
):
    """
    Log data access for audit compliance.

    Args:
        logger: SecureLogger instance
        resource: Resource being accessed
        user_id: User identifier
        action: Action performed (read, write, delete)
        success: Whether access succeeded
    """
    logger.info(
        f"Data access: {action} on {resource}",
        extra={
            'resource': resource,
            'user_id': user_id,
            'action': action,
            'success': success
        }
    )


# Export main interface
__all__ = [
    'get_logger',
    'configure_secure_logging',
    'sanitize_log_message',
    'sanitize_exception',
    'log_user_action',
    'log_security_event',
    'log_data_access',
    'SecureLogger',
    'SanitizingLogFilter',
]
