"""Compatibility wrapper for package module."""

from importlib import import_module as _import_module
import sys as _sys

_impl = _import_module("tw_stock_tool.reports.report")
_sys.modules[__name__] = _impl
