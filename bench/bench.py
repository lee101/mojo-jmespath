"""End-to-end mojo-jmespath versus upstream jmespath.py."""

from __future__ import annotations

import importlib
import os
import platform
import statistics
import sys
import time


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_PYTHON = os.path.join(ROOT, "python")


def _import_implementations():
    original_path = sys.path[:]
    sys.path[:] = [
        entry
        for entry in sys.path
        if os.path.abspath(entry or os.curdir) != os.path.abspath(LOCAL_PYTHON)
    ]
    upstream = importlib.import_module("jmespath")
    for name in list(sys.modules):
        if name == "jmespath" or name.startswith("jmespath."):
            sys.modules.pop(name)
    sys.path[:] = original_path
    if LOCAL_PYTHON not in sys.path:
        sys.path.insert(0, LOCAL_PYTHON)
    mojo = importlib.import_module("jmespath")
    return mojo, upstream


def measure(function, repetitions=7):
    function()
    samples = []
    for _ in range(repetitions):
        start = time.perf_counter()
        function()
        samples.append(time.perf_counter() - start)
    return statistics.median(samples)


def machine():
    model = " ".join(platform.processor().split())
    if model in ("", "x86_64", "AMD64") and os.path.exists("/proc/cpuinfo"):
        with open("/proc/cpuinfo", encoding="utf8") as cpuinfo:
            for line in cpuinfo:
                if line.startswith("model name"):
                    model = line.split(":", 1)[1].strip()
                    break
    return model or platform.machine()


def main():
    mojo, upstream = _import_implementations()
    count = 500_000
    data = {
        "rows": [
            {
                "metric": {"value": i % 1000},
                "payload": {"label": i},
                "group": i % 11,
                "tag": "keep" if i % 11 == 5 else "drop",
            }
            for i in range(count)
        ]
    }
    cases = [
        ("nested projection", "rows[*].metric.value"),
        (
            "numeric filter, 50% selected",
            "rows[?metric.value >= `500`].payload.label",
        ),
        (
            "numeric filter, 1% selected",
            "rows[?metric.value >= `990`].payload.label",
        ),
        (
            "numeric != filter, 99.9% selected",
            "rows[?metric.value != `500`].payload.label",
        ),
        (
            "string filter, 9.1% selected",
            "rows[?tag == 'keep'].payload.label",
        ),
    ]

    print(f"Machine: {machine()}")
    print(f"Input: {count:,} JSON-compatible Python records; median of 7 runs")
    print()
    print("| Query | mojo-jmespath | upstream jmespath | Speedup |")
    print("| --- | ---: | ---: | ---: |")
    for label, expression in cases:
        mojo_expression = mojo.compile(expression)
        upstream_expression = upstream.compile(expression)
        expected = upstream_expression.search(data)
        actual = mojo_expression.search(data)
        if actual != expected:
            raise AssertionError(f"benchmark parity failed for {expression}")
        mojo_seconds = measure(lambda: mojo_expression.search(data))
        upstream_seconds = measure(lambda: upstream_expression.search(data))
        speedup = upstream_seconds / mojo_seconds
        print(
            f"| {label} | {mojo_seconds * 1000:.2f} ms | "
            f"{upstream_seconds * 1000:.2f} ms | {speedup:.2f}x |"
        )


if __name__ == "__main__":
    main()
