"""Structured JSON logging for production observability."""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from .config import Config


class JSONFormatter(logging.Formatter):
    """Format log records as JSON for Cloud Logging compatibility."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "severity": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields if present
        if hasattr(record, "session_id"):
            log_entry["session_id"] = record.session_id
        if hasattr(record, "agent"):
            log_entry["agent"] = record.agent
        if hasattr(record, "pipeline"):
            log_entry["pipeline"] = record.pipeline
        if hasattr(record, "step"):
            log_entry["step"] = record.step
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


class DevelopmentFormatter(logging.Formatter):
    """Human-readable format for local development."""

    def format(self, record: logging.LogRecord) -> str:
        # Add color codes for different levels
        colors = {
            "DEBUG": "\033[36m",  # Cyan
            "INFO": "\033[32m",  # Green
            "WARNING": "\033[33m",  # Yellow
            "ERROR": "\033[31m",  # Red
            "CRITICAL": "\033[35m",  # Magenta
        }
        reset = "\033[0m"

        level_color = colors.get(record.levelname, "")
        prefix = f"{level_color}[{record.levelname}]{reset}"

        # Add context if available
        context_parts = []
        if hasattr(record, "agent"):
            context_parts.append(f"agent={record.agent}")
        if hasattr(record, "step"):
            context_parts.append(f"step={record.step}")

        context = f" ({', '.join(context_parts)})" if context_parts else ""

        return f"{prefix} {record.name}{context}: {record.getMessage()}"


def setup_logging(level: int = logging.INFO) -> None:
    """Configure logging for the application.

    Uses JSON format in production, human-readable format locally.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    # Use JSON in production, readable format locally
    if Config.is_production():
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(DevelopmentFormatter())

    root_logger.addHandler(handler)

    # Reduce noise from external libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name."""
    return logging.getLogger(name)


class LogContext:
    """Context manager for adding extra fields to log records."""

    def __init__(self, logger: logging.Logger, **kwargs: Any):
        self.logger = logger
        self.extra = kwargs

    def __enter__(self) -> logging.Logger:
        # Create adapter with extra fields
        return logging.LoggerAdapter(self.logger, self.extra)

    def __exit__(self, *args: Any) -> None:
        pass
