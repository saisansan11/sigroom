from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_online_teaching_user_copy_is_plain_thai():
    home = _read("templates/bookings/online_teaching_home.html")
    book = _read("templates/bookings/online_teaching_book.html")
    form_source = _read("bookings/online_teaching.py")

    assert "สำหรับครูผู้สอน" in home
    assert "Teacher Self-Service" not in home
    assert "Booking Core" not in home
    assert "สำหรับครูผู้สอน" in book
    assert "Teacher Self-Service" not in book
    assert "ยืนยันการจอง" in book
    assert 'label="หลักสูตรและรุ่น"' in form_source


def test_lodging_course_run_selection_refreshes_dates_every_time():
    template = _read("templates/lodging/manage_list.html")

    assert "หลักสูตรและรุ่น" in template
    assert "if (start) start.value" in template
    assert "if (end) end.value" in template
    assert "!start.value" not in template
    assert "!end.value" not in template


def test_phase_e_touch_targets_keep_44px_minimum():
    app_css = _read("static/css/app.css")
    online_css = _read("static/css/online_teaching.css")

    lodging_block = app_css.split(".lodging-selection-btn {", 1)[1].split("}", 1)[0]
    assert "min-height: 44px" in lodging_block
    assert "min-height: 38px" not in lodging_block
    assert ".online-booking-actions{display:grid;grid-template-columns:1fr;width:100%;justify-content:stretch}" in online_css
