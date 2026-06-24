"""
In-memory registry mapping a client-supplied job_id to the asyncio Task running
that request. Lets a separate cancel endpoint terminate an in-flight analysis or
test-generation run mid-request (including aborting the live LLM stream).

Process-local by design: a job_id is only cancellable on the worker handling it.
For the single-process dev/deploy here that's sufficient.
"""
from __future__ import annotations

import asyncio

import structlog

logger = structlog.get_logger()

_tasks: dict[str, asyncio.Task] = {}


def register(job_id: str, task: asyncio.Task) -> None:
    _tasks[job_id] = task


def unregister(job_id: str) -> None:
    _tasks.pop(job_id, None)


def cancel(job_id: str) -> bool:
    """Cancel the task for job_id. Returns True if a live task was signalled."""
    task = _tasks.get(job_id)
    if task is not None and not task.done():
        task.cancel()
        logger.info("job.cancel.signalled", job_id=job_id)
        return True
    return False
