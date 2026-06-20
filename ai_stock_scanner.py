"""Batch AI baseline scanner for multiple Taiwan stocks.

This scanner reuses ai_prediction_report.run_ai_prediction_report for each
stock and combines the Summary row into a ranking table. It does not implement
or train any additional model.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable

import pandas as pd

from ai_prediction_report import run_ai_prediction_report
from config import DEFAULT_PERIOD, OUTPUT_DIR
from scanner import load_stock_ids_from_file, normalize_stock_ids

AI_STOCK_RANKING_COLUMNS = [
    "Rank",
    "Stock",
    "Period",
    "Horizon",
    "Windows",
    "Avg Accuracy",
    "Avg Precision",
    "Avg Recall",
    "Avg F1",
    "Avg Test Positive Rate %",
    "Avg Predicted Positive Rate %",
    "Error Windows",
    "Status",
    "Error",
]


def collect_stock_ids(stocks: Iterable[str] | None = None, file_path: str | Path | None = None) -> list[str]:
    """Collect stocks from direct values and/or a text file."""
    values: list[str] = []
    if file_path:
        values.extend(load_stock_ids_from_file(file_path))
    if stocks:
        values.extend(stocks)
    collected = normalize_stock_ids(values)
    if not collected:
        raise ValueError("No stocks provided. Use --stocks or --file.")
    return collected


def _summary_to_row(stock_id: str, summary: pd.DataFrame) -> dict[str, object]:
    row = summary.iloc[0].to_dict()
    return {
        "Rank": None,
        "Stock": stock_id,
        "Period": row.get("Period", ""),
        "Horizon": row.get("Horizon", None),
        "Windows": row.get("Windows", None),
        "Avg Accuracy": row.get("Avg Accuracy", None),
        "Avg Precision": row.get("Avg Precision", None),
        "Avg Recall": row.get("Avg Recall", None),
        "Avg F1": row.get("Avg F1", None),
        "Avg Test Positive Rate %": row.get("Avg Test Positive Rate %", None),
        "Avg Predicted Positive Rate %": row.get("Avg Predicted Positive Rate %", None),
        "Error Windows": row.get("Error Windows", None),
        "Status": "OK",
        "Error": "",
    }


def scan_one_stock(
    stock_id: str,
    period: str = DEFAULT_PERIOD,
    horizon: int = 5,
    train_size: int = 252,
    test_size: int = 63,
    step_size: int | None = None,
    force_refresh: bool = False,
    dropna: bool = True,
    n_estimators: int = 100,
    random_state: int = 42,
) -> dict[str, object]:
    """Run one stock through the baseline AI prediction report."""
    try:
        frames = run_ai_prediction_report(
            stock_id=stock_id,
            period=period,
            horizon=horizon,
            train_size=train_size,
            test_size=test_size,
            step_size=step_size,
            force_refresh=force_refresh,
            dropna=dropna,
            n_estimators=n_estimators,
            random_state=random_state,
        )
        summary = frames["Summary"]
        if summary.empty:
            raise ValueError("summary is empty")
        return _summary_to_row(stock_id, summary)
    except Exception as exc:
        return {
            "Rank": None,
            "Stock": stock_id,
            "Period": period,
            "Horizon": horizon,
            "Windows": None,
            "Avg Accuracy": None,
            "Avg Precision": None,
            "Avg Recall": None,
            "Avg F1": None,
            "Avg Test Positive Rate %": None,
            "Avg Predicted Positive Rate %": None,
            "Error Windows": None,
            "Status": "ERROR",
            "Error": str(exc),
        }


def rank_ai_stock_results(rows: list[dict[str, object]]) -> pd.DataFrame:
    """Sort OK rows by model metrics, then append error rows."""
    result = pd.DataFrame(rows, columns=AI_STOCK_RANKING_COLUMNS)
    if result.empty:
        return result

    ok = result[result["Status"] == "OK"].copy()
    errors = result[result["Status"] != "OK"].copy()
    for column in ["Avg F1", "Avg Accuracy", "Error Windows"]:
        ok[column] = pd.to_numeric(ok[column], errors="coerce")
    ok = ok.sort_values(
        by=["Avg F1", "Avg Accuracy", "Error Windows", "Stock"],
        ascending=[False, False, True, True],
        kind="mergesort",
    )
    ok = ok.reset_index(drop=True)
    if not ok.empty:
        ok["Rank"] = range(1, len(ok) + 1)
    errors = errors.sort_values(by="Stock", kind="mergesort")
    return pd.concat([ok, errors], ignore_index=True)[AI_STOCK_RANKING_COLUMNS]


def scan_ai_stocks(
    stock_ids: Iterable[str],
    period: str = DEFAULT_PERIOD,
    horizon: int = 5,
    train_size: int = 252,
    test_size: int = 63,
    step_size: int | None = None,
    force_refresh: bool = False,
    dropna: bool = True,
    n_estimators: int = 100,
    random_state: int = 42,
    workers: int = 1,
) -> pd.DataFrame:
    """Run baseline AI validation for many stocks and return a ranking."""
    stocks = normalize_stock_ids(stock_ids)
    if not stocks:
        raise ValueError("No stocks provided.")
    max_workers = max(1, min(workers, len(stocks)))
    rows: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(
                scan_one_stock,
                stock_id,
                period,
                horizon,
                train_size,
                test_size,
                step_size,
                force_refresh,
                dropna,
                n_estimators,
                random_state,
            ): stock_id
            for stock_id in stocks
        }
        for future in as_completed(future_map):
            rows.append(future.result())
    return rank_ai_stock_results(rows)


def export_ai_stock_ranking(df: pd.DataFrame, output: str | None) -> Path | None:
    """Export AI stock ranking to Excel when requested."""
    if output is None:
        return None
    output_path = OUTPUT_DIR / "ai_stock_ranking.xlsx" if output == "" else Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            df.reindex(columns=AI_STOCK_RANKING_COLUMNS).to_excel(
                writer,
                index=False,
                sheet_name="Ranking",
            )
    except PermissionError as exc:
        raise ValueError(
            f"Failed to write Excel file: {output_path}. Please close the file if it is open."
        ) from exc
    except Exception as exc:
        raise ValueError(f"Failed to write Excel file: {output_path}. {exc}") from exc
    return output_path


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch AI baseline stock scanner")
    parser.add_argument("--stocks", nargs="*", help="Stock ids, for example --stocks 2330 2317 2454")
    parser.add_argument("--file", help="Text file containing one stock id per line")
    parser.add_argument("--period", default=DEFAULT_PERIOD)
    parser.add_argument("--horizon", type=int, default=5)
    parser.add_argument("--train-size", type=int, default=252)
    parser.add_argument("--test-size", type=int, default=63)
    parser.add_argument("--step-size", type=int)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument(
        "--dropna",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Drop rows with missing values when building the ML dataset",
    )
    parser.add_argument("--n-estimators", type=int, default=100)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--output", nargs="?", const="", help="Export Excel; omit path for default output")
    return parser.parse_args(argv)


def main() -> None:
    try:
        args = _parse_args()
        stock_ids = collect_stock_ids(args.stocks, args.file)
        ranking = scan_ai_stocks(
            stock_ids,
            period=args.period,
            horizon=args.horizon,
            train_size=args.train_size,
            test_size=args.test_size,
            step_size=args.step_size,
            force_refresh=args.force_refresh,
            dropna=args.dropna,
            n_estimators=args.n_estimators,
            random_state=args.random_state,
            workers=args.workers,
        )
        print(ranking.to_string(index=False))
        output_path = export_ai_stock_ranking(ranking, args.output)
        if output_path:
            print(f"\nAI stock ranking exported: {output_path}")
        print("\nAI stock scanner is for research only and is not investment advice.")
    except Exception as exc:
        print(f"Error: {exc}")


if __name__ == "__main__":
    main()
