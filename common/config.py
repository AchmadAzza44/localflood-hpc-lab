"""Konfigurasi dan konstanta LocalFlood HPC Lab."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SAMPLES_DIR = DATA_DIR / "samples"
JOBS_DIR = DATA_DIR / "jobs"
REPORTS_DIR = DATA_DIR / "reports"

ALLOWED_DATA_EXTENSIONS = (".csv", ".xlsx")
MAX_UPLOAD_MB = 50
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

LOCALFLOOD_NAME = "LocalFlood HPC Lab"

DISCLAIMER_FLOOD = (
    "LocalFlood HPC Lab adalah alat pembelajaran dan simulasi demonstratif, bukan sistem "
    "peringatan dini resmi dan bukan model hidrologi terverifikasi. Hasil simulasi tidak "
    "boleh digunakan sebagai satu-satunya dasar keputusan keselamatan."
)


def ensure_runtime_dirs() -> None:
    """Create runtime directories used by the applications."""
    for directory in (DATA_DIR, SAMPLES_DIR, JOBS_DIR, REPORTS_DIR):
        directory.mkdir(parents=True, exist_ok=True)
