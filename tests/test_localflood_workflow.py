"""Tests for job tracking, exports, and reporting (FR-06, FR-07)."""

from __future__ import annotations

import json

import pytest

from localflood.historical import summarize_history
from localflood.reporting import build_flood_report_pdf, results_to_csv_bytes
from localflood.schema import normalize_flood_dataframe, validate_flood_dataframe
from localflood.simulation import (
    SimulationParameters,
    compare_modes,
    generate_scenarios,
    run_serial,
)
from localflood.workflow import JobRecord, JobStore

FAST = dict(samples_per_scenario=2_000, time_steps=12)


@pytest.fixture
def store(tmp_path):
    return JobStore(tmp_path)


@pytest.fixture
def valid_flood(flood_frame):
    normalized, _, _ = normalize_flood_dataframe(flood_frame)
    valid, _ = validate_flood_dataframe(normalized)
    return valid


def test_job_store_create_and_load(store):
    record = store.create(
        dataset_name="flood.csv",
        dataset_sha256="a" * 64,
        dataset_rows=100,
        parameters={"runoff_coefficient": 0.5},
        mode="serial",
    )
    loaded = store.load(record.job_id)
    assert loaded.job_id == record.job_id
    assert loaded.status == "pending"
    assert loaded.dataset_sha256 == "a" * 64


def test_job_store_complete(store):
    record = store.create("f.csv", "b" * 64, 10, {}, "parallel")
    store.complete(record, elapsed_seconds=1.25, workers=4, result_summary={"scenarios": 8})
    loaded = store.load(record.job_id)
    assert loaded.status == "completed"
    assert loaded.elapsed_seconds == pytest.approx(1.25)
    assert loaded.workers == 4
    assert loaded.finished_at is not None
    assert loaded.reproducible


def test_job_store_fail(store):
    record = store.create("f.csv", "c" * 64, 10, {}, "serial")
    store.fail(record, "boom")
    loaded = store.load(record.job_id)
    assert loaded.status == "failed"
    assert loaded.error == "boom"


def test_job_store_list_jobs(store):
    first = store.create("a.csv", "1" * 64, 1, {}, "serial")
    second = store.create("b.csv", "2" * 64, 2, {}, "parallel")
    jobs = store.list_jobs()
    assert {job.job_id for job in jobs} == {first.job_id, second.job_id}


def test_job_store_load_missing(store):
    with pytest.raises(FileNotFoundError):
        store.load("job-missing")


def test_job_record_roundtrip_json(store):
    record = store.create("a.csv", "d" * 64, 5, {"x": 1}, "serial")
    path = store.save(record)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["dataset_name"] == "a.csv"
    restored = JobRecord.from_dict(payload)
    assert restored.job_id == record.job_id


def test_results_csv_bytes():
    parameters = SimulationParameters(**FAST)
    outcome = run_serial(generate_scenarios(100, count=3), parameters)
    payload = results_to_csv_bytes(outcome.results)
    assert payload.startswith(b"\xef\xbb\xbf")
    text = payload.decode("utf-8-sig")
    assert "risk_score" in text
    assert text.count("\n") >= 4


def test_flood_report_pdf_single_mode(valid_flood):
    summary = summarize_history(valid_flood)
    parameters = SimulationParameters(**FAST)
    outcome = run_serial(generate_scenarios(120, count=3), parameters)
    pdf = build_flood_report_pdf(
        dataset_name="flood.csv",
        dataset_sha256="e" * 64,
        summary=summary,
        parameters=parameters,
        primary=outcome,
        job_id="job-test",
    )
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 10_000


def test_flood_report_pdf_comparison(valid_flood):
    summary = summarize_history(valid_flood)
    parameters = SimulationParameters(**FAST)
    comparison = compare_modes(
        generate_scenarios(120, count=3), parameters, max_workers=2, executor="thread"
    )
    pdf = build_flood_report_pdf(
        dataset_name="flood.csv",
        dataset_sha256="f" * 64,
        summary=summary,
        parameters=parameters,
        primary=comparison["serial"],
        serial=comparison["serial"],
        parallel=comparison["parallel"],
        job_id="job-compare",
        dataset_warnings=["Peringatan uji."],
    )
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 10_000
