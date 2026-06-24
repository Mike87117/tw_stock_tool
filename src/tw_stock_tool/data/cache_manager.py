import argparse

from tw_stock_tool.data.cache_utils import cache_summary, clear_cache, list_cache_files


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="cache 管理工具")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="列出 cache 檔案")
    group.add_argument("--clear", action="store_true", help="清除 cache 檔案")
    group.add_argument("--summary", action="store_true", help="顯示 cache 摘要")
    return parser.parse_args()


def main() -> None:
    try:
        args = _parse_args()
        if args.list:
            files = list_cache_files()
            if not files:
                print("目前沒有 cache 檔案。")
                return
            for path in files:
                print(path)
        elif args.clear:
            count = clear_cache()
            print(f"已清除 {count} 個 cache 檔案。")
        elif args.summary:
            summary = cache_summary()
            if summary.empty:
                print("目前沒有 cache 檔案。")
            else:
                print(summary.to_string(index=False))
    except Exception as exc:
        print(f"錯誤：{exc}")


if __name__ == "__main__":
    main()
