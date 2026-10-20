"""Shared pytest fixtures and path setup."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def project_root() -> Path:
    return ROOT


@pytest.fixture
def sales_frame() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    rows = 120
    advertising = rng.uniform(5, 80, rows).round(2)
    price = rng.uniform(8, 35, rows).round(2)
    promotion = rng.choice(["Tidak", "Diskon"], rows, p=[0.6, 0.4])
    sales = 30 + 0.8 * advertising - 0.5 * price + np.where(promotion == "Diskon", 6, 0) + rng.normal(0, 3, rows)
    frame = pd.DataFrame(
        {
            "biaya_iklan": advertising,
            "harga": price,
            "promosi": promotion,
            "penjualan": sales.round(2),
        }
    )
    frame.loc[3, "biaya_iklan"] = np.nan
    frame.loc[5, "promosi"] = np.nan
    return frame


@pytest.fixture
def churn_frame() -> pd.DataFrame:
    rng = np.random.default_rng(11)
    rows = 150
    tenure = rng.integers(1, 60, rows)
    charges = rng.uniform(20, 110, rows)
    contract = rng.choice(["Bulanan", "Tahunan"], rows, p=[0.6, 0.4])
    logit = -0.5 + 0.02 * charges - 0.04 * tenure + np.where(contract == "Bulanan", 0.9, -0.4)
    probability = 1 / (1 + np.exp(-logit))
    churn = np.where(rng.random(rows) < probability, "Ya", "Tidak")
    return pd.DataFrame(
        {
            "masa_berlangganan": tenure,
            "tagihan": charges.round(2),
            "kontrak": contract,
            "churn": churn,
        }
    )


@pytest.fixture
def flood_frame() -> pd.DataFrame:
    rng = np.random.default_rng(3)
    dates = pd.date_range("2021-01-01", periods=48, freq="MS")
    rainfall = rng.uniform(20, 220, len(dates)).round(1)
    return pd.DataFrame(
        {
            "tanggal": dates.strftime("%Y-%m-%d"),
            "lokasi": "Kota Uji",
            "latitude": -6.2,
            "longitude": 106.8,
            "curah_hujan_mm": rainfall,
            "banjir": rainfall > 140,
            "durasi_jam": np.where(rainfall > 140, 6.0, 0.0),
        }
    )


@pytest.fixture
def csv_bytes():
    def _factory(frame: pd.DataFrame) -> bytes:
        return frame.to_csv(index=False).encode("utf-8")

    return _factory
