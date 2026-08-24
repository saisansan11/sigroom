# SIGROOM — บันทึกการทำ M5

## จุดขัดกันที่ต้องตัดสินใจก่อนลงมือ

### 1. ประวัติการถอนคำขอแก้ไขไม่มีชนิดการดำเนินการรองรับ

- `docs/m5-plan.md` ข้อ 2.2 กำหนดให้ `withdraw_amendment(...)` ปลด hold และสร้าง `Approval` พร้อมแจ้งเตือน
- `approvals.Approval.Action` ปัจจุบันมีเพียง `submitted`, `approved`, `rejected`, `expired`
- ข้อ 2.1 อนุญาตให้แก้ `Approval` เฉพาะเพิ่ม `amendment` FK และ CheckConstraint
- ข้อ 2.7 ห้ามแตะนอกขอบเขต 2.1/2.4 จึงไม่อนุญาตให้เพิ่ม action `withdrawn`

ผลกระทบ: ไม่สามารถบันทึกการถอนให้มีความหมายถูกต้องได้โดยไม่เดาว่าจะใช้ `rejected` แทน หรือขยาย schema ด้วย `withdrawn`

สถานะ: **ตัดสินใจแล้ว**

## คำตัดสินของผู้ใช้

- อนุญาตให้เพิ่ม `Approval.Action.WITHDRAWN` โดยถือเป็นส่วนหนึ่งของการเพิ่ม amendment FK ตามข้อ 2.1
- การถอน amendment ทุกกรณีต้องสร้างแถว `Approval` เสมอ
- `acted_by` คือผู้ที่ทำให้เกิดการถอน: ผู้จอง, superuser, ผู้กดยกเลิกการจอง หรือผู้สั่งบังคับย้าย
- `on_behalf_of` เป็น `NULL`
- เหตุผลไม่บังคับสำหรับการถอนด้วยตนเอง แต่การถอนอัตโนมัติต้องมีเหตุผลระบบ เช่น
  `ถอนอัตโนมัติ: การจองถูกยกเลิก`
- หน้า S5 แสดงประวัติเป็น `ถอนคำขอแก้ไข โดย … เมื่อ …`

## สรุปการลงมือ

- เพิ่ม `BookingAmendment`, `Preemption` และ amendment hold โดยไม่แก้ `excl_overlapping_holds`
- เพิ่ม partial unique constraints และ composite FK `fk_amendment_same_booking` แบบ deferred พร้อม reverse migration
- เพิ่ม service สำหรับ submit/apply/reject/withdraw/expire amendment โดย lock ทั้ง amendment และ booking และตรวจ `base_revision`
- ก่อน apply ระบบตรวจซ้ำว่า active hold ปลายทางมีห้องใหม่และอุปกรณ์ชุดเต็มครบ จึงค่อยปลดของเดิม
- เพิ่ม service บังคับย้ายแบบ transaction เดียว: ถอน amendment ค้าง, ปลด displaced, สร้าง incoming, สร้าง replacement และแจ้งผู้เกี่ยวข้อง
- ปิดการรั่วชื่อกิจกรรม incoming ต่อผู้จองเดิมทั้ง notification, ปฏิทิน และหน้ารายละเอียด
- เพิ่มหน้า S13/S14, การ์ด S5/S7, ปฏิทิน amendment, URL, Admin และงานตามเวลา

## ผลตรวจข้อ 2.7

- `uv run pytest` → **59 passed** (เดิม 43 + M5 ใหม่ 16)
- `uv run manage.py check` → **System check identified no issues**
- `uv run manage.py makemigrations --check` → **No changes detected**
- migration `bookings.0005` และ `approvals.0002` apply กับฐานข้อมูลพัฒนาสำเร็จ
- `git diff --check` สะอาด
- ไม่เพิ่มแพ็กเกจ ไม่แก้เทสเดิม และยังไม่ commit
