"""UX-11 contracts for reports dashboard mobile clarity."""
from pathlib import Path

from django.conf import settings


def _template() -> str:
    return (Path(settings.BASE_DIR) / "templates" / "reports" / "dashboard.html").read_text(encoding="utf-8")


def _css() -> str:
    return (Path(settings.BASE_DIR) / "static" / "css" / "app.css").read_text(encoding="utf-8")


def test_reports_dashboard_keeps_five_semantic_tables_and_filter_contract():
    template = _template()

    assert template.count("<table") == 5
    assert template.count("<caption") == 5
    assert 'method="get"' in template
    assert 'name="month"' in template
    assert 'name="room"' in template
    assert 'name="unit"' in template
    assert "กรองรายงาน" in template

    for hook in (
        "report-filter-grid",
        "report-table-wrap",
        "report-table",
        "report-row",
        "report-empty-row",
        "report-empty-cell",
        "report-download-button",
    ):
        assert hook in template


def test_reports_dashboard_preserves_all_csv_report_keys_and_values():
    template = _template()

    assert template.count("format=csv&report=") == 5
    for key in ("room_usage", "cancellation", "approval", "preemption", "equipment"):
        assert f"format=csv&report={key}" in template

    for report_hook in (
        "report-table-room-usage",
        "report-table-cancellation",
        "report-table-approval",
        "report-table-preemption",
        "report-table-equipment",
    ):
        assert report_hook in template

    # Mobile labels must come from explicit table-cell metadata, not reordered data.
    for label in (
        'data-label="ห้อง"',
        'data-label="หน่วย"',
        'data-label="ผู้อนุมัติ"',
        'data-label="เลขอ้างอิง"',
        'data-label="อุปกรณ์"',
    ):
        assert label in template

    assert "reports.room_usage" in template
    assert "reports.cancellation" in template
    assert "reports.approval" in template
    assert "reports.preemption" in template
    assert "reports.equipment" in template


def test_ux11_css_is_reports_scoped_mobile_only_and_wrap_safe():
    css = _css()
    marker = "/* UX-11 Reports Dashboard Mobile Clarity */"

    assert marker in css
    ux11 = css.split(marker, 1)[1]
    assert "@media (max-width: 47.99rem)" in ux11
    assert "@media (max-width: 48rem)" not in ux11
    assert ".report-table-wrap .report-table" in ux11
    assert ".report-table .report-row" in ux11
    assert ".report-download-button" in ux11
    assert ".report-empty-cell" in ux11
    assert "content: attr(data-label)" in ux11
    assert "min-width: 0" in ux11
    assert "min-height: 44px" in ux11
    assert "overflow-wrap: anywhere" in ux11
    assert "word-break: break-word" in ux11
    assert ":has(" not in ux11
