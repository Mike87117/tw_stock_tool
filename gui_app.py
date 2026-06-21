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
        task_log_frame = ttk.Frame(notebook)
        notebook.add(environment_frame, text="Environment")
        notebook.add(data_sources_frame, text="Data Sources")
        notebook.add(task_log_frame, text="Task Log")

        self._build_environment_tab(environment_frame)
        self._build_data_sources_tab(data_sources_frame)
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
