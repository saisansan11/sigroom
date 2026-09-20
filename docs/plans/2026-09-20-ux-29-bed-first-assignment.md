# SIGROOM UX-29 — Bed-first Assignment

## Goal
ลด friction ใน Lodging Staff Workspace หลัง UX-28 โดยให้เจ้าหน้าที่เริ่มจากเตียงว่างที่เห็นอยู่จริง แล้วพาไปยังฟอร์มจัดผู้พักพร้อมเลือกห้อง/เตียงให้อัตโนมัติ แทนการจำเลขห้องและเลือกซ้ำเอง

## Verified friction
- ผังห้องแสดงเตียงว่าง แต่ฟอร์มจัดผู้พักเป็น select ห้อง + select เตียงแยกต่างหาก
- บนมือถือฟอร์มอยู่หลังรายการห้อง ทำให้ต้องจำห้อง/เตียงและเลื่อนลงไกล
- การเลือกด้วยมืออาจเลือกเตียงที่เพิ่งมีผู้พักแล้ว แม้ backend จะ revalidate และปฏิเสธอย่างถูกต้อง

## Scope
1. เพิ่ม action `จัดคนลงเตียงนี้` เฉพาะเตียงที่ว่างใน staff workspace
2. Action ใช้ URL/query string ไปยัง workspace เดิม พร้อม `cohort`, `room`, `bed` และ fragment ไปส่วน assignment
3. View ตรวจว่า room อยู่ใน cohort, bed อยู่ในช่วงที่กำหนด และยังว่างก่อนใช้เป็น initial ของ AssignmentForm
4. แสดง selected-bed context ใน assignment panel เพื่อให้เจ้าหน้าที่เห็นว่ากำลังจัดห้อง/เตียงใด
5. คง manual selects ไว้เป็น fallback และคง backend validation/race protection เดิมทั้งหมด

## Non-goals
- ไม่เปลี่ยน schema/migration
- ไม่เปลี่ยน permission หรือ privacy
- ไม่เปลี่ยน `assign_lodging_bed()` หรือกฎ conflict
- ไม่เพิ่ม client-side source of truth สำหรับสถานะเตียง
- ไม่ deploy production ใน phase นี้

## Risks / controls
- Query string ถูกแก้เองได้: ใช้เพื่อ prefill เท่านั้น และต้อง revalidate กับ cohort/current occupancy ก่อนแสดง selected context
- Race หลัง page load: backend `assign_lodging_bed()` ยังคง lock/revalidate ตอน POST
- Mobile usability: action ต้องมี touch target ชัดเจนและ assignment panel ไม่ sticky บน mobile ตาม behavior เดิม

## Verification
- Targeted UX-29 tests: free-bed action, preselection, occupied/tampered selection rejection
- Existing UX-28 operations regression
- Django `check`
- `makemigrations --check --dry-run`
- full pytest regression
- `git diff --check`
- Real browser QA: staff workspace 390px and 1440px, click free bed → correct preselection/context, occupied bed has no action, no overflow/console error
- PR Safety Gate before merge
