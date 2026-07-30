"""ctypes bridge to the Mojo traversal kernels."""

from __future__ import annotations

import ctypes
from functools import lru_cache
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LIB = os.environ.get("MOJO_JMESPATH_LIB") or os.path.join(
    ROOT, "dist", "libmojo-jmespath.so"
)

I = ctypes.c_int64

_SIGNATURES = {
    "mjp_project": ([I, I, I, I, I, I, I], I),
    "mjp_filter_project_number": (
        [I] * 14,
        I,
    ),
    "mjp_filter_project_string": (
        [I] * 11,
        I,
    ),
}

_loaded: ctypes.PyDLL | None = None
_NUMBER_TYPES = (int, float)


def lib() -> ctypes.PyDLL:
    global _loaded
    if _loaded is None:
        if not os.path.exists(LIB):
            raise RuntimeError(
                f"Mojo JMESPath library not found at {LIB}; run `pixi run build`"
            )
        _loaded = ctypes.PyDLL(LIB)
        for name, (argtypes, restype) in _SIGNATURES.items():
            function = getattr(_loaded, name)
            function.argtypes = argtypes
            function.restype = restype
    return _loaded


@lru_cache(maxsize=256)
def key_buffer(keys: tuple[str, ...]) -> ctypes.Array:
    # The cache retains both the strings and their packed pointer array.  A
    # one-element sentinel keeps the C-ABI pointer non-null for identity
    # projections, where depth is zero and the element is never read.
    addresses = [id(key) for key in keys] or [0]
    return (I * len(addresses))(*addresses)


def _run(function, arguments: tuple, kernel: str) -> int:
    written = function(*arguments)
    if written < 0:
        raise RuntimeError(f"Mojo {kernel} kernel failed with status {written}")
    return written


def project(source: list, keys: tuple[str, ...]) -> list:
    target = [None] * len(source)
    key_addresses = key_buffer(keys)
    written = _run(
        lib().mjp_project,
        (
            id(source), id(target), len(source), ctypes.addressof(key_addresses),
            len(keys), id(dict), id(None),
        ),
        "projection",
    )
    if written < 0:
        raise RuntimeError("Mojo projection kernel rejected its arguments")
    del target[written:]
    return target


_OPERATION = {"lt": 0, "lte": 1, "eq": 2, "ne": 3, "gt": 4, "gte": 5}
_REVERSED = {"eq": "eq", "ne": "ne", "lt": "gt", "lte": "gte", "gt": "lt", "gte": "lte"}


def filter_project_number(
    source: list,
    predicate_keys: tuple[str, ...],
    projection_keys: tuple[str, ...],
    literal: int | float,
    operation: str,
    literal_on_left: bool,
) -> list:
    if literal_on_left:
        operation = _REVERSED[operation]
    target = [None] * len(source)
    predicate_addresses = key_buffer(predicate_keys)
    projection_addresses = key_buffer(projection_keys)
    written = _run(
        lib().mjp_filter_project_number,
        (
            id(source), id(target), len(source),
            ctypes.addressof(predicate_addresses), len(predicate_keys),
            ctypes.addressof(projection_addresses), len(projection_keys),
            id(literal), _OPERATION[operation], id(dict), id(_NUMBER_TYPES),
            id(str), id(bool), id(None),
        ),
        "numeric filter",
    )
    if written < 0:
        raise RuntimeError("Mojo filter kernel rejected its arguments")
    del target[written:]
    return target


def filter_project_string(
    source: list,
    predicate_keys: tuple[str, ...],
    projection_keys: tuple[str, ...],
    literal: str,
    operation: str,
) -> list:
    target = [None] * len(source)
    predicate_addresses = key_buffer(predicate_keys)
    projection_addresses = key_buffer(projection_keys)
    written = _run(
        lib().mjp_filter_project_string,
        (
            id(source), id(target), len(source),
            ctypes.addressof(predicate_addresses), len(predicate_keys),
            ctypes.addressof(projection_addresses), len(projection_keys),
            id(literal), _OPERATION[operation], id(dict), id(None),
        ),
        "string filter",
    )
    if written < 0:
        raise RuntimeError("Mojo string filter kernel rejected its arguments")
    del target[written:]
    return target
