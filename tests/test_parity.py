from collections import OrderedDict
import math

import pytest

import jmespath
from jmespath import exceptions, functions

from conftest import UPSTREAM


DOCUMENT = {
    "locations": [
        {"name": "Seattle", "state": "WA", "population": 733_919, "score": 8.2},
        {"name": "Portland", "state": "OR", "population": 652_503, "score": 7.8},
        {"name": "San Francisco", "state": "CA", "population": 815_201, "score": 9.1},
        {"name": "Los Angeles", "state": "CA", "population": 3_822_238, "score": 8.7},
        {"name": "Ghost", "state": None, "population": None},
    ],
    "meta": {"source": "census", "year": 2024},
    "nested": [[1, 2], [3], 4],
    "words": ["pear", "apple", "banana"],
}


@pytest.mark.parametrize(
    "expression",
    [
        "meta.source",
        "meta.missing",
        "locations[0].name",
        "locations[-1].name",
        "locations[1:4].name",
        "locations[::-1].name",
        "locations[*].name",
        "locations[].population",
        "meta.*",
        "nested[]",
        "locations[?state == 'CA'].name",
        "locations[?population > `700000`].name",
        "locations[?population <= `700000`].name",
        "locations[?`8.0` < score].name",
        "locations[?state == 'CA' && score > `9`].name",
        "locations[?state == 'WA' || state == 'OR'].name",
        "locations[?state != null].name",
        "locations[*].[name, state]",
        "locations[*].{city: name, region: state}",
        "locations[?state == 'CA'] | [0].name",
        "sort(words)",
        "sort_by(locations[?population != null], &population)[0].name",
        "max_by(locations[?population != null], &population).name",
        "min_by(locations[?population != null], &score).name",
        "sum(locations[].population)",
        "avg(locations[].score)",
        "length(locations)",
        "keys(meta)",
        "values(meta)",
        "contains(words, 'apple')",
        "starts_with(meta.source, 'cen')",
        "ends_with(meta.source, 'sus')",
        "reverse(words)",
        "join('-', words)",
        "type(meta)",
        "to_array(meta.year)",
        "to_number('42.5')",
        "to_string(meta.year)",
        "not_null(missing, meta.source)",
        "merge(meta, `{ \"unit\": \"people\" }`)",
        "map(&name, locations)",
        "max(`[1, 4, 2]`)",
        "min(`[1, 4, 2]`)",
        "abs(`-4.5`)",
        "ceil(`4.2`)",
        "floor(`4.8`)",
        '"meta"."source"',
        "`[1, 2, 3]`[1]",
    ],
)
def test_search_matches_upstream(expression):
    assert jmespath.search(expression, DOCUMENT) == UPSTREAM.search(
        expression, DOCUMENT
    )


@pytest.mark.parametrize("size", [128, 1000, 10_000])
def test_accelerated_projection_matches_upstream(size):
    data = {
        "rows": [
            {"payload": {"value": i if i % 7 else None}, "other": i}
            for i in range(size)
        ]
    }
    expression = "rows[*].payload.value"
    assert jmespath.search(expression, data) == UPSTREAM.search(expression, data)


@pytest.mark.parametrize("operation", ["==", "!=", "<", "<=", ">", ">="])
def test_accelerated_numeric_filters_match_upstream(operation):
    rows = []
    for i in range(2000):
        value = i % 17
        if i % 101 == 0:
            value = None
        elif i % 103 == 0:
            value = True
        rows.append({"metric": {"value": value}, "label": str(i)})
    data = {"rows": rows}
    expression = f"rows[?metric.value {operation} `8`].label"
    assert jmespath.search(expression, data) == UPSTREAM.search(expression, data)


def test_accelerated_literal_on_left_and_nested_projection():
    data = {
        "rows": [
            {"metric": {"value": i}, "payload": {"label": f"r{i}"}}
            for i in range(1000)
        ]
    }
    expression = "rows[?`995` < metric.value].payload.label"
    assert jmespath.search(expression, data) == ["r996", "r997", "r998", "r999"]
    assert jmespath.search(expression, data) == UPSTREAM.search(expression, data)


@pytest.mark.parametrize("size", [127, 128, 129, 1000])
@pytest.mark.parametrize("operation", ["==", "!="])
@pytest.mark.parametrize("literal_on_left", [False, True])
@pytest.mark.parametrize("projection", ["", ".payload.label"])
def test_string_filter_threshold_and_projection(
    size, operation, literal_on_left, projection
):
    rows = []
    for i in range(size):
        row = {"payload": {"label": i}}
        if i % 17:
            row["tag"] = "keep" if i % 5 == 0 else "drop"
        rows.append(row)
    if literal_on_left:
        predicate = f"'keep' {operation} tag"
    else:
        predicate = f"tag {operation} 'keep'"
    data = {"rows": rows}
    expression = f"rows[?{predicate}]{projection}"
    assert jmespath.search(expression, data) == UPSTREAM.search(expression, data)


def test_compiled_expression_sees_mutations():
    expression = jmespath.compile("rows[?value >= `2`].value")
    data = {"rows": [{"value": i} for i in range(500)]}
    assert expression.search(data)[0] == 2
    data["rows"][0]["value"] = 1000
    assert expression.search(data)[0] == 1000


def test_compile_cache_and_purge_match_public_api():
    first = jmespath.compile("meta.year")
    second = jmespath.compile("meta.year")
    assert first is second
    assert first.expression == "meta.year"
    assert first.search(DOCUMENT) == 2024
    jmespath.parser.Parser.purge()
    assert jmespath.compile("meta.year") is not first


def test_options_dict_class():
    options = jmespath.Options(dict_cls=OrderedDict)
    result = jmespath.search("{city: locations[0].name, year: meta.year}", DOCUMENT, options)
    assert isinstance(result, OrderedDict)
    assert list(result.items()) == [("city", "Seattle"), ("year", 2024)]


class DoubleFunctions(functions.Functions):
    @functions.signature({"types": ["number"]})
    def _func_double(self, value):
        return value * 2


def test_custom_functions():
    options = jmespath.Options(custom_functions=DoubleFunctions())
    assert jmespath.search("double(meta.year)", DOCUMENT, options) == 4048


@pytest.mark.parametrize(
    "expression, exception_type",
    [
        ("locations[", exceptions.IncompleteExpressionError),
        ("unknown_function(meta)", exceptions.UnknownFunctionError),
        ("sum(words)", exceptions.JMESPathTypeError),
        ("length()", exceptions.ArityError),
    ],
)
def test_errors_match_upstream_exception_names(expression, exception_type):
    with pytest.raises(exception_type) as local_error:
        jmespath.search(expression, DOCUMENT)
    with pytest.raises(Exception) as upstream_error:
        UPSTREAM.search(expression, DOCUMENT)
    assert type(local_error.value).__name__ == type(upstream_error.value).__name__


def test_jmespath_truth_rules():
    data = {"rows": [{"v": 0}, {"v": False}, {"v": []}, {"v": 1}]}
    assert jmespath.search("rows[?v].v", data) == [0, 1]
    assert jmespath.search("rows[?!v].v", data) == [False, []]


def test_numeric_equality_does_not_conflate_boolean():
    data = {"rows": [{"v": True}, {"v": 1}, {"v": False}, {"v": 0}] * 100}
    assert jmespath.search("rows[?v == `1`].v", data) == [1] * 100
    assert jmespath.search("rows[?v == `0`].v", data) == [0] * 100


def test_accelerated_integer_comparison_is_exact_above_float_precision():
    boundary = 2**53
    data = {
        "rows": [
            {"v": boundary + (i % 3), "i": i}
            for i in range(300)
        ]
    }
    expression = f"rows[?v == `{boundary + 1}`].i"
    assert jmespath.search(expression, data) == UPSTREAM.search(expression, data)


def test_nan_ordering_matches_upstream_for_fallback_expression():
    data = {"x": math.nan}
    assert jmespath.search("x > `1`", data) == UPSTREAM.search("x > `1`", data)


def test_accelerated_kernel_failures_are_not_silently_swallowed(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("injected kernel failure")

    monkeypatch.setattr("jmespath.visitor.mojo_lib.project", fail)
    with pytest.raises(RuntimeError, match="injected kernel failure"):
        jmespath.search("rows[*].value", {"rows": [{"value": 1}] * 128})


def test_accelerated_comparison_errors_propagate():
    class BrokenEquality:
        def __eq__(self, other):
            raise ValueError("comparison failed")

    rows = [{"value": BrokenEquality()}] * 128
    with pytest.raises(ValueError, match="comparison failed"):
        jmespath.search("rows[?value == 'x']", {"rows": rows})


@pytest.mark.parametrize("size", [127, 128])
def test_mixed_string_number_ordering_error_matches_at_threshold(size):
    data = {"rows": [{"value": "not a number"}] * size}
    with pytest.raises(TypeError):
        jmespath.search("rows[?value < `1`]", data)
