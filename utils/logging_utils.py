"""
Shared logging utilities for consistent status reporting across the pipeline.
Provides standardized log formatting with status indicators.
"""
from datetime import datetime


def log_info(message: str, include_timestamp: bool = False):
    """Log informational message."""
    timestamp = f"{datetime.now().isoformat()} - " if include_timestamp else ""
    print(f"[INFO] {timestamp}{message}")


def log_ok(message: str):
    """Log successful operation."""
    print(f"[OK] {message}")


def log_success(message: str):
    """Log task/pipeline completion."""
    print(f"[SUCCESS] {message}")


def log_fail(message: str):
    """Log operation failure."""
    print(f"[FAIL] {message}")


def log_warning(message: str):
    """Log non-critical issue."""
    print(f"[WARNING] {message}")


def log_start(message: str):
    """Log task/pipeline start."""
    print(f"[START] {message}")
