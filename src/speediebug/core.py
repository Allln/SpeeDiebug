"""Public initialization and debugger detection."""

from __future__ import annotations

import importlib
import os
import sys
from dataclasses import dataclass
from types import TracebackType
from typing import Iterable, Optional

from .logger import print_summary
from .pydevd_hooks import (
    DEFAULT_EXCLUDE_MODULES,
    HookResult,
    install_hooks,
    normalize_exclusions,
)

_INITIALIZED = False
_POST_MORTEM_INSTALLED = False


@dataclass(frozen=True)
class InitResult:
    """Result returned by :func:`init`."""

    enabled: bool
    debugger_detected: bool
    excluded_modules: tuple[str, ...]
    environment: dict[str, str]
    patched_callables: int


def _pydevd_loaded() -> bool:
    return any(
        name == "pydevd"
        or name.startswith("pydevd.")
        or name == "_pydevd_bundle"
        or name.startswith("_pydevd_bundle.")
        for name in sys.modules
    )


def is_debugger_active() -> bool:
    """Detect PyCharm/pydevd without importing the debugger."""
    if _pydevd_loaded():
        return True
    if os.environ.get("PYCHARM_HOSTED") or os.environ.get(
        "PYDEV_COMPLETER_PYTHONPATH"
    ):
        return True
    return sys.gettrace() is not None


def _debugger_version() -> str:
    for module_name in ("pydevd", "_pydevd_bundle"):
        module = sys.modules.get(module_name)
        if module is not None:
            version = getattr(module, "__version__", None)
            if version:
                return str(version)
    try:
        module = importlib.import_module("pydevd")
    except ImportError:
        return "unknown"
    return str(getattr(module, "__version__", "unknown"))


def _install_post_mortem() -> None:
    global _POST_MORTEM_INSTALLED
    if _POST_MORTEM_INSTALLED:
        return
    previous_hook = sys.excepthook

    def hook(
        exception_type: type[BaseException],
        exception: BaseException,
        traceback: Optional[TracebackType],
    ) -> None:
        try:
            pydevd = importlib.import_module("pydevd")
        except ImportError:
            previous_hook(exception_type, exception, traceback)
            return
        post_mortem = getattr(pydevd, "post_mortem", None)
        if callable(post_mortem):
            post_mortem()
        previous_hook(exception_type, exception, traceback)

    sys.excepthook = hook
    _POST_MORTEM_INSTALLED = True


def init(
    exclude_modules: Optional[Iterable[str]] = None,
    *,
    enable_post_mortem: bool = False,
    quiet: bool = False,
    force: bool = False,
    unblock_timeout: int = 10,
) -> InitResult:
    """Enable speediebug optimizations when a debugger is active."""
    global _INITIALIZED
    exclusions = normalize_exclusions(exclude_modules)
    detected = is_debugger_active()
    if not detected and not force:
        return InitResult(
            enabled=False,
            debugger_detected=False,
            excluded_modules=exclusions,
            environment={},
            patched_callables=0,
        )

    if not _INITIALIZED:
        hooks = install_hooks(exclusions, unblock_timeout)
        _INITIALIZED = True
    else:
        hooks = HookResult(environment={}, patched_callables=0)

    if enable_post_mortem:
        _install_post_mortem()
    if not quiet:
        print_summary(
            debugger_version=_debugger_version(),
            excluded_modules=exclusions,
        )
    return InitResult(
        enabled=True,
        debugger_detected=detected,
        excluded_modules=exclusions,
        environment=dict(hooks.environment),
        patched_callables=hooks.patched_callables,
    )
