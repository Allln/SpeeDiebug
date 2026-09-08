import sys

from speediebug.core import is_debugger_active


def test_detection_finds_loaded_pydevd(monkeypatch):
    monkeypatch.delenv("PYCHARM_HOSTED", raising=False)
    monkeypatch.delenv("PYDEV_COMPLETER_PYTHONPATH", raising=False)
    monkeypatch.setitem(sys.modules, "pydevd", object())
    try:
        assert is_debugger_active()
    finally:
        monkeypatch.delitem(sys.modules, "pydevd", raising=False)


def test_detection_finds_pycharm_environment(monkeypatch):
    monkeypatch.setenv("PYCHARM_HOSTED", "1")
    assert is_debugger_active()


def test_detection_is_false_without_indicators(monkeypatch):
    monkeypatch.delenv("PYCHARM_HOSTED", raising=False)
    monkeypatch.delenv("PYDEV_COMPLETER_PYTHONPATH", raising=False)
    monkeypatch.delitem(sys.modules, "pydevd", raising=False)
    monkeypatch.delitem(sys.modules, "_pydevd_bundle", raising=False)
    monkeypatch.setattr(sys, "gettrace", lambda: None)
    assert not is_debugger_active()
