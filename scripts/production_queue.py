#!/usr/bin/env python3
"""Persistent single-worker production queue for voice generation batches."""

from __future__ import annotations

import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


class ProductionQueue:
    """Durable FIFO queue.

    A single worker deliberately serializes provider calls and manifest writes.
    The browser may close without losing status, and interrupted jobs require an
    explicit retry so restarting the workstation never spends API quota silently.
    """

    def __init__(self, outputs: Path, worker: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        self.root = outputs / "production_jobs"
        self.root.mkdir(parents=True, exist_ok=True)
        self.worker = worker
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="voice-production")
        self.cancel_flags: dict[str, threading.Event] = {}
        self._recover_interrupted_jobs()

    def _job_path(self, job_id: str) -> Path:
        safe = "".join(char for char in str(job_id) if char.isalnum() or char in "_-")[:80]
        path = self.root / safe / "job.json"
        record = load_json(path, None)
        if not isinstance(record, dict) or record.get("id") != job_id:
            raise ValueError("找不到指定製作任務")
        return path

    def _recover_interrupted_jobs(self) -> None:
        for path in self.root.glob("*/job.json"):
            record = load_json(path, None)
            if not isinstance(record, dict) or record.get("status") not in {"queued", "running", "cancelling"}:
                continue
            record["status"] = "interrupted"
            record["error"] = "工作站曾停止；為避免自動消耗 API，請手動重試。"
            record["updatedAt"] = utc_now()
            for item in record.get("items", []):
                if item.get("status") in {"queued", "running"}:
                    item["status"] = "interrupted"
            atomic_write(path, record)

    def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        raw_items = payload.get("items", [])
        if not isinstance(raw_items, list) or not raw_items:
            raise ValueError("批次製作至少需要一個項目")
        if len(raw_items) > 50:
            raise ValueError("單一批次最多 50 個生成項目")
        items = []
        for index, raw in enumerate(raw_items):
            if not isinstance(raw, dict):
                raise ValueError(f"第 {index + 1} 個生成項目格式無效")
            seed_id = str(raw.get("seedId", "")).strip()
            text = str(raw.get("text", "")).strip()
            if not seed_id or not text:
                raise ValueError(f"第 {index + 1} 個生成項目缺少聲音種子或台詞")
            items.append({
                "index": index,
                "label": str(raw.get("label", "")).strip()[:120] or f"Take {index + 1}",
                "status": "queued",
                "payload": dict(raw),
                "result": None,
                "error": None,
            })
        created = utc_now()
        identity = json.dumps({"created": created, "title": payload.get("title"), "items": raw_items}, ensure_ascii=False, sort_keys=True)
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:10]
        job_id = f"job_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{digest}"
        record = {
            "schemaVersion": 1,
            "id": job_id,
            "type": str(payload.get("type", "voice_batch")),
            "title": str(payload.get("title", "批次語音製作")).strip()[:160] or "批次語音製作",
            "description": str(payload.get("description", "")).strip()[:500],
            "status": "queued",
            "priority": max(1, min(5, int(payload.get("priority", 3)))),
            "itemCount": len(items),
            "completedCount": 0,
            "failedCount": 0,
            "progress": 0.0,
            "cancelRequested": False,
            "createdAt": created,
            "updatedAt": created,
            "startedAt": None,
            "finishedAt": None,
            "items": items,
        }
        path = self.root / job_id / "job.json"
        with self.lock:
            atomic_write(path, record)
            self.cancel_flags[job_id] = threading.Event()
            self.executor.submit(self._run, job_id)
        return self.summary(record)

    def _run(self, job_id: str) -> None:
        path = self.root / job_id / "job.json"
        cancel = self.cancel_flags.setdefault(job_id, threading.Event())
        with self.lock:
            record = load_json(path, None)
            if not isinstance(record, dict):
                return
            record.update({"status": "running", "startedAt": utc_now(), "updatedAt": utc_now()})
            atomic_write(path, record)
        for item in record["items"]:
            if cancel.is_set():
                break
            with self.lock:
                latest = load_json(path, record)
                if latest.get("cancelRequested"):
                    cancel.set()
                    break
                item = latest["items"][int(item["index"])]
                item["status"] = "running"
                item["startedAt"] = utc_now()
                latest["updatedAt"] = utc_now()
                atomic_write(path, latest)
            try:
                result = self.worker(dict(item["payload"]))
                status, error = "completed", None
            except Exception as exc:  # isolated batch item; the next take should still run
                result, status, error = None, "failed", f"{type(exc).__name__}: {str(exc)[:800]}"
            with self.lock:
                latest = load_json(path, latest)
                current = latest["items"][int(item["index"])]
                current.update({"status": status, "result": result, "error": error, "finishedAt": utc_now()})
                completed = sum(entry.get("status") == "completed" for entry in latest["items"])
                failed = sum(entry.get("status") == "failed" for entry in latest["items"])
                finished = completed + failed
                latest.update({
                    "completedCount": completed,
                    "failedCount": failed,
                    "progress": round(finished / max(1, len(latest["items"])), 4),
                    "updatedAt": utc_now(),
                })
                atomic_write(path, latest)
                record = latest
        with self.lock:
            latest = load_json(path, record)
            if cancel.is_set() or latest.get("cancelRequested"):
                final_status = "cancelled"
                for item in latest["items"]:
                    if item.get("status") == "queued":
                        item["status"] = "cancelled"
            elif latest.get("failedCount", 0):
                final_status = "completed_with_errors"
            else:
                final_status = "completed"
            latest.update({"status": final_status, "progress": 1.0, "finishedAt": utc_now(), "updatedAt": utc_now()})
            atomic_write(path, latest)

    @staticmethod
    def summary(record: dict[str, Any]) -> dict[str, Any]:
        return {key: record.get(key) for key in (
            "id", "type", "title", "description", "status", "priority", "itemCount",
            "completedCount", "failedCount", "progress", "cancelRequested", "createdAt",
            "updatedAt", "startedAt", "finishedAt", "error",
        )}

    def list(self, limit: int = 100) -> list[dict[str, Any]]:
        records = []
        for path in self.root.glob("*/job.json"):
            record = load_json(path, None)
            if isinstance(record, dict):
                records.append(self.summary(record))
        records.sort(key=lambda item: str(item.get("createdAt", "")), reverse=True)
        return records[: max(1, min(500, limit))]

    def get(self, job_id: str) -> dict[str, Any]:
        record = load_json(self._job_path(job_id), None)
        if not isinstance(record, dict):
            raise ValueError("找不到指定製作任務")
        return record

    def cancel(self, job_id: str) -> dict[str, Any]:
        with self.lock:
            path = self._job_path(job_id)
            record = load_json(path, {})
            if record.get("status") not in {"queued", "running", "cancelling"}:
                return self.summary(record)
            record.update({"cancelRequested": True, "status": "cancelling", "updatedAt": utc_now()})
            atomic_write(path, record)
            self.cancel_flags.setdefault(job_id, threading.Event()).set()
            return self.summary(record)

    def retry(self, job_id: str, failed_only: bool = False) -> dict[str, Any]:
        original = self.get(job_id)
        candidates = [
            item for item in original.get("items", [])
            if not failed_only or item.get("status") in {"failed", "interrupted", "cancelled"}
        ]
        if not candidates:
            raise ValueError("這個任務沒有可重試的項目")
        return self.submit({
            "type": original.get("type", "voice_batch"),
            "title": f"重試｜{original.get('title', '批次製作')}",
            "description": f"來源任務：{job_id}",
            "priority": original.get("priority", 3),
            "items": [item["payload"] for item in candidates],
        })

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)
