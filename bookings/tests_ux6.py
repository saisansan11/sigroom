"""UX-6 contracts for recurring-booking preview on narrow screens."""
from pathlib import Path

from django.conf import settings


def test_series_preview_template_keeps_one_table_and_submit_contracts():
    template = (Path(settings.BASE_DIR) / "templates" / "bookings" / "series_preview.html").read_text(encoding="utf-8")

    assert template.count('<table class="series-preview-table">') == 1
    for hook in (
        "series-preview-wrap",
        "series-preview-row",
        "series-preview-index",
        "series-preview-date",
        "series-preview-result",
    ):
        assert hook in template
    assert "{% url 'bookings:series_create' room.code %}" in template
    assert 'name="_preview_free_dates"' in template
    assert "{% if item.is_free %}" in template
    assert "จองเฉพาะครั้งที่ว่าง" in template


def test_series_preview_template_preserves_status_and_reason_logic():
    template = (Path(settings.BASE_DIR) / "templates" / "bookings" / "series_preview.html").read_text(encoding="utf-8")

    assert "{% if item.status == 'free' %}" in template
    assert "{% elif item.status == 'blackout' %}" in template
    assert '<span class="status status-approved">ว่าง</span>' in template
    assert '<span class="status status-draft">ข้าม</span> {{ item.reason }}' in template
    assert '<span class="status status-rejected">เวลาชน</span> {{ item.reason }}' in template


def test_ux6_css_is_preview_scoped_and_exact_768_stays_desktop():
    css = (Path(settings.BASE_DIR) / "static" / "css" / "app.css").read_text(encoding="utf-8")
    marker = "/* UX-6 Series Preview Mobile Clarity */"

    assert marker in css
    ux6 = css.split(marker, 1)[1]
    assert "@media (max-width: 47.99rem)" in ux6
    assert ".series-preview-wrap .series-preview-table" in ux6
    assert "min-width: 0" in ux6
    assert "grid-template-areas" in ux6
    assert ".series-preview-result" in ux6
    assert ".series-summary-grid" in ux6
    assert ":has(" not in ux6
