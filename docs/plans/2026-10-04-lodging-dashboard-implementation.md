# แผนลงมือ PR-7

ฐานแยก `task/online-beta-pr7` จาก PR-1 ที่ merge แล้ว ผู้ทำงานหลักนำ diff ไปต่อ PR-6 ตามลำดับหลังตรวจ

- เพิ่มประเภทแอร์/พัดลมใน Resource แบบ expand ตั้งค่าเฉพาะ alias ห้องในแปลนจริงจาก lodging_about_data; ห้องอื่นไม่เดาประเภท
- Occupancy ใช้ CourseStudentLodging ของ cohort ที่ allocation_status=allocated และ Booking ที่ approved + PublicLodgingAccess ไม่เอา cohort room holds มานับซ้ำ คืนข้อมูลด้วยจำนวน query คงที่เมื่อเพิ่มห้อง
- เพิ่ม LodgingRate จาก RATES และ nullable อัตราที่เจ้าหน้าที่เลือกชัดเจนใน student/Booking ไม่เดาประเภทผู้พักจากยศหรือสังกัด ไม่มีอัตราแสดงยอดยังไม่ครบ
- Decimal เท่านั้น คืนอย่างน้อย1 ราคาต่อวัน×คืน ต่อคนเป็นค่าเริ่มต้น Admin เปลี่ยนต่อห้องได้ รายเดือนใช้แสดงเทียบเมื่อเกิน30คืนเท่านั้น
- มิเตอร์เฉพาะห้องแอร์ ช่วงเข้าพัก/เลขเข้า/เลขออก/ราคาต่อหน่วย ผู้บันทึก เวลา; ไม่มีราคาไฟตั้งต้น ตรวจเลขไม่ติดลบ/ออก>=เข้าและ audit ทุก save รวม Admin
- Dashboard ใช้ can_access_lodging_management, filters วัน/ชั้น/ว่าง/มีผู้พัก/เต็ม, partial refresh30s เฉพาะเมื่อ tab visible, รายชื่อใน drawer ยังจำกัดสิทธิ์ของแต่ละ cohort/Booking และ CSV มีเฉพาะยอดรายห้อง
- เมนูจัดการที่พักชี้ dashboard แต่มีลิงก์ workspace/manage เดิม ไม่ย้ายกฎ allocation/การจอง/การกันชน
- ตรวจ negative permissions, ข้อมูลทั้งสองแหล่ง, query bound, Decimal/basis, meter validation/audit/Admin, full regression/Node/check/drift/diff; ภาพ Browser QA ผู้ทำงานหลักตรวจหลังรวม stack

ร่างหน้า: แดชบอร์ดห้องพัก [วัน] [ชั้น] [สถานะ] → สรุปจำนวนและยอดที่ทราบ → ห้องแต่ละชั้น (จุด+ข้อความ+จำนวน) → เลือกห้องเปิดแผงรายชื่อที่มีสิทธิ์ อัตราที่เลือก และฟอร์มมิเตอร์

นอกขอบเขต: เปลี่ยนการจัดเตียง/อนุมัติ/ข้อมูล production, ใบแจ้งหนี้หรือการรับเงิน, แบ่งค่าไฟรายคน, ใช้ราคารายเดือนอัตโนมัติ, เดาประเภทผู้พักหรือราคาไฟ, commit/push/PR/release โดย worker
