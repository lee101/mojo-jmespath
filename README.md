# mojo-jmespath

`mojo-jmespath` is the upstream Python JMESPath implementation with Mojo kernels
for a few common list traversals. Expressions outside those kernels continue
through the vendored upstream parser and interpreter.

## Install and use

The current release builds from source on Linux:

```bash
pixi install
pixi run build
pixi run python - <<'PY'
import jmespath

document = {
    "cities": [
        {"name": "Seattle", "region": "north"},
        {"name": "Portland", "region": "south"},
        {"name": "Vancouver", "region": "north"},
    ]
}

result = jmespath.search(
    "cities[?region == 'north'].name",
    document,
)
assert result == ["Seattle", "Vancouver"]
print(result)
PY
```

`pixi run test` runs the parity suite. `pixi run bench` reproduces the table
below. `MOJO_JMESPATH_LIB` may point to a compatible shared library in a
non-default location.

## Coverage and limitations

The Python path is derived from upstream `jmespath.py` and provides:

- `search`, `compile`, and compiled expression reuse
- fields, indexes, slices, wildcards, flattening, pipes, and projections
- comparisons, logical expressions, literals, expression references, and
  multi-selects
- every standard upstream function
- `Options`, custom functions, custom result dictionaries, and upstream
  exception classes

The test suite exercises every item above, invokes every standard function, and
compares results and representative failures with the separately installed
upstream package.

Mojo accelerates only:

- list projections with an identity or nested-field result
- numeric-literal filters with a nested-field predicate
- string-literal equality and inequality filters with a nested-field predicate

The accelerated shapes are tested at the dispatch boundary and at several input
sizes. Small lists use the Python visitor. Parsing, slices, logical predicates,
object projections, sorting, and function dispatch are not implemented in
Mojo; they are supported by the Python compatibility path and receive no Mojo
speedup.

Inputs should be ordinary JSON-compatible Python lists, dictionaries, strings,
numbers, booleans, and nulls. Custom mapping behavior and arbitrary numeric
classes are outside the accelerated contract. This project does not add the
optional upstream compliance-data suite, so it does not claim validation
against every expression in that external corpus.

## Benchmarks

This is the literal output of `pixi run bench` on the publishing machine. The
benchmark compiles each expression before timing and includes result allocation
and traversal.

Machine: Intel(R) Xeon(R) CPU E5-2697 v4 @ 2.30GHz

Input: 500,000 JSON-compatible Python records; median of 7 runs

| Query | mojo-jmespath | upstream jmespath | Speedup |
| --- | ---: | ---: | ---: |
| nested projection | 68.82 ms | 866.22 ms | 12.59x |
| numeric filter, 50% selected | 77.82 ms | 2230.15 ms | 28.66x |
| numeric filter, 1% selected | 64.28 ms | 1884.80 ms | 29.32x |
| numeric != filter, 99.9% selected | 91.70 ms | 2556.46 ms | 27.88x |
| string filter, 9.1% selected | 53.02 ms | 1486.50 ms | 28.04x |

Results vary with hardware, record shape, and selectivity. Non-accelerated
expressions run through the Python visitor.

## How it works

The Pratt parser produces an AST. The visitor recognizes the accelerated AST
shapes and otherwise evaluates the AST in Python.

For an accelerated expression, Python preallocates the result list and passes
the source list, result list, field-name pointers, and validated dimensions
through a C ABI. `ctypes.PyDLL` keeps the GIL held, so Mojo can use CPython list
and dictionary APIs safely. The bridge retains the source, destination,
literals, field strings, and packed pointer buffers for the whole call. Mojo
checks list sizes, depths, operation codes, required pointers for null,
comparison errors, and list writes. Each returned borrowed reference is
incremented before being placed in the result list.

The kernels are scalar CPU traversal. There is no SIMD or threading path: the
work follows non-contiguous Python objects and calls the CPython API while
holding the GIL. These pointer-chasing kernels have negligible arithmetic
intensity, so a GPU path is not justified; transferring object data would cost
more than the comparisons themselves.

MIT licensed. See `LICENSE`.
