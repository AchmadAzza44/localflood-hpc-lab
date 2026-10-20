# Benchmark Serial vs Paralel

`python scripts/benchmark.py` (Python 3.13.16, CPU logis 4, 4 worker). Beban kerja **setara**: skenario, parameter, dan seed yang sama untuk serial dan paralel; satu pemanasan; tiap sel sekali jalan (variasi antar eksekusi ada).

| Skenario | Sampel/skenario | Executor | Serial (s) | Paralel (s) | Speedup | Hasil identik | Selisih maks |
|---|---|---|---|---|---|---|---|
| 8 | 2.000 | process | 0,007 | 0,029 | 0,23x | ya | 0 |
| 8 | 2.000 | thread | 0,009 | 0,046 | 0,20x | ya | 0 |
| 8 | 20.000 | process | 0,073 | 0,059 | 1,24x | ya | 0 |
| 8 | 20.000 | thread | 0,085 | 0,072 | 1,18x | ya | 0 |
| 8 | 150.000 | process | 0,838 | 0,422 | 1,99x | ya | 0 |
| 8 | 150.000 | thread | 0,721 | 0,228 | 3,17x | ya | 0 |
| 32 | 2.000 | process | 0,038 | 0,060 | 0,64x | ya | 0 |
| 32 | 2.000 | thread | 0,038 | 0,180 | 0,21x | ya | 0 |
| 32 | 20.000 | process | 0,281 | 0,136 | 2,07x | ya | 0 |
| 32 | 20.000 | thread | 0,231 | 0,224 | 1,03x | ya | 0 |
| 32 | 150.000 | process | 2,831 | 0,973 | 2,91x | ya | 0 |
| 32 | 150.000 | thread | 2,460 | 0,771 | 3,19x | ya | 0 |
| 64 | 2.000 | process | 0,068 | 0,081 | 0,83x | ya | 0 |
| 64 | 2.000 | thread | 0,059 | 0,366 | 0,16x | ya | 0 |
| 64 | 20.000 | process | 0,510 | 0,180 | 2,84x | ya | 0 |
| 64 | 20.000 | thread | 0,511 | 0,385 | 1,33x | ya | 0 |
| 64 | 150.000 | process | 5,323 | 1,652 | 3,22x | ya | 0 |
| 64 | 150.000 | thread | 4,930 | 1,446 | 3,41x | ya | 0 |

## Pembacaan yang didukung angka
- **Beban kecil lebih lambat saat paralel** (0,16-0,83x pada 2.000 sampel): overhead start-up dan koordinasi melebihi kerja yang dibagi. Ini yang PRD peringatkan.
- Beban besar (150.000 sampel, >=32 skenario) mencapai **2,9-3,4x pada 4 inti** (maksimum teoretis 4x); skala tidak linear.
- Thread kompetitif untuk beban NumPy karena NumPy melepas GIL pada operasi besar; pada beban sangat kecil thread bisa paling lambat.
- Hasil serial dan paralel **identik** di semua 18 kondisi.
**Batas:** satu mesin 4 inti, sekali jalan per sel; belum diuji pada server/HPC, antrean pekerjaan, atau GPU (Tahap 3 PRD).
