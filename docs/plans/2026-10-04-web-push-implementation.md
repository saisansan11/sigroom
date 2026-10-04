# แผน PR-5: แจ้งเตือนเข้ามือถือ

อิง runbook PR-5 และ stack PR-1 → PR-4 ใช้ worktree แยก `online-beta-pr5` ให้ parent ประกอบ ตรวจ full regression และเปิด PR ตามลำดับ

1. เพิ่ม pywebpush ที่ผู้ใช้อนุมัติ พร้อม model subscription แบบ expand
2. ปิดฟีเจอร์เมื่อ env VAPID ไม่ครบ ทุก push URL และ service worker ตอบ 404
3. บันทึก/ลบ subscription ด้วย login + POST + CSRF จำกัด 10 ต่อบัญชี ไม่เปลี่ยนเจ้าของ endpoint
4. ตรวจ endpoint HTTPS เฉพาะผู้ให้บริการ browser push ที่ยืนยันได้ และตรวจ key ก่อนบันทึก ปิด redirect ขณะส่ง
5. เพิ่มปุ่มเดียวบนหน้ากระดิ่งและหน้าจองออนไลน์ ขอ permission เฉพาะผู้ใช้กด สถานะปิด/เปิด/ไม่รองรับ/ล้มเหลว และคู่มือติดตั้ง iPhone
6. service worker รับ push และเปิด URL ภายในเท่านั้น ไม่ fetch/cache หน้าเว็บ
7. ส่งทุกเครื่อง แยกความล้มเหลว ลบ 404/410 บันทึกเวลา/จำนวนล้มเหลว เชื่อม PR-4 หลังสร้างแถวใหม่และ commit
8. คู่มือสร้างกุญแจ/ตั้ง secret ให้ผู้ใช้ทำเอง ไม่สร้างกุญแจในงานนี้

ทดสอบ: config ปิด, login/CSRF/POST, cap/ownership/keys/endpoint, mock ส่งสำเร็จ/หมดอายุ/ล้มเหลว, payload ไม่บรรจุข้อมูลส่วนตัวหรือ URL ภายนอก, Node เรื่อง user gesture/CSRF/session/worker URL จากนั้น parent full pytest, migration drift, Node และ browser มือถือ 390px/คอม

นอกขอบเขต: deploy, Google Cloud, ข้อมูลจริง, แสดง push จริงโดยไม่มีกุญแจ, merge PR, แก้ PR #82 หรือ workflow booking เดิม
