# SIGROOM — แผน M4: จองเป็นชุด + ปฏิทินส่วนกลาง + งดใช้ห้อง

สถานะ: **ร่างเพื่อให้ผู้ใช้ดูหน้าจอก่อน → แล้ว Codex ลงมือ**
อ้างอิง: `CLAUDE.md`, SRS FR-11–17, D10, ของเดิม `docs/m2-plan.md` / `docs/m3-plan.md`

## 0. เป้าหมายและขอบเขต

**ทำใน M4:**
- จองเป็นชุด (FR-13–17, D10): รายวัน/รายสัปดาห์เลือกหลายวัน/กำหนดวันเอง · ตัวอย่างก่อนยืนยันพร้อมครั้งที่ชน · จองเฉพาะครั้งที่ว่าง · อนุมัติทั้งชุดครั้งเดียว ตัดบางครั้งได้พร้อมเหตุผล · แต่ละครั้งยกเลิกอิสระ
- ปฏิทินส่วนกลาง (FR-11): วันหยุด/พิธี/กิจกรรมรวม กำหนดขอบเขต ทุกห้อง/อาคาร/ประเภทห้อง/ห้องที่เลือก บล็อกการจองใหม่ และทำให้ชุดการจองข้ามครั้งนั้นอัตโนมัติ
- งดใช้ห้องชั่วคราว (FR-12): เจ้าหน้าที่ดูแลห้องตั้งช่วงงดใช้ + เหตุผล → บล็อกจองใหม่ แสดงการจองที่ได้รับผลกระทบ แจ้งผู้จอง และตั้งสถานะการใช้งาน "ห้องใช้งานไม่ได้"
- SLA/หมดอายุ/เร่งด่วน (M3) ต้องนับวันทำการโดย **ข้ามวันหยุดตามปฏิทินส่วนกลาง** (ปิดหมายเหตุที่ค้างจาก M3)

**ไม่ทำใน M4:** ย้ายการจองที่กระทบไปห้องอื่นอัตโนมัติ (บังคับย้าย = M5) · การแก้ไขชุดทั้งชุดหลังส่ง (ยกเลิกรายครั้ง/ทั้งชุดแล้วจองใหม่แทน) · รายงาน (M6)

**ข้อตัดสินใจที่ฝังในแผน (ทักได้):**
1. คำขอชุดที่ต้องอนุมัติ หมดอายุ **ทั้งชุด** เมื่อเหลือ 24 ชม. ก่อนครั้งแรก (นับเป็นคำขอเดียวตาม FR-16/22)
2. ครั้งที่ผู้อนุมัติตัดออก บันทึกเป็นการจองสถานะ "ปฏิเสธ" พร้อมเหตุผล (เห็นได้ในชุด)
3. ปฏิทินส่วนกลาง (Blackout) จัดการผ่าน **Django Admin** ใน M4 — ผู้ใช้ทั่วไปเห็นผลบนปฏิทินและตอนจองเท่านั้น
4. หน้าตั้งงดใช้ห้องเป็นหน้าเว็บง่าย ๆ สำหรับเจ้าหน้าที่ดูแลห้อง (ไม่ต้องเข้า Admin)

## 1. ร่างหน้าจอ

### S4 (เพิ่มในฟอร์มจองเดิม) — สลับ "จองเป็นชุด"
```
◻ จองเป็นชุด   (แสดงเฉพาะห้องที่กฎอนุญาต allow_series)
  รูปแบบ  (● รายสัปดาห์  ○ ทุกวันราชการ  ○ กำหนดวันเอง)
  รายสัปดาห์: [☑ จ] [☐ อ] [☑ พ] [☐ พฤ] [☐ ศ]
  สิ้นสุด  (● วันที่ [28/11/2569])  (○ จำนวน [16] ครั้ง)   สูงสุด <ตามกฎห้อง> ครั้ง
  เวลาใช้ทุกครั้ง: ตามช่องเวลาด้านบน
[ตรวจสอบชุดการจอง →]   (แทนปุ่มส่งคำขอเมื่อเปิดโหมดชุด)
```

### S10 ตรวจสอบชุดการจอง  `/book/<code>/series/preview/`
```
วิชาสายอากาศ — B1-201 · จันทร์และพุธ 09:00–12:00 · 25 ส.ค. – 28 พ.ย. 2569 (28 ครั้ง)
┌────┬────────────────┬──────────────────────────────────────────┐
│ 1  │ จ 25 ส.ค. 2569  │ ✅ ว่าง                                    │
│ 2  │ พ 27 ส.ค. 2569  │ ✅ ว่าง                                    │
│ 3  │ จ 1 ก.ย. 2569   │ ❌ ชน: ไม่ว่าง — แผนกวิชา EW (ตามสิทธิ์เห็น) │
│ 4  │ พ 3 ก.ย. 2569   │ ⏭ ข้าม: วันหยุดชดเชย (ปฏิทินส่วนกลาง)       │
│ …  │                 │                                          │
└────┴────────────────┴──────────────────────────────────────────┘
สรุป: ว่าง 25 · ชน 2 · ข้ามอัตโนมัติ 1
[จองเฉพาะครั้งที่ว่าง (25 ครั้ง)]   [← กลับไปเปลี่ยนเวลา]   [ยกเลิกทั้งชุด]
หมายเหตุ: ถ้ามีคนจองตัดหน้าระหว่างยืนยัน ครั้งนั้นจะถูกข้ามและแจ้งในผลลัพธ์
```

### S11 รายละเอียดชุด  `/series/<id>/`
```
ชุดการจอง [SR-3F21] วิชาสายอากาศ — B1-201 · จันทร์/พุธ 09:00–12:00 · สถานะ: อนุมัติ 24 · ปฏิเสธ 1 · ยกเลิก 1 · ข้าม 3
ตาราง: ครั้ง | วันที่ | สถานะคำขอ | หมายเหตุ (เหตุผลปฏิเสธ/ข้าม) | [ดู] [ยกเลิกครั้งนี้]
[ยกเลิกครั้งที่เหลือทั้งหมด]  (เฉพาะครั้งในอนาคตที่ยังไม่ถูกใช้)
หน้า S5 ของครั้งที่อยู่ในชุด มีบรรทัด "ส่วนหนึ่งของชุด [SR-3F21] → ดูทั้งชุด"
S6 การจองของฉัน: แถวของชุดยุบเป็นบรรทัดเดียว "ชุด 25 ครั้ง (ถัดไป จ 25 ส.ค.)" กดขยายได้
```

### S7 (เพิ่มในคิวอนุมัติ) — การ์ดชุด
```
│ ชุดการจอง · B1-… MTG-1 · จันทร์/พุธ 13:00–14:00 · 8 ครั้ง (25 ส.ค. – 17 ก.ย.)     │
│ ประชุมประจำสัปดาห์ — แผนกวิชาการสื่อสาร · หมดอายุใน 30 ชม. (นับจากครั้งแรก)        │
│ [ดูรายการทุกครั้ง ▾]  ☐ ตัดครั้งที่ 3 (1 ก.ย.) ออก  เหตุผล [ติดภารกิจหน่วย] ▾        │
│                                  [อนุมัติทั้งชุด (ตัด 1 ครั้ง)]   [ปฏิเสธทั้งชุด]      │
```

### S12 งดใช้ห้อง  `/resources/<code>/outage/`  (เจ้าหน้าที่ดูแลห้องนั้น + ผู้ดูแลระบบเท่านั้น)
```
ห้อง LAB-COMM · ตั้งงดใช้ชั่วคราว
ตั้งแต่ [26/08/2569 08:00] ถึง [30/08/2569 17:00]   เหตุผล [ซ่อมเครื่องปรับอากาศ] ▾
การจองที่ได้รับผลกระทบ (2): 27 ส.ค. 09:00 วิชา… (อนุมัติ) · 29 ส.ค. 13:00 [BK-…] (รออนุมัติ)
⚠ ระบบจะแจ้งผู้จองทุกราย ตั้งสถานะ "ห้องใช้งานไม่ได้" และให้เจ้าหน้าที่ประสานย้าย/ยกเลิกเอง (การย้ายอัตโนมัติมาใน M5)
[ยืนยันงดใช้]      รายการงดใช้ที่มีอยู่: ตาราง + [สิ้นสุดก่อนกำหนด]
```

### ปฏิทิน (S2) — เพิ่ม
- Blackout แสดงเป็นแถบพื้นหลังทั้งช่วง พร้อมชื่อ เช่น "วันเฉลิมฯ (ทุกห้อง)" — เห็นทุกคน
- ช่วงงดใช้ห้อง แสดงเป็นแถบพื้นหลังสีเทาเมื่อกรองดูห้องนั้น "งดใช้: ซ่อมแอร์"

## 2. สเปกเทคนิค (สำหรับ Codex)

### 2.1 โมเดลใหม่ (expand เท่านั้น)
```
bookings.BookingSeries
  id uuid PK · room FK Resource(PROTECT) · created_by FK User · unit FK Unit
  freq choices: weekly / workdays / custom
  weekdays JSONField(list[int] 0=จันทร์) default []
  custom_dates JSONField(list["YYYY-MM-DD"]) default []
  start_date DateField · end_date DateField null · requested_count PositiveInt null
  time_start TimeField · time_end TimeField
  created_at auto
  # ฟิลด์เนื้อหาใช้ของ Booking ครั้งแรกเป็นแม่แบบ ไม่เก็บซ้ำใน series

bookings.SeriesSkip            # ครั้งที่ไม่ได้สร้างเป็นการจอง
  series FK(related_name="skips") · occur_date DateField
  kind choices: blackout / conflict / conflict_at_submit
  reason CharField(200)

Booking (เพิ่ม — expand): series FK BookingSeries null related_name="occurrences"
                           series_index PositiveInt null   # ครั้งที่

resources.Blackout             # FR-11 — จัดการใน Django Admin
  title CharField · start_at DateTimeField · end_at DateTimeField
  scope choices: all / building / category / rooms
  building CharField blank · room_category CharField blank (choices ของ Resource.Category)
  rooms M2M Resource blank (จำกัด resource_type=room)
  created_by FK User null · Meta: Check(end_at > start_at)
  method `applies_to(resource) -> bool`

resources.ResourceOutage       # FR-12
  resource FK(related_name="outages") · start_at · end_at · reason CharField(200)
  created_by FK User · created_at auto · ended_early_at DateTimeField null
  Meta: Check(end_at > start_at)
```

### 2.2 services
`bookings/series_services.py` (ไฟล์ใหม่ — ไม่แตะ services.py เดิมนอกจากที่ระบุ 2.3)
| ฟังก์ชัน | พฤติกรรม |
|---|---|
| `generate_occurrence_dates(series_params, rule)` | รายการวันที่ตาม freq/weekdays/custom จน end_date หรือครบ requested_count · เกิน `rule.max_series_occurrences` → ValidationError · `rule.allow_series` เป็นเท็จ → ValidationError |
| `preview_series(room, series_params, booking_template, user, now)` | ต่อวันที่: (1) blackout ที่ครอบห้อง → skip(blackout, title) (2) `validate_booking_window` ผิด → skip พร้อมข้อความ (3) hold ชน → conflict พร้อม `calendar_label` ตามสิทธิ์ · คืนรายการ + สรุปนับ |
| `create_series(room, series_params, booking_template, user, mode="only_free")` | ใน `transaction.atomic`: สร้าง BookingSeries → ต่อครั้งที่ว่าง สร้าง Booking (สถานะตามนโยบายเหมือน `submit_booking`: ทั้งชุดเป็น APPROVED หรือ PENDING เหมือนกันหมด) + `place_holds` ใน savepoint — ชนตอนบันทึก → SeriesSkip(conflict_at_submit) ไม่ล้มทั้งชุด · blackout/ชนจาก preview → SeriesSkip · ตั้ง `series_index` เรียงตามวันที่ · ตั้ง `is_urgent` จากครั้งแรก · แจ้งเตือนเหมือนคำขอเดี่ยว (การ์ดชุดใบเดียว) · ไม่มีครั้งว่างเลย → ValidationError |
| `cancel_remaining(series, user, now)` | วนใช้ `cancel_booking` เดิมกับครั้งอนาคตที่ pending/approved · ครั้งที่ติดเส้นตาย 4 ชม. รายงานว่าข้ามพร้อมเหตุผล |
| `series_ref(series)` | "SR-" + 4 ตัวแรกของ id พิมพ์ใหญ่ |

`approvals/services.py` (เพิ่ม)
| ฟังก์ชัน | พฤติกรรม |
|---|---|
| `decide_series(series, user, action, excluded, reason_excluded, reason_reject, now)` | ล็อกทุก occurrence PENDING ด้วย `select_for_update` เรียง pk: `approve` → อนุมัติทุกครั้งยกเว้น excluded (excluded → REJECTED + ปลด hold + เหตุผล บังคับกรอกเมื่อมี excluded) · `reject` → ปฏิเสธทุกครั้ง (เหตุผลบังคับ) · Approval ต่อ occurrence (`acted_by/on_behalf_of` เดิม) · แจ้งผู้จอง 1 ใบสรุป "อนุมัติ 7 ตัด 1" · ทั้งหมดใน transaction เดียว (FR-16) |
| `series_expiry_deadline(series)` | จาก occurrence แรก (min start_at ของ PENDING/APPROVED) ตามกติกาข้อ 1 |
| แก้ `expiry_deadline(booking)` | ถ้า `booking.series_id` → ใช้ `series_expiry_deadline` ของชุด (ทั้งชุดหมดอายุพร้อมกันใน `run_scheduled_jobs` — ยังคง idempotent) |
| แก้ `sla_deadline` + `_urgent_deadline`(ใน bookings) | "วันทำการ" ข้ามวันที่มี Blackout scope=all ด้วย (ปิดหมายเหตุ M3) — เพิ่ม helper `is_business_day(date)` ใน approvals/services.py แล้วให้ทั้งสองฝั่งเรียกใช้ |
| `pending_for` | จัดกลุ่ม: occurrence ของชุดเดียวกันรวมเป็นการ์ดเดียว (ส่ง object ชุด + รายการครั้ง) |

`resources/services.py` (ไฟล์ใหม่)
| ฟังก์ชัน | พฤติกรรม |
|---|---|
| `active_blackouts(resource, start, end)` | Blackout ที่ครอบห้องและซ้อนช่วง |
| `active_outages(resource, start, end)` | Outage ที่ยังไม่ `ended_early_at` และซ้อนช่วง |
| `create_outage(resource, user, start, end, reason)` | สิทธิ์: custodian ของห้องหรือ superuser · สร้าง → หา booking ที่กระทบ (PENDING/APPROVED ซ้อนช่วง) → ตั้ง `usage_status=ROOM_UNAVAILABLE` + แจ้งผู้จองและ custodians (ข้อความไม่มีชื่อกิจกรรม) · **ไม่ปลด hold ไม่เปลี่ยนสถานะคำขอ** (รอย้าย/ยกเลิกโดยเจ้าหน้าที่; บังคับย้าย M5) · คืนรายการที่กระทบ |
| `end_outage_early(outage, user, now)` | ตั้ง `ended_early_at` · booking ที่ถูกธง ROOM_UNAVAILABLE และไม่โดน outage อื่น → คืนเป็น UPCOMING + แจ้ง |

### 2.3 แก้ของเดิม (อนุญาตเฉพาะจุดนี้ + เทส M2 เดิมต้องผ่านโดยไม่แก้)
- `bookings/services.py::validate_booking_window` — เพิ่มตรวจ 2 ข้อท้ายรายการ: ซ้อน blackout ("ติดวันหยุด/กิจกรรมส่วนกลาง: <title>") และซ้อน outage ("ห้องงดใช้: <เหตุผล>")
- `bookings/services.py::find_available_rooms` — เหตุผลไม่ว่างรวม blackout/outage (ผ่าน validate ข้างบนอยู่แล้ว — ยืนยันว่าไม่ต้องแก้เพิ่ม)
- `bookings/views.py::calendar_events` — เพิ่ม background events ของ blackout (ทุกคนเห็นชื่อ) และ outage (เมื่อกรองห้องนั้น)
- `notifications` — ไม่มีแก้โครงสร้าง ใช้ `notify` เดิม

### 2.4 URL / view
| URL | ทำอะไร |
|---|---|
| `/book/<code>/series/preview/` | POST จากฟอร์ม S4 (โหมดชุด) → S10 · เก็บพารามิเตอร์ในฟอร์ม hidden ไม่ใช้ session |
| `/book/<code>/series/create/` | POST ยืนยัน "จองเฉพาะครั้งที่ว่าง" → สร้าง → redirect S11 พร้อมสรุป (รวมครั้งที่เพิ่งชนตอนบันทึก) |
| `/series/<uuid:id>/` | S11 — สิทธิ์เห็นเต็มตาม `can_view_details` ของ occurrence แรก |
| `/series/<uuid:id>/cancel-remaining/` | POST + ยืนยัน |
| `/approvals/series/<uuid:id>/decide/` | POST (action, excluded[], reasons) → `decide_series` |
| `/resources/<code>/outage/` | S12 GET/POST · `/resources/outage/<id>/end/` POST สิ้นสุดก่อนกำหนด |
| Django Admin | ลงทะเบียน Blackout (filter_horizontal rooms, list วันเวลา+ขอบเขต), ResourceOutage (อ่านเขียน), BookingSeries + SeriesSkip (อ่านอย่างเดียว) |

### 2.5 template
- แก้ `bookings/book_form.html` (โหมดชุด — JS เล็กน้อยเปิด/ปิดฟิลด์ ไม่มีไลบรารีใหม่) · ใหม่: `bookings/series_preview.html`, `bookings/series_detail.html`, `resources/outage.html` · แก้ `approvals/queue.html` (การ์ดชุด), `bookings/my_bookings.html` (ยุบชุด), `booking_detail.html` (ลิงก์ชุด), ปฏิทิน background events
- วันที่ทุกจุดเป็น พ.ศ. ตาม filter เดิม · ไม่เพิ่มแพ็กเกจ/ไฟล์ vendor ใหม่

### 2.6 seed
- `seed_pilot` เพิ่ม Blackout ตัวอย่าง: "วันหยุดชดเชย" (scope=all, วันจันทร์หน้า) — เพื่อเห็นการข้ามใน preview ทันที

### 2.7 เทส (`bookings/tests_m4.py`, `approvals/tests_m4.py`, `resources/tests.py` — inject `now`/`today` ทุกข้อ)
1. `generate_occurrence_dates`: weekly จ+พ 4 สัปดาห์ = 8 ครั้ง · เกิน max → ValidationError · ห้องไม่อนุญาตชุด → ValidationError
2. `preview_series`: ครั้งชนติด conflict พร้อม label ตามสิทธิ์ · ครั้งติด blackout scope=building เฉพาะอาคารนั้น
3. `create_series` only_free: สร้างเฉพาะว่าง + SeriesSkip ครบ · จำลองชนตอนบันทึก (สร้าง booking แทรกก่อนเรียก) → กลายเป็น skip ไม่ error ทั้งชุด
4. ชุดห้องอัตโนมัติ → ทุกครั้ง APPROVED · ชุดห้องต้องอนุมัติ → ทุกครั้ง PENDING และคิว S7 เห็นเป็นการ์ดเดียว
5. `decide_series` approve + excluded 1 → ที่เหลืออนุมัติ ครั้งที่ตัด REJECTED พร้อมเหตุผล + hold ปลด · reject ทั้งชุด → ทุกครั้ง REJECTED · ตัดสินซ้ำ → ValueError
6. หมดอายุทั้งชุด: `run_scheduled_jobs` ที่ now = ครั้งแรก − 23 ชม. → ทุก PENDING ในชุด EXPIRED + ปลด hold + แจ้งใบเดียว · รันซ้ำไม่ซ้ำ
7. `cancel_booking` ครั้งเดียวในชุด → ครั้งอื่นไม่กระทบ · `cancel_remaining` ยกเลิกเฉพาะอนาคตและรายงานครั้งที่ติดเส้นตาย
8. blackout scope ทั้ง 4 แบบ บล็อกถูกขอบเขต (จองใหม่โดน validate + search แสดงเหตุผล)
9. `is_business_day` ข้าม blackout scope=all → `sla_deadline` เลื่อนถูกต้อง
10. outage: จองใหม่ทับช่วงถูกปฏิเสธ · booking เดิมถูกธง ROOM_UNAVAILABLE + ผู้จองได้รับแจ้ง (ไม่มีชื่อกิจกรรม) · hold ไม่ถูกปลด · `end_outage_early` คืนสถานะ
11. สิทธิ์หน้า outage: somchai (ไม่ใช่ custodian) → 403 · custodian ผ่าน
12. ปฏิทิน: blackout เป็น background event ทุกคนเห็นชื่อ · เทสเดิม 28 ข้อผ่านโดยไม่แก้ (ยกเว้นจำเป็นจริง → อธิบายใน notes)

### 2.8 นิยาม "เสร็จ"
- `uv run pytest` ผ่านทั้งหมด (28 + ~14 ใหม่) · `check` สะอาด · `makemigrations --check` ไม่ค้าง
- ห้ามแตะ: `BookingResource`+constraints, `compute_hold/place_holds/release_holds/approval_policy_for/submit_booking`, `approve_booking/reject_booking` (เพิ่มฟังก์ชันใหม่ได้), เทสเดิม
- ไม่เพิ่มแพ็กเกจ · ภาษาไทย · กฎใน services · อัปเดต `build-plan.md`, เขียน `docs/m4-notes.md` · **ยังไม่ commit** รอ Claude ตรวจ

## 3. ดูผลด้วยตา
1. seed ใหม่ → มี blackout "วันหยุดชดเชย" วันจันทร์หน้า
2. `somchai` จอง B1-201 แบบชุด จ+พ 09:00–11:00 6 สัปดาห์ → หน้า preview เห็น "ข้าม: วันหยุดชดเชย" 1 ครั้ง → จองเฉพาะครั้งที่ว่าง → S11 แสดงครบ
3. จองชุด MTG-1 (ต้องอนุมัติ) 4 ครั้ง → `wanida` เห็นการ์ดชุดในคิว → ตัด 1 ครั้งพร้อมเหตุผล → อนุมัติ → `somchai` ได้แจ้ง "อนุมัติ 3 ตัด 1"
4. `somchai` ยกเลิกครั้งเดียวจากชุด → ครั้งอื่นคงอยู่
5. `admin` เข้า LAB-COMM `/outage/` ตั้งงดใช้สัปดาห์หน้า → การจองที่ทับถูกธง "ห้องใช้งานไม่ได้" + ผู้จองได้กระดิ่ง · ค้นห้องช่วงนั้นไม่เจอ LAB-COMM พร้อมเหตุผล
6. ปฏิทินเห็นแถบพื้นหลังวันหยุดและช่วงงดใช้
