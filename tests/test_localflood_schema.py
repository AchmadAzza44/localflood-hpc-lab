"""Tests for flood data import and validation (LocalFlood FR-01)."""

from __future__ import annotations

import io

import numpy as np
import pandas as pd
import pytest

from localflood.schema import (
    SchemaValidationError,
    load_flood_dataset,
    normalize_flood_dataframe,
    validate_flood_dataframe,
)


def test_normalize_recognizes_aliases(flood_frame):
    renamed = flood_frame.rename(
        columns={
            "tanggal": "date",
            "lokasi": "location",
            "curah_hujan_mm": "rainfall",
            "banjir": "flooded",
        }
    )
    normalized, mapping, _ = normalize_flood_dataframe(renamed)
    assert mapping["date"] == "date"
    assert mapping["rainfall"] == "rainfall"
    assert normalized["valid"].all()


def test_missing_required_column_raises():
    frame = pd.DataFrame({"tanggal": ["2024-01-01"], "curah_hujan_mm": [10.0]})
    with pytest.raises(SchemaValidationError, match="Kolom wajib"):
        normalize_flood_dataframe(frame)


def test_invalid_rows_are_flagged():
    frame = pd.DataFrame(
        {
            "tanggal": ["2024-01-01", "bukan-tanggal", "2024-02-01"],
            "lokasi": ["A", "B", "C"],
            "curah_hujan_mm": [10.0, -5.0, 20.0],
        }
    )
    normalized, _, _ = normalize_flood_dataframe(frame)
    assert normalized["valid"].tolist() == [True, False, True]
    assert "tanggal tidak valid" in normalized.loc[1, "validation_issue"]
    assert "curah hujan negatif" in normalized.loc[1, "validation_issue"]


def test_invalid_coordinates_flagged():
    frame = pd.DataFrame(
        {
            "tanggal": ["2024-01-01"],
            "lokasi": ["A"],
            "curah_hujan_mm": [10.0],
            "latitude": [120.0],
            "longitude": [200.0],
        }
    )
    normalized, _, _ = normalize_flood_dataframe(frame)
    assert not normalized["valid"].iloc[0]
    assert "latitude" in normalized["validation_issue"].iloc[0]


def test_boolean_parsing_variants():
    frame = pd.DataFrame(
        {
            "tanggal": ["2024-01-01"] * 4,
            "lokasi": ["A"] * 4,
            "curah_hujan_mm": [10.0] * 4,
            "banjir": ["ya", "tidak", "1", "0"],
        }
    )
    normalized, _, _ = normalize_flood_dataframe(frame)
    assert normalized["banjir"].tolist() == [True, False, True, False]


def test_validate_split(flood_frame):
    normalized, _, _ = normalize_flood_dataframe(flood_frame)
    valid, invalid = validate_flood_dataframe(normalized)
    assert len(valid) + len(invalid) == len(flood_frame)
    assert "validation_issue" not in valid.columns


def test_load_flood_dataset_returns_metadata(flood_frame):
    payload = flood_frame.to_csv(index=False).encode("utf-8")
    dataset = load_flood_dataset("flood.csv", payload)
    assert dataset.valid_row_count == len(flood_frame)
    assert len(dataset.sha256) == 64
    metadata = dataset.to_metadata()
    assert metadata["rows"] == len(flood_frame)


def test_load_flood_dataset_rejects_unsupported_format():
    with pytest.raises(SchemaValidationError, match="tidak didukung"):
        load_flood_dataset("flood.txt", b"data")


def test_load_flood_dataset_rejects_all_invalid():
    frame = pd.DataFrame({"tanggal": ["x"], "lokasi": ["A"], "curah_hujan_mm": ["?"]})
    with pytest.raises(SchemaValidationError, match="Tidak ada baris valid"):
        load_flood_dataset("bad.csv", frame.to_csv(index=False).encode("utf-8"))


def test_load_flood_dataset_xlsx(flood_frame):
    buffer = io.BytesIO()
    flood_frame.to_excel(buffer, index=False, engine="openpyxl")
    dataset = load_flood_dataset("flood.xlsx", buffer.getvalue())
    assert dataset.valid_row_count == len(flood_frame)


def test_warns_on_extreme_rainfall():
    frame = pd.DataFrame(
        {
            "tanggal": ["2024-01-01"],
            "lokasi": ["A"],
            "curah_hujan_mm": [1500.0],
        }
    )
    normalized, _, warnings = normalize_flood_dataframe(frame)
    assert any("1000" in warning for warning in warnings)
    assert not normalized["valid"].iloc[0]


def test_units_warning_for_tiny_rainfall():
    frame = pd.DataFrame(
        {
            "tanggal": ["2024-01-01"] * 3,
            "lokasi": ["A"] * 3,
            "curah_hujan_mm": [1.0, 2.0, 3.0],
        }
    )
    _, _, warnings = normalize_flood_dataframe(frame)
    assert any("satuan" in warning for warning in warnings)
