import importlib.util
from pathlib import Path
import sys

import pytest


SCRIPT = Path(__file__).parents[1] / "benchmarks" / "benchmark_debug.py"
SPEC = importlib.util.spec_from_file_location("benchmark_debug", SCRIPT)
benchmark = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["benchmark_debug"] = benchmark
SPEC.loader.exec_module(benchmark)


def test_workload_rows_scales_with_complexity():
    assert benchmark.workload_rows(1) == 128
    assert benchmark.workload_rows(3) == 384


def test_workload_rows_rejects_invalid_complexity():
    with pytest.raises(ValueError):
        benchmark.workload_rows(0)
    with pytest.raises(TypeError):
        benchmark.workload_rows(True)


def test_pandas_loop_validation():
    assert benchmark.validate_pandas_loops(4) == 4
    with pytest.raises(ValueError):
        benchmark.validate_pandas_loops(0)
    with pytest.raises(TypeError):
        benchmark.validate_pandas_loops(True)


def test_parse_args_defaults_and_overrides():
    defaults = benchmark._parse_args([])
    assert defaults.complexity == 1
    assert defaults.repeats == 3
    assert defaults.pandas_loops == 8
    assert "scipy" in defaults.exclude

    custom = benchmark._parse_args(
        [
            "--complexity",
            "4",
            "--repeats",
            "2",
            "--pandas-loops",
            "12",
            "--exclude",
            "pandas",
            "numpy",
        ]
    )
    assert custom.complexity == 4
    assert custom.repeats == 2
    assert custom.pandas_loops == 12
    assert custom.exclude == ["pandas", "numpy"]


def test_trace_factory_filters_excluded_modules():
    counter = {"events": 0}
    tracer = benchmark._trace_factory(("pandas",), counter)

    class Frame:
        f_globals = {"__name__": "pandas.core"}

    assert tracer(Frame(), "call", None) is None
    assert counter["events"] == 0


def test_format_result_contains_comparison_metrics():
    stats = benchmark.TraceStats(1.0, 100)
    result = benchmark.BenchmarkResult(
        complexity=1,
        repeats=1,
        rows=128,
        pandas_loops=8,
        excluded_modules=("pandas",),
        baseline=stats,
        speediebug=benchmark.TraceStats(0.5, 50),
    )
    output = benchmark.format_result(result)
    assert "2.00x elapsed speedup" in output
    assert "50.0% fewer trace events" in output
