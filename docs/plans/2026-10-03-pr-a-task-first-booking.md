# PR-A: จองตามงาน (3D Gateway → จองทันที)

เขียน 3 ต.ค. 2569 · ผู้ทำ: Codex · ผู้ตรวจ: Claude
แผนนี้ผู้ใช้อนุมัติแล้ว (ห้องพักใช้แนวทาง A) ทำตามนี้ ถ้าเจอสิ่งที่ขัดกับแผน ให้หยุดแล้วเขียนไว้ในหัวข้อ "ข้อสงสัย" ของ PR ห้ามตัดสินใจเอง

## 0. อ่านก่อนเริ่ม
1. `CLAUDE.md` โดยเฉพาะกติกาข้อ 1–8
2. `docs/theme-a-ledger.md` สี ฟอนต์ และชุดสถานะที่อนุมัติแล้ว PR นี้ใช้ธีม A เดิม **ห้ามเพิ่มความสวยงามใหม่** (ธีม 90s อยู่ใน PR-B)
3. แผนนี้ทั้งไฟล์

## 1. เป้าหมาย
เปลี่ยนแกนของระบบจาก "ดูสถานะห้องก่อน" เป็น "บอกงานที่ต้องการแล้วจองได้เลย"

| บริการ | เส้นทางใหม่ | จำนวนหน้าจาก Gateway ถึงยืนยัน |
|---|---|---|
| ห้องสอนออนไลน์ | Gateway → `/online/` (เลือกเวลา, ระบบเสนอห้อง, ยืนยัน) | 2 |
| ห้องเรียน | Gateway → `/book/?category=classroom` → ฟอร์มจอง | 3 |
| ห้องประชุม | Gateway → `/book/?category=meeting` → ฟอร์มจอง | 3 |
| ห้องพักหลักสูตร | Gateway → รายชื่อรอบ (ถ้ามีหลายรอบ) → หน้าเลือกเตียงของรอบ | 2–3 |
| ห้องพักบุคคลทั่วไป | Gateway → `/lodging/request/` (เลือกวันก่อน, ระบบเลือกห้อง, ส่งคำขอ) | 2 |

หน้าสถานะห้อง (`/home/`) ยังอยู่ แต่เป็นเมนูรองเท่านั้น

## 2. ขอบเขต
**ทำ**
- A1 ทางเข้า: `/` และ splash ของ Firebase พาไปหน้า Gateway
- A2 การ์ดบริการบน Gateway ลิงก์ไปหน้าจองโดยตรง
- A3 หลัง login พาไปหน้าตามบทบาท + ตัวสลับบริการ
- A4 ห้องสอนออนไลน์: เลือกเวลาก่อน แล้วระบบเสนอห้อง
- A5 ห้องพัก: หน้าเลือกกลุ่ม, รอบเดียวข้ามหน้ารายชื่อ, คำขอบุคคลทั่วไปแบบเลือกวันก่อน

**ไม่ทำ (ห้ามแตะ)**
- ธีม 90s และบัตรตลับเทป (อยู่ใน PR-B)
- จุดกดบนภาพ 3D ของอาคาร (`static/js/lodging_about_explorer.js`) ให้คงเดิม
- PR #82: **ห้าม merge และห้ามนำโค้ดมาใช้ใน PR นี้** ส่วนล็อกหมวดฝั่ง server จะแยกเป็น PR ภายหลัง
- schema / migration: PR นี้ **ต้องไม่มี migration** (`makemigrations --check` ต้องผ่าน)
- กฎธุรกิจเดิม: การกันจองซ้อน, การอนุมัติอัตโนมัติของห้องออนไลน์, กันส่งถี่, สิทธิ์ ต้องไม่เปลี่ยน

## 3. Branch
- base: `feat/lodging-v5-2` (commit `74933b1` หรือใหม่กว่า)
- branch: `feat/task-first-booking`
- แบ่ง commit ตามหัวข้อ A1–A5 ให้ตรวจทีละเรื่องได้

---

## A1. ทางเข้า Gateway

**ข้อเท็จจริงที่ต้องรู้:** Firebase Hosting เสิร์ฟ `public/index.html` (splash) ที่ `/` ก่อนส่งต่อไป Cloud Run และ splash นี้สั่ง `location.replace('/home/'...)` คนที่เข้าเว็บจึงตกไปหน้าสถานะห้องตลอด

แก้:
1. `public/index.html`
   - เปลี่ยนปลายทางจาก `/home/` เป็น `/lodging/about/` ทั้งใน script (`location.replace`) และใน `<noscript>`
   - ส่ง `location.search` และ `location.hash` ต่อเหมือนเดิม
   - ข้อความ noscript: "เข้าสู่ SIGROOM"
2. `bookings/urls.py`: path `""` (name `calendar_root`) เปลี่ยนเป็น redirect ไป `bookings:lodging_about`
   - ใช้ `RedirectView.as_view(pattern_name="bookings:lodging_about", query_string=True, permanent=False)`
   - คงชื่อ `calendar_root` ไว้ เพราะ `templates/base.html` ใช้ชื่อนี้อยู่ 4 จุด
3. `templates/base.html`: ปุ่ม "หน้าแรก" และโลโก้ชี้ `lodging_about` อยู่แล้ว (จาก PR #81) ไม่ต้องแก้ ส่วน "สถานะห้อง" ให้คงเป็นเมนูรองตามเดิม

**Test** (ไฟล์ใหม่ `bookings/tests_task_first_a1_entry.py`)
- `public/index.html` มี `/lodging/about/` และไม่มี `'/home/'` ใน `location.replace`
- `GET /` ได้ 302 ไป `/lodging/about/` และส่ง query string ต่อ
- `GET /home/` ยังได้ 200 (หน้าสถานะห้องยังอยู่)

---

## A2. การ์ดบริการบน Gateway (`templates/lodging/lodging_about.html`)

**ตอนนี้** (บรรทัดประมาณ 55–85) มีการ์ด 4 ใบ: ห้องพักหลักสูตร, ห้องพักบุคคลทั่วไป, ห้องสอนออนไลน์ และ "ห้องเรียน / ห้องประชุม" ที่**ไม่มีลิงก์**

**เปลี่ยนเป็น** หัวข้อ "วันนี้ต้องการทำอะไร" ตามด้วยการ์ด 4 ใบ ใช้ markup และ CSS class เดิม (`lka-r3g-service`):

| การ์ด | ข้อความ | ลิงก์ |
|---|---|---|
| ห้องพัก | **จองห้องพัก** + ปุ่มย่อย 2 ปุ่มในการ์ด: "นักเรียนหลักสูตร" / "บุคคลทั่วไป" | ปุ่มย่อยชี้ `bookings:lodging_index` และ `bookings:lodging_general_request` ส่วนตัวการ์ดชี้ `bookings:lodging_start` (A5) |
| ออนไลน์ | **จองห้องสอนออนไลน์** · "เลือกเวลา ระบบหาห้องว่างให้" | `bookings:online_teaching_home` |
| ห้องเรียน | **จองห้องเรียน** · "บอกวัน เวลา จำนวนคน" | `{% url 'bookings:book_search' %}?category=classroom` |
| ห้องประชุม | **จองห้องประชุม** · "บอกวัน เวลา จำนวนคน" | `{% url 'bookings:book_search' %}?category=meeting` |

- การ์ดห้องพักห้ามซ้อน `<a>` ใน `<a>` ให้ทำการ์ดเป็น `<div>` ที่มีลิงก์หัวการ์ดและลิงก์ปุ่มย่อยแยกกัน
- ใต้การ์ดมีลิงก์รอง "ดูสถานะห้องทั้งหมด" ไป `bookings:calendar` เป็นตัวหนังสือธรรมดา ไม่ทำเป็นการ์ด
- ถ้าผู้ใช้ login อยู่และมีการจองที่ยังไม่จบ: แสดงแถว "การจองของฉัน (N)" ลิงก์ไป `bookings:my_bookings`
  - นับจำนวนใน view `lodging_about` ด้วย query แบบเดียวกับ `my_pending_count` ใน `calendar_view` (การจองที่ requester เป็นผู้ใช้, สถานะอยู่ใน `HOLDING_STATUSES`, `end_at > now`)
- ป้าย "กำลังพัฒนา" ของห้องเรียน/ประชุมในคำอธิบายผัง (ประมาณบรรทัด 203) ให้ลบออก
- ลิงก์ "จัดการ…" ของเจ้าหน้าที่ (ประมาณบรรทัด 520–522) คงไว้

**Test** (`bookings/tests_task_first_a2_gateway.py`)
- หน้า gateway มีลิงก์ครบทั้ง 5 ปลายทางในตาราง
- `/book/?category=classroom` และ `?category=meeting` ได้ 200 เมื่อ login
- ไม่มีการ์ดบริการที่ลิงก์ไป `bookings:calendar` (ลิงก์ "ดูสถานะห้องทั้งหมด" เป็นตัวหนังสือได้)
- ผู้ใช้ login ที่มีการจองค้าง 2 รายการเห็น "การจองของฉัน (2)" ส่วนผู้ไม่ login ไม่เห็นแถวนี้
- **ห้ามมีการ์ดที่ไม่มีลิงก์:** ทุก `.lka-r3g-service` มี `href` หรือมีลิงก์อยู่ข้างใน

ตรวจ test เดิมที่อาจพัง: `tests_lodging_about_r3g2.py`, `tests_ux17_showcase.py`, `tests_ux20_lodging_about.py`, `tests_ux21a_lodging_about.py`, `tests_gateway_navigation.py`, `tests_lodging_service_gateway.py`
ถ้าพังเพราะ IA เปลี่ยนจริง ให้แก้ assertion ให้ตรง IA ใหม่ และอธิบายใน PR ทีละไฟล์ **ห้ามลบ test ทิ้ง**

---

## A3. หลัง login พาไปหน้าตามบทบาท

**ไฟล์ใหม่ `bookings/role_home.py`** (กฎสิทธิ์อยู่ในฟังก์ชัน ไม่อยู่ใน view)

```python
SERVICE_LODGING, SERVICE_ONLINE, SERVICE_LEARNING = "lodging", "online", "learning"

def managed_services(user) -> list[str]:
    """บริการที่ผู้ใช้ดูแล เรียงลำดับคงที่: ห้องพัก → ออนไลน์ → ห้องเรียน/ประชุม"""
```
- ห้องพัก: `can_access_lodging_management(user)`
- ออนไลน์: เป็น custodian ของห้อง `room_category=ONLINE` อย่างน้อย 1 ห้อง
- ห้องเรียน/ประชุม: เป็น custodian ของห้อง `CLASSROOM`, `LAB`, `MEETING` หรือ `SPECIAL` อย่างน้อย 1 ห้อง
- **superuser คืน `[]`** ให้ไปหน้า Gateway เพราะ superuser ผ่านทุกเงื่อนไข ถ้าไม่ตัดออกจะถูกพาไปหน้าห้องพักทุกครั้ง
- ห้ามคัดลอกตรรกะจาก `service_staff_entry` ให้ refactor `service_staff_entry` มาเรียกฟังก์ชันเดียวกัน (ตรวจหมวดของ learning ให้ตรงกัน: ตอนนี้ `service_staff_entry` ไม่รวม `SPECIAL` ให้เพิ่มทั้งสองที่ และเขียนไว้ใน PR)

**View `role_home`** ที่ path `start/` (name `bookings:role_home`)
- `@login_required`
- ถ้าผู้ใช้ต้องเปลี่ยนรหัสผ่านครั้งแรก ระบบเดิมจัดการให้แล้ว ไม่ต้องทำอะไรเพิ่ม
- `managed_services` ว่าง → redirect `bookings:lodging_about`
- ไม่ว่าง → redirect `bookings:service_staff_entry` ด้วยบริการแรกในลำดับ

**Settings:** `LOGIN_REDIRECT_URL = "/start/"`
- `LoginView` ใช้ `?next=` ก่อนค่านี้อยู่แล้ว ต้องมี test ยืนยัน
- `accounts/views.py: first_password_change` ตอนนี้ redirect ไป `bookings:calendar` 2 จุด ให้เปลี่ยนเป็น `bookings:role_home`

**ตัวสลับบริการ** (เฉพาะผู้ดูแลมากกว่า 1 บริการ)
- เพิ่ม key `nav_managed_services` ใน `notifications/context_processors.navigation_counts` เป็น list ของ `(slug, ป้ายไทย, url)`
- `templates/base.html`: ถ้า list ยาวมากกว่า 1 แสดงแถบเล็กใต้หัวเว็บ "งานของฉัน:" ตามด้วยลิงก์แต่ละบริการ ใช้ `aria-current` กับหน้าปัจจุบัน
- ผู้ดูแลทุกคน (list ไม่ว่าง) มีลิงก์ "จองห้องให้ตัวเอง" ไป `bookings:lodging_about` ในแถบเดียวกัน

**Test** (`bookings/tests_task_first_a3_role_home.py`) ทำเป็นตารางพาราเมตริก:

| ผู้ใช้ | ปลายทางหลัง login |
|---|---|
| ผู้ใช้ทั่วไป | `/lodging/about/` |
| มีสิทธิ์จัดการห้องพัก | `/lodging/staff/lodging/` แล้ว `/lodging/workspace/` |
| custodian ห้องออนไลน์ | `/lodging/staff/online/` |
| custodian ห้องประชุม | `/lodging/staff/learning/` |
| ดูแลห้องพักและออนไลน์ | ไปห้องพัก และเห็นตัวสลับ 2 ลิงก์ |
| superuser | `/lodging/about/` |
| login พร้อม `?next=/bookings/mine/` | `/bookings/mine/` |

และ: ผู้ดูแลบริการเดียวไม่เห็นตัวสลับ, `GET /start/` ตอนไม่ login ถูกพาไปหน้า login

---

## A4. ห้องสอนออนไลน์: เลือกเวลาก่อน

### A4.1 ย้ายกฎการจองไปไว้ใน service (กติกาข้อ 3)
**ไฟล์ใหม่ `bookings/online_teaching_services.py`** ตามแบบ `lodging_services.py` / `series_services.py`

```python
def create_online_teaching_booking(*, user, room, start_at, end_at, course_run, purpose) -> Booking:
```
- ย้ายตรรกะจาก `online_teaching_book` (POST action=book) มาทั้งก้อน:
  - ตรวจ policy AUTO, ตรวจ unit/phone
  - `full_clean`, `save`, `submit_booking`
  - ถ้าสถานะไม่ใช่ APPROVED ให้ลบการจองแล้ว error
  - `audit` และ `notify_submitted`
- ยก `BookingConflict` / `ValidationError` ออกไปให้ view จัดการ
- `online_teaching_book` (หน้าเดิมแบบเลือกห้องก่อน) ต้องเรียกฟังก์ชันนี้ และพฤติกรรมต้องเหมือนเดิมทุกอย่าง

```python
def suggest_online_rooms(*, user, start_at, end_at) -> tuple[list, list]:
    """(ห้องว่างเรียงตามรหัส, ช่วงเวลาใกล้เคียงที่ว่างอย่างน้อย 1 ห้อง สูงสุด 3 ช่วง)"""
```
- ห้องว่างใช้ `find_available_rooms(..., room_categories=(Resource.Category.ONLINE,))` และกรองเฉพาะห้องที่มี rule AUTO
- ช่วงใกล้เคียง: เลื่อนทีละ 30 นาที ทั้งก่อนและหลัง ไม่เกิน ±3 ชม. อยู่ในวันเดียวกัน และไม่ย้อนอดีต

### A4.2 หน้า `/online/` ใหม่ (แทนรายการห้องเดิมใน `online_teaching_home`)

```
จองห้องสอนออนไลน์                สอนในนาม: <ยศ ชื่อ> · <สังกัด> · <เบอร์>   [แก้ข้อมูล]
① วันไหน     [วันนี้] [พรุ่งนี้] [<วันถัดไป>] [เลือกวัน…]
② เริ่มกี่โมง  [08.00][09.00][10.00][11.00][13.00][14.00][15.00] [เวลาอื่น ▾]
③ นานเท่าไร   [30 นาที] [1 ชม.] [2 ชม.] [ครึ่งวันเช้า] [ครึ่งวันบ่าย]
④ หลักสูตร/รุ่น [select]   (เลือกรุ่นที่ผู้ใช้จองครั้งล่าสุดไว้ให้ ถ้าไม่มีใช้ตัวแรก)
── ผลลัพธ์ (โหลดใหม่ทันทีเมื่อเปลี่ยนตัวเลือก) ──
✅ STU-ONLINE-2 ว่าง 10.00–11.00 น.                [ยืนยันจอง]
   ห้องอื่นที่ว่าง: [STU-ONLINE-1] [STU-ONLINE-3]     (กดแล้วเปลี่ยนห้องที่เสนอ)
▸ ตัวเลือกเพิ่มเติม: วัตถุประสงค์ (ค่าเริ่มต้น "สอน")
```

- ชิปวัน: ใช้ `search_date_choices` และพารามิเตอร์ `day`/`date` แบบเดียวกับ `/book/` (ฟังก์ชันเดิมใน `bookings/services.py`)
- ชิปเวลาเริ่ม: พารามิเตอร์ `start=HH:MM` ส่วน "เวลาอื่น" เป็น `<select>` จาก `time_choices()`
- ชิประยะเวลา: พารามิเตอร์ `dur` = `30` / `60` / `120` / `am` / `pm`
  - `am` และ `pm` ใช้ช่วงเช้า/บ่ายจาก `search_period_choices()` ตัวแรกและตัวที่สองตามที่ผู้ดูแลตั้ง และ**ไม่สนใจ start**
  - ถ้าผู้ดูแลตั้งช่วงไว้ไม่ถึง 2 ช่วง ให้ซ่อนชิปที่ไม่มี
- ชิปทั้งหมดเป็น `<a>` หรือ radio ใน `<form method="get">` ที่ใช้ได้แม้ไม่มี JS และ HTMX แค่โหลดผลลัพธ์บางส่วน (`hx-get` + `hx-target="#online-results"` + `hx-push-url="true"`) แบบเดียวกับ `book_search`
- **partial ผลลัพธ์:** `templates/bookings/partials/online_results.html`
- **ปุ่มยืนยันจอง:** POST ไป path ใหม่ `online/book/` (name `online_teaching_quick_book`) ส่ง `room`, `start_at`, `end_at` (ISO), `course_run`, `purpose`
  - view ต้อง**คำนวณและตรวจทุกค่าใหม่ทั้งหมด** ห้ามเชื่อค่าจาก form ว่าห้องว่าง
  - เรียก `create_online_teaching_booking`
  - สำเร็จ → `messages.success` แล้ว redirect `bookings:my_bookings` (เหมือนเดิม)
  - ชน → แสดงหน้า `/online/` เดิมพร้อมตัวเลือกเดิมและข้อความ "ห้องนี้เพิ่งถูกจอง กรุณาเลือกห้องอื่น"
- ไม่มีห้องว่าง: แสดง "ไม่มีห้องว่างช่วงนี้" พร้อมปุ่มช่วงใกล้เคียงสูงสุด 3 ปุ่ม กดแล้วเลือกช่วงนั้นให้
- หน้าเดิม `online/<code>/` ยังใช้ได้ (คนที่บันทึกลิงก์ไว้) แต่ไม่มีลิงก์จากหน้าใหม่ไปที่นั่น ยกเว้นลิงก์รอง "เลือกห้องเอง" ท้ายผลลัพธ์

### A4.3 ข้อมูลบัญชีไม่ครบ
**ตอนนี้** ถ้าไม่มีสังกัดหรือเบอร์ จะได้ 403 ทันที

**เปลี่ยนเป็น** ในหน้า `/online/` ถ้า `user.unit_id` หรือ `user.phone` ว่าง ให้แสดงกล่อง "กรอกข้อมูลครั้งเดียว" แทนปุ่มยืนยันจอง:
- สังกัด: `<select>` จาก `Unit` ที่ active (ฟิลด์อ้างอิง ต้องเลือกอย่างเดียว ตามกติกาข้อ 7)
- เบอร์: ตรวจด้วย `normalize_phone`
- POST ไป path ใหม่ `online/profile/` บันทึกลง user แล้ว redirect กลับ `/online/` พร้อม query เดิม
- ตรรกะบันทึกอยู่ใน `accounts/services.py` (ฟังก์ชันใหม่ `complete_contact_profile(user, unit, phone)`) และมี audit
- ห้ามให้ผู้ใช้เปลี่ยนสังกัดที่มีอยู่แล้วผ่านช่องทางนี้: ฟังก์ชันตั้งได้เฉพาะช่องที่ว่าง

### A4.4 ผู้ที่ไม่มีสิทธิ์
- ไม่ login: ใช้ `login_required` ซึ่งพาไป login แล้วกลับมา `/online/`
- login แต่ไม่อยู่กลุ่มครู (`can_book_online_teaching` เป็น False):
  - `GET /online/` → 200 หน้าอธิบาย "บัญชีนี้ยังไม่มีสิทธิ์จองห้องสอนออนไลน์ ติดต่อ บก.กศ.รร.ส.สส."
  - POST ทุกตัวยังเป็น 403 เหมือนเดิม
  - **ตรวจ `tests_phase_e_online_teaching.py`** ถ้ามี test คาดว่า GET จะได้ 403 ให้แก้ตาม IA ใหม่และอธิบายใน PR

**Test** (`bookings/tests_task_first_a4_online.py`)
- เลือกเวลาที่ห้อง 2 ว่างแต่ห้อง 1 ไม่ว่าง → ผลลัพธ์เสนอห้อง 2 และไม่มีห้อง 1
- กดยืนยัน → ได้การจอง APPROVED หนึ่งรายการ, redirect ไป my_bookings, มี audit
- POST ซ้ำช่วงเดียวกันห้องเดียวกัน → ไม่เกิดการจองที่สอง, แสดงข้อความชน
- POST ที่แก้ `room` เป็นห้องที่ไม่ใช่ออนไลน์ → ถูกปฏิเสธ
- `dur=am` ใช้ช่วงเช้าจาก preset ไม่ใช่ start
- ไม่มีห้องว่าง → มีช่วงใกล้เคียง ≤ 3 และไม่ย้อนอดีต
- ผู้ใช้ไม่มีเบอร์ → เห็นกล่องกรอกข้อมูล ไม่เห็นปุ่มยืนยัน → POST profile → เบอร์ถูกบันทึก → เห็นปุ่มยืนยัน
- profile POST ไม่เปลี่ยนสังกัดที่มีอยู่แล้ว
- ไม่ใช่ครู → GET 200 หน้าอธิบาย, POST 403
- หน้าเดิม `online/<code>/` ยังจองได้เหมือนเดิม (test เดิมผ่าน)
- **journey:** login ครู → GET gateway → GET `/online/?day=…&start=10:00&dur=60` → POST `online/book/` → จองสำเร็จ (นับได้ 2 หน้าก่อนยืนยัน)

---

## A5. ห้องพัก (แนวทาง A)

### A5.1 หน้าเลือกกลุ่ม `lodging/start/` (name `bookings:lodging_start`)
```
จองห้องพัก — คุณคือ
[นักเรียนหลักสูตร]  รอบหลักสูตรกำหนดวันพักไว้แล้ว เลือกเตียงได้เลย   → lodging_index
[บุคคลทั่วไป]       เลือกวันเข้า–ออก แล้วส่งคำขอ                  → lodging_general_request
```
- เปิดได้โดยไม่ต้อง login
- เมนู "จองห้องพัก" ใน `base.html` (ตอนนี้ชี้ `lodging_index`) เปลี่ยนให้ชี้หน้านี้

### A5.2 นักเรียนหลักสูตร (`lodging_index`)
- มีรอบเปิดรอบเดียว → redirect 302 ไป `lodging_portal` ของรอบนั้นทันที
- เปิดหลายรอบ → แสดงรายการเหมือนเดิม
- ไม่มีรอบเปิด → "ยังไม่มีรอบที่เปิดจอง ขอลิงก์หรือ QR จากผู้กำกับหลักสูตร" และลิงก์กลับ `lodging_start`
- **ไม่แตะ** `lodging_portal`, `lodging_book_bed` และกฎของรอบหลักสูตร
- ผู้จัดการห้องพักต้องเห็นรายการเสมอแม้มีรอบเดียว: ถ้า `nav_can_manage_lodging` ไม่ redirect เพราะต้องใช้ลิงก์ "จัดการที่พัก"

### A5.3 บุคคลทั่วไป: เลือกวันก่อน (`general_request`)

**ข้อเท็จจริง:** `request_general_lodging` ต้องรับ `room` เพราะ `Booking.room` ห้ามว่าง และคำขอที่รออนุมัติจะกันห้องนั้นไว้แล้ว **ห้ามแก้ส่วนนี้** แนวทางคือให้ระบบเลือกห้องให้ แต่ผู้ใช้เปลี่ยนเองได้

```
ขอใช้ห้องพัก
① เข้าพัก [date] (14.00 น.)   ออก [date] (12.00 น.)   · N คืน
② จำนวนผู้พัก  [–] 1 [+]          (input type=number min=1 max=20 พร้อมปุ่ม –/+ ใช้ได้แม้ไม่มี JS)
③ ผู้ติดต่อ    ดึงชื่อและเบอร์จากบัญชีถ้า login อยู่ ถ้าไม่ login ให้กรอก 2 ช่อง
── ระบบเลือกห้องให้ (โหลดใหม่เมื่อเปลี่ยนวันหรือจำนวนคน) ──
ห้อง 412 ว่างตลอดช่วงนี้ (รองรับ 2 คน)   [เปลี่ยนห้อง ▾ select เฉพาะห้องที่ว่าง]
หมายเหตุ (ไม่บังคับ)
[ส่งคำขอ]
```

**Service ใหม่ใน `bookings/lodging_services.py`**
```python
def available_public_lodging_rooms(*, check_in, check_out, attendees) -> list[Resource]:
    """ห้องพักสาธารณะที่ว่างตลอดช่วง เรียง: ห้องที่ capacity พอดีที่สุดก่อน แล้วตามรหัส"""
```
- ตั้งต้นจาก `public_lodging_rooms()` แล้วตัดห้องที่มีการจองใน `HOLDING_STATUSES` ทับช่วง (14:00 วันเข้า ถึง 12:00 วันออก)
- **ตรวจก่อนว่า `find_available_rooms` ใช้กับผู้ไม่ login ได้ไหม** ถ้าต้องมี user ให้ใช้ `_public_lodging_principal()` แบบเดียวกับ `request_general_lodging` หรือเขียน query ตรงจาก `BookingResource` ที่ใช้ช่วงเวลาเดียวกับ constraint และอธิบายใน PR ว่าเลือกทางไหน
- capacity 0 = ไม่กำหนด ให้นับว่ารองรับได้ แต่เรียงไว้หลังห้องที่ capacity พอดี
- ห้องที่ capacity < จำนวนคน **ไม่ต้องตัดทิ้ง** (model บอกให้เตือน ไม่บล็อก) แต่เรียงไว้ท้ายและแสดง "เกินความจุ" ใน select

แก้ `request_general_lodging`
- เพิ่ม kwarg `attendees=1` เก็บลง `Booking.attendees` (ฟิลด์มีอยู่แล้ว ไม่ต้อง migration)
- ตรวจว่า `attendees >= 1`

แก้ `GeneralRequestForm`
- เรียงฟิลด์ใหม่: `check_in`, `check_out`, `attendees`, `guest_name`, `phone`, `room`, `note`
- `room` ยังจำเป็น แต่ queryset = `available_public_lodging_rooms(...)` เมื่อวันถูกต้อง และค่าเริ่มต้น = ห้องแรก
- `room` เป็นฟิลด์อ้างอิง ต้องเลือกอย่างเดียว (กติกาข้อ 7)

HTMX
- เปลี่ยนวันหรือจำนวนคน → `hx-get` ไป path ใหม่ `lodging/request/rooms/` (name `lodging_general_request_rooms`) คืนเฉพาะ partial ห้องที่เสนอ
- partial **ต้องไม่แสดงข้อมูลผู้พักคนอื่น** แสดงแค่รหัสห้อง ความจุ และ "ว่าง"
- view ของ partial ต้องจำกัดช่วงวัน: ไม่ย้อนอดีต และไม่เกิน 60 วันข้างหน้า กันการสแกนข้อมูล
- ไม่มี JS ก็ยังใช้ได้: กดปุ่ม "ค้นหาห้อง" (GET) แล้วหน้าโหลดใหม่พร้อมห้องที่เสนอ

`?room_id=` เดิม (ลิงก์จากผัง 3D) ยังใช้ได้: ถ้าห้องนั้นว่างในวันที่เลือก ให้เลือกห้องนั้นเป็นค่าเริ่มต้น

ถ้าไม่มีห้องว่าง: "ช่วงนี้ห้องเต็ม" พร้อมวันเข้าใกล้เคียงที่ว่าง (ไม่เกิน ±7 วัน สูงสุด 3 ตัวเลือก)

**Test** (`bookings/tests_task_first_a5_lodging.py`)
- `lodging/start/` มีลิงก์ 2 กลุ่ม และเปิดได้โดยไม่ login
- `lodging_index` รอบเปิด 1 รอบ → 302 ไป portal / 2 รอบ → 200 รายการ / 0 รอบ → ข้อความและลิงก์กลับ
- ผู้จัดการห้องพักกับรอบเดียว → ไม่ redirect
- `available_public_lodging_rooms`
  - ตัดห้องที่มีคำขอ PENDING ทับช่วง
  - ไม่ตัดห้องที่การจองจบ 12:00 วันที่เราเข้า 14:00
  - เรียงตาม capacity พอดี
- POST คำขอพร้อม `attendees=2` → `Booking.attendees == 2`
- POST ห้องที่เพิ่งถูกจองทับ → error ไม่เกิดการจองซ้อน (constraint เดิมทำงาน)
- partial rooms: วันย้อนอดีต / เกิน 60 วัน → 400 หรือข้อความ error, และไม่มีชื่อผู้พักอื่นใน HTML
- ไม่ login ส่งคำขอได้เหมือนเดิม (กันส่งถี่เดิมยังทำงาน: test เดิมผ่าน)
- `?room_id=` ของห้องที่ว่าง → ถูกเลือกเป็นค่าเริ่มต้น

---

## 4. เกณฑ์ผ่าน (ต้องครบทุกข้อก่อนเปิด PR)
- [ ] `uv run pytest` ผ่านทั้งหมด (ฐานตอนนี้ประมาณ 750+ ข้อ) ใส่ตัวเลขจริงใน PR
- [ ] `uv run manage.py check` ผ่าน
- [ ] `uv run manage.py makemigrations --check --dry-run` ได้ "No changes detected"
- [ ] `git diff --check` สะอาด
- [ ] ไม่มีข้อความภาษาอังกฤษในหน้าผู้ใช้ที่เพิ่มใหม่ (ยกเว้น SIGROOM, QR, LINE)
- [ ] ทุกหน้าใหม่ใช้ได้บนจอกว้าง 360px โดยไม่เลื่อนแนวนอน
- [ ] ทุกฟอร์มใหม่ใช้ได้เมื่อปิด JavaScript
- [ ] แนบภาพหน้าจอมือถือ: gateway, `/online/` (มีห้องว่าง / ไม่มีห้องว่าง / ข้อมูลไม่ครบ), `lodging/start/`, คำขอบุคคลทั่วไป
- [ ] ไม่มีการแก้ `lodging_about_explorer.js`, migration หรือไฟล์จาก PR #82

## 5. รูปแบบ PR
- ชื่อ: `feat(ux): task-first booking — gateway → book directly`
- base: `feat/lodging-v5-2`
- เนื้อหา PR (ภาษาไทย)
  - สรุปตาม A1–A5
  - ตาราง test เดิมที่แก้ assertion พร้อมเหตุผลทีละไฟล์
  - หัวข้อ "ข้อสงสัย"
  - ผลรัน test และ check ทั้งหมด
  - วิธีดูผลด้วยตาตัวเอง (URL ที่ต้องเปิดทีละหน้า)
- ระบุใน PR ว่า "PR #82 ยังไม่ merge และไม่ได้ใช้โค้ดจาก PR นั้น"

## 6. จุดที่ Claude จะตรวจเป็นพิเศษ
1. view ไหนเชื่อค่าจาก form/hidden field ว่าห้องว่าง (ต้องไม่มี)
2. ตรรกะสิทธิ์และกฎธุรกิจหลุดไปอยู่ใน view หรือ template
3. superuser ถูกพาไปหน้าห้องพัก
4. partial ห้องพักเปิดเผยข้อมูลผู้พักคนอื่น หรือสแกนช่วงวันได้ไม่จำกัด
5. test เดิมถูกลบหรือถูกทำให้หลวมโดยไม่อธิบาย
6. การจองออนไลน์ผ่านหน้าใหม่กับหน้าเดิมให้ผลต่างกัน (ต้องเรียก service เดียวกัน)
