"""Compare unfiltered tracing with speediebug's exclusion-aware tracing.

Run from the repository root:

    python benchmarks/benchmark_debug.py --complexity 2 --repeats 3

The scientific stack is intentionally imported only when the benchmark runs.
It is an optional development dependency and is not part of speediebug's
runtime installation requirements.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, Iterable, Optional, Sequence, Tuple

from speediebug.pydevd_hooks import (
    DEFAULT_EXCLUDE_MODULES,
    is_excluded_module,
    normalize_exclusions,
)

BENCHMARK_DEFAULT_EXCLUDES = DEFAULT_EXCLUDE_MODULES + ("scipy",)


@dataclass
class TraceStats:
    """Measurements collected for one tracing mode."""

    elapsed_seconds: float
    trace_events: int


@dataclass
class BenchmarkResult:
    """Serializable result for both tracing modes."""

    complexity: int
    repeats: int
    rows: int
    pandas_loops: int
    excluded_modules: Tuple[str, ...]
    baseline: TraceStats
    speediebug: TraceStats

    @property
    def elapsed_speedup(self) -> float:
        if self.speediebug.elapsed_seconds == 0:
            return float("inf")
        return self.baseline.elapsed_seconds / self.speediebug.elapsed_seconds

    @property
    def event_reduction(self) -> float:
        if self.baseline.trace_events == 0:
            return 0.0
        return 1.0 - (
            self.speediebug.trace_events / float(self.baseline.trace_events)
        )


def workload_rows(complexity: int) -> int:
    """Return the deterministic data size for a positive complexity value."""
    if isinstance(complexity, bool) or not isinstance(complexity, int):
        raise TypeError("complexity must be an integer")
    if complexity < 1:
        raise ValueError("complexity must be at least 1")
    return 128 * complexity


def validate_pandas_loops(pandas_loops: int) -> int:
    """Validate the number of deliberately expensive pandas adjustments."""
    if isinstance(pandas_loops, bool) or not isinstance(pandas_loops, int):
        raise TypeError("pandas_loops must be an integer")
    if pandas_loops < 1:
        raise ValueError("pandas_loops must be at least 1")
    return pandas_loops


def run_workload(complexity: int, pandas_loops: int) -> float:
    """Run a mixed dataframe, array, and SciPy linear algebra workload."""
    import numpy as np
    import pandas as pd
    from scipy import linalg

    rows = workload_rows(complexity)
    rng = np.random.default_rng(42)
    values = rng.normal(size=(rows, 4))
    frame = pd.DataFrame(values, columns=("a", "b", "c", "d"))
    frame["bucket"] = np.arange(rows) % (4 + complexity)
    grouped = frame.groupby("bucket", sort=True).agg(["mean", "std"])
    for iteration in range(validate_pandas_loops(pandas_loops)):
        scale = 1.0 + (iteration % 5) / 10.0
        frame["a"] = frame["a"] * scale + frame["b"].shift(1).fillna(0.0)
        frame["adjusted"] = frame[["a", "c"]].mean(axis=1)
        frame = frame.sort_values(
            ["bucket", "adjusted"], kind="mergesort"
        ).reset_index(drop=True)
        frame["centered"] = frame["adjusted"] - frame.groupby(
            "bucket", sort=False
        )["adjusted"].transform("mean")
    matrix = np.dot(values.T, values) + np.eye(values.shape[1])
    solution = linalg.solve(matrix, values.sum(axis=0), assume_a="pos")
    return float(
        grouped.to_numpy().sum()
        + frame[["adjusted", "centered"]].to_numpy().sum()
        + solution.sum()
    )


def _trace_factory(
    excluded_modules: Optional[Iterable[str]],
    counter: Dict[str, int],
) -> Callable[..., Any]:
    exclusions = tuple(excluded_modules or ())

    def trace(frame: Any, event: str, arg: Any) -> Callable[..., Any]:
        module_name = frame.f_globals.get("__name__", "")
        if event == "call" and is_excluded_module(module_name, exclusions):
            return None
        counter["events"] += 1
        return trace

    return trace


def measure(
    complexity: int,
    pandas_loops: int,
    excluded_modules: Optional[Sequence[str]],
) -> TraceStats:
    """Measure one workload run with either a full or filtered trace."""
    counter = {"events": 0}
    tracer = _trace_factory(excluded_modules, counter)
    started = time.perf_counter()
    previous_trace = sys.gettrace()
    sys.settrace(tracer)
    try:
        run_workload(complexity, pandas_loops)
    finally:
        sys.settrace(previous_trace)
    return TraceStats(
        elapsed_seconds=time.perf_counter() - started,
        trace_events=counter["events"],
    )


def run_benchmark(
    complexity: int,
    repeats: int,
    excluded_modules: Optional[Iterable[str]] = None,
    pandas_loops: int = 8,
) -> BenchmarkResult:
    """Run baseline and speediebug measurements and average repeated runs."""
    if isinstance(repeats, bool) or not isinstance(repeats, int):
        raise TypeError("repeats must be an integer")
    if repeats < 1:
        raise ValueError("repeats must be at least 1")
    pandas_loops = validate_pandas_loops(pandas_loops)
    exclusions = normalize_exclusions(excluded_modules)
    _require_scientific_stack()
    baseline_runs = [
        measure(complexity, pandas_loops, ()) for _ in range(repeats)
    ]
    optimized_runs = [
        measure(complexity, pandas_loops, exclusions) for _ in range(repeats)
    ]

    def average(runs: Sequence[TraceStats]) -> TraceStats:
        return TraceStats(
            elapsed_seconds=statistics.mean(item.elapsed_seconds for item in runs),
            trace_events=int(
                statistics.mean(item.trace_events for item in runs)
            ),
        )

    return BenchmarkResult(
        complexity=complexity,
        repeats=repeats,
        rows=workload_rows(complexity),
        pandas_loops=pandas_loops,
        excluded_modules=exclusions,
        baseline=average(baseline_runs),
        speediebug=average(optimized_runs),
    )


def _require_scientific_stack() -> None:
    """Import optional benchmark dependencies before tracing begins."""
    import numpy  # noqa: F401
    import pandas  # noqa: F401
    import scipy  # noqa: F401


def format_result(result: BenchmarkResult) -> str:
    """Format a human-readable benchmark summary."""
    return "\n".join(
        (
            "speediebug debug benchmark",
            "  workload: %d rows (complexity=%d), %d pandas loop(s), %d repeat(s)"
            % (
                result.rows,
                result.complexity,
                result.pandas_loops,
                result.repeats,
            ),
            "  baseline:    %.4fs, %d trace events"
            % (
                result.baseline.elapsed_seconds,
                result.baseline.trace_events,
            ),
            "  speediebug:  %.4fs, %d trace events"
            % (
                result.speediebug.elapsed_seconds,
                result.speediebug.trace_events,
            ),
            "  comparison:  %.2fx elapsed speedup, %.1f%% fewer trace events"
            % (result.elapsed_speedup, result.event_reduction * 100),
            "  exclusions:  %s" % (", ".join(result.excluded_modules)),
        )
    )


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare full tracing with speediebug module exclusions."
    )
    parser.add_argument(
        "--complexity",
        type=int,
        default=1,
        help="Scale the deterministic workload (default: 1).",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=3,
        help="Measurements per mode (default: 3).",
    )
    parser.add_argument(
        "--pandas-loops",
        type=int,
        default=8,
        help="Heavy pandas adjustment loops per workload (default: 8).",
    )
    parser.add_argument(
        "--exclude",
        nargs="+",
        default=list(BENCHMARK_DEFAULT_EXCLUDES),
        help="Package prefixes excluded from the optimized trace.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of the summary.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        result = run_benchmark(
            args.complexity,
            args.repeats,
            args.exclude,
            args.pandas_loops,
        )
    except ImportError as error:
        raise SystemExit(
            "The benchmark requires pandas, numpy, and scipy. "
            "Install them with: python -m pip install pandas numpy scipy"
        ) from error
    if args.json:
        payload = asdict(result)
        payload["elapsed_speedup"] = result.elapsed_speedup
        payload["event_reduction"] = result.event_reduction
        print(json.dumps(payload, indent=2))
    else:
        print(format_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
