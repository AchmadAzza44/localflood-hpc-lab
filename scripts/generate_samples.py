"""Generate reproducible sample datasets for LocalFlood (data SINTETIS).

Run from the project root:
    python scripts/generate_samples.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config import SAMPLES_DIR, ensure_runtime_dirs  # noqa: E402

RANDOM_SEED = 2024


def build_flood_history() -> pd.DataFrame:
    rng = np.random.default_rng(RANDOM_SEED + 2)
    rows: list[dict] = []
    dates = pd.date_range("2018-01-01", "2024-12-31", freq="D")
    for location, latitude, longitude in LOCATIONS:
        bias = rng.uniform(0.8, 1.35)
        for date in dates:
            if rng.random() > 0.34:
                continue
            month = date.month
            seasonal = 1.55 if month in (11, 12, 1, 2, 3) else 0.85
            rainfall = max(0.0, rng.gamma(shape=2.1, scale=22.0) * seasonal * bias)
            if rng.random() > 0.72:
                continue
            threshold = rng.uniform(70, 110) * bias
            flooded = rainfall > threshold or (
                rainfall > threshold * 0.75 and rng.random() < 0.18
            )
            rows.append(
                {
                    "tanggal": date.strftime("%Y-%m-%d"),
                    "lokasi": location,
                    "latitude": round(latitude + rng.normal(0, 0.01), 5),
                    "longitude": round(longitude + rng.normal(0, 0.01), 5),
                    "curah_hujan_mm": round(float(rainfall), 1),
                    "banjir": bool(flooded),
                    "durasi_jam": round(float(max(0.5, rng.normal(7, 3))), 1) if flooded else 0.0,
                    "tinggi_muka_air_m": round(float(rng.uniform(0.5, 2.4) + (1.0 if flooded else 0.0)), 2),
                }
            )
    frame = pd.DataFrame(rows).sort_values("tanggal").reset_index(drop=True)

    dirty = frame.sample(6, random_state=RANDOM_SEED).index
    frame.loc[dirty[:2], "curah_hujan_mm"] = np.nan
    frame.loc[dirty[2], "latitude"] = 123.0
    frame.loc[dirty[3], "longitude"] = 250.0
    frame.loc[dirty[4], "tanggal"] = "bukan-tanggal"
    return frame


def main() -> None:
    ensure_runtime_dirs()
    frame = build_flood_history()
    path = SAMPLES_DIR / "flood_history.csv"
    frame.to_csv(path, index=False)
    print(f"{path.relative_to(ROOT)}  ({frame.shape[0]} baris x {frame.shape[1]} kolom)")


if __name__ == "__main__":
    main()
