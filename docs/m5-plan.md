# SIGROOM — แผน M5: แก้ไขหลังอนุมัติ (Amendment) + บังคับย้าย (Preemption)

สถานะ: **ร่างเพื่อให้ผู้ใช้ดูหน้าจอก่อน → แล้ว Codex ลงมือ**
อ้างอิง: SRS 0.4 §6.4 (FR-34–38), §8 (FR-25–30) และผลตรวจ P1 ทั้ง 3 ข้อ (บันทึกในบทสนทนา SRS: ชุดปลายทางครบ / constraint ครบ / base_revision)
**คำเตือนถึง Codex:** milestone นี้แตะตารางถือครองเวลา ผิดพลาด = ห้องหาย/จองซ้อน ทำตามสเปกทีละข้อ ห้ามตีความเอง ถ้าสเปกขัดกันให้หยุดและบันทึกใน notes แทนการเดา

## 0. เป้าหมายและขอบเขต

- **Amendment:** ผู้จองขอแก้ เวลา/ห้อง/อุปกรณ์/ผู้เข้าร่วมภายนอก ของการจองที่ **อนุมัติแล้ว** โดยการจองเดิมคงอยู่จนกว่าการแก้จะอนุมัติ ปฏิเสธแล้วของเดิมไม่หาย (FR-34–38)
- **Preemption:** งานสำคัญแทรกห้องที่อนุมัติแล้วอย่างเป็นกระบวนการ: เหตุผล+เลขอ้างอิง, ห้องทดแทน, รับทราบ, ประวัติครบ (FR-25–30)
- การจองสถานะ "รออนุมัติ" ยังใช้วิธี ยกเลิกแล้วจองใหม่ (ถูกกว่า ไม่มีof เสียสิทธิ์) — ปุ่มขอแก้ไขแสดงเฉพาะ "อนุมัติ"
- รายงานการบังคับย้ายแบบเต็มอยู่ M6 — M5 มีหน้า Admin อ่านได้

## 1. ร่างหน้าจอ

### S5 (เพิ่ม) — การจองสถานะอนุมัติ ของผู้จองเอง ก่อนเส้นตาย 4 ชม.
```
[แก้ไขรายละเอียด]  [ขอแก้ไขเวลา/ห้อง/อุปกรณ์ →]  [ยกเลิกการจอง]
ถ้ามีคำขอแก้ไขค้าง: กล่องเหลือง "คำขอแก้ไข [AM-7C2E] รออนุมัติ" + ตารางเทียบ เดิม→ใหม่ + [ถอนคำขอแก้ไข]
ถ้าถูกบังคับย้าย: กล่องแดง "ถูกย้ายตามคำสั่ง <เลขอ้างอิง> โดย <ตำแหน่งผู้สั่ง>" + ห้อง/เวลาทดแทน (ถ้ามี) + ปุ่ม [รับทราบ]
```

### S13 ฟอร์มขอแก้ไข  `/bookings/<id>/amend/`
```
การจองเดิม: วิชาสายอากาศ · B1-201 · พ 27 ส.ค. 09:00–12:00 (คงอยู่จนกว่าการแก้ไขจะอนุมัติ)
สิ่งที่ขอแก้ (กรอกเฉพาะที่เปลี่ยน ช่องอื่นแสดงค่าเดิม):
  วันที่ [27/08/2569]  เริ่ม [13:00 ▼]  สิ้นสุด [16:00 ▼]
  ห้อง   [B1-201 (เดิม) ▼]  — รายการเฉพาะห้องที่ว่างในช่วงใหม่ + ห้องเดิม
  อุปกรณ์ส่วนกลาง [☑ โปรเจกเตอร์พกพา 1] [☐ ชุดประชุมออนไลน์ 1]   ← ชุดเต็มที่จะใช้จริง ไม่ใช่ส่วนต่าง
  ผู้เข้าร่วมภายนอก (○ ไม่มี ● มี) [รายละเอียด]     จำนวนผู้เข้าร่วม [30]
ผลการประเมิน: 🕒 การแก้ไขนี้ต้องผ่านผู้อนุมัติของห้อง B1-201   (หรือ ✅ มีผลทันทีเมื่อกดส่ง)
⚠ ระหว่างรอผล ช่วงเวลาใหม่จะถูกกันไว้ชั่วคราว และช่วงเวลาเดิมยังเป็นของคุณ
[ส่งคำขอแก้ไข]   [ยกเลิก]
```

### S7 (เพิ่ม) — การ์ดคำขอแก้ไขในคิวอนุมัติ
```
│ ✏ คำขอแก้ไข [AM-7C2E] · วิชาสายอากาศ — แผนกวิชาการสื่อสาร                    │
│    เดิม: B1-201 · พ 27 ส.ค. 09:00–12:00      ใหม่: B1-201 · พ 27 ส.ค. 13:00–16:00 │
│    อุปกรณ์: เดิม โปรเจกเตอร์พกพา 1 → ใหม่ (เหมือนเดิม)                          │
│    หมดอายุใน 20 ชม. (นับจากเวลาเริ่มที่เร็วกว่า)        [อนุมัติ]  [ปฏิเสธ]      │
```

### S14 บังคับย้าย  `/bookings/<id>/preempt/`  (ผู้อนุมัติหลัก/รักษาการของห้องนั้น + ผู้ดูแลระบบ)
```
ขั้น 1 เหตุผลและอ้างอิง:  เหตุผล* [ภารกิจ ผบ. เร่งด่วน] ▾   เลขอ้างอิงคำสั่ง/หนังสือ* [กห 0021/…]
ขั้น 2 งานที่จะเข้าแทน (สร้างเป็นการจองใหม่ สถานะอนุมัติทันที):
  ชื่อกิจกรรม* [ประชุม ผบ.] หน่วย* [กองบังคับการ ▼] ผู้รับผิดชอบ* […] โทร* […]
  เวลา [ค่าเริ่มต้น = ช่วงของการจองเดิม แก้ได้ ต้องซ้อนกับการจองเดิม] การมองเห็น [จำกัด ▼]
ขั้น 3 ห้องทดแทนให้ผู้จองเดิม (ระบบเสนอที่ว่างช่วงเดิม ≥3 ถ้ามี เรียงตามสิทธิ์):
  (● B1-202 — อนุมัติอัตโนมัติ, จะยืนยันทันที)
  (○ LAB-COMM — อนุมัติอัตโนมัติ)  (○ MTG-CO — ต้องอนุมัติของห้องนั้น จะเข้าคิวแบบเร่งด่วน)
  (○ ไม่มีห้องทดแทน)
สรุปผลกระทบ: ผู้จองเดิม (ร.อ.สมชาย) จะได้รับแจ้งทันทีและต้องกดรับทราบ ไม่ตอบใน 24 ชม. ถือว่ารับทราบ
[ยืนยันบังคับย้าย]  [ยกเลิก]
```

### ปฏิทิน
- ช่วงเวลาใหม่ของ amendment แสดงเป็นแท่งลายเส้น "รออนุมัติ" (ป้ายตามสิทธิ์มองเห็นเหมือนการจองปกติ) · การจองเดิมแสดงปกติพร้อมจุด ✏ สำหรับผู้มีสิทธิ์เห็นรายละเอียด

## 2. สเปกเทคนิค

### 2.1 การเปลี่ยน schema (expand — จุดที่ **อนุญาตให้แตะของเดิม** ระบุชัดที่นี่เท่านั้น)
```
bookings.BookingAmendment
  id uuid PK · booking FK(PROTECT, related_name="amendments") · submitted_by FK User
  status choices: pending / approved / rejected / expired / withdrawn
  base_revision PositiveInt                      # P1.3 — ค่า booking.revision ตอนยื่น
  proposed_room FK Resource(PROTECT) null        # null = ห้องเดิม
  proposed_start_at / proposed_end_at DateTimeField null   # null = เวลาเดิม (ต้องมาคู่กัน)
  proposed_equipment M2M Resource blank          # P1.1 — ชุดเต็มที่จะใช้ ไม่ใช่ส่วนต่าง
  proposed_attendees PositiveInt null · proposed_has_external BooleanField null
  proposed_external_note CharField blank
  reason CharField(300) blank                    # เหตุผลของผู้ขอ (แสดงผู้อนุมัติ)
  decision_reason TextField blank · submitted_at auto · decided_at null · is_urgent bool
  sla_escalated_at DateTimeField null
  Meta constraints:
    UniqueConstraint(fields=["booking"], condition=Q(status="pending"), name="one_pending_amendment_per_booking")   # FR-36
    UniqueConstraint(fields=["id", "booking"], name="uniq_amendment_id_booking")   # รองรับ composite FK ด้านล่าง
    CheckConstraint((proposed_start_at IS NULL) = (proposed_end_at IS NULL), name="amendment_times_together")

bookings.BookingResource (แก้ — ได้รับอนุญาตเฉพาะรายการนี้):
  + amendment FK BookingAmendment null blank on_delete=PROTECT related_name="holds"
  + แก้ UniqueConstraint เดิม uniq_active_hold_per_booking_resource → เพิ่มเงื่อนไข amendment IS NULL
  + เพิ่ม UniqueConstraint(fields=["amendment","resource"], condition=Q(released_at__isnull=True), name="uniq_active_amendment_hold")
  + ใน migration เดียวกัน เพิ่ม RunSQL composite FK (P1.2):
      ALTER TABLE bookings_bookingresource ADD CONSTRAINT fk_amendment_same_booking
      FOREIGN KEY (amendment_id, booking_id) REFERENCES bookings_bookingamendment (id, booking_id)
      DEFERRABLE INITIALLY DEFERRED;   (reverse_sql: DROP CONSTRAINT)
    → กันแอปผูก amendment ของ booking อื่นเพื่อหลบ exclusion constraint
  ❗ ห้ามแตะ ExclusionConstraint `excl_overlapping_holds` — พฤติกรรมเดิมถูกต้องอยู่แล้ว:
    แถว amendment ใช้ booking_id เดียวกับการจองเดิม จึงซ้อนกับของตัวเองได้ (FR-35) แต่ชนคนอื่นไม่ได้

approvals.Approval (แก้ — อนุญาต): + amendment FK null blank related_name="approvals"
  + CheckConstraint: อ้าง booking หรือ amendment อย่างน้อยหนึ่ง (มี booking เสมอในทางปฏิบัติ — ใช้ booking ของ amendment)

bookings.Preemption
  id uuid PK · displaced FK Booking(PROTECT, related_name="preemption_as_displaced")
  incoming FK Booking(PROTECT, related_name="preemption_as_incoming")
  replacement FK Booking(PROTECT, null, related_name="preemption_as_replacement")
  ordered_by FK User · ordered_by_position CharField(200)   # ตำแหน่ง ณ วันสั่ง (FR-29 ใช้ในข้อความ)
  reference_no CharField(100) · reason CharField(300)
  acknowledged_at DateTimeField null · deemed_acknowledged Bool default False · created_at auto
```

### 2.2 services ใหม่ `bookings/amendment_services.py`
| ฟังก์ชัน | พฤติกรรม |
|---|---|
| `evaluate_amendment_policy(booking, proposed)` | นโยบายของห้องปลายทาง + ถ้า `proposed_has_external` เป็นจริง → REQUIRED (ตรรกะเดียวกับ `approval_policy_for` ห้ามก็อปโค้ด — refactor ให้เรียกร่วมกันได้โดยไม่แก้พฤติกรรมเดิม) |
| `submit_amendment(booking, user, proposed, now)` | ใน `transaction.atomic` + `select_for_update(booking)`: ตรวจ (1) ผู้ยื่น = requester/superuser (2) booking สถานะ APPROVED และ usage_status = UPCOMING (3) ก่อนเส้นตาย 4 ชม. ของเวลาเริ่มเดิม (4) ไม่มี amendment ค้าง (5) `validate_booking_window` ของห้อง/เวลาปลายทาง (6) มีอะไรเปลี่ยนจริงอย่างน้อย 1 ฟิลด์ → สร้าง amendment (`base_revision = booking.revision`) → วางช่วงถือครองชั่วคราว: แถว `BookingResource(booking=เดิม, amendment=ใหม่)` สำหรับ **ห้องปลายทาง + อุปกรณ์ชุดเต็ม** ช่วงเวลาปลายทาง (P1.1) — ชนคนอื่น → BookingConflict ยกเลิกทั้งหมด ของเดิมไม่ขยับ → ประเมินนโยบาย: AUTO → เรียก `apply_amendment` ทันทีใน transaction เดียวกัน (FR-38) · REQUIRED → pending + `is_urgent` ตาม FR-23 + แจ้งผู้อนุมัติห้องปลายทาง และถ้าเปลี่ยนห้องข้ามเจ้าของ แจ้งผู้อนุมัติห้องเดิมเพื่อทราบ |
| `apply_amendment(amendment, acted_by, on_behalf_of, now)` | **หัวใจ FR-38 + P1.3** ใน `transaction.atomic`: `select_for_update` booking → ตรวจ booking ยัง APPROVED + usage UPCOMING และ `booking.revision == amendment.base_revision` ไม่ผ่าน → ValueError "ข้อมูลการจองเปลี่ยนไปแล้ว กรุณาถอนและยื่นใหม่" → (1) `released_at` ให้แถวถือครองเดิม (`amendment IS NULL`) (2) แถวของ amendment: เซ็ต `amendment=NULL` เลื่อนเป็นแถวหลัก (3) เขียนค่าที่เสนอทั้งหมดลง booking + sync `booking.equipment` + `revision += 1` (4) amendment → approved + `decided_at` (5) Approval(action=approved, amendment=…) (6) แจ้งผู้จอง + จนท.ห้องเดิมและใหม่ · **ระวัง:** ขั้น (2) ต้องมาก่อน constraint ตรวจ `uniq_active_hold_per_booking_resource` — ใช้ลำดับ (1) แล้ว (2) ใน transaction เดียว (constraint เป็น immediate ได้เพราะ (1) ปลดแถวเดิมก่อน) |
| `withdraw_amendment(amendment, user, reason, now)` / `reject_amendment(...)` / `expire_amendment(...)` | ปลดเฉพาะแถวของ amendment · เดิมไม่แตะ · Approval + แจ้ง (ปฏิเสธต้องมีเหตุผล) |
| `amendment_expiry_deadline(a)` | ใช้กติกา FR-22/23 กับ `min(เวลาเริ่มเดิม, เวลาเริ่มใหม่)` (FR-36) |
| `amendment_ref(a)` | "AM-" + 4 ตัวแรก id |

### 2.3 services ใหม่ `bookings/preemption_services.py`
| ฟังก์ชัน | พฤติกรรม |
|---|---|
| `can_preempt(user, booking, now)` | superuser หรือ ผู้อนุมัติหลัก/ผู้รักษาการของห้องนั้น (ใช้ `effective_approver_ids` เดิม — สำรองไม่มีสิทธิ์) |
| `replacement_options(booking, actor, now)` | ห้องว่างช่วงเดิม ความจุ ≥ attendees เรียง (1) นโยบายอัตโนมัติ (2) ห้องที่ actor เป็นผู้อนุมัติ (3) อื่น ๆ อย่างละไม่เกิน 3 |
| `execute_preemption(booking, actor, reason, reference_no, incoming_data, replacement_room, now)` | **transaction เดียว** + `select_for_update` displaced: ตรวจสิทธิ์ · displaced ต้อง APPROVED/UPCOMING · เวลา incoming ต้องซ้อน displaced → (1) ถ้ามี amendment ค้างของ displaced → withdraw + ปลดแถว (2) ปลดแถวถือครอง displaced + `usage_status=DISPLACED` (สถานะคำขอคง APPROVED ตาม SRS) (3) สร้าง incoming: APPROVED + place_holds (4) replacement: ห้องกลุ่ม (1)/(2) → APPROVED + holds · กลุ่ม (3) → PENDING + `is_urgent=True` + แจ้งผู้อนุมัติห้องนั้น · ไม่เลือก → ไม่มี (5) สร้าง Preemption (6) แจ้งผู้จองเดิม: "การจอง [BK-…] ถูกย้ายตามคำสั่ง <ref> โดย <ตำแหน่ง>" + ห้องทดแทน + ลิงก์กดรับทราบ (ห้ามมีชื่อกิจกรรม incoming — FR-29) แจ้ง จนท.ห้องทั้งสอง · ล้มเหลวขั้นไหน → ย้อนทั้งหมด |
| `acknowledge(preemption, user, now)` | เฉพาะผู้จองเดิม · ตั้ง `acknowledged_at` แจ้งผู้สั่ง |
| ใน `run_scheduled_jobs` (แก้ approvals/services.py — อนุญาต): | เพิ่ม 3 งาน idempotent: (ก) amendment pending เกิน `amendment_expiry_deadline` → expired (ข) amendment SLA ครั้งเดียว (`sla_escalated_at`) (ค) Preemption ที่ `acknowledged_at IS NULL AND NOT deemed_acknowledged AND created_at ≤ now−24h` → `deemed_acknowledged=True` + แจ้งผู้สั่ง |

### 2.4 การแก้ของเดิมที่อนุญาต (นอกเหนือจากนี้ = ห้าม)
- `bookings/services.py::cancel_booking` — เพิ่มท้าย: ถ้ามี amendment ค้าง → `withdraw_amendment` ใน transaction เดียวกัน (P1.3)
- `approvals/services.py` — `run_scheduled_jobs` (ตาม 2.3), `pending_for` เพิ่มการ์ด amendment, `can_decide` ขยายให้ใช้กับ amendment (ยึดห้องปลายทาง)
- `bookings/views.py::calendar_events` — เพิ่ม event ของแถว amendment (ลายเส้น pending, label ตามสิทธิ์)
- templates ที่เกี่ยว + `booking_edit` เดิม: ลบข้อความ "จะมีในรุ่นถัดไป" เปลี่ยนเป็นลิงก์ไป S13

### 2.5 URL / view
`/bookings/<id>/amend/` GET/POST (S13) · `/amendments/<id>/withdraw/` POST · `/approvals/amendments/<id>/approve|reject/` POST · `/bookings/<id>/preempt/` GET/POST (S14 — ตรวจ `can_preempt`) · `/preemptions/<id>/acknowledge/` POST · Django Admin: BookingAmendment (อ่าน), Preemption (อ่าน) · ทุก view `login_required`

### 2.6 เทส (`bookings/tests_m5.py`, `approvals/tests_m5.py` — inject now ทุกข้อ)
1. ยื่น amendment เปลี่ยนห้องอย่างเดียว → แถวชั่วคราวมี **ห้องใหม่ + อุปกรณ์เดิมครบ** (P1.1) และแถวเดิมยังถือครอง
2. ช่วงใหม่ชนการจองคนอื่น → ยื่นไม่ผ่าน ของเดิมไม่เปลี่ยน ไม่มีแถวค้าง
3. ขยายเวลา (ทับช่วงเดิมของตัวเอง) → ยื่นผ่าน (FR-35)
4. ปลายทางอัตโนมัติ → มีผลทันที: ค่าใหม่ถูกเขียน แถวเดิมปลด แถวใหม่เลื่อนเป็นหลัก revision+1
5. ปลายทางต้องอนุมัติ → pending · การ์ดโผล่คิวผู้อนุมัติห้องปลายทาง · เปลี่ยนห้องข้ามเจ้าของ → ผู้อนุมัติห้องเดิมได้แจ้งเพื่อทราบ
6. approve สำเร็จ = FR-38 ครบ · แก้ฟิลด์กลุ่ม (ค) ระหว่างรอ (revision ขยับ) → approve ล้ม "ข้อมูลเปลี่ยนไปแล้ว" ของเดิมคงอยู่
7. reject/withdraw → ปลดเฉพาะแถว amendment · เดิมไม่แตะ · ปฏิเสธไม่มีเหตุผล → error
8. ยื่นซ้ำระหว่างค้าง → ValidationError (unique partial ที่ DB ด้วย — ทดสอบผ่าน IntegrityError ตรง ๆ 1 ครั้ง)
9. cancel_booking ระหว่างมี amendment ค้าง → amendment ถูกถอน + แถวปลด (P1.3)
10. run_jobs: amendment หมดอายุตาม min(เวลาเดิม,ใหม่) − 24 ชม. + idempotent + SLA ครั้งเดียว
11. constraint: แถว amendment (booking เดียวกัน) อยู่ร่วมแถวหลัก active ได้ · ผูก amendment ของ booking อื่น → IntegrityError จาก composite FK (P1.2)
12. preemption: somchai ไม่มีสิทธิ์ 403 · wanida (หลักของ MTG-1) ทำได้
13. execute: แถว displaced ปลด + DISPLACED + incoming APPROVED ถือครองจริง — ใน transaction เดียว (จำลอง fail ขั้น replacement → ทุกอย่างย้อน)
14. replacement ห้องอัตโนมัติ → APPROVED ทันที · ห้องต้องอนุมัติต่างเจ้าของ → PENDING + urgent + ผู้สั่งไม่ได้อนุมัติแทน
15. ข้อความแจ้งผู้จองเดิมมี reference_no ไม่มีชื่อกิจกรรม incoming · acknowledge ตั้งเวลา · เกิน 24 ชม. → deemed ครั้งเดียว
16. เทสเดิม 43 ข้อผ่านโดยไม่แก้
17. ปฏิทิน: แถว amendment แสดงเป็น event ลายเส้นพร้อม label ตามสิทธิ์ · S5 ผู้จองเห็นตารางเทียบเดิม→ใหม่

### 2.7 นิยาม "เสร็จ"
- `uv run pytest` ผ่านทั้งหมด (43 + ~17) · `check` สะอาด · `makemigrations --check` ไม่ค้าง (RunSQL composite FK อยู่ในไฟล์ migration ที่ generate แล้วเพิ่มมือ พร้อม reverse)
- ห้ามแตะนอกรายการ 2.1/2.4: ExclusionConstraint, `compute_hold/place_holds/release_holds/submit_booking/approve_booking/reject_booking/decide_series`, เทสเดิมทุกไฟล์
- ไม่เพิ่มแพ็กเกจ · ภาษาไทย · อัปเดต `build-plan.md` + `docs/m5-notes.md` + ER ใน SRS **ไม่ต้องแก้** (ตรงอยู่แล้ว) · ยังไม่ commit รอ Claude ตรวจ

## 3. ดูผลด้วยตา
1. `somchai` เปิดการจอง B1-201 ที่อนุมัติแล้ว → [ขอแก้ไขเวลา/ห้อง/อุปกรณ์] เลื่อนเวลาบ่าย → ปฏิทินเห็นทั้งแท่งเดิม (ปกติ) และแท่งใหม่ (ลายเส้น)
2. ห้องอัตโนมัติ → มีผลทันที · ลองกับ MTG-1 → การ์ด ✏ ในคิว `wanida` เห็นตารางเทียบ → ปฏิเสธ → ของเดิมไม่หาย
3. ยื่นใหม่ → `wanida` อนุมัติ → เวลาเปลี่ยน แท่งเดิมหาย
4. `wanida` เปิดการจอง MTG-1 ของ somchai → [บังคับย้าย] กรอกเหตุผล+เลขอ้างอิง เลือกห้องทดแทน B1-202 → ยืนยัน
5. `somchai` ได้กระดิ่ง "ถูกย้ายตามคำสั่ง…" (ไม่เห็นชื่องานที่มาแทน) → เห็นการจองทดแทน B1-202 อนุมัติแล้ว → กด [รับทราบ]
6. `uv run manage.py run_jobs` ไม่ทำอะไรซ้ำ
