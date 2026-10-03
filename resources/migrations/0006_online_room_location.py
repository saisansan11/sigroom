from django.db import migrations

ROOM_CODES = ("STU-ONLINE-1", "STU-ONLINE-2", "STU-ONLINE-3")
OLD = {"building": "อาคาร บก.กศ.", "floor": "1"}
NEW = {"building": "บก.กศ.รร.ส.สส.", "floor": "3"}


def _move(apps, source, target):
    # แก้เฉพาะแถวที่ยังเป็นค่าตั้งต้นเดิม ค่าที่ผู้ดูแลแก้เองใน Admin จะไม่ถูกทับ
    Resource = apps.get_model("resources", "Resource")
    Resource.objects.filter(code__in=ROOM_CODES, **source).update(**target)


def forwards(apps, schema_editor):
    _move(apps, OLD, NEW)


def backwards(apps, schema_editor):
    _move(apps, NEW, OLD)


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0005_alter_blackout_room_category_and_more"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
