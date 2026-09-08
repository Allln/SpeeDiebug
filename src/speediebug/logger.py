"""Console formatting for speediebug initialization diagnostics."""

from __future__ import annotations

from typing import Iterable, Optional, TextIO


def format_summary(
    *,
    debugger_version: str,
    excluded_modules: Iterable[str],
    cython_active: bool = True,
    stream: Optional[TextIO] = None,
) -> str:
    """Return the compact three-line initialization summary."""
    excluded = list(excluded_modules)
    version = debugger_version or "unknown"
    cython_status = "Active" if cython_active else "Requested"
    lines = [
        "[speediebug] PyCharm Debugger Detected (pydevd v%s)" % version,
        "[speediebug] Optimizations: File Validation Disabled | Cython %s | Async Values"
        % cython_status,
        "[speediebug] Excluded Tracing: %s (%d packages bypassed)"
        % (excluded, len(excluded)),
    ]
    return "\n".join(lines)


def print_summary(
    *,
    debugger_version: str,
    excluded_modules: Iterable[str],
    cython_active: bool = True,
    stream: Optional[TextIO] = None,
) -> None:
    """Write the initialization summary to the requested stream."""
    import sys

    output = stream if stream is not None else sys.stdout
    print(
        format_summary(
            debugger_version=debugger_version,
            excluded_modules=excluded_modules,
            cython_active=cython_active,
        ),
        file=output,
    )
