import unittest
from unittest.mock import Mock

import gui_app
from gui_tasks import TaskState


class GuiAppTest(unittest.TestCase):
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

        app.refresh_tasks(schedule_next=False)
        app.refresh_tasks(schedule_next=False)

        app.result_text.insert.assert_called_once()
        inserted_text = app.result_text.insert.call_args.args[1]
        self.assertIn("SUCCESS: Doctor", inserted_text)
        self.assertIn("{'ok': True}", inserted_text)

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
