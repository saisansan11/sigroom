# แผนดำเนินงาน beta 8 PR

ฐานที่ตรวจแล้ว: `claude/online-classroom-planning-fc892e` ที่ `15ed031` ตรงกับ GitHub; base ปัจจุบัน `feat/lodging-v5-2` ที่ `06ac114` รวม PR #86 แล้ว เปิดอยู่เฉพาะ PR #82 ซึ่งอยู่นอกขอบเขตนี้

ใช้ worktree `F:/ogn_ROOM/.worktrees/online-beta` และ branch ตาม runbook ทีละ PR โดยไม่รอ merge ไม่ rebase และไม่ force push

1. PR-1 ตรวจงานเดิม เพิ่มสถานะวันซ้ำและคำอธิบายเวลา preset โดยคง Booking Core
2. PR-2 แยกเมนูจาก route และกรองหมวดบริการ รักษาสิทธิ์เดิม
3. PR-3 ใช้ partial บัตรร่วมกัน ตรวจสิทธิ์และ QR ไม่ใส่ข้อมูลส่วนตัว
4. PR-4 เพิ่มแจ้งเตือนสองรอบพร้อม constraint กันซ้ำ และคู่มือ Cloud เท่านั้น
5. PR-5 เพิ่ม push แบบปิดเมื่อไม่มี config ไม่ cache หน้าเว็บ
6. PR-6 เพิ่ม Google login และบัญชีนักเรียนสิทธิ์ต่ำสุด ตรวจ verified/domain/hd และรุ่นที่ QR กำหนด
7. PR-7 เพิ่มแดชบอร์ดและประมาณค่าใช้จ่าย Decimal พร้อมสิทธิ์ audit และควบคุม query
8. PR-8 เอฟเฟกต์หมึกเฉพาะหน้าที่อนุญาต ปิด motion และไม่หน่วง interaction

ทุกขั้นอ่าน source ที่เกี่ยวข้อง ตรวจ diff และ targeted tests ตามด้วย pytest ทั้งชุด, Django check, migration drift, Node interaction tests, diff check และ browser มือถือ 390px/คอม บันทึกหลักฐานจริงและผล CI ของแต่ละ PR

ไม่ทำ: merge PR, deploy, gcloud, เปลี่ยนข้อมูล production, ตั้งค่า secret/Cloud, แก้ PR #82, ลบหรือ skip test เดิม งานอื่นใน repo คงไว้

ความเสี่ยง: radio วันซ้ำต้องไม่ส่งค่าซ้ำ; redirect/สิทธิ์บัตร; งานแจ้งเตือนซ้ำ; OAuth ต้องไม่เพิ่มสิทธิ์นักเรียนและต้องไม่เชื่อ header; billing ยังเป็นประมาณการตามค่าตั้งต้นใน runbook ข้อสงสัยจะบันทึกใน PR ที่เกี่ยวข้อง

## คำอนุญาตล่าสุด 4 ต.ค. 2569

ผู้ใช้สั่งให้เปิด PR แล้ว merge และ deploy เมื่อปลอดภัย จากนั้นทำเฟสต่อไปจนครบทุก PR โดยอนุญาตงานที่ปลอดภัย คำสั่งนี้แทนข้อห้าม merge/deploy เดิม: ต้องตรวจ source, regression, browser QA และ CI ก่อน merge ทุกครั้ง แล้ว deploy จาก checkout สะอาดที่ตรงกับ SHA ที่ merge ผ่าน guard เดิม พร้อมบันทึก backup, revision เดิม, migration และ smoke check ไม่ force-push ไม่แตะ PR #82 และไม่ข้าม test หรือ guard

การปรับ assertion ที่ยังคาดข้อความหรือเมนูเก่าให้ตรวจพฤติกรรมใหม่ตามแผนอยู่ในขอบเขตที่อนุญาต โดยคงการตรวจสิทธิ์และเส้นทางเดิมที่ยังรองรับไว้ ระบุไฟล์และเหตุผลในแต่ละ PR
