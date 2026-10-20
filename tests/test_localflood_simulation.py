"""Tests for simulation and parallel execution (FR-04, FR-05)."""

from __future__ import annotations

import pytest

from localflood.simulation import (
    MAX_SAMPLES,
    SimulationParameters,
    compare_modes,
    generate_scenarios,
    risk_category,
    run_parallel,
    run_scenarios,
    run_serial,
    simulate_scenario,
)

FAST = dict(samples_per_scenario=2_000, time_steps=12)


def test_parameter_validation():
    with pytest.raises(ValueError):
        SimulationParameters(rainfall_multiplier=-1).validated()
    with pytest.raises(ValueError):
        SimulationParameters(runoff_coefficient=2).validated()
    with pytest.raises(ValueError):
        SimulationParameters(threshold_mm=0).validated()
    with pytest.raises(ValueError):
        SimulationParameters(samples_per_scenario=MAX_SAMPLES + 1).validated()
    with pytest.raises(ValueError):
        SimulationParameters(time_steps=0).validated()


def test_risk_category_thresholds():
    assert risk_category(0) == "Rendah"
    assert risk_category(30) == "Sedang"
    assert risk_category(60) == "Tinggi"
    assert risk_category(95) == "Sangat Tinggi"


def test_simulate_scenario_bounds():
    parameters = SimulationParameters(**FAST)
    scenario = generate_scenarios(150, count=1)[0]
    result = simulate_scenario(scenario, parameters)
    assert 0.0 <= result.risk_score <= 100.0
    assert result.samples == FAST["samples_per_scenario"]
    assert result.risk_category in {"Rendah", "Sedang", "Tinggi", "Sangat Tinggi"}


def test_higher_rainfall_increases_risk():
    parameters = SimulationParameters(**FAST)
    low = simulate_scenario(generate_scenarios(50, count=1)[0], parameters)
    high = simulate_scenario(generate_scenarios(250, count=1)[0], parameters)
    assert high.risk_score > low.risk_score


def test_simulation_is_reproducible():
    parameters = SimulationParameters(**FAST)
    scenario = generate_scenarios(120, count=1)[0]
    first = simulate_scenario(scenario, parameters)
    second = simulate_scenario(scenario, parameters)
    assert first.risk_score == second.risk_score
    assert first.p90_risk_score == second.p90_risk_score


def test_simulate_rejects_negative_rainfall():
    parameters = SimulationParameters(**FAST)
    scenario = generate_scenarios(10, count=1)[0]
    object.__setattr__(scenario, "rainfall_mm", -5.0)
    with pytest.raises(ValueError):
        simulate_scenario(scenario, parameters)


def test_serial_and_parallel_match():
    parameters = SimulationParameters(**FAST)
    scenarios = generate_scenarios(120, count=4)
    serial = run_serial(scenarios, parameters)
    parallel = run_parallel(scenarios, parameters, max_workers=2, executor="thread")
    assert len(serial.results) == len(parallel.results)
    for left, right in zip(serial.results, parallel.results):
        assert left.name == right.name
        assert left.risk_score == pytest.approx(right.risk_score, abs=1e-9)


def test_parallel_preserves_scenario_order():
    parameters = SimulationParameters(**FAST)
    scenarios = generate_scenarios(120, count=6)
    parallel = run_parallel(scenarios, parameters, max_workers=3, executor="thread")
    assert [result.name for result in parallel.results] == [scenario.name for scenario in scenarios]


def test_run_scenarios_dispatch():
    parameters = SimulationParameters(**FAST)
    scenarios = generate_scenarios(120, count=2)
    assert run_scenarios(scenarios, parameters, mode="serial").mode == "serial"
    assert "parallel" in run_scenarios(
        scenarios, parameters, mode="parallel-thread", max_workers=2
    ).mode
    with pytest.raises(ValueError):
        run_scenarios(scenarios, parameters, mode="unknown")


def test_compare_modes_consistency():
    parameters = SimulationParameters(**FAST)
    scenarios = generate_scenarios(120, count=4)
    comparison = compare_modes(scenarios, parameters, max_workers=2, executor="thread")
    assert comparison["consistent"] is True
    assert comparison["max_delta"] == pytest.approx(0.0, abs=1e-9)
    assert comparison["serial"].mode == "serial"
    assert "parallel" in comparison["parallel"].mode


def test_generate_scenarios_count_and_multipliers():
    scenarios = generate_scenarios(100, count=5)
    assert len(scenarios) == 5
    assert scenarios[0].rainfall_mm < scenarios[-1].rainfall_mm
    assert len({scenario.seed for scenario in scenarios}) == 5


def test_empty_parallel_returns_empty_outcome():
    parameters = SimulationParameters(**FAST)
    outcome = run_parallel([], parameters, max_workers=2, executor="thread")
    assert outcome.results == []
    assert outcome.warnings


def test_outcome_to_dict_and_frame():
    parameters = SimulationParameters(**FAST)
    outcome = run_serial(generate_scenarios(100, count=2), parameters)
    payload = outcome.to_dict()
    assert payload["mode"] == "serial"
    frame = outcome.results_frame()
    assert len(frame) == 2
    assert "risk_score" in frame.columns
