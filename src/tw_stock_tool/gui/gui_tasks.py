"""Thread-safe background task runner for future GUI integrations.

This module does not create a GUI. It provides a small execution layer that a
future GUI can use to call app_services without blocking the UI thread.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import datetime
from threading import Lock
from typing import Any, Callable
from uuid import uuid4

PENDING = "PENDING"
RUNNING = "RUNNING"
SUCCESS = "SUCCESS"
FAILED = "FAILED"
CANCELLED = "CANCELLED"

_FINISHED_STATUSES = {SUCCESS, FAILED, CANCELLED}


@dataclass(frozen=True)
class TaskState:
    """Snapshot of a GUI background task state."""

    task_id: str
    name: str
    status: str
    progress: float
    message: str
    result: Any | None
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None


class TaskRunner:
    """Run service-layer calls in background threads.

    Threads cannot be safely force-stopped in Python. cancel_task() can only
    cancel tasks that are still pending in the executor queue. Running tasks
    return False; future cooperative cancellation can build on update_task().
    """

    def __init__(self, max_workers: int = 2) -> None:
        if max_workers <= 0:
            raise ValueError("max_workers must be greater than 0")
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._lock = Lock()
        self._tasks: dict[str, TaskState] = {}
        self._futures: dict[str, Future[Any]] = {}

    def submit(self, name: str, func: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
        """Submit a background task and immediately return its task id."""
        if not name.strip():
            raise ValueError("name must not be blank")
        task_id = str(uuid4())
        state = TaskState(
            task_id=task_id,
            name=name,
            status=PENDING,
            progress=0.0,
            message="",
            result=None,
            error=None,
            started_at=None,
            finished_at=None,
        )
        with self._lock:
            self._tasks[task_id] = state
        future = self._executor.submit(self._run_task, task_id, func, args, kwargs)
        with self._lock:
            self._futures[task_id] = future
        return task_id

    def _run_task(
        self,
        task_id: str,
        func: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> None:
        with self._lock:
            state = self._tasks.get(task_id)
            if state is None or state.status == CANCELLED:
                return
            self._tasks[task_id] = replace(
                state,
                status=RUNNING,
                started_at=datetime.now(),
            )
        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            with self._lock:
                state = self._tasks[task_id]
                self._tasks[task_id] = replace(
                    state,
                    status=FAILED,
                    error=str(exc),
                    finished_at=datetime.now(),
                )
        else:
            with self._lock:
                state = self._tasks[task_id]
                self._tasks[task_id] = replace(
                    state,
                    status=SUCCESS,
                    progress=1.0,
                    result=result,
                    finished_at=datetime.now(),
                )

    def get_task(self, task_id: str) -> TaskState:
        """Return a copy of one task state."""
        with self._lock:
            if task_id not in self._tasks:
                raise KeyError(task_id)
            return replace(self._tasks[task_id])

    def list_tasks(self) -> list[TaskState]:
        """Return copies of all task states."""
        with self._lock:
            return [replace(state) for state in self._tasks.values()]

    def update_task(
        self,
        task_id: str,
        progress: float | None = None,
        message: str | None = None,
    ) -> TaskState:
        """Update progress/message for a task and return the new snapshot."""
        with self._lock:
            if task_id not in self._tasks:
                raise KeyError(task_id)
            state = self._tasks[task_id]
            if progress is not None and not 0.0 <= progress <= 1.0:
                raise ValueError("progress must be between 0.0 and 1.0")
            updated = replace(
                state,
                progress=state.progress if progress is None else progress,
                message=state.message if message is None else message,
            )
            self._tasks[task_id] = updated
            return replace(updated)

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task.

        Returns True only when the executor confirms that the task had not
        started yet. Running tasks cannot be safely interrupted and return False.
        """
        with self._lock:
            if task_id not in self._tasks:
                raise KeyError(task_id)
            state = self._tasks[task_id]
            future = self._futures.get(task_id)
            if state.status != PENDING or future is None:
                return False
        if not future.cancel():
            return False
        with self._lock:
            state = self._tasks[task_id]
            self._tasks[task_id] = replace(
                state,
                status=CANCELLED,
                finished_at=datetime.now(),
            )
        return True

    def clear_finished(self) -> int:
        """Remove finished tasks and return the number removed."""
        with self._lock:
            finished_ids = [
                task_id
                for task_id, state in self._tasks.items()
                if state.status in _FINISHED_STATUSES
            ]
            for task_id in finished_ids:
                self._tasks.pop(task_id, None)
                self._futures.pop(task_id, None)
            return len(finished_ids)

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the underlying executor."""
        self._executor.shutdown(wait=wait)
