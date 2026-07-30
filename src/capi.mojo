"""Bulk JMESPath list traversal through CPython's stable object API."""

from std.ffi import external_call


comptime KeyPtr = UnsafePointer[Int64, AnyOrigin[mut=True]]


@always_inline
def _is_instance(value: Int, type_object: Int) -> Bool:
    return external_call["PyObject_IsInstance", Int32](value, type_object) > 0


@always_inline
def _lookup(
    value: Int,
    keys: KeyPtr,
    depth: Int,
    dict_type: Int,
) -> Int:
    var current = value
    for level in range(depth):
        if current == 0 or not _is_instance(current, dict_type):
            return 0
        current = external_call["PyDict_GetItem", Int](current, Int(keys[level]))
    return current


@always_inline
def _append_borrowed(target: Int, position: Int, value: Int) -> Int32:
    external_call["Py_IncRef", NoneType](value)
    return external_call["PyList_SetItem", Int32](target, position, value)


@export("mjp_project")
def mjp_project(
    source: Int,
    target: Int,
    count: Int,
    keys_address: Int,
    depth: Int,
    dict_type: Int,
    none_object: Int,
) abi("C") -> Int:
    if (
        source == 0
        or target == 0
        or count < 0
        or depth < 0
        or keys_address == 0
        or dict_type == 0
        or none_object == 0
        or external_call["PyList_Size", Int](source) != count
        or external_call["PyList_Size", Int](target) < count
    ):
        return -1
    var keys = KeyPtr(unsafe_from_address=keys_address)
    var written = 0
    for i in range(count):
        var element = external_call["PyList_GetItem", Int](source, i)
        var projected = _lookup(element, keys, depth, dict_type)
        if projected != 0 and projected != none_object:
            if _append_borrowed(target, written, projected) != 0:
                return -2
            written += 1
    return written


@export("mjp_filter_project_number")
def mjp_filter_project_number(
    source: Int,
    target: Int,
    count: Int,
    predicate_keys_address: Int,
    predicate_depth: Int,
    projection_keys_address: Int,
    projection_depth: Int,
    literal: Int,
    operation: Int,
    dict_type: Int,
    number_types: Int,
    string_type: Int,
    bool_type: Int,
    none_object: Int,
) abi("C") -> Int:
    if (
        source == 0
        or target == 0
        or count < 0
        or predicate_depth <= 0
        or projection_depth < 0
        or predicate_keys_address == 0
        or projection_keys_address == 0
        or literal == 0
        or operation < 0
        or operation > 5
        or dict_type == 0
        or number_types == 0
        or string_type == 0
        or bool_type == 0
        or none_object == 0
        or external_call["PyList_Size", Int](source) != count
        or external_call["PyList_Size", Int](target) < count
    ):
        return -1
    var predicate_keys = KeyPtr(unsafe_from_address=predicate_keys_address)
    var projection_keys = KeyPtr(unsafe_from_address=projection_keys_address)
    var written = 0
    for i in range(count):
        var element = external_call["PyList_GetItem", Int](source, i)
        var candidate = _lookup(
            element, predicate_keys, predicate_depth, dict_type
        )
        var comparable = (
            candidate != 0
            and not _is_instance(candidate, bool_type)
            and (
                _is_instance(candidate, number_types)
                or _is_instance(candidate, string_type)
            )
        )
        if comparable:
            var compared = external_call["PyObject_RichCompareBool", Int32](
                candidate, literal, operation
            )
            if compared < 0:
                return -2
            if compared != 1:
                continue
        elif operation != 3:
            continue
        var projected = element
        if projection_depth > 0:
            projected = _lookup(
                element, projection_keys, projection_depth, dict_type
            )
        if projected != 0 and projected != none_object:
            if _append_borrowed(target, written, projected) != 0:
                return -2
            written += 1
    return written


@export("mjp_filter_project_string")
def mjp_filter_project_string(
    source: Int,
    target: Int,
    count: Int,
    predicate_keys_address: Int,
    predicate_depth: Int,
    projection_keys_address: Int,
    projection_depth: Int,
    literal: Int,
    operation: Int,
    dict_type: Int,
    none_object: Int,
) abi("C") -> Int:
    if (
        source == 0
        or target == 0
        or count < 0
        or predicate_depth <= 0
        or projection_depth < 0
        or predicate_keys_address == 0
        or projection_keys_address == 0
        or literal == 0
        or (operation != 2 and operation != 3)
        or dict_type == 0
        or none_object == 0
        or external_call["PyList_Size", Int](source) != count
        or external_call["PyList_Size", Int](target) < count
    ):
        return -1
    var predicate_keys = KeyPtr(unsafe_from_address=predicate_keys_address)
    var projection_keys = KeyPtr(unsafe_from_address=projection_keys_address)
    var written = 0
    for i in range(count):
        var element = external_call["PyList_GetItem", Int](source, i)
        var candidate = _lookup(
            element, predicate_keys, predicate_depth, dict_type
        )
        var matched = operation == 3 and candidate == 0
        if candidate != 0:
            var compared = external_call["PyObject_RichCompareBool", Int32](
                candidate, literal, operation
            )
            if compared < 0:
                return -2
            matched = compared == 1
        if not matched:
            continue
        var projected = element
        if projection_depth > 0:
            projected = _lookup(
                element, projection_keys, projection_depth, dict_type
            )
        if projected != 0 and projected != none_object:
            if _append_borrowed(target, written, projected) != 0:
                return -2
            written += 1
    return written
