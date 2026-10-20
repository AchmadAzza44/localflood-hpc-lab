# Test Plan
`python -m pytest -q` -> **60 lulus** (Python 3.13, pandas 3.0.5, Streamlit 1.66).
| Area | Yang diuji | Berkas |
|---|---|---|
| Validasi | alias kolom, kolom wajib hilang, koordinat/tanggal/hujan tidak valid ditandai dengan alasan, format dan ukuran | test_localflood_schema.py |
| Historis | jumlah kejadian, laju, distribusi waktu, kasus tanpa kolom opsional | test_localflood_history.py |
| Simulasi | parameter di luar rentang ditolak; determinisme per seed; serial = paralel (process dan thread); urutan hasil; kategori risiko | test_localflood_simulation.py |
| Workflow | pencatatan job, status, galat, pemuatan ulang, reproduksibilitas | test_localflood_workflow.py |
| UI | 5 langkah tampil; dataset contoh dimuat; **langkah aktif dipertahankan setelah simulasi** (regresi) | test_ui_smoke.py |

## Verifikasi di browser (Playwright/Chromium)
Muat `flood_history.csv` (6.321 valid) -> peta -> simulasi "Bandingkan keduanya" (64 skenario x 150.000 sampel, 4 worker): **speedup 1,85x, konsisten: ya, selisih maks 0** -> tab Workflow menampilkan pekerjaan dengan SHA-256 dataset. Tidak ada galat aplikasi; galat `L/$ is not defined` pada konsol berasal dari CDN Leaflet/jQuery yang diblokir sandbox dan diganti salinan lokal hanya untuk screenshot.

## Temuan yang diperbaiki
- Setelah simulasi, antarmuka kembali ke tab pertama (`st.tabs` tidak menyimpan pilihan) -> diganti navigasi radio.
- Tile peta "CartoDB positron" kini memerlukan API key -> OpenStreetMap.
- Uploader menampilkan batas 200 MB padahal aplikasi membatasi 50 MB -> `.streamlit/config.toml`.
Belum diuji: eksekusi di server/HPC, uji pengguna, keandalan banyak pekerjaan bersamaan.
