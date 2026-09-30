from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from accounts.models import Unit
from bookings.lodging_about_data import TOTAL_BEDS, TOTAL_ROOMS
from bookings.lodging_operations import GeneralRequestForm
from bookings.lodging_room_details import room_details
from resources.management.commands.sync_lodging_room_registry import authoritative_room_specs
from resources.models import Resource, ResourceRule


@pytest.fixture
def hq(db):
    return Unit.objects.create(code="HQ", name="กองบังคับการ")


def test_authoritative_specs_are_87_rooms_234_beds():
    specs = authoritative_room_specs()
    assert len(specs) == TOTAL_ROOMS == 87
    assert sum(item.capacity for item in specs) == TOTAL_BEDS == 234
    assert {item.number for item in specs}.isdisjoint({408, 409, 410})


@pytest.mark.django_db
def test_preview_is_read_only_and_reports_full_create_plan(hq):
    out = StringIO()
    call_command("sync_lodging_room_registry", stdout=out)

    assert Resource.objects.count() == 0
    assert ResourceRule.objects.count() == 0
    text = out.getvalue()
    assert "PLAN create=87 existing=0 inactive=0 conflicts=0" in text
    assert "PREVIEW ONLY" in text


@pytest.mark.django_db
def test_apply_creates_real_inventory_and_makes_plan_room_resolvable(hq):
    out = StringIO()
    call_command("sync_lodging_room_registry", apply=True, stdout=out)

    rooms = Resource.objects.filter(room_category=Resource.Category.LODGING)
    assert rooms.count() == 87
    assert sum(rooms.values_list("capacity", flat=True)) == 234
    assert ResourceRule.objects.filter(resource__in=rooms).count() == 87
    assert not rooms.filter(code__in=["DORM-408", "DORM-409", "DORM-410"]).exists()

    room401 = rooms.get(code="DORM-401")
    room417 = rooms.get(code="DORM-417")
    room501 = rooms.get(code="DORM-501")
    assert (room401.floor, room401.capacity) == ("4", 2)
    assert "เครื่องปรับอากาศ" in room401.fixed_equipment
    assert (room417.floor, room417.capacity) == ("4", 2)
    assert "พัดลม" in room417.fixed_equipment
    assert (room501.floor, room501.capacity) == ("5", 4)
    assert "เครื่องปรับอากาศ" in room501.fixed_equipment

    detail = room_details(425)
    assert detail is not None
    assert detail["code"] == "DORM-425"
    assert detail["capacity"] == 2
    assert detail["active"] is True
    assert detail["request_url"].endswith(f"?room_id={rooms.get(code='DORM-425').pk}")


@pytest.mark.django_db
def test_apply_is_idempotent_and_preserves_existing_compatible_room(hq):
    existing = Resource.objects.create(
        code="401",
        name="ชื่อเดิมที่เจ้าหน้าที่ตั้ง",
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING,
        building="อาคารเดิม",
        floor="4",
        capacity=2,
        owner_unit=hq,
        status=Resource.Status.ACTIVE,
    )

    call_command("sync_lodging_room_registry", apply=True, stdout=StringIO())
    call_command("sync_lodging_room_registry", apply=True, stdout=StringIO())

    assert Resource.objects.filter(room_category=Resource.Category.LODGING).count() == 87
    existing.refresh_from_db()
    assert existing.name == "ชื่อเดิมที่เจ้าหน้าที่ตั้ง"
    assert existing.building == "อาคารเดิม"
    assert not Resource.objects.filter(code="DORM-401").exists()
    assert ResourceRule.objects.filter(resource=existing).count() == 1


@pytest.mark.django_db
def test_apply_fails_closed_on_incompatible_existing_alias_without_partial_writes(hq):
    Resource.objects.create(
        code="DORM-401",
        name="ชนกับห้องอื่น",
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.CLASSROOM,
        floor="4",
        capacity=2,
        owner_unit=hq,
    )

    with pytest.raises(CommandError, match="ไม่เขียนข้อมูลใด ๆ"):
        call_command("sync_lodging_room_registry", apply=True, stdout=StringIO(), stderr=StringIO())

    assert Resource.objects.count() == 1
    assert ResourceRule.objects.count() == 0


@pytest.mark.django_db
def test_apply_fails_closed_when_both_numeric_and_dorm_alias_exist(hq):
    for code in ("401", "DORM-401"):
        Resource.objects.create(
            code=code,
            name=code,
            resource_type=Resource.Type.ROOM,
            room_category=Resource.Category.LODGING,
            floor="4",
            capacity=2,
            owner_unit=hq,
        )

    with pytest.raises(CommandError, match="ไม่เขียนข้อมูลใด ๆ"):
        call_command("sync_lodging_room_registry", apply=True, stdout=StringIO(), stderr=StringIO())

    assert Resource.objects.count() == 2


@pytest.mark.django_db
def test_legacy_pilot_rooms_are_reported_but_never_modified(hq):
    legacy = Resource.objects.create(
        code="DORM-101",
        name="legacy pilot",
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING,
        building="อาคารพัก 1",
        floor="1",
        capacity=4,
        owner_unit=hq,
        status=Resource.Status.ACTIVE,
    )
    out = StringIO()
    call_command("sync_lodging_room_registry", apply=True, stdout=out)

    legacy.refresh_from_db()
    assert legacy.name == "legacy pilot"
    assert legacy.floor == "1"
    assert legacy.capacity == 4
    assert "legacy_active=1" in out.getvalue()
    assert "LEGACY pilot rooms remain untouched: DORM-101" in out.getvalue()


@pytest.mark.django_db
def test_apply_requires_active_owner_unit():
    with pytest.raises(CommandError, match="ไม่พบหน่วยเจ้าของที่เปิดใช้"):
        call_command("sync_lodging_room_registry", apply=True, stdout=StringIO())
    assert Resource.objects.count() == 0


@pytest.mark.django_db
def test_public_form_falls_back_to_legacy_until_real_inventory_exists(hq):
    legacy = Resource.objects.create(
        code="DORM-101", name="legacy pilot", resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING, floor="1", capacity=4, owner_unit=hq,
        status=Resource.Status.ACTIVE,
    )
    form = GeneralRequestForm()
    assert list(form.fields["room"].queryset.values_list("pk", flat=True)) == [legacy.pk]


@pytest.mark.django_db
def test_public_form_keeps_fallback_if_authoritative_inventory_is_partial(hq):
    legacy = Resource.objects.create(
        code="DORM-101", name="legacy pilot", resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING, floor="1", capacity=4, owner_unit=hq,
        status=Resource.Status.ACTIVE,
    )
    partial = Resource.objects.create(
        code="DORM-401", name="ห้องพัก 401", resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING, floor="4", capacity=2, owner_unit=hq,
        status=Resource.Status.ACTIVE,
    )

    codes = set(GeneralRequestForm().fields["room"].queryset.values_list("code", flat=True))
    assert codes == {legacy.code, partial.code}


@pytest.mark.django_db
def test_public_form_hides_legacy_after_authoritative_inventory_is_synced(hq):
    legacy = Resource.objects.create(
        code="DORM-101", name="legacy pilot", resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING, floor="1", capacity=4, owner_unit=hq,
        status=Resource.Status.ACTIVE,
    )
    call_command("sync_lodging_room_registry", apply=True, stdout=StringIO())

    form = GeneralRequestForm()
    codes = list(form.fields["room"].queryset.values_list("code", flat=True))
    assert len(codes) == 87
    assert "DORM-425" in codes
    assert legacy.code not in codes


@pytest.mark.django_db
def test_general_request_prefills_authoritative_room_from_popup(client, hq):
    call_command("sync_lodging_room_registry", apply=True, stdout=StringIO())
    room = Resource.objects.get(code="DORM-425")

    response = client.get(f"/lodging/request/?room_id={room.pk}")

    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert f'value="{room.pk}" selected' in html
    assert "DORM-425" in html
    assert "DORM-101" not in html
