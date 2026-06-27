import argparse
from pathlib import Path

from tw_stock_tool.analysis.scanner import load_stock_ids_from_file, normalize_stock_ids
from tw_stock_tool.analysis.stock_selection import apply_stock_selection
from tw_stock_tool.data import stock_list_updater as stock_list_updater_module
from tw_stock_tool.scanners.daily_watchlist import (
    build_daily_watchlist,
    export_daily_watchlist_excel,
    export_daily_watchlist_markdown,
)
from tw_stock_tool.utils.config import DEFAULT_PERIOD


def _split_cli_stock_values(values: list[str] | None) -> list[str]:
    if not values:
        return []
    stocks: list[str] = []
    for value in values:
        stocks.extend(str(value).replace(",", " ").split())
    return stocks


def _ask_stock_ids() -> list[str]:
    print("Enter stock IDs, one per line. Submit an empty line to finish:")
    values = []
    while True:
        try:
            value = input().strip()
            if not value:
                break
            values.append(value)
        except EOFError:
            break
    return normalize_stock_ids(values)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Daily watchlist scanner")
    parser.add_argument("--stock", action="append", dest="stocks", help="Single stock ID. Repeat this option to add more.")
    parser.add_argument("--stocks", nargs="*", help="Stock IDs such as --stocks 2330 2317 2454 or --stocks 2330,2317")
    parser.add_argument("--file", help="Load stock IDs from a txt file")
    parser.add_argument("--auto-stock-list", action="store_true", help="Update the official stock list before scanning")
    parser.add_argument("--auto-stock-list-output", default="output/auto_stock_list.txt", help="Path to save the auto-downloaded stock list")
    parser.add_argument("--stock-market", choices=("all", "twse", "tpex"), default="all")
    parser.add_argument("--stock-limit", type=int, help="Limit how many stocks are scanned")
    parser.add_argument("--period", default=DEFAULT_PERIOD, help="Analysis period")
    parser.add_argument("--force-refresh", action="store_true", help="Ignore cache and redownload data")
    parser.add_argument("--breakout-min-score", type=float, default=3.0, help="Minimum score for technical breakout candidates")
    parser.add_argument("--risk-min-score", type=float, default=2.0, help="Minimum score for risk warning candidates")
    parser.add_argument("--output-excel", nargs="?", const="", default=None, help="Export Excel report, optionally with a custom output path")
    parser.add_argument("--output-md", nargs="?", const="", default=None, help="Export Markdown report, optionally with a custom output path")
    parser.add_argument("--output-dir", default="output", help="Default output directory")
    return parser.parse_args(argv)


def _collect_stock_ids(args: argparse.Namespace) -> list[str]:
    if args.auto_stock_list:
        stocks_df, _ = stock_list_updater_module.update_stock_list(
            market=args.stock_market,
            output=args.auto_stock_list_output,
            allow_partial=False,
        )
        stocks = normalize_stock_ids(stocks_df["Stock"].astype(str).tolist())
    else:
        stocks: list[str] = []
        if args.file:
            stocks.extend(load_stock_ids_from_file(args.file))
        if args.stocks:
            stocks.extend(_split_cli_stock_values(args.stocks))
        if not stocks:
            stocks = _ask_stock_ids()
        stocks = normalize_stock_ids(stocks)
    return apply_stock_selection(stocks, stock_limit=getattr(args, "stock_limit", None))


def main() -> None:
    try:
        args = _parse_args()
        stock_ids = _collect_stock_ids(args)

        print(f"Scanning {len(stock_ids)} stock(s)...")

        df = build_daily_watchlist(
            stock_ids=stock_ids,
            period=args.period,
            stock_limit=args.stock_limit,
            force_refresh=args.force_refresh,
            breakout_min_score=args.breakout_min_score,
            risk_min_score=args.risk_min_score,
        )

        print("\nScan complete.")

        if df.empty:
            print("No watchlist candidates.")
            candidate_count = 0
            error_count = 0
        else:
            candidate_count = int((df["Status"] == "ok").sum())
            error_count = int((df["Status"] != "ok").sum())
            
        print(f"Candidate rows: {candidate_count}, Error rows: {error_count}")

        out_dir = Path(args.output_dir)

        if args.output_excel is not None:
            excel_output = args.output_excel or str(out_dir / "daily_watchlist.xlsx")
            excel_path = export_daily_watchlist_excel(df, excel_output)
            print(f"Excel: {excel_path}")

        if args.output_md is not None:
            md_output = args.output_md or str(out_dir / "daily_watchlist.md")
            md_path = export_daily_watchlist_markdown(df, md_output)
            print(f"Markdown: {md_path}")

        if args.output_excel is None and args.output_md is None and not df.empty:
            print(df[["Stock", "Name", "Category", "Score", "Close", "Status"]].to_string())

    except Exception as exc:
        print(f"Unexpected error: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
