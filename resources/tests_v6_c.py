"""Test งาน v6-c — รูปห้องแบบเว็บโรงแรม (ประตูที่ 1 เท่านั้น ดู docs/v6-plan-antigravity.md)"""
import io
from unittest.mock import patch

import pytest
from django.contrib import admin as django_admin
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from accounts.models import Unit, User
from bookings.lodging_models import CourseLodgingCohort
from resources.admin import ResourcePhotoInline
from resources.models import Resource, ResourcePhoto
from resources.services import delete_room_photo, save_room_photo

pytestmark = pytest.mark.django_db


def _make_upload(name="photo.png", color=(255, 0, 0), fmt="PNG", raw_bytes=None):
    if raw_bytes is not None:
        return SimpleUploadedFile(name, raw_bytes, content_type="image/png")
    buf = io.BytesIO()
    Image.new("RGB", (2, 2), color=color).save(buf, format=fmt)
    return SimpleUploadedFile(name, buf.getvalue(), content_type=f"image/{fmt.lower()}")


def _make_room(code="ROOM-C1", **kwargs):
    return Resource.objects.create(code=code, name=f"ห้อง {code}", building="อาคาร 9", **kwargs)


@pytest.fixture
def upload_enabled(settings, tmp_path):
    """เปิดใช้อัปโหลดและชี้ storage ไปที่โฟลเดอร์ชั่วคราวของ test เท่านั้น (ไม่แตะ media/ จริง)"""
    settings.ROOM_PHOTO_UPLOAD_ENABLED = True
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


@pytest.fixture
def room(upload_enabled):
    return _make_room()


@pytest.fixture
def equipment():
    return Resource.objects.create(code="EQ-C1", name="โปรเจกเตอร์", resource_type=Resource.Type.EQUIPMENT)


# --- C2: model/service ------------------------------------------------------


def test_cover_photo_duplicate_at_db_level_raises_integrity_error(room):
    """constraint unique_cover_photo_per_resource ต้องบังคับที่ระดับฐานข้อมูลจริง
    สร้างตรงผ่าน ORM ข้าม service ตามข้อยกเว้นที่ระบุใน C2/C4 (full_clean ของ service
    จะดักก่อนถึง DB เสมอ จึงต้องพิสูจน์ด้วยการข้าม full_clean ไปเลย)
    """
    ResourcePhoto.objects.create(resource=room, image=_make_upload(), is_cover=True)
    with pytest.raises(IntegrityError):
        ResourcePhoto.objects.create(resource=room, image=_make_upload(name="two.png"), is_cover=True)


def test_save_room_photo_rejects_cover_duplicate_with_thai_message(room):
    save_room_photo(resource=room, image=_make_upload(), is_cover=True)
    with pytest.raises(ValidationError) as exc:
        save_room_photo(resource=room, image=_make_upload(name="two.png"), is_cover=True)
    assert "รูปหน้าปก" in str(exc.value)


def test_save_room_photo_rejects_non_room_resource(equipment, upload_enabled):
    with pytest.raises(ValidationError) as exc:
        save_room_photo(resource=equipment, image=_make_upload())
    assert "เฉพาะห้อง" in str(exc.value)


def test_save_room_photo_rejects_disallowed_file_type(room):
    bad_file = SimpleUploadedFile("notes.txt", b"not an image at all", content_type="text/plain")
    with pytest.raises(ValidationError) as exc:
        save_room_photo(resource=room, image=bad_file)
    assert "รูปภาพ" in str(exc.value)


def test_save_room_photo_rejects_file_larger_than_5mb(room):
    too_big = SimpleUploadedFile("big.png", b"0" * (5 * 1024 * 1024 + 1), content_type="image/png")
    with pytest.raises(ValidationError) as exc:
        save_room_photo(resource=room, image=too_big)
    assert "5MB" in str(exc.value)


def test_uploading_two_files_with_same_original_name_get_different_paths(room):
    first = save_room_photo(resource=room, image=_make_upload(name="photo.png", color=(255, 0, 0)))
    second = save_room_photo(resource=room, image=_make_upload(name="photo.png", color=(0, 255, 0)))

    assert first.image.name != second.image.name
    assert first.image.storage.exists(first.image.name)
    assert second.image.storage.exists(second.image.name)


# --- C2: ไฟล์กำพร้า 4 กรณี ----------------------------------------------------


def test_delete_room_photo_removes_file_from_storage(room, django_capture_on_commit_callbacks):
    photo = save_room_photo(resource=room, image=_make_upload())
    storage, name = photo.image.storage, photo.image.name
    assert storage.exists(name)

    with django_capture_on_commit_callbacks(execute=True):
        delete_room_photo(photo)

    assert not storage.exists(name)
    assert not ResourcePhoto.objects.filter(pk=photo.pk).exists()


def test_save_room_photo_deletes_new_file_when_db_save_fails_after_write(room):
    """จำลอง exception หลังไฟล์ถูกเขียนลง storage แล้วแต่ก่อน DB commit (mock ขั้นบันทึกแถว DB
    โดยตรง ไม่ใช่แค่ validation error — full_clean() ผ่านไปแล้วตอนนี้ ไฟล์ถูกเขียนจริงแล้ว)
    ต้องได้ทั้งสองอย่าง: ไฟล์ใหม่ถูกลบ และ exception ต้นฉบับถูกส่งกลับ (ห้ามกลืน error)
    """
    upload = _make_upload()
    captured = {}

    def _boom(self, *args, **kwargs):
        # ไฟล์ถูกเขียนลง storage แล้ว ณ จุดนี้ (save_room_photo เรียก image.save(...) ก่อนหน้านี้)
        captured["name"] = self.image.name
        captured["storage"] = self.image.storage
        assert self.image.storage.exists(self.image.name), "ไฟล์ต้องถูกเขียนลง storage ไปแล้วก่อน DB save จะถูกเรียก"
        raise IntegrityError("จำลอง DB ล่มกลางคัน")

    with patch.object(ResourcePhoto, "save", new=_boom):
        with pytest.raises(IntegrityError, match="จำลอง DB ล่มกลางคัน"):
            save_room_photo(resource=room, image=upload)

    assert "name" in captured, "ต้องเขียนไฟล์ลง storage ก่อนจะเรียก DB save (ตาม flow ที่ mock ไว้)"
    assert not captured["storage"].exists(captured["name"]), "ไฟล์ใหม่ที่ค้างต้องถูกลบแบบ best-effort"
    assert not ResourcePhoto.objects.filter(resource=room).exists()


def test_save_room_photo_replacing_image_deletes_old_file_keeps_new_one(room, django_capture_on_commit_callbacks):
    """แทนที่รูปเดิมสำเร็จแล้วไฟล์เก่าต้องหาย ไฟล์ใหม่ต้องยังอยู่"""
    photo = save_room_photo(resource=room, image=_make_upload(color=(255, 0, 0)))
    old_storage, old_name = photo.image.storage, photo.image.name
    assert old_storage.exists(old_name)

    with django_capture_on_commit_callbacks(execute=True):
        updated = save_room_photo(resource=room, image=_make_upload(color=(0, 0, 255)), photo=photo)

    assert updated.image.name != old_name
    assert not old_storage.exists(old_name)
    assert updated.image.storage.exists(updated.image.name)


def test_delete_room_photo_callback_storage_error_is_logged_not_raised(room, django_capture_on_commit_callbacks, caplog):
    """callback ลบไฟล์ใน transaction.on_commit ต้อง best-effort เสมอ — ถ้า storage.delete() พัง
    ต้องแค่ log ไม่ทำให้ flow หลัก (ที่ commit สำเร็จไปแล้ว) fail ให้ผู้ใช้เห็น
    """
    photo = save_room_photo(resource=room, image=_make_upload())
    storage = photo.image.storage

    with patch.object(storage, "delete", side_effect=OSError("storage ล่ม")):
        with django_capture_on_commit_callbacks(execute=True):
            delete_room_photo(photo)  # ต้องไม่ raise ออกมาแม้ storage.delete() จะพัง

    assert not ResourcePhoto.objects.filter(pk=photo.pk).exists()
    assert any("ลบไฟล์" in record.message for record in caplog.records)


# --- flag ปิดอัปโหลด (C1) ----------------------------------------------------


def test_save_room_photo_raises_when_upload_flag_disabled(room, settings):
    settings.ROOM_PHOTO_UPLOAD_ENABLED = False
    with pytest.raises(ValidationError) as exc:
        save_room_photo(resource=room, image=_make_upload())
    assert "GS_BUCKET_NAME" in str(exc.value)


def test_admin_inline_hides_upload_field_when_flag_disabled(settings):
    settings.ROOM_PHOTO_UPLOAD_ENABLED = False
    inline = ResourcePhotoInline(Resource, django_admin.site)
    fields = inline.get_fields(None)
    assert "image" not in fields
    assert inline.has_add_permission(None) is False


def test_admin_inline_shows_upload_field_when_flag_enabled(settings):
    settings.ROOM_PHOTO_UPLOAD_ENABLED = True
    inline = ResourcePhotoInline(Resource, django_admin.site)
    fields = inline.get_fields(None)
    assert "image" in fields
    assert inline.has_add_permission(None) is True


# --- C3: หน้าเว็บ (render + N+1) ---------------------------------------------


def test_calendar_view_renders_cover_photo_and_placeholder(client, room):
    other_room = _make_room("ROOM-C2")
    save_room_photo(resource=room, image=_make_upload(), is_cover=True)

    resp = client.get(reverse("bookings:calendar"))
    assert resp.status_code == 200
    content = resp.content.decode()
    assert "tl-room-thumb" in content
    assert "room-placeholder.svg" in content  # other_room ไม่มีรูป ต้องได้ placeholder
    assert other_room.code in content


@pytest.fixture
def logged_in_user(client):
    unit = Unit.objects.create(code="V6C", name="แผนกสื่อสาร")
    user = User.objects.create_user(
        username="user_v6c", email="user_v6c@signalschool.ac.th", password="Password-2569", unit=unit
    )
    client.force_login(user)
    return user


def test_book_search_renders_cover_photo_and_placeholder(client, room, logged_in_user):
    other_room = _make_room("ROOM-C7")
    save_room_photo(resource=room, image=_make_upload(), is_cover=True)
    tomorrow = timezone.localdate() + timezone.timedelta(days=1)
    date_text = f"{tomorrow.day:02d}/{tomorrow.month:02d}/{tomorrow.year + 543}"

    resp = client.get(reverse("bookings:book_search"), {"search": "1", "date": date_text, "start": "09:00", "end": "10:00"})
    assert resp.status_code == 200
    content = resp.content.decode()
    assert "room-card-thumb" in content
    assert "room-placeholder.svg" in content
    assert other_room.code in content


@pytest.fixture
def cohort_setup(room):
    other_room = _make_room("ROOM-C8")
    unit = Unit.objects.create(code="V6C2", name="แผนกวิชาการ")
    supervisor = User.objects.create_user(
        username="sup_v6c", email="sup_v6c@signalschool.ac.th", password="Password-2569", unit=unit
    )
    today = timezone.localdate()
    cohort = CourseLodgingCohort.objects.create(
        title="นนส. เหล่า ส. รุ่น 62",
        slug="nns-62",
        supervisor=supervisor,
        unit=unit,
        check_in_date=today,
        check_out_date=today + timezone.timedelta(days=14),
        beds_per_room=2,
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
        is_active=True,
    )
    cohort.rooms.add(room, other_room)
    return cohort, room, other_room


def test_student_portal_renders_gallery_trigger_and_placeholder(client, cohort_setup):
    cohort, room, other_room = cohort_setup
    save_room_photo(resource=room, image=_make_upload(), is_cover=True)

    resp = client.get(reverse("bookings:lodging_portal", args=[cohort.slug]))
    assert resp.status_code == 200
    content = resp.content.decode()
    assert "room-photo-trigger" in content
    assert "room-placeholder.svg" in content
    assert "roomGalleryDialog" in content


def test_student_portal_photo_prefetch_avoids_n_plus_one(client, cohort_setup):
    cohort, room, other_room = cohort_setup
    save_room_photo(resource=room, image=_make_upload(), is_cover=True)
    save_room_photo(resource=other_room, image=_make_upload(name="other.png"), is_cover=True)

    from django.db import connection

    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(reverse("bookings:lodging_portal", args=[cohort.slug]))
        assert resp.status_code == 200
    baseline_queries = len(ctx.captured_queries)

    third_room = _make_room("ROOM-C9")
    cohort.rooms.add(third_room)
    save_room_photo(resource=third_room, image=_make_upload(name="third.png"), is_cover=True)

    with CaptureQueriesContext(connection) as ctx2:
        resp = client.get(reverse("bookings:lodging_portal", args=[cohort.slug]))
        assert resp.status_code == 200

    assert len(ctx2.captured_queries) == baseline_queries


def test_resource_cover_photo_and_photo_url_list_use_prefetch_cache_without_extra_query(room):
    """cover_photo/photo_url_list ต้องอ่านจาก prefetch cache โดยตรง ไม่ยิง query ซ้ำต่อห้อง"""
    save_room_photo(resource=room, image=_make_upload(name="a.png"), order=1)
    save_room_photo(resource=room, image=_make_upload(name="b.png"), order=0, is_cover=True)

    from django.db import connection

    with CaptureQueriesContext(connection) as ctx:
        fetched = list(Resource.objects.filter(pk=room.pk).prefetch_related("photos"))
        r = fetched[0]
        assert r.cover_photo is not None
        assert r.cover_photo.is_cover is True
        assert len(r.photo_url_list) == 2
    assert len(ctx.captured_queries) == 2  # 1: resource, 1: prefetch photos — ไม่มี query เพิ่มตอนอ่าน cover/list
