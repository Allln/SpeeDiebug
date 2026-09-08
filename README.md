# speediebug

[![PyPI](https://img.shields.io/pypi/v/speediebug.svg)](https://pypi.org/project/speediebug/)
[![Python](https://img.shields.io/pypi/pyversions/speediebug.svg)](https://pypi.org/project/speediebug/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Build](https://github.com/Allln/SpeeDiebug/actions/workflows/publish.yml/badge.svg)](https://github.com/Allln/SpeeDiebug/actions/workflows/publish.yml)

`speediebug` is a zero-dependency helper for making PyCharm's `pydevd` debugger
less disruptive in projects that use large third-party packages.

## Quickstart

```console
pip install speediebug
```

Add two lines to the application's entry point:

```python
import speediebug

speediebug.init()
```

When no debugger is active, initialization returns immediately. In PyCharm,
the default configuration disables repeated file validation, requests async
value loading and Cython-backed pydevd paths, and avoids stepping through
common heavy packages.

## Configuration

```python
speediebug.init(
    exclude_modules=["pandas", "numpy", "torch"],
    enable_post_mortem=False,
    quiet=False,
    force=False,
    unblock_timeout=10,
)
```

`force=True` is useful for testing or non-PyCharm debugger environments.
`enable_post_mortem=True` calls `pydevd.post_mortem()` for uncaught exceptions
when that API is available. Private pydevd layouts vary between releases, so
unsupported tracing hook layouts are left unchanged rather than breaking an
application.

## Recommended PyCharm settings

- Enable the pydevd Cython speedup when PyCharm offers it.
- Keep *Do not step into library scripts* enabled.
- Add generated code and known high-volume vendor directories to PyCharm's
  *Stepping* filters.
- Disable Gevent or PyQt debugger integration unless the project needs it.
- Prefer conditional or function breakpoints in hot loops over line
  breakpoints in third-party code.

## Why it helps

Every traced Python frame can trigger breakpoint bookkeeping and object
representation requests. Large libraries multiply that work even when the
developer only needs to inspect application code. `speediebug` configures
pydevd's file-validation and asynchronous-value flags early, then supplies
package-boundary filtering for compatible pydevd versions. This reduces
filesystem checks and avoids repeatedly entering heavy dependency frames.

The benefit depends on the project and breakpoint mix; workloads with many
third-party frames generally see the largest improvement. The library does
not change application execution when no debugger is detected.

## Development

```console
python -m pytest
```

The package has no runtime dependencies and supports Python 3.8 and newer.

## License

MIT
