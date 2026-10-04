# SIGROOM Online Beta — PR-4 เตือนก่อนสอน

วันที่ตรวจ: 4 ต.ค. 2569
ฐานก่อน PR-4: `feat/lodging-v5-2` ที่ merge SHA `673bf1e2d2143540ef767c7c17f1a1a254d20ab5` (PR #89)
Worktree: `F:\ogn_ROOM\.worktrees\online-beta-pr4`
Branch: `task/online-beta-pr4`

## ขอบเขต
เพิ่มการเตือนสำหรับห้องสอนออนไลน์ 2 รอบผ่าน `run_jobs`: รอบก่อนสอน 30 ถึงก่อน 5 นาที และรอบถึงเวลาตั้งแต่เริ่มถึงก่อน 10 นาทีหลังเริ่ม เฉพาะ booking ที่อนุมัติแล้ว สถานะ UPCOMING และห้อง ONLINE

กระดิ่งไม่เก็บ private meeting URL; อีเมลส่งหลัง transaction commit และส่ง private meeting URL เฉพาะเจ้าของ booking หากอีเมลล้ม กระดิ่งยังอยู่และ `email_failed` เพิ่มโดยไม่ log เนื้อหาอีเมล

ใช้ DB unique constraint `(booking,user,kind)` เฉพาะ `kind != ''` กันแจ้งซ้ำ

## Rolling-update / rollback compatibility
`Notification.kind` มีทั้ง `default=""` และ `db_default=""` เพื่อให้แอปรุ่นเก่าที่ไม่ส่งคอลัมน์ `kind` ยัง INSERT ได้ระหว่าง migration หรือ rollback

SQL migration ที่ตรวจได้:
`ALTER TABLE notifications_notification ADD COLUMN kind varchar(30) DEFAULT '' NOT NULL;`

เพิ่ม test raw SQL ที่จงใจ omit `kind` และยืนยันว่า DB เติมค่าว่างให้จริง

## สิ่งที่แก้จาก WIP เดิม
1. เพิ่ม `db_default=""` ทั้ง model และ migration
2. ลบ fixture route ชั่วคราว เพราะ PR-3 มี route `bookings:booking_pass` จริงแล้ว
3. เพิ่ม test legacy INSERT
4. Stack ฐาน PR-2/PR-3 เข้ามาแบบ fast-forward โดยไม่ reset/clean WIP

## ผลทดสอบสด
- `manage.py check` — PASS, 0 issues
- migration drift — PASS, `No changes detected`
- Targeted reminders — **37 passed, 2 warnings**
- Full pytest — **1069 passed, 490 warnings, 162.06s**
- Fresh migration ถึง `notifications.0002` — PASS
- `git diff --check` — PASS

## Browser QA local
ใช้ DB แยก local และบัญชี QA เท่านั้น ตรวจแล้วว่า:
- รอบก่อนสอนสร้างกระดิ่ง 1 รายการ
- กระดิ่งแสดงห้อง/วัน พ.ศ./เวลา และไม่เผย private meeting URL
- กดกระดิ่งแล้ว mark-read และเปิดบัตร PR-3 จริง
- บัตรเจ้าของ booking แสดง private meeting link ตามสิทธิ์
- รอบถึงเวลาสร้างอีก 1 รายการ
- รันซ้ำในหน้าต่างเดียวกันได้ 0 ไม่เกิด duplicate

ผล dedup:
`START={'remind_30':0,'remind_start':1,'email_failed':0}`
`REPEAT={'remind_30':0,'remind_start':0,'email_failed':0}`

## หลัง merge/deploy PR-4
Runbook อยู่ที่ `docs/ops/run-jobs-cloud.md`
หลัง production web deploy และ migration สำเร็จแล้ว จึงสร้าง/อัปเดต Cloud Run Job `sigroom-run-jobs` ให้ใช้ image/config เดียวกับ production web, ทดสอบ execution จริง แล้วค่อยตั้ง Scheduler ทุก 5 นาที Asia/Bangkok

ทุกครั้งที่ deploy web รุ่นใหม่ ต้อง sync image/config ของ Job ใหม่ด้วย เพราะ web deploy ไม่อัปเดต Job อัตโนมัติ

## Ops warning เดิมที่ต้องตรวจ
จาก release ก่อนหน้า script ยังเตือนเรื่อง SMTP config, explicit secure setting และ trusted client-IP/proxy config สิ่งเหล่านี้ไม่ใช่ regression ของ PR-4 แต่ SMTP ต้องตรวจให้พร้อมก่อนเปิด scheduled reminders จริง

## Gate ก่อน merge/deploy
- ห้าม stage `.tmp/`
- migration drift PASS
- PR Safety CI ทุก gate PASS บน exact HEAD
- PR CLEAN/MERGEABLE
- deploy exact merge SHA ผ่าน production guard เท่านั้น
- หลัง deploy ยืนยัน revision/image/traffic 100% และ HTTP smoke ก่อนเปิด Cloud Job/Scheduler
