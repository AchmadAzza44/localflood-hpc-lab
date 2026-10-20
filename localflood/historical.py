"""Historical flood analysis (LocalFlood FR-02)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class HistoricalSummary:
    """Aggregated historical statistics about rainfall and flood events."""

    row_count: int
    location_count: int
    date_min: str | None
    date_max: str | None
    span_days: int | None
    flood_event_count: int
    flood_row_count: int
    non_flood_row_count: int
    unknown_event_count: int
    flood_rate_pct: float
    rainfall_stats: dict[str, Any]
    monthly_counts: pd.DataFrame
    yearly_counts: pd.DataFrame
    top_locations: pd.DataFrame
    rainfall_by_event: pd.DataFrame
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "row_count": self.row_count,
            "location_count": self.location_count,
            "date_min": self.date_min,
            "date_max": self.date_max,
            "span_days": self.span_days,
            "flood_event_count": self.flood_event_count,
            "flood_row_count": self.flood_row_count,
            "non_flood_row_count": self.non_flood_row_count,
            "unknown_event_count": self.unknown_event_count,
            "flood_rate_pct": round(self.flood_rate_pct, 2),
            "rainfall_stats": self.rainfall_stats,
            "warnings": self.warnings,
        }


def _rainfall_stats(series: pd.Series) -> dict[str, Any]:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return {}
    return {
        "count": int(clean.count()),
        "mean": float(clean.mean()),
        "median": float(clean.median()),
        "std": float(clean.std()) if clean.count() > 1 else 0.0,
        "min": float(clean.min()),
        "max": float(clean.max()),
        "p90": float(clean.quantile(0.9)),
        "p95": float(clean.quantile(0.95)),
        "p99": float(clean.quantile(0.99)),
    }


def summarize_history(df: pd.DataFrame) -> HistoricalSummary:
    """Summarize historical flood events and rainfall."""
    if df is None or df.empty:
        raise ValueError("Dataset historis kosong.")

    working = df.copy()
    working["tanggal"] = pd.to_datetime(working["tanggal"], errors="coerce")
    working["lokasi"] = working["lokasi"].astype(str)

    events = working["banjir"].fillna(False).astype(bool)
    flood_row_count = int(events.sum())
    unknown_events = int(working["banjir"].isna().sum())
    non_flood = int(len(working) - flood_row_count - unknown_events)

    dates = working["tanggal"].dropna()
    date_min = dates.min().date().isoformat() if not dates.empty else None
    date_max = dates.max().date().isoformat() if not dates.empty else None
    span_days = int((dates.max() - dates.min()).days) if not dates.empty else None

    monthly = pd.DataFrame(columns=["periode", "jumlah_kejadian", "total_observasi"])
    yearly = pd.DataFrame(columns=["tahun", "jumlah_kejadian", "total_observasi"])
    if not dates.empty:
        dated = working.dropna(subset=["tanggal"]).copy()
        dated["periode"] = dated["tanggal"].dt.to_period("M").astype(str)
        dated["tahun"] = dated["tanggal"].dt.year
        dated["kejadian"] = dated["banjir"].fillna(False).astype(bool)
        monthly = (
            dated.groupby("periode")
            .agg(jumlah_kejadian=("kejadian", "sum"), total_observasi=("kejadian", "size"))
            .reset_index()
        )
        monthly["jumlah_kejadian"] = monthly["jumlah_kejadian"].astype(int)
        monthly["total_observasi"] = monthly["total_observasi"].astype(int)
        yearly = (
            dated.groupby("tahun")
            .agg(jumlah_kejadian=("kejadian", "sum"), total_observasi=("kejadian", "size"))
            .reset_index()
        )
        yearly["jumlah_kejadian"] = yearly["jumlah_kejadian"].astype(int)
        yearly["total_observasi"] = yearly["total_observasi"].astype(int)

    location_counts = (
        working.assign(kejadian=events)
        .groupby("lokasi")
        .agg(
            jumlah_kejadian=("kejadian", "sum"),
            total_observasi=("kejadian", "size"),
            curah_hujan_rata_rata=("curah_hujan_mm", "mean"),
        )
        .reset_index()
    )
    location_counts["jumlah_kejadian"] = location_counts["jumlah_kejadian"].astype(int)
    location_counts["total_observasi"] = location_counts["total_observasi"].astype(int)
    location_counts["curah_hujan_rata_rata"] = location_counts["curah_hujan_rata_rata"].round(2)
    location_counts = location_counts.sort_values(
        ["jumlah_kejadian", "total_observasi"], ascending=False
    ).reset_index(drop=True)

    flood_events = working[events & working["tanggal"].notna()]
    flood_event_count = int(
        flood_events[["tanggal", "lokasi"]].drop_duplicates().shape[0]
    ) if not flood_events.empty else 0

    rainfall_by_event = pd.DataFrame(columns=["kategori", "jumlah", "rata_rata", "median", "maksimum"])
    if working["curah_hujan_mm"].notna().any():
        grouped = working.assign(
            kategori=np.where(events, "Banjir", np.where(working["banjir"].isna(), "Tidak diketahui", "Tidak banjir"))
        ).groupby("kategori")["curah_hujan_mm"]
        rainfall_by_event = (
            grouped.agg(jumlah="count", rata_rata="mean", median="median", maksimum="max")
            .reset_index()
            .round(2)
        )

    warnings: list[str] = []
    if unknown_events:
        warnings.append(
            f"{unknown_events} baris tidak memiliki informasi kejadian banjir yang jelas."
        )
    if not dates.empty and span_days is not None and span_days < 365:
        warnings.append("Rentang data historis kurang dari satu tahun; pola musiman belum stabil.")
    if working["banjir"].notna().any() and flood_row_count == 0:
        warnings.append("Tidak ada kejadian banjir tercatat pada dataset ini.")
    if working["curah_hujan_mm"].isna().all():
        warnings.append("Tidak ada nilai curah hujan valid; analisis hujan tidak tersedia.")

    return HistoricalSummary(
        row_count=int(len(working)),
        location_count=int(working["lokasi"].nunique()),
        date_min=date_min,
        date_max=date_max,
        span_days=span_days,
        flood_event_count=flood_event_count,
        flood_row_count=flood_row_count,
        non_flood_row_count=non_flood,
        unknown_event_count=unknown_events,
        flood_rate_pct=(flood_row_count / len(working) * 100) if len(working) else 0.0,
        rainfall_stats=_rainfall_stats(working["curah_hujan_mm"]),
        monthly_counts=monthly,
        yearly_counts=yearly,
        top_locations=location_counts.head(15),
        rainfall_by_event=rainfall_by_event,
        warnings=warnings,
    )
