# ต้นแบบนกพิราบสื่อสาร 3D

ฐาน: a9fc55233ea9e01cabb6bd2a85ac88ca9e2b6c03 (#84 merged และ deploy แล้ว)
branch: feat/teaching-pigeon-3d-preview

## ผลงาน
- docs/mockups/teaching-pigeon-3d-preview.html: ต้นแบบแยกจากฉบับเดิม ตัวเครื่องมีฝาหลัง ขอบ จอเว้า สกรู และปุ่มกดยุบ ปรับมุมด้วยคีย์บอร์ด/สัมผัสได้
- docs/plans/2026-10-03-teaching-pigeon-3d-preview.md: ขอบเขตต้นแบบและแผนเชื่อมระบบ PR-C
- ทั้งหมดเป็นข้อมูลสมมติ ไม่เชื่อมบัญชี ไม่สร้าง migration และไม่เปลี่ยน application routes
- ฟักไข่แสดงลูกนกโดยจำนวนสอนจบยังเป็น 0; ใช้ฟอนต์ local ไม่มี URL ภายนอก

## ตรวจแล้ว
- Full regression: 862 passed (151.49s) บนฐานทดสอบ local แยก; warnings เดิมเรื่อง Django 6 และ static directory
- Inline JavaScript syntax ผ่าน 1 script; ไม่มี ID ซ้ำ; HTML 23,989 bytes
- Django check: 0 issues; migration check: No changes detected
- Browser จริงผ่าน in-app Chromium ที่ localhost:8017/docs/mockups/teaching-pigeon-3d-preview.html
- ตรวจ overflow 360/390/430/768/1280/1440px: ไม่ล้น
- ตรวจภาพมือถือ 390px และ desktop; ทดสอบฟักไข่/ให้อาหาร/ลูบหัว/สถิติ/ตั้งชื่อ/ปรับมุมด้วย End/คืนมุมตรง
- Console error: ไม่พบในเส้นทางที่ตรวจ
- reduced-motion/hidden-tab มี implementation แต่ยังไม่ได้ตรวจ OS preference และ Safari จริง จึงไม่อ้าง device acceptance

## งานอื่น
- PR #85 ตลับเทป HEAD d91eb4d12cb62484ee54ac99f1d00410279c1e2c: CI 37119236680 ผ่านครบ 6 gate; ยัง Draft ไม่ merge/deploy
- Production ยังคง #84: a9fc552 / sigroom-00076-d6x ตามหลักฐาน deploy รอบก่อน

## งานถัดไป
ตรวจภาพต้นแบบก่อนต่อ PR-C จากแผนเดิม: TeachingPigeon model, services, savepoint failure isolation, run_jobs, owner-only/no-store และ UI จริง โดยโตจาก USED ไม่ใช่จากการจอง และไม่ถอยขั้น

## ส่งต่องาน
อ่าน SIGROOM workflow และแผน PR-C แล้วตรวจ Git/GitHub ล่าสุดอีกครั้ง งานต้นแบบ 3D อยู่ branch feat/teaching-pigeon-3d-preview; งานตลับอยู่ Draft #85 อย่า merge/deploy งานใหม่โดยไม่มีคำสั่งเฉพาะ รักษางานอื่นทั้งหมด
## Review correction — 3 Oct 2026
Feedback expiry now uses a one-shot timer independent of animation; renaming clears feedback and updates immediately. Opacity moved to outer stage, keeping device preserve-3d intact. Added four dependency-free Node tests and wired npm run test:interaction into required Repository checks (same workflow/script change as #85, glob includes both suites after merging).
Local verification: four Node tests pass with reduced-motion enabled and zero animation intervals; A/B/C feedback expires, rename works, hatch count stays zero. Django check and migration drift pass. Full suite: 862 passed in 131s (existing warnings). Browser at port 8017: petOff on, tilt 24 degrees, LCD and A/B/C remain visible; rename during feedback updates immediately. Actual OS reduced-motion and Safari not exercised; reduced-motion evidence is VM regression tests. Screenshot displayed during QA; saving the screenshot was denied by the browser tool filesystem.
Scope remains a mockup plus tests/CI/docs, not runtime pet integration. Review new HEAD before leaving Draft; no merge or deploy. CI must be checked on new HEAD.
