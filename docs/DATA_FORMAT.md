# Format Data

CSV atau XLSX (maks. 50 MB). Kolom dikenali lewat alias (tidak peka huruf besar/kecil); nama kanonik hasil normalisasi dicetak tebal.

| Kolom kanonik | Wajib | Alias yang dikenali | Aturan validasi |
|---|---|---|---|
| **tanggal** | ya | date, waktu, datetime, time, periode | harus dapat di-parse sebagai tanggal |
| **lokasi** | ya | location, wilayah, kecamatan, site, station, stasiun | tidak kosong |
| **curah_hujan_mm** | ya | curah_hujan, rainfall, rainfall_mm, hujan, precipitation, precip_mm, rr | numerik, tidak negatif; satuan diasumsikan **mm** per periode observasi |
| latitude | tidak | lat, lintang | -90..90 (dan peringatan bila di luar kotak Indonesia) |
| longitude | tidak | lon, lng, bujur | -180..180 |
| banjir | tidak | flooded, flood, kejadian_banjir, flood_event, event | boolean (ya/tidak, true/false, 1/0) |
| durasi_jam | tidak | duration, duration_hours, durasi | numerik, jam |
| tinggi_muka_air_m | tidak | tma, water_level, river_level, debit | numerik, meter |

Baris yang melanggar aturan **tidak dipakai** tetapi **ditampilkan dengan alasan** (`validation_issue`): mis. "latitude di luar -90..90", "curah hujan tidak valid", "tanggal tidak valid". Pengguna melihat jumlah baris valid vs tidak valid, dan SHA-256 dataset dicatat pada setiap pekerjaan.

## `data/samples/flood_history.csv` (SINTETIS)
6.326 baris mentah x 8 kolom; **5 baris sengaja tidak valid** (menguji validasi) -> **6.321 baris valid**; 10 lokasi (kota-kota Indonesia, koordinat sintetis di sekitar kota), 2018-01-01 s.d. 2024-12-31; 1.145 kejadian banjir (18,11%). Dibuat `scripts/generate_samples.py` (seed tetap). Bukan data historis nyata.
