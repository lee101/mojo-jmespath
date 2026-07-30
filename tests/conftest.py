import importlib
import os
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_PYTHON = os.path.join(ROOT, "python")


def _without_local_path():
    return [
        entry
        for entry in sys.path
        if os.path.abspath(entry or os.curdir) != os.path.abspath(LOCAL_PYTHON)
    ]


original_path = sys.path[:]
sys.path[:] = _without_local_path()
UPSTREAM = importlib.import_module("jmespath")
UPSTREAM_MODULES = {
    name: module
    for name, module in sys.modules.items()
    if name == "jmespath" or name.startswith("jmespath.")
}
for name in UPSTREAM_MODULES:
    sys.modules.pop(name, None)
sys.path[:] = original_path
if LOCAL_PYTHON not in sys.path:
    sys.path.insert(0, LOCAL_PYTHON)
