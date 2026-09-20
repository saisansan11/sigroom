# SIGROOM UX-30 — Lodging Occupancy Triage

## Goal
ทำให้เจ้าหน้าที่เห็นความคืบหน้าการจัดผู้เข้าพักและหาห้องที่ต้องทำงานต่อได้ทันทีใน Lodging Staff Workspace หลัง UX-29 โดยไม่ต้องเปิดการ์ดห้องทีละใบ

## Verified friction
- Workspace แสดงห้องเป็นการ์ดแบบพับทั้งหมด แต่ไม่มีภาพรวมว่าจัดผู้พักแล้วกี่คน เหลือกี่เตียง หรือรายงานตัวแล้วกี่คน
- เมื่อต้องจัดหลายห้อง เจ้าหน้าที่ต้องไล่เปิดการ์ดเพื่อแยกห้องที่ยังมีเตียงว่างออกจากห้องที่เต็มแล้ว
- ข้อมูลที่ต้องใช้มีอยู่แล้วใน `CourseLodgingCohort`, ห้องที่จัดสรร และ `CourseStudentLodging`; ไม่ต้องเพิ่ม schema

## Scope
1. เพิ่ม summary สำหรับความจุทั้งหมด, จำนวนจัดแล้ว, จำนวนเตียงว่าง และจำนวนรายงานตัวแล้ว
2. เพิ่มจำนวนห้องทั้งหมด / ห้องที่ยังมีเตียงว่าง / ห้องเต็ม
3. เพิ่ม server-side filter `room_filter=all|free|full`
4. ค่า filter ที่ไม่รู้จักต้อง fallback เป็น `all`
5. Bed-first action ของ UX-29 ต้องรักษา room filter ปัจจุบันเมื่อพาไป assignment panel
6. Empty state ของ filter ต้องบอกชัดและมีทางกลับไปดูทุกห้อง

## Non-goals
- ไม่เปลี่ยน schema/migration
- ไม่เปลี่ยน permission/privacy
- ไม่เปลี่ยน allocation, assignment, conflict, check-in หรือ transaction rules
- ไม่เพิ่ม client-side source of truth
- ไม่ deploy production ใน phase นี้

## Risks / controls
- Summary ต้องคำนวณจากข้อมูลชุดเดียวกับ room board เพื่อลดความเสี่ยงตัวเลขไม่ตรงกัน
- Filter เป็น presentation-only; ห้ามมีผลต่อ form choices หรือ backend validation
- PII ยังคงอยู่เฉพาะ staff workspace ที่มี authorization เดิม
- Mobile filter controls ต้องแตะง่ายและไม่สร้าง horizontal overflow

## Verification
- UX-30 targeted tests: summary counts, free/full/all filter, invalid filter fallback
- UX-29 regression เพื่อยืนยัน bed-first assignment ไม่ถอยหลัง
- Django `check`
- `makemigrations --check --dry-run`
- full pytest regression
- `git diff --check`
- Real browser QA 390px และ 1440px: summary, filter free/full/all, bed-first action, no overflow/console error, axe A/AA
- PR Safety Gate ก่อน merge
