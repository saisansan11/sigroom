# SIGROOM UX-31 — Lodging Arrival Triage

## Goal
ทำให้เจ้าหน้าที่เห็นผู้เข้าพักที่ยังไม่รายงานตัวและไปยืนยัน check-in ได้จาก Lodging Staff Workspace โดยใช้ check-in route/service เดิม ไม่สร้าง business rule ใหม่

## Verified friction
- UX30 แสดงจำนวนรายงานตัวแล้ว แต่ยังไม่แสดงจำนวนผู้ที่รอรายงานตัวโดยตรง
- ผังเตียงแสดงคำว่า “รายงานตัวแล้ว” เฉพาะผู้ที่มาแล้ว แต่ผู้ที่ยังไม่มาไม่มีสถานะหรือ action ต่อ
- เจ้าหน้าที่ต้องออกจาก workspace แล้วค้นหา QR/check-in page แยก ทั้งที่ `CourseStudentLodging` และ `check_in_student()` มี contract ที่ปลอดภัยอยู่แล้ว

## Scope
1. เพิ่ม arrival summary แยกจำนวน “รอรายงานตัว” และ “รายงานตัวแล้ว” โดยไม่เปลี่ยน occupancy contract ของ UX30
2. เพิ่ม presentation-only filter `arrival_filter=all|pending|checked_in` และ fallback เป็น `all` เมื่อค่าผิด
3. ให้ occupied bed แสดงสถานะ arrival ชัดเจน และผู้ที่ยังไม่รายงานตัวมีลิงก์ “ตรวจรับรายงานตัว” ไป route เดิม
4. เมื่อเข้าหน้า check-in จาก staff workspace ให้มี safe return link กลับ workspace และคง context หลัง POST โดยไม่รับ arbitrary redirect URL
5. รักษา room filter/bed-first context ของ UX29–30

## Non-goals
- ไม่เพิ่มหรือแก้ schema/migration
- ไม่เปลี่ยน `check_in_student()` transaction, locking, duplicate protection หรือ permission
- ไม่เพิ่ม endpoint check-in ใหม่
- ไม่เปลี่ยน public QR privacy behavior
- ไม่ deploy production ใน phase นี้

## Risks / controls
- Arrival filter เป็น presentation-only; backend check-in authorization ยังคงอยู่ใน `check_in_student()`
- Return navigation ใช้ flag คงที่จากระบบและสร้าง URL ฝั่ง server; ไม่รับ `next` URL จากผู้ใช้
- Public/anonymous check-in view ต้องไม่แสดงลิงก์ staff workspace แม้มี query flag
- ตัวกรอง arrival และ room ต้อง compose กันได้โดยไม่เปลี่ยน assignment form choices

## Verification
- UX31 targeted tests: arrival counts/filter/fallback/status/action/safe return/public privacy/POST redirect
- UX29–30 targeted regression
- Django `check`
- `makemigrations --check --dry-run`
- full pytest regression
- `git diff --check`
- Real browser QA 390×844 และ 1440×900: arrival summary/filter, pending action, return path, no overflow/console errors, axe A/AA
- PR Safety Gate before merge
