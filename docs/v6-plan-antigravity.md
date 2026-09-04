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
6. **สิทธิ์ merge:** แม้ reviewer ผ่านแล้ว ต้องรอเจ้าของระบบสั่งชัดเจนว่า **"merge PR #..."**
   จึง merge ได้ — คำว่า "ตรวจรับ" หรือ "ผ่าน" เฉย ๆ **ไม่ใช่** คำอนุญาต merge
7. **PR ที่มี migration — ลำดับที่ปลอดภัยมีทางเดียว: migrate ก่อน deploy**

   ปัจจุบัน `cloudbuild.yaml` ทำ build → push → **deploy ทันที** และอ้าง tag `:latest`
   ทุกขั้น — ถ้าปล่อยไว้แล้ว merge PR ที่มี migration โค้ดใหม่จะขึ้นเว็บ**ก่อน** schema ใหม่
   แล้ว query คอลัมน์/ตารางที่ยังไม่มี (เช่น `checked_in_at` ของงาน B, ตาราง
   `ResourcePhoto` ของงาน C) → **เว็บพังชั่วคราวทุกครั้ง** จึงต้องแก้ pipeline ก่อน
   เริ่มงานที่มี migration ใด ๆ:

   **งาน B0 (`feat/v6-b0-pipeline` — PR เล็กแยกต่างหาก ต้อง merge ก่อนงาน B):**
   แก้ `cloudbuild.yaml` ให้เป็นลำดับนี้เท่านั้น
   1. build + push image โดย tag ด้วย `$COMMIT_SHA` (คง tag `latest` ควบคู่ได้
      แต่ขั้นที่ 2–3 ต้องอ้าง `$COMMIT_SHA` **เท่านั้น** — ห้ามอ้าง `:latest` เพราะถ้ามี
      build สองอันซ้อนกัน tag จะชี้ image ผิดตัว)
   2. update + execute + รอผล ใน**คำสั่งเดียว**:
      `gcloud run jobs update sigroom-migrate --image=...:$COMMIT_SHA --region=... --wait`
      — flag `--wait` มีผลเป็น "สั่ง execute ทันทีหลัง update แล้วรอจนจบ" (ตาม
      gcloud reference: `--wait` implies `--execute-now`) **ห้ามแยกเป็นคำสั่ง
      update หนึ่งคำสั่งแล้วตามด้วย execute อีกคำสั่ง** เพราะ job เป็น resource
      ที่ทุก build ใช้ร่วมกัน: ถ้า build อื่น update image คั่นกลางระหว่างสองคำสั่ง
      execute ของ build นี้จะรัน image ผิดตัวทันที — **ถ้า migrate ล้มเหลว
      build ทั้งอันต้อง fail และต้องไม่ไปถึงขั้น deploy** (Cloud Build หยุดเอง
      เมื่อ step ล้มเหลว — revision เดิมยังให้บริการตามปกติ ไม่มีช่วงเว็บพัง)
   3. deploy Cloud Run service `sigroom` ด้วย image `$COMMIT_SHA` **ตัวเดียวกับขั้น 2**

   หมายเหตุงาน B0:
   - รัน migrate ทุก build ได้ปลอดภัย — `manage.py migrate` เป็น no-op เมื่อไม่มี
     migration ใหม่ และสอดคล้องกับกติกา expand/contract (schema ใหม่ต้องไม่ทำให้
     โค้ดเก่าที่ยังรันอยู่พัง)
   - **กติกากันชนกันของ build (ตัดสินตามสถานะ build ล่าสุดของ production):**
     Cloud Run job เดียวกันรัน execution **พร้อมกันได้หลายชุด** — ห้ามคิดว่า job
     จะจัดคิว serialize ให้เอง ให้ดูสถานะ build ล่าสุดใน Cloud Build → History
     แล้วทำตามนี้:
     - build ยัง **RUNNING** → ห้าม merge/push ใด ๆ ที่ trigger build เพิ่ม รอให้จบก่อน
     - **SUCCESS** ครบทุกขั้น → ทำงานปกติ merge ชุดถัดไปได้
     - **FAILURE/CANCELLED** → บล็อกเฉพาะ **feature PR** แต่**อนุญาต recovery PR**
       (PR ที่แก้ pipeline/migration ให้ build กลับมาผ่าน) หรือการ rerun build
       ที่เจ้าของสั่งชัดเจน — ต้องมีข้อยกเว้นนี้ มิฉะนั้นกฎจะล็อกตัวเอง:
       ถ้า B0 ล้มเหลวเพราะ `cloudbuild.yaml` ผิด จะไม่มีทาง push ตัวแก้ได้เลย
     - กรณี **migrate สำเร็จแต่ขั้น deploy ล้มเหลว** → สั่ง deploy image SHA เดิมซ้ำ
       (หรือ rerun build เดิม) ได้อย่างปลอดภัย เพราะ schema แบบ expand ต้อง
       เข้ากันได้กับ revision เดิมที่ยังรันอยู่ (กติกา CLAUDE.md/NF-17) —
       migrate รอบ rerun เป็น no-op
     โปรเจกต์นี้เจ้าของเป็นคน merge ทีละ PR อยู่แล้ว (ข้อ 0.6) ·
     database advisory lock กันสอง migration รันพร้อมกันเป็นทางเลือกเสริมใน
     อนาคตถ้ามีผู้ merge หลายคน — ยังไม่บังคับตอนนี้
   - **ก่อนเริ่ม B0** ยืนยันกับเจ้าของระบบว่า job ยังมีอยู่จริงและต่อฐานข้อมูล production ได้
     (`gcloud run jobs describe sigroom-migrate --region=asia-southeast3 --project=sixth-storm-439008-u2`)
     — job นี้**อยู่นอก repository** (สร้างไว้ใน GCP project `sixth-storm-439008-u2`,
     region `asia-southeast3` เมื่อ 4 ก.ย. 69) ถ้าไม่มีให้แจ้งใน PR แทนการสร้างเอง
   - **ก่อน merge B0** ให้เจ้าของยืนยันว่า service account ของ Cloud Build มีสิทธิ์
     update/execute Cloud Run Job (ถ้ายังไม่มี Claude จะพาเพิ่ม role ตอนนั้น)
     และ**หลัง merge B0** ให้ดู Cloud Build → History ว่า build แรกผ่านครบทั้ง 3 ขั้น
     จึงถือว่า B0 เสร็จ

   **หลัง B0 merge แล้ว:** PR ที่มี migration ไม่ต้องรันคำสั่งมือใด ๆ — แค่ระบุใน
   PR description ให้ชัดว่า "มี migration" และหลัง merge ให้ตรวจใน Cloud Build → History
   ว่า build ของ commit นั้นผ่านครบทั้งขั้น migrate และขั้น deploy

   **คำสั่งมือ (fallback — ใช้เฉพาะกู้สถานการณ์เมื่อ pipeline พัง):** คำสั่งเดียวจบ
   (update + execute + รอผล — เหตุผลเดียวกับขั้นที่ 2 ของ B0: แยกสองคำสั่งจะเปิด
   ช่อง race) เป็นบรรทัดเดียวรันใน PowerShell ได้โดยตรง (ห้ามแตกหลายบรรทัดด้วย `\`
   — แบบนั้นใช้ได้เฉพาะ Cloud Shell/bash) และแทน `<COMMIT_SHA>` ด้วย SHA ของ
   commit ที่ build+push สำเร็จแล้วเท่านั้น — **ห้ามใช้ `:latest`**:
   ```
   gcloud run jobs update sigroom-migrate --region=asia-southeast3 --project=sixth-storm-439008-u2 --image=asia-southeast3-docker.pkg.dev/sixth-storm-439008-u2/sigroom-repo/sigroom:<COMMIT_SHA> --wait
   ```

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
  1. **"ดูห้องว่างตอนนี้"** → เลื่อนลงไปที่กระดานสถานะวันนี้ ด้วย anchor `#today-board`
     — **หมายเหตุ: ปัจจุบัน element กระดานมีแค่ `class="today-board"` ยังไม่มี id**
     ต้องเพิ่ม `id="today-board"` ให้ element นั้นด้วย และมี test ยืนยันว่า
     หน้าแรก render แล้วมีทั้งลิงก์ `href="#today-board"` และ element `id="today-board"` จริง
  2. **"จองห้องเรียน/ห้องประชุม"** → `/accounts/login/?next=/book/` พร้อมคำอธิบายสั้น "สำหรับ จนท. มีบัญชีหน่วย"
  3. **"จองที่พักนักเรียนหลักสูตร"** → `/lodging/` พร้อมคำอธิบาย "นักเรียนใช้ลิงก์ที่ได้จากกลุ่ม LINE ของรุ่น"
- ผู้ล็อกอินแล้ว: คงการ์ด action เดิม (คิวอนุมัติ/การใช้งานห้อง/จองด่วน) แต่เรียงตามเกณฑ์ชัดเจนนี้:
  1. การ์ดคิวอนุมัติ ถ้า `nav_pending_approval_count > 0`
  2. การ์ดการใช้งานห้อง ถ้า `usage_today_count > 0`
  3. การ์ดที่เหลือตามลำดับเดิม
  (การ์ดที่ตัวเลขเป็น 0 หรือ None คงอยู่ในหน้าแต่ต่อท้ายเสมอ — เกณฑ์ตัดสินใช้ตัวแปร context
  ที่มีอยู่แล้วเท่านั้น ห้าม query เพิ่มใน template)
- ห้ามลบข้อมูล/ฟีเจอร์ใดออกจากหน้า แค่จัดลำดับและเพิ่ม role router

### A2. หน้าเลือกเตียงนักเรียน (`/lodging/c/<slug>/` — `templates/lodging/student_portal.html`)

เส้นทางปัจจุบัน: เปิดลิงก์ → เลื่อนหาห้องที่ว่าง → กด "เลือกเตียงนี้" → กรอก 5 ช่อง → ยืนยัน (2 คลิก + ฟอร์ม — ดีอยู่แล้ว ปรับความชัด)

สิ่งที่ต้องทำ:
- เพิ่มปุ่มลอย (sticky ล่างจอ เฉพาะจอแคบ ≤768px) **"ไปที่เตียงว่างถัดไป ▾"** เลื่อนไปห้องแรกที่ยังมีเตียงว่าง — ห้ามใช้ JS framework ใช้ vanilla JS สั้น ๆ ได้
- ห้องที่เต็มแล้วให้จัดไป **ท้ายรายการ** (เรียงใน view: ห้องว่างก่อน ห้องเต็มทีหลัง — จัดใน `lodging_views.lodging_portal` ไม่ใช่ใน template)
- ในกล่อง modal ฟอร์ม: ช่องเบอร์โทรใส่ `inputmode="tel"`, ช่องชื่อ `autofocus`
- **error ตอนจอง (เบอร์ซ้ำ / เตียงถูกแย่งตัดหน้า / ข้อมูลไม่ผ่าน):** ต้องกลับมา**เปิด modal เดิม
  โดยอัตโนมัติ พร้อมห้อง/เตียงเดิมและค่าที่ผู้ใช้กรอกไว้** แล้วแสดงข้อความ error ในตัว modal
  — แค่ส่ง Django message แล้ว redirect กลับหน้าบน **ไม่ผ่านเกณฑ์** (ผู้ใช้ต้องไม่ต้องหา
  ห้อง/เตียงแล้วกรอกใหม่ทั้งหมด) วิธีทำ: view ส่ง context ระบุ error + ค่าที่กรอก แล้ว template
  เปิด dialog อัตโนมัติเมื่อมี error (`<script>` สั้น ๆ หรือ attribute `open`)
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
- **Keyboard accessibility:** ตัวการ์ดที่พลิกได้ต้องเป็น `<button>` (หรือมี `role="button"` +
  `tabindex="0"`) พลิกได้ด้วย Enter/Space, มี focus style มองเห็นชัด, และมี `aria-label`
  บอกว่ากดเพื่อพลิกดูด้านหลัง/หน้า
- รองรับ `prefers-reduced-motion` (ปิด animation อัตโนมัติ)
- ปุ่มใต้การ์ด: "บันทึกลงเครื่อง" (แนะนำ screenshot) และ "เปิดลิงก์รุ่น"

### B2. ระบบ check-in ด้วย QR
- เพิ่มฟิลด์ใหม่ใน `CourseStudentLodging`: `checked_in_at` (DateTimeField null=True blank=True) + `checked_in_by` (FK User null=True on_delete=SET_NULL) — migration แบบ expand
- QR บนบัตรชี้ไป URL ใหม่: `/lodging/checkin/<student_id>/` — **ต้องสร้าง URL ผ่าน
  `get_canonical_public_url()`** (มีอยู่แล้วใน `lodging_services.py`) เพื่อให้ QR ใช้โดเมน
  สาธารณะที่ถูกต้อง (`PUBLIC_BASE_URL`) ไม่ใช่ host ภายในของ Cloud Run
- หน้า check-in:
  - ผู้เปิดที่ **ไม่ได้ล็อกอิน/ไม่มีสิทธิ์**: เห็นเฉพาะสถานะ "บัตรถูกต้อง ✓ (ยศ-ชื่อ masked, ห้อง/เตียง)" — ใช้การ mask ชื่อแบบเดียวกับ `_masked_name` ที่มีอยู่
  - ผู้มีสิทธิ์ (superuser / staff / supervisor ของรุ่น — ใช้ `can_manage_cohort` เดิม): เห็นข้อมูลเต็ม + ปุ่ม **"ยืนยันรายงานตัว"** → บันทึก `checked_in_at`/`checked_in_by` — ถ้าเคยยืนยันแล้วให้แสดงเวลา (พ.ศ.) และผู้ยืนยัน ไม่ให้ยืนยันซ้ำ
- กฎธุรกิจ check-in อยู่ใน `lodging_services.py` (function ใหม่ เช่น `check_in_student(student, actor)`) พร้อม audit log แนวเดียวกับ `update_cohort_allocation`
- หน้า detail ของรุ่น (`cohort_detail`) เพิ่มคอลัมน์สถานะรายงานตัว (✓ + เวลา หรือ "-")

### B3. Acceptance criteria งาน B
- เปิดบัตรบนมือถือ: การ์ดแสดงเต็มจอพอดี พลิกหน้า-หลังได้ทั้งแตะและคีย์บอร์ด (Enter/Space)
- สแกน QR → เข้าหน้า check-in ตามสิทธิ์ที่ถูกต้อง ผ่านโดเมนสาธารณะ (canonical URL)
- `check_in_student()` ต้องกันการยืนยันซ้ำแบบพร้อมกัน (concurrent) ด้วย
  `select_for_update()` ภายใน `transaction.atomic` — ไม่ใช่แค่เช็ค if ธรรมดา
- test อย่างน้อย: (1) check_in_student สำเร็จ + บันทึกผู้ยืนยัน + audit,
  (2) **duplicate submission**: เรียก service ซ้ำหลังยืนยันแล้วต้องได้ ValidationError —
  test นี้ครอบเฉพาะการกดยืนยันซ้ำตามลำดับ **ไม่ใช่** การพิสูจน์การกันสองคำขอพร้อมกัน
  (การกัน concurrent เป็นหน้าที่ของ `select_for_update()` ตามข้อบังคับด้านบน —
  ไม่บังคับเขียน concurrent test ด้วย thread แต่ reviewer ต้องตรวจในโค้ดว่ามี
  `select_for_update()` ใน `transaction.atomic` จริง), (3) **POST ยืนยันโดยผู้ไม่มีสิทธิ์ต้องถูกปฏิเสธ (403)**
  ไม่ใช่แค่ซ่อนปุ่มใน template, (4) ผู้ไม่ล็อกอินเห็นชื่อแบบ masked เท่านั้น,
  (5) QR URL ขึ้นต้นด้วยค่า PUBLIC_BASE_URL เมื่อกำหนดไว้
- **PR นี้มี migration → ต้องรอให้งาน B0 (ข้อ 0.7) merge และผ่านการทดสอบก่อน** —
  ระบุใน PR ว่ามี migration และหลัง merge ตรวจ Cloud Build → History ว่า build
  ผ่านครบขั้น migrate และ deploy (pipeline จัดลำดับ migrate ก่อน deploy ให้เอง)

---

## งาน C — รูปห้องแบบเว็บโรงแรม (`feat/v6-c-photos`)

**เป้าหมาย:** ทุกห้องมีรูปประกอบ นำเสนอแบบเว็บจองโรงแรม คนจองเห็นแล้วว้าว

> ⚠️ งานนี้มี **งาน infra ที่ผู้ใช้ต้องทำเองก่อน** (สร้าง GCS bucket + ให้สิทธิ์) —
> Antigravity เขียนโค้ดให้เสร็จได้เลยโดยใช้ env var ชี้ bucket แต่ห้าม hardcode ชื่อ bucket

### C1. โครงสร้างเก็บรูป
- Cloud Run เก็บไฟล์บนเครื่องไม่ได้ (ดิสก์หายเมื่อ restart) → ใช้ **Google Cloud Storage**
- เพิ่ม dependency: `django-storages[google]`
- ตั้งค่าใน `settings.py` แยก **3 กรณี** ให้ชัด:
  1. **มี env `GS_BUCKET_NAME`** → ใช้ GCS เป็น storage ของ media โดย**ต้องตั้ง**
     `GS_DEFAULT_ACL = None` (bucket ใช้ uniform bucket-level access ตาม C5 —
     ห้ามส่ง ACL รายไฟล์ มิฉะนั้นอัปโหลดจะ error), `GS_QUERYSTRING_AUTH = False`
     (เสิร์ฟ URL สาธารณะตรง ๆ — ค่า default ที่สร้าง signed URL จะล้มเหลวบน Cloud Run
     เพราะ service account ไม่มี private key ในเครื่อง) และ `GS_FILE_OVERWRITE = False`
     (ค่า default ของ django-storages คือ**เขียนทับไฟล์ชื่อซ้ำทันทีโดยไม่เตือน** —
     ต่างจาก FileSystemStorage ของ Django ที่ตั้งชื่อใหม่ให้เอง) · การเปิดให้ browser
     ของ guest อ่าน bucket ได้จริงเป็นงาน infra ตามเช็กลิสต์ C5
  2. **ไม่มี env และ `DEBUG=True`** (dev ในเครื่อง) → FileSystemStorage เดิม ครบวงจร
  3. **ไม่มี env และ `DEBUG=False`** (production ที่ infra ยังไม่พร้อม) → **ปิดการอัปโหลดรูป**:
     กำหนด flag เดียวใน settings เช่น `ROOM_PHOTO_UPLOAD_ENABLED` แล้วให้ admin/service
     อ่าน flag นี้ (ห้ามกระจายเงื่อนไข DEBUG/env ไปหลายที่) — admin ซ่อนช่องอัปโหลด
     และแสดงข้อความไทยแทน เช่น "ยังไม่ได้ตั้งค่าที่เก็บรูป (GS_BUCKET_NAME) —
     อัปโหลดได้เมื่อตั้งค่าตาม C5 แล้ว" **ห้ามปล่อยให้รูปตกลง FileSystemStorage
     บน Cloud Run เด็ดขาด** เพราะไฟล์จะหายเมื่อ restart โดยผู้ใช้ไม่รู้ตัว
- `.env.example` เพิ่ม `GS_BUCKET_NAME=` พร้อมคอมเมนต์อธิบาย

### C2. Model
- Model ใหม่ `ResourcePhoto` ใน `resources/models.py`:
  `resource` (FK Resource, related_name="photos", `limit_choices_to={"resource_type": Resource.Type.ROOM}`),
  `image` (ImageField — `upload_to` ต้องเป็น **function ที่ตั้งชื่อไฟล์ใหม่เป็น UUID**
  เช่น `rooms/<uuid4>.<นามสกุลเดิม>` ห้ามใช้ชื่อไฟล์เดิมจากผู้ใช้ — กันชื่อซ้ำเขียนทับ
  (คู่กับ `GS_FILE_OVERWRITE=False` ใน C1) และเลี่ยงปัญหาชื่อไฟล์ภาษาไทย/อักขระพิเศษ),
  `caption` (CharField blank),
  `order` (PositiveSmallIntegerField default 0), `is_cover` (Boolean default False)
- เพิ่ม dependency `Pillow`
- Admin: inline ใน ResourceAdmin อัปโหลดได้หลายรูป จัด order ได้
- **กฎ cover บังคับที่ระดับฐานข้อมูล** (ตามหลักเดียวกับกติกา CLAUDE.md ข้อ 1):
  partial unique constraint —
  `UniqueConstraint(fields=["resource"], condition=Q(is_cover=True), name="unique_cover_photo_per_resource")`
  — `clean()` ใช้แค่แปลง error เป็นข้อความไทยที่อ่านรู้เรื่อง ห้ามเป็นกลไกบังคับเพียงชั้นเดียว
- **ทุกช่องทางสร้าง/แก้ไข/ลบ `ResourcePhoto` ต้องผ่าน service** ใน `resources/services.py`
  (เช่น `save_room_photo(...)`) ซึ่งเรียก `full_clean()` เสมอก่อนบันทึก — เหตุผล:
  `limit_choices_to` คุมแค่ฟอร์ม admin และ `clean()` **ไม่ถูกเรียกอัตโนมัติ** เมื่อโค้ด
  สร้างตรงด้วย `.objects.create()` ดังนั้น service คือด่านบังคับกฎด่านเดียวที่ครอบ
  ทุกช่องทาง (ตามกติกา CLAUDE.md ข้อ 3) · admin inline ต้อง save ผ่าน service นี้ด้วย
  (override การ save ของ inline/formset) และ test ที่สร้างรูปทุกตัวต้องสร้างผ่าน service เช่นกัน
  — **ยกเว้นข้อเดียว:** test ที่พิสูจน์ constraint ระดับฐานข้อมูลโดยเฉพาะ (เช่น cover
  ตัวที่สองต้องโดน `IntegrityError`) ให้สร้างตรงผ่าน ORM (`.objects.create()`) ได้
  เพราะ service เรียก `full_clean()` ซึ่งจะหยุดด้วย `ValidationError` ก่อนถึงฐานข้อมูล
  — ด่าน DB ต้องพิสูจน์แบบข้าม service เท่านั้นจึงจะรู้ว่าทำงานจริง
- **การลบรูปต้องลบไฟล์จริงใน storage ด้วย:** Django ลบแถวใน DB แล้ว**ไม่ลบไฟล์
  อัตโนมัติ** → service ลบ (เช่น `delete_room_photo(...)`) ต้องลบไฟล์ออกจาก storage
  ผ่าน `transaction.on_commit(...)` หลังลบแถวสำเร็จเท่านั้น (กันกรณี transaction
  rollback แล้วไฟล์หายทั้งที่แถวยังอยู่) · กรณีแก้ไขแทนที่รูปเดิม ให้ลบไฟล์เก่าแบบเดียวกัน
  · การลบผ่าน admin (รวม inline) ต้องวิ่งผ่าน service นี้ด้วย
  · **ตัว callback ใน `on_commit` ต้อง best-effort เสมอ:** ครอบการลบไฟล์ด้วย
  try/except แล้ว log — เพราะ callback ทำงาน**หลัง** transaction commit สำเร็จแล้ว
  (นอก transaction) ถ้า storage มีปัญหาตอนนั้น ห้ามให้ error โผล่ถึงผู้ใช้
  ทั้งที่ข้อมูลบันทึก/ลบสำเร็จไปแล้ว
- **ฝั่งอัปโหลดก็มีช่องไฟล์กำพร้า:** ตอน save ไฟล์ใหม่ถูกเขียนลง storage **ก่อน**
  แถว DB จะบันทึกสำเร็จ — ถ้าขั้นบันทึกแถว DB ล้มเหลว**หลังไฟล์ถูกเขียนแล้ว**
  (เช่น DB ล่ม, IntegrityError จากช่องทางที่หลุด full_clean) ไฟล์ใหม่จะค้างอยู่ใน
  storage → service create/update ต้องครอบด้วย try/except แล้ว**ลบไฟล์ใหม่
  แบบ best-effort เมื่อ transaction ล้มเหลว** (ถ้าลบไม่สำเร็จไม่ต้อง raise ซ้ำ —
  บันทึก log พอ แล้วปล่อย error เดิมของ transaction ขึ้นไปตามปกติ)
  หมายเหตุ: กรณีชน validation ผ่าน service ปกติ `full_clean()` จะดักก่อนไฟล์ถูกเขียน
  — ช่องนี้จึงเป็นเรื่องของความล้มเหลว**หลัง**จุดเขียนไฟล์เท่านั้น (ดูวิธี test ใน C4)
- `clean()` ต้องตรวจด้วยว่า resource เป็นประเภทห้อง (ROOM) พร้อมข้อความไทย
- **Validation ไฟล์รูป:** จำกัดชนิด (JPEG/PNG/WebP) และขนาด ≤ 5MB — ตรวจใน `clean()`/validator
  ของ field พร้อมข้อความไทย + test ไฟล์ผิดชนิดและไฟล์ใหญ่เกิน

### C3. UI
- **หน้าเลือกเตียงนักเรียน** (student_portal): การ์ดห้องแสดงรูป cover ด้านบนการ์ด อัตราส่วน 16:9,
  กดรูปเปิดแกลเลอรีดูรูปทั้งหมดของห้อง (ใช้ `<dialog>` + ปุ่มเลื่อนซ้ายขวา vanilla JS)
- **หน้าแรก + หน้าจองห้องปกติ** (book_search): การ์ด/แถวห้องแสดงรูป cover ขนาดย่อ
- ห้องที่ไม่มีรูป: placeholder SVG สวยงามโทนเดียวกับธีม (สร้างเป็น static asset ไม่ใช่ external URL)
- รูปใส่ `loading="lazy"` ทุกจุด
- **ป้องกัน N+1 query:** ทุก view ที่แสดงหลายห้องพร้อมรูป ต้อง `prefetch_related("photos")`
  (หรือ `Prefetch` เฉพาะ cover) — เพิ่ม test ยืนยันจำนวน query คงที่ด้วย
  `django.test.utils.CaptureQueriesContext` หรือ `assertNumQueries`

### C4. Acceptance criteria งาน C — แบ่งเป็น 2 ประตูชัดเจน

**ประตูที่ 1 — โค้ดเสร็จ (Antigravity ทำได้ทันที ไม่ต้องรอ infra):**
- dev ในเครื่อง (ไม่มี `GS_BUCKET_NAME`) ทำงานครบวงจรด้วย FileSystemStorage:
  อัปโหลดผ่าน admin → แสดงบนหน้าเว็บ
- ห้องไม่มีรูปแสดง placeholder ไม่ layout พัง
- test: constraint cover เดียว (ระดับ DB — ทดสอบว่าแถวที่สองที่ is_cover=True โดน IntegrityError
  — **test ข้อนี้สร้างตรงผ่าน ORM ข้าม service** ตามข้อยกเว้นใน C2),
  resource ต้องเป็นห้อง, validation ชนิด/ขนาดไฟล์,
  อัปโหลดสองไฟล์ที่ชื่อไฟล์ต้นทางเหมือนกันแล้วได้ path ต่างกัน (รูปแรกไม่ถูกทับ),
  **ชุด test ไฟล์กำพร้า 4 กรณี:** (ก) ลบรูปแล้วไฟล์ใน storage ถูกลบด้วย,
  (ข) create/update ล้มเหลวต้องไม่ทิ้งไฟล์ใหม่ค้าง — **ต้องจำลอง exception
  หลังไฟล์ถูกเขียนลง storage แล้วแต่ก่อน DB commit** (เช่น mock ให้ขั้นบันทึก
  แถว DB ล้มเหลว) **ห้ามใช้แค่กรณีชน validation/constraint ผ่าน service**
  เพราะ `full_clean()` จะดักก่อนไฟล์ถูกเขียน — test จะผ่านโดยไม่เคยทดสอบ
  cleanup จริง · ยืนยันทั้งสองอย่าง: ไฟล์ใหม่ถูกลบ **และ** exception ต้นฉบับ
  ยังถูกส่งกลับ (cleanup ห้ามกลืน error),
  (ค) แทนที่รูปสำเร็จแล้วไฟล์เก่าหายแต่ไฟล์ใหม่ยังอยู่,
  (ง) callback ลบไฟล์เจอ storage error (จำลอง `storage.delete` พัง) →
  แค่ log, flow หลักที่ commit สำเร็จแล้วต้องไม่ล้มเหลวให้ผู้ใช้เห็น
  — test ที่ตรวจผลของ `transaction.on_commit` ต้องใช้
  `captureOnCommitCallbacks(execute=True)` หรือ `TransactionTestCase`
  เพราะ callback ทำงานหลัง commit จริงเท่านั้น (`TestCase` ปกติ rollback ไม่เคย commit),
  หน้า render ทั้งมีรูป/ไม่มีรูป,
  จำนวน query คงที่ (N+1), **flag ปิดอัปโหลด** (จำลอง `DEBUG=False` + ไม่มี
  `GS_BUCKET_NAME` แล้ว flag ต้องปิด / admin ไม่แสดงช่องอัปโหลด) — ทั้งหมดใช้ temp storage ใน test
- PR ผ่านการตรวจได้ด้วยประตูที่ 1 เท่านั้น **การ merge ยังไม่ต้องรอ infra** —
  ปลอดภัยเพราะกรณีที่ 3 ของ C1 ปิดการอัปโหลดบน production ไว้จนกว่า infra จะพร้อม
  (ไม่มีช่องให้รูปตกลงดิสก์ชั่วคราวของ Cloud Run)

**ประตูที่ 2 — ยืนยันบน production (หลัง merge + infra พร้อม):**
- ลำดับตายตัว (ลำดับเดียวกับ "ลำดับการทำและการส่งมอบ" ข้อ 4 — ห้ามสลับ):
  เจ้าของสั่ง merge → pipeline รันเองครบสามขั้น (build → migrate → deploy —
  ตรวจ Cloud Build → History ว่าผ่านครบ ตามข้อ 0.7) → ผู้ใช้ทำ C5 เสร็จ
  (bucket + IAM + env) → อัปโหลดรูปจริงผ่าน admin production → รูปขึ้น GCS →
  แสดงบนเว็บจริง — ขั้นนี้เป็นเงื่อนไข "ปิดงาน C" ไม่ใช่เงื่อนไข merge
- **PR นี้มี migration → ต้องรอให้งาน B0 (ข้อ 0.7) merge และผ่านการทดสอบก่อน** —
  ระบุใน PR ว่ามี migration และหลัง merge ตรวจ Cloud Build → History ว่าผ่านครบ

### C5. งานฝั่งผู้ใช้ (Claude จะพาไปทำตอนถึงประตูที่ 2)

เช็กลิสต์ infra **ครบทุกข้อ** — ขาดข้อใดข้อหนึ่ง guest จะเปิดรูปไม่ได้ (403) หรืออัปโหลดพัง:
1. สร้าง bucket ใน project `sixth-storm-439008-u2` แบบ **Uniform bucket-level access**
   (ไม่ใช้ ACL รายไฟล์ — สอดคล้องกับ `GS_DEFAULT_ACL=None` ฝั่งโค้ดใน C1)
2. **ปิด Public Access Prevention** ของ bucket นี้ — รูปห้องตั้งใจเปิดสาธารณะ
   ดังนั้น **ห้ามเก็บไฟล์ประเภทอื่นใน bucket นี้เด็ดขาด** (รูปห้องเท่านั้น)
3. ให้สิทธิ์ `allUsers` เป็น **Storage Object Viewer** บน bucket →
   browser ของ guest อ่านรูปผ่าน URL สาธารณะได้ตรง ๆ (คู่กับ `GS_QUERYSTRING_AUTH=False`)
4. ให้สิทธิ์ `sigroom-run-sa` เป็น **Storage Object Admin** บน bucket (อัปโหลด/ลบรูปจาก admin)
5. ตั้ง env `GS_BUCKET_NAME=<ชื่อ bucket>` บน Cloud Run service `sigroom`
   (การแก้ env จะสร้าง revision ใหม่อัตโนมัติ — flag อัปโหลดใน C1 จะเปิดเอง)

---

## ลำดับการทำและการส่งมอบ

(ทุกขั้น "merge" หมายถึง: เจ้าของระบบสั่ง "merge PR #..." อย่างชัดเจนแล้วเท่านั้น — ตามข้อ 0.6)

1. งาน A → PR → Claude ตรวจ → เจ้าของสั่ง merge → ตรวจผลบนเว็บจริง (ไม่มี migration)
2. งาน B0 (แก้ `cloudbuild.yaml` ให้ migrate ก่อน deploy — ข้อ 0.7) → ยืนยัน job `sigroom-migrate` ยังอยู่จริง + Cloud Build SA มีสิทธิ์จัดการ job ก่อนเริ่ม → PR → ตรวจ → เจ้าของสั่ง merge → ดู Cloud Build history ว่า build แรกผ่านครบ 3 ขั้นจึงถือว่าเสร็จ
3. งาน B → PR → ตรวจ → เจ้าของสั่ง merge → ตรวจ Cloud Build history ว่าขั้น migrate + deploy ผ่าน (pipeline รันให้เอง)
4. งาน C → PR → ตรวจ (ประตูที่ 1) → เจ้าของสั่ง merge → ตรวจ Cloud Build history ว่าขั้น migrate + deploy ผ่าน → ผู้ใช้ทำ infra ตาม C5 → ยืนยันประตูที่ 2 จึงปิดงาน

ห้ามเริ่มงานถัดไปก่อนงานปัจจุบันถูก merge ถ้าติดคำถามเชิงออกแบบ ให้ถามในตัว PR
แทนการตัดสินใจเอง
