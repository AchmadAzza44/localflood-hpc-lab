# Model Simulasi (SIMULASI DEMONSTRATIF)

Sesuai PRD 2.9, model ini **bukan model hidrologi terverifikasi**. Ia mendefinisikan hubungan eksplisit sederhana antara parameter hujan dan skor skenario, untuk menunjukkan alur komputasi dan pemrosesan paralel.

## Definisi (diverifikasi terhadap `localflood/simulation.py::_ensemble`)
1. **Hujan total** per sampel = hujan skenario x pengali x draw, dengan draw ~ Normal(1, ketidakpastian hujan), dipotong ke [0,05; 3,0].
2. **Hietograf segitiga**: hujan dibagi ke `time_steps` langkah (default 24) dengan bobot segitiga di sekitar tengah rentang aktif; jumlah langkah aktif = durasi skenario (jam).
3. **Reservoir limpasan** per langkah: masuk = hujan langkah x koefisien limpasan; keluar = min(simpanan + masuk, kapasitas drainase / jumlah langkah); simpanan = simpanan + masuk - keluar, lalu berkurang 8% (perkolasi tetap); simpanan awal = kelembapan awal x ambang x 0,5. Dicatat **puncak simpanan** sepanjang langkah.
4. **Skor per sampel** = 100 x (1 - exp(-puncak / ambang)), dibatasi 0-100. **Skor skenario** = rata-rata skor seluruh sampel Monte Carlo; juga dilaporkan P10, P90, peluang skor >= 50, dan beban puncak rata-rata.
5. **Kategori**: Rendah < 25, Sedang < 50, Tinggi < 75, Sangat Tinggi >= 75.

Konstanta tetap (perkolasi 8%, faktor simpanan awal 0,5, distribusi segitiga) adalah pilihan demonstratif, bukan hasil kalibrasi terhadap data.

## Parameter
pengali curah hujan, koefisien limpasan (0-1), kapasitas drainase (mm), kelembapan tanah awal (0-1), ambang (mm), ketidakpastian hujan, sampel Monte Carlo, langkah waktu (1-240). Semua divalidasi; nilai di luar rentang ditolak.

## Reproduksibilitas
Seed skenario = seed dasar + indeks x 101 dan generator `numpy.random.default_rng(seed)` dibuat di dalam setiap skenario, sehingga serial dan paralel menghitung **bilangan acak yang sama** per skenario; hasil identik (selisih maksimum 0 pada seluruh benchmark).

## Yang dibutuhkan untuk prediksi sungguhan (PRD 2.9)
Curah hujan historis dan terkini, tinggi muka air/debit, lokasi dan waktu kejadian banjir, elevasi dan karakter wilayah, serta data validasi. Tidak satu pun dari ini dipakai model ini; karena itu keluarannya tidak boleh disebut prediksi banjir.
