import threading
import time
import unittest

import gui_tasks


class GuiTasksTest(unittest.TestCase):
    def tearDown(self) -> None:
        runner = getattr(self, "runner", None)
        if runner is not None:
            runner.shutdown(wait=True)

    def _wait_for_status(self, task_id: str, status: str, timeout: float = 2.0) -> gui_tasks.TaskState:
        deadline = time.time() + timeout
        while time.time() < deadline:
            state = self.runner.get_task(task_id)
            if state.status == status:
                return state
            time.sleep(0.01)
        self.fail(f"task {task_id} did not reach {status}")

    def test_submit_success_task_sets_success_and_result(self) -> None:
        self.runner = gui_tasks.TaskRunner(max_workers=1)
        task_id = self.runner.submit("add", lambda x, y: x + y, 2, 3)

        state = self._wait_for_status(task_id, gui_tasks.SUCCESS)

        self.assertEqual(state.result, 5)
        self.assertEqual(state.progress, 1.0)
        self.assertIsNotNone(state.started_at)
        self.assertIsNotNone(state.finished_at)
        self.assertIsNone(state.error)

    def test_failed_task_sets_failed_and_error(self) -> None:
        self.runner = gui_tasks.TaskRunner(max_workers=1)

        def fail() -> None:
            raise RuntimeError("boom")

        task_id = self.runner.submit("fail", fail)

        state = self._wait_for_status(task_id, gui_tasks.FAILED)

        self.assertIn("boom", state.error or "")
        self.assertIsNotNone(state.started_at)
        self.assertIsNotNone(state.finished_at)

    def test_list_tasks_includes_submitted_task(self) -> None:
        self.runner = gui_tasks.TaskRunner(max_workers=1)
        task_id = self.runner.submit("ok", lambda: "done")
        self._wait_for_status(task_id, gui_tasks.SUCCESS)

        task_ids = {task.task_id for task in self.runner.list_tasks()}

        self.assertIn(task_id, task_ids)

    def test_get_task_missing_raises_key_error(self) -> None:
        self.runner = gui_tasks.TaskRunner(max_workers=1)

        with self.assertRaises(KeyError):
            self.runner.get_task("missing")

    def test_clear_finished_only_removes_finished_tasks(self) -> None:
        self.runner = gui_tasks.TaskRunner(max_workers=1)
        release = threading.Event()
        running_id = self.runner.submit("running", release.wait)
        success_id = self.runner.submit("success", lambda: "ok")
        self._wait_for_status(running_id, gui_tasks.RUNNING)

        self.assertEqual(self.runner.clear_finished(), 0)
        self.assertEqual(self.runner.get_task(running_id).status, gui_tasks.RUNNING)

        release.set()
        self._wait_for_status(running_id, gui_tasks.SUCCESS)
        self._wait_for_status(success_id, gui_tasks.SUCCESS)

        self.assertEqual(self.runner.clear_finished(), 2)
        self.assertEqual(self.runner.list_tasks(), [])

    def test_update_task_updates_progress_and_message(self) -> None:
        self.runner = gui_tasks.TaskRunner(max_workers=1)
        release = threading.Event()
        task_id = self.runner.submit("wait", release.wait)
        self._wait_for_status(task_id, gui_tasks.RUNNING)

        updated = self.runner.update_task(task_id, progress=0.4, message="Working")

        self.assertEqual(updated.progress, 0.4)
        self.assertEqual(updated.message, "Working")
        release.set()
        self._wait_for_status(task_id, gui_tasks.SUCCESS)

    def test_update_task_rejects_invalid_progress(self) -> None:
        self.runner = gui_tasks.TaskRunner(max_workers=1)
        release = threading.Event()
        task_id = self.runner.submit("wait", release.wait)

        with self.assertRaises(ValueError):
            self.runner.update_task(task_id, progress=1.5)

        release.set()
        self._wait_for_status(task_id, gui_tasks.SUCCESS)

    def test_cancel_task_can_cancel_pending_task(self) -> None:
        self.runner = gui_tasks.TaskRunner(max_workers=1)
        release = threading.Event()
        first_id = self.runner.submit("blocker", release.wait)
        second_id = self.runner.submit("pending", lambda: "should not run")
        self._wait_for_status(first_id, gui_tasks.RUNNING)

        cancelled = self.runner.cancel_task(second_id)

        self.assertTrue(cancelled)
        self.assertEqual(self.runner.get_task(second_id).status, gui_tasks.CANCELLED)
        release.set()
        self._wait_for_status(first_id, gui_tasks.SUCCESS)

    def test_cancel_task_returns_false_for_running_task(self) -> None:
        self.runner = gui_tasks.TaskRunner(max_workers=1)
        release = threading.Event()
        task_id = self.runner.submit("running", release.wait)
        self._wait_for_status(task_id, gui_tasks.RUNNING)

        self.assertFalse(self.runner.cancel_task(task_id))
        self.assertEqual(self.runner.get_task(task_id).status, gui_tasks.RUNNING)
        release.set()
        self._wait_for_status(task_id, gui_tasks.SUCCESS)


if __name__ == "__main__":
    unittest.main()
