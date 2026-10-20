# LocalFlood HPC Lab

Sistem analisis dan simulasi risiko banjir berbasis data (Streamlit). Materi kuliah: **Bridging Global Infrastructure to Address Local Challenge in HPC**. PRD: bagian II dokumen "Implementasi Dua Materi Kuliah Praktisi Informatika".

> **Batasan penting:** alat pembelajaran dan simulasi **demonstratif**. Bukan sistem peringatan dini resmi, bukan model hidrologi terverifikasi. Hasil simulasi bukan prediksi kejadian banjir; dataset contoh adalah data SINTETIS.


## Struktur folder
```text
app.py                # titik masuk Streamlit
localflood/           # logika inti: schema, historical, geo, simulation, workflow, reporting
ui/                   # tampilan 5 langkah (localflood_app.py) + gaya bersama
common/               # konfigurasi dan utilitas
data/samples/         # flood_history.csv (SINTETIS); data/jobs/ = catatan pekerjaan saat runtime (tidak di-commit)
scripts/              # generate_samples.py, benchmark.py (serial vs paralel)
tests/                # 60 tes pytest
docs/                 # DATA_FORMAT, MODEL_SIMULASI, BENCHMARK, ARCHITECTURE, TEST_PLAN, PROGRESS, LAPORAN, screenshots/
requirements-optional.txt  # GeoPandas/Shapely (opsional)
```

## Menjalankan
```bash
pip install -r requirements.txt          # opsional: pip install -r requirements-optional.txt (GeoPandas)
python -m streamlit run app.py
python -m pytest -q                      # 60 tes
python scripts/benchmark.py              # ukur serial vs paralel pada beban setara
python scripts/generate_samples.py       # buat ulang flood_history.csv (SINTETIS, seed tetap)
```

## Dokumen
`docs/DATA_FORMAT.md` - `docs/MODEL_SIMULASI.md` - `docs/BENCHMARK.md` - `docs/ARCHITECTURE.md` - `docs/TEST_PLAN.md` - `docs/PROGRESS.md` - `docs/LAPORAN.md` - `docs/screenshots/`.
