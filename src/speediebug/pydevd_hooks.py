"""Optional, defensive integration points for pydevd internals."""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence, Tuple

DEFAULT_EXCLUDE_MODULES = (
    "pandas",
    "numpy",
    "torch",
    "pydantic",
    "requests",
    "urllib3",
    "asyncio",
)

_ENVIRONMENT_FLAGS = {
    "PYDEVD_DISABLE_FILE_VALIDATION": "1",
    "PYDEVD_USE_CYTHON": "YES",
    "PYDEVD_LOAD_VALUES_ASYNC": "1",
}


@dataclass(frozen=True)
class HookResult:
    """Details about the environment and optional private hook installation."""

    environment: Mapping[str, str]
    patched_callables: int


def configure_environment(unblock_timeout: int) -> dict[str, str]:
    """Set pydevd optimization flags and return the values applied."""
    if isinstance(unblock_timeout, bool) or not isinstance(unblock_timeout, int):
        raise TypeError("unblock_timeout must be an integer")
    if unblock_timeout < 0:
        raise ValueError("unblock_timeout must be non-negative")

    values = dict(_ENVIRONMENT_FLAGS)
    values["PYDEVD_UNBLOCK_THREADS_TIMEOUT"] = str(unblock_timeout)
    for name, value in values.items():
        os.environ[name] = value
    return values


def normalize_exclusions(
    exclude_modules: Optional[Iterable[str]],
) -> Tuple[str, ...]:
    """Normalize package names, preserving order and removing duplicates."""
    values = DEFAULT_EXCLUDE_MODULES if exclude_modules is None else exclude_modules
    normalized = []
    for name in values:
        if not isinstance(name, str):
            raise TypeError("exclude_modules must contain only strings")
        package = name.strip()
        if not package:
            raise ValueError("exclude_modules cannot contain empty names")
        if package not in normalized:
            normalized.append(package)
    return tuple(normalized)


def is_excluded_module(module_name: str, excluded_modules: Iterable[str]) -> bool:
    """Return whether a module belongs to one of the configured packages."""
    if not module_name:
        return False
    for package in excluded_modules:
        if module_name == package or module_name.startswith(package + "."):
            return True
    return False


def should_trace_module(module_name: str, excluded_modules: Iterable[str]) -> bool:
    """Return the tracing decision used by speediebug's filter."""
    return not is_excluded_module(module_name, excluded_modules)


def _wrap_tracing_callable(
    original: Callable[..., Any], excluded_modules: Sequence[str]
) -> Callable[..., Any]:
    @wraps(original)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        module_name = kwargs.get("module_name") or kwargs.get("module")
        if module_name is None and args and isinstance(args[0], str):
            module_name = args[0]
        if isinstance(module_name, str) and is_excluded_module(
            module_name, excluded_modules
        ):
            return False
        return original(*args, **kwargs)

    return wrapper


def install_exclusion_filter(excluded_modules: Iterable[str]) -> HookResult:
    """Install a best-effort filter on known pydevd tracing callables.

    pydevd's private names vary by release. Unknown layouts are intentionally
    left alone; callers can always use :func:`should_trace_module` directly.
    """
    exclusions = tuple(excluded_modules)
    patched = 0
    tracing_modules = []
    for module_name in ("pydevd_tracing", "_pydevd_bundle.pydevd_tracing"):
        try:
            tracing_modules.append(importlib.import_module(module_name))
        except ImportError:
            continue

    for tracing in tracing_modules:
        for name in ("should_trace", "_should_trace"):
            candidate = getattr(tracing, name, None)
            if callable(candidate) and not getattr(
                candidate, "_speediebug_wrapper", False
            ):
                wrapped = _wrap_tracing_callable(candidate, exclusions)
                setattr(wrapped, "_speediebug_wrapper", True)
                setattr(tracing, name, wrapped)
                patched += 1

    return HookResult(environment={}, patched_callables=patched)


def install_hooks(
    exclude_modules: Iterable[str], unblock_timeout: int
) -> HookResult:
    """Apply environment flags and install any compatible pydevd filter."""
    environment = configure_environment(unblock_timeout)
    filter_result = install_exclusion_filter(exclude_modules)
    return HookResult(
        environment=environment,
        patched_callables=filter_result.patched_callables,
    )
