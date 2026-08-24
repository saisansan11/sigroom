# SIGROOM — แผน M6: ปิดระบบให้พร้อม pilot

สถานะ: **ร่างเพื่อให้ผู้ใช้ดูก่อน → 6A ให้ Codex, 6B ทำร่วมกับ Claude**
อ้างอิง: SRS §9 (สถานะการใช้งาน), §13 (รายงาน), NF-01/02 (audit), NF-04 (สำรองข้อมูล), build-plan "ค้างจาก M1"

## ส่วน 6A — ฟังก์ชัน (Codex)

### A1 สถานะการใช้งานและ no-show (SRS §9)
- `run_scheduled_jobs` เพิ่มงาน: การจอง APPROVED + UPCOMING ที่ `end_at < now` → `usage_status=USED` อัตโนมัติ (เว้น DISPLACED / ROOM_UNAVAILABLE) — idempotent ไม่แจ้งเตือน
- **S15 การใช้งานห้อง** `/usage/` (เจ้าหน้าที่ดูแลห้อง + ผู้ดูแลระบบ): รายการจองของห้องที่ตนดูแล ช่วง 3 วันหลังสุดถึงวันนี้ · ปุ่มสลับ [ใช้งานแล้ว] / [ไม่มาใช้] ได้ภายใน 3 วันหลังวันใช้งาน (แก้ทับค่าอัตโนมัติได้) เกิน 3 วัน → ปุ่มปิด
- บันทึก no-show → แจ้งผู้จอง "การจอง [BK-…] ถูกบันทึกว่าไม่มาใช้" (ไม่แจ้งหัวหน้าหน่วย — ยังไม่มีข้อมูลหัวหน้าหน่วยในระบบ ใช้รายงานแทน)

### A2 รายงาน (SRS §13) — **S16** `/reports/`
สิทธิ์: superuser เห็นทุกห้อง · ผู้อนุมัติ/เจ้าหน้าที่ดูแล เห็นเฉพาะห้องตน (ตามตาราง §3 ของ SRS) · ตัวกรอง: เดือน (พ.ศ.), ห้อง, หน่วย · ทุกรายงานมีปุ่ม **CSV** (UTF-8 BOM ให้ Excel ไทยอ่านได้)
1. อัตราการใช้ห้อง: ชั่วโมงใช้จริง (USED) และชั่วโมงจองอนุมัติ / ชั่วโมงให้บริการ รายห้อง·ประเภท·หน่วย·เดือน
2. ยกเลิก + no-show: จำนวนและอัตราส่วนต่อการจองทั้งหมด รายหน่วยและรายบุคคล
3. การอนุมัติ: เวลาเฉลี่ย submit→ตัดสิน · จำนวนเกิน SLA · หมดอายุ รายผู้อนุมัติ (รวม amendment)
4. บังคับย้ายทั้งหมด: วันเวลา ห้อง เลขอ้างอิง ผู้สั่ง สถานะรับทราบ (FR-30)
5. อุปกรณ์ส่วนกลาง: จำนวนครั้ง/ชั่วโมงที่ถูกใช้ รายเดือน
   ⚠ ข้อเบี่ยงจาก SRS: "ถูกปฏิเสธเพราะชนกี่ครั้ง" ยังไม่เก็บสถิติการค้นที่พลาด — บันทึกเป็นข้อจำกัดใน notes · PDF เลื่อนไปหลัง pilot (CSV พอสำหรับเดือนแรก)

### A3 Audit log (NF-01/02)
- โมเดล `audit.AuditLog`: `at, actor FK null, entity, entity_id, action, before JSON, after JSON, ip` — **append-only**: override `save()` ห้าม update (pk ซ้ำ → raise), ไม่มี ModelAdmin แก้/ลบ (อ่าน+filter อย่างเดียว), `delete()` raise
- จุดบันทึก (เรียกชัด ๆ ใน services ไม่ใช้ middleware ดักทุกอย่าง): สร้าง/ส่ง/แก้/ยกเลิกการจอง · ตัดสิน (อนุมัติ/ปฏิเสธ/หมดอายุ/ถอน ทั้ง booking, series, amendment) · บังคับย้าย+รับทราบ · งดใช้ห้อง/สิ้นสุด · เปลี่ยนสถานะการใช้งาน · login/logout/login ล้มเหลว (signals `user_logged_in/out, user_login_failed`) · การแก้ทะเบียน (ผูกกับ `post_save/post_delete` ของ Resource/ResourceRule/ResourceApprover/Blackout/Unit/User โดย actor จาก request ถ้ามี)
- `ip` จาก request เมื่อมี · helper `audit(actor, entity, entity_id, action, before=None, after=None, ip="")`

### A4 บัญชีผู้ใช้จริง
- `import_users` command: อ่าน CSV (`username,email,rank,first_name,last_name,unit_code,phone,service_number`) → สร้างบัญชี + รหัสผ่านเริ่มต้นสุ่ม 12 ตัว เขียนผลลัพธ์เป็นไฟล์ `imported-users-<วันที่>.csv` (username, รหัสเริ่มต้น) ให้ผู้ดูแลแจกด้วยมือ พร้อมคำเตือนให้ลบไฟล์หลังแจก · ตรวจโดเมนอีเมล/unit ครบก่อนสร้าง ผิดแถวไหนรายงานแล้วข้าม
- ฟิลด์ `must_change_password` + middleware: ล็อกอินแล้วถูกบังคับไปหน้าเปลี่ยนรหัสผ่านก่อนใช้งานทุกหน้า (**S17**) · `import_users` และ `seed_pilot --demo-users` ตั้ง flag นี้ · เปลี่ยนแล้ว flag หลุด + audit

### A5 สำรองข้อมูล (NF-04) + ตัวช่วยติดตั้ง
- `scripts/backup.ps1`: `pg_dump -Fc` → `<BACKUP_DIR>\sigroom-<YYYYMMDD-HHmm>.dump` + ลบให้เหลือ 30 ชุดล่าสุด + เขียน `backup-log.txt` (สำเร็จ/ล้มเหลว) · อ่านค่าจาก `.env`
- `scripts/restore-test.ps1`: กู้ dump ล่าสุดเข้าฐาน `ogn_room_restore_test` แล้วนับจำนวนแถว Booking เทียบ — พิมพ์ผล ผ่าน/ไม่ผ่าน
- `config/settings.py` (อนุญาตแก้): เพิ่ม `DJANGO_SECURE` env (ค่า 0 = ปิด `SECURE_SSL_REDIRECT`/`SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE`/HSTS สำหรับ pilot ใน LAN ที่ยังไม่มี TLS — DEBUG=0 ได้โดยไม่พังการเข้าระบบ) + `CSRF_TRUSTED_ORIGINS` จาก env + **WhiteNoise** สำหรับ static ใน production
- แพ็กเกจใหม่ที่อนุญาต (ครั้งแรกตั้งแต่ M0): `waitress` (WSGI server บน Windows), `whitenoise` (เสิร์ฟ static) — เหตุผล: ติดตั้งบนเครื่องหน่วยที่เป็น Windows โดยไม่ต้องมี nginx/IIS
- `scripts/run-server.ps1`: `uv run waitress-serve --listen=0.0.0.0:8000 config.wsgi:application`

### A6 เทส (`~13 ข้อ` + เดิม 59 ต้องผ่าน)
1. auto-USED: จบเวลาแล้วเปลี่ยน · DISPLACED/ROOM_UNAVAILABLE ไม่ถูกทับ · idempotent
2. no-show: custodian ตั้งได้ใน 3 วัน แก้ทับ USED ได้ · เกิน 3 วัน → error · ผู้ใช้อื่น 403 · ผู้จองได้รับแจ้ง
3. รายงาน 1–5: fixture เล็ก คำนวณตัวเลขตรง (ชั่วโมง, อัตราส่วน, เวลาเฉลี่ย) · การกรองเดือน/หน่วย
4. สิทธิ์รายงาน: wanida เห็นเฉพาะ MTG-1 · somchai 403 · CSV ต้อง login และมี BOM
5. AuditLog: การกระทำหลัก 6 ชนิดสร้างแถว · `save()` ทับแถวเดิม → raise · `delete()` → raise · login fail มีแถว
6. import_users: สร้างครบ, แถวเสียถูกข้ามพร้อมรายงาน, ไฟล์รหัสเริ่มต้นถูกสร้าง, `must_change_password=True`
7. middleware: ผู้ใช้ flag ค้างถูก redirect ทุกหน้าไป S17 · เปลี่ยนแล้วหลุด + flag ปิด + audit
8. `DJANGO_SECURE=0` → ไม่มี ssl redirect (ทดสอบผ่าน override_settings/client)

### A7 นิยาม "เสร็จ" ของ 6A
- pytest ทั้งหมดผ่าน · check สะอาด · ไม่มี migration ค้าง (ทุกอันเป็น expand)
- ห้ามแตะรายการเดิมทั้งหมดของ M1–M5 นอกจาก: `run_scheduled_jobs` (เพิ่มงาน auto-USED), `settings.py` (ตาม A5), `base.html` (เพิ่มเมนู การใช้งานห้อง/รายงาน ตามสิทธิ์)
- อัปเดต build-plan + `docs/m6-notes.md` · ยังไม่ commit รอ Claude ตรวจ

## ส่วน 6B — ขัด UX/UI + ติดตั้ง + เริ่ม pilot (Claude + ผู้ใช้)

### B1 ขัด UX/UI รวบยอด (Claude ทำในเครื่องนี้ หลัง 6A ผ่านตรวจ)
- ไล่ทุกหน้า (S1–S17) ให้: ระยะห่าง/ลำดับสายตา/ปุ่มหลัก-รองสม่ำเสมอ · สีสถานะชุดเดียวทั้งระบบ · มือถือ 360px ไม่มี scroll แนวนอน · focus ชัด · ข้อความผิดพลาด/ว่าง/สำเร็จครบทุกหน้า (สอดคล้อง NF-10–12 ระดับ pilot ไม่ถึงขั้น audit WCAG เต็ม)
- หน้าแรกของแต่ละบทบาทเห็นงานตัวเองก่อน: ผู้อนุมัติเห็นคิว ผู้จองเห็นปฏิทิน+การจองใกล้ถึง เจ้าหน้าที่เห็นการใช้งานวันนี้
- เกณฑ์จบ: เดินครบ 6 บท user journey บนจอ 360/768/1280 โดยไม่เจอจุดสะดุดที่ต้องอธิบาย

### B2 ติดตั้งเครื่องหน่วย (runbook `docs/deploy-guide.md` — Claude เขียน ผู้ใช้ทำตามทีละขั้น)
1. เตรียมเครื่อง Windows ในหน่วย: ติดตั้ง Python 3.12 + uv + PostgreSQL 16 · คัดลอกโปรเจค (git bundle/USB)
2. `.env` production: `DJANGO_DEBUG=0`, `DJANGO_SECURE=0` (LAN, ยังไม่มี TLS — ความเสี่ยงบันทึกไว้), `SECRET_KEY` ใหม่ (สุ่ม), `ALLOWED_HOSTS`+`CSRF_TRUSTED_ORIGINS` = ชื่อเครื่อง/IP ใน LAN
3. ความปลอดภัยค้างจาก M1: เปลี่ยนรหัส `postgres` · สร้าง DB user `sigroom_app` สิทธิ์จำกัด (ไม่ superuser) + `REVOKE UPDATE, DELETE ON audit_auditlog FROM sigroom_app` (บังคับ NF-02 ที่ DB) · `listen_addresses='localhost'` · เปลี่ยนรหัส admin เว็บ
4. `migrate` + `collectstatic` + `seed_pilot` (ไม่ใส่ --demo-users) + `import_users` รายชื่อจริง 30–50 คน
5. Task Scheduler: `run_jobs` ทุก 5 นาที · `backup.ps1` ทุกวัน 19:00 → ปลายทางเป็นดิสก์/แชร์คนละเครื่อง · firewall เปิดพอร์ต 8000 เฉพาะ LAN
6. ทดสอบกู้คืน 1 ครั้งด้วย `restore-test.ps1` และเก็บผลไว้ (เกณฑ์รับมอบข้อ 12 ของ SRS)
7. ตรวจรับติดตั้ง: เปิดจากเครื่องอื่นใน LAN + มือถือ · จองจริง 1 รายการครบวงจร

### B3 เอกสารเริ่ม pilot (`docs/pilot-checklist.md`)
- เกณฑ์รับมอบ pilot (แปลงจาก SRS 15.2 เฉพาะข้อที่ใช้กับ pilot LAN): จองซ้อน=0 · วงจรอนุมัติ/รักษาการ/หมดอายุทำงาน · amendment ปฏิเสธแล้วของเดิมอยู่ · บังคับย้ายครบขั้น · ปกปิดข้ามหน่วย · กู้คืนสำเร็จ · แบบสอบถามหลังเดือน ≥ 3.5/5
- กิจวัตร: ทุกเช้าดู backup-log · ทุกศุกร์ export รายงาน · ช่องทางรับปัญหา (สมุด/Google Form ของหน่วย) + ตารางบันทึกข้อบกพร่อง
- สิ่งที่ **ยังไม่มี** ใน pilot และต้องบอกผู้ใช้ล่วงหน้า: LINE, 2FA, เข้าจากนอก LAN, ลืมรหัสผ่านเอง (ติดต่อผู้ดูแล), พิมพ์แบบฟอร์มราชการ

### ลำดับการทำ M6
1. Codex ทำ 6A → Claude ตรวจรับ + commit
2. Claude ทำ B1 (ขัด UI) → ผู้ใช้เดิน user journey ยืนยัน → commit
3. Claude เขียน deploy-guide + pilot-checklist → ผู้ใช้ติดตั้งตาม B2 บนเครื่องหน่วย (Claude ช่วยแก้ปัญหาสด) → เริ่ม pilot 1 เดือน

## ดูผลด้วยตา (6A)
1. จองห้องเมื่อวาน (ผ่าน Admin ปรับเวลา) → `run_jobs` → กลายเป็น "ใช้งานแล้ว" · `admin` เปิด `/usage/` สลับเป็น "ไม่มาใช้" → somchai ได้กระดิ่ง
2. `/reports/` เห็นอัตราใช้ห้องเดือนนี้ กด CSV เปิดใน Excel อ่านไทยได้
3. Admin → Audit log เห็นแถวการกระทำล่าสุด ลองแก้ → ระบบไม่ยอม
4. `import_users` ไฟล์ตัวอย่าง 3 คน → ล็อกอินคนใหม่ → ถูกบังคับเปลี่ยนรหัสก่อน
5. รัน `scripts/backup.ps1` → มีไฟล์ dump + log · `restore-test.ps1` → ผ่าน
