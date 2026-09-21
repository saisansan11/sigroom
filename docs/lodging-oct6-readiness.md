# SIGROOM Lodging — 6 Oct 2026 Readiness Runbook

เอกสารนี้ใช้กับ Phase D ของระบบที่พัก โดยอ้างอิงหลักสูตรจริงใน seed:

- ชื่อ: `นายสิบชั้นต้น เหล่า ส. ผ่านสื่ออิเล็กทรอนิกส์(หลักสูตรเร่งรัด) รุ่นที่ 11`
- slug: `jnr-nco-11`
- วันเริ่มเข้าพัก: **6 ตุลาคม 2026**
- วันสิ้นสุด: **25 ธันวาคม 2026**

> เอกสารนี้เป็น readiness/rehearsal guide เท่านั้น ไม่ใช่คำอนุมัติ deploy Production

## 1. Readiness contract

ก่อนประกาศ Lodging Production Ready ต้องพิสูจน์อย่างน้อย:

1. เจ้าหน้าที่จัดสรรห้องและกำหนด booking window ได้
2. นักเรียนจองเตียงแรกได้ และได้ private management link + public digital pass แยกกัน
3. near-full / last-bed ไม่ overbook แม้มีคำขอพร้อมกัน
4. duplicate phone / duplicate bed ถูกปฏิเสธ
5. นักเรียนยกเลิกเองได้เฉพาะช่วงที่ self-booking ยังเปิด และเตียงถูกคืนทันที
6. หลังยกเลิก นักเรียนจองใหม่ได้ถ้ายังอยู่ใน booking window
7. เจ้าหน้าที่ปิดรับจองกลางทางแล้ว direct POST ใหม่ต้องถูกปฏิเสธที่ service layer
8. check-in ก่อนวันเข้าพักถูกปฏิเสธ
9. check-in ในวันเข้าพักและ late arrival ภายในช่วงพักยังทำได้
10. check-in หลังวันสิ้นสุดถูกปฏิเสธ
11. เจ้าหน้าที่บันทึก no-show ได้ตั้งแต่วันเข้าพัก และเตียงถูกคืนพร้อมประวัติ/audit
12. ผู้ไม่มีสิทธิ์ไม่สามารถ check-in, no-show, move bed หรือเข้า Staff Workspace
13. anonymous public lodging request ถูกกัน exact duplicate และมี persistent rate limit โดยไม่เก็บ raw throttle identifier
14. backup/rollback procedure พร้อมและ operator รู้จุดหยุดก่อน migration/deploy
15. ไม่มี P0/P1 ค้าง

## 2. Student self-service lifecycle

Self-booking ใหม่สร้าง 2 capability แยกกัน:

- **Digital Pass URL** — ใช้แสดง/แชร์ให้เจ้าหน้าที่ ดูบัตรและ QR check-in แต่ไม่มีสิทธิ์ยกเลิก
- **Private Management URL** — ใช้ดูบัตรและยกเลิก reservation ของตนเอง ห้ามส่งต่อ

การยกเลิกด้วยตนเองอนุญาตเมื่อ:

- reservation ยังไม่ check-in
- booking window ของหลักสูตรยังอยู่ในสถานะ `open`
- management token ตรงกับ reservation

เมื่อยกเลิก ระบบสร้าง `CourseLodgingRelease(outcome=cancelled)` เป็นประวัติก่อนลบ active `CourseStudentLodging` เพื่อคืน unique bed/phone inventory ทันที

> Reservation ที่สร้าง **ก่อน** migration 0013 จะยังไม่มี private management token และต้องให้เจ้าหน้าที่ดำเนินการยกเลิกผ่าน Staff Workspace; reservation ใหม่หลัง 0013 จะได้ token อัตโนมัติ

## 3. Staff arrival / no-show lifecycle

- `check_in_student()` อนุญาตตั้งแต่ `check_in_date` ถึง `check_out_date`
- ก่อนวันเข้าพัก: reject
- late arrival ภายในช่วงเข้าพัก: allow
- หลังวันสิ้นสุด: reject
- no-show เป็น staff-only และทำได้ตั้งแต่วันเข้าพักเป็นต้นไป
- reservation ที่ check-in แล้วห้าม cancel/no-show ด้วย release flow
- no-show ถูกเก็บใน `CourseLodgingRelease(outcome=no_show)` + AuditLog ก่อนคืนเตียง

## 4. Public request anti-abuse

ค่า default ปรับผ่าน `.env` ได้:

```text
PUBLIC_LODGING_RATE_WINDOW_SECONDS=900
PUBLIC_LODGING_RATE_PHONE_LIMIT=3
PUBLIC_LODGING_RATE_CLIENT_LIMIT=8
```

หลักการ:

- exact duplicate (ห้อง + ช่วงเวลา + เบอร์โทรเดียวกัน และรายการเดิมยัง pending/approved) ถูกปฏิเสธด้วยข้อความทั่วไป ไม่สร้าง Booking ซ้ำและไม่เปิดเผย status token เดิม
- anonymous request ใช้ fixed-window counter แยก phone/client
- identifier ใน throttle table เป็น HMAC-SHA256; ไม่เก็บ raw phone/session key
- Booking จริงยังเก็บเบอร์โทรตามวัตถุประสงค์งานที่พักตามเดิม

## 5. Migration 0013

`bookings/migrations/0013_courselodgingaccess_publiclodgingthrottle_and_more.py` เป็น **expand-only migration**:

- create `CourseLodgingAccess`
- create `CourseLodgingRelease`
- create `PublicLodgingThrottle`
- ไม่ alter/drop `CourseStudentLodging`
- ไม่แก้ unique constraints เดิม
- ไม่มี destructive data migration

### Rollback rule

ถ้าต้อง rollback application หลัง deploy ให้ **rollback code ก่อนและคง schema 0013 ไว้** (expand/contract strategy) เพราะ code รุ่นก่อนจะเพิกเฉยตารางใหม่ได้

ห้าม reverse migration 0013 เป็นขั้นตอน rollback ปกติ เพราะจะลบประวัติ cancel/no-show และ throttle counters ที่สร้างหลัง deploy

ถ้าจำเป็นต้อง reverse schema จริง ต้องหยุดการเขียนระบบ + backup สด + ได้อนุมัติ maintenance แยกก่อน

## 6. Pre-deploy gate (ยังห้าม deploy หากไม่ได้รับคำสั่งอนุมัติ)

ก่อนเสนอ Production deploy ต้องรายงาน:

- commit SHA ที่จะ deploy
- environment/target
- components ที่เปลี่ยน
- migration: `0013` (expand-only)
- backup ล่าสุด + restore verification
- rollback commit/path
- smoke plan
- known issues / blockers

ลำดับเมื่อได้รับอนุมัติในอนาคต:

1. หยุด/ลดการเขียนตาม maintenance procedure
2. backup สดและตรวจไฟล์ dump
3. deploy code ที่ผ่าน CI
4. run migration 0013
5. smoke public request + course portal + staff workspace
6. เปิดการใช้งานกลับ
7. เก็บ evidence

## 7. 6 Oct rehearsal script

ใช้ test/staging data เท่านั้นจนกว่าจะได้รับอนุมัติ Production:

1. ยืนยัน `jnr-nco-11` วันที่ 6 ต.ค. 2026–25 ธ.ค. 2026
2. allocate ห้องทดสอบอย่างน้อย 2 ห้อง
3. เปิด booking window
4. จองคนแรก
5. จองจน near-full
6. ยิงคำขอสองรายการพร้อมกันที่ last bed → ต้องสำเร็จ 1 รายการเท่านั้น
7. ทดสอบ duplicate phone/bed
8. self-cancel 1 รายการ → free bed เพิ่มทันที
9. rebook เบอร์เดิมในเตียงใหม่ → สำเร็จถ้า window ยังเปิด
10. staff ปิด booking → direct POST ใหม่ถูก reject
11. early check-in (5 ต.ค.) → reject
12. on-time check-in (6 ต.ค.) → pass
13. late check-in (หลัง 6 ต.ค. แต่ก่อน 25 ธ.ค.) → pass
14. no-show ตั้งแต่ 6 ต.ค. → staff-only, archive + audit + free bed
15. move bed → conflict-safe
16. after-checkout check-in (26 ธ.ค.) → reject
17. refresh/relogin Staff Workspace → counts ต้องคงจาก DB
18. anonymous → Staff Workspace ต้อง redirect login / ไม่มี PII หลุด

## 8. Known blocker — Course Membership Source of Truth

ปัจจุบัน repository มี `CourseLodgingCohort` และรายชื่อผู้ที่จองแล้ว (`CourseStudentLodging`) แต่ **ไม่มี canonical Course Enrollment / Student Roster model หรือ connector** ที่ยืนยันได้ว่า “บุคคลนี้เป็นนักเรียนในหลักสูตรนี้จริง”

ดังนั้น Phase D **ไม่กล่าวอ้างว่า `student ∈ course` ถูก enforce แล้ว**

ก่อน Production Ready แบบเต็มสำหรับ student eligibility ต้องกำหนด Source of Truth ที่เชื่อถือได้ก่อน เช่นระบบทะเบียน/Signalschool identity ที่มี course membership แล้วเชื่อมเป็น eligibility layer โดยไม่ hard-code ลง Booking Core

จนกว่าจะมี Source of Truth นี้ ให้ถือเป็น readiness blocker ที่ต้องได้รับการยอมรับ/แก้ไขอย่างชัดเจนก่อนเปิด student self-booking จริงในวงกว้าง

## 9. Evidence to retain

- Phase D automated test output
- PR Safety Gate (Critical / Full / Security / Repository / Accessibility)
- migration drift check
- browser QA desktop/mobile
- screenshot/evidence ของ Staff → Student → Arrival rehearsal
- backup/restore evidence
- final deploy approval record (ถ้ามีในอนาคต)
