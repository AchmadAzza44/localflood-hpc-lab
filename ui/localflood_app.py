"""Streamlit interface for LocalFlood HPC Lab."""

from __future__ import annotations

import time

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

from common.config import DISCLAIMER_FLOOD, LOCALFLOOD_NAME, MAX_UPLOAD_MB
from common.utils import safe_json
from localflood.geo import (
    build_map_points,
    geodataframe_available,
    map_bounds,
    map_center,
    outside_indonesia_count,
)
from localflood.historical import summarize_history
from localflood.reporting import build_flood_report_pdf, results_to_csv_bytes
from localflood.schema import (
    CANONICAL_COLUMNS,
    COLUMN_ALIASES,
    SchemaValidationError,
    load_flood_dataset,
)
from localflood.simulation import (
    MODEL_DESCRIPTION,
    SimulationParameters,
    compare_modes,
    generate_scenarios,
    run_scenarios,
)
from localflood.workflow import JobStore
from ui.shared import (
    download_row,
    format_number,
    hero,
    metric_card,
    notice,
    sample_files,
    show_json,
    step_label,
)

KEYS = {
    "dataset": "lf_dataset",
    "comparison": "lf_comparison",
    "job": "lf_job",
    "report": "lf_report",
}


def _reset_state() -> None:
    for key in KEYS.values():
        st.session_state.pop(key, None)


def _job_store() -> JobStore:
    return JobStore()


def _render_upload() -> None:
    step_label("Langkah 1")
    st.subheader("Impor dan validasi data")
    st.caption(
        f"Unggah CSV/XLSX dengan kolom tanggal, lokasi, dan curah hujan. "
        f"Ukuran maksimum {MAX_UPLOAD_MB} MB. Data tidak dikirim ke layanan eksternal."
    )

    with st.expander("Format kolom yang didukung", expanded=False):
        st.markdown(
            "- **Wajib**: `tanggal`, `lokasi`, `curah_hujan_mm`\n"
            "- **Opsional**: `latitude`, `longitude`, `banjir`, `durasi_jam`, `tinggi_muka_air_m`\n"
            "- Alias seperti `date`, `rainfall`, `flooded`, `lat`, `lon` juga dikenali.\n"
            "- Satuan diasumsikan: curah hujan **mm**, durasi **jam**, tinggi muka air **meter**."
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {"kolom": CANONICAL_COLUMNS[key], "alias": ", ".join(aliases)}
                    for key, aliases in COLUMN_ALIASES.items()
                ]
            ),
            width="stretch",
            hide_index=True,
        )

    uploaded = st.file_uploader(
        "Pilih file data banjir",
        type=["csv", "xlsx"],
        key="lf_uploader",
    )
    samples = [path for path in sample_files() if path.name == "flood_history.csv"]
    sample_choice = st.selectbox(
        "Atau gunakan dataset contoh",
        options=["(tidak menggunakan contoh)"] + [path.name for path in samples],
        key="lf_sample_choice",
    )

    col_a, col_b = st.columns([1, 3])
    with col_a:
        load_clicked = st.button("Muat dan validasi", type="primary", width="stretch")
    with col_b:
        if st.button("Bersihkan sesi", key="lf_reset"):
            _reset_state()
            st.rerun()

    if not load_clicked:
        return

    try:
        if uploaded is not None:
            dataset = load_flood_dataset(uploaded.name, uploaded.getvalue())
        elif sample_choice != "(tidak menggunakan contoh)":
            path = next(path for path in samples if path.name == sample_choice)
            dataset = load_flood_dataset(path.name, path.read_bytes())
        else:
            st.warning("Pilih file atau dataset contoh terlebih dahulu.")
            return
    except SchemaValidationError as exc:
        st.error(f"Validasi gagal: {exc}")
        return
    except Exception as exc:  # pragma: no cover - defensive UI guard
        st.error(f"Terjadi kesalahan saat membaca dataset: {exc}")
        return

    _reset_state()
    st.session_state[KEYS["dataset"]] = dataset
    st.success(f"Dataset '{dataset.name}' lolos validasi dengan {dataset.valid_row_count:,} baris.")


def _render_validation_and_history() -> None:
    dataset = st.session_state.get(KEYS["dataset"])
    if dataset is None:
        notice("Belum ada dataset. Unggah dataset pada tab <b>Import</b>.", "info")
        return

    summary = summarize_history(dataset.dataframe)
    step_label("Langkah 2")
    st.subheader("Validasi dan analisis historis")

    cards = st.columns(4)
    cards[0].markdown(metric_card("Baris valid", f"{summary.row_count:,}", "setelah validasi"), unsafe_allow_html=True)
    cards[1].markdown(metric_card("Lokasi", f"{summary.location_count:,}", "wilayah unik"), unsafe_allow_html=True)
    cards[2].markdown(metric_card("Kejadian banjir", f"{summary.flood_event_count:,}", f"{summary.flood_rate_pct:.1f}% baris"), unsafe_allow_html=True)
    cards[3].markdown(metric_card("Rentang data", f"{summary.span_days or 0:,} hari", f"{summary.date_min or '-'} s.d. {summary.date_max or '-'}"), unsafe_allow_html=True)

    if dataset.warnings:
        for warning in dataset.warnings:
            notice(warning, "danger")
    if dataset.invalid_row_count:
        notice(
            f"{dataset.invalid_row_count} baris ditandai tidak valid dan dikeluarkan dari analisis.",
            "danger",
        )
        with st.expander("Lihat baris tidak valid"):
            st.dataframe(dataset.invalid_rows, width="stretch", hide_index=True)

    mapping_frame = pd.DataFrame(
        [{"kolom_kanonik": key, "kolom_sumber": value} for key, value in dataset.mapping.items()]
    )
    with st.expander("Pemetaan kolom dan metadata"):
        st.dataframe(mapping_frame, width="stretch", hide_index=True)
        show_json(dataset.to_metadata(), "Metadata dataset")

    history_tab, rainfall_tab, location_tab = st.tabs(
        ["Tren kejadian", "Curah hujan", "Lokasi"]
    )

    with history_tab:
        if summary.monthly_counts.empty:
            notice("Tidak ada tanggal valid untuk analisis tren.", "info")
        else:
            figure = px.line(
                summary.monthly_counts,
                x="periode",
                y="jumlah_kejadian",
                markers=True,
                title="Kejadian banjir per bulan",
                labels={"periode": "Periode", "jumlah_kejadian": "Jumlah kejadian"},
            )
            figure.update_layout(height=360, margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(figure, width="stretch")
            if not summary.yearly_counts.empty:
                st.markdown("##### Ringkasan per tahun")
                st.dataframe(summary.yearly_counts, width="stretch", hide_index=True)

    with rainfall_tab:
        if not summary.rainfall_stats:
            notice("Tidak ada nilai curah hujan valid.", "info")
        else:
            stats = summary.rainfall_stats
            columns = st.columns(4)
            columns[0].metric("Rata-rata", f"{stats['mean']:.1f} mm")
            columns[1].metric("Median", f"{stats['median']:.1f} mm")
            columns[2].metric("Maksimum", f"{stats['max']:.1f} mm")
            columns[3].metric("Persentil 95", f"{stats['p95']:.1f} mm")
            if not summary.rainfall_by_event.empty:
                st.dataframe(summary.rainfall_by_event, width="stretch", hide_index=True)
            figure = px.histogram(
                dataset.dataframe,
                x="curah_hujan_mm",
                nbins=40,
                title="Distribusi curah hujan historis",
                labels={"curah_hujan_mm": "Curah hujan (mm)"},
                color_discrete_sequence=["#12708C"],
            )
            figure.update_layout(height=340, margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(figure, width="stretch")

    with location_tab:
        st.dataframe(summary.top_locations, width="stretch", hide_index=True)
        outside = outside_indonesia_count(dataset.dataframe)
        if outside:
            notice(
                f"{outside} titik berada di luar bounding box Indonesia. "
                "Peta tetap menampilkan koordinat valid yang tersedia.",
                "info",
            )

    if summary.warnings:
        for warning in summary.warnings:
            notice(warning, "info")


def _folium_map(points: pd.DataFrame) -> components.html | None:
    try:
        import folium
    except ImportError:
        return None

    center = map_center(points)
    bounds = map_bounds(points)
    map_object = folium.Map(location=center, zoom_start=6, tiles="OpenStreetMap", control_scale=True)
    palette = {"Kejadian banjir": "#C0392B", "Tidak banjir": "#12708C", "Tidak diketahui": "#8AA1B1"}

    for _, row in points.head(1500).iterrows():
        color = palette.get(row["status"], "#8AA1B1")
        popup = folium.Popup(
            f"<b>{row['lokasi']}</b><br/>{row['tanggal']}<br/>"
            f"Curah hujan: {row['curah_hujan_mm']} mm<br/>Status: {row['status']}",
            max_width=260,
        )
        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=float(row["radius"]),
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.55,
            weight=1,
            popup=popup,
        ).add_to(map_object)

    map_object.fit_bounds(
        [[bounds["lat_min"], bounds["lon_min"]], [bounds["lat_max"], bounds["lon_max"]]]
    )
    folium.LayerControl().add_to(map_object)
    return components.html(map_object._repr_html_(), height=520, scrolling=False)


def _pydeck_map(points: pd.DataFrame):
    try:
        import pydeck as pdk
    except ImportError:
        return None

    center = map_center(points)
    bounds = map_bounds(points)
    frame = points.copy()
    frame["color"] = frame["status"].map(
        {
            "Kejadian banjir": [192, 57, 43, 180],
            "Tidak banjir": [18, 112, 140, 170],
            "Tidak diketahui": [138, 161, 177, 160],
        }
    )
    frame["color"] = frame["color"].apply(lambda value: value if isinstance(value, list) else [138, 161, 177, 160])
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=frame,
        get_position=["longitude", "latitude"],
        get_fill_color="color",
        get_radius="radius",
        radius_units="'pixels'",
        pickable=True,
        auto_highlight=True,
    )
    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=pdk.ViewState(
            latitude=center[0],
            longitude=center[1],
            zoom=6,
            pitch=0,
        ),
        map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        tooltip={
            "html": "<b>{lokasi}</b><br/>{tanggal}<br/>Hujan: {curah_hujan_mm} mm<br/>{status}",
            "style": {"backgroundColor": "#0B3D4F", "color": "white"},
        },
    )
    return deck


def _render_map() -> None:
    dataset = st.session_state.get(KEYS["dataset"])
    if dataset is None:
        notice("Unggah dataset terlebih dahulu.", "info")
        return

    step_label("Langkah 3")
    st.subheader("Visualisasi geografis")
    points = build_map_points(dataset.dataframe)
    if points.empty:
        notice(
            "Tidak ada koordinat valid pada dataset. Tambahkan kolom latitude dan longitude "
            "untuk menampilkan peta.",
            "info",
        )
        return

    st.caption(
        f"{len(points):,} titik ditampilkan. Warna menunjukkan status kejadian; ukuran "
        "menggambarkan curah hujan. Peta hanya menampilkan wilayah yang didukung data."
    )
    engine = st.radio(
        "Mesin peta",
        options=["Folium", "PyDeck"],
        horizontal=True,
        key="lf_map_engine",
    )
    if engine == "Folium":
        rendered = _folium_map(points)
        if rendered is None:
            notice("Folium tidak tersedia. Menggunakan PyDeck.", "info")
            engine = "PyDeck"
    if engine == "PyDeck":
        deck = _pydeck_map(points)
        if deck is None:
            st.error("PyDeck tidak tersedia pada lingkungan ini.")
        else:
            st.pydeck_chart(deck, width="stretch", height=520)

    st.caption(
        f"GeoPandas {'tersedia' if geodataframe_available() else 'tidak tersedia'} "
        "pada lingkungan ini; analisis spasial lanjutan memerlukan GeoPandas."
    )
    with st.expander("Lihat data peta"):
        st.dataframe(points.head(200), width="stretch", hide_index=True)


def _render_simulation() -> None:
    dataset = st.session_state.get(KEYS["dataset"])
    if dataset is None:
        notice("Unggah dataset terlebih dahulu.", "info")
        return

    summary = summarize_history(dataset.dataframe)
    step_label("Langkah 4")
    st.subheader("Simulasi skenario dan pemrosesan paralel")
    notice(MODEL_DESCRIPTION, "info")

    default_rainfall = (
        summary.rainfall_stats.get("p95", 80.0) if summary.rainfall_stats else 80.0
    )

    with st.form("lf_simulation_form"):
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            base_rainfall = st.number_input(
                "Curah hujan dasar (mm)",
                min_value=1.0,
                max_value=1000.0,
                value=float(round(default_rainfall, 1)),
                step=5.0,
            )
            scenario_count = st.slider("Jumlah skenario", 2, 64, 8)
            duration = st.number_input("Durasi hujan (jam)", min_value=0.5, max_value=72.0, value=6.0, step=0.5)
        with col_b:
            multiplier_min = st.slider("Pengali minimum", 0.1, 3.0, 0.5, step=0.1)
            multiplier_max = st.slider("Pengali maksimum", 0.5, 5.0, 2.0, step=0.1)
            runoff = st.slider("Koefisien limpasan", 0.0, 1.0, 0.55, step=0.05)
        with col_c:
            drainage = st.number_input("Kapasitas drainase (mm)", min_value=0.0, max_value=500.0, value=45.0, step=5.0)
            moisture = st.slider("Kelembapan tanah awal", 0.0, 1.0, 0.4, step=0.05)
            threshold = st.number_input("Ambang risiko (mm)", min_value=1.0, max_value=500.0, value=60.0, step=5.0)

        mode = st.radio(
            "Mode eksekusi",
            options=["Serial", "Paralel", "Bandingkan keduanya"],
            horizontal=True,
        )
        exec_col, worker_col, load_col = st.columns(3)
        with exec_col:
            executor = st.selectbox(
                "Jenis worker",
                options=["process", "thread"],
                format_func=lambda value: "Proses (multiprocessing)"
                if value == "process"
                else "Thread (I/O dan NumPy)",
                help="Proses memberi isolasi penuh; thread menghindari overhead start-up "
                "sehingga sering lebih cepat untuk beban kerja sedang.",
            )
        with worker_col:
            workers = st.slider("Jumlah worker (mode paralel)", 1, 8, 4)
        with load_col:
            samples = st.select_slider(
                "Sampel Monte Carlo per skenario",
                options=[20_000, 60_000, 150_000, 300_000, 500_000],
                value=150_000,
                help="Semakin banyak sampel, semakin besar beban komputasi sehingga "
                "perbandingan serial vs paralel lebih bermakna.",
            )
        submitted = st.form_submit_button("Jalankan simulasi", type="primary")

    if multiplier_max <= multiplier_min:
        notice("Pengali maksimum harus lebih besar dari pengali minimum.", "danger")
        return

    if not submitted:
        comparison = st.session_state.get(KEYS["comparison"])
        if comparison is not None:
            _render_comparison(comparison, dataset)
        return

    parameters = SimulationParameters(
        runoff_coefficient=runoff,
        drainage_capacity_mm=drainage,
        antecedent_moisture=moisture,
        threshold_mm=threshold,
        samples_per_scenario=int(samples),
        time_steps=48,
    )
    try:
        parameters.validated()
    except ValueError as exc:
        st.error(str(exc))
        return

    multipliers = [
        multiplier_min + (multiplier_max - multiplier_min) * index / max(1, scenario_count - 1)
        for index in range(scenario_count)
    ]
    scenarios = generate_scenarios(base_rainfall, multipliers, duration, scenario_count)

    store = _job_store()
    job = store.create(
        dataset_name=dataset.name,
        dataset_sha256=dataset.sha256,
        dataset_rows=dataset.valid_row_count,
        parameters=parameters.to_dict(),
        mode=mode.lower(),
        notes=[f"{scenario_count} skenario", f"curah hujan dasar {base_rainfall} mm"],
    )
    st.session_state[KEYS["job"]] = job.job_id

    progress = st.progress(0.0, text="Menyiapkan simulasi...")
    try:
        if mode == "Serial":
            progress.progress(0.3, text="Menjalankan mode serial...")
            outcome = run_scenarios(scenarios, parameters, mode="serial")
            comparison = {
                "primary": outcome,
                "serial": outcome,
                "parallel": None,
                "consistent": True,
                "max_delta": 0.0,
                "speedup": None,
                "warnings": [],
                "executor": executor,
            }
        elif mode == "Paralel":
            progress.progress(0.3, text="Menjalankan mode paralel...")
            outcome = run_scenarios(
                scenarios,
                parameters,
                mode="parallel-thread" if executor == "thread" else "parallel",
                max_workers=workers,
            )
            comparison = {
                "primary": outcome,
                "serial": None,
                "parallel": outcome,
                "consistent": True,
                "max_delta": 0.0,
                "speedup": None,
                "warnings": list(outcome.warnings),
                "executor": executor,
            }
        else:
            progress.progress(0.25, text="Menjalankan mode serial...")
            progress.progress(0.55, text="Menjalankan mode paralel...")
            comparison = compare_modes(
                scenarios, parameters, max_workers=workers, executor=executor
            )
            comparison["executor"] = executor
            comparison["primary"] = comparison["serial"]
        progress.progress(1.0, text="Selesai.")
    except Exception as exc:
        store.fail(job, str(exc))
        progress.empty()
        st.error(f"Simulasi gagal: {exc}")
        return

    primary = comparison["primary"]
    summary_payload = {
        "scenarios": len(primary.results),
        "max_risk_score": max((result.risk_score for result in primary.results), default=0.0),
        "mean_risk_score": (
            sum(result.risk_score for result in primary.results) / len(primary.results)
            if primary.results
            else 0.0
        ),
        "consistent": comparison["consistent"],
        "speedup": comparison.get("speedup"),
    }
    store.complete(job, primary.elapsed_seconds, primary.workers, summary_payload)
    st.session_state[KEYS["comparison"]] = comparison
    st.session_state.pop(KEYS["report"], None)
    progress.empty()
    st.success(f"Simulasi selesai. ID pekerjaan: {job.job_id}")
    _render_comparison(comparison, dataset)


def _render_comparison(comparison: dict, dataset) -> None:
    primary = comparison["primary"]
    serial = comparison.get("serial")
    parallel = comparison.get("parallel")
    st.markdown("#### Hasil simulasi")

    frame = primary.results_frame()
    if not frame.empty:
        cards = st.columns(4)
        cards[0].markdown(metric_card("Skenario", f"{len(frame)}", "dihitung"), unsafe_allow_html=True)
        cards[1].markdown(metric_card("Skor maksimum", format_number(frame["risk_score"].max(), 1), "dari 100"), unsafe_allow_html=True)
        cards[2].markdown(metric_card("Skor rata-rata", format_number(frame["risk_score"].mean(), 1), "dari 100"), unsafe_allow_html=True)
        cards[3].markdown(metric_card("Kategori tertinggi", str(frame.loc[frame["risk_score"].idxmax(), "risk_category"]), "skenario terburuk"), unsafe_allow_html=True)

        figure = px.bar(
            frame,
            x="name",
            y="risk_score",
            color="risk_category",
            title="Skor risiko per skenario (hasil model demonstratif)",
            labels={"name": "Skenario", "risk_score": "Skor risiko", "risk_category": "Kategori"},
            color_discrete_map={
                "Rendah": "#4C956C",
                "Sedang": "#E9C46A",
                "Tinggi": "#F4A261",
                "Sangat Tinggi": "#C0392B",
            },
        )
        figure.update_layout(
            height=400,
            xaxis_tickangle=-35,
            yaxis_range=[0, 105],
            margin=dict(l=10, r=10, t=50, b=10),
        )
        st.plotly_chart(figure, width="stretch")
        st.dataframe(frame, width="stretch", hide_index=True)

    st.markdown("#### Perbandingan eksekusi")
    timing_rows = [
        {
            "mode": primary.mode,
            "waktu_detik": primary.elapsed_seconds,
            "worker": primary.workers,
            "sampel_per_skenario": primary.parameters.samples_per_scenario,
            "langkah_waktu": primary.parameters.time_steps,
        }
    ]
    if serial is not None and parallel is not None:
        timing_rows = [
            {
                "mode": "Serial",
                "waktu_detik": serial.elapsed_seconds,
                "worker": serial.workers,
                "sampel_per_skenario": serial.parameters.samples_per_scenario,
                "langkah_waktu": serial.parameters.time_steps,
            },
            {
                "mode": parallel.mode,
                "waktu_detik": parallel.elapsed_seconds,
                "worker": parallel.workers,
                "sampel_per_skenario": parallel.parameters.samples_per_scenario,
                "langkah_waktu": parallel.parameters.time_steps,
            },
        ]
    timing = pd.DataFrame(timing_rows)
    st.dataframe(timing, width="stretch", hide_index=True)

    if serial is not None and parallel is not None:
        columns = st.columns(3)
        columns[0].metric("Speedup", f"{comparison['speedup']:.2f}x" if comparison.get("speedup") else "-")
        columns[1].metric("Konsisten", "Ya" if comparison["consistent"] else "Tidak")
        columns[2].metric("Selisih maksimum", f"{comparison['max_delta']:.2e}")
        if not comparison["consistent"]:
            notice("Hasil serial dan paralel berbeda. Periksa konfigurasi eksekusi.", "danger")
        for warning in comparison.get("warnings", []):
            notice(warning, "info")
        notice(
            "Performa paralel bergantung pada jumlah inti CPU dan ukuran tugas. Untuk tugas "
            "kecil, overhead proses dapat membuat eksekusi paralel lebih lambat. "
            "Mode thread sering lebih cepat untuk beban NumPy karena menghindari start-up proses.",
            "info",
        )

    st.markdown("#### Ekspor hasil")
    download_row(
        [
            ("Unduh hasil simulasi (CSV)", results_to_csv_bytes(frame), "localflood_results.csv", "text/csv"),
            (
                "Unduh parameter (JSON)",
                safe_json(
                    {
                        "dataset": dataset.name,
                        "dataset_sha256": dataset.sha256,
                        "parameters": primary.parameters.to_dict(),
                        "serial_seconds": serial.elapsed_seconds if serial else None,
                        "parallel_seconds": parallel.elapsed_seconds if parallel else None,
                        "speedup": comparison.get("speedup"),
                    }
                ).encode("utf-8"),
                "localflood_parameters.json",
                "application/json",
            ),
        ],
        key_prefix="simulation",
    )

    if st.button("Susun laporan PDF", type="primary", key="lf_build_report"):
        try:
            pdf = build_flood_report_pdf(
                dataset_name=dataset.name,
                dataset_sha256=dataset.sha256,
                summary=summarize_history(dataset.dataframe),
                parameters=primary.parameters,
                primary=primary,
                serial=serial,
                parallel=parallel,
                job_id=st.session_state.get(KEYS["job"]),
                dataset_warnings=dataset.warnings,
            )
        except Exception as exc:  # pragma: no cover - report generation guard
            st.error(f"Laporan gagal dibuat: {exc}")
        else:
            st.session_state[KEYS["report"]] = pdf
            st.success("Laporan PDF siap diunduh.")

    pdf = st.session_state.get(KEYS["report"])
    if pdf is not None:
        download_row([("Unduh laporan PDF", pdf, "localflood_report.pdf", "application/pdf")])


def _render_workflow() -> None:
    step_label("Langkah 5")
    st.subheader("Workflow dan riwayat pekerjaan")
    st.caption(
        "Setiap pekerjaan mencatat dataset, hash, parameter, metode, waktu, status, dan hasil. "
        "Catatan ini membantu reproduksi dan pemindahan pekerjaan ke infrastruktur lain."
    )

    store = _job_store()
    jobs = store.list_jobs(limit=20)
    if not jobs:
        notice("Belum ada pekerjaan tercatat. Jalankan simulasi pada tab <b>Simulasi</b>.", "info")
        return

    table = pd.DataFrame(
        [
            {
                "job_id": job.job_id,
                "dataset": job.dataset_name,
                "status": job.status,
                "mode": job.mode,
                "waktu_detik": job.elapsed_seconds,
                "worker": job.workers,
                "selesai": job.finished_at,
            }
            for job in jobs
        ]
    )
    st.dataframe(table, width="stretch", hide_index=True)

    selected = st.selectbox("Lihat detail pekerjaan", options=[job.job_id for job in jobs])
    record = store.load(selected)
    show_json(record.to_dict(), f"Detail {record.job_id}")

    if record.status == "completed":
        notice("Pekerjaan selesai dan dapat direproduksi dengan parameter yang sama.", "info")
    elif record.status == "failed":
        notice(f"Pekerjaan gagal: {record.error}", "danger")

    st.markdown("#### Riwayat versi dataset")
    dataset = st.session_state.get(KEYS["dataset"])
    if dataset is not None:
        st.code(
            f"dataset : {dataset.name}\n"
            f"sha256  : {dataset.sha256}\n"
            f"baris   : {dataset.valid_row_count}\n"
            f"kolom   : {len(dataset.dataframe.columns)}",
            language="text",
        )


def render_localflood() -> None:
    hero(
        f"{LOCALFLOOD_NAME}",
        "Eksplorasi data hujan dan kejadian banjir, simulasi skenario demonstratif, dan "
        "demonstrasi pemrosesan serial vs paralel.",
    )
    dataset = st.session_state.get(KEYS["dataset"])
    if dataset is not None:
        st.caption(
            f"Dataset aktif: **{dataset.name}** · {dataset.valid_row_count:,} baris valid · "
            f"SHA-256 `{dataset.sha256[:12]}…`"
        )

    # Navigasi radio (bukan st.tabs): st.tabs mengembalikan pengguna ke tab pertama setelah rerun
    # (mis. selesai simulasi), dan versi Streamlit lama tidak menyediakan cara mempertahankannya.
    steps = {
        "1. Import": _render_upload,
        "2. Historis": _render_validation_and_history,
        "3. Peta": _render_map,
        "4. Simulasi": _render_simulation,
        "5. Workflow": _render_workflow,
    }
    choice = st.radio("Langkah", list(steps), horizontal=True, key="lf_nav")
    steps[choice]()

    st.divider()
    st.caption(DISCLAIMER_FLOOD)
