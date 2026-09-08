"""Speed up PyCharm debugging with safe, zero-dependency pydevd settings."""

from .core import InitResult, init, is_debugger_active

__all__ = ["InitResult", "init", "is_debugger_active"]
__version__ = "0.1.0"
