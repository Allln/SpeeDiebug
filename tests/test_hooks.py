import os
import sys
import types

import pytest

from speediebug.pydevd_hooks import (
    DEFAULT_EXCLUDE_MODULES,
    configure_environment,
    install_exclusion_filter,
    is_excluded_module,
    normalize_exclusions,
)


def test_configure_environment_sets_all_flags(monkeypatch):
    for name in (
        "PYDEVD_DISABLE_FILE_VALIDATION",
        "PYDEVD_USE_CYTHON",
        "PYDEVD_LOAD_VALUES_ASYNC",
        "PYDEVD_UNBLOCK_THREADS_TIMEOUT",
    ):
        monkeypatch.delenv(name, raising=False)
    values = configure_environment(7)
    assert values["PYDEVD_DISABLE_FILE_VALIDATION"] == "1"
    assert values["PYDEVD_USE_CYTHON"] == "YES"
    assert values["PYDEVD_LOAD_VALUES_ASYNC"] == "1"
    assert os.environ["PYDEVD_UNBLOCK_THREADS_TIMEOUT"] == "7"


def test_default_exclusions_and_module_boundaries():
    assert normalize_exclusions(None) == DEFAULT_EXCLUDE_MODULES
    assert is_excluded_module("pandas.core", ("pandas",))
    assert not is_excluded_module("pandas_tools", ("pandas",))


def test_exclusion_validation():
    with pytest.raises(TypeError):
        normalize_exclusions(["pandas", 3])
    with pytest.raises(ValueError):
        normalize_exclusions([""])
    with pytest.raises(ValueError):
        configure_environment(-1)


def test_install_exclusion_filter_wraps_pydevd_bundle(monkeypatch):
    tracing = types.ModuleType("_pydevd_bundle.pydevd_tracing")

    def should_trace(module_name):
        return module_name == "application"

    tracing.should_trace = should_trace
    monkeypatch.setitem(sys.modules, "_pydevd_bundle.pydevd_tracing", tracing)
    result = install_exclusion_filter(("pandas",))
    assert result.patched_callables == 1
    assert tracing.should_trace("pandas.core") is False
    assert tracing.should_trace("application") is True
