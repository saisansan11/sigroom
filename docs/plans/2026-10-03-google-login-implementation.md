# แผนลงมือ PR-6

ฐานงานแยก `task/online-beta-pr6` จาก PR-1; นำ diff ไปต่อ PR-5 ตาม runbook โดยผู้ทำงานหลัก

- เพิ่ม django-allauth เฉพาะ Google จาก env; URL อื่นของ allauth ไม่เปิด, เริ่มด้วย POST/CSRF, ตรวจลายเซ็น ID token และ state ของ OAuth, callback ใช้ PUBLIC_BASE_URL
- จับคู่บัญชีเดิมด้วย school email ที่ยืนยันแล้วและ hd; ปฏิเสธบัญชีปิดใช้/uid ไม่ตรง; คง password backend และ login audit เดิม
- เพิ่มรายชื่อสิทธิ์นักเรียนตามรุ่นใน Admin เพราะฐานเดิมไม่มี roster ที่พิสูจน์ membership; สร้างบัญชีอัตโนมัติเฉพาะอีเมลในรายชื่อของรุ่นที่สแกน QR แล้ว สิทธิ์ต่ำสุดและรหัสใช้ไม่ได้
- เพิ่ม nullable user ในการจองเตียง; ล็อกสิทธิ์บัญชีนักเรียนใหม่ที่ service และ middleware; ข้อมูลติดต่อจาก roster เติมให้ ถ้ายังไม่ครบใช้ฟอร์มจองเตียงเดิม โดยชื่อจาก Google
- login ก่อนรายการรุ่น/portal/จองเตียง; token บัตรเดิมยังใช้ได้; บัตรใหม่ผูกกับเจ้าของบัญชี
- เพิ่ม tests สำหรับ claims, state, CSRF, next, callback header, UID, membership, ownership, สิทธิ์นักเรียน และบัญชีเดิม
- เขียนคู่มือ Cloud ให้ผู้ใช้ทำเอง ไม่ตั้ง OAuth/secret/deploy

ข้อสงสัย: ไม่มีข้อมูลระบุสมาชิกหลักสูตรเดิม จึงต้องให้ผู้จัดหลักสูตรเตรียมรายชื่อก่อนเปิด flow; ไม่ใช้ school domain/QR เป็นหลักฐานเป็นนักเรียนรุ่นนั้น ยศ สังกัด และโทรศัพท์ไม่เดาค่าเอง

การตรวจ full pytest, Node, Django check, migrations check, browser login มี/ไม่มีปุ่มทั้ง 390px และ desktop รวมถึง PR/CI ดำเนินการโดยผู้ทำงานหลักหลังรวมลง stack
