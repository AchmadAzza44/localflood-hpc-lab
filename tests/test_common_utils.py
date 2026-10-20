"""Tests for shared utilities."""

from __future__ import annotations

import json
from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from common.utils import (
    dataframe_to_csv_bytes,
    format_bytes,
    safe_json,
    sha256_bytes,
    sha256_dataframe,
    slugify,
    to_jsonable,
    utc_now_iso,
)


def test_sha256_bytes_is_stable():
    assert sha256_bytes(b"abc") == sha256_bytes(b"abc")
    assert sha256_bytes(b"abc") != sha256_bytes(b"abd")
    assert len(sha256_bytes(b"abc")) == 64


def test_sha256_dataframe_changes_with_content():
    first = pd.DataFrame({"a": [1, 2]})
    second = pd.DataFrame({"a": [1, 3]})
    assert sha256_dataframe(first) == sha256_dataframe(first.copy())
    assert sha256_dataframe(first) != sha256_dataframe(second)


def test_slugify():
    assert slugify("My Dataset (2024).csv") == "My-Dataset-2024-.csv"
    assert slugify("") == "dataset"
    assert slugify("***") == "dataset"


def test_format_bytes():
    assert format_bytes(0) == "0 B"
    assert format_bytes(1024) == "1.0 KB"
    assert format_bytes(5 * 1024 * 1024) == "5.0 MB"


def test_utc_now_iso_parses():
    parsed = datetime.fromisoformat(utc_now_iso())
    assert parsed.tzinfo is not None


def test_safe_json_handles_numpy():
    payload = {"int": np.int64(3), "float": np.float64(1.5), "array": np.array([1, 2])}
    text = safe_json(payload)
    assert json.loads(text)["int"] == 3
    assert json.loads(text)["array"] == [1, 2]


def test_safe_json_handles_nan():
    text = safe_json({"value": float("nan")})
    assert json.loads(text)["value"] is None


def test_to_jsonable_nested():
    value = {"a": [np.int64(1), {"b": np.float64(2.5)}], "c": pd.Timestamp("2024-01-01")}
    result = to_jsonable(value)
    assert result["a"][0] == 1
    assert result["a"][1]["b"] == 2.5
    assert result["c"].startswith("2024-01-01")


def test_dataframe_to_csv_bytes_has_bom():
    frame = pd.DataFrame({"a": [1, 2]})
    payload = dataframe_to_csv_bytes(frame)
    assert payload.startswith(b"\xef\xbb\xbf")
    assert b"a" in payload


def test_slugify_preserves_safe_characters():
    assert slugify("report_2024-final.csv") == "report_2024-final.csv"
