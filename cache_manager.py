"""Compatibility wrapper for package module."""

from importlib import import_module as _import_module
import sys as _sys

_impl = _import_module("tw_stock_tool.data.cache_manager")
if __name__ == "__main__":
    raise SystemExit(_impl.main())
else:
    _sys.modules[__name__] = _impl
