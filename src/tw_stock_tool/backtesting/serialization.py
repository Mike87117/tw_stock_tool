import json
import math
import datetime
from typing import Any
import pandas as pd

from tw_stock_tool.backtesting.results import BacktestResult

class BacktestResultSerializationError(Exception):
    """Raised when an error occurs during backtest result serialization or deserialization."""
    pass


def _is_finite_number(val: Any) -> bool:
    if isinstance(val, bool):
        return False
    if not isinstance(val, (int, float)):
        return False
    return math.isfinite(val)


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
        "initial_capital": result.initial_capital,
        "final_capital": result.final_capital,
        "total_return_pct": result.total_return_pct,
        "buy_hold_return_pct": result.buy_hold_return_pct,
        "cagr_pct": result.cagr_pct,
        "exposure_pct": result.exposure_pct,
        "trade_count": result.trade_count,
        "win_rate_pct": result.win_rate_pct,
        "max_drawdown_pct": result.max_drawdown_pct,
        "profit_factor": result.profit_factor,
        "best_trade_pct": result.best_trade_pct,
        "worst_trade_pct": result.worst_trade_pct,
        "avg_hold_days": result.avg_hold_days,
        "sharpe_ratio": result.sharpe_ratio,
        "sortino_ratio": result.sortino_ratio,
        "avg_profit": result.avg_profit,
        "avg_loss": result.avg_loss,
        "stock": result.stock,
        "strategy": result.strategy,
        "parameters": parameters,
        "start_date": _format_datetime(result.start_date),
        "end_date": _format_datetime(result.end_date),
    }

    # Validate numeric values
    for key, val in summary.items():
        if key in ["stock", "strategy", "parameters", "start_date", "end_date", "trade_count"]:
            continue
        if not _is_finite_number(val):
            raise BacktestResultSerializationError(f"Numeric value for {key} must be finite, got: {val}")

    if not isinstance(summary["trade_count"], int) or isinstance(summary["trade_count"], bool):
        raise BacktestResultSerializationError("trade_count must be an integer.")

    trades_list = []
    if result.trades is not None and not result.trades.empty:
        for idx, row in result.trades.iterrows():
            record = {}
            for col, val in row.items():
                if pd.isna(val):
                    record[str(col)] = None
                elif _is_finite_number(val):
                    record[str(col)] = float(val) if isinstance(val, float) else int(val)
                elif hasattr(val, "isoformat"):
                    record[str(col)] = val.isoformat()
                else:
                    record[str(col)] = str(val)
            trades_list.append(record)

    equity_list = []
    if result.equity_curve is not None and not result.equity_curve.empty:
        for date, equity in result.equity_curve.items():
            if not _is_finite_number(equity):
                raise BacktestResultSerializationError(f"Equity value must be finite, got: {equity}")
            equity_list.append({
                "date": _format_datetime(date),
                "equity": float(equity),
            })

    return {
        "schema_version": 1,
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

    if data["schema_version"] != 1:
        raise BacktestResultSerializationError(f"Unsupported schema_version: {data['schema_version']}")

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

    # Validate numeric summary fields
    for key in expected_summary_keys:
        if key in ["stock", "strategy", "parameters", "start_date", "end_date", "trade_count"]:
            continue
        val = summary[key]
        if not _is_finite_number(val):
            raise BacktestResultSerializationError(f"Numeric value for {key} must be finite, got: {val}")

    if not isinstance(summary["trade_count"], int) or isinstance(summary["trade_count"], bool):
        raise BacktestResultSerializationError("trade_count must be an integer.")

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
        eq = item["equity"]
        if not _is_finite_number(eq):
            raise BacktestResultSerializationError(f"Equity value must be finite, got: {eq}")
        equity_index.append(item["date"])
        equity_values.append(eq)

    equity_curve = pd.Series(equity_values, index=equity_index, name="Equity", dtype=float)

    return BacktestResult(
        initial_capital=float(summary["initial_capital"]),
        final_capital=float(summary["final_capital"]),
        total_return_pct=float(summary["total_return_pct"]),
        buy_hold_return_pct=float(summary["buy_hold_return_pct"]),
        cagr_pct=float(summary["cagr_pct"]),
        exposure_pct=float(summary["exposure_pct"]),
        trade_count=int(summary["trade_count"]),
        win_rate_pct=float(summary["win_rate_pct"]),
        max_drawdown_pct=float(summary["max_drawdown_pct"]),
        profit_factor=float(summary["profit_factor"]),
        best_trade_pct=float(summary["best_trade_pct"]),
        worst_trade_pct=float(summary["worst_trade_pct"]),
        avg_hold_days=float(summary["avg_hold_days"]),
        sharpe_ratio=float(summary["sharpe_ratio"]),
        sortino_ratio=float(summary["sortino_ratio"]),
        avg_profit=float(summary["avg_profit"]),
        avg_loss=float(summary["avg_loss"]),
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
