#!/usr/bin/env python3
"""Offline regression tests for the durable production queue."""

from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from production_queue import ProductionQueue, atomic_write, utc_now


def wait_for(queue: ProductionQueue, job_id: str, statuses: set[str], timeout: float = 4.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        record = queue.get(job_id)
        if record.get("status") in statuses:
            return record
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} did not reach {statuses}: {queue.get(job_id).get('status')}")


class ProductionQueueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.outputs = Path(self.temporary.name) / "outputs"
        self.queues: list[ProductionQueue] = []

    def tearDown(self) -> None:
        for queue in self.queues:
            queue.shutdown()
        self.temporary.cleanup()

    def queue(self, worker) -> ProductionQueue:
        queue = ProductionQueue(self.outputs, worker)
        self.queues.append(queue)
        return queue

    def test_batch_persists_progress_and_isolates_failures(self) -> None:
        attempts: dict[str, int] = {}

        def worker(payload: dict) -> dict:
            text = str(payload["text"])
            attempts[text] = attempts.get(text, 0) + 1
            if text == "fail" and attempts[text] == 1:
                raise RuntimeError("provider rejected take")
            return {"url": f"/{text}.wav", "durationSeconds": 1.0}

        queue = self.queue(worker)
        summary = queue.submit({
            "title": "三句批次",
            "items": [
                {"seedId": "seed_a", "text": "one"},
                {"seedId": "seed_a", "text": "fail"},
                {"seedId": "seed_a", "text": "three"},
            ],
        })
        finished = wait_for(queue, summary["id"], {"completed_with_errors"})
        self.assertEqual(finished["completedCount"], 2)
        self.assertEqual(finished["failedCount"], 1)
        self.assertEqual([item["status"] for item in finished["items"]], ["completed", "failed", "completed"])
        self.assertTrue((self.outputs / "production_jobs" / summary["id"] / "job.json").exists())

        retried = queue.retry(summary["id"], failed_only=True)
        self.assertEqual(retried["itemCount"], 1)
        retry_finished = wait_for(queue, retried["id"], {"completed"})
        self.assertEqual(retry_finished["completedCount"], 1)
        self.assertEqual(attempts["fail"], 2)

    def test_cancel_finishes_current_take_and_skips_remaining(self) -> None:
        started = threading.Event()
        release = threading.Event()

        def worker(payload: dict) -> dict:
            started.set()
            release.wait(2.0)
            return {"url": "/done.wav"}

        queue = self.queue(worker)
        summary = queue.submit({
            "title": "可取消批次",
            "items": [
                {"seedId": "seed_a", "text": "current"},
                {"seedId": "seed_a", "text": "remaining"},
            ],
        })
        self.assertTrue(started.wait(1.0))
        queue.cancel(summary["id"])
        release.set()
        finished = wait_for(queue, summary["id"], {"cancelled"})
        self.assertEqual(finished["items"][0]["status"], "completed")
        self.assertEqual(finished["items"][1]["status"], "cancelled")

    def test_restart_marks_inflight_job_interrupted_without_spending(self) -> None:
        job_id = "job_recovery_test"
        created = utc_now()
        atomic_write(self.outputs / "production_jobs" / job_id / "job.json", {
            "schemaVersion": 1,
            "id": job_id,
            "title": "重啟恢復",
            "status": "running",
            "createdAt": created,
            "updatedAt": created,
            "items": [{"index": 0, "status": "running", "payload": {"seedId": "seed_a", "text": "do not run"}}],
        })
        calls: list[dict] = []
        queue = self.queue(lambda payload: calls.append(payload) or {})
        recovered = queue.get(job_id)
        self.assertEqual(recovered["status"], "interrupted")
        self.assertEqual(recovered["items"][0]["status"], "interrupted")
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
