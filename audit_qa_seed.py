import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.conf import settings
assert settings.DATABASES['default']['NAME'] == 'sigroom_audit_qa_20261003'
from datetime import datetime, time, timedelta
from django.utils import timezone
from accounts.models import Unit, User
from resources.models import Resource, ResourceRule, ResourceOutage
from bookings.models import Booking
from bookings.services import submit_booking
unit = Unit.objects.create(code='QA', name='หน่วยทดสอบ')
user = User.objects.create_user(username='audit-qa', password='Local-QA-20261003!', unit=unit, phone='0810000000', first_name='ทดสอบ')
room = Resource.objects.create(code='QA-OPEN', name='ห้องทดสอบยกเลิก')
ResourceRule.objects.create(resource=room)
start = timezone.make_aware(datetime.combine(timezone.localdate()+timedelta(days=7), time(9)))
booking = Booking.objects.create(room=room, requester=user, unit=unit, title='ทดสอบยกเลิก', responsible_name='ผู้ทดสอบ', responsible_phone='0810000000', start_at=start, end_at=start+timedelta(hours=1))
submit_booking(booking)
closed = Resource.objects.create(code='QA-CLOSED', name='ห้องปิดซ่อมไม่มีกฎ')
ResourceOutage.objects.create(resource=closed, created_by=user, reason='ปิดซ่อม QA', start_at=start, end_at=start+timedelta(hours=1))
print('Booking URL: /bookings/'+str(booking.pk)+'/')
print('Search URL: /book/?date='+start.date().isoformat()+'&start=09:00&end=10:00')
