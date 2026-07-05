READ_ONLY_UI_ALLOWED_SURFACES = (
    "dashboard",
    "artifact_viewer",
    "report_viewer",
    "backtest_result_viewer",
    "paper_trading_result_viewer",
    "risk_evaluation_summary_viewer",
    "local_file_viewer",
)

READ_ONLY_UI_FORBIDDEN_ACTIONS = (
    "run_scan",
    "run_daily_report",
    "run_single_stock_analysis",
    "update_stock_list",
    "clear_cache",
    "run_doctor_live",
    "check_price_data_source",
    "check_stock_list_source",
    "broker_connection",
    "shioaji",
    "live_trading",
    "order_placement",
    "semi_auto_order_confirmation",
    "buy_sell_hold_recommendation",
)

LEGACY_GUI_BOUNDARY_NOTE = (
    "tw_stock_tool.gui is a legacy/local research control panel. "
    "Phase 37 read-only UI work must start from tw_stock_tool.ui."
)

def is_read_only_surface(name: str) -> bool:
    return name in READ_ONLY_UI_ALLOWED_SURFACES
