"""Job/workflow tracking for LocalFlood (FR-06).

Each run is persisted as a JSON record so results can be traced back to the
dataset version, parameters, execution method, and status.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from common.config import JOBS_DIR, ensure_runtime_dirs
from common.utils import safe_json, to_jsonable, utc_now_iso


@dataclass
class JobRecord:
    """A single reproducible simulation job."""

    job_id: str
    dataset_name: str
    dataset_sha256: str
    dataset_rows: int
    parameters: dict[str, Any]
    mode: str
    status: str = "pending"
    started_at: str = field(default_factory=utc_now_iso)
    finished_at: str | None = None
    elapsed_seconds: float | None = None
    workers: int | None = None
    result_summary: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    notes: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)

    @property
    def reproducible(self) -> bool:
        return self.status == "completed" and bool(self.dataset_sha256)

    def to_dict(self) -> dict[str, Any]:
        return to_jsonable(
            {
                "job_id": self.job_id,
                "dataset_name": self.dataset_name,
                "dataset_sha256": self.dataset_sha256,
                "dataset_rows": self.dataset_rows,
                "parameters": self.parameters,
                "mode": self.mode,
                "status": self.status,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "elapsed_seconds": self.elapsed_seconds,
                "workers": self.workers,
                "result_summary": self.result_summary,
                "error": self.error,
                "notes": self.notes,
                "created_at": self.created_at,
            }
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "JobRecord":
        known = {field_name for field_name in cls.__dataclass_fields__}
        return cls(**{key: value for key, value in payload.items() if key in known})


class JobStore:
    """File-backed job store under data/jobs."""

    def __init__(self, directory: Path | None = None) -> None:
        ensure_runtime_dirs()
        self.directory = Path(directory) if directory else JOBS_DIR
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, job_id: str) -> Path:
        safe_id = "".join(char for char in job_id if char.isalnum() or char in "-_")
        if not safe_id:
            raise ValueError("ID pekerjaan tidak valid.")
        return self.directory / f"{safe_id}.json"

    def create(
        self,
        dataset_name: str,
        dataset_sha256: str,
        dataset_rows: int,
        parameters: dict[str, Any],
        mode: str,
        notes: list[str] | None = None,
    ) -> JobRecord:
        record = JobRecord(
            job_id=f"job-{uuid.uuid4().hex[:12]}",
            dataset_name=dataset_name,
            dataset_sha256=dataset_sha256,
            dataset_rows=dataset_rows,
            parameters=parameters,
            mode=mode,
            notes=notes or [],
        )
        self.save(record)
        return record

    def save(self, record: JobRecord) -> Path:
        path = self._path(record.job_id)
        path.write_text(safe_json(record.to_dict()), encoding="utf-8")
        return path

    def load(self, job_id: str) -> JobRecord:
        path = self._path(job_id)
        if not path.exists():
            raise FileNotFoundError(f"Pekerjaan '{job_id}' tidak ditemukan.")
        return JobRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list_jobs(self, limit: int = 25) -> list[JobRecord]:
        records: list[JobRecord] = []
        for path in sorted(self.directory.glob("job-*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                records.append(JobRecord.from_dict(json.loads(path.read_text(encoding="utf-8"))))
            except (json.JSONDecodeError, TypeError):
                continue
            if len(records) >= limit:
                break
        return records

    def complete(
        self,
        record: JobRecord,
        elapsed_seconds: float,
        workers: int,
        result_summary: dict[str, Any],
    ) -> JobRecord:
        record.status = "completed"
        record.finished_at = utc_now_iso()
        record.elapsed_seconds = elapsed_seconds
        record.workers = workers
        record.result_summary = result_summary
        self.save(record)
        return record

    def fail(self, record: JobRecord, error: str) -> JobRecord:
        record.status = "failed"
        record.finished_at = utc_now_iso()
        record.error = error
        self.save(record)
        return record
