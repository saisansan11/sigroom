# SIGROOM UX/UI Improvement V2 — Phase A–F

วันที่: 24 ก.ย. 2569

## เป้าหมาย

ลดความซับซ้อนของหน้าจอง ทำให้ผู้ใช้ใหม่เข้าใจ SIGROOM ได้เร็วขึ้น แยกเส้นทาง “ห้องเรียน/ประชุม”, “ห้องสอนออนไลน์”, “ห้องพัก” ให้ชัด และยกระดับ mobile/accessibility โดยไม่เปลี่ยน business rules ที่ผ่าน Production QA แล้ว

## Phase A — UX Audit + Bug Hunt

สถานะ: COMPLETE

- ตรวจ Production baseline แบบ read-only
- พบ duplicate online navigation
- พบ generic booking ปน dedicated flow ของ online/lodging
- พบ Step 1 booking density สูงจาก time dropdowns
- พบ lodging action touch target ต่ำกว่า 44px
- บันทึกลง `docs/qa/2026-09-24-sigroom-ux-v2-bug-register.md`

## Phase B — Booking Flow V2

สถานะ: COMPLETE (local branch)

- คง stepper 1–5 และ backend booking flow เดิม
- แยก generic booking ให้ CLASSROOM/MEETING/SPECIAL/LAB
- เพิ่ม category choice ที่ Step 1
- ใช้ time presets เป็น primary path
- ซ่อน start/end dropdown ใน “กำหนดเวลาเอง”
- เก็บ equipment เป็น advanced disclosure
- เพิ่ม today/tomorrow shortcuts
- ไม่เปลี่ยน conflict/approval/hold validation

## Phase C — Home / Intro + Dual CTA

สถานะ: COMPLETE (local branch)

- เพิ่ม `/about/` public intro page
- หน้า authenticated home มี task cards หลัก:
  - จองห้องเรียน/ห้องประชุม (+ ห้องสอนออนไลน์เมื่อมีสิทธิ์)
  - จองห้องพัก
- guest hero อธิบายระบบก่อน dashboard/status data
- เพิ่มทางเข้า “รู้จัก SIGROOM / วิธีใช้งาน”

## Phase D — Navigation Cleanup

สถานะ: COMPLETE (local branch)

- ลบ “ห้องสอนออนไลน์” ซ้ำ
- เปลี่ยน generic label เป็น “จองห้องเรียน” ให้ไม่ชนความหมายกับห้องพัก
- เพิ่ม `รู้จัก SIGROOM` สำหรับ guest และ account popover
- คง role/permission-based operations navigation เดิม

## Phase E — Mobile + Accessibility Polish

สถานะ: COMPLETE ตามหลักฐาน local QA

- CTA และ booking controls หลัก min touch target >=44px
- lodging workspace actions >=44px
- responsive cards collapse เป็น one-column <=50rem
- booking category pills collapse <=30rem
- desktop/narrow-window browser inspection ไม่มี horizontal overflow
- automated accessibility subset PASS

ข้อจำกัดหลักฐาน: browser เครื่อง QA มี native minimum inner width ~500px และ raw CDP mobile emulation ถูก safety layer block จึงใช้ responsive source/test contract ครอบ 360/390/430 แทน screenshot จริง

## Phase F — Full QA + Quality Scorecard

สถานะ: LOCAL COMPLETE — Quality Gate PASS / รอ PR และ CI

หลักฐาน local ที่ปิดแล้วก่อน PR/merge:

1. targeted tests — PASS
2. full pytest 614/614 — PASS
3. Django system check — PASS
4. migration drift — No changes detected
5. git diff hygiene — PASS
6. accessibility gate / Playwright axe 32/32 — PASS
7. local browser visual QA — PASS
8. PR Safety CI — pending PR
9. post-merge CI — pending merge

Production deploy อยู่นอก Phase A–F รอบนี้และต้องขออนุมัติแยก
