# นกพิราบสื่อสาร: เริ่มงานตัวเครื่อง 3D

ฐานที่ปล่อยแล้ว: #84 / a9fc55233ea9e01cabb6bd2a85ac88ca9e2b6c03
branch: feat/teaching-pigeon-3d-preview; แยกจากงานตลับเทป #85

## รอบนี้
สร้างต้นแบบโต้ตอบของตัวเครื่องให้ตรวจรูปลักษณ์ก่อนเชื่อมข้อมูลจริง ตามขั้นร่างหน้าจอก่อน implementation ใน CLAUDE.md
- ใช้ docs/mockups/teaching-pigeon-mockup.html เดิมเป็นฐาน และเก็บไฟล์เดิมไว้เปรียบเทียบ
- ตัวเครื่องเขียวทหาร มีฝาหน้า/หลังและขอบหนา รอยประกบ สกรู เบ้าจอ LCD และปุ่ม A/B/C ที่กดยุบได้
- ปรับมุมด้วยตัวเลื่อนที่ใช้คีย์บอร์ดและสัมผัสได้ แสดงสถานะจำลองชัดเจน ข้อมูลทั้งหมดเป็นสมมติ
- โหลดฟอนต์จาก static/fonts ของ repository เท่านั้น; ไม่เพิ่ม library
- reduced-motion ปิดการเคลื่อนไหวอัตโนมัติและคงตัวเครื่องตรง; หยุด timer เมื่อแท็บถูกซ่อน
- ตรวจภาพและปุ่มจริงในเบราว์เซอร์ที่ 390px และ desktop, ตรวจ overflow ตาม UI profile

## รอบเชื่อมระบบ (PR-C)
ใช้แผน 2026-10-03-pr-c-teaching-pigeon.md ต่อ: model/migration เพิ่มตาราง, services, permission/no-store, run_jobs, หน้านก, ข้อความหลังจองและ gateway
- การเติบโตมาจาก USED; ไข่ได้ครั้งแรก ฟักถึงเวลาสอน; ไม่ถอยขั้น ไม่ตาย ไม่หิว
- ให้อาหารและลูบหัวไม่เปลี่ยน booking, usage หรือคะแนน
- แยกความล้มเหลว grant_egg ด้วย savepoint ภายใน booking transaction; DatabaseError ของนกต้องไม่ทำให้การจองเสีย
- GET อ่านอย่างเดียว; sync job idempotent; ข้อมูลเฉพาะเจ้าของ; storage ฉากฟักต้องไม่ปะปนผู้ใช้บนเครื่องร่วม
- เพิ่ม tests ของการจองล้ม/ซ้ำ/พร้อมกัน, stage/mood, เจ้าของและสิทธิ์, no-store, setting ปิดระบบ, migration ฐานว่าง/ฐานเดิม
- Full pytest, check, migration check, real Browser QA, CI และ Reviewer ก่อน merge/deploy

## ขอบเขต
ต้นแบบรอบนี้ยังไม่ให้ไข่จริง ไม่บันทึกข้อมูล ไม่สร้าง migration และไม่ใช่ฟีเจอร์ที่เปิด production แล้ว การเชื่อม backend เป็น PR-C ถัดจากการตรวจต้นแบบนี้
