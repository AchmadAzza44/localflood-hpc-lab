"""Flood dataset import and validation (LocalFlood FR-01).

The canonical schema is deliberately small so that historical datasets from
different sources can be mapped with column aliases. Invalid rows are flagged
with explicit reasons rather than silently discarded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from common.config import ALLOWED_DATA_EXTENSIONS, MAX_UPLOAD_BYTES, MAX_UPLOAD_MB
from common.utils import sha256_bytes

CANONICAL_COLUMNS = {
    "date": "tanggal",
    "location": "lokasi",
    "latitude": "latitude",
    "longitude": "longitude",
    "rainfall": "curah_hujan_mm",
    "flooded": "banjir",
    "duration": "durasi_jam",
    "river_level": "tinggi_muka_air_m",
}

COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "date": ("tanggal", "date", "waktu", "datetime", "time", "periode"),
    "location": ("lokasi", "location", "wilayah", "kecamatan", "site", "station", "stasiun"),
    "latitude": ("latitude", "lat", "lintang"),
    "longitude": ("longitude", "lon", "lng", "bujur"),
    "rainfall": (
        "curah_hujan_mm",
        "curah_hujan",
        "rainfall",
        "rainfall_mm",
        "hujan",
        "precipitation",
        "precip_mm",
        "rr",
    ),
    "flooded": ("banjir", "flooded", "flood", "kejadian_banjir", "flood_event", "event"),
    "duration": ("durasi_jam", "duration", "duration_hours", "durasi"),
    "river_level": (
        "tinggi_muka_air_m",
        "tinggi_muka_air",
        "river_level",
        "water_level",
        "tma",
        "debit",
    ),
}

REQUIRED_FIELDS = ("date", "location", "rainfall")
UNIT_HINTS = {
    "rainfall": "Curah hujan diasumsikan dalam milimeter (mm) per periode observasi.",
    "duration": "Durasi diasumsikan dalam jam.",
    "river_level": "Tinggi muka air diasumsikan dalam meter (m).",
    "latitude": "Latitude harus berada pada rentang -90 s.d. 90 derajat.",
    "longitude": "Longitude harus berada pada rentang -180 s.d. 180 derajat.",
}


class SchemaValidationError(ValueError):
    """Raised when a flood dataset cannot be normalized."""


@dataclass
class FloodDataset:
    """Normalized flood dataset with validation diagnostics."""

    name: str
    dataframe: pd.DataFrame
    sha256: str
    size_bytes: int
    original_columns: list[str]
    mapping: dict[str, str]
    invalid_rows: pd.DataFrame = field(default_factory=pd.DataFrame)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def valid(self) -> pd.DataFrame:
        return self.dataframe

    @property
    def valid_row_count(self) -> int:
        return int(self.dataframe.shape[0])

    @property
    def invalid_row_count(self) -> int:
        return int(self.invalid_rows.shape[0])

    def to_metadata(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "rows": self.valid_row_count,
            "invalid_rows": self.invalid_row_count,
            "mapping": self.mapping,
            "warnings": self.warnings,
            "errors": self.errors,
        }


def _normalize_key(value: str) -> str:
    return (
        str(value)
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace(".", "_")
        .replace("(", "")
        .replace(")", "")
        .replace("%", "persen")
    )


def _detect_mapping(columns: list[str]) -> tuple[dict[str, str], list[str]]:
    mapping: dict[str, str] = {}
    normalized = {_normalize_key(col): col for col in columns}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            key = _normalize_key(alias)
            if key in normalized:
                mapping[canonical] = normalized[key]
                break
    missing = [field for field in REQUIRED_FIELDS if field not in mapping]
    return mapping, missing


def _parse_boolean(value: Any) -> Any:
    if pd.isna(value):
        return np.nan
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "ya", "yes", "y", "banjir", "flood", "terjadi"}:
        return True
    if text in {"0", "false", "tidak", "no", "n", "tidak_banjir", "no_flood", "tidak terjadi"}:
        return False
    return np.nan


def _read_bytes(name: str, payload: bytes) -> pd.DataFrame:
    extension = Path(name).suffix.lower()
    if extension not in ALLOWED_DATA_EXTENSIONS:
        raise SchemaValidationError(
            "Format file tidak didukung. Gunakan CSV atau XLSX."
        )
    if not payload:
        raise SchemaValidationError("File kosong. Unggah file yang memiliki data.")
    if len(payload) > MAX_UPLOAD_BYTES:
        raise SchemaValidationError(
            f"Ukuran file melebihi batas {MAX_UPLOAD_MB} MB."
        )
    import io

    if extension == ".csv":
        try:
            frame = pd.read_csv(io.BytesIO(payload), encoding="utf-8-sig")
        except UnicodeDecodeError:
            frame = pd.read_csv(io.BytesIO(payload), encoding="latin-1")
        except pd.errors.EmptyDataError as exc:
            raise SchemaValidationError("File CSV tidak berisi data.") from exc
        except pd.errors.ParserError as exc:
            raise SchemaValidationError(
                "Struktur CSV tidak valid. Periksa jumlah kolom pada setiap baris."
            ) from exc
    else:
        try:
            frame = pd.read_excel(io.BytesIO(payload), engine="openpyxl")
        except Exception as exc:
            raise SchemaValidationError("File Excel tidak dapat dibaca.") from exc
    if frame.empty:
        raise SchemaValidationError("Dataset tidak memiliki baris data.")
    frame.columns = [str(col).strip() for col in frame.columns]
    return frame


def normalize_flood_dataframe(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str], list[str]]:
    """Normalize a raw frame into the canonical schema.

    Returns (normalized_frame, column_mapping, warnings). Rows that cannot be
    validated are retained in the normalized frame with a `validation_issue`
    column so the caller can separate them explicitly.
    """
    mapping, missing = _detect_mapping(list(frame.columns))
    if missing:
        readable = ", ".join(CANONICAL_COLUMNS[field] for field in missing)
        raise SchemaValidationError(
            f"Kolom wajib tidak ditemukan: {readable}. "
            f"Kolom yang tersedia: {', '.join(map(str, frame.columns))}."
        )

    warnings: list[str] = []
    working = pd.DataFrame(index=frame.index)

    dates = pd.to_datetime(frame[mapping["date"]], errors="coerce")
    working["tanggal"] = dates
    working["lokasi"] = frame[mapping["location"]].astype(str).str.strip()

    rainfall = pd.to_numeric(frame[mapping["rainfall"]], errors="coerce")
    working["curah_hujan_mm"] = rainfall

    if "latitude" in mapping:
        working["latitude"] = pd.to_numeric(frame[mapping["latitude"]], errors="coerce")
    else:
        working["latitude"] = np.nan
        warnings.append("Kolom latitude tidak ditemukan; peta tidak dapat menampilkan titik.")

    if "longitude" in mapping:
        working["longitude"] = pd.to_numeric(frame[mapping["longitude"]], errors="coerce")
    else:
        working["longitude"] = np.nan
        warnings.append("Kolom longitude tidak ditemukan; peta tidak dapat menampilkan titik.")

    if "flooded" in mapping:
        working["banjir"] = frame[mapping["flooded"]].map(_parse_boolean)
    else:
        working["banjir"] = np.nan
        warnings.append("Kolom kejadian banjir tidak ditemukan; analisis frekuensi dibatasi.")

    if "duration" in mapping:
        working["durasi_jam"] = pd.to_numeric(frame[mapping["duration"]], errors="coerce")
    else:
        working["durasi_jam"] = np.nan

    if "river_level" in mapping:
        working["tinggi_muka_air_m"] = pd.to_numeric(frame[mapping["river_level"]], errors="coerce")
    else:
        working["tinggi_muka_air_m"] = np.nan

    issues: list[str] = []
    issue_frame = pd.DataFrame(index=frame.index)
    issue_frame["tanggal_tidak_valid"] = working["tanggal"].isna()
    issue_frame["lokasi_kosong"] = working["lokasi"].isin(["", "nan", "None"])
    issue_frame["curah_hujan_tidak_valid"] = working["curah_hujan_mm"].isna()
    issue_frame["curah_hujan_negatif"] = working["curah_hujan_mm"] < 0
    issue_frame["curah_hujan_ekstrem"] = working["curah_hujan_mm"] > 1000
    issue_frame["latitude_tidak_valid"] = ~working["latitude"].between(-90, 90) & working["latitude"].notna()
    issue_frame["longitude_tidak_valid"] = ~working["longitude"].between(-180, 180) & working["longitude"].notna()
    issue_frame["durasi_tidak_valid"] = working["durasi_jam"] < 0

    def _issue_text(row: pd.Series) -> str:
        labels = {
            "tanggal_tidak_valid": "tanggal tidak valid",
            "lokasi_kosong": "lokasi kosong",
            "curah_hujan_tidak_valid": "curah hujan tidak valid",
            "curah_hujan_negatif": "curah hujan negatif",
            "curah_hujan_ekstrem": "curah hujan > 1000 mm (periksa satuan)",
            "latitude_tidak_valid": "latitude di luar -90..90",
            "longitude_tidak_valid": "longitude di luar -180..180",
            "durasi_tidak_valid": "durasi negatif",
        }
        return "; ".join(label for key, label in labels.items() if bool(row[key]))

    working["validation_issue"] = issue_frame.apply(_issue_text, axis=1)

    coordinate_pairs = working["latitude"].notna() & working["longitude"].notna()
    if coordinate_pairs.any() and not working.loc[coordinate_pairs, "latitude"].between(-90, 90).all():
        warnings.append("Terdapat koordinat latitude di luar rentang yang valid.")
    if coordinate_pairs.any() and not working.loc[coordinate_pairs, "longitude"].between(-180, 180).all():
        warnings.append("Terdapat koordinat longitude di luar rentang yang valid.")

    if rainfall.notna().any() and rainfall.max() > 1000:
        warnings.append(
            "Curah hujan maksimum melebihi 1000 mm per periode; periksa satuan data "
            "(mm vs cm atau akumulasi tahunan)."
        )
    if rainfall.notna().any() and rainfall.max() <= 20:
        warnings.append(
            "Nilai curah hujan maksimum sangat kecil; pastikan satuan yang digunakan adalah milimeter."
        )

    working = working.reset_index(drop=True)
    working["valid"] = working["validation_issue"].eq("")
    return working, mapping, warnings


def validate_flood_dataframe(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split a normalized frame into valid and invalid rows."""
    if "valid" not in frame.columns:
        raise SchemaValidationError("Dataframe belum dinormalisasi.")
    valid = frame[frame["valid"]].drop(columns=["valid", "validation_issue"]).reset_index(drop=True)
    invalid = frame[~frame["valid"]].reset_index(drop=True)
    return valid, invalid


def load_flood_dataset(name: str, payload: bytes) -> FloodDataset:
    """Load, normalize, and validate an uploaded flood dataset."""
    raw = _read_bytes(name, payload)
    normalized, mapping, warnings = normalize_flood_dataframe(raw)
    valid, invalid = validate_flood_dataframe(normalized)
    if valid.empty:
        raise SchemaValidationError(
            "Tidak ada baris valid setelah validasi. Periksa format tanggal, lokasi, "
            "dan curah hujan pada dataset."
        )
    errors: list[str] = []
    if not invalid.empty:
        errors.append(
            f"{len(invalid)} baris ditandai tidak valid dan dikeluarkan dari analisis."
        )
    return FloodDataset(
        name=name,
        dataframe=valid,
        sha256=sha256_bytes(payload),
        size_bytes=len(payload),
        original_columns=list(raw.columns),
        mapping=mapping,
        invalid_rows=invalid,
        warnings=warnings,
        errors=errors,
    )


def load_flood_dataset_from_path(path: str | Path) -> FloodDataset:
    path = Path(path)
    return load_flood_dataset(path.name, path.read_bytes())
