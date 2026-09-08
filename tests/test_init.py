import sys

from speediebug import core


def reset_core(monkeypatch):
    monkeypatch.setattr(core, "_INITIALIZED", False)
    monkeypatch.setattr(core, "_POST_MORTEM_INSTALLED", False)


def test_init_exits_without_debugger(monkeypatch):
    reset_core(monkeypatch)
    monkeypatch.setattr(core, "is_debugger_active", lambda: False)
    result = core.init(quiet=True)
    assert not result.enabled
    assert result.environment == {}


def test_force_initializes_and_logs(monkeypatch, capsys):
    reset_core(monkeypatch)
    monkeypatch.setattr(core, "is_debugger_active", lambda: False)
    result = core.init(
        exclude_modules=["pandas", "numpy"],
        force=True,
        unblock_timeout=4,
    )
    output = capsys.readouterr().out
    assert result.enabled
    assert not result.debugger_detected
    assert "File Validation Disabled" in output
    assert "2 packages bypassed" in output


def test_post_mortem_hook_calls_pydevd(monkeypatch):
    reset_core(monkeypatch)
    calls = []

    class FakePydevd:
        def post_mortem(self):
            calls.append("post_mortem")

    monkeypatch.setattr(core, "is_debugger_active", lambda: True)
    monkeypatch.setitem(sys.modules, "pydevd", FakePydevd())
    original = sys.excepthook
    monkeypatch.setattr(sys, "excepthook", lambda *args: calls.append("original"))
    try:
        core.init(enable_post_mortem=True, quiet=True)
        sys.excepthook(RuntimeError, RuntimeError("boom"), None)
    finally:
        monkeypatch.setattr(sys, "excepthook", original)
        monkeypatch.delitem(sys.modules, "pydevd", raising=False)
    assert calls == ["post_mortem", "original"]
