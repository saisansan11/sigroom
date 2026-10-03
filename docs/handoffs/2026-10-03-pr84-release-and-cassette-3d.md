# PR #84 release และตลับเทป 3D

## Production ที่ยืนยันแล้ว
- ผู้ใช้ส่งผล Reviewer ผ่าน HEAD 55322d32e99894bb658023076a3f8d99776518d1 และอนุมัติ merge/deploy ชัดเจน
- #84 merged: a9fc55233ea9e01cabb6bd2a85ac88ca9e2b6c03; tree เหมือน approved HEAD
- CI ของ merge commit: 37118515816 SUCCESS
- Cloud Build: f7b80bf6-3783-4a1a-afca-b0564cc7c328 SUCCESS; migration/build/deploy สำเร็จ ไม่มี migration delta จาก production เดิม
- Cloud Run: sigroom-00076-d6x, traffic 100%, image tag ตรง a9fc55233ea9e01cabb6bd2a85ac88ca9e2b6c03
- Firebase Hosting sigroom ปล่อยสำเร็จ; https://sigroom.web.app/home/ HTTP 200; เปิด login production ในเบราว์เซอร์ได้
- จุด rollback Cloud Run เดิม: sigroom-00075-5lg, image tag 74933b125df8809c35278b344ec7dfe50d2b8d16; หากต้องย้อนทั้ง release ให้คืน Hosting/static ของ commit เดียวกันด้วย ยังไม่ได้ดำเนินการ rollback

## งานใหม่
- branch feat/cassette-3d-realism จาก a9fc552; production ยังเป็น #84
- แก้ CSS specificity ที่ทำให้ธีมห้องพักทับสีเปลือกและปุ่มครอบบัตร เพิ่มผิว/สัน/สกรู/รอยประกบ/หน้าต่างเว้า และย้ายหน้าต่างพ้นชื่อผู้เข้าพัก
- จำกัดมุมลาก; pointercancel/lost capture คืนสภาพโดยไม่พลิก; หยุด reel เมื่ออยู่นอกจอและเปิด dialog QR
- ไม่แก้ services, permissions, no-store, QR endpoint หรือ stay progress
- full pytest 862 passed; node interaction tests 3 passed; Django check 0 issues; migration check no changes; diff check ผ่าน
- Browser QA: ข้อมูลสมมติในฐาน local sigroom_pr84_browser_qa แยกจากฐานเดิม; Chrome engine ผ่าน in-app browser
- หน้าบัตรตรวจ overflow ที่ 360/390/430/768/1280/1440px; ภาพด้านหน้าบน 390px; ทดสอบ flip, dialog, Escape และ focus return; ไม่มี console error ในเส้นทางตรวจ
- เปิด login และ gateway ของ approved #84 ที่ 390px; ต้นแบบใหม่ตรวจเฉพาะหน้าบัตรตาม scope
- ยังไม่ได้ทดสอบกล้องจริงสองเครื่อง, Safari หรือ OS reduced-motion; unit tests ไม่ใช่หลักฐานแทนการตรวจอุปกรณ์จริง
- Follow-up Reviewer เดิม: ประกาศหลายวันควรแสดงวันที่, native confirm เดิม, blackout logic ซ้ำ ไม่รวมใน PR นี้
- งานถัดไป: นกพิราบสื่อสารตาม PR-C และแผน 3D; ฟีเจอร์ใหม่ต้องส่ง Review ก่อน merge/deploy
