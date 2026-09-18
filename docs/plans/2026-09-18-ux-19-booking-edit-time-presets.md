# UX-19 — Booking Edit Time Preset Parity

วันที่: 18 กันยายน 2569

## สถานะตั้งต้นที่ตรวจจริง

- Base: `origin/feat/lodging-v5-2`
- Base commit: `456069ab0b1cabbc28c722eb8527827a36fa1655` (Merge PR #41 / UX-18)
- UX-18 commit `2ed5814cfb7f7ff442302243d95c83b50cbe40a0` อยู่ในประวัติ base แล้ว
- PR #41 = MERGED และ PR Safety Gate ผ่านครบจาก GitHub
- ไม่มี deploy ในขอบเขต UX-19

## ปัญหาที่พิสูจน์จาก source

`docs/v7-notes.md` ระบุ Known Issue ว่า Draft Booking Edit ยังแก้วัน/เวลาได้ แต่ไม่แสดง Time Presets เพราะ `booking_edit` ไม่ส่ง `time_presets` เข้า template context.

ตรวจ source แล้วพบว่า:

1. `templates/bookings/booking_edit.html` reuse `bookings/partials/booking_fields.html`.
2. shared partial จะแสดง `partials/time_presets.html` เมื่อมี date/start/end fields และมี `time_presets` ใน context.
3. `bookings.views.book_search` และ `book_form` ส่ง `time_presets()` อยู่แล้ว แต่ `booking_edit` ยังไม่ส่ง.
4. `bookings.services.editable_fields()` อนุญาต date/start/end เฉพาะ Draft; หลัง submit ใช้ `POST_SUBMIT_EDITABLE_FIELDS` ซึ่งไม่มีวัน/เวลา.
5. CSS ของ `.time-preset-row` / `.time-preset-button` มี flex-wrap และ touch target >= 44px อยู่แล้ว จึงไม่ต้องเพิ่ม CSS ซ้ำ.

## เป้าหมาย

ทำให้หน้า Draft Booking Edit มี Time Presets แบบเดียวกับ flow จองปกติ โดยไม่เปลี่ยน business rule, สิทธิ์, conflict protection หรือ post-submit edit policy.

## ขอบเขต implementation

1. เพิ่ม `time_presets()` ให้ context ของ `booking_edit`.
2. เพิ่ม regression tests ใหม่สำหรับ UX-19 เพื่อยืนยันว่า:
   - Draft owner เปิดหน้า edit แล้วเห็น preset buttons และ date/start/end fields.
   - Post-submit owner เปิดหน้า edit แล้วไม่เห็น preset buttons และไม่มี date/start/end fields.
   - ผู้ใช้ที่ไม่ใช่ owner ยังถูกปฏิเสธเหมือนเดิม.
   - POST หลัง submit ที่แอบส่งวัน/เวลาใหม่ยังไม่เปลี่ยนเวลาเดิม (regression ของ security/business invariant).
3. อัปเดต Known Issue ใน `docs/v7-notes.md` หลังตรวจผ่าน ให้ระบุว่าแก้ใน UX-19 โดยไม่ลบประวัติเดิมแบบไร้ร่องรอย.
4. จัดทำ handoff หลังผ่านทุก gate.

## นอกขอบเขต

- ไม่แก้ `editable_fields`, `POST_SUBMIT_EDITABLE_FIELDS`, amendment flow หรือ conflict logic
- ไม่แก้ schema / migration / models
- ไม่เพิ่ม JavaScript หรือ CSS ใหม่ถ้า existing preset component ใช้งานได้จริง
- ไม่ redesign booking form ทั้งหน้า
- ไม่ deploy
- ไม่ merge PR โดยไม่มีคำสั่งอนุมัติ merge ที่ระบุ PR ชัดเจน

## Quality Gates

1. Self-review diff
2. Targeted UX-19 tests + regression tests ที่เกี่ยวข้อง
3. `uv run manage.py check`
4. `uv run manage.py makemigrations --check --dry-run`
5. `uv run pytest`
6. `git diff --check`
7. Real Browser QA อย่างน้อย mobile 390px และ desktop 1280px:
   - Draft edit: preset visible; click preset updates start/end controls
   - Post-submit edit: preset absent; date/time absent; amendment guidance preserved
   - ไม่มี horizontal overflow / action button usable
8. Review complete diff
9. Commit + push feature branch
10. PR against `feat/lodging-v5-2`
11. Re-read PR diff + CI / PR Safety Gate
12. Stop before merge and request explicit approval
