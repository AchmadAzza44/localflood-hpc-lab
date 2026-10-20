"""Demonstrative flood-risk scenario simulation with serial and parallel modes.

The model is intentionally simple and fully documented: a lumped rainfall-runoff
reservoir is integrated over hourly time steps for a Monte Carlo ensemble of
rainfall realizations. Fixed seeds per scenario make every result reproducible.

The ensemble exists so that the serial-versus-parallel demonstration measures a
real computational workload. This is NOT a hydrological model and must not be
used for operational flood forecasting.
"""

from __future__ import annotations

import math
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

import numpy as np

RISK_CATEGORIES = (
    (25.0, "Rendah"),
    (50.0, "Sedang"),
    (75.0, "Tinggi"),
    (100.01, "Sangat Tinggi"),
)

MODEL_DESCRIPTION = (
    "Model demonstratif: hujan skenario dibagi ke dalam langkah waktu per jam, lalu "
    "dialirkan melalui reservoir limpasan sederhana dengan kapasitas drainase tetap. "
    "Ketidakpastian hujan (+/-10%) diintegrasikan melalui ensemble Monte Carlo dengan "
    "seed tetap per skenario. Skor risiko adalah rata-rata puncak beban reservoir "
    "relatif terhadap ambang, bukan prediksi kejadian banjir."
)

DEFAULT_SAMPLES = 60_000
MAX_SAMPLES = 500_000
DEFAULT_STEPS = 24


def risk_category(score: float) -> str:
    for upper, label in RISK_CATEGORIES:
        if score < upper:
            return label
    return "Sangat Tinggi"


@dataclass(frozen=True)
class SimulationParameters:
    """Global parameters applied to every scenario."""

    rainfall_multiplier: float = 1.0
    runoff_coefficient: float = 0.55
    drainage_capacity_mm: float = 45.0
    antecedent_moisture: float = 0.4
    threshold_mm: float = 60.0
    rainfall_uncertainty: float = 0.10
    samples_per_scenario: int = DEFAULT_SAMPLES
    time_steps: int = DEFAULT_STEPS

    def validated(self) -> "SimulationParameters":
        if not 0.0 <= self.rainfall_multiplier <= 5.0:
            raise ValueError("Pengali curah hujan harus berada pada rentang 0 s.d. 5.")
        if not 0.0 <= self.runoff_coefficient <= 1.0:
            raise ValueError("Koefisien limpasan harus berada pada rentang 0 s.d. 1.")
        if self.drainage_capacity_mm < 0:
            raise ValueError("Kapasitas drainase tidak boleh negatif.")
        if not 0.0 <= self.antecedent_moisture <= 1.0:
            raise ValueError("Kelembapan tanah awal harus berada pada rentang 0 s.d. 1.")
        if self.threshold_mm <= 0:
            raise ValueError("Ambang curah hujan harus lebih besar dari nol.")
        if not 0.0 <= self.rainfall_uncertainty <= 1.0:
            raise ValueError("Ketidakpastian hujan harus berada pada rentang 0 s.d. 1.")
        if not 1 <= self.samples_per_scenario <= MAX_SAMPLES:
            raise ValueError(
                f"Jumlah sampel harus berada pada rentang 1 s.d. {MAX_SAMPLES:,}."
            )
        if not 1 <= self.time_steps <= 240:
            raise ValueError("Jumlah langkah waktu harus berada pada rentang 1 s.d. 240.")
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "rainfall_multiplier": self.rainfall_multiplier,
            "runoff_coefficient": self.runoff_coefficient,
            "drainage_capacity_mm": self.drainage_capacity_mm,
            "antecedent_moisture": self.antecedent_moisture,
            "threshold_mm": self.threshold_mm,
            "rainfall_uncertainty": self.rainfall_uncertainty,
            "samples_per_scenario": self.samples_per_scenario,
            "time_steps": self.time_steps,
        }


@dataclass(frozen=True)
class Scenario:
    """One independent rainfall scenario."""

    name: str
    rainfall_mm: float
    duration_hours: float = 6.0
    seed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "rainfall_mm": self.rainfall_mm,
            "duration_hours": self.duration_hours,
            "seed": self.seed,
        }


@dataclass
class ScenarioResult:
    """Model output for a single scenario."""

    name: str
    rainfall_mm: float
    effective_rainfall_mm: float
    excess_mm: float
    risk_score: float
    risk_category: str
    duration_hours: float
    mean_risk_score: float = 0.0
    p10_risk_score: float = 0.0
    p90_risk_score: float = 0.0
    probability_high_pct: float = 0.0
    peak_load_mm: float = 0.0
    samples: int = 0
    time_steps: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "rainfall_mm": round(self.rainfall_mm, 4),
            "duration_hours": round(self.duration_hours, 4),
            "effective_rainfall_mm": round(self.effective_rainfall_mm, 4),
            "excess_mm": round(self.excess_mm, 4),
            "risk_score": round(self.risk_score, 4),
            "risk_category": self.risk_category,
            "mean_risk_score": round(self.mean_risk_score, 4),
            "p10_risk_score": round(self.p10_risk_score, 4),
            "p90_risk_score": round(self.p90_risk_score, 4),
            "probability_high_pct": round(self.probability_high_pct, 4),
            "peak_load_mm": round(self.peak_load_mm, 4),
            "samples": self.samples,
            "time_steps": self.time_steps,
        }


@dataclass
class SimulationOutcome:
    """Results for a batch of scenarios plus execution metadata."""

    mode: str
    results: list[ScenarioResult]
    elapsed_seconds: float
    workers: int
    parameters: SimulationParameters
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "elapsed_seconds": round(self.elapsed_seconds, 6),
            "workers": self.workers,
            "parameters": self.parameters.to_dict(),
            "results": [result.to_dict() for result in self.results],
            "warnings": self.warnings,
        }

    def results_frame(self):
        import pandas as pd

        return pd.DataFrame([result.to_dict() for result in self.results])


def _hyetograph(steps: int, duration_hours: float) -> np.ndarray:
    """Triangular rainfall distribution across time steps (sums to 1)."""
    positions = np.linspace(-1.0, 1.0, steps)
    weights = 1.0 - np.abs(positions) * 0.85
    weights = np.clip(weights, 0.05, None)
    active = np.zeros(steps)
    active_steps = max(1, min(steps, int(round(duration_hours))))
    start = max(0, (steps - active_steps) // 2)
    active[start : start + active_steps] = weights[:active_steps]
    return active / active.sum()


def _ensemble(scenario: Scenario, parameters: SimulationParameters) -> dict[str, float]:
    """Integrate the lumped reservoir over a Monte Carlo ensemble."""
    rng = np.random.default_rng(scenario.seed or 0)
    samples = parameters.samples_per_scenario
    steps = parameters.time_steps

    draws = rng.normal(loc=1.0, scale=parameters.rainfall_uncertainty, size=samples)
    draws = np.clip(draws, 0.05, 3.0)
    total_rain = scenario.rainfall_mm * parameters.rainfall_multiplier * draws

    pattern = _hyetograph(steps, scenario.duration_hours)
    hourly_rain = total_rain[:, None] * pattern[None, :]

    initial_storage = parameters.antecedent_moisture * parameters.threshold_mm * 0.5
    storage = np.full(samples, initial_storage, dtype="float64")
    peak = np.zeros(samples, dtype="float64")
    drainage_per_step = parameters.drainage_capacity_mm / steps
    runoff = parameters.runoff_coefficient
    percolation = 0.08

    for step in range(steps):
        inflow = hourly_rain[:, step] * runoff
        outflow = np.minimum(storage + inflow, drainage_per_step)
        storage = storage + inflow - outflow
        storage *= 1.0 - percolation
        np.maximum(storage, 0.0, out=storage)
        np.maximum(peak, storage, out=peak)

    load_ratio = peak / parameters.threshold_mm
    load_ratio = np.maximum(load_ratio, 0.0)
    scores = 100.0 * (1.0 - np.exp(-load_ratio))
    scores = np.clip(scores, 0.0, 100.0)

    return {
        "mean_score": float(scores.mean()),
        "p10": float(np.percentile(scores, 10)),
        "p90": float(np.percentile(scores, 90)),
        "probability_high": float((scores >= 50.0).mean() * 100.0),
        "effective_mean": float((hourly_rain * runoff).sum(axis=1).mean()),
        "excess_mean": float(np.maximum(peak - parameters.drainage_capacity_mm, 0.0).mean()),
        "peak_mean": float(peak.mean()),
    }


def simulate_scenario(
    scenario: Scenario | dict[str, Any], parameters: SimulationParameters
) -> ScenarioResult:
    """Evaluate a single scenario with the demonstrative risk model."""
    if isinstance(scenario, dict):
        scenario = Scenario(
            name=str(scenario.get("name", "skenario")),
            rainfall_mm=float(scenario.get("rainfall_mm", 0.0)),
            duration_hours=float(scenario.get("duration_hours", 6.0)),
            seed=int(scenario.get("seed", 0)),
        )
    if scenario.rainfall_mm < 0:
        raise ValueError(f"Curah hujan skenario '{scenario.name}' tidak boleh negatif.")
    if scenario.duration_hours <= 0:
        raise ValueError(f"Durasi skenario '{scenario.name}' harus lebih besar dari nol.")

    params = parameters.validated()
    ensemble = _ensemble(scenario, params)
    score = round(max(0.0, min(100.0, ensemble["mean_score"])), 4)

    return ScenarioResult(
        name=scenario.name,
        rainfall_mm=scenario.rainfall_mm,
        effective_rainfall_mm=round(ensemble["effective_mean"], 4),
        excess_mm=round(ensemble["excess_mean"], 4),
        risk_score=score,
        risk_category=risk_category(score),
        duration_hours=scenario.duration_hours,
        mean_risk_score=round(ensemble["mean_score"], 4),
        p10_risk_score=round(ensemble["p10"], 4),
        p90_risk_score=round(ensemble["p90"], 4),
        probability_high_pct=round(ensemble["probability_high"], 4),
        peak_load_mm=round(ensemble["peak_mean"], 4),
        samples=params.samples_per_scenario,
        time_steps=params.time_steps,
    )


def _simulate_worker(payload: dict[str, Any]) -> dict[str, Any]:
    """Top-level worker so results can be pickled by process pools."""
    return simulate_scenario(payload["scenario"], payload["parameters"]).to_dict()


def run_serial(
    scenarios: Sequence[Scenario], parameters: SimulationParameters
) -> SimulationOutcome:
    """Evaluate scenarios sequentially."""
    params = parameters.validated()
    started = time.perf_counter()
    results = [simulate_scenario(scenario, params) for scenario in scenarios]
    elapsed = time.perf_counter() - started
    return SimulationOutcome(
        mode="serial",
        results=results,
        elapsed_seconds=elapsed,
        workers=1,
        parameters=params,
        warnings=[],
    )


def _default_workers() -> int:
    import os

    return max(1, min(8, (os.cpu_count() or 2)))


def run_parallel(
    scenarios: Sequence[Scenario],
    parameters: SimulationParameters,
    max_workers: int | None = None,
    executor: str = "process",
) -> SimulationOutcome:
    """Evaluate scenarios concurrently and preserve deterministic ordering."""
    params = parameters.validated()
    warnings: list[str] = []
    if not scenarios:
        return SimulationOutcome("parallel", [], 0.0, 0, params, ["Tidak ada skenario."])

    worker_count = max(1, min(max_workers or _default_workers(), len(scenarios)))
    payloads = [{"scenario": scenario.to_dict(), "parameters": params} for scenario in scenarios]

    started = time.perf_counter()
    raw_results: dict[int, dict[str, Any]] = {}
    used_executor = executor

    def _dispatch(pool_factory):
        with pool_factory(max_workers=worker_count) as pool:
            futures = {
                pool.submit(_simulate_worker, payload): index
                for index, payload in enumerate(payloads)
            }
            for future in as_completed(futures):
                raw_results[futures[future]] = future.result()

    try:
        if executor == "process":
            _dispatch(ProcessPoolExecutor)
        else:
            _dispatch(ThreadPoolExecutor)
    except (OSError, PermissionError, RuntimeError) as exc:
        warnings.append(
            f"Eksekusi {executor} gagal ({exc.__class__.__name__}); menggunakan thread pool."
        )
        raw_results.clear()
        used_executor = "thread"
        _dispatch(ThreadPoolExecutor)

    elapsed = time.perf_counter() - started
    ordered = [raw_results[index] for index in sorted(raw_results)]
    results = [
        ScenarioResult(
            name=str(item["name"]),
            rainfall_mm=float(item["rainfall_mm"]),
            effective_rainfall_mm=float(item["effective_rainfall_mm"]),
            excess_mm=float(item["excess_mm"]),
            risk_score=float(item["risk_score"]),
            risk_category=str(item["risk_category"]),
            duration_hours=float(item["duration_hours"]),
            mean_risk_score=float(item.get("mean_risk_score", item["risk_score"])),
            p10_risk_score=float(item.get("p10_risk_score", item["risk_score"])),
            p90_risk_score=float(item.get("p90_risk_score", item["risk_score"])),
            probability_high_pct=float(item.get("probability_high_pct", 0.0)),
            peak_load_mm=float(item.get("peak_load_mm", 0.0)),
            samples=int(item.get("samples", params.samples_per_scenario)),
            time_steps=int(item.get("time_steps", params.time_steps)),
        )
        for item in ordered
    ]

    return SimulationOutcome(
        mode=f"parallel-{used_executor}",
        results=results,
        elapsed_seconds=elapsed,
        workers=worker_count,
        parameters=params,
        warnings=warnings,
    )


def run_scenarios(
    scenarios: Sequence[Scenario],
    parameters: SimulationParameters,
    mode: str = "serial",
    max_workers: int | None = None,
) -> SimulationOutcome:
    """Run scenarios in the requested mode."""
    if mode == "serial":
        return run_serial(scenarios, parameters)
    if mode in ("parallel", "parallel-process"):
        return run_parallel(scenarios, parameters, max_workers, executor="process")
    if mode in ("parallel-thread", "thread"):
        return run_parallel(scenarios, parameters, max_workers, executor="thread")
    raise ValueError("Mode harus 'serial' atau 'parallel'.")


def compare_modes(
    scenarios: Sequence[Scenario],
    parameters: SimulationParameters,
    max_workers: int | None = None,
    tolerance: float = 1e-6,
    executor: str = "process",
) -> dict[str, Any]:
    """Run both modes and verify that their results are consistent."""
    serial = run_serial(scenarios, parameters)
    parallel = run_parallel(scenarios, parameters, max_workers=max_workers, executor=executor)

    serial_scores = [result.risk_score for result in serial.results]
    parallel_scores = [result.risk_score for result in parallel.results]
    consistent = len(serial_scores) == len(parallel_scores) and all(
        abs(left - right) <= tolerance for left, right in zip(serial_scores, parallel_scores)
    )

    max_delta = (
        max(abs(left - right) for left, right in zip(serial_scores, parallel_scores))
        if serial_scores and parallel_scores
        else 0.0
    )
    speedup = (
        serial.elapsed_seconds / parallel.elapsed_seconds
        if parallel.elapsed_seconds > 0
        else float("nan")
    )

    warnings = list(parallel.warnings)
    if not consistent:
        warnings.append(
            "Hasil serial dan paralel tidak identik. Periksa konfigurasi eksekusi."
        )
    if speedup < 1.0:
        warnings.append(
            "Mode paralel lebih lambat dari serial karena overhead proses; ini normal "
            "untuk beban kerja kecil."
        )

    return {
        "serial": serial,
        "parallel": parallel,
        "consistent": consistent,
        "max_delta": max_delta,
        "speedup": speedup,
        "warnings": warnings,
    }


def generate_scenarios(
    base_rainfall_mm: float,
    multipliers: Iterable[float] | None = None,
    duration_hours: float = 6.0,
    count: int = 8,
    seed: int = 42,
) -> list[Scenario]:
    """Generate a reproducible family of rainfall scenarios."""
    if multipliers is None:
        multipliers = np.linspace(0.5, 2.0, num=max(2, count))
    scenarios: list[Scenario] = []
    for index, multiplier in enumerate(multipliers, start=1):
        scenarios.append(
            Scenario(
                name=f"Skenario {index} (x{float(multiplier):.2f})",
                rainfall_mm=round(max(0.0, base_rainfall_mm * float(multiplier)), 3),
                duration_hours=float(duration_hours),
                seed=seed + index * 101,
            )
        )
    return scenarios
