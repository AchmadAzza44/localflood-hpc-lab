"""Geographic helpers for LocalFlood (FR-03).

GeoPandas is optional in this MVP. When available it is used for distance-based
spatial summaries; the map itself uses Folium or PyDeck through Streamlit.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

INDONESIA_BOUNDS = {"lat_min": -11.5, "lat_max": 6.5, "lon_min": 94.0, "lon_max": 141.5}


def valid_coordinate_mask(df: pd.DataFrame) -> pd.Series:
    """Boolean mask for rows with plausible coordinates."""
    if "latitude" not in df.columns or "longitude" not in df.columns:
        return pd.Series(False, index=df.index)
    latitude = pd.to_numeric(df["latitude"], errors="coerce")
    longitude = pd.to_numeric(df["longitude"], errors="coerce")
    mask = latitude.notna() & longitude.notna()
    mask &= latitude.between(-90, 90) & longitude.between(-180, 180)
    return mask


def outside_indonesia_count(df: pd.DataFrame) -> int:
    """Count valid coordinates that fall outside the Indonesian bounding box."""
    mask = valid_coordinate_mask(df)
    if not mask.any():
        return 0
    subset = df[mask]
    outside = ~(
        subset["latitude"].between(INDONESIA_BOUNDS["lat_min"], INDONESIA_BOUNDS["lat_max"])
        & subset["longitude"].between(INDONESIA_BOUNDS["lon_min"], INDONESIA_BOUNDS["lon_max"])
    )
    return int(outside.sum())


def build_map_points(df: pd.DataFrame) -> pd.DataFrame:
    """Return map-ready points with flood severity labels."""
    mask = valid_coordinate_mask(df)
    if not mask.any():
        return pd.DataFrame(
            columns=[
                "latitude",
                "longitude",
                "lokasi",
                "tanggal",
                "curah_hujan_mm",
                "banjir",
                "status",
                "radius",
            ]
        )

    points = df[mask].copy()
    points["tanggal"] = pd.to_datetime(points["tanggal"], errors="coerce")
    events = points["banjir"].fillna(False).astype(bool)
    points["status"] = np.where(
        events, "Kejadian banjir", np.where(points["banjir"].isna(), "Tidak diketahui", "Tidak banjir")
    )
    rainfall = pd.to_numeric(points["curah_hujan_mm"], errors="coerce").fillna(0.0)
    points["radius"] = (rainfall.clip(lower=0, upper=300) / 6 + 4).round(1)
    points["tanggal"] = points["tanggal"].dt.strftime("%Y-%m-%d").fillna("")
    return points[
        ["latitude", "longitude", "lokasi", "tanggal", "curah_hujan_mm", "banjir", "status", "radius"]
    ].reset_index(drop=True)


def map_center(points: pd.DataFrame) -> tuple[float, float]:
    """Compute a sensible map center from the available points."""
    if points is None or points.empty:
        return (-2.5, 118.0)
    return (float(points["latitude"].mean()), float(points["longitude"].mean()))


def map_bounds(points: pd.DataFrame) -> dict[str, float]:
    """Compute map bounds with padding."""
    if points is None or points.empty:
        return {
            "lat_min": INDONESIA_BOUNDS["lat_min"],
            "lat_max": INDONESIA_BOUNDS["lat_max"],
            "lon_min": INDONESIA_BOUNDS["lon_min"],
            "lon_max": INDONESIA_BOUNDS["lon_max"],
        }
    lat_pad = max(0.5, (points["latitude"].max() - points["latitude"].min()) * 0.15)
    lon_pad = max(0.5, (points["longitude"].max() - points["longitude"].min()) * 0.15)
    return {
        "lat_min": float(points["latitude"].min() - lat_pad),
        "lat_max": float(points["latitude"].max() + lat_pad),
        "lon_min": float(points["longitude"].min() - lon_pad),
        "lon_max": float(points["longitude"].max() + lon_pad),
    }


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two coordinates in kilometers."""
    radius = 6371.0088
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    delta_phi = np.radians(lat2 - lat1)
    delta_lambda = np.radians(lon2 - lon1)
    a = np.sin(delta_phi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(delta_lambda / 2) ** 2
    return float(2 * radius * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0))))


def nearest_locations(
    df: pd.DataFrame, latitude: float, longitude: float, limit: int = 5
) -> pd.DataFrame:
    """Find the closest observations to a coordinate using haversine distance."""
    mask = valid_coordinate_mask(df)
    if not mask.any():
        return pd.DataFrame(columns=["lokasi", "jarak_km", "curah_hujan_mm", "banjir"])
    subset = df[mask].copy()
    subset["jarak_km"] = [
        haversine_km(latitude, longitude, lat, lon)
        for lat, lon in zip(subset["latitude"], subset["longitude"])
    ]
    subset = subset.sort_values("jarak_km").head(limit)
    columns = [col for col in ("lokasi", "jarak_km", "curah_hujan_mm", "banjir", "tanggal") if col in subset.columns]
    return subset[columns].reset_index(drop=True)


def geodataframe_available() -> bool:
    """Report whether GeoPandas is importable in the current environment."""
    try:
        import geopandas  # noqa: F401

        return True
    except ImportError:
        return False


def points_to_geodataframe(points: pd.DataFrame) -> Any | None:
    """Convert map points into a GeoDataFrame when GeoPandas is installed."""
    try:
        import geopandas as gpd
        from shapely.geometry import Point
    except ImportError:
        return None
    if points is None or points.empty:
        return None
    geometry = [Point(lon, lat) for lon, lat in zip(points["longitude"], points["latitude"])]
    return gpd.GeoDataFrame(points.copy(), geometry=geometry, crs="EPSG:4326")
