"""Minimal Tkinter GUI prototype for tw_stock_tool.

This is intentionally small: it proves that a local GUI can submit app_services
calls through gui_tasks.TaskRunner without blocking the Tk main thread.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

import app_services
from gui_tasks import FAILED, SUCCESS, TaskRunner, TaskState

REFRESH_MS = 500


class TwStockToolGUI:
    """Minimal GUI shell backed by TaskRunner."""

    def __init__(
        self,
        root: tk.Tk | None = None,
        runner: TaskRunner | None = None,
        build_ui: bool = True,
    ) -> None:
        self.root = root or tk.Tk()
        self.runner = runner or TaskRunner(max_workers=2)
        self._closed = False
        self._reported_finished: set[str] = set()
        self.market_var: tk.StringVar | None = None
        self.output_var: tk.StringVar | None = None
        self.allow_partial_var: tk.BooleanVar | None = None
        self.scan_stock_ids_var: tk.StringVar | None = None
        self.scan_period_var: tk.StringVar | None = None
        self.scan_interval_var: tk.StringVar | None = None
        self.scan_max_workers_var: tk.StringVar | None = None
        self.scan_min_score_var: tk.StringVar | None = None
        self.scan_top_var: tk.StringVar | None = None
        self.scan_errors_only_var: tk.BooleanVar | None = None
        self.daily_stock_ids_var: tk.StringVar | None = None
        self.daily_period_var: tk.StringVar | None = None
        self.daily_interval_var: tk.StringVar | None = None
        self.daily_min_score_var: tk.StringVar | None = None
        self.daily_top_var: tk.StringVar | None = None
        self.daily_output_var: tk.StringVar | None = None
        self.daily_progress_var: tk.BooleanVar | None = None
        self.single_stock_id_var: tk.StringVar | None = None
        self.single_period_var: tk.StringVar | None = None
        self.single_interval_var: tk.StringVar | None = None
        self.single_stop_loss_var: tk.StringVar | None = None
        self.single_take_profit_var: tk.StringVar | None = None
        self.single_max_hold_days_var: tk.StringVar | None = None
        self.single_position_size_var: tk.StringVar | None = None
        self.single_export_excel_var: tk.BooleanVar | None = None
        self.single_save_chart_var: tk.BooleanVar | None = None
        self.task_tree: ttk.Treeview | None = None
        self.result_text: tk.Text | None = None
        if build_ui:
            self._build_ui()

    def _build_ui(self) -> None:
        self.root.title("tw_stock_tool GUI")
        self.root.geometry("1000x700")
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        environment_frame = ttk.Frame(notebook)
        data_sources_frame = ttk.Frame(notebook)
        stock_list_frame = ttk.Frame(notebook)
        scan_frame = ttk.Frame(notebook)
        daily_report_frame = ttk.Frame(notebook)
        single_stock_frame = ttk.Frame(notebook)
        cache_frame = ttk.Frame(notebook)
        task_log_frame = ttk.Frame(notebook)
        notebook.add(environment_frame, text="Environment")
        notebook.add(data_sources_frame, text="Data Sources")
        notebook.add(stock_list_frame, text="Stock List")
        notebook.add(scan_frame, text="Scan")
        notebook.add(daily_report_frame, text="Daily Report")
        notebook.add(single_stock_frame, text="Single Stock")
        notebook.add(cache_frame, text="Cache")
        notebook.add(task_log_frame, text="Task Log")

        self._build_environment_tab(environment_frame)
        self._build_data_sources_tab(data_sources_frame)
        self._build_stock_list_tab(stock_list_frame)
        self._build_scan_tab(scan_frame)
        self._build_daily_report_tab(daily_report_frame)
        self._build_single_stock_tab(single_stock_frame)
        self._build_cache_tab(cache_frame)
        self._build_task_log_tab(task_log_frame)
        self.refresh_tasks()

    def _build_environment_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Environment checks", font=("TkDefaultFont", 12, "bold")).pack(
            anchor="w", padx=12, pady=(12, 8)
        )
        ttk.Button(
            parent,
            text="Run Doctor",
            command=lambda: self.submit_task(
                "Run Doctor",
                app_services.doctor_service,
                live=False,
            ),
        ).pack(anchor="w", padx=12, pady=4)
        ttk.Button(
            parent,
            text="Run Doctor --live",
            command=lambda: self.submit_task(
                "Run Doctor --live",
                app_services.doctor_service,
                live=True,
            ),
        ).pack(anchor="w", padx=12, pady=4)

    def _build_data_sources_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Data source checks", font=("TkDefaultFont", 12, "bold")).pack(
            anchor="w", padx=12, pady=(12, 8)
        )
        ttk.Button(
            parent,
            text="Check Stock List Source",
            command=lambda: self.submit_task(
                "Check Stock List Source",
                app_services.stock_list_smoke_check_service,
            ),
        ).pack(anchor="w", padx=12, pady=4)
        ttk.Button(
            parent,
            text="Check Price Data Source",
            command=lambda: self.submit_task(
                "Check Price Data Source",
                app_services.price_data_smoke_check_service,
            ),
        ).pack(anchor="w", padx=12, pady=4)

    def _build_stock_list_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Update official stock list", font=("TkDefaultFont", 12, "bold")).pack(
            anchor="w", padx=12, pady=(12, 8)
        )

        form = ttk.Frame(parent)
        form.pack(anchor="w", fill="x", padx=12, pady=4)

        ttk.Label(form, text="Market").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        self.market_var = tk.StringVar(value="all")
        ttk.Combobox(
            form,
            textvariable=self.market_var,
            values=("all", "twse", "tpex"),
            state="readonly",
            width=12,
        ).grid(row=0, column=1, sticky="w", pady=4)

        ttk.Label(form, text="Output").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        self.output_var = tk.StringVar(value="stocks.txt")
        ttk.Entry(form, textvariable=self.output_var, width=40).grid(row=1, column=1, sticky="w", pady=4)

        self.allow_partial_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            form,
            text="Allow partial",
            variable=self.allow_partial_var,
        ).grid(row=2, column=1, sticky="w", pady=4)

        ttk.Button(
            parent,
            text="Update Stock List",
            command=self.submit_stock_list_update,
        ).pack(anchor="w", padx=12, pady=(8, 4))

    def _build_scan_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Run multi-stock scan", font=("TkDefaultFont", 12, "bold")).pack(
            anchor="w", padx=12, pady=(12, 8)
        )

        form = ttk.Frame(parent)
        form.pack(anchor="w", fill="x", padx=12, pady=4)

        ttk.Label(form, text="Stock IDs").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        self.scan_stock_ids_var = tk.StringVar(value="2330,2317,2454")
        ttk.Entry(form, textvariable=self.scan_stock_ids_var, width=42).grid(row=0, column=1, sticky="w", pady=4)

        ttk.Label(form, text="Period").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        self.scan_period_var = tk.StringVar(value="1y")
        ttk.Combobox(
            form,
            textvariable=self.scan_period_var,
            values=("1y", "2y", "5y"),
            state="readonly",
            width=12,
        ).grid(row=1, column=1, sticky="w", pady=4)

        ttk.Label(form, text="Interval").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        self.scan_interval_var = tk.StringVar(value="1d")
        ttk.Combobox(
            form,
            textvariable=self.scan_interval_var,
            values=("1d", "1wk", "1mo"),
            state="readonly",
            width=12,
        ).grid(row=2, column=1, sticky="w", pady=4)

        ttk.Label(form, text="Max workers").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=4)
        self.scan_max_workers_var = tk.StringVar(value="4")
        ttk.Entry(form, textvariable=self.scan_max_workers_var, width=12).grid(row=3, column=1, sticky="w", pady=4)

        ttk.Label(form, text="Min score").grid(row=4, column=0, sticky="w", padx=(0, 8), pady=4)
        self.scan_min_score_var = tk.StringVar(value="")
        ttk.Entry(form, textvariable=self.scan_min_score_var, width=12).grid(row=4, column=1, sticky="w", pady=4)

        ttk.Label(form, text="Top").grid(row=5, column=0, sticky="w", padx=(0, 8), pady=4)
        self.scan_top_var = tk.StringVar(value="")
        ttk.Entry(form, textvariable=self.scan_top_var, width=12).grid(row=5, column=1, sticky="w", pady=4)

        self.scan_errors_only_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            form,
            text="Errors only",
            variable=self.scan_errors_only_var,
        ).grid(row=6, column=1, sticky="w", pady=4)

        ttk.Button(
            parent,
            text="Run Scan",
            command=self.submit_scan,
        ).pack(anchor="w", padx=12, pady=(8, 4))

    def _build_daily_report_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Run daily candidate report", font=("TkDefaultFont", 12, "bold")).pack(
            anchor="w", padx=12, pady=(12, 8)
        )

        form = ttk.Frame(parent)
        form.pack(anchor="w", fill="x", padx=12, pady=4)

        ttk.Label(form, text="Stock IDs").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        self.daily_stock_ids_var = tk.StringVar(value="2330,2317,2454")
        ttk.Entry(form, textvariable=self.daily_stock_ids_var, width=42).grid(row=0, column=1, sticky="w", pady=4)

        ttk.Label(form, text="Period").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        self.daily_period_var = tk.StringVar(value="1y")
        ttk.Combobox(
            form,
            textvariable=self.daily_period_var,
            values=("1y", "2y", "5y"),
            state="readonly",
            width=12,
        ).grid(row=1, column=1, sticky="w", pady=4)

        ttk.Label(form, text="Interval").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        self.daily_interval_var = tk.StringVar(value="1d")
        ttk.Combobox(
            form,
            textvariable=self.daily_interval_var,
            values=("1d", "1wk", "1mo"),
            state="readonly",
            width=12,
        ).grid(row=2, column=1, sticky="w", pady=4)

        ttk.Label(form, text="Min score").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=4)
        self.daily_min_score_var = tk.StringVar(value="")
        ttk.Entry(form, textvariable=self.daily_min_score_var, width=12).grid(row=3, column=1, sticky="w", pady=4)

        ttk.Label(form, text="Top").grid(row=4, column=0, sticky="w", padx=(0, 8), pady=4)
        self.daily_top_var = tk.StringVar(value="")
        ttk.Entry(form, textvariable=self.daily_top_var, width=12).grid(row=4, column=1, sticky="w", pady=4)

        ttk.Label(form, text="Output").grid(row=5, column=0, sticky="w", padx=(0, 8), pady=4)
        self.daily_output_var = tk.StringVar(value="output/daily_report.xlsx")
        ttk.Entry(form, textvariable=self.daily_output_var, width=42).grid(row=5, column=1, sticky="w", pady=4)

        self.daily_progress_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            form,
            text="Progress",
            variable=self.daily_progress_var,
        ).grid(row=6, column=1, sticky="w", pady=4)

        ttk.Button(
            parent,
            text="Run Daily Report",
            command=self.submit_daily_report,
        ).pack(anchor="w", padx=12, pady=(8, 4))

    def _build_single_stock_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Run single stock analysis", font=("TkDefaultFont", 12, "bold")).pack(
            anchor="w", padx=12, pady=(12, 8)
        )

        form = ttk.Frame(parent)
        form.pack(anchor="w", fill="x", padx=12, pady=4)

        ttk.Label(form, text="Stock ID").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        self.single_stock_id_var = tk.StringVar(value="2330")
        ttk.Entry(form, textvariable=self.single_stock_id_var, width=18).grid(row=0, column=1, sticky="w", pady=4)

        ttk.Label(form, text="Period").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        self.single_period_var = tk.StringVar(value="2y")
        ttk.Combobox(
            form,
            textvariable=self.single_period_var,
            values=("1y", "2y", "5y", "10y"),
            state="readonly",
            width=12,
        ).grid(row=1, column=1, sticky="w", pady=4)

        ttk.Label(form, text="Interval").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        self.single_interval_var = tk.StringVar(value="1d")
        ttk.Combobox(
            form,
            textvariable=self.single_interval_var,
            values=("1d", "1wk", "1mo"),
            state="readonly",
            width=12,
        ).grid(row=2, column=1, sticky="w", pady=4)

        ttk.Label(form, text="Stop loss %").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=4)
        self.single_stop_loss_var = tk.StringVar(value="")
        ttk.Entry(form, textvariable=self.single_stop_loss_var, width=12).grid(row=3, column=1, sticky="w", pady=4)

        ttk.Label(form, text="Take profit %").grid(row=4, column=0, sticky="w", padx=(0, 8), pady=4)
        self.single_take_profit_var = tk.StringVar(value="")
        ttk.Entry(form, textvariable=self.single_take_profit_var, width=12).grid(row=4, column=1, sticky="w", pady=4)

        ttk.Label(form, text="Max hold days").grid(row=5, column=0, sticky="w", padx=(0, 8), pady=4)
        self.single_max_hold_days_var = tk.StringVar(value="")
        ttk.Entry(form, textvariable=self.single_max_hold_days_var, width=12).grid(row=5, column=1, sticky="w", pady=4)

        ttk.Label(form, text="Position size").grid(row=6, column=0, sticky="w", padx=(0, 8), pady=4)
        self.single_position_size_var = tk.StringVar(value="1.0")
        ttk.Entry(form, textvariable=self.single_position_size_var, width=12).grid(row=6, column=1, sticky="w", pady=4)

        self.single_export_excel_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            form,
            text="Export Excel",
            variable=self.single_export_excel_var,
        ).grid(row=7, column=1, sticky="w", pady=4)

        self.single_save_chart_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            form,
            text="Save chart",
            variable=self.single_save_chart_var,
        ).grid(row=8, column=1, sticky="w", pady=4)

        ttk.Button(
            parent,
            text="Run Single Stock Analysis",
            command=self.submit_single_stock_analysis,
        ).pack(anchor="w", padx=12, pady=(8, 4))

    def _build_cache_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Cache management", font=("TkDefaultFont", 12, "bold")).pack(
            anchor="w", padx=12, pady=(12, 8)
        )
        ttk.Button(
            parent,
            text="Cache Summary",
            command=self.submit_cache_summary,
        ).pack(anchor="w", padx=12, pady=4)
        ttk.Button(
            parent,
            text="Clear Cache",
            command=self.submit_cache_clear,
        ).pack(anchor="w", padx=12, pady=4)

    def _build_task_log_tab(self, parent: ttk.Frame) -> None:
        columns = (
            "task_id",
            "name",
            "status",
            "progress",
            "message",
            "error",
            "started_at",
            "finished_at",
        )
        self.task_tree = ttk.Treeview(parent, columns=columns, show="headings", height=12)
        for column in columns:
            self.task_tree.heading(column, text=column)
            self.task_tree.column(column, width=115, stretch=True)
        self.task_tree.pack(fill="both", expand=True, padx=8, pady=8)

        button_frame = ttk.Frame(parent)
        button_frame.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(button_frame, text="Cancel Selected Task", command=self.cancel_selected_task).pack(side="left")
        ttk.Button(button_frame, text="Clear Finished", command=self.clear_finished_tasks).pack(side="left", padx=8)

        self.result_text = tk.Text(parent, height=12, wrap="word")
        self.result_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def parse_stock_ids(self, value: str) -> list[str]:
        """Parse comma/space separated stock ids from GUI input."""
        return [stock_id for stock_id in value.replace(",", " ").split() if stock_id.strip()]

    def _parse_positive_int(self, value: str, error_message: str) -> int:
        try:
            number = int(value.strip())
        except ValueError as exc:
            raise ValueError(error_message) from exc
        if number <= 0:
            raise ValueError(error_message)
        return number

    def _parse_optional_float(self, value: str, error_message: str) -> float | None:
        text = value.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError as exc:
            raise ValueError(error_message) from exc

    def _parse_optional_positive_int(self, value: str, error_message: str) -> int | None:
        text = value.strip()
        if not text:
            return None
        return self._parse_positive_int(text, error_message)

    def _parse_optional_positive_float(self, value: str, error_message: str) -> float | None:
        number = self._parse_optional_float(value, error_message)
        if number is not None and number <= 0:
            raise ValueError(error_message)
        return number

    def _parse_position_size(self, value: str) -> float:
        try:
            number = float(value.strip())
        except ValueError as exc:
            raise ValueError("Position size must be greater than 0 and less than or equal to 1.") from exc
        if not 0 < number <= 1:
            raise ValueError("Position size must be greater than 0 and less than or equal to 1.")
        return number

    def submit_cache_summary(self) -> str:
        """Submit cache summary task."""
        return self.submit_task(
            "Cache Summary",
            app_services.cache_summary_service,
        )

    def submit_cache_clear(self) -> str:
        """Submit cache clear task."""
        return self.submit_task(
            "Clear Cache",
            app_services.cache_clear_service,
        )

    def submit_single_stock_analysis(self) -> str | None:
        """Submit single-stock analysis using current form values."""
        stock_id = self.single_stock_id_var.get().strip() if self.single_stock_id_var is not None else ""
        if not stock_id:
            self._append_result("Stock ID cannot be blank.")
            return None

        try:
            stop_loss_pct = self._parse_optional_positive_float(
                self.single_stop_loss_var.get() if self.single_stop_loss_var is not None else "",
                "Stop loss must be a positive number.",
            )
            take_profit_pct = self._parse_optional_positive_float(
                self.single_take_profit_var.get() if self.single_take_profit_var is not None else "",
                "Take profit must be a positive number.",
            )
            max_hold_days = self._parse_optional_positive_int(
                self.single_max_hold_days_var.get() if self.single_max_hold_days_var is not None else "",
                "Max hold days must be a positive integer.",
            )
            position_size = self._parse_position_size(
                self.single_position_size_var.get() if self.single_position_size_var is not None else "1.0"
            )
        except ValueError as exc:
            self._append_result(str(exc))
            return None

        period = self.single_period_var.get() if self.single_period_var is not None else "2y"
        interval = self.single_interval_var.get() if self.single_interval_var is not None else "1d"
        export_excel = self.single_export_excel_var.get() if self.single_export_excel_var is not None else True
        save_chart = self.single_save_chart_var.get() if self.single_save_chart_var is not None else True
        return self.submit_task(
            "Run Single Stock Analysis",
            app_services.single_stock_analysis_service,
            stock_id=stock_id,
            period=period,
            interval=interval,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            max_hold_days=max_hold_days,
            position_size=position_size,
            export_excel=export_excel,
            save_chart=save_chart,
        )

    def submit_daily_report(self) -> str | None:
        """Submit daily report generation using current form values."""
        raw_stock_ids = self.daily_stock_ids_var.get() if self.daily_stock_ids_var is not None else ""
        stock_ids = self.parse_stock_ids(raw_stock_ids)
        if not stock_ids:
            self._append_result("Stock IDs cannot be blank.")
            return None

        try:
            min_score = self._parse_optional_float(
                self.daily_min_score_var.get() if self.daily_min_score_var is not None else "",
                "Min score must be a number.",
            )
            top = self._parse_optional_positive_int(
                self.daily_top_var.get() if self.daily_top_var is not None else "",
                "Top must be a positive integer.",
            )
        except ValueError as exc:
            self._append_result(str(exc))
            return None

        period = self.daily_period_var.get() if self.daily_period_var is not None else "1y"
        interval = self.daily_interval_var.get() if self.daily_interval_var is not None else "1d"
        output = self.daily_output_var.get().strip() if self.daily_output_var is not None else ""
        progress = self.daily_progress_var.get() if self.daily_progress_var is not None else False
        return self.submit_task(
            "Run Daily Report",
            app_services.daily_report_service,
            stock_ids=stock_ids,
            period=period,
            interval=interval,
            min_score=app_services.DEFAULT_MIN_SCORE if min_score is None else min_score,
            top=top,
            output=output or None,
            progress=progress,
        )

    def submit_scan(self) -> str | None:
        """Submit multi-stock scanner using current form values."""
        raw_stock_ids = self.scan_stock_ids_var.get() if self.scan_stock_ids_var is not None else ""
        stock_ids = self.parse_stock_ids(raw_stock_ids)
        if not stock_ids:
            self._append_result("Stock IDs cannot be blank.")
            return None

        try:
            max_workers = self._parse_positive_int(
                self.scan_max_workers_var.get() if self.scan_max_workers_var is not None else "4",
                "Max workers must be a positive integer.",
            )
            min_score = self._parse_optional_float(
                self.scan_min_score_var.get() if self.scan_min_score_var is not None else "",
                "Min score must be a number.",
            )
            top = self._parse_optional_positive_int(
                self.scan_top_var.get() if self.scan_top_var is not None else "",
                "Top must be a positive integer.",
            )
        except ValueError as exc:
            self._append_result(str(exc))
            return None

        period = self.scan_period_var.get() if self.scan_period_var is not None else "1y"
        interval = self.scan_interval_var.get() if self.scan_interval_var is not None else "1d"
        errors_only = self.scan_errors_only_var.get() if self.scan_errors_only_var is not None else False
        return self.submit_task(
            "Run Scan",
            app_services.scan_stocks_with_options_service,
            stock_ids=stock_ids,
            period=period,
            interval=interval,
            max_workers=max_workers,
            min_score=min_score,
            top=top,
            errors_only=errors_only,
        )

    def submit_stock_list_update(self) -> str | None:
        """Submit official stock-list update using current form values."""
        market = self.market_var.get() if self.market_var is not None else "all"
        output = self.output_var.get().strip() if self.output_var is not None else "stocks.txt"
        allow_partial = self.allow_partial_var.get() if self.allow_partial_var is not None else False
        if not output:
            self._append_result("Output path cannot be blank.")
            return None
        return self.submit_task(
            "Update Stock List",
            app_services.stock_list_updater_service,
            market=market,
            output=output,
            allow_partial=allow_partial,
        )

    def submit_task(self, name: str, func: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
        """Submit a service call to the background runner."""
        task_id = self.runner.submit(name, func, *args, **kwargs)
        self._append_result(f"Submitted: {name} ({task_id})")
        self.refresh_tasks(schedule_next=False)
        return task_id

    def refresh_tasks(self, schedule_next: bool = True) -> None:
        """Refresh task list and append newly finished results."""
        tasks = self.runner.list_tasks()
        if self.task_tree is not None:
            self._refresh_tree(tasks)
        for task in tasks:
            if task.status in {SUCCESS, FAILED} and task.task_id not in self._reported_finished:
                self._reported_finished.add(task.task_id)
                self._append_finished_task(task)
        if schedule_next and not self._closed:
            self.root.after(REFRESH_MS, self.refresh_tasks)

    def _refresh_tree(self, tasks: list[TaskState]) -> None:
        assert self.task_tree is not None
        self.task_tree.delete(*self.task_tree.get_children())
        for task in tasks:
            self.task_tree.insert(
                "",
                "end",
                iid=task.task_id,
                values=(
                    task.task_id,
                    task.name,
                    task.status,
                    f"{task.progress:.0%}",
                    task.message,
                    task.error or "",
                    task.started_at.isoformat(sep=" ", timespec="seconds") if task.started_at else "",
                    task.finished_at.isoformat(sep=" ", timespec="seconds") if task.finished_at else "",
                ),
            )

    def _append_finished_task(self, task: TaskState) -> None:
        if task.status == SUCCESS:
            self._append_result(f"SUCCESS: {task.name}\n{task.result}")
        elif task.status == FAILED:
            self._append_result(f"FAILED: {task.name}\n{task.error}")

    def _append_result(self, text: str) -> None:
        if self.result_text is None:
            return
        self.result_text.insert("end", text + "\n\n")
        self.result_text.see("end")

    def _selected_task_id(self) -> str | None:
        if self.task_tree is None:
            return None
        selected = self.task_tree.selection()
        if not selected:
            return None
        return str(selected[0])

    def cancel_selected_task(self) -> None:
        """Cancel the selected task when it has not started yet."""
        task_id = self._selected_task_id()
        if task_id is None:
            self._append_result("No task selected.")
            return
        try:
            cancelled = self.runner.cancel_task(task_id)
        except KeyError:
            self._append_result(f"Task not found: {task_id}")
            return
        if cancelled:
            self._append_result(f"Cancelled task: {task_id}")
        else:
            self._append_result("Task is already running or finished; it cannot be cancelled safely.")
        self.refresh_tasks(schedule_next=False)

    def clear_finished_tasks(self) -> None:
        removed = self.runner.clear_finished()
        self._append_result(f"Cleared finished tasks: {removed}")
        self.refresh_tasks(schedule_next=False)

    def close(self) -> None:
        """Close the GUI and stop accepting new background work."""
        self._closed = True
        self.runner.shutdown(wait=False)
        self.root.destroy()


def main() -> None:
    app = TwStockToolGUI()
    try:
        app.root.mainloop()
    except KeyboardInterrupt:
        app.close()
    except Exception as exc:
        messagebox.showerror("tw_stock_tool GUI", str(exc))
        app.close()


if __name__ == "__main__":
    main()
