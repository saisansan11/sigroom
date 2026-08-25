# แผนงาน Trial Feedback Round 1 — สั่งงานผู้ช่วยเขียนโค้ด (Codex/ChatGPT ทำ, Claude ตรวจรับ)

เอกสารนี้สมบูรณ์ในตัวเอง ผู้รับงานต้องอ่าน `CLAUDE.md` ที่รากโปรเจกต์ก่อนเริ่ม และห้ามละเมิดกติกาในนั้น
ที่มา: ผู้ใช้จริงทดลองระบบบนมือถือผ่าน LAN แล้วให้ feedback 4 ข้อ (24–25 ส.ค. 2569)

## บริบทที่ต้องรู้

- Django 5.2 + PostgreSQL 16 + Django templates + HTMX (ไม่มี React/SPA) · ฟอร์มตามกติกาข้อ 7 ของ CLAUDE.md (datalist พิมพ์เองได้ ยกเว้นฟิลด์อ้างอิงระบบ)
- UI เป็นธีม Tactical HUD อยู่ใน `static/css/app.css` — ห้ามเขียน CSS inline ในเทมเพลต ให้เพิ่ม class ในไฟล์นี้
- กฎธุรกิจทั้งหมดอยู่ใน `services.py` ของแต่ละแอป — **งานรอบนี้ห้ามแก้กฎธุรกิจใด ๆ** เป็นงาน UI/ฟอร์ม/ข้อมูลตั้งต้นล้วน
- ทุก schema change ผ่าน `makemigrations` แบบ expand/contract เท่านั้น
- เทสต้องผ่านครบ: `uv run pytest` (ปัจจุบัน 82 ตัว) และเพิ่มเทสของสิ่งที่ทำใหม่
- ข้อความผู้ใช้เห็นเป็นภาษาไทยทั้งหมด วันที่ พ.ศ.

## งานที่ 1 — กดปุ่มแล้วพาผู้ใช้ไปที่ผลลัพธ์เสมอ (mobile-first)

**ปัญหา:** หน้า "ค้นหาห้องว่าง" (`templates/bookings/book_search.html`) ใช้ HTMX โหลดผลเข้า `#room-results` ซึ่งอยู่ใต้ฟอร์ม — บนมือถือผลอยู่นอกจอ ผู้ใช้คิดว่ากดแล้วไม่เกิดอะไร

**ให้ทำ:**
1. เพิ่ม script กลางใน `templates/base.html` (ท้าย body): ฟัง event `htmx:afterSwap` — ถ้า target มี attribute `data-scroll-on-swap` ให้ `scrollIntoView({behavior:'smooth', block:'start'})` และย้าย focus ไปที่ heading แรกใน target (`tabindex="-1"` ชั่วคราว) เพื่อ screen reader
2. ใส่ `data-scroll-on-swap` ให้ `#room-results` ใน `book_search.html`
3. หัวผลลัพธ์ใน `templates/bookings/partials/room_list.html` ต้องขึ้นจำนวนชัดเจน เช่น `<h2>พบ 5 ห้องว่าง</h2>` / "ไม่พบห้องว่างในช่วงที่เลือก" (ถ้ามีอยู่แล้วให้คงไว้และให้เป็น element ที่รับ focus)
4. เพิ่ม CSS `scroll-margin-top` (~4.5rem) ให้ element ที่เป็นเป้าเลื่อน กัน sticky header บัง
5. ไล่จุดอื่นที่ผลอยู่นอกจอบนมือถือ ให้พฤติกรรมเดียวกัน:
   - ฟอร์มจอง (`book_form.html`) validate ไม่ผ่าน → หลังโหลดหน้า ให้เลื่อน/โฟกัสไปช่องแรกที่มี error (script เล็กใน base: ถ้ามี `.field-error` ตัวแรก ให้เลื่อนไป field ของมัน)
   - หน้า preview ชุดการจอง และผล HTMX อื่นถ้ามี target ลักษณะเดียวกัน → ใส่ `data-scroll-on-swap`
   - ข้อความ success/error หลัง redirect (`.notice` ใน base) ต้องมองเห็น: ถ้าอยู่นอกจอให้เลื่อนไปหา (notice อยู่บนสุดของ main อยู่แล้ว โดยปกติเห็น — ตรวจบนมือถือยืนยัน)
6. เคารพ `prefers-reduced-motion` (ใช้ `behavior:'auto'` เมื่อผู้ใช้ตั้งลดการเคลื่อนไหว)

**เทส:** เพิ่มเทสว่า room_list partial มีจำนวนห้องในหัวข้อ (เทส template context ก็พอ ไม่ต้องเทส JS)

## งานที่ 2 — รายการชื่อวิชาตั้งต้นสำหรับช่อง "ชื่อกิจกรรม/วิชา"

**ปัญหา:** datalist ของ `title` มาจาก `bookings.services.frequent_values()` ซึ่งดึงจากประวัติการจองของหน่วยเท่านั้น (`bookings/services.py` บรรทัด ~288) — ระบบใหม่จึงว่างเปล่า ผู้ใช้ต้องพิมพ์เองหมด

**ให้ทำ:**
1. Model ใหม่ `ReferenceValue` ในแอป `bookings` (หรือ `resources` ถ้าเห็นว่าเหมาะกว่า ให้เลือกแล้วบันทึกเหตุผลใน docstring):
   - ฟิลด์: `field` (CharField choices จาก `FREQUENT_FIELDS` เดิม เช่น `title`), `value` (CharField 200), `order` (PositiveInteger default 0), `is_active` (Bool default True)
   - `unique_together (field, value)` · migration ใหม่ 1 ไฟล์
   - ลงทะเบียนใน Django Admin (list แก้ `order`/`is_active` ได้, กรองตาม `field`)
2. แก้ `frequent_values(unit, field)`: คืนค่า **ReferenceValue ที่ active (เรียงตาม order, value) + ประวัติหน่วย 10 ค่าล่าสุด** โดยไม่ซ้ำ — reference มาก่อน ประวัติต่อท้าย จำกัดรวมไม่เกิน 40 ค่า (datalist ยาวได้ พิมพ์กรองเองได้)
3. Management command `import_reference`:
   ```
   uv run manage.py import_reference title รายชื่อวิชา.txt
   ```
   - อาร์กิวเมนต์: ชื่อ field + ไฟล์ข้อความ (หนึ่งค่า/บรรทัด, UTF-8, ข้ามบรรทัดว่าง, ตัดช่องว่างหัวท้าย)
   - idempotent: ค่าที่มีแล้วไม่สร้างซ้ำ ไม่รีเซ็ต order/is_active ของเดิม · สรุปผลท้ายรัน (สร้างกี่รายการ ข้ามกี่รายการ)
4. ไฟล์ข้อมูลจริงอยู่ที่ `E:\งาน กศ\รายชื่อวิชา-ชั้นนายร้อย70.txt` (57 บรรทัด) — **ไม่ต้อง commit ไฟล์นี้เข้า repo** ผู้ใช้จะรันคำสั่งเอง

**เทส:** เทสว่า (ก) frequent_values รวม reference + ประวัติแบบไม่ซ้ำและ reference มาก่อน (ข) import_reference รันซ้ำแล้วไม่สร้างซ้ำ

## งานที่ 3 — นำเข้าหน่วยงาน (แผนกจริง 9 แผนก) แบบง่าย

**ให้ทำ:**
1. Management command `import_units`:
   ```
   uv run manage.py import_units units.csv
   ```
   - CSV UTF-8(-sig) หัวคอลัมน์ `code,name,parent` (parent = code ของหน่วยแม่ ว่างได้)
   - ประมวลผลให้หน่วยแม่ถูกสร้างก่อนถ้าอยู่ในไฟล์เดียวกัน (สองรอบ: สร้างทั้งหมด → ผูก parent)
   - idempotent: code ที่มีแล้ว update ชื่อ/parent ตามไฟล์ (ไม่สร้างซ้ำ) · report สรุปท้ายรัน
2. สร้างไฟล์ตัวอย่าง `docs/examples/units-กศ.csv` (commit ได้ — เป็นชื่อแผนกที่เปิดเผยทั่วไป):
   ```csv
   code,name,parent
   EDU,กองการศึกษา,
   BK,บก.กศ.รร.ส.สส.,EDU
   WIRE,แผนกวิชาการสื่อสารประเภทสาย,EDU
   REW,แผนกวิชาสื่อสารประเภทวิทยุและการสงครามอิเล็กทรอนิกส์,EDU
   STAFF,แผนกวิชาฝ่ายอำนวยการ,EDU
   GEN,แผนกวิชาทั่วไป,EDU
   SIG,แผนกวิชาทหารสื่อสาร,EDU
   LOG,แผนกวิชาการส่งกำลังและการซ่อมบำรุงสาย ส.,EDU
   ELEC,แผนกวิชาไฟฟ้าและอิเล็กทรอนิกส์พื้นฐาน,EDU
   COMP,แผนกวิชาคอมพิวเตอร์และสื่อสารข้อมูล,EDU
   ```
3. แก้ `docs/deploy-guide.md` หมวด 5.5: เพิ่มขั้น "นำเข้าหน่วยงานจริงด้วย `import_units`" ก่อน import ผู้ใช้ (แทนการคีย์มือใน Admin)

**เทส:** import_units สร้างครบ+ผูก parent ถูก, รันซ้ำไม่ duplicate, code ซ้ำ = update ชื่อ

## งานที่ 4 — จัดฟอร์มจองใหม่ ลดช่องท่วมจอ (งานใหญ่สุด)

**ปัญหา:** `templates/bookings/partials/booking_fields.html` วนลูปทุก field ของ `BookingForm` (~20 ช่อง) ลง grid เดียว — บนมือถือยาวหลายจอ ผู้ใช้บอก "ช่องให้กรอกดูเยอะไปหมด"

**ให้ทำ (template + form init เท่านั้น — ห้ามแตะ validation/services):**

1. **โครงใหม่ของ `booking_fields.html`** แบ่ง 4 ส่วน:
   - **ส่วน ๑ สรุปการจอง (อ่านอย่างเดียว):** ห้อง + วันที่ (พ.ศ.) + เวลา ที่ถูกเลือกมาจากขั้นค้นหา แสดงเป็นแถบสรุป (ใช้ context ที่ view ส่งให้ `book_form` อยู่แล้ว) พร้อมลิงก์ "เปลี่ยนวัน/เวลา ←" กลับไปหน้า search พร้อม query เดิม — ช่อง `date/start_time/end_time` ยังต้องอยู่ในฟอร์มเป็น hidden input (ค่าเดิม) เพื่อไม่กระทบ validation ฝั่ง server
   - **ส่วน ๒ กิจกรรม (ช่องหลัก):** `title` (มี datalist จากงานที่ 2), `purpose`, `attendees`
   - **ส่วน ๓ ผู้รับผิดชอบ:** `unit`, `responsible_name`, `responsible_phone` — **prefill ใน `BookingForm.__init__`** เมื่อเป็นฟอร์มสร้างใหม่ (ไม่ bound, ไม่มี instance): `responsible_name` = `user.display_name`, `responsible_phone` = `user.phone` (ถ้ามี), `unit` = `user.unit` (มีพฤติกรรมเดิมอยู่แล้วบางส่วน — ตรวจก่อน อย่าทำซ้ำ)
   - **ส่วน ๔ `<details class="form-more">` "ตัวเลือกเพิ่มเติม":** `attendee_level`, `layout`, `equipment`, `fixed_equipment_*`, `has_external_attendees`, `external_attendees_note`, `visibility`, `note`, และกลุ่ม `is_series`/`series_*` ทั้งหมด — **เปิดอัตโนมัติ (`open`) เมื่อ field ข้างในมี error หรือมีค่า non-default** (เช็คใน template ผ่าน flag ที่ form เตรียมให้ เช่น property `has_more_data`)
2. มือถือ (≤50rem): ฟอร์มคอลัมน์เดียว, ปุ่ม submit หลัก sticky ติดล่างจอ (`position:sticky; bottom:0` พร้อมพื้นหลังทึบ) — เพิ่ม class ใน `app.css`
3. ฟอร์ม amendment (`amend_form.html`) ใช้ partial เดียวกัน — ต้องยังทำงานถูก: กรณี `allowed_fields` จำกัดช่อง ให้ template ข้ามส่วนที่ไม่มี field เหลืออยู่ (ห้าม render หัวข้อเปล่า)
4. ห้ามเปลี่ยน: ชื่อ field, ลำดับ validation, พฤติกรรม HTMX/series ที่มีอยู่ (ปุ่ม "ตรวจสอบชุดการจอง →" ต้องอยู่และทำงานเดิม)

**เทส:** (ก) ฟอร์มใหม่ prefill ชื่อ/เบอร์/หน่วยจากผู้ใช้ (ข) ฟอร์มมี error ในส่วน ๔ → `has_more_data`/flag เปิด details เป็น True (ค) amendment ที่ allowed_fields จำกัด ยัง render ได้ไม่มี KeyError — และเทสเดิม 82 ตัวผ่านครบ

## ลำดับทำ + Definition of Done

ทำเรียง 3 → 2 → 1 → 4 (สองงานแรกให้ข้อมูลใช้ทดลองได้ทันที)

เสร็จเมื่อ:
1. `uv run pytest` ผ่านทั้งหมด (เดิม 82 + ใหม่ของทั้ง 4 งาน) · `uv run manage.py check` ผ่าน
2. `uv run manage.py makemigrations --check --dry-run` ไม่มี migration ค้าง
3. มือถือ 360px: หน้า search กดค้นหาแล้วจอเลื่อนไปผลเอง · ฟอร์มจองเห็นช่องหลัก ≤ 1.5 จอ · ไม่มี horizontal overflow ใหม่
4. รายงานสรุป: แก้ไฟล์ไหน ทำไม พร้อมคำสั่งที่ผู้ตรวจใช้ดูผลด้วยตาได้ทีละขั้น
5. **ห้าม commit** — Claude ตรวจรับก่อน (ผู้ใช้เดินตรวจบนมือถือจริงอีกชั้น)

## สิ่งที่ห้ามทำในรอบนี้

- ห้ามแก้ business rules ใน services (ยกเว้น `frequent_values` ตามงานที่ 2 ซึ่งเป็น presentation helper)
- ห้ามแก้ `ExclusionConstraint` / model Booking / flow อนุมัติ
- ห้ามเพิ่ม dependency ใหม่ / JS framework — vanilla JS สั้น ๆ ใน base.html เท่านั้น
- ห้ามแตะไฟล์ B2/B3 (`deploy-guide.md` แก้ได้เฉพาะจุดที่งานที่ 3 ระบุ, `pilot-checklist.md` ห้ามแตะ)
- ห้าม hard-code รายชื่อวิชา/แผนกในโค้ด — ต้องมาจาก DB ผ่าน command เท่านั้น
