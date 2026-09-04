# แผนพัฒนา V6 — UX 3 คลิก · Key Card 3D · รูปห้องแบบโรงแรม

เอกสารนี้เป็น **แผนงานสำหรับ agent ผู้พัฒนา (Antigravity)** โดยมี **Claude เป็นผู้ตรวจรับ (reviewer)**
และผู้ใช้ (เจ้าของระบบ) เป็นผู้อนุมัติขั้นสุดท้าย — ทำทีละงาน **ห้ามข้ามลำดับ ห้ามรวบหลายงานใน PR เดียว**

## 0. กติกา workflow (บังคับทุกงาน — ความปลอดภัยหลายขั้น)

Branch `feat/lodging-v5-2` คือ **branch production**: ทุก commit ที่เข้า branch นี้จะถูก
Cloud Build **build + deploy ขึ้นเว็บจริงอัตโนมัติทันที** (trigger `auto-deploy-sigroom`)
ดังนั้น:

1. **ห้าม push ตรงเข้า `feat/lodging-v5-2` เด็ดขาด** ไม่ว่ากรณีใด
2. พัฒนาบน branch แยกตามงาน ตั้งชื่อ `feat/v6-<รหัสงาน>` เช่น `feat/v6-a-3click`
3. ก่อนเปิด PR ต้องผ่านครบ:
   - `uv run pytest` ผ่าน **ทุก** test (ของเดิม + ที่เพิ่มใหม่)
   - `uv run manage.py check` ไม่มี issue
   - `uv run manage.py makemigrations --check --dry-run` ไม่มี migration ตกค้าง
4. เปิด PR เข้า `feat/lodging-v5-2` อธิบาย: ทำอะไร ทำไม ทดสอบอย่างไร มี migration ไหม
   ถ้ามีการเปลี่ยนหน้าจอ ให้แนบภาพหรือคำอธิบายหน้าจอใน PR ด้วย
5. **Claude ตรวจ PR** — ถ้ามี finding ให้แก้ตามแล้ว push เพิ่มใน branch เดิมจนผ่าน
6. ผู้ใช้ยืนยัน "ตรวจรับ" → จึง merge (Claude เป็นผู้ merge)
7. **PR ที่มี migration**: หลัง merge ต้องรัน job migrate บน production หนึ่งครั้ง
   (`gcloud run jobs execute sigroom-migrate --region=asia-southeast3 --wait`)
   — ระบุคำเตือนนี้ให้ชัดใน PR description ทุกครั้งที่มีไฟล์ migration ใหม่

กติกาโค้ดเดิมใน `CLAUDE.md` มีผลทุกข้อ โดยเฉพาะ:
- กฎธุรกิจอยู่ใน `services.py` เท่านั้น ไม่อยู่ใน view/template/admin form
- ข้อความที่ผู้ใช้เห็นเป็นภาษาไทย วันที่แสดง พ.ศ. (มี template filter `thai_date` อยู่แล้ว)
- schema เปลี่ยนผ่าน `makemigrations` แบบ expand/contract เท่านั้น
- ห้าม secret ในโค้ด
- ทุกกฎที่เพิ่มต้องมี test

---

## งาน A — เส้นทางใช้งานจบใน ≤3 คลิก (`feat/v6-a-3click`)

**เป้าหมาย:** ผู้ใช้เปิดลิงก์แล้วรู้ทันทีว่าตัวเองต้องกดอะไร และงานหลักจบได้ไม่เกิน 3 คลิก
(ไม่นับการพิมพ์กรอกฟอร์ม)

### A1. หน้าแรก (`/` — `templates/bookings/calendar.html`)

สภาพปัจจุบัน: มีข้อมูลครบแต่ guest ไม่รู้ว่าต้องไปทางไหน ปุ่มหลักจมอยู่กลางหน้า

สิ่งที่ต้องทำ:
- เพิ่ม **แถบทางเลือกตามบทบาท (role router)** ไว้บนสุดใต้ hero เฉพาะผู้ที่ **ยังไม่ล็อกอิน**:
  การ์ดใหญ่ 3 ใบ กดได้ทั้งใบ เรียงแนวนอน (มือถือเรียงลง):
  1. **"ดูห้องว่างตอนนี้"** → เลื่อนลงไปที่กระดานสถานะวันนี้ (anchor `#today-board`)
  2. **"จองห้องเรียน/ห้องประชุม"** → `/accounts/login/?next=/book/` พร้อมคำอธิบายสั้น "สำหรับ จนท. มีบัญชีหน่วย"
  3. **"จองที่พักนักเรียนหลักสูตร"** → `/lodging/` พร้อมคำอธิบาย "นักเรียนใช้ลิงก์ที่ได้จากกลุ่ม LINE ของรุ่น"
- ผู้ล็อกอินแล้ว: คงการ์ด action เดิม (คิวอนุมัติ/การใช้งานห้อง/จองด่วน) แต่เรียงการ์ดที่มีงานค้าง (ตัวเลข > 0) ขึ้นก่อนเสมอ
- ห้ามลบข้อมูล/ฟีเจอร์ใดออกจากหน้า แค่จัดลำดับและเพิ่ม role router

### A2. หน้าเลือกเตียงนักเรียน (`/lodging/c/<slug>/` — `templates/lodging/student_portal.html`)

เส้นทางปัจจุบัน: เปิดลิงก์ → เลื่อนหาห้องที่ว่าง → กด "เลือกเตียงนี้" → กรอก 5 ช่อง → ยืนยัน (2 คลิก + ฟอร์ม — ดีอยู่แล้ว ปรับความชัด)

สิ่งที่ต้องทำ:
- เพิ่มปุ่มลอย (sticky ล่างจอ เฉพาะจอแคบ ≤768px) **"ไปที่เตียงว่างถัดไป ▾"** เลื่อนไปห้องแรกที่ยังมีเตียงว่าง — ห้ามใช้ JS framework ใช้ vanilla JS สั้น ๆ ได้
- ห้องที่เต็มแล้วให้จัดไป **ท้ายรายการ** (เรียงใน view: ห้องว่างก่อน ห้องเต็มทีหลัง — จัดใน `lodging_views.lodging_portal` ไม่ใช่ใน template)
- ในกล่อง modal ฟอร์ม: ช่องเบอร์โทรใส่ `inputmode="tel"`, ช่องชื่อ `autofocus`, และแสดงข้อความ error จอง (เช่น เบอร์ซ้ำ/เตียงถูกแย่ง) ใน modal เดิมไม่ใช่ให้เด้งกลับหน้าบน
- หลังจองสำเร็จ redirect ไปหน้าบัตร pass ทันที (ตรวจว่าปัจจุบันทำแล้วหรือยัง ถ้าแล้วคงไว้)

### A3. Acceptance criteria งาน A
- Guest เปิด `/` แล้วเห็นการ์ด 3 ทางเลือกโดยไม่ต้องเลื่อนจอ (บนจอมือถือ 390px เห็นการ์ดแรกเต็มใบ)
- นักเรียนเปิดลิงก์รุ่น → กดปุ่มไปเตียงว่าง → กดเลือกเตียง → กรอก → ยืนยัน = 3 คลิก + ฟอร์ม
- test อย่างน้อย: (1) หน้าแรก guest render มีการ์ด 3 ใบ / ผู้ล็อกอินไม่เห็น role router, (2) ลำดับห้องใน lodging portal ห้องว่างมาก่อนห้องเต็ม, (3) test เดิมทั้งหมดยังผ่าน

---

## งาน B — Key Card 3D + QR check-in (`feat/v6-b-keycard`)

**เป้าหมาย:** จองเสร็จได้บัตรดิจิทัลแบบการ์ด 3D หมุนได้ มี QR ให้เวรสแกนตอนเข้าพักจริง

### B1. ปรับหน้าบัตร (`/lodging/c/<slug>/pass/<student_id>/` — `templates/lodging/student_pass.html`)
- ทำเป็นการ์ดสไตล์ key card โรงแรม ขนาดเท่าบัตรเครดิตแนวนอน กลางจอ:
  - **ด้านหน้า:** โลโก้/ชื่อ SIGROOM + รร.ส.สส., ยศ-ชื่อ, ห้อง + หมายเลขเตียง (ตัวใหญ่), ชื่อรุ่น, ช่วงวันที่เข้าพัก (พ.ศ.)
  - **ด้านหลัง:** QR code (มี endpoint สร้าง QR SVG อยู่แล้ว ใช้แนวเดียวกัน), ข้อความ "แสดงบัตรนี้ต่อเวรรับรายงานตัว"
- **การหมุน:** CSS 3D ล้วน (`perspective` + `transform: rotateY`) — แตะ/คลิกการ์ดเพื่อพลิกหน้า-หลัง และมี animation ลอยเอียงเล็กน้อยตลอดเวลา (`@keyframes` เอียง ±6°) ให้ดูมีมิติ **ห้ามใช้ไลบรารี JS 3D**
- รองรับ `prefers-reduced-motion` (ปิด animation อัตโนมัติ)
- ปุ่มใต้การ์ด: "บันทึกลงเครื่อง" (แนะนำ screenshot) และ "เปิดลิงก์รุ่น"

### B2. ระบบ check-in ด้วย QR
- เพิ่มฟิลด์ใหม่ใน `CourseStudentLodging`: `checked_in_at` (DateTimeField null=True blank=True) + `checked_in_by` (FK User null=True on_delete=SET_NULL) — migration แบบ expand
- QR บนบัตรชี้ไป URL ใหม่: `/lodging/checkin/<student_id>/`
- หน้า check-in:
  - ผู้เปิดที่ **ไม่ได้ล็อกอิน/ไม่มีสิทธิ์**: เห็นเฉพาะสถานะ "บัตรถูกต้อง ✓ (ยศ-ชื่อ masked, ห้อง/เตียง)" — ใช้การ mask ชื่อแบบเดียวกับ `_masked_name` ที่มีอยู่
  - ผู้มีสิทธิ์ (superuser / staff / supervisor ของรุ่น — ใช้ `can_manage_cohort` เดิม): เห็นข้อมูลเต็ม + ปุ่ม **"ยืนยันรายงานตัว"** → บันทึก `checked_in_at`/`checked_in_by` — ถ้าเคยยืนยันแล้วให้แสดงเวลา (พ.ศ.) และผู้ยืนยัน ไม่ให้ยืนยันซ้ำ
- กฎธุรกิจ check-in อยู่ใน `lodging_services.py` (function ใหม่ เช่น `check_in_student(student, actor)`) พร้อม audit log แนวเดียวกับ `update_cohort_allocation`
- หน้า detail ของรุ่น (`cohort_detail`) เพิ่มคอลัมน์สถานะรายงานตัว (✓ + เวลา หรือ "-")

### B3. Acceptance criteria งาน B
- เปิดบัตรบนมือถือ: การ์ดแสดงเต็มจอพอดี พลิกหน้า-หลังได้ด้วยการแตะ
- สแกน QR → เข้าหน้า check-in ตามสิทธิ์ที่ถูกต้อง
- test อย่างน้อย: (1) check_in_student สำเร็จ + บันทึกผู้ยืนยัน, (2) ยืนยันซ้ำถูกปฏิเสธ, (3) ผู้ไม่มีสิทธิ์กดยืนยันไม่ได้ (403/ไม่มีปุ่ม), (4) ผู้ไม่ล็อกอินเห็นชื่อแบบ masked เท่านั้น
- **PR นี้มี migration → ระบุใน PR ให้รัน `sigroom-migrate` หลัง merge**

---

## งาน C — รูปห้องแบบเว็บโรงแรม (`feat/v6-c-photos`)

**เป้าหมาย:** ทุกห้องมีรูปประกอบ นำเสนอแบบเว็บจองโรงแรม คนจองเห็นแล้วว้าว

> ⚠️ งานนี้มี **งาน infra ที่ผู้ใช้ต้องทำเองก่อน** (สร้าง GCS bucket + ให้สิทธิ์) —
> Antigravity เขียนโค้ดให้เสร็จได้เลยโดยใช้ env var ชี้ bucket แต่ห้าม hardcode ชื่อ bucket

### C1. โครงสร้างเก็บรูป
- Cloud Run เก็บไฟล์บนเครื่องไม่ได้ (ดิสก์หายเมื่อ restart) → ใช้ **Google Cloud Storage**
- เพิ่ม dependency: `django-storages[google]`
- ตั้งค่าใน `settings.py`: ถ้ามี env `GS_BUCKET_NAME` → ใช้ GCS เป็น default storage ของ media
  (public-read สำหรับรูปห้อง — ไม่ใช่ข้อมูลลับ) · ไม่มี env → ใช้ FileSystemStorage เดิม (dev ในเครื่อง)
- `.env.example` เพิ่ม `GS_BUCKET_NAME=` พร้อมคอมเมนต์อธิบาย

### C2. Model
- Model ใหม่ `ResourcePhoto` ใน `resources/models.py`:
  `resource` (FK Resource, related_name="photos"), `image` (ImageField upload_to="rooms/"),
  `caption` (CharField blank), `order` (PositiveSmallIntegerField default 0), `is_cover` (Boolean default False)
- เพิ่ม dependency `Pillow`
- Admin: inline ใน ResourceAdmin อัปโหลดได้หลายรูป จัด order ได้
- Constraint/กฎ: cover ได้ห้องละ 1 รูป (บังคับใน `resources/services.py` หรือ clean) + test

### C3. UI
- **หน้าเลือกเตียงนักเรียน** (student_portal): การ์ดห้องแสดงรูป cover ด้านบนการ์ด อัตราส่วน 16:9,
  กดรูปเปิดแกลเลอรีดูรูปทั้งหมดของห้อง (ใช้ `<dialog>` + ปุ่มเลื่อนซ้ายขวา vanilla JS)
- **หน้าแรก + หน้าจองห้องปกติ** (book_search): การ์ด/แถวห้องแสดงรูป cover ขนาดย่อ
- ห้องที่ไม่มีรูป: placeholder SVG สวยงามโทนเดียวกับธีม (สร้างเป็น static asset ไม่ใช่ external URL)
- รูปใส่ `loading="lazy"` ทุกจุด

### C4. Acceptance criteria งาน C
- อัปโหลดรูปผ่าน admin → รูปขึ้น GCS → แสดงบนหน้าเว็บทันที
- ห้องไม่มีรูปแสดง placeholder ไม่ layout พัง
- dev ในเครื่อง (ไม่มี GS_BUCKET_NAME) ยังทำงานได้ด้วย FileSystemStorage
- test: model + กฎ cover เดียว + หน้า render ทั้งมีรูป/ไม่มีรูป (ใช้ temp storage ใน test)
- **PR นี้มี migration → รัน `sigroom-migrate` หลัง merge** และผู้ใช้ต้องเพิ่ม env `GS_BUCKET_NAME` ใน Cloud Run ก่อนใช้จริง

### C5. งานฝั่งผู้ใช้ (Claude จะพาไปทำตอน merge งาน C)
- สร้าง bucket + ให้สิทธิ์ `sigroom-run-sa` เขียน/อ่าน + ตั้ง env `GS_BUCKET_NAME` บน Cloud Run

---

## ลำดับการทำและการส่งมอบ

1. งาน A → PR → Claude ตรวจ → ผู้ใช้ตรวจรับบนเว็บจริง → merge (ไม่มี migration)
2. งาน B → PR → ตรวจ → merge → รัน `sigroom-migrate`
3. งาน C → PR → ตรวจ → ผู้ใช้ทำ infra ตาม C5 → merge → รัน `sigroom-migrate`

ห้ามเริ่มงานถัดไปก่อนงานปัจจุบันถูก merge ถ้าติดคำถามเชิงออกแบบ ให้ถามในตัว PR
แทนการตัดสินใจเอง
