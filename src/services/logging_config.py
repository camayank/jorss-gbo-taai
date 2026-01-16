"""
Logging Configuration for Tax Decision Intelligence Platform.

Provides structured logging with:
- JSON formatting for production
- Human-readable formatting for development
- Calculation-specific logging for audit trails
- Performance metrics tracking
"""

import logging
import json
import sys
import time
from datetime import datetime
from typing import Optional, Dict, Any, Callable
from functools import wraps
from uuid import UUID
from pathlib import Path
from contextvars import ContextVar

# Context variables for request tracking
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar('user_id', default=None)


class JsonFormatter(logging.Formatter):
    """
    JSON log formatter for structured logging.

    Outputs logs as JSON objects for easy parsing by log aggregators.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add context variables
        request_id = request_id_var.get()
        if request_id:
            log_data["request_id"] = request_id

        user_id = user_id_var.get()
        if user_id:
            log_data["user_id"] = user_id

        # Add extra fields from the record
        if hasattr(record, 'extra_data'):
            log_data.update(record.extra_data)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


class ReadableFormatter(logging.Formatter):
    """
    Human-readable log formatter for development.
    """

    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m',
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format log record for human readability."""
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']

        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        level = f"{color}{record.levelname:8s}{reset}"

        message = f"{timestamp} {level} [{record.name}] {record.getMessage()}"

        # Add extra fields
        if hasattr(record, 'extra_data') and record.extra_data:
            extras = ' | '.join(f"{k}={v}" for k, v in record.extra_data.items())
            message += f" | {extras}"

        return message


class ContextLogger(logging.LoggerAdapter):
    """
    Logger adapter that includes context in all log messages.
    """

    def process(self, msg: str, kwargs: Dict) -> tuple:
        """Add context to log message."""
        extra = kwargs.get('extra', {})

        # Add context variables
        request_id = request_id_var.get()
        if request_id:
            extra['request_id'] = request_id

        user_id = user_id_var.get()
        if user_id:
            extra['user_id'] = user_id

        # Merge with any existing extra data
        if 'extra_data' not in extra:
            extra['extra_data'] = {}
        extra['extra_data'].update(self.extra)

        kwargs['extra'] = extra
        return msg, kwargs


def configure_logging(
    level: str = "INFO",
    json_output: bool = False,
    log_file: Optional[Path] = None
) -> None:
    """
    Configure application logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: If True, output JSON formatted logs
        log_file: Optional file path for log output
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create formatter
    if json_output:
        formatter = JsonFormatter()
    else:
        formatter = ReadableFormatter()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler if specified
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(JsonFormatter())  # Always JSON for files
        root_logger.addHandler(file_handler)

    # Set levels for noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str, **extra) -> ContextLogger:
    """
    Get a context-aware logger.

    Args:
        name: Logger name (typically __name__)
        **extra: Additional context to include in all logs

    Returns:
        ContextLogger instance
    """
    base_logger = logging.getLogger(name)
    return ContextLogger(base_logger, extra)


class CalculationLogger:
    """
    Specialized logger for tax calculations.

    Provides detailed logging of:
    - Calculation inputs
    - Step-by-step computation
    - Performance metrics
    - Results and validation
    """

    def __init__(self, return_id: Optional[UUID] = None):
        """
        Initialize calculation logger.

        Args:
            return_id: Tax return ID for correlation
        """
        self.logger = get_logger(
            "calculation",
            return_id=str(return_id) if return_id else None
        )
        self.return_id = return_id
        self._start_time: Optional[float] = None
        self._step_times: Dict[str, float] = {}

    def start_calculation(self, tax_year: int, filing_status: str) -> None:
        """Log calculation start."""
        self._start_time = time.time()
        self.logger.info(
            "Starting tax calculation",
            extra={'extra_data': {
                'tax_year': tax_year,
                'filing_status': filing_status,
                'return_id': str(self.return_id) if self.return_id else None,
            }}
        )

    def log_step(self, step_name: str, **data) -> None:
        """
        Log a calculation step.

        Args:
            step_name: Name of the step
            **data: Step-specific data to log
        """
        step_start = time.time()
        self.logger.debug(
            f"Calculation step: {step_name}",
            extra={'extra_data': {
                'step': step_name,
                **data
            }}
        )
        return step_start

    def complete_step(self, step_name: str, step_start: float, **result) -> None:
        """
        Log step completion with timing.

        Args:
            step_name: Name of the step
            step_start: Start time from log_step
            **result: Step results
        """
        duration_ms = int((time.time() - step_start) * 1000)
        self._step_times[step_name] = duration_ms
        self.logger.debug(
            f"Completed step: {step_name}",
            extra={'extra_data': {
                'step': step_name,
                'duration_ms': duration_ms,
                **result
            }}
        )

    def log_income(
        self,
        gross_income: float,
        adjustments: float,
        agi: float
    ) -> None:
        """Log income calculation."""
        self.logger.info(
            "Income calculated",
            extra={'extra_data': {
                'gross_income': gross_income,
                'adjustments': adjustments,
                'agi': agi,
            }}
        )

    def log_deductions(
        self,
        deduction_type: str,
        deduction_amount: float,
        taxable_income: float
    ) -> None:
        """Log deduction calculation."""
        self.logger.info(
            "Deductions calculated",
            extra={'extra_data': {
                'deduction_type': deduction_type,
                'deduction_amount': deduction_amount,
                'taxable_income': taxable_income,
            }}
        )

    def log_tax(
        self,
        ordinary_tax: float,
        preferential_tax: float,
        se_tax: float,
        total_before_credits: float
    ) -> None:
        """Log tax calculation."""
        self.logger.info(
            "Tax computed",
            extra={'extra_data': {
                'ordinary_tax': ordinary_tax,
                'preferential_tax': preferential_tax,
                'se_tax': se_tax,
                'total_before_credits': total_before_credits,
            }}
        )

    def log_credits(
        self,
        nonrefundable: float,
        refundable: float,
        total_credits: float
    ) -> None:
        """Log credit calculation."""
        self.logger.info(
            "Credits calculated",
            extra={'extra_data': {
                'nonrefundable_credits': nonrefundable,
                'refundable_credits': refundable,
                'total_credits': total_credits,
            }}
        )

    def log_result(
        self,
        total_tax: float,
        total_payments: float,
        refund_or_owed: float,
        effective_rate: float
    ) -> None:
        """Log final calculation result."""
        duration_ms = int((time.time() - self._start_time) * 1000) if self._start_time else 0

        self.logger.info(
            "Calculation complete",
            extra={'extra_data': {
                'total_tax': total_tax,
                'total_payments': total_payments,
                'refund_or_owed': refund_or_owed,
                'effective_rate': effective_rate,
                'duration_ms': duration_ms,
                'step_times': self._step_times,
            }}
        )

    def log_warning(self, message: str, **data) -> None:
        """Log calculation warning."""
        self.logger.warning(
            message,
            extra={'extra_data': data}
        )

    def log_error(self, message: str, **data) -> None:
        """Log calculation error."""
        self.logger.error(
            message,
            extra={'extra_data': data}
        )

    def log_validation_error(self, field: str, error: str, value: Any = None) -> None:
        """Log validation error."""
        self.logger.error(
            f"Validation failed: {field}",
            extra={'extra_data': {
                'field': field,
                'error': error,
                'value': value,
            }}
        )


def log_performance(name: Optional[str] = None) -> Callable:
    """
    Decorator to log function performance.

    Args:
        name: Optional name override for the log entry

    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        func_name = name or func.__name__

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_logger("performance")
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                duration_ms = int((time.time() - start) * 1000)
                logger.info(
                    f"{func_name} completed",
                    extra={'extra_data': {'duration_ms': duration_ms}}
                )
                return result
            except Exception as e:
                duration_ms = int((time.time() - start) * 1000)
                logger.error(
                    f"{func_name} failed",
                    extra={'extra_data': {
                        'duration_ms': duration_ms,
                        'error': str(e),
                    }}
                )
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_logger("performance")
            start = time.time()
            try:
                result = func(*args, **kwargs)
                duration_ms = int((time.time() - start) * 1000)
                logger.info(
                    f"{func_name} completed",
                    extra={'extra_data': {'duration_ms': duration_ms}}
                )
                return result
            except Exception as e:
                duration_ms = int((time.time() - start) * 1000)
                logger.error(
                    f"{func_name} failed",
                    extra={'extra_data': {
                        'duration_ms': duration_ms,
                        'error': str(e),
                    }}
                )
                raise

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
