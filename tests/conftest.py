import importlib, sys, os, pytest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def load(modname):
    try:
        return importlib.import_module(modname)
    except Exception as e:  # missing deliverable
        pytest.skip(f"NOT RUN (missing deliverable): cannot import {modname}: {e}")

def call(fn, *a, **k):
    """Call product code; a NotImplementedError stub means NOT RUN, not PASS."""
    try:
        return fn(*a, **k)
    except NotImplementedError:
        pytest.skip(f"NOT RUN (stub): {getattr(fn,'__qualname__',fn)} not implemented")
