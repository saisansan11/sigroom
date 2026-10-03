# PR-1 ห้องสอนออนไลน์

ฐาน GitHub ที่ตรวจแล้ว: `feat/lodging-v5-2` = `06ac114`; งานตั้งต้น `15ed031` ตรงกับ origin นำ base เข้าด้วย merge commit โดยไม่แตะ PR #82
Branch: `feat/online-quick-booking` → base `feat/lodging-v5-2`

งาน: คงฟอร์ม radio/ปฏิทิน HTMX และข้อมูลสถานที่จาก branch ตั้งต้น เพิ่ม script 12 บรรทัดให้วันเดียวกันในชิปและปฏิทินแสดงตรงกัน และส่งค่าฟอร์มปัจจุบันตอนเปลี่ยนเดือน เพิ่มคำบอกเวลาจริงของช่วงเช้า/บ่ายและลดความเด่นแถวเวลาเริ่ม

ตรวจ diff ครบแล้ว ไม่มีการเปลี่ยน Booking Core หรือ constraint กันจองซ้อน Migration `resources.0006` เปลี่ยนเฉพาะข้อมูลสถานที่ค่าตั้งต้น ไม่ทับค่าที่เจ้าหน้าที่แก้เอง

ผลบน Python 3.12.10 และ PostgreSQL local แยกชื่อ `sigroom_online_beta_qa`:
- `uv sync --python 3.12` ผ่าน
- `uv run pytest --tb=short -q`: **866 passed** (140.35s) รวม targeted online tests
- `uv run manage.py check`: ไม่มีปัญหา
- `uv run manage.py makemigrations --check --dry-run`: No changes detected
- `npm run test:interaction`: **10 passed**, ไม่มี skip
- `git diff --check`: ผ่าน

Browser QA ใช้ครูสมมติที่มีกลุ่ม signalschool-teacher ไม่มีสิทธิ์ผู้ดูแล บน 390×844 และ 1280×900: login เข้าหน้าจอง, ยืนยันพรุ่งนี้ 09:00–10:00 ครั้งเดียว, เปลี่ยนวัน/เวลา/ระยะ/หลักสูตรสี่ตัวเลือกแล้วจอง, เลือกวันที่ซ้ำจากปฏิทิน, สลับเดือนโดยคงวันเดิม, preset เช้า 08:00–12:00, ไม่มีห้องว่างพร้อมช่วงใกล้เคียง, ไม่ล้นจอ, console error ไม่มี ภาพจริงใน `docs/qa/online-beta/pr1/`

Test เดิมที่แก้ใน branch ตั้งต้น: `bookings/tests_lodging_service_gateway.py::test_online_teaching_section_exposes_exact_three_signal_school_rooms` เปลี่ยนตรวจความจุเป็นสถานที่ตามแผน ไม่ลบหรือ skip

ข้อสงสัย: การเปลี่ยนทุกตัวเลือกนับ 4 ตัวเลือก + 1 ยืนยัน ไม่รวมเปิดปฏิทินซึ่งเป็นทางเลือกเพิ่มเติมของวันที่อยู่นอกแถวชิป คง fallback ปฏิทิน 90 วันจากแผนตั้งต้นเมื่อห้องไม่มี max_advance_days ไม่เพิ่มกฎธุรกิจใหม่

ยังไม่ได้ทำ: ทดสอบ browser เมื่อปิด JavaScript (ตรวจโครง noscript แล้ว), production/Cloud/deploy ผู้ใช้เป็นผู้ทำ CI จะตรวจจาก PR ที่เปิด

วิธีดูผลในเครื่องที่มี `.env` สำหรับฐานข้อมูลทดสอบ:
```powershell
git fetch origin
git switch feat/online-quick-booking
uv sync --python 3.12
uv run manage.py migrate
uv run manage.py runserver
```
เปิด `/accounts/login/` ด้วยครูที่อยู่กลุ่ม signalschool-teacher และมีสังกัด/โทรศัพท์ แล้วตรวจหน้าจอง `/online/` ไม่ใช้ superuser แทนครู

ขั้นต่อไป PR-2 แตก `feat/service-shell` จาก branch นี้ อ่าน runbook และสถานะจริงอีกครั้งก่อนแก้เมนู รักษาการตรวจสิทธิ์ server-side และข้อมูล booking เดิม
