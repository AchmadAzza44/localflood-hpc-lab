"""Tests for historical analysis and geospatial helpers (FR-02, FR-03)."""

from __future__ import annotations

import pandas as pd
import pytest

from localflood.geo import (
    build_map_points,
    haversine_km,
    map_bounds,
    map_center,
    nearest_locations,
    outside_indonesia_count,
    valid_coordinate_mask,
)
from localflood.historical import summarize_history
from localflood.schema import normalize_flood_dataframe, validate_flood_dataframe


@pytest.fixture
def valid_flood(flood_frame):
    normalized, _, _ = normalize_flood_dataframe(flood_frame)
    valid, _ = validate_flood_dataframe(normalized)
    return valid


def test_summarize_history_counts(valid_flood):
    summary = summarize_history(valid_flood)
    assert summary.row_count == len(valid_flood)
    assert summary.flood_row_count == int(valid_flood["banjir"].sum())
    assert summary.flood_rate_pct == pytest.approx(
        summary.flood_row_count / summary.row_count * 100, rel=1e-3
    )


def test_summarize_history_temporal_tables(valid_flood):
    summary = summarize_history(valid_flood)
    assert not summary.monthly_counts.empty
    assert not summary.yearly_counts.empty
    assert summary.date_min is not None
    assert summary.date_max is not None
    assert summary.span_days > 0


def test_summarize_history_rainfall_stats(valid_flood):
    summary = summarize_history(valid_flood)
    stats = summary.rainfall_stats
    assert stats["min"] <= stats["median"] <= stats["max"]
    assert stats["p95"] >= stats["median"]


def test_summarize_history_locations(valid_flood):
    summary = summarize_history(valid_flood)
    assert not summary.top_locations.empty
    assert summary.top_locations["jumlah_kejadian"].sum() == summary.flood_row_count


def test_summarize_history_rejects_empty():
    with pytest.raises(ValueError):
        summarize_history(pd.DataFrame())


def test_summarize_history_warns_short_span():
    frame = pd.DataFrame(
        {
            "tanggal": pd.to_datetime(["2024-01-01", "2024-02-01"]),
            "lokasi": ["A", "A"],
            "curah_hujan_mm": [10.0, 20.0],
            "banjir": [False, True],
        }
    )
    summary = summarize_history(frame)
    assert any("kurang dari satu tahun" in warning for warning in summary.warnings)


def test_valid_coordinate_mask(valid_flood):
    mask = valid_coordinate_mask(valid_flood)
    assert mask.all()


def test_build_map_points(valid_flood):
    points = build_map_points(valid_flood)
    assert len(points) == len(valid_flood)
    assert set(points.columns) >= {"latitude", "longitude", "lokasi", "status", "radius"}
    assert points["status"].isin(["Kejadian banjir", "Tidak banjir", "Tidak diketahui"]).all()


def test_map_center_and_bounds(valid_flood):
    points = build_map_points(valid_flood)
    center = map_center(points)
    bounds = map_bounds(points)
    assert bounds["lat_min"] < center[0] < bounds["lat_max"]
    assert bounds["lon_min"] < center[1] < bounds["lon_max"]


def test_haversine_known_distance():
    distance = haversine_km(-6.2, 106.8, -6.9175, 107.6191)
    assert 110 < distance < 130


def test_nearest_locations(valid_flood):
    nearest = nearest_locations(valid_flood, -6.2, 106.8, limit=3)
    assert len(nearest) == 3
    assert nearest["jarak_km"].is_monotonic_increasing


def test_outside_indonesia_count(valid_flood):
    assert outside_indonesia_count(valid_flood) == 0
    shifted = valid_flood.copy()
    shifted.loc[0, "latitude"] = 40.0
    shifted.loc[0, "longitude"] = -74.0
    assert outside_indonesia_count(shifted) == 1


def test_build_map_points_without_coordinates():
    frame = pd.DataFrame(
        {
            "tanggal": ["2024-01-01"],
            "lokasi": ["A"],
            "curah_hujan_mm": [10.0],
            "banjir": [True],
        }
    )
    points = build_map_points(frame)
    assert points.empty
