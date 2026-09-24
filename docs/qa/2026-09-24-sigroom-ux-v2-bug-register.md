# SIGROOM UX V2 — Bug Register

วันที่: 24 ก.ย. 2569
ฐานงาน: `origin/feat/lodging-v5-2` @ `48310a576155f37a5af0a6dea0356a340cf94c55`
ขอบเขต: หน้าแนะนำ, หน้าแรก, เส้นทางจองห้อง/ห้องพัก/ห้องสอนออนไลน์, Booking Flow, navigation, mobile/touch UX

## Product defects / UX debt

| ID | ระดับ | อาการก่อนแก้ | สาเหตุ | การแก้ | สถานะ |
|---|---|---|---|---|---|
| UX32-01 | P1 | เมนู desktop แสดง “ห้องสอนออนไลน์” ซ้ำ 2 รายการ | template navigation ซ้ำ | เหลือ direct link เดียวและคง permission guard เดิม | FIXED |
| UX32-02 | P1 | `/book/` เป็นเส้นทางรวมจนผู้ใช้ไม่รู้ว่าห้องพัก/ห้องออนไลน์มี flow เฉพาะ | generic search ไม่จำกัด category | generic booking จำกัดเฉพาะ CLASSROOM/MEETING/SPECIAL/LAB และเพิ่ม category filter | FIXED |
| UX32-03 | P0 UX | หน้า Step 1 แสดง start/end dropdown 15 นาทีจำนวนมากพร้อมกัน ทำให้หน้ารก | progressive disclosure ไม่เพียงพอ | preset “คาบเช้า/คาบบ่าย/ทั้งวัน” เป็นทางหลัก; start/end อยู่ใต้ “กำหนดเวลาเอง” | FIXED |
| UX32-04 | P1 UX | หน้าแรกเหมือน operations dashboard มากกว่าหน้าเริ่มงาน ผู้ใช้ใหม่ไม่เห็นเส้นทางหลักทันที | visual hierarchy เริ่มจากข้อมูลสถานะ | เพิ่ม task cards “จองห้องเรียน/ห้องสอน” และ “จองห้องพัก” ก่อนเนื้อหารอง พร้อมหน้า `/about/` | FIXED |
| UX32-05 | P2 | action links บางจุดใน lodging workspace สูง ~25–40px บน mobile | link style ไม่มี minimum touch target | class `lodging-workspace-link` min-height >= 44px | FIXED |
| UX32-06 | P2 | summary “อุปกรณ์ส่วนกลาง” วัดจาก browser ได้ 37px | legacy summary style | override min-height >= 44px; browser read-back = 44px | FIXED |
| UX32-07 | P2 regression | guest homepage copy contract “สถานะห้องและที่พักวันนี้” หายหลังปรับ hero | เปลี่ยน headline โดยไม่เก็บ semantic/status copy เดิม | ย้ายข้อความเดิมไว้ใน eyebrow และคง headline onboarding ใหม่ | FIXED |

## QA / environment findings (ไม่ใช่ product defect)

| ID | อาการ | การจัดการ |
|---|---|---|
| QA32-01 | local pytest รอบแรกได้ 301 ทุกหน้า | พบว่า local env ใช้ secure redirect เมื่อไม่ได้กำหนด `DJANGO_SECURE=0`; รันซ้ำด้วย local test env แล้ว targeted 42/42 PASS |
| QA32-02 | accessibility subset ชน `test_postgres` กับ full pytest ที่รันขนานกัน | รัน sequential หลัง full test ปิด connection; accessibility subset 13/13 PASS |
| QA32-03 | raw DevTools mobile emulation ถูก safety layer ปฏิเสธ | ไม่ bypass; ใช้ native narrow-window QA (~500px), responsive CSS contracts และ automated accessibility testsแทน |
| QA32-04 | local preview DB ไม่มี schema | สร้าง local-only `sigroom_ux32_preview`, migrate และ seed resource data; ไม่แตะ Production |

## Known non-blockers / follow-up

- Chrome บนเครื่อง QA มี minimum inner width ราว 500px เมื่อ resize แบบ native; breakpoint 360/390/430 จึงยืนยันจาก CSS/test contract ไม่ใช่ screenshot จริงในรอบนี้.
- ไม่มี performance benchmark/Lighthouse ใหม่ใน scope นี้; feature ไม่เพิ่ม external JS library หรือ media asset ใหม่.
- Production ยังไม่ถูก deploy จาก branch UX V2 จนกว่าจะผ่าน PR/CI/merge และได้รับอนุมัติ deploy แยก.
