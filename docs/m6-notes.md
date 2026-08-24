# SIGROOM — บันทึกการพัฒนา M6 ส่วน 6A

วันที่ตรวจ: 24 ส.ค. 2569
ขอบเขต: ทำเฉพาะ A1–A7 ใน `docs/m6-plan.md` · ยังไม่เริ่ม 6B · ยังไม่ commit เพื่อรอตรวจรับ

## A1 สถานะการใช้งานและ S15

- `run_jobs` เรียกงานปิดการจองที่อนุมัติแล้ว จาก `upcoming` เป็น `used` เมื่อ `end_at < now`
- งานรันซ้ำได้: เปลี่ยนเฉพาะแถวที่ยังเป็น `upcoming`; ไม่ทับ `displaced`, `room_unavailable`, `no_show` หรือ `used`
- หน้า `/usage/` เปิดให้ superuser และ custodians ของห้องเท่านั้น เห็นรายการที่สิ้นสุดตั้งแต่ 3 วันที่ผ่านมาถึงวันนี้ เฉพาะห้องที่รับผิดชอบ
- เปลี่ยนเป็น “ใช้งานแล้ว” หรือ “ไม่มาใช้” ได้หลังสิ้นสุดรายการและไม่เกิน 3 วันตามวันที่ท้องถิ่น; สถานะถูกย้าย/ห้องใช้งานไม่ได้เปลี่ยนทับไม่ได้
- เมื่อบันทึก no-show ระบบแจ้งเฉพาะผู้จองด้วยรหัส `[BK-…]` และบันทึก audit

## A2 รายงาน S16 และ CSV

หน้า `/reports/` เปิดให้ superuser, ผู้อนุมัติที่ผูกกับห้อง และ custodian ที่ผูกกับห้อง รายงาน/CSV ใช้ room scope ชุดเดียวกัน จึงไม่สามารถเปลี่ยน query string เพื่อเห็นห้องอื่นได้ ผู้ใช้ทั่วไปได้ HTTP 403

ตัวกรองรองรับเดือนทั้ง พ.ศ. (`2569-08`) และ ค.ศ. (`2026-08`) พร้อมห้องและหน่วย รายงานมี 5 ชุด:

1. อัตราการใช้ห้อง: จัดกลุ่มห้อง/ประเภทกิจกรรม/หน่วย; ชั่วโมงใช้จริงนับ `USED`; ชั่วโมงจองอนุมัตินับสถานะคำขอ `APPROVED`; ชั่วโมงให้บริการคำนวณจากเวลาเปิด–ปิดรายห้องคูณจำนวนวันในเดือน
2. ยกเลิกและ no-show: จัดกลุ่มหน่วย/บุคคล; ไม่นับร่าง; แสดงจำนวนและอัตราต่อการจองทั้งหมด
3. การอนุมัติ: รวม booking และ amendment จากประวัติ Approval; เฉลี่ย submit→approve/reject; นับเกิน SLA ด้วยกฎ SLA เดิม; แยกหมดอายุ (ผู้ดำเนินการ “ระบบ”)
4. บังคับย้าย: วันเวลา พ.ศ. ห้อง รหัสการจอง เลขอ้างอิง ผู้สั่ง และสถานะรับทราบ
5. อุปกรณ์ส่วนกลาง: จำนวนครั้งและชั่วโมงจากการจองที่อนุมัติและมีสถานะ `USED`

CSV ทุกไฟล์เริ่มด้วย UTF-8 BOM และผ่านเทส byte `EF BB BF` เพื่อเปิดภาษาไทยใน Excel ได้
การดาวน์โหลด CSV คำนวณเฉพาะรายงานที่เลือก ไม่คำนวณรายงานอีก 4 ชุดโดยไม่จำเป็น

ข้อจำกัดที่ยอมรับใน pilot: ยังไม่เก็บสถิติ “ค้นหาแล้วอุปกรณ์ชน” และยังไม่ส่งออก PDF

## A3 Audit log

- เพิ่ม `audit.AuditLog`: เวลา ผู้กระทำ entity/id action before/after และ IP
- ป้องกันแก้/ลบทั้ง `model.save()`, `model.delete()`, `QuerySet.update()` และ `QuerySet.delete()`; Admin เป็นอ่าน/ค้น/กรองอย่างเดียวสำหรับ superuser หรือเจ้าหน้าที่ความมั่นคงสารสนเทศ
- จุดบันทึกครอบคลุมสร้าง/ส่ง/แก้/ยกเลิก booking, ชุดการจอง, approve/reject/expire, amendment submit/approve/reject/withdraw/expire, preemption/acknowledge/deemed acknowledge, outage create/end, usage status, login/logout/login failed และการแก้ทะเบียนที่ระบุในแผน
- request context ส่ง actor/IP ให้ service และ registry signals โดยไม่ใช้ middleware ดักสร้าง log ทุก request
- snapshot ของ User ไม่เก็บ `password` หรือ `last_login`; การเปลี่ยนรหัสบันทึกเพียง `password_changed=true` และ login สำเร็จสร้าง audit เพียงเหตุการณ์ login โดยไม่สร้าง registry update ซ้ำ
- การบังคับ `REVOKE UPDATE, DELETE ON audit_auditlog` ที่ PostgreSQL ทำในขั้นติดตั้งเครื่องหน่วย B2 เพราะฐานพัฒนายังใช้บัญชี `postgres`

## A4 บัญชีจริงและ S17

คำสั่ง:

```powershell
uv run manage.py import_users .\users.csv --output-dir .\private-output
```

หัว CSV: `username,email,rank,first_name,last_name,unit_code,phone,service_number`

- ตรวจโดเมนอีเมล หน่วยที่เปิดใช้ และข้อมูลซ้ำก่อนสร้างแต่ละแถว; แถวเสียรายงานเลขแถวแล้วข้าม
- สุ่มรหัสเริ่มต้น 12 ตัว แล้วออก `imported-users-YYYYMMDD.csv` แบบ UTF-8 BOM มีเฉพาะ username/รหัสเริ่มต้น
- ไฟล์รหัสถูก gitignore; ผู้ดูแลต้องแจกด้วยมือและลบทันทีหลังแจกครบ
- ผู้ใช้ที่นำเข้าและบัญชี demo ที่สร้างใหม่ด้วย `seed_pilot --demo-users` มี `must_change_password=True`; การรัน seed ซ้ำไม่เปลี่ยนรหัสหรือ flag ของบัญชีเดิม
- หลัง login ทุกหน้าถูก redirect ไป S17 จนเปลี่ยนรหัสสำเร็จ; กฎตั้งรหัส/ปิด flag/audit อยู่ใน `accounts/services.py` และทำใน transaction เดียว
- request แบบ HTMX ได้ `HX-Redirect` ไป S17 จึงไม่ฝังหน้าเต็มลง fragment; auth recovery URLs ยังคงเข้าถึงได้

## A5 Production helpers และสำรองข้อมูล

- เพิ่ม `waitress` และ `whitenoise`; `scripts/run-server.ps1` เปิด WSGI ที่ `0.0.0.0:8000`
- `DJANGO_SECURE=0` ทำให้ DEBUG=0 ใช้ HTTP ภายใน LAN ได้โดยไม่ redirect HTTPS/ไม่ตั้ง secure cookies/HSTS; เมื่อมี TLS ต้องเปลี่ยนเป็น `1`
- เมื่อ DEBUG=0 ระบบเตือนตอน startup ทั้งกรณีไม่ได้กำหนด `DJANGO_SECURE` และกรณีกำหนด `0` เพื่อไม่ให้ลืมค่าระหว่าง pilot/deploy จริง
- `CSRF_TRUSTED_ORIGINS` อ่านรายการคั่นด้วย comma จาก `.env`
- `backup.ps1` ใช้ `pg_dump -Fc`, เขียน log สำเร็จ/ล้มเหลว และลบเฉพาะ dump เก่าให้เหลือ 30 ชุด
- `restore-test.ps1` สร้างใหม่เฉพาะฐานชื่อ `ogn_room_restore_test`, กู้ dump ล่าสุด และเทียบจำนวนแถว `bookings_booking`
- ทั้งสองสคริปต์อ่าน `.env`; ตัวแปร process `SIGROOM_BACKUP_DIR` ใช้ override ปลายทางชั่วคราวตอนทดสอบได้
- สคริปต์ PowerShell บันทึกเป็น UTF-8 BOM เพื่อให้ Windows PowerShell 5 อ่านภาษาไทยได้ถูกต้อง

ผลทดลองจริงบนเครื่องพัฒนา:

- หลัง apply migration M6 แล้ว สำรองล่าสุดสำเร็จเป็น `backups/sigroom-20260824-1245.dump` และมี `backup-log.txt` (ทั้งโฟลเดอร์ถูก gitignore)
- กู้เข้า `ogn_room_restore_test` สำเร็จ และ Booking ฐานจริง/ฐานกู้คืนตรงกัน 1 แถว
- ฐานทดสอบ restore ถูกเก็บไว้เพื่อให้ตรวจด้วยตา; สคริปต์จะลบและสร้างเฉพาะฐานชื่อนี้ใหม่เมื่อรันครั้งถัดไป

ก่อนใช้งานจริงต้องใส่ `BACKUP_DIR` ใน `.env` ให้เป็นดิสก์หรือ network share คนละเครื่องกับเครื่องบริการ

## A6–A7 ผลตรวจ

```text
Django system check: 0 issues
makemigrations --check --dry-run: No changes detected
pytest: 80 passed (59 เดิม + 21 M6/regression)
dev database migrate: accounts.0002 + audit.0001 ผ่าน
collectstatic: 171 files copied และ post-processed
waitress command: เรียกใช้งานได้
PowerShell syntax: backup.ps1 / restore-test.ps1 / run-server.ps1 ผ่าน
backup/restore test: ผ่าน
```

เทส M6 ครอบคลุม auto-USED/idempotent/สถานะพิเศษ, no-show/สิทธิ์/3 วัน/notification, รายงาน 1–5/ตัวกรอง/room scope/CSV BOM/ปี พ.ศ./คำนวณ CSV ชุดเดียว, audit append-only/login fail/redact password/ไม่ log ซ้ำ, import users, seed ไม่รีเซ็ตรหัส, S17/HTMX และ HTTP pilot warning

## ผลแก้หลังตรวจรับเชิงลึก

แก้ครบ 10 ประเด็นที่ verifier ยืนยันแล้ว: password hash ไม่เข้า audit, seed ไม่รีเซ็ตรหัสเดิม, secure startup warning, S17 รองรับ HTMX/auth recovery, preemption ใช้ปี พ.ศ., เวลาให้บริการข้ามคืนถูก validation และรายงานไม่ติดลบ, login audit ไม่ซ้ำ, CSV คำนวณเฉพาะชุดที่ขอ, ย้ายกฎ S17 เข้า service และใช้ `Resource.Type.ROOM` แทน magic string

ตรวจฐานพัฒนาหลังแก้แบบอ่านอย่างเดียว: AuditLog มี 0 แถว และไม่พบ password material ค้าง จึงไม่ต้องใช้คำสั่งลบที่ขัดกับ append-only

## ดูผลด้วยตา

1. รัน `uv run manage.py migrate` แล้ว `uv run manage.py runserver`
2. ปรับการจองที่อนุมัติให้จบในอดีต แล้วรัน `uv run manage.py run_jobs` → สถานะเป็น “ใช้งานแล้ว”
3. เข้า `/usage/` ด้วย custodian/admin → สลับเป็น “ไม่มาใช้” → ผู้จองเห็นกระดิ่ง
4. เข้า `/reports/` → กรองเดือน/ห้อง/หน่วย → ดาวน์โหลด CSV และเปิดด้วย Excel
5. Admin → Audit log → เปิดดูได้แต่ไม่มีปุ่มบันทึก/ลบ
6. ทดลอง `import_users` → login บัญชีใหม่ → ระบบบังคับไปหน้าตั้งรหัสผ่าน S17
7. กำหนด `BACKUP_DIR` แล้วรัน `scripts\backup.ps1` และ `scripts\restore-test.ps1`

## งานต่อไปหลังตรวจรับ 6A

เริ่ม 6B ตามลำดับ: B1 ขัด UX/UI → B2 runbook ติดตั้ง/DB REVOKE/ความปลอดภัย → B3 pilot checklist ห้าม deploy หรือเริ่ม pilot ก่อนตรวจรับและทำรายการเหล่านี้ครบ
