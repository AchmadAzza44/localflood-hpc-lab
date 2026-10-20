# Laporan Singkat - LocalFlood HPC Lab
**Materi kuliah:** Bridging Global Infrastructure to Address Local Challenge in HPC. PRD: bagian II.

## Hubungan fitur dengan materi
| Konsep materi | Implementasi | Bukti |
|---|---|---|
| Menghubungkan infrastruktur komputasi dengan masalah lokal | alur masalah banjir -> data -> simulasi -> hasil/laporan | screenshot 01-05 |
| Workflow dari input sampai output | `JobStore` mencatat dataset+hash, parameter, metode, waktu, status, hasil | `test_localflood_workflow.py` |
| Pemrosesan paralel dan pengukuran performa | serial vs paralel (process/thread) pada beban setara | `docs/BENCHMARK.md` |
| Jalur menuju HPC | pemisahan UI/data/simulasi/eksekusi; skenario independen mudah didistribusikan; catatan job dapat dipindah | `ARCHITECTURE.md` |
| Kolaborasi ahli komputasi-ahli domain | model dan keterbatasannya didokumentasikan agar ahli hidrologi dapat menilai/menggantinya | `MODEL_SIMULASI.md` |

## Hasil nyata
- 60 tes lulus. Benchmark 18 kondisi pada 4 inti: **beban kecil lebih lambat saat paralel (0,16-0,83x), beban besar 2,9-3,4x**, hasil identik di semua kondisi.
- Alur di browser: 6.321 baris valid dari 6.326 (5 ditandai dengan alasan); simulasi 64 skenario, speedup 1,85x, konsisten.
- Tiga perbaikan: navigasi kembali ke awal setelah simulasi, tile peta tanpa API key, batas unggah yang menyesatkan.

## Keterbatasan
Data sintetis; model demonstratif tanpa validasi hidrologi (bukan prediksi/peringatan banjir); benchmark pada satu mesin 4 inti; belum diuji di server/HPC, tanpa antrean pekerjaan atau GPU.

## Demonstrasi
`python -m streamlit run app.py` -> Import (`flood_history.csv`) -> Historis -> Peta -> Simulasi (Bandingkan keduanya) -> Workflow -> unduh CSV/PDF.
