"""CSV and PDF exports for LocalFlood (FR-07)."""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any, Sequence

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from common.config import DISCLAIMER_FLOOD, LOCALFLOOD_NAME
from localflood.historical import HistoricalSummary
from localflood.simulation import MODEL_DESCRIPTION, ScenarioResult, SimulationOutcome, SimulationParameters


def results_to_csv_bytes(results: Sequence[ScenarioResult] | pd.DataFrame) -> bytes:
    """Serialize scenario results to CSV bytes."""
    if isinstance(results, pd.DataFrame):
        frame = results
    else:
        frame = pd.DataFrame([result.to_dict() for result in results])
    return frame.to_csv(index=False).encode("utf-8-sig")


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "TitleFlood",
            parent=base["Title"],
            fontSize=19,
            textColor=colors.HexColor("#0B3D4F"),
            spaceAfter=6,
        ),
        "subtitle": ParagraphStyle(
            "SubtitleFlood",
            parent=base["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#5A6B7B"),
            spaceAfter=12,
        ),
        "h1": ParagraphStyle(
            "H1Flood",
            parent=base["Heading1"],
            fontSize=13,
            textColor=colors.HexColor("#0B3D4F"),
            spaceBefore=14,
            spaceAfter=6,
        ),
        "h2": ParagraphStyle(
            "H2Flood",
            parent=base["Heading2"],
            fontSize=10.5,
            textColor=colors.HexColor("#12708C"),
            spaceBefore=8,
            spaceAfter=4,
        ),
        "body": ParagraphStyle("BodyFlood", parent=base["BodyText"], fontSize=9, leading=13),
        "small": ParagraphStyle("SmallFlood", parent=base["BodyText"], fontSize=8, leading=11),
        "warning": ParagraphStyle(
            "WarningFlood",
            parent=base["BodyText"],
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#7A3E00"),
            backColor=colors.HexColor("#FFF3E0"),
            borderPadding=6,
        ),
    }


def _table(data: list[list[Any]], widths: list[float] | None = None) -> Table:
    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#12708C")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E0")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F7F9")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _figure_to_image(figure: plt.Figure, width_cm: float = 15.5, ratio: float = 0.45) -> Image:
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=150, bbox_inches="tight")
    plt.close(figure)
    buffer.seek(0)
    return Image(buffer, width=width_cm * cm, height=width_cm * cm * ratio)


def _scenario_chart(results: Sequence[ScenarioResult]) -> Image | None:
    if not results:
        return None
    figure, axis = plt.subplots(figsize=(7.0, 3.2))
    names = [result.name for result in results]
    scores = [result.risk_score for result in results]
    palette = {"Rendah": "#4C956C", "Sedang": "#E9C46A", "Tinggi": "#F4A261", "Sangat Tinggi": "#C0392B"}
    colors_list = [palette.get(result.risk_category, "#8AA1B1") for result in results]
    axis.bar(range(len(results)), scores, color=colors_list, edgecolor="white")
    axis.set_xticks(range(len(results)))
    axis.set_xticklabels([name.split(" (")[0] for name in names], rotation=30, ha="right", fontsize=6)
    axis.set_ylabel("Skor risiko (0-100)", fontsize=8)
    axis.set_ylim(0, 105)
    axis.set_title("Skor risiko per skenario (hasil model demonstratif)", fontsize=9)
    axis.grid(axis="y", alpha=0.25)
    axis.tick_params(labelsize=7)
    figure.tight_layout()
    return _figure_to_image(figure)


def _history_chart(summary: HistoricalSummary) -> Image | None:
    monthly = summary.monthly_counts
    if monthly is None or monthly.empty:
        return None
    figure, axis = plt.subplots(figsize=(7.0, 3.0))
    axis.plot(
        range(len(monthly)),
        monthly["jumlah_kejadian"],
        marker="o",
        markersize=3,
        color="#12708C",
    )
    axis.set_title("Kejadian banjir per bulan", fontsize=9)
    axis.set_ylabel("Jumlah kejadian", fontsize=8)
    axis.set_xticks(range(len(monthly)))
    step = max(1, len(monthly) // 10)
    axis.set_xticklabels(
        [period if index % step == 0 else "" for index, period in enumerate(monthly["periode"])],
        rotation=45,
        ha="right",
        fontsize=6,
    )
    axis.grid(alpha=0.25)
    axis.tick_params(labelsize=7)
    figure.tight_layout()
    return _figure_to_image(figure)


def _timing_chart(serial_seconds: float, parallel_seconds: float) -> Image | None:
    if serial_seconds <= 0 and parallel_seconds <= 0:
        return None
    figure, axis = plt.subplots(figsize=(5.4, 2.6))
    axis.bar(["Serial", "Paralel"], [serial_seconds, parallel_seconds], color=["#8AA1B1", "#12708C"])
    for index, value in enumerate([serial_seconds, parallel_seconds]):
        axis.text(index, value, f"{value:.4f}s", ha="center", va="bottom", fontsize=8)
    axis.set_ylabel("Waktu eksekusi (detik)", fontsize=8)
    axis.set_title("Perbandingan waktu eksekusi", fontsize=9)
    axis.grid(axis="y", alpha=0.25)
    axis.tick_params(labelsize=7)
    figure.tight_layout()
    return _figure_to_image(figure, width_cm=11.0, ratio=0.5)


def _add_footer(canvas, document) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#6B7C8F"))
    canvas.drawString(2 * cm, 1.2 * cm, f"{LOCALFLOOD_NAME} - laporan simulasi")
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Halaman {document.page}")
    canvas.restoreState()


def build_flood_report_pdf(
    dataset_name: str,
    dataset_sha256: str,
    summary: HistoricalSummary,
    parameters: SimulationParameters,
    primary: SimulationOutcome,
    serial: SimulationOutcome | None = None,
    parallel: SimulationOutcome | None = None,
    job_id: str | None = None,
    dataset_warnings: list[str] | None = None,
    generated_at: datetime | None = None,
) -> bytes:
    """Build a PDF report for a LocalFlood simulation run."""
    styles = _styles()
    generated_at = generated_at or datetime.now()
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title=f"{LOCALFLOOD_NAME} Report - {dataset_name}",
        author=LOCALFLOOD_NAME,
    )

    story: list[Any] = [
        Paragraph("Laporan Simulasi Risiko Banjir", styles["title"]),
        Paragraph(
            f"{dataset_name} &nbsp;|&nbsp; dibuat {generated_at.strftime('%d %B %Y %H:%M')} "
            f"&nbsp;|&nbsp; SHA-256: {dataset_sha256[:16]}...",
            styles["subtitle"],
        ),
        Paragraph(DISCLAIMER_FLOOD, styles["warning"]),
        Spacer(1, 10),
        Paragraph("1. Informasi Dataset dan Pekerjaan", styles["h1"]),
        _table(
            [
                ["Properti", "Nilai"],
                ["Nama dataset", dataset_name],
                ["Hash dataset (SHA-256)", dataset_sha256],
                ["Baris valid", f"{summary.row_count:,}"],
                ["Jumlah lokasi", f"{summary.location_count:,}"],
                ["Rentang tanggal", f"{summary.date_min or '-'} s.d. {summary.date_max or '-'}"],
                ["Kejadian banjir", f"{summary.flood_event_count:,}"],
                ["Rasio baris banjir", f"{summary.flood_rate_pct:.2f}%"],
                ["ID pekerjaan", job_id or "-"],
            ],
            widths=[5 * cm, 11.5 * cm],
        ),
        Paragraph("2. Ringkasan Historis", styles["h1"]),
    ]

    if summary.rainfall_stats:
        stats = summary.rainfall_stats
        story.append(
            _table(
                [
                    ["Statistik curah hujan (mm)", "Nilai"],
                    ["Jumlah observasi", f"{stats['count']:,}"],
                    ["Rata-rata", f"{stats['mean']:.2f}"],
                    ["Median", f"{stats['median']:.2f}"],
                    ["Maksimum", f"{stats['max']:.2f}"],
                    ["Persentil 95", f"{stats['p95']:.2f}"],
                ],
                widths=[6 * cm, 5 * cm],
            )
        )
    else:
        story.append(Paragraph("Tidak ada data curah hujan valid.", styles["body"]))

    history_chart = _history_chart(summary)
    if history_chart is not None:
        story.append(KeepTogether([Paragraph("Tren kejadian per bulan", styles["h2"]), history_chart]))

    if not summary.top_locations.empty:
        story.append(Paragraph("Lokasi dengan kejadian terbanyak", styles["h2"]))
        rows = [["Lokasi", "Kejadian", "Observasi", "Rata-rata hujan (mm)"]]
        for _, row in summary.top_locations.head(10).iterrows():
            rows.append(
                [
                    str(row["lokasi"])[:32],
                    str(int(row["jumlah_kejadian"])),
                    str(int(row["total_observasi"])),
                    f"{row['curah_hujan_rata_rata']:.2f}"
                    if pd.notna(row["curah_hujan_rata_rata"])
                    else "-",
                ]
            )
        story.append(_table(rows, widths=[6 * cm, 2.6 * cm, 2.6 * cm, 4 * cm]))

    story.append(Paragraph("3. Parameter Simulasi", styles["h1"]))
    story.append(
        _table(
            [["Parameter", "Nilai"]]
            + [[key, f"{value:.4g}" if isinstance(value, float) else str(value)] for key, value in parameters.to_dict().items()],
            widths=[7 * cm, 6 * cm],
        )
    )
    story.append(Paragraph(MODEL_DESCRIPTION, styles["small"]))
    story.append(Spacer(1, 6))

    story.append(Paragraph("4. Hasil Simulasi", styles["h1"]))
    results = primary.results
    chart = _scenario_chart(results)
    if chart is not None:
        story.append(KeepTogether([Paragraph("Skor risiko skenario", styles["h2"]), chart]))
    result_rows = [["Skenario", "Hujan (mm)", "Durasi (jam)", "Efektif (mm)", "Skor", "Kategori"]]
    for result in results:
        result_rows.append(
            [
                result.name[:28],
                f"{result.rainfall_mm:.2f}",
                f"{result.duration_hours:.1f}",
                f"{result.effective_rainfall_mm:.2f}",
                f"{result.risk_score:.2f}",
                result.risk_category,
            ]
        )
    story.append(_table(result_rows, widths=[5 * cm, 2.4 * cm, 2.2 * cm, 2.4 * cm, 1.8 * cm, 2.8 * cm]))

    story.append(Paragraph("5. Perbandingan Serial dan Paralel", styles["h1"]))
    timing = [["Mode", "Waktu (detik)", "Worker", "Catatan"]]
    if serial is not None and parallel is not None:
        speedup = (
            serial.elapsed_seconds / parallel.elapsed_seconds
            if parallel.elapsed_seconds > 0
            else float("nan")
        )
        timing.append(["Serial", f"{serial.elapsed_seconds:.6f}", str(serial.workers), "Berurutan"])
        timing.append(
            [
                "Paralel",
                f"{parallel.elapsed_seconds:.6f}",
                str(parallel.workers),
                f"Speedup {speedup:.2f}x",
            ]
        )
        consistent = all(
            abs(left.risk_score - right.risk_score) <= 1e-6
            for left, right in zip(serial.results, parallel.results)
        )
        story.append(_table(timing, widths=[3 * cm, 3.4 * cm, 2 * cm, 7.6 * cm]))
        story.append(
            Paragraph(
                f"Konsistensi hasil serial vs paralel: {'konsisten' if consistent else 'TIDAK konsisten'}.",
                styles["body"],
            )
        )
        timing_chart = _timing_chart(serial.elapsed_seconds, parallel.elapsed_seconds)
        if timing_chart is not None:
            story.append(KeepTogether([Paragraph("Waktu eksekusi", styles["h2"]), timing_chart]))
    else:
        timing.append(
            [
                primary.mode,
                f"{primary.elapsed_seconds:.6f}",
                str(primary.workers),
                "Mode tunggal (tanpa pembanding)",
            ]
        )
        story.append(_table(timing, widths=[3 * cm, 3.4 * cm, 2 * cm, 7.6 * cm]))
        story.append(
            Paragraph(
                "Jalankan mode 'Bandingkan keduanya' untuk mengukur speedup serial vs paralel.",
                styles["body"],
            )
        )

    story.append(Paragraph("6. Keterbatasan dan Peringatan", styles["h1"]))
    limitations = [
        "Model simulasi bersifat demonstratif dan tidak divalidasi terhadap data hidrologi lapangan.",
        "Skor risiko adalah indikator relatif untuk pembelajaran, bukan prediksi kejadian banjir.",
        "Hasil bergantung pada kualitas, cakupan, dan satuan data masukan.",
        "Pemrosesan paralel lokal hanya mendemonstrasikan konsep HPC; beban kerja kecil dapat "
        "lebih lambat karena overhead.",
    ]
    limitations.extend(summary.warnings)
    limitations.extend(dataset_warnings or [])
    for item in dict.fromkeys(limitations):
        story.append(Paragraph(f"- {item}", styles["body"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph(DISCLAIMER_FLOOD, styles["warning"]))

    document.build(story, onFirstPage=_add_footer, onLaterPages=_add_footer)
    return buffer.getvalue()
