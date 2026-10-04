"""Synchronize the real lodging-room registry from the authoritative floor-plan data.

Preview is the default. Database writes require --apply. The command never renames,
retires, reallocates, or mutates existing lodging rooms; incompatible existing rows
fail closed so operators can reconcile them explicitly.
"""
from dataclasses import dataclass

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Unit
from bookings.lodging_about_data import (
    FLOOR4_AIR_ROOMS,
    FLOOR4_FAN_ROOMS,
    FLOOR4_BEDS_PER_ROOM,
    FLOOR5_AIR_ROOMS,
    FLOOR5_BEDS_PER_ROOM,
    TOTAL_BEDS,
    TOTAL_ROOMS,
)
from resources.models import Resource, ResourceRule


BUILDING_NAME = "อาคารที่พักนักเรียน"
LEGACY_PILOT_CODES = ("DORM-101", "DORM-102", "DORM-103", "DORM-104")


@dataclass(frozen=True)
class RoomSpec:
    number: int
    floor: str
    capacity: int
    cooling: str

    @property
    def preferred_code(self) -> str:
        return f"DORM-{self.number}"

    @property
    def aliases(self) -> tuple[str, str]:
        return (str(self.number), self.preferred_code)

    @property
    def equipment(self) -> str:
        cooling_label = "เครื่องปรับอากาศ" if self.cooling == "air" else "พัดลม"
        return f"เตียง {self.capacity} ชุด\n{cooling_label}"

    @property
    def name(self) -> str:
        return f"ห้องพัก {self.number} ({self.capacity} เตียง)"


def authoritative_room_specs() -> tuple[RoomSpec, ...]:
    specs = []
    specs.extend(RoomSpec(n, "4", FLOOR4_BEDS_PER_ROOM, "air") for n in FLOOR4_AIR_ROOMS)
    specs.extend(RoomSpec(n, "4", FLOOR4_BEDS_PER_ROOM, "fan") for n in FLOOR4_FAN_ROOMS)
    specs.extend(RoomSpec(n, "5", FLOOR5_BEDS_PER_ROOM, "air") for n in FLOOR5_AIR_ROOMS)
    return tuple(sorted(specs, key=lambda item: item.number))


def compatibility_errors(resource: Resource, spec: RoomSpec) -> list[str]:
    errors = []
    if resource.resource_type != Resource.Type.ROOM:
        errors.append("resource_type ไม่ใช่ room")
    if resource.room_category != Resource.Category.LODGING:
        errors.append("room_category ไม่ใช่ lodging")
    if resource.floor and resource.floor != spec.floor:
        errors.append(f"floor={resource.floor!r} แต่แปลนเป็น {spec.floor!r}")
    if resource.capacity != spec.capacity:
        errors.append(f"capacity={resource.capacity} แต่แปลนเป็น {spec.capacity}")
    return errors


class Command(BaseCommand):
    help = "Preview/sync ทะเบียนห้องพักจริง 87 ห้องจาก lodging_about_data (ต้อง --apply จึงเขียน DB)"

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="สร้างห้องที่ขาดหลัง preflight ผ่านทั้งหมด")
        parser.add_argument(
            "--owner-unit",
            default="HQ",
            help="รหัสหน่วยเจ้าของสำหรับห้องที่สร้างใหม่เท่านั้น (ค่าเริ่มต้น HQ)",
        )

    def handle(self, *args, **options):
        specs = authoritative_room_specs()
        if len(specs) != TOTAL_ROOMS or sum(item.capacity for item in specs) != TOTAL_BEDS:
            raise CommandError("authoritative lodging inventory totals are inconsistent")

        create_specs: list[RoomSpec] = []
        compatible_existing: list[tuple[RoomSpec, Resource]] = []
        inactive_existing: list[tuple[RoomSpec, Resource]] = []
        conflicts: list[str] = []

        for spec in specs:
            matches = list(Resource.objects.filter(code__in=spec.aliases).order_by("code"))
            if not matches:
                create_specs.append(spec)
                continue
            if len(matches) > 1:
                conflicts.append(
                    f"ห้อง {spec.number}: พบทั้ง alias {', '.join(room.code for room in matches)} ทำให้ mapping กำกวม"
                )
                continue
            room = matches[0]
            errors = compatibility_errors(room, spec)
            if errors:
                conflicts.append(f"{room.code}: " + "; ".join(errors))
                continue
            compatible_existing.append((spec, room))
            if room.status != Resource.Status.ACTIVE:
                inactive_existing.append((spec, room))

        legacy_active = list(
            Resource.objects.filter(code__in=LEGACY_PILOT_CODES, status=Resource.Status.ACTIVE)
            .order_by("code")
            .values_list("code", flat=True)
        )

        self.stdout.write(
            f"AUTHORITATIVE inventory: rooms={TOTAL_ROOMS} beds={TOTAL_BEDS} "
            f"floor4={len(FLOOR4_AIR_ROOMS) + len(FLOOR4_FAN_ROOMS)} floor5={len(FLOOR5_AIR_ROOMS)}"
        )
        self.stdout.write(
            f"PLAN create={len(create_specs)} existing={len(compatible_existing)} "
            f"inactive={len(inactive_existing)} conflicts={len(conflicts)} legacy_active={len(legacy_active)}"
        )
        if legacy_active:
            self.stdout.write(
                self.style.WARNING(
                    "LEGACY pilot rooms remain untouched: " + ", ".join(legacy_active)
                )
            )
        for conflict in conflicts:
            self.stderr.write(self.style.ERROR("CONFLICT: " + conflict))

        if conflicts:
            raise CommandError("พบทะเบียนห้องขัดกับ source-of-truth; ไม่เขียนข้อมูลใด ๆ")

        if not options["apply"]:
            self.stdout.write(self.style.WARNING("PREVIEW ONLY: no database changes were made. Use --apply to create missing rooms."))
            return

        try:
            owner_unit = Unit.objects.get(code=options["owner_unit"], is_active=True)
        except Unit.DoesNotExist as exc:
            raise CommandError(f"ไม่พบหน่วยเจ้าของที่เปิดใช้ code={options['owner_unit']}") from exc

        created_count = 0
        rules_created = 0
        with transaction.atomic():
            for spec in create_specs:
                room = Resource.objects.create(
                    code=spec.preferred_code,
                    lodging_cooling=spec.cooling,
                    name=spec.name,
                    resource_type=Resource.Type.ROOM,
                    room_category=Resource.Category.LODGING,
                    building=BUILDING_NAME,
                    floor=spec.floor,
                    capacity=spec.capacity,
                    owner_unit=owner_unit,
                    fixed_equipment=spec.equipment,
                    status=Resource.Status.ACTIVE,
                )
                ResourceRule.objects.create(
                    resource=room,
                    approval_policy=ResourceRule.ApprovalPolicy.AUTO,
                    buffer_before_min=0,
                    buffer_after_min=0,
                )
                created_count += 1
                rules_created += 1

            for _spec, room in compatible_existing:
                _rule, rule_created = ResourceRule.objects.get_or_create(
                    resource=room,
                    defaults={
                        "approval_policy": ResourceRule.ApprovalPolicy.AUTO,
                        "buffer_before_min": 0,
                        "buffer_after_min": 0,
                    },
                )
                rules_created += int(rule_created)

        self.stdout.write(
            self.style.SUCCESS(
                f"APPLIED rooms_created={created_count} rules_created={rules_created} "
                f"existing_preserved={len(compatible_existing)} legacy_untouched={len(legacy_active)}"
            )
        )
        if inactive_existing:
            self.stdout.write(
                self.style.WARNING(
                    "INACTIVE preserved (not auto-enabled): "
                    + ", ".join(room.code for _spec, room in inactive_existing)
                )
            )
