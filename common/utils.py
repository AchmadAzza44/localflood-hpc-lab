"""Small, dependency-light helpers shared by both applications."""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd


def utc_now_iso() -> str:
    """Return an ISO-8601 UTC timestamp with second precision."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(payload: bytes) -> str:
    """Return the SHA-256 hex digest of raw bytes."""
    return hashlib.sha256(payload).hexdigest()


def sha256_dataframe(df: pd.DataFrame) -> str:
    """Return a stable SHA-256 digest for a dataframe's content and schema."""
    hashed = pd.util.hash_pandas_object(df, index=True).to_numpy(dtype="uint64")
    digest = hashlib.sha256(hashed.tobytes())
    digest.update("|".join(f"{col}:{dtype}" for col, dtype in df.dtypes.items()).encode("utf-8"))
    digest.update(str(df.shape).encode("utf-8"))
    return digest.hexdigest()


def slugify(value: str, fallback: str = "dataset") -> str:
    """Create a filesystem-friendly slug from a display name."""
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(value).strip()).strip("-._")
    return cleaned[:80] or fallback


def format_bytes(num_bytes: int | float) -> str:
    """Format a byte count using binary units."""
    size = float(max(0.0, num_bytes))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024.0
    return f"{size:.1f} TB"


def safe_json(value: Any, *, indent: int | None = 2) -> str:
    """Serialize a value to JSON, converting numpy/pandas types safely."""
    return json.dumps(
        to_jsonable(value),
        ensure_ascii=False,
        indent=indent,
        allow_nan=False,
    )


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    """Serialize a dataframe to UTF-8 CSV bytes with a BOM for Excel compatibility."""
    return df.to_csv(index=False).encode("utf-8-sig")


def to_jsonable(value: Any) -> Any:
    """Recursively convert a structure into JSON-serializable primitives."""
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        number = float(value)
        return None if not math.isfinite(number) else number
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, np.ndarray):
        return [to_jsonable(item) for item in value.tolist()]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
