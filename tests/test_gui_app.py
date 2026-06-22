import unittest
from unittest.mock import Mock, patch

import gui_app
from gui_tasks import TaskState


class GuiAppTest(unittest.TestCase):
    class _Var:
        def __init__(self, value):
            self.value = value

        def get(self):
            return self.value

    def _root(self) -> Mock:
        root = Mock()
        root.after = Mock()
        root.destroy = Mock()
        return root

    def _runner(self) -> Mock:
        runner = Mock()
        runner.list_tasks.return_value = []
        runner.submit.return_value = "task-1"
        runner.shutdown = Mock()
        return runner

    def test_import_gui_app(self) -> None:
        self.assertTrue(hasattr(gui_app, "TwStockToolGUI"))

    def test_gui_class_can_be_created_without_mainloop(self) -> None:
        root = self._root()
        runner = self._runner()

        app = gui_app.TwStockToolGUI(root=root, runner=runner, build_ui=False)

        self.assertIs(app.root, root)
        self.assertIs(app.runner, runner)
        root.after.assert_not_called()

    def test_stock_list_variables_exist_on_gui_instance(self) -> None:
        root = self._root()
        runner = self._runner()

        app = gui_app.TwStockToolGUI(root=root, runner=runner, build_ui=False)

        self.assertTrue(hasattr(app, "market_var"))
        self.assertTrue(hasattr(app, "output_var"))
        self.assertTrue(hasattr(app, "allow_partial_var"))

    def test_submit_stock_list_update_calls_runner_submit(self) -> None:
        root = self._root()
        runner = self._runner()
        app = gui_app.TwStockToolGUI(root=root, runner=runner, build_ui=False)
        app.market_var = self._Var("tpex")
        app.output_var = self._Var("output/stocks.txt")
        app.allow_partial_var = self._Var(True)

        task_id = app.submit_stock_list_update()

        self.assertEqual(task_id, "task-1")
        runner.submit.assert_called_once_with(
            "Update Stock List",
            gui_app.app_services.stock_list_updater_service,
            market="tpex",
            output="output/stocks.txt",
            allow_partial=True,
        )

    def test_submit_stock_list_update_rejects_blank_output(self) -> None:
        root = self._root()
        runner = self._runner()
        app = gui_app.TwStockToolGUI(root=root, runner=runner, build_ui=False)
        app.market_var = self._Var("all")
        app.output_var = self._Var("   ")
        app.allow_partial_var = self._Var(False)
        app.result_text = Mock()

        task_id = app.submit_stock_list_update()

        self.assertIsNone(task_id)
        runner.submit.assert_not_called()
        inserted_text = app.result_text.insert.call_args.args[1]
        self.assertIn("Output path cannot be blank.", inserted_text)

    def _configure_scan_vars(
        self,
        app,
        stock_ids="2330, 2317 2454",
        period="2y",
        interval="1d",
        max_workers="4",
        min_score="3.5",
        top="10",
        errors_only=True,
    ) -> None:
        app.scan_stock_ids_var = self._Var(stock_ids)
        app.scan_period_var = self._Var(period)
        app.scan_interval_var = self._Var(interval)
        app.scan_max_workers_var = self._Var(max_workers)
        app.scan_min_score_var = self._Var(min_score)
        app.scan_top_var = self._Var(top)
        app.scan_errors_only_var = self._Var(errors_only)

    def test_scan_variables_exist_on_gui_instance(self) -> None:
        root = self._root()
        runner = self._runner()

        app = gui_app.TwStockToolGUI(root=root, runner=runner, build_ui=False)

        self.assertTrue(hasattr(app, "scan_stock_ids_var"))
        self.assertTrue(hasattr(app, "scan_period_var"))
        self.assertTrue(hasattr(app, "scan_interval_var"))
        self.assertTrue(hasattr(app, "scan_max_workers_var"))
        self.assertTrue(hasattr(app, "scan_min_score_var"))
        self.assertTrue(hasattr(app, "scan_top_var"))
        self.assertTrue(hasattr(app, "scan_errors_only_var"))

    def test_parse_stock_ids_handles_commas_and_spaces(self) -> None:
        app = gui_app.TwStockToolGUI(root=self._root(), runner=self._runner(), build_ui=False)

        result = app.parse_stock_ids("2330, 2317 2454")

        self.assertEqual(result, ["2330", "2317", "2454"])

    def test_submit_scan_calls_runner_submit_with_options(self) -> None:
        root = self._root()
        runner = self._runner()
        app = gui_app.TwStockToolGUI(root=root, runner=runner, build_ui=False)
        self._configure_scan_vars(app)

        task_id = app.submit_scan()

        self.assertEqual(task_id, "task-1")
        runner.submit.assert_called_once_with(
            "Run Scan",
            gui_app.app_services.scan_stocks_with_options_service,
            stock_ids=["2330", "2317", "2454"],
            period="2y",
            interval="1d",
            max_workers=4,
            min_score=3.5,
            top=10,
            errors_only=True,
        )

    def test_submit_scan_allows_blank_optional_fields(self) -> None:
        runner = self._runner()
        app = gui_app.TwStockToolGUI(root=self._root(), runner=runner, build_ui=False)
        self._configure_scan_vars(app, min_score="", top="", errors_only=False)

        app.submit_scan()

        kwargs = runner.submit.call_args.kwargs
        self.assertIsNone(kwargs["min_score"])
        self.assertIsNone(kwargs["top"])
        self.assertFalse(kwargs["errors_only"])

    def test_submit_scan_rejects_blank_stock_ids(self) -> None:
        runner = self._runner()
        app = gui_app.TwStockToolGUI(root=self._root(), runner=runner, build_ui=False)
        self._configure_scan_vars(app, stock_ids="   ")
        app.result_text = Mock()

        task_id = app.submit_scan()

        self.assertIsNone(task_id)
        runner.submit.assert_not_called()
        inserted_text = app.result_text.insert.call_args.args[1]
        self.assertIn("Stock IDs cannot be blank.", inserted_text)

    def test_submit_scan_rejects_invalid_max_workers(self) -> None:
        runner = self._runner()
        app = gui_app.TwStockToolGUI(root=self._root(), runner=runner, build_ui=False)
        self._configure_scan_vars(app, max_workers="0")
        app.result_text = Mock()

        self.assertIsNone(app.submit_scan())
        runner.submit.assert_not_called()
        self.assertIn("Max workers must be a positive integer.", app.result_text.insert.call_args.args[1])

    def test_submit_scan_rejects_invalid_min_score(self) -> None:
        runner = self._runner()
        app = gui_app.TwStockToolGUI(root=self._root(), runner=runner, build_ui=False)
        self._configure_scan_vars(app, min_score="abc")
        app.result_text = Mock()

        self.assertIsNone(app.submit_scan())
        runner.submit.assert_not_called()
        self.assertIn("Min score must be a number.", app.result_text.insert.call_args.args[1])

    def test_submit_scan_rejects_invalid_top(self) -> None:
        runner = self._runner()
        app = gui_app.TwStockToolGUI(root=self._root(), runner=runner, build_ui=False)
        self._configure_scan_vars(app, top="0")
        app.result_text = Mock()

        self.assertIsNone(app.submit_scan())
        runner.submit.assert_not_called()
        self.assertIn("Top must be a positive integer.", app.result_text.insert.call_args.args[1])

    def _configure_daily_vars(
        self,
        app,
        stock_ids="2330, 2317 2454",
        period="2y",
        interval="1d",
        min_score="4.5",
        top="20",
        output="output/daily_report.xlsx",
        progress=True,
    ) -> None:
        app.daily_stock_ids_var = self._Var(stock_ids)
        app.daily_period_var = self._Var(period)
        app.daily_interval_var = self._Var(interval)
        app.daily_min_score_var = self._Var(min_score)
        app.daily_top_var = self._Var(top)
        app.daily_output_var = self._Var(output)
        app.daily_progress_var = self._Var(progress)

    def test_daily_report_variables_exist_on_gui_instance(self) -> None:
        root = self._root()
        runner = self._runner()

        app = gui_app.TwStockToolGUI(root=root, runner=runner, build_ui=False)

        self.assertTrue(hasattr(app, "daily_stock_ids_var"))
        self.assertTrue(hasattr(app, "daily_period_var"))
        self.assertTrue(hasattr(app, "daily_interval_var"))
        self.assertTrue(hasattr(app, "daily_min_score_var"))
        self.assertTrue(hasattr(app, "daily_top_var"))
        self.assertTrue(hasattr(app, "daily_output_var"))
        self.assertTrue(hasattr(app, "daily_progress_var"))

    def test_submit_daily_report_calls_runner_submit_with_options(self) -> None:
        root = self._root()
        runner = self._runner()
        app = gui_app.TwStockToolGUI(root=root, runner=runner, build_ui=False)
        self._configure_daily_vars(app)

        task_id = app.submit_daily_report()

        self.assertEqual(task_id, "task-1")
        runner.submit.assert_called_once_with(
            "Run Daily Report",
            gui_app.app_services.daily_report_service,
            stock_ids=["2330", "2317", "2454"],
            period="2y",
            interval="1d",
            min_score=4.5,
            top=20,
            output="output/daily_report.xlsx",
            progress=True,
        )

    def test_submit_daily_report_blank_output_passes_none(self) -> None:
        runner = self._runner()
        app = gui_app.TwStockToolGUI(root=self._root(), runner=runner, build_ui=False)
        self._configure_daily_vars(app, output="   ")

        app.submit_daily_report()

        self.assertIsNone(runner.submit.call_args.kwargs["output"])

    def test_submit_daily_report_blank_min_score_uses_default(self) -> None:
        runner = self._runner()
        app = gui_app.TwStockToolGUI(root=self._root(), runner=runner, build_ui=False)
        self._configure_daily_vars(app, min_score="")

        app.submit_daily_report()

        self.assertEqual(runner.submit.call_args.kwargs["min_score"], gui_app.app_services.DEFAULT_MIN_SCORE)

    def test_submit_daily_report_blank_top_passes_none(self) -> None:
        runner = self._runner()
        app = gui_app.TwStockToolGUI(root=self._root(), runner=runner, build_ui=False)
        self._configure_daily_vars(app, top="")

        app.submit_daily_report()

        self.assertIsNone(runner.submit.call_args.kwargs["top"])

    def test_submit_daily_report_rejects_blank_stock_ids(self) -> None:
        runner = self._runner()
        app = gui_app.TwStockToolGUI(root=self._root(), runner=runner, build_ui=False)
        self._configure_daily_vars(app, stock_ids="   ")
        app.result_text = Mock()

        task_id = app.submit_daily_report()

        self.assertIsNone(task_id)
        runner.submit.assert_not_called()
        self.assertIn("Stock IDs cannot be blank.", app.result_text.insert.call_args.args[1])

    def test_submit_daily_report_rejects_invalid_min_score(self) -> None:
        runner = self._runner()
        app = gui_app.TwStockToolGUI(root=self._root(), runner=runner, build_ui=False)
        self._configure_daily_vars(app, min_score="abc")
        app.result_text = Mock()

        self.assertIsNone(app.submit_daily_report())
        runner.submit.assert_not_called()
        self.assertIn("Min score must be a number.", app.result_text.insert.call_args.args[1])

    def test_submit_daily_report_rejects_invalid_top(self) -> None:
        runner = self._runner()
        app = gui_app.TwStockToolGUI(root=self._root(), runner=runner, build_ui=False)
        self._configure_daily_vars(app, top="0")
        app.result_text = Mock()

        self.assertIsNone(app.submit_daily_report())
        runner.submit.assert_not_called()
        self.assertIn("Top must be a positive integer.", app.result_text.insert.call_args.args[1])

    def _configure_single_stock_vars(
        self,
        app,
        stock_id="2330",
        period="2y",
        interval="1d",
        stop_loss="8",
        take_profit="20",
        max_hold_days="30",
        position_size="0.5",
        export_excel=True,
        save_chart=True,
    ) -> None:
        app.single_stock_id_var = self._Var(stock_id)
        app.single_period_var = self._Var(period)
        app.single_interval_var = self._Var(interval)
        app.single_stop_loss_var = self._Var(stop_loss)
        app.single_take_profit_var = self._Var(take_profit)
        app.single_max_hold_days_var = self._Var(max_hold_days)
        app.single_position_size_var = self._Var(position_size)
        app.single_export_excel_var = self._Var(export_excel)
        app.single_save_chart_var = self._Var(save_chart)

    def test_single_stock_variables_exist_on_gui_instance(self) -> None:
        root = self._root()
        runner = self._runner()

        app = gui_app.TwStockToolGUI(root=root, runner=runner, build_ui=False)

        self.assertTrue(hasattr(app, "single_stock_id_var"))
        self.assertTrue(hasattr(app, "single_period_var"))
        self.assertTrue(hasattr(app, "single_interval_var"))
        self.assertTrue(hasattr(app, "single_stop_loss_var"))
        self.assertTrue(hasattr(app, "single_take_profit_var"))
        self.assertTrue(hasattr(app, "single_max_hold_days_var"))
        self.assertTrue(hasattr(app, "single_position_size_var"))
        self.assertTrue(hasattr(app, "single_export_excel_var"))
        self.assertTrue(hasattr(app, "single_save_chart_var"))

    def test_submit_single_stock_analysis_calls_runner_submit_with_options(self) -> None:
        root = self._root()
        runner = self._runner()
        app = gui_app.TwStockToolGUI(root=root, runner=runner, build_ui=False)
        self._configure_single_stock_vars(app)

        task_id = app.submit_single_stock_analysis()

        self.assertEqual(task_id, "task-1")
        runner.submit.assert_called_once_with(
            "Run Single Stock Analysis",
            gui_app.app_services.single_stock_analysis_service,
            stock_id="2330",
            period="2y",
            interval="1d",
            stop_loss_pct=8.0,
            take_profit_pct=20.0,
            max_hold_days=30,
            position_size=0.5,
            export_excel=True,
            save_chart=True,
        )

    def test_submit_single_stock_analysis_optional_fields_blank_pass_none(self) -> None:
        runner = self._runner()
        app = gui_app.TwStockToolGUI(root=self._root(), runner=runner, build_ui=False)
        self._configure_single_stock_vars(
            app,
            stop_loss="",
            take_profit="",
            max_hold_days="",
            position_size="1.0",
            export_excel=False,
            save_chart=False,
        )

        app.submit_single_stock_analysis()

        kwargs = runner.submit.call_args.kwargs
        self.assertIsNone(kwargs["stop_loss_pct"])
        self.assertIsNone(kwargs["take_profit_pct"])
        self.assertIsNone(kwargs["max_hold_days"])
        self.assertEqual(kwargs["position_size"], 1.0)
        self.assertFalse(kwargs["export_excel"])
        self.assertFalse(kwargs["save_chart"])

    def test_submit_single_stock_analysis_rejects_blank_stock_id(self) -> None:
        runner = self._runner()
        app = gui_app.TwStockToolGUI(root=self._root(), runner=runner, build_ui=False)
        self._configure_single_stock_vars(app, stock_id="   ")
        app.result_text = Mock()

        self.assertIsNone(app.submit_single_stock_analysis())
        runner.submit.assert_not_called()
        self.assertIn("Stock ID cannot be blank.", app.result_text.insert.call_args.args[1])

    def test_submit_single_stock_analysis_rejects_invalid_stop_loss(self) -> None:
        for value in ("0", "abc"):
            with self.subTest(value=value):
                runner = self._runner()
                app = gui_app.TwStockToolGUI(root=self._root(), runner=runner, build_ui=False)
                self._configure_single_stock_vars(app, stop_loss=value)
                app.result_text = Mock()

                self.assertIsNone(app.submit_single_stock_analysis())
                runner.submit.assert_not_called()
                self.assertIn("Stop loss must be a positive number.", app.result_text.insert.call_args.args[1])

    def test_submit_single_stock_analysis_rejects_invalid_take_profit(self) -> None:
        for value in ("0", "abc"):
            with self.subTest(value=value):
                runner = self._runner()
                app = gui_app.TwStockToolGUI(root=self._root(), runner=runner, build_ui=False)
                self._configure_single_stock_vars(app, take_profit=value)
                app.result_text = Mock()

                self.assertIsNone(app.submit_single_stock_analysis())
                runner.submit.assert_not_called()
                self.assertIn("Take profit must be a positive number.", app.result_text.insert.call_args.args[1])

    def test_submit_single_stock_analysis_rejects_invalid_max_hold_days(self) -> None:
        for value in ("0", "abc"):
            with self.subTest(value=value):
                runner = self._runner()
                app = gui_app.TwStockToolGUI(root=self._root(), runner=runner, build_ui=False)
                self._configure_single_stock_vars(app, max_hold_days=value)
                app.result_text = Mock()

                self.assertIsNone(app.submit_single_stock_analysis())
                runner.submit.assert_not_called()
                self.assertIn("Max hold days must be a positive integer.", app.result_text.insert.call_args.args[1])

    def test_submit_single_stock_analysis_rejects_invalid_position_size(self) -> None:
        for value in ("abc", "0", "1.5"):
            with self.subTest(value=value):
                runner = self._runner()
                app = gui_app.TwStockToolGUI(root=self._root(), runner=runner, build_ui=False)
                self._configure_single_stock_vars(app, position_size=value)
                app.result_text = Mock()

                self.assertIsNone(app.submit_single_stock_analysis())
                runner.submit.assert_not_called()
                self.assertIn(
                    "Position size must be greater than 0 and less than or equal to 1.",
                    app.result_text.insert.call_args.args[1],
                )

    def test_cache_submit_methods_exist_on_gui_instance(self) -> None:
        root = self._root()
        runner = self._runner()

        app = gui_app.TwStockToolGUI(root=root, runner=runner, build_ui=False)

        self.assertTrue(hasattr(app, "submit_cache_summary"))
        self.assertTrue(hasattr(app, "submit_cache_clear"))

    def test_submit_cache_summary_calls_runner_submit(self) -> None:
        root = self._root()
        runner = self._runner()
        app = gui_app.TwStockToolGUI(root=root, runner=runner, build_ui=False)

        task_id = app.submit_cache_summary()

        self.assertEqual(task_id, "task-1")
        runner.submit.assert_called_once_with(
            "Cache Summary",
            gui_app.app_services.cache_summary_service,
        )

    def test_submit_cache_clear_calls_runner_submit(self) -> None:
        root = self._root()
        runner = self._runner()
        app = gui_app.TwStockToolGUI(root=root, runner=runner, build_ui=False)

        task_id = app.submit_cache_clear()

        self.assertEqual(task_id, "task-1")
        runner.submit.assert_called_once_with(
            "Clear Cache",
            gui_app.app_services.cache_clear_service,
        )

    def test_submit_task_calls_task_runner_submit(self) -> None:
        root = self._root()
        runner = self._runner()
        app = gui_app.TwStockToolGUI(root=root, runner=runner, build_ui=False)

        task_id = app.submit_task("Doctor", gui_app.app_services.doctor_service, live=True)

        self.assertEqual(task_id, "task-1")
        runner.submit.assert_called_once_with("Doctor", gui_app.app_services.doctor_service, live=True)
        runner.list_tasks.assert_called_once_with()
        root.after.assert_not_called()

    def test_refresh_tasks_handles_empty_task_list(self) -> None:
        root = self._root()
        runner = self._runner()
        app = gui_app.TwStockToolGUI(root=root, runner=runner, build_ui=False)

        app.refresh_tasks(schedule_next=False)

        runner.list_tasks.assert_called_once_with()
        root.after.assert_not_called()

    def test_refresh_tasks_schedules_next_refresh_by_default(self) -> None:
        root = self._root()
        runner = self._runner()
        app = gui_app.TwStockToolGUI(root=root, runner=runner, build_ui=False)

        app.refresh_tasks()

        root.after.assert_called_once()
        self.assertEqual(root.after.call_args.args[0], gui_app.REFRESH_MS)

    def test_refresh_tasks_appends_success_result_once(self) -> None:
        root = self._root()
        runner = self._runner()
        task = TaskState(
            task_id="task-1",
            name="Doctor",
            status=gui_app.SUCCESS,
            progress=1.0,
            message="",
            result={"ok": True},
            error=None,
            started_at=None,
            finished_at=None,
        )
        runner.list_tasks.return_value = [task]
        app = gui_app.TwStockToolGUI(root=root, runner=runner, build_ui=False)
        app.result_text = Mock()

        with patch.object(gui_app, "format_task_result", return_value="formatted result") as formatter:
            app.refresh_tasks(schedule_next=False)
            app.refresh_tasks(schedule_next=False)

        formatter.assert_called_once_with("Doctor", {"ok": True})
        app.result_text.insert.assert_called_once()
        inserted_text = app.result_text.insert.call_args.args[1]
        self.assertIn("SUCCESS: Doctor", inserted_text)
        self.assertIn("formatted result", inserted_text)
        self.assertNotIn("{'ok': True}", inserted_text)

    def test_cancel_selected_task_calls_runner_cancel(self) -> None:
        root = self._root()
        runner = self._runner()
        runner.cancel_task.return_value = True
        app = gui_app.TwStockToolGUI(root=root, runner=runner, build_ui=False)
        app.task_tree = Mock()
        app.task_tree.selection.return_value = ("task-1",)
        app.task_tree.get_children.return_value = []
        app.result_text = Mock()

        app.cancel_selected_task()

        runner.cancel_task.assert_called_once_with("task-1")
        runner.list_tasks.assert_called_once_with()

    def test_close_calls_runner_shutdown_and_destroy(self) -> None:
        root = self._root()
        runner = self._runner()
        app = gui_app.TwStockToolGUI(root=root, runner=runner, build_ui=False)

        app.close()

        runner.shutdown.assert_called_once_with(wait=False)
        root.destroy.assert_called_once_with()
        self.assertTrue(app._closed)


if __name__ == "__main__":
    unittest.main()
