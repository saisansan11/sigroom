# SIGROOM — แผน M3: ระบบอนุมัติ

สถานะ: **ร่างเพื่อให้ผู้ใช้ดูหน้าจอก่อน → แล้ว Codex ลงมือ**
อ้างอิง: `CLAUDE.md`, `docs/room-booking-srs.html` (FR-18–24, D2, D3), `docs/m2-plan.md` (ของที่มีแล้ว)

## 0. เป้าหมายและขอบเขต

ห้องนโยบาย "ต้องอนุมัติ" มีคนอนุมัติได้จริง: ผู้อนุมัติหลักเห็นคิว → อนุมัติ/ปฏิเสธพร้อมเหตุผล →
ผู้จองได้รับแจ้งในระบบ · มีผู้รักษาการแทน · คำขอค้างเกิน SLA เปิดสิทธิ์ผู้อนุมัติสำรอง · คำขอใกล้วันใช้งานหมดอายุอัตโนมัติ

**ทำใน M3:** FR-18 (ส่งผู้อนุมัติของห้อง), FR-20 (ผู้รักษาการ + `acted_by`/`on_behalf_of`), FR-21 (SLA 2 วันทำการ → เปิดสิทธิ์สำรอง + เตือนซ้ำ), FR-22 (หมดอายุเมื่อเหลือ 24 ชม.), FR-23 (เร่งด่วน → หลัก+สำรองพร้อมกัน; ส่งล่วงหน้า <24 ชม. หมดอายุเมื่อถึงเวลาเริ่ม), FR-24 (ปฏิเสธต้องมีเหตุผล), แจ้งเตือนในระบบ (กระดิ่ง), `run_jobs`
**ไม่ทำใน M3:** LINE/อีเมล, จองเป็นชุด (M4), amendment/บังคับย้าย (M5), no-show/รายงาน (M6)
**หมายเหตุ:** FR-19 ถูกยกเลิกใน SRS 0.2 (มาก่อนได้ก่อน) — ไม่มีการจัดสรรแข่งกัน คิวของผู้อนุมัติจึงไม่มีรายการชนกันเอง

## 1. ร่างหน้าจอ

```
[แถบบน]  SIGROOM | ปฏิทิน | จองห้อง | การจองของฉัน | รออนุมัติ (2)   🔔3   ชื่อผู้ใช้ | ออกจากระบบ
          "รออนุมัติ (n)" เห็นเฉพาะคนที่เป็นผู้อนุมัติ/ผู้รักษาการ/สำรองของห้องใดห้องหนึ่ง
```

### S7 คิวรออนุมัติ  `/approvals/`
```
รายการรอการอนุมัติของฉัน (เรียงใกล้วันใช้งานก่อน)
┌──────────────────────────────────────────────────────────────────────────────┐
│ 🔴 เร่งด่วน · MTG-1 ห้องประชุม 1 · พรุ่งนี้ 13:00–14:00                        │
│    ประชุมเตรียมการฝึก — แผนกวิชาการสื่อสาร · ร.อ.สมชาย (โทร 081-…)             │
│    ผู้เข้าร่วม 12 · อุปกรณ์: ชุดประชุมออนไลน์ · ส่งเมื่อ 24 ส.ค. 09:12          │
│    หมดอายุใน 13 ชม.                                    [อนุมัติ]  [ปฏิเสธ]     │
├──────────────────────────────────────────────────────────────────────────────┤
│ 🟡 เกิน SLA (ค้าง 3 วันทำการ) · MTG-CO · 2 ก.ย. 09:00–12:00  (ฉันเป็นสำรอง)    │
│    …                                                   [อนุมัติ]  [ปฏิเสธ]     │
└──────────────────────────────────────────────────────────────────────────────┘
กด [ปฏิเสธ] → กล่องเหตุผล (บังคับกรอก, มีรายการเหตุผลที่เคยใช้ + พิมพ์เอง) [ยืนยันการปฏิเสธ]
กดชื่อกิจกรรม → S5 รายละเอียดเต็ม (ผู้อนุมัติของห้องเห็นเต็มอยู่แล้ว) ซึ่งมีปุ่มอนุมัติ/ปฏิเสธเช่นกัน
ว่าง: "ไม่มีคำขอรออนุมัติ"
```

### S8 ผู้รักษาการแทน  `/approvals/delegation/`
```
(เห็นเฉพาะผู้อนุมัติหลักของห้องใดห้องหนึ่ง)
มอบหมายผู้รักษาการเมื่อฉันไม่อยู่:
  ผู้รักษาการ [เลือกผู้ใช้ ▼ พิมพ์ค้นหาได้]   ตั้งแต่ [25/08/2569] ถึง [29/08/2569]   [บันทึก]
รายการมอบหมายของฉัน: ตาราง ผู้รักษาการ | ช่วงวันที่ | สถานะ (กำลังใช้/รอถึงวัน/สิ้นสุด) | [ยกเลิก]
กติกา: ช่วงวันที่ทับซ้อนกันไม่ได้ · มอบหมายให้ตัวเองไม่ได้ · ระหว่างช่วง คำขอของห้องฉันเข้าคิวผู้รักษาการแทน
```

### S9 แจ้งเตือน  `/notifications/` + กระดิ่งบนแถบ
```
🔔 ตัวเลข = ยังไม่อ่าน · กดกระดิ่ง → หน้ารายการ (ใหม่→เก่า, ยังไม่อ่านตัวหนา)
  • "คำขอ [BK-1A2B] MTG-1 25 ส.ค. 13:00 ได้รับการอนุมัติ" — กดแล้วไปหน้าการจองและนับว่าอ่านแล้ว
  • "มีคำขอใหม่รออนุมัติ: MTG-1 25 ส.ค. 13:00 (เร่งด่วน)"
  • "คำขอ [BK-9F3C] ถูกปฏิเสธ: อุปกรณ์ห้องไม่พร้อม"   [ทำเครื่องหมายอ่านทั้งหมด]
ข้อความแจ้งเตือนใช้ รหัสจอง + ห้อง + วัน-เวลา + สถานะ ไม่ใส่ชื่อกิจกรรม (เตรียมตาม SR-08 ตั้งแต่ตอนนี้)
```

### ส่วนที่เพิ่มในหน้าเดิม
- **S5 รายละเอียด**: กล่อง "ประวัติการพิจารณา" — ส่งเมื่อ / อนุมัติโดย ร.อ.วนิดา (รักษาการแทน พ.ต.สมศักดิ์) เมื่อ … / เหตุผลปฏิเสธ ถ้ามี · ผู้อนุมัติเห็นปุ่ม [อนุมัติ] [ปฏิเสธ] บนหน้านี้ด้วย
- **S6 การจองของฉัน**: แถวที่ถูกปฏิเสธแสดงเหตุผลย่อ · สถานะ "หมดอายุ" แสดงคำอธิบายสั้น

## 2. สเปกเทคนิค (สำหรับ Codex)

### 2.1 แอป/โมเดลใหม่ (migration แบบ expand เท่านั้น)
สร้างแอป `approvals` และ `notifications` (เพิ่มใน INSTALLED_APPS + อัปเดตแผนผังใน CLAUDE.md)

```
approvals.Approval            # ประวัติการพิจารณา (SRS §12.1 APPROVAL — amendment_id ค่อยเพิ่ม M5)
  booking      FK Booking (PROTECT, related_name="approvals")
  action       choices: submitted / approved / rejected / expired
  acted_by     FK User null=True   # null = ระบบ (เช่น หมดอายุ)
  on_behalf_of FK User null=True   # ผู้อนุมัติหลักที่ถูกรักษาการแทน
  reason       TextField blank
  acted_at     DateTimeField auto_now_add

approvals.ApproverDelegation  # FR-20
  delegator FK User related_name="delegations_given"
  delegate  FK User related_name="delegations_received"
  start_date DateField, end_date DateField
  created_at auto
  Meta: CheckConstraint(end_date >= start_date), CheckConstraint(delegator != delegate)
  ห้ามช่วงทับซ้อนของ delegator เดียวกัน: ตรวจใน service ตอนสร้าง (ไม่ต้อง exclusion constraint)

notifications.Notification
  user FK User related_name="notifications"
  text CharField(300)          # รหัสจอง+ห้อง+เวลา+สถานะ ห้ามใส่ชื่อกิจกรรม
  url  CharField(200) blank
  booking FK Booking null=True on_delete=SET_NULL
  created_at auto, read_at DateTimeField null
  Meta: index (user, read_at)

Booking (เพิ่มฟิลด์ — expand):
  sla_escalated_at DateTimeField null   # กันเตือน SLA ซ้ำ
  decision_reason  TextField blank      # สำเนาเหตุผลปฏิเสธล่าสุด ให้ S6 ใช้เร็ว
```

### 2.2 services

`approvals/services.py`
| ฟังก์ชัน | พฤติกรรม |
|---|---|
| `active_delegate(approver, on_date)` | ผู้รักษาการของ approver ในวันนั้น หรือ None |
| `effective_approver_ids(room, now)` | dict: `primary_ids` (หลัก หรือผู้รักษาการของหลักในช่วงวันนั้น), `backup_ids` — จาก `ResourceApprover` |
| `can_decide(user, booking, now)` | True เมื่อ: superuser · อยู่ใน primary_ids · หรืออยู่ใน backup_ids และ (booking.is_urgent หรือเกิน SLA ตาม `sla_deadline`) |
| `sla_deadline(booking)` | submitted_at + 2 วันทำการ (จันทร์–ศุกร์ เวลาเดียวกัน) |
| `expiry_deadline(booking)` | start_at − 24 ชม. · แต่ถ้า (start_at − submitted_at) < 24 ชม. → start_at (FR-23) |
| `approve_booking(booking, user, now)` | ใน `transaction.atomic` + `select_for_update` โหลด booking ใหม่: ต้องเป็น PENDING (ถ้าไม่ → ValueError "คำขอนี้ถูกดำเนินการแล้ว"), `can_decide` (ถ้าไม่ → PermissionError), now < expiry_deadline (ถ้าเกิน → ValueError "คำขอหมดอายุแล้ว") → APPROVED, สร้าง Approval(action=approved, acted_by=user, on_behalf_of=หลักถ้า user เป็นผู้รักษาการ), notify ผู้จอง + custodians ของห้อง |
| `reject_booking(booking, user, reason, now)` | เหมือนกันแต่ reason ว่าง → ValidationError "กรุณาระบุเหตุผล" → REJECTED, `release_holds`, `decision_reason=reason`, Approval, notify ผู้จอง |
| `pending_for(user, now)` | คิวของ user: PENDING ที่ user ตัดสินได้ พร้อม annotate `is_over_sla`, `expires_at` เรียงตาม start_at |
| `create_delegation(delegator, delegate, start, end)` | ตรวจ: delegator เป็นผู้อนุมัติหลักของอย่างน้อย 1 ห้อง, ไม่ทับซ้อนช่วงเดิม, delegate ≠ delegator → สร้าง + notify delegate |
| `run_scheduled_jobs(now)` | **idempotent**: (1) PENDING ที่ now ≥ expiry_deadline → EXPIRED + release_holds + Approval(action=expired, acted_by=None) + notify ผู้จองและผู้อนุมัติ (2) PENDING ที่ now ≥ sla_deadline และ `sla_escalated_at IS NULL` → ตั้ง sla_escalated_at + notify หลัก (เตือนซ้ำ) และสำรอง (เปิดสิทธิ์) · คืน dict จำนวนที่ทำ เพื่อ log |

`notifications/services.py`
- `notify(users, text, url="", booking=None)` — สร้างรายการ (ข้อความห้ามมีชื่อกิจกรรม — ใช้ `booking_ref(booking)` = 8 ตัวแรกของ id พิมพ์ใหญ่)
- `unread_count(user)` · `mark_read(user, notification_id | all)`
- hook จุดที่มีอยู่แล้ว: `submit_booking` (M2) → หลังสำเร็จ ให้ view เรียก `notify_submitted(booking)`: แจ้งผู้จอง (ยืนยันส่ง) และถ้า PENDING แจ้ง effective approvers (+สำรองถ้า is_urgent ตาม FR-23) — ทำใน view/service ใหม่ **ห้ามแก้ตัว `submit_booking` เดิม**

### 2.3 management command
`bookings/management/commands/run_jobs.py` → เรียก `approvals.services.run_scheduled_jobs(timezone.now())` แล้วพิมพ์สรุป · เอกสารวิธีตั้ง Task Scheduler ทุก 5 นาทีเขียนใน `docs/m3-notes.md` (ยังไม่ต้องตั้งจริงจนกว่า M6)

### 2.4 URL / view (แอป approvals และ notifications, ทุกอัน `login_required`)
| URL | ทำอะไร |
|---|---|
| `/approvals/` | S7 — ถ้า user ไม่มีสิทธิ์ตัดสินห้องใดเลยและไม่มีรายการ → 403 หน้าข้อความไทย |
| `/approvals/<uuid:id>/approve/` | POST → `approve_booking` → messages + redirect กลับ |
| `/approvals/<uuid:id>/reject/` | POST (reason) → `reject_booking` |
| `/approvals/delegation/` | S8 — GET รายการ+ฟอร์ม / POST สร้าง · `/approvals/delegation/<id>/delete/` POST ยกเลิก (เฉพาะของตนเอง สถานะยังไม่สิ้นสุด) |
| `/notifications/` | S9 — GET รายการ 50 ล่าสุด · `/notifications/read-all/` POST · กดรายการ = redirect ไป url พร้อม mark read (`/notifications/<id>/open/`) |
| context processor หรือ inclusion tag | ตัวเลขกระดิ่ง + ตัวเลข "รออนุมัติ" บนแถบ (query เบา ๆ, เฉพาะผู้เกี่ยวข้อง) |

### 2.5 template
- `approvals/queue.html`, `approvals/delegation.html`, `notifications/list.html` · แก้ `base.html` (เมนู+กระดิ่ง), `bookings/booking_detail.html` (ประวัติการพิจารณา + ปุ่มอนุมัติ/ปฏิเสธ), `bookings/my_bookings.html` (เหตุผลปฏิเสธ)
- กล่องเหตุผลปฏิเสธ: `<details>`/HTMX inline form + datalist จากเหตุผลที่ user เคยใช้ (`Approval.objects.filter(acted_by=user, action="rejected")` 10 ค่าล่าสุด)
- ป้าย: 🔴 เร่งด่วน (`is_urgent`) · 🟡 เกิน SLA · แสดง "หมดอายุใน X ชม." จาก `expiry_deadline`

### 2.6 seed (แก้ `seed_pilot --demo-users`)
- เพิ่มบัญชี `somsak` (พ.ต.สมศักดิ์ HQ) = ผู้อนุมัติหลัก **MTG-CO** และผู้อนุมัติสำรอง **MTG-1** · wanida คงเป็นหลักของ MTG-1 · รหัสผ่านเดียวกับ demo เดิม

### 2.7 เทส (`approvals/tests.py`) — ทุกข้อ inject `now` ไม่ใช้ sleep
1. wanida เห็นคำขอ MTG-1 ในคิว · somchai เปิด `/approvals/` ได้ 403 · somsak (สำรอง) ยังไม่เห็นก่อน SLA
2. approve → APPROVED + Approval(acted_by=wanida) + Notification ถึง somchai
3. reject ไม่ใส่เหตุผล → error ไทย · ใส่แล้ว → REJECTED + hold ปลด + เหตุผลแสดงใน S5/S6
4. delegation ช่วงวันที่ active → somsak (ในบท delegate) อนุมัติแทน wanida ได้ และ `on_behalf_of=wanida` · นอกช่วง → PermissionError · ช่วงทับซ้อน → ValidationError
5. สำรอง: ก่อน SLA `can_decide=False` · หลัง 2 วันทำการ → True · `is_urgent=True` → True ทันที
6. `run_scheduled_jobs`: คำขอเหลือ 23 ชม. → EXPIRED + ปลด hold · คำขอที่ส่งล่วงหน้า 20 ชม. ไม่หมดอายุจน `now = start_at` (FR-23)
7. `run_scheduled_jobs` เรียกซ้ำ → ไม่สร้าง Notification/Approval ซ้ำ (นับจำนวนเท่าเดิม)
8. SLA: เกิน 2 วันทำการ → `sla_escalated_at` ตั้งครั้งเดียว + สำรองได้รับแจ้ง
9. กดอนุมัติพร้อมกันสองครั้ง (เรียก service ซ้ำหลัง APPROVED) → ครั้งที่สอง ValueError "ถูกดำเนินการแล้ว" ไม่สร้าง Approval ซ้ำ
10. Notification: `unread_count` ถูกต้อง · เปิดรายการแล้ว read_at ตั้ง · user เห็นเฉพาะของตัวเอง · ข้อความไม่มีชื่อกิจกรรม (assert title not in text)
- เทสเดิม 19 ข้อต้องผ่าน

### 2.8 นิยาม "เสร็จ"
- `uv run pytest` ผ่านทั้งหมด (19 + ~10 ใหม่) · `check` สะอาด · `makemigrations --check` ไม่ค้าง
- **ห้ามแตะ**: `BookingResource` + constraints, `compute_hold/place_holds/release_holds/approval_policy_for`, พฤติกรรมเดิมของ `submit_booking` (hook แจ้งเตือนทำที่ view), เทส M1/M2 (แก้ได้เฉพาะเหตุจำเป็นและอธิบายใน notes)
- ไม่เพิ่มแพ็กเกจใหม่ · ภาษาไทยทุกข้อความ · กฎอยู่ใน services
- อัปเดต `docs/build-plan.md` (ติ๊ก M3) + เขียน `docs/m3-notes.md` (สิ่งที่ทำ/ตัดสินใจเอง/วิธีดูผล) + อัปเดตแผนผังใน `CLAUDE.md`
- งานยังไม่ commit — ให้ Claude ตรวจ diff ก่อน

## 3. ดูผลด้วยตา (หลัง Codex เสร็จ)
1. `uv run manage.py seed_pilot --demo-users` → `runserver`
2. `somchai` จอง MTG-1 มะรืนนี้ 13:00–14:00 → สถานะรออนุมัติ · กระดิ่งของ somchai มี "ส่งคำขอแล้ว"
3. เข้า `wanida` → แถบบนมี "รออนุมัติ (1)" → เปิดคิว เห็นรายละเอียดเต็ม → กดปฏิเสธโดยไม่กรอกเหตุผล → ระบบไม่ยอม → กรอก "ห้องติดภารกิจ ผบ." → ยืนยัน
4. กลับ `somchai` → กระดิ่งแจ้ง "ถูกปฏิเสธ: ห้องติดภารกิจ ผบ." · การจองของฉันแสดงเหตุผล · ปฏิทินช่วงนั้นว่างแล้ว
5. จองใหม่อีกครั้ง → `wanida` ตั้งผู้รักษาการ = somsak วันนี้–พรุ่งนี้ → เข้า `somsak` เห็นคิว กดอนุมัติ → S5 แสดง "อนุมัติโดย พ.ต.สมศักดิ์ (รักษาการแทน ร.อ.วนิดา)"
6. รัน `uv run manage.py run_jobs` → ไม่มีอะไรเปลี่ยน (ไม่มีคำขอค้าง) — ลองจองห้องประชุมเวลาใกล้ ๆ (พรุ่งนี้เช้า) แล้วรันอีกครั้งเพื่อดูหมดอายุ
