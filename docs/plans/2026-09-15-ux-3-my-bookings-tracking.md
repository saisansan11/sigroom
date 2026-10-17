# SIGROOM UX-3 Implementation Plan — My Bookings / Request Tracking

## 1. Goal
ปรับหน้า `การจองของฉัน` ให้ติดตามสถานะและดำเนินการต่อได้ง่ายบนมือถือ โดยลดการพึ่งพาตารางเลื่อนแนวนอน และคง business logic / permission / privacy / schema เดิมทั้งหมด

ฐานงาน:
- Integration base: `feat/lodging-v5-2`
- Base SHA after UX-2 merge: `9884012d48acc448a4b92eb7f3c5845c20a26ab3`
- Branch: `feat/ux-3-my-bookings-tracking`

## 2. Verified friction
จาก real browser บน `/bookings/mine/`:
- Desktop ใช้งานได้ตามปกติ
- ที่ viewport ประมาณ 500px ตัวหน้าไม่ overflow ทั้งหน้า แต่ `.my-bookings-table-wrap` กว้างประมาณ 433px ขณะที่ตารางภายในกว้างประมาณ 645px จึงต้องเลื่อนแนวนอน
- แถบ tabs กว้างกว่าพื้นที่จริงและต้องเลื่อนแนวนอนเล็กน้อย
- ข้อมูลสำคัญสำหรับผู้ใช้มือถือ (กิจกรรม, สถานะ, วันเวลา, ห้อง, action) กระจายเป็นหลายคอลัมน์ จึงสแกนยาก

## 3. Scope
### My bookings tabs
- Desktop behavior เดิม
- Mobile <= 48rem: ให้ tabs wrap เป็นหลายแถวแทน horizontal scrolling
- touch target >= 44px where practical
- รักษา `aria-current="page"` และ query-string tab contract เดิม

### Booking list
- Desktop ยังคง semantic table เดิม
- Mobile <= 48rem: transform table rows ให้เป็น card-like tracking items โดยใช้ markup ชุดเดิม ไม่ duplicate booking loop
- ลำดับภาพบนมือถือ: `กิจกรรม + สถานะ` → `วันเวลา` → `ห้อง` → `อุปกรณ์ (ถ้ามี)` → `actions`
- ปุ่ม `ดูรายละเอียด` และ `จองแบบเดิมอีกครั้ง` ต้องกดง่ายและไม่ล้น
- empty state เดิมต้องยังทำงาน

### Booking series
- ถ้ามี `series_items`, table ของชุดการจองต้องลด horizontal scrolling บนมือถือด้วย responsive card treatment ที่สอดคล้องกัน
- คง link `ดูทั้งชุด` และข้อมูลเดิมทั้งหมด

## 4. Out of scope
ห้ามเปลี่ยน:
- booking/query grouping logic
- request statuses หรือ approval workflow
- rebook eligibility/business rule
- series business behavior
- booking permissions
- privacy model
- database models/schema/migrations
- routes
- production deployment

## 5. Implementation approach
1. เพิ่ม semantic class names เฉพาะ cell ที่ต้องจัด layout responsive ใน `templates/bookings/my_bookings.html`
2. ใช้ CSS breakpoint <= 48rem เพื่อเปลี่ยน presentation ของ `.my-bookings-table` / `.my-series-table` เป็น stacked card rows โดยไม่สร้าง duplicate mobile markup
3. override generic `.table-wrap table { min-width: 42rem; }` เฉพาะ tables สองชุดนี้ใน mobile scope เท่านั้น
4. ให้ `.my-bookings-tabs` wrap และแต่ละ item มี touch target ชัดเจน
5. ใช้ design tokens เดิมเท่านั้น; ห้ามสร้าง token ใหม่เพื่อแก้จุดเดียว

## 6. Automated contracts
สร้าง `bookings/tests_ux3.py` อย่างน้อยตรวจว่า:
- my bookings ยังแสดง 4 tabs และ aria-current ตาม tab ที่เลือก
- booking row มี responsive cell hooks ครบ
- approved booking ยังมี rebook link
- non-approved booking ไม่ได้ rebook link จาก UX-3
- empty state ยังอยู่
- series table responsive hooks ยังอยู่เมื่อมี series data
- CSS มี mobile override ที่ทำให้ my-bookings / my-series ไม่ติด min-width 42rem และ tabs wrap

ห้ามแก้ tests เดิมให้หลวมลง

## 7. Browser QA
ใช้ local/dev only ตรวจ route `/bookings/mine/`:
- authenticated requester
- tabs: upcoming / drafts / past / closed
- approved item + rebook
- draft item
- empty tab
- series section ถ้ามี seed ที่เข้าถึงได้

Viewports target:
- 360 / 390 / 430 / 768 / 1280 / 1440
- ถ้า native Chrome connector มี minimum viewport สูงกว่า 430 ให้บันทึกข้อจำกัด และตรวจค่าที่ทำได้จริงพร้อมอ้างผลเดิมที่ไม่ถูกเปลี่ยนโดย scope นี้

ตรวจ:
- no page horizontal overflow
- no inner booking-list horizontal scrolling on mobile
- clipped text / overlap
- touch target
- keyboard focus
- status readability
- action usability
- desktop table remains table-like
- console/runtime errors when available

## 8. Required gates
ก่อนพร้อม PR:
- targeted UX-3 tests PASS
- related my-bookings / rebook regression PASS
- `uv run manage.py check`
- `uv run manage.py makemigrations --check --dry-run` → No changes detected
- `uv run pytest --tb=short -q` full suite PASS
- `git diff --check` PASS
- complete branch diff review versus `feat/lodging-v5-2`
- verify no undefined CSS variables / duplicate CSS / dead markup / business-rule drift

## 9. PR contract
เมื่อผ่านทุก gate:
- handoff: `docs/handoffs/2026-09-15-ux-3-my-bookings-tracking.md`
- stage scoped files only
- commit / push branch `feat/ux-3-my-bookings-tracking`
- open PR to `feat/lodging-v5-2`
- re-review PR diff / base / head / head SHA / mergeability / checks
- stop at `READY FOR MERGE`
- do not merge without explicit user instruction
