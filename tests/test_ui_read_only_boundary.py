import unittest

class TestUIReadOnlyBoundary(unittest.TestCase):
    def test_public_import(self):
        try:
            import tw_stock_tool.ui
            from tw_stock_tool.ui import READ_ONLY_UI_ALLOWED_SURFACES, READ_ONLY_UI_FORBIDDEN_ACTIONS, LEGACY_GUI_BOUNDARY_NOTE, is_read_only_surface
        except ImportError:
            self.fail("tw_stock_tool.ui public import failed.")

    def test_allowed_surfaces(self):
        from tw_stock_tool.ui import READ_ONLY_UI_ALLOWED_SURFACES
        expected_surfaces = {
            "dashboard",
            "artifact_viewer",
            "report_viewer",
            "backtest_result_viewer",
            "paper_trading_result_viewer",
            "risk_evaluation_summary_viewer",
            "local_file_viewer",
        }
        self.assertTrue(expected_surfaces.issubset(set(READ_ONLY_UI_ALLOWED_SURFACES)))

    def test_forbidden_actions(self):
        from tw_stock_tool.ui import READ_ONLY_UI_FORBIDDEN_ACTIONS
        expected_forbidden = {
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
        }
        self.assertTrue(expected_forbidden.issubset(set(READ_ONLY_UI_FORBIDDEN_ACTIONS)))

    def test_allowed_does_not_overlap_forbidden(self):
        from tw_stock_tool.ui import READ_ONLY_UI_ALLOWED_SURFACES, READ_ONLY_UI_FORBIDDEN_ACTIONS
        allowed_set = set(READ_ONLY_UI_ALLOWED_SURFACES)
        forbidden_set = set(READ_ONLY_UI_FORBIDDEN_ACTIONS)
        intersection = allowed_set.intersection(forbidden_set)
        self.assertEqual(len(intersection), 0, f"Allowed and forbidden sets overlap: {intersection}")

    def test_legacy_boundary_note(self):
        from tw_stock_tool.ui import LEGACY_GUI_BOUNDARY_NOTE
        self.assertIn("tw_stock_tool.gui", LEGACY_GUI_BOUNDARY_NOTE)
        self.assertIn("legacy/local research control panel", LEGACY_GUI_BOUNDARY_NOTE)
        self.assertIn("tw_stock_tool.ui", LEGACY_GUI_BOUNDARY_NOTE)
        self.assertIn("Phase 37 read-only UI", LEGACY_GUI_BOUNDARY_NOTE)

    def test_is_read_only_surface_helper(self):
        from tw_stock_tool.ui import is_read_only_surface
        self.assertTrue(is_read_only_surface("dashboard"))
        self.assertFalse(is_read_only_surface("run_scan"))

if __name__ == '__main__':
    unittest.main()
