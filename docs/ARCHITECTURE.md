# Arsitektur
```text
app.py (Streamlit) -> ui/localflood_app.py (5 langkah)
   schema -> historical -> geo -> simulation (serial | paralel) -> workflow (JobStore, JSON) -> reporting (CSV/JSON/PDF)
```
| Modul | Tanggung jawab |
|---|---|
| schema | baca CSV/XLSX, alias kolom, validasi (tanggal, koordinat, hujan, satuan), diagnosis per baris |
| historical | ringkasan kejadian, distribusi waktu, statistik hujan |
| geo | titik peta valid, pusat/batas, haversine; GeoPandas opsional |
| simulation | `SimulationParameters`, `Scenario`, `run_serial`, `run_parallel`, `compare_modes`; seed per skenario |
| workflow | `JobStore`: catatan pekerjaan JSON di `data/jobs/` (dataset+hash, parameter, metode, waktu, status, hasil, galat) |
| reporting | CSV hasil, PDF laporan (parameter, hasil, waktu, keterbatasan) |

Pemisahan antarmuka/data/simulasi/eksekusi memudahkan pemindahan `run_parallel` ke antrean pekerjaan atau HPC kelak. Navigasi memakai radio (bukan `st.tabs`) agar langkah aktif tidak kembali ke awal setelah simulasi selesai; dilindungi tes regresi.
