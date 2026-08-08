"""BacktestResult JSON artifact schema.

Schema history
--------------
1. Every numeric summary field is a finite JSON number.
2. ``summary.profit_factor`` becomes ``number | null``. ``null`` means the
   profit factor is *mathematically unbounded*: gross profit is positive and
   gross loss is exactly zero, so the ratio has no finite value. This is the
   only case that produces ``null``; ``0.0`` continues to mean "no trades, or
   no gross profit" and the two stay distinguishable.

Version 1 artifacts remain readable and their meaning is unchanged - an
all-winning backtest simply could not be serialized as version 1 at all,
because ``math.inf`` is not a finite number and JSON has no infinity literal.
Version 1 therefore still requires a finite number for ``profit_factor``.
"""

import json
import math
from typing import Any
import pandas as pd
import numpy as np

from tw_stock_tool.backtesting.results import BacktestResult

BACKTEST_RESULT_SCHEMA_VERSION = 2
SUPPORTED_BACKTEST_RESULT_SCHEMA_VERSIONS = (1, 2)

# The JSON value carrying "unbounded profit factor". Keeping this named makes
# the two distinct zero-ish states impossible to confuse at call sites.
UNBOUNDED_PROFIT_FACTOR_JSON: None = None


class BacktestResultSerializationError(Exception):
    """Raised when an error occurs during backtest result serialization or deserialization."""
    pass


def _normalize_float(val: Any, name: str) -> float:
    if isinstance(val, bool) or isinstance(val, np.bool_):
        raise BacktestResultSerializationError(f"{name} must be numeric, got bool.")
    if not isinstance(val, (int, float, np.integer, np.floating)):
        raise BacktestResultSerializationError(f"{name} must be numeric.")
    val_float = float(val)
    if not math.isfinite(val_float):
        raise BacktestResultSerializationError(f"Numeric value for {name} must be finite, got: {val}")
    return val_float

def _normalize_int(val: Any, name: str) -> int:
    if isinstance(val, bool) or isinstance(val, np.bool_):
        raise BacktestResultSerializationError(f"{name} must be an integer, got bool.")
    if not isinstance(val, (int, np.integer)):
        raise BacktestResultSerializationError(f"{name} must be an integer.")
    return int(val)

def _normalize_numeric(val: Any, name: str) -> int | float:
    if isinstance(val, bool) or isinstance(val, np.bool_):
        raise BacktestResultSerializationError(f"{name} must be numeric, got bool.")
    if isinstance(val, (int, np.integer)):
        return int(val)
    if isinstance(val, (float, np.floating)):
        val_float = float(val)
        if not math.isfinite(val_float):
            raise BacktestResultSerializationError(f"Numeric value for {name} must be finite, got: {val}")
        return val_float
    raise BacktestResultSerializationError(f"{name} must be numeric.")

def _profit_factor_to_json(val: Any) -> float | None:
    """Encode BacktestResult.profit_factor for the artifact.

    ``+inf`` is the value calculate_profit_factor() produces when gross loss is
    zero and gross profit is positive, so it is a legitimate derived state and
    is encoded as ``null``. ``NaN`` and ``-inf`` are not reachable from that
    calculation, so they are treated as malformed and rejected - this helper
    deliberately does not widen the general finite-number rule.
    """
    if isinstance(val, bool) or isinstance(val, np.bool_):
        raise BacktestResultSerializationError("profit_factor must be numeric, got bool.")
    if not isinstance(val, (int, float, np.integer, np.floating)):
        raise BacktestResultSerializationError("profit_factor must be numeric.")
    val_float = float(val)
    if math.isinf(val_float) and val_float > 0:
        return UNBOUNDED_PROFIT_FACTOR_JSON
    if not math.isfinite(val_float):
        raise BacktestResultSerializationError(
            f"Numeric value for profit_factor must be finite or positive infinity, got: {val}"
        )
    return val_float


def _profit_factor_from_json(val: Any, schema_version: int) -> float:
    """Decode summary.profit_factor back to its internal mathematical meaning."""
    if val is UNBOUNDED_PROFIT_FACTOR_JSON:
        if schema_version < 2:
            raise BacktestResultSerializationError(
                f"profit_factor must be numeric in schema_version {schema_version}."
            )
        return math.inf
    return _normalize_float(val, "profit_factor")


def _is_finite_number(val: Any) -> bool:
    if isinstance(val, bool) or isinstance(val, np.bool_):
        return False
    if not isinstance(val, (int, float, np.integer, np.floating)):
        return False
    return math.isfinite(float(val))

def _is_json_serializable(data: dict) -> bool:
    try:
        json.dumps(data)
        return True
    except (TypeError, ValueError):
        return False


def _format_datetime(dt: Any) -> str | None:
    if dt is None:
        return None
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt)


def serialize_backtest_result(result: BacktestResult) -> dict[str, Any]:
    if not isinstance(result, BacktestResult):
        raise BacktestResultSerializationError("Input must be a BacktestResult.")

    parameters = result.parameters
    if parameters is None:
        parameters = {}
    if not isinstance(parameters, dict):
        raise BacktestResultSerializationError("parameters must be a dict.")
    if not _is_json_serializable(parameters):
        raise BacktestResultSerializationError("parameters must be JSON serializable.")

    summary = {
        "initial_capital": _normalize_float(result.initial_capital, "initial_capital"),
        "final_capital": _normalize_float(result.final_capital, "final_capital"),
        "total_return_pct": _normalize_float(result.total_return_pct, "total_return_pct"),
        "buy_hold_return_pct": _normalize_float(result.buy_hold_return_pct, "buy_hold_return_pct"),
        "cagr_pct": _normalize_float(result.cagr_pct, "cagr_pct"),
        "exposure_pct": _normalize_float(result.exposure_pct, "exposure_pct"),
        "trade_count": _normalize_int(result.trade_count, "trade_count"),
        "win_rate_pct": _normalize_float(result.win_rate_pct, "win_rate_pct"),
        "max_drawdown_pct": _normalize_float(result.max_drawdown_pct, "max_drawdown_pct"),
        "profit_factor": _profit_factor_to_json(result.profit_factor),
        "best_trade_pct": _normalize_float(result.best_trade_pct, "best_trade_pct"),
        "worst_trade_pct": _normalize_float(result.worst_trade_pct, "worst_trade_pct"),
        "avg_hold_days": _normalize_float(result.avg_hold_days, "avg_hold_days"),
        "sharpe_ratio": _normalize_float(result.sharpe_ratio, "sharpe_ratio"),
        "sortino_ratio": _normalize_float(result.sortino_ratio, "sortino_ratio"),
        "avg_profit": _normalize_float(result.avg_profit, "avg_profit"),
        "avg_loss": _normalize_float(result.avg_loss, "avg_loss"),
        "stock": result.stock,
        "strategy": result.strategy,
        "parameters": parameters,
        "start_date": _format_datetime(result.start_date),
        "end_date": _format_datetime(result.end_date),
    }

    trades_list = []
    if result.trades is not None and not result.trades.empty:
        for idx, row in result.trades.iterrows():
            record = {}
            for col, val in row.items():
                if pd.isna(val):
                    record[str(col)] = None
                elif _is_finite_number(val):
                    record[str(col)] = _normalize_numeric(val, str(col))
                elif hasattr(val, "isoformat"):
                    record[str(col)] = val.isoformat()
                else:
                    record[str(col)] = str(val)
            trades_list.append(record)

    equity_list = []
    if result.equity_curve is not None and not result.equity_curve.empty:
        for date, equity in result.equity_curve.items():
            equity_list.append({
                "date": _format_datetime(date),
                "equity": _normalize_float(equity, "equity"),
            })

    return {
        "schema_version": BACKTEST_RESULT_SCHEMA_VERSION,
        "result_type": "backtest_result",
        "summary": summary,
        "trades": trades_list,
        "equity_curve": equity_list,
        "metadata": {
            "source": "backtest_result",
            "semantics": "offline_research_artifact"
        }
    }


def deserialize_backtest_result(data: dict[str, Any]) -> BacktestResult:
    if not isinstance(data, dict):
        raise BacktestResultSerializationError("Data must be a dictionary.")

    required_keys = {"schema_version", "result_type", "summary", "trades", "equity_curve", "metadata"}
    missing = required_keys - set(data.keys())
    if missing:
        raise BacktestResultSerializationError(f"Missing top-level fields: {missing}")

    unknown = set(data.keys()) - required_keys
    if unknown:
        raise BacktestResultSerializationError(f"Unknown top-level fields: {unknown}")

    schema_version = data["schema_version"]
    if isinstance(schema_version, bool) or schema_version not in SUPPORTED_BACKTEST_RESULT_SCHEMA_VERSIONS:
        raise BacktestResultSerializationError(f"Unsupported schema_version: {schema_version}")

    if data["result_type"] != "backtest_result":
        raise BacktestResultSerializationError(f"Unsupported result_type: {data['result_type']}")

    summary = data["summary"]
    if not isinstance(summary, dict):
        raise BacktestResultSerializationError("summary must be a dictionary.")

    expected_summary_keys = {
        "initial_capital", "final_capital", "total_return_pct", "buy_hold_return_pct",
        "cagr_pct", "exposure_pct", "trade_count", "win_rate_pct", "max_drawdown_pct",
        "profit_factor", "best_trade_pct", "worst_trade_pct", "avg_hold_days",
        "sharpe_ratio", "sortino_ratio", "avg_profit", "avg_loss",
        "stock", "strategy", "parameters", "start_date", "end_date"
    }
    missing_summary = expected_summary_keys - set(summary.keys())
    if missing_summary:
        raise BacktestResultSerializationError(f"Missing summary fields: {missing_summary}")
    
    unknown_summary = set(summary.keys()) - expected_summary_keys
    if unknown_summary:
        raise BacktestResultSerializationError(f"Unknown summary fields: {unknown_summary}")

    parameters = summary["parameters"]
    if not isinstance(parameters, dict):
        raise BacktestResultSerializationError("parameters must be a dict.")
    if not _is_json_serializable(parameters):
        raise BacktestResultSerializationError("parameters must be JSON serializable.")

    trades = data["trades"]
    if not isinstance(trades, list):
        raise BacktestResultSerializationError("trades must be a list.")

    equity_curve_data = data["equity_curve"]
    if not isinstance(equity_curve_data, list):
        raise BacktestResultSerializationError("equity_curve must be a list.")

    trades_df = pd.DataFrame(trades)
    
    equity_index = []
    equity_values = []
    for item in equity_curve_data:
        if not isinstance(item, dict) or "date" not in item or "equity" not in item:
            raise BacktestResultSerializationError("Invalid equity_curve record format.")
        eq = _normalize_float(item["equity"], "equity")
        equity_index.append(item["date"])
        equity_values.append(eq)

    equity_curve = pd.Series(equity_values, index=equity_index, name="Equity", dtype=float)

    return BacktestResult(
        initial_capital=_normalize_float(summary["initial_capital"], "initial_capital"),
        final_capital=_normalize_float(summary["final_capital"], "final_capital"),
        total_return_pct=_normalize_float(summary["total_return_pct"], "total_return_pct"),
        buy_hold_return_pct=_normalize_float(summary["buy_hold_return_pct"], "buy_hold_return_pct"),
        cagr_pct=_normalize_float(summary["cagr_pct"], "cagr_pct"),
        exposure_pct=_normalize_float(summary["exposure_pct"], "exposure_pct"),
        trade_count=_normalize_int(summary["trade_count"], "trade_count"),
        win_rate_pct=_normalize_float(summary["win_rate_pct"], "win_rate_pct"),
        max_drawdown_pct=_normalize_float(summary["max_drawdown_pct"], "max_drawdown_pct"),
        profit_factor=_profit_factor_from_json(summary["profit_factor"], schema_version),
        best_trade_pct=_normalize_float(summary["best_trade_pct"], "best_trade_pct"),
        worst_trade_pct=_normalize_float(summary["worst_trade_pct"], "worst_trade_pct"),
        avg_hold_days=_normalize_float(summary["avg_hold_days"], "avg_hold_days"),
        sharpe_ratio=_normalize_float(summary["sharpe_ratio"], "sharpe_ratio"),
        sortino_ratio=_normalize_float(summary["sortino_ratio"], "sortino_ratio"),
        avg_profit=_normalize_float(summary["avg_profit"], "avg_profit"),
        avg_loss=_normalize_float(summary["avg_loss"], "avg_loss"),
        trades=trades_df,
        equity_curve=equity_curve,
        stock=summary["stock"],
        strategy=summary["strategy"],
        parameters=summary["parameters"],
        start_date=summary["start_date"],
        end_date=summary["end_date"]
    )


def export_backtest_result_json(result: BacktestResult) -> str:
    data = serialize_backtest_result(result)
    return json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)


def load_backtest_result_json(content: str) -> BacktestResult:
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise BacktestResultSerializationError(f"Invalid JSON content: {e}")
    return deserialize_backtest_result(data)
