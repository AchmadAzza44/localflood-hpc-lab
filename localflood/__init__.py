"""LocalFlood HPC Lab: historical analysis, simulation, and HPC demonstration."""

from .schema import (
    CANONICAL_COLUMNS,
    COLUMN_ALIASES,
    FloodDataset,
    SchemaValidationError,
    load_flood_dataset,
    normalize_flood_dataframe,
    validate_flood_dataframe,
)
from .historical import HistoricalSummary, summarize_history
from .geo import build_map_points, valid_coordinate_mask
from .simulation import (
    Scenario,
    SimulationOutcome,
    SimulationParameters,
    compare_modes,
    run_parallel,
    run_serial,
    run_scenarios,
    simulate_scenario,
)
from .workflow import JobRecord, JobStore
from .reporting import build_flood_report_pdf, results_to_csv_bytes

__all__ = [
    "CANONICAL_COLUMNS",
    "COLUMN_ALIASES",
    "FloodDataset",
    "SchemaValidationError",
    "load_flood_dataset",
    "normalize_flood_dataframe",
    "validate_flood_dataframe",
    "HistoricalSummary",
    "summarize_history",
    "build_map_points",
    "valid_coordinate_mask",
    "Scenario",
    "SimulationOutcome",
    "SimulationParameters",
    "compare_modes",
    "run_parallel",
    "run_serial",
    "run_scenarios",
    "simulate_scenario",
    "JobRecord",
    "JobStore",
    "build_flood_report_pdf",
    "results_to_csv_bytes",
]
