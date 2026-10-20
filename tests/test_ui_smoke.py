"""Smoke test wiring Streamlit LocalFlood HPC Lab."""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def _fresh_app() -> AppTest:
    app = AppTest.from_file(APP, default_timeout=180)
    app.run()
    assert not app.exception
    return app


def test_page_renders_with_five_steps():
    assert _fresh_app().radio[0].options == ["1. Import", "2. Historis", "3. Peta", "4. Simulasi", "5. Workflow"]


def test_loads_flood_sample():
    app = _fresh_app()
    sample = next(s for s in app.selectbox if s.key == "lf_sample_choice")
    sample.set_value("flood_history.csv")
    next(b for b in app.button if b.label == "Muat dan validasi").click().run()
    assert not app.exception


def test_step_is_kept_after_running_simulation():
    """Regresi: setelah simulasi selesai pengguna tidak boleh dikembalikan ke langkah pertama."""
    app = _fresh_app()
    next(s for s in app.selectbox if s.key == "lf_sample_choice").set_value("flood_history.csv")
    next(b for b in app.button if b.label == "Muat dan validasi").click().run()
    app.radio[0].set_value("4. Simulasi").run()
    next(b for b in app.button if b.label == "Jalankan simulasi").click().run()
    assert not app.exception
    assert app.radio[0].value == "4. Simulasi"
    assert len(app.metric) > 0 or len(app.dataframe) > 0  # hasil simulasi tampil di langkah yang sama
