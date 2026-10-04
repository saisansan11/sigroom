# PR-3 บัตรจองแบบตลับเทป

ฐานจริง `feat/lodging-v5-2` ที่ `372e4059b7c2b7c220d7ec57f1d9a34c68ffdeb0` รวม PR #87 และ PR #88 แล้ว Branch `feat/booking-cassette-pass` เริ่มจาก SHA เดียวกับ `origin/feat/lodging-v5-2` หลัง `git fetch origin` รอบตรวจสุดท้าย ไม่มี rebase หรือ force-push และไม่แตะงานค้างใน checkout หลักหรือ PR #82

## สิ่งที่ทำ

- เพิ่มบัตรจองหน้าตาแบบตลับเทปเป็น partial กลาง ใช้ร่วมกับบัตรจองห้องทั่วไป/ห้องสอนออนไลน์และบัตรเตียงเดิม
- บัตรแสดงสถานะอนุมัติ/รออนุมัติ รายละเอียดที่จำเป็น QR ปุ่มคัดลอกลิงก์ ดาวน์โหลดปฏิทิน และลิงก์ดำเนินการต่อโดยไม่ต้องพึ่งภาพตกแต่ง
- หลังจองห้องทั่วไปหรือห้องสอนออนไลน์สำเร็จ พาไปหน้าบัตรจริงของรายการนั้น
- route บัตรและ QR บังคับ login และใช้ `can_view_details` เดิม ไม่เพิ่มสิทธิ์ให้ผู้อนุมัติที่ไม่มีสิทธิ์ดูรายละเอียด ผู้ใช้ที่เห็นรายละเอียดแต่ไม่มีสิทธิ์เปิดลิงก์ห้องออนไลน์จะไม่เห็นลิงก์นั้น
- QR canonical URL สร้างจาก `PUBLIC_BASE_URL` ที่ผ่าน validation ไม่เชื่อ Host header และไม่ยอมรับ credentials/path/query/fragment/backslash/whitespace/พอร์ตผิดรูป
- JavaScript ของตลับเทปรองรับ Enter/Space, reduced motion, QR dialog และ fallback คัดลอก relative URL

## การตรวจรอบ freeze ก่อน commit

ตรวจด้วยฐาน PostgreSQL local แยกชื่อ `sigroom_online_beta_qa` ผ่าน wrapper `.tmp/local_env.py` ซึ่งบังคับ DB host เป็น loopback และตั้ง `PUBLIC_BASE_URL=http://127.0.0.1:8019` โดย `.tmp/` ไม่อยู่ใน scope commit

- `uv sync --locked` — PASS
- `uv run manage.py check` — **PASS**, 0 issues
- `uv run manage.py makemigrations --check --dry-run` — **PASS**, no changes detected
- `node --test tests/cassette-interaction.test.cjs` — **13 passed, 0 failed**
- `git diff --check` — **PASS**
- Full regression `uv run pytest -q --disable-warnings` — **1032 passed, 489 warnings, 124.09s**

ผู้ตรวจแยกจากผู้เขียนอ่าน source/diff ของ `services.py`, route/view, online teaching, lodging reuse, shared partial, JavaScript และ tests อีกครั้ง ไม่พบ regression ด้าน authorization, sensitive link, QR origin หรือ redirect

## Browser QA

รอบสดก่อน commit ด้วย managed Chrome + local QA database:

- approved online pass เปิดจากรายการจองจริงได้ รายละเอียดครบ ไม่มี horizontal overflow
- โฟกัสตลับเทปแล้วกด Enter พลิกไปด้าน QR และ Space พลิกกลับได้จริง
- QR dialog เปิด/ปิดได้จริง และมีลิงก์ `.ics` จริง
- pending meeting pass แสดง `รออนุมัติ` และข้อความว่า `ยังต้องรอผลพิจารณาก่อนใช้งาน` โดยไม่มี horizontal overflow

ข้อจำกัดของรอบสด: managed Chrome instance นี้คง device metrics ภายในไว้แม้ย่อ native window จึงไม่สามารถยืนยัน viewport 390px ใหม่จาก session เดียวกันได้ และ console event stream ไม่ได้เปิด subscription จึงไม่มี fresh console capture ปุ่มคัดลอกถูกกดได้แต่ CDP ไม่คืนสถานะ Clipboard API จึง **ไม่อ้าง** ว่ารอบสดยืนยัน clipboard สำเร็จ

หลักฐาน Browser QA ก่อนหยุดงานยังอยู่บน WIP เดียวกันและ Git state ไม่เปลี่ยนตั้งแต่ handoff: ทดสอบ 390px/1280px ทั้ง approved online, pending meeting และ legacy lodging pass, Enter/Space, QR, actual copy, ICS, no overflow และไม่มี console error ภาพ 7 ไฟล์อยู่ใน `docs/qa/online-beta/pr3/`: `online-mobile.jpg`, `online-desktop.jpg`, `pending-mobile.jpg`, `pending-desktop.jpg`, `lodging-mobile.jpg`, `lodging-desktop.jpg`, `qr-mobile.jpg`

## Tests ที่เพิ่ม/ปรับ

- เพิ่ม `bookings/tests_booking_pass.py` ครอบคลุม auth, sensitive visibility, QR origin/PII, service link, success redirect, race/preemption และ delegate/approver boundary
- เพิ่ม/ปรับ `tests/cassette-interaction.test.cjs` สำหรับ interaction ของ shared cassette component
- ปรับ regression ที่เกี่ยวข้องกับ online teaching, lodging, service shell, booking flow, task-first และ UI ให้คาด redirect/โครงสร้างบัตรใหม่ โดยไม่ลบหรือ skip เกณฑ์เดิม

## Invariants ที่ต้องรักษา

- ห้ามใช้ request Host สร้าง public QR URL; ต้องผ่าน `PUBLIC_BASE_URL`
- ห้ามให้ `can_decide` หรือสถานะ approver แปลเป็นสิทธิ์ดูบัตร/ลิงก์ sensitive โดยอัตโนมัติ
- บัตร lodging เดิมต้อง reuse shared partial โดยไม่เปลี่ยน ownership/token semantics เดิม
- `.tmp/` เป็น local QA helper ห้าม stage/commit
- PR #87/#88 คือฐานที่ deploy แล้ว ห้ามทำซ้ำ

## สิ่งที่ไม่ทำใน PR นี้

- ไม่เพิ่ม Notification/Job/Scheduler ของ PR-4
- ไม่เพิ่ม Web Push/VAPID ของ PR-5
- ไม่เพิ่ม Google OAuth/สิทธิ์นักเรียนของ PR-6
- ไม่เพิ่ม Dashboard/ค่าที่พักของ PR-7
- ไม่เพิ่มเอฟเฟกต์หมึกของ PR-8

## ขั้นถัดไป

หลัง PR นี้ผ่าน CI, merge และ deploy exact SHA แล้ว ค่อยรวม PR-4 บน stack ใหม่ โดยแก้ `Notification.kind` ให้มี `db_default=""` พร้อม legacy INSERT test, เอา fixture route ชั่วคราวออก แล้วทำ full regression/Browser QA ก่อนตั้ง Cloud Job และ Scheduler ทุก 5 นาที

### Prompt ส่งต่อเอเจนต์ถัดไป

```text
รับงานต่อ SIGROOM Online Beta หลัง PR-3 บัตรจองแบบตลับเทป

1. ตรวจ Git/remote/production สดก่อนทุกครั้ง และอ่าน docs/handoffs/2026-10-04-online-beta-pr3.md
2. ห้ามทำ PR #87/#88 ซ้ำ และห้าม reset/clean worktree PR-4 ถึง PR-7
3. เริ่ม PR-4 ที่ F:\ogn_ROOM\.worktrees\online-beta-pr4 หลังยืนยันว่า PR-3 merge/deploy exact SHA แล้ว
4. แก้ Notification.kind ให้มี db_default="" และเพิ่ม legacy INSERT compatibility test
5. หลัง PR-3 route จริงอยู่ใน base ให้ลบ fixture ชั่วคราวที่ชดเชย booking pass route
6. รัน targeted + full regression + migration drift + Browser QA กระดิ่ง/อีเมล แล้วจึง commit/push/PR/CI
7. ก่อน schema change ขึ้น production ให้ทำ Cloud SQL backup ใหม่ตาม runbook
8. ตั้ง sigroom-run-jobs และ Scheduler ทุก 5 นาทีเฉพาะหลัง PR-4 deploy แล้ว และตรวจ execution จริง; web deploy อย่างเดียวไม่อัปเดต Job image/config
```
