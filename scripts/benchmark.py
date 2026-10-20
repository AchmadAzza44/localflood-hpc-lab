"""Benchmark serial vs paralel pada beban KERJA SETARA (skenario, parameter, dan seed sama). Cetak tabel Markdown.

Jalankan dari akar proyek: python scripts/benchmark.py
Setiap sel = sekali jalan setelah pemanasan; waktu bervariasi antar mesin dan antar eksekusi.
"""

import os
import platform
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from localflood.simulation import SimulationParameters, compare_modes, generate_scenarios  # noqa: E402

if __name__ == "__main__":
    print(f"Python {platform.python_version()}, CPU logis: {os.cpu_count()}, worker: 4")
    compare_modes(generate_scenarios(60, count=4), SimulationParameters(samples_per_scenario=5000), max_workers=2, executor="thread")  # pemanasan
    print("| Skenario | Sampel/skenario | Executor | Serial (s) | Paralel (s) | Speedup | Hasil identik | Selisih maks |\n|---|---|---|---|---|---|---|---|")
    for count in (8, 32, 64):
        for samples in (2_000, 20_000, 150_000):
            for executor in ("process", "thread"):
                scenarios = generate_scenarios(60, count=count, duration_hours=6)
                params = SimulationParameters(samples_per_scenario=samples)
                r = compare_modes(scenarios, params, max_workers=4, executor=executor)
                print(f"| {count} | {samples:,} | {executor} | {r['serial'].elapsed_seconds:.3f} | {r['parallel'].elapsed_seconds:.3f} | "
                      f"{r['speedup']:.2f}x | {'ya' if r['consistent'] else 'TIDAK'} | {r['max_delta']:.1e} |")
