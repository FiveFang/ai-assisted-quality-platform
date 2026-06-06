"""
Temporal workflow definitions.

The workflow is the durable execution boundary:
- If the process crashes mid-pipeline, Temporal replays from the last successful activity.
- Human review pauses are modeled as Temporal signals (workflow waits indefinitely).
- All state flows through activity inputs/outputs — no shared mutable state.
"""
from __future__ import annotations

import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from .activities import (
        run_raa_activity,
        run_tga_activity,
        store_normalized_requirement_activity,
        store_test_suite_activity,
    )

_RETRY = RetryPolicy(
    maximum_attempts=3,
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
)

_ACTIVITY_TIMEOUT = timedelta(minutes=15)


@workflow.defn
class QAPipelineWorkflow:
    """
    End-to-end QA pipeline workflow: RAA → human review (optional) → TGA → human review.
    """

    def __init__(self) -> None:
        self._raa_approved = False
        self._tga_approved = False
        self._rejection_reason: str | None = None

    @workflow.run
    async def run(self, payload: dict) -> dict:
        # Step 1: Run RAA
        normalized = await workflow.execute_activity(
            run_raa_activity,
            payload,
            start_to_close_timeout=_ACTIVITY_TIMEOUT,
            retry_policy=_RETRY,
        )

        # Step 2: Persist RAA output
        await workflow.execute_activity(
            store_normalized_requirement_activity,
            normalized,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=_RETRY,
        )

        # Step 3: Wait for human approval if required
        if normalized.get("human_review_required"):
            await workflow.wait_condition(
                lambda: self._raa_approved or self._rejection_reason is not None,
                timeout=timedelta(days=7),
            )
            if self._rejection_reason:
                return {"status": "REJECTED", "reason": self._rejection_reason}

        # Step 4: Run TGA
        test_suite = await workflow.execute_activity(
            run_tga_activity,
            normalized,
            start_to_close_timeout=_ACTIVITY_TIMEOUT,
            retry_policy=_RETRY,
        )

        # Step 5: Persist TGA output
        await workflow.execute_activity(
            store_test_suite_activity,
            test_suite,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=_RETRY,
        )

        # Step 6: Human review of generated tests (always enabled; configurable)
        await workflow.wait_condition(
            lambda: self._tga_approved or self._rejection_reason is not None,
            timeout=timedelta(days=7),
        )

        return {
            "status": "APPROVED" if self._tga_approved else "REJECTED",
            "normalized_requirement_id": normalized.get("requirement_id"),
            "test_suite_id": test_suite.get("test_suite_id"),
            "reason": self._rejection_reason,
        }

    @workflow.signal
    def approve_raa(self) -> None:
        self._raa_approved = True

    @workflow.signal
    def approve_tga(self) -> None:
        self._tga_approved = True

    @workflow.signal
    def reject(self, reason: str) -> None:
        self._rejection_reason = reason

    @workflow.query
    def get_status(self) -> dict:
        return {
            "raa_approved": self._raa_approved,
            "tga_approved": self._tga_approved,
            "rejection_reason": self._rejection_reason,
        }
