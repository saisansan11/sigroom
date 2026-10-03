# PR-B: ธีม A + กลิ่นสำนักงานไทยยุค 90 และบัตรเข้าพักตลับเทป 3D

เขียน 3 ต.ค. 2569 · ผู้ทำ: Codex · ผู้ตรวจ: Claude
**ต่อยอดจาก PR-A** (`docs/plans/2026-10-03-pr-a-task-first-booking.md`) เพราะ PR นี้ตกแต่งหน้าที่ PR-A สร้าง ทำแบบ stacked branch ตาม `docs/plans/2026-10-03-codex-runbook.md`

ผู้ใช้อนุมัติแล้ว:
- แนวทาง "สำนักงานไทยยุค 90"
- สีตลับเทปดำเทา
- คำบนตรายาง "จองแล้ว"

ถ้าเจอสิ่งที่ขัดกับแผน ให้เขียนไว้ในหัวข้อ "ข้อสงสัย" ของ PR ห้ามตัดสินใจเอง

## 0. อ่านก่อนเริ่ม
1. `CLAUDE.md`
2. `docs/theme-a-ledger.md` (สี ฟอนต์ สถานะ และข้อห้าม)
3. **ต้นแบบที่ผู้ใช้อนุมัติ:** `docs/mockups/lodging-cassette-pass-mockup.html` (branch `claude/cassette-pass-mockup`)
   - เปิดดูใน Chrome แล้วลากและแตะเล่นก่อนเริ่มเขียน
   - ของจริงต้องหน้าตาและพฤติกรรมเหมือนต้นแบบนี้
   - ตัวต้นแบบมีส่วนที่ "เฉพาะ mockup" ซึ่ง**ห้ามนำไปใช้**: แถบจำลองวัน, กล่องหมายเหตุ mockup, ฟอนต์จาก Google, QR ที่ฝังในหน้า
4. แผนนี้ทั้งไฟล์

## 1. หลักการ
- เป็น**ชั้นตกแต่ง**บนธีม A ไม่เปลี่ยน token สีหลัก ฟอนต์หลัก หรือโครงหน้า
- ถ้าลบไฟล์ CSS ของ PR นี้ออก ทุกหน้าต้องยังใช้งานได้ครบ
- ภาษาไทยทุกจุดใช้ Sarabun / Noto Serif Thai ที่ self-host อยู่แล้ว **ห้ามเพิ่มฟอนต์ใหม่ และห้ามโหลดจาก Google**
- "ตัวพิมพ์ดีด" ใช้ Sarabun + `font-variant-numeric: tabular-nums` + `letter-spacing` เฉพาะตัวเลข เลขที่ใบจอง และรหัสห้อง
- ไม่ใส่ตัวนับผู้เข้าชม ข้อความวิ่ง GIF หรืออะไรที่ทำให้ดูไม่เป็นทางการ (เป็นระบบของหน่วยทหาร)
- ทุกการเคลื่อนไหวต้องปิดได้ด้วย `prefers-reduced-motion: reduce`
- ไม่มี migration ไม่เปลี่ยนสิทธิ์ ไม่เปลี่ยนกฎธุรกิจ และไม่เพิ่มไลบรารี JS

## 2. Branch
- แตก branch จาก `feat/task-first-booking` (PR-A) และเปิด PR โดยตั้ง base เป็น `feat/task-first-booking` เมื่อ PR-A merge แล้ว ให้เปลี่ยน base เป็น `feat/lodging-v5-2`
- branch: `feat/theme-90s-cassette`
- commit แยก: B1 ไฟล์ธีม · B2 การ์ดแฟ้ม · B3 ชิปปุ่มกด · B4 แถบผลลัพธ์ · B5 ใบจองและตรายาง · B6 บัตรตลับเทป · B8 หน้าแรกยุค 90 · B7 เอกสาร

---

## B1. ไฟล์ธีมและข้อยกเว้น
- ไฟล์ใหม่ `static/css/theme_90s.css` โหลดใน `templates/base.html` **ต่อจาก** `app.css`
- ไฟล์ใหม่ `static/css/lodging_cassette_pass.css` โหลดเฉพาะหน้าบัตร (block `head` ของ `student_pass.html`)
- ไฟล์ใหม่ `static/js/lodging_cassette_pass.js` โหลดแบบ `defer` เฉพาะหน้าบัตร
- ขนาดหลังบีบอัด (gzip): `theme_90s.css` ≤ 6 KB, `lodging_cassette_pass.css` ≤ 8 KB, `lodging_cassette_pass.js` ≤ 5 KB (ใส่ตัวเลขจริงใน PR)
- token ใหม่ประกาศใน `:root` ของ `theme_90s.css` เท่านั้น ห้ามแก้ token เดิมใน `app.css`:
  - แถบหูแฟ้ม: `--tab-lodging: #2F6B3A`, `--tab-online: #1F4E79`, `--tab-classroom: #C98A1B`, `--tab-meeting: #A3241C`
  - ตลับเทป: `--shell: #2A2E2B`, `--shell-edge: #1A1D1B`, `--shell-side: #121413`, `--tape: #4A2F22`, `--hub: #ECE6D6`
- `docs/theme-a-ledger.md` ให้เพิ่มหัวข้อ "ข้อยกเว้นยุค 90":
  - เงาและ gradient อนุญาต**เฉพาะภายในวัตถุตลับเทป**เพื่อให้ดูเป็นของจริง (ม้วนเทป กระจกหน้าต่าง ความหนาตลับ)
  - ที่อื่นยังห้ามตามเดิม

## B2. การ์ดบริการเป็นแฟ้มเอกสาร (หน้า Gateway)
- การ์ด `.lka-r3g-service` 4 ใบที่ PR-A ทำ: เพิ่ม "หูแฟ้ม" เป็นแถบสีเล็กที่มุมบนซ้ายของการ์ด
  - ทำด้วย `::before` สูง ~10px กว้าง ~38% ของการ์ด มุมบนโค้ง 2px สีตาม `--tab-*`
  - ใส่ class `service--lodging` / `--online` / `--classroom` / `--meeting` บนการ์ด
- ตัวการ์ดคงพื้นกระดาษธีม A และเส้นขอบ 1px
- ตอน hover/focus การ์ดยกขึ้น 2px (`transform: translateY(-2px)`) ปิดเมื่อ reduced-motion
- สีไม่ใช่ตัวบอกความหมายเพียงอย่างเดียว เพราะชื่อบริการเขียนไว้แล้ว
- **ห้ามแตะ** ภาพ 3D และ `lodging_about_explorer.js`

## B3. ชิปเป็นปุ่มกดแบบเครื่องคิดเลขตั้งโต๊ะ
- ใช้กับ `.chip > span` ทั้งระบบ (หน้า `/book/` และ `/online/`) ผ่าน `theme_90s.css`
- ปกติ: เส้นขอบ 1px ink + ขอบล่าง 3px `var(--rule-strong)`
- `:active` และ `input:checked + span`: ขอบล่างเหลือ 1px + `translateY(2px)` ให้ดูเหมือนกดยุบ ส่วนสี checked คง ink ทึบตามธีม A
- `min-height: 44px` ต้องคงไว้ (เป้ากดบนมือถือ)
- focus ring เดิม (`outline 2px var(--link)`) ต้องยังเห็น

## B4. ผลลัพธ์ห้องว่างเป็นแถบกระดาษต่อเนื่อง (dot-matrix)
ใช้กับการ์ดห้องที่ระบบเสนอใน `partials/online_results.html` (PR-A) และกล่อง "ระบบเลือกห้องให้" ของคำขอห้องพักบุคคลทั่วไป:
- class ใหม่ `.slip`: พื้น `--paper-raised`, ขอบซ้ายและขวาเป็นรูหนามเตย
  - ทำด้วย `radial-gradient` วงกลม 5px ห่าง 14px ซ้ำแนวตั้ง กว้างข้างละ 14px
  - เส้นประบาง 1px คั่นระหว่างแถบรูกับเนื้อหา
- รหัสห้องและเวลาใช้ตัวพิมพ์ดีด (tabular-nums + letter-spacing .04em)
- ตอนผลลัพธ์โหลดใหม่ (`htmx:afterSwap`) แถบเลื่อนลงจาก -8px ใน 180ms เหมือนกระดาษออกจากเครื่องพิมพ์ ทำครั้งเดียว และปิดเมื่อ reduced-motion
- ปุ่ม "ยืนยันจอง" คงเป็นปุ่มหลักธีม A

## B5. ใบจองและตรายาง
- ใช้ `.stamp` เดิมใน `app.css` **ห้ามสร้างระบบตราใหม่**
- หน้า `booking_detail` (ส่วนผลการจองที่มี `booking_ref`):
  - หัวใบจองใช้ตัวพิมพ์ดีดสำหรับ "เลขที่ {{ booking_ref }}"
  - ตราอนุมัติคงเป็น "อนุมัติ" ตามสถานะเดิม (เป็นข้อความสถานะของระบบ ห้ามเปลี่ยน)
- หน้า `lodging/general_request_status.html`:
  - คำขอที่เพิ่งส่ง (PENDING) แสดงตรา "รับเรื่องแล้ว" สีแดงเอียง พร้อมเลขอ้างอิงคำขอ
  - เลขอ้างอิงเรียก `bookings.services.booking_ref(booking)` ตัวเดียวกับ booking_detail **ห้ามสร้างรูปแบบเลขใหม่**
  - **ห้ามแสดง token ของลิงก์สถานะ** บนหน้า เพราะเป็นกุญแจเข้าถึง
- ตราทุกอันมี `aria-hidden="true"` และข้อมูลสถานะจริงต้องมีเป็นตัวหนังสือปกติในหน้า (ตามแบบ booking_detail ที่มีอยู่)

---

## B6. บัตรเข้าพักตลับเทป 3D (`templates/lodging/student_pass.html`)

หน้านี้ใช้ 2 ที่:
- `lodging_pass` (บัตรของนักเรียน)
- `lodging_reservation_manage` (หน้าจัดการการจองด้วย token ซึ่งมีปุ่มยกเลิก)

ทั้งสองต้องได้ตลับเทป

### B6.1 ข้อมูลความคืบหน้าการพัก (ฝั่ง server)
เพิ่มใน `bookings/lodging_services.py`:
```python
@dataclass(frozen=True)
class StayProgress:
    nights_total: int      # check_out_date - check_in_date (อย่างน้อย 1)
    nights_elapsed: int    # 0 ก่อนวันเข้า, เพิ่มทีละ 1 ทุกวันที่ผ่านไปหลังวันเข้า, เท่ากับ total ตั้งแต่วันออก
    state: str             # "upcoming" | "staying" | "checkout_day" | "ended"

def stay_progress(check_in_date, check_out_date, today=None) -> StayProgress:
```
- `today` ค่าเริ่มต้น `timezone.localdate()` (Asia/Bangkok)
- ตัวอย่าง: เข้า 5 ต.ค. ออก 9 ต.ค. → total 4
  - วันที่ 4 → elapsed 0, upcoming
  - วันที่ 5 → 0, staying
  - วันที่ 7 → 2, staying
  - วันที่ 9 → 4, checkout_day
  - วันที่ 10 → 4, ended
- `_student_pass_context` เพิ่ม `stay = stay_progress(cohort.check_in_date, cohort.check_out_date)`

### B6.2 Markup
โครงสร้างตามต้นแบบ แต่ต้อง**คง contract ที่ `bookings/tests_ux16.py` ตรวจอยู่**:
- `id="keycard"` (มีตัวเดียว), `role="button"`, `tabindex="0"`, `aria-pressed`
- class `keycard-front`, `keycard-back`, `keycard-actions-bar`

ให้ใส่ class เพิ่ม `keycard--cassette` บน `#keycard` แทนการเปลี่ยนชื่อ ถ้า contract ใดคงไว้ไม่ได้จริง ให้แก้ test พร้อมอธิบายใน PR **ห้ามลบ test**

```
#keycard.keycard.keycard--cassette            ← เวที 3D (perspective) และรับการลาก/แตะ/คีย์บอร์ด
  .cassette                                    ← preserve-3d, หมุนตามลาก
    .cassette-side.top / .bottom / .left / .right   ← ความหนาตลับ
    .keycard-face.keycard-front  (ด้าน A)
      สกรู 5 ตัว, ฉลาก (.cassette-label), ร่องกันลื่น, ช่องหัวเทป (.cassette-lip)
      ฉลาก: [A] SIGROOM · ที่พัก รร.ส.สส.
            ห้อง {{ student.room.code }}  เตียง {{ student.bed_number }}
            แถบสี 3 เส้น + หน้าต่างเทป (SVG ม้วนเทป)
            {{ student.rank }} {{ student.full_name }}
            {{ cohort.title }} · {{ cohort.check_in_date|thai_date }} – {{ cohort.check_out_date|thai_date }}
            ตรายาง "จองแล้ว"
    .keycard-face.keycard-back   (ด้าน B)
      สติกเกอร์ขาว: <img class="keycard-qr" src="{% url 'bookings:lodging_checkin_qr_svg' student.id %}" …>
                    [B] ห้อง … เตียง … ชื่อ หลักสูตร วันที่
```

- **ด้านหลัง:** ใช้ `<img>` QR จาก URL เดิมเท่านั้น ห้ามฝัง SVG ของ QR ในหน้า และห้ามสร้าง QR ฝั่ง JS
  - เปลี่ยน `loading="lazy"` เป็น `loading="eager"` เพราะผู้ใช้จะพลิกมาดูทันที
- ส่วน `aria-hidden="true"` ใส่ทั้งก้อน `.cassette` แล้ว**เพิ่มตาราง "รายละเอียดการเข้าพัก"** ใต้ตลับเป็นข้อความปกติ (`<dl>`) ตามต้นแบบ:
  - ห้อง/เตียง, ผู้เข้าพัก, หลักสูตร, เข้าพัก (วันที่ 14.00 น.), ออก (วันที่ 12.00 น.), สถานะ
  - สถานะ: "ยังไม่ถึงวันเข้าพัก · N คืน" / "เข้าพักแล้ว · เหลือ N คืน" / "วันออก · คืนห้องภายใน 12.00 น." / "สิ้นสุดการเข้าพัก"
- ป้ายในหน้าต่างเทป (SVG `<text>`):
  - "เหลือ N" ระหว่างพัก (N = total − elapsed)
  - "N คืน" ก่อนเข้าพัก
  - "ครบ" ตั้งแต่วันออก
- **QR แบบเต็มจอ:** ปุ่ม "ขยาย QR เต็มจอ (ให้เจ้าหน้าที่สแกน)" เปิด `<dialog>` พื้นขาวที่มี `<img>` QR เดิมขนาด `min(78vw, 60vh)` + ห้อง/เตียง/ชื่อ + ปุ่มปิด กด Esc ปิดได้ (ใช้ `<dialog>` ของเบราว์เซอร์ ไม่ต้องเขียนเอง)
- ปุ่มเดิม (แชร์ LINE, คัดลอกลิงก์, กลับหน้ารอบ, ยกเลิก) คงอยู่ใน `.keycard-actions-bar` ตามเดิม
- ใน `copyPassLink` ให้เปลี่ยน `alert(...)` เป็นข้อความในหน้า (`role="status"`)

### B6.3 ม้วนเทป (SVG + JS)
ทำตามต้นแบบ:
- `defs`: `radialGradient` เนื้อเทป, `linearGradient` แสงสะท้อนกระจก, `<g id="packArt">` (วงเทป r=40 + เส้นวงซ้อน 7 วงแบบ `vector-effect="non-scaling-stroke"` + ขอบเข้ม + แสงโค้ง)
- ม้วนซ้าย/ขวาใช้ `<use href="#packArt">` แล้วปรับขนาดด้วย `scale(r/40)`
- รัศมีม้วนตาม**พื้นที่** (ไม่ใช่เส้นตรง):
  ```
  r(frac) = sqrt(MINR² + (MAXR² − MINR²) · frac)
  MINR = 12, MAXR = 40
  ม้วนซ้าย frac = 1 − elapsed/total, ม้วนขวา frac = elapsed/total
  ```
- **server render ค่าเริ่มต้นให้ถูกตั้งแต่ HTML** (ใส่ `transform` ของม้วนใน template จาก `stay`) หน้าจึงถูกต้องแม้ JS ไม่โหลด
  - ส่งค่าให้ JS ผ่าน `data-nights-total` / `data-nights-elapsed` บน `#keycard` **ห้ามใช้ inline script ฝังข้อมูล**
- ดุม: วงขาว + วงเงา + ร่องหนีบเทป + รูเฟือง 6 ซี่ สร้างใน template เป็น SVG คงที่ (JS แค่หมุน)
- **การเคลื่อนไหว** (เฉพาะเมื่อไม่ reduced-motion):
  - เปิดหน้า: กรอเทปจาก elapsed=0 ไปค่าจริงใน 0.7–1.8 วินาที (ease-out) ดุมหมุนเร็ว
  - หลังจากนั้นเล่นช้า ๆ ด้วยความเร็วเส้นคงที่ (`PLAY = 9`): มุมที่หมุน = `speed / r` ม้วนเล็กจึงหมุนเร็วกว่า
  - หยุด `requestAnimationFrame` เมื่อพลิกไปด้าน B หรือแท็บถูกซ่อน (`visibilitychange`) เพื่อประหยัดแบตเตอรี่
- reduced-motion: ไม่กรอ ไม่หมุน แสดงค่าจริงทันที พลิกด้านแบบไม่มี transition

### B6.4 การหมุนและพลิก
- ลากด้วย Pointer Events:
  - `rotateY` ตาม dx × 0.35 จำกัด ±38°
  - `rotateX` ตาม −dy × 0.3 จำกัด ±24°
  - ปล่อยแล้วกลับ 0 ด้วย transition 0.7s
- `touch-action: pan-y` ให้หน้ายังเลื่อนขึ้นลงได้บนมือถือ
- แตะ (ขยับน้อยกว่า 6px), Enter หรือ Space → พลิก
  - อัปเดต `aria-pressed` และ `aria-label` ตามแบบเดิมในไฟล์
- **ด้าน B ห้ามเอียง:**
  - เมื่อพลิกไปด้าน B ให้รีเซ็ตเป็น `rotateY(180deg)` ตรง และไม่รับการลากเอียง
  - บนด้าน B ห้ามมีเงา gradient หรือลายทับ QR
  - ขอบขาวรอบ QR ≥ 4 โมดูล (มาจาก `border=4` ของ generator อยู่แล้ว ห้าม crop)
- ไม่ใช้ `deviceorientation`
- ความหนาตลับใช้ตัวแปร `--t: 3.6cqw` และ `container-type: inline-size` บนเวทีตามต้นแบบ
  - ถ้าเบราว์เซอร์ไม่รองรับ `cqw` ให้ fallback ด้วย `@supports not (width: 1cqw)` เป็นค่า px คงที่

### B6.5 Header ความปลอดภัย
`_student_pass_response` ต้องคง `Cache-Control: private, no-store…`, `X-Robots-Tag`, `Referrer-Policy: no-referrer`, `nosniff` ไว้ทั้งหมด **ห้ามแตะ**

---

## B8. หน้าแรกแบบโต๊ะทำงานยุค 90 (`lodging_about.html` ส่วนบนและส่วนบริการ)
ต้นแบบที่ผู้ใช้อนุมัติ: `docs/mockups/gateway-90s-mockup.html` (ตัวควบคุม "จำลอง" ในต้นแบบ**ห้ามนำไปใช้**)

### B8.1 ปฏิทินฉีก
- กล่องเล็กข้างหัวข้อ "วันนี้ต้องการใช้ห้องอะไร": แถบหัวสี `--stamp` เขียน "ต.ค. ๒๕๖๙", เลขวันเลขไทยตัวใหญ่ (Noto Serif Thai), ชื่อวัน, รอยปรุด้านล่าง, รูห่วงด้านบน
- **render ฝั่ง server** ด้วย `timezone.localdate()` ห้ามคำนวณวันที่ด้วย JS
  - เลขไทยใช้ template filter ที่มีอยู่ใน `bookings/templatetags/thaidate` ถ้ายังไม่มี filter แปลงเลขไทย ให้เพิ่มในไฟล์นั้นพร้อม test
- ห่อด้วย `role="img"` และ `aria-label="วันนี้ วัน…ที่ … พ.ศ. …"`

### B8.2 เพจเจอร์ (เฉพาะผู้ที่ login)
- แทนแถว "การจองของฉัน (N)" ที่ PR-A ทำ: ตัวเครื่องดำ จอ LCD (`--lcd`, `--lcd-ink`) ไม่มี glow
  - บรรทัดบน "มีข้อความ N" (N = จำนวนแจ้งเตือนที่ยังไม่อ่าน จาก `nav_unread_count` ที่มีอยู่แล้ว) และเวลาปัจจุบัน HH:MM
  - บรรทัดล่างแสดงข้อความล่าสุด 1–2 รายการ:
    1. หัวข้อแจ้งเตือนล่าสุดที่ยังไม่อ่าน (ถ้ามี)
    2. การจองถัดไปของผู้ใช้ เช่น "พรุ่งนี้ 10.00 น. STU-ONLINE-2" ใช้ query `next_booking` แบบเดียวกับ `calendar_view`
  - มีข้อความ 2 รายการ: สลับทุก 3.5 วินาที ด้วย JS ใน `static/js/gateway_90s.js` ปิดเมื่อ reduced-motion
- ทั้งก้อนเป็นลิงก์เดียวไป `bookings:my_bookings` และมี `aria-label` ที่อ่านจำนวนข้อความได้
- ไม่มีข้อความเลย: "ไม่มีข้อความใหม่" และไม่กะพริบ

### B8.3 แฟ้มบริการ
ทำตาม B2 และเพิ่ม:
- ป้ายเล็ก "แฟ้ม ๑–๔" บนการ์ดแต่ละใบ
- ปุ่มย่อยของการ์ดห้องพักใช้สไตล์ปุ่มกดแบบ B3

### B8.4 บอร์ดไม้ก๊อก "ประกาศวันนี้" (ใต้แฟ้มบริการ)
- กรอบไม้ + พื้นลายจุดไม้ก๊อก + กระดาษโน้ตปักหมุดเอียงเล็กน้อย (≤ 2°) สูงสุด 4 แผ่น
- **ข้อมูลจริงเท่านั้น** ดึงผ่าน service ใหม่ใน `bookings/services.py`:
  ```python
  def gateway_notices(today) -> list[dict]:  # {"kind": "closed"|"lodging_open", "title", "body", "url"}
  ```
  - `closed`: `resources.Blackout` และ `resources.ResourceOutage` ที่ทับวันนี้ (หัวแดง "งดใช้ห้อง")
    - แสดงขอบเขต (ทุกห้อง/อาคาร/ประเภท/ห้อง) ช่วงเวลา และเหตุผล
    - **อย่าแสดงเหตุผลของรายการที่ไม่ควรเปิดเผยต่อสาธารณะ** ตรวจว่า model มีฟิลด์ระดับการมองเห็นหรือไม่ ถ้ามี ให้เคารพฟิลด์นั้น ถ้าไม่แน่ใจ ให้แสดงแค่ "ปิดปรับปรุง" แล้วเขียนไว้ในข้อสงสัย
  - `lodging_open`: รอบหลักสูตรที่ `cohort_self_booking_status(...) == "open"` (หัวเขียว "เปิดจองที่พัก" + ลิงก์ไป portal)
  - เรียง closed ก่อน แล้วตามเวลาเริ่ม
- ไม่มีประกาศ: บอร์ดแสดงข้อความ "วันนี้ไม่มีประกาศ"
- ลิงก์ "ดูสถานะห้องทั้งหมด" อยู่ใต้บอร์ด (ลิงก์ตัวหนังสือ)

### B8.5 ข้อบังคับเพิ่มเติม
- หน้า gateway เปิดได้โดยไม่ login และตอนนี้ไม่มี `Cache-Control`
  - เมื่อมีเนื้อหาเฉพาะผู้ใช้ (เพจเจอร์) ต้องตั้ง `Cache-Control: private, no-store` **เฉพาะเมื่อ login** กัน CDN ของ Firebase เก็บหน้าของคนหนึ่งไปให้อีกคน
  - กรณีไม่ login ให้คงพฤติกรรมเดิม
- docstring ของ `lodging_about` ที่เขียนว่า "ไม่มีข้อมูลส่วนบุคคล" ให้แก้ให้ตรงความจริง
- เพิ่ม query ไม่เกิน 4 ครั้งต่อการเปิดหน้า (ใช้ `django_assert_max_num_queries` ใน test)

### B8.6 Test (เพิ่มใน `bookings/tests_theme_90s_cassette.py`)
- ปฏิทิน: freeze วันที่ 5 ต.ค. 2569 → หน้ามี "๕", "ต.ค. ๒๕๖๙" และ "วันจันทร์"
- เพจเจอร์: ไม่ login ไม่มีเพจเจอร์ / login มีแจ้งเตือนค้าง 2 → "มีข้อความ 2" และลิงก์ my_bookings / login ไม่มีอะไร → "ไม่มีข้อความใหม่"
- login → response มี `Cache-Control` ที่มี `no-store` / ไม่ login → ไม่มี `no-store`
- บอร์ด: มี Blackout วันนี้ → โน้ต "งดใช้ห้อง" / มีรอบเปิด → โน้ต "เปิดจองที่พัก" พร้อมลิงก์ portal / ไม่มี → "วันนี้ไม่มีประกาศ"
- จำนวน query ตาม B8.5

---

## B7. เอกสาร
- `docs/theme-a-ledger.md` เพิ่มหัวข้อ "ชั้นตกแต่งยุค 90" ประกอบด้วย:
  - รายการ B2–B6
  - token ใหม่
  - ข้อยกเว้นเงาและ gradient ในตลับเทป
  - กติกา "ด้าน QR ห้ามเอียง/ห้ามลายทับ"

## 3. Test (ไฟล์ใหม่ `bookings/tests_theme_90s_cassette.py`)
- `stay_progress` ครบ 5 กรณีในตัวอย่าง B6.1 รวมรอบที่พัก 1 คืน และกรณีข้อมูลวันออกไม่หลังวันเข้า (total = 1, ไม่ error)
- หน้า `lodging_pass`:
  - มี `<img` ที่ชี้ `lodging_checkin_qr_svg` ของนักเรียนคนนั้นทั้งบนด้าน B และใน dialog
  - ไม่มี `<svg` ของ QR ฝังในหน้า
  - มีข้อมูล ห้อง/เตียง/ชื่อ/หลักสูตร/วันเข้า/วันออก/สถานะ เป็นข้อความใน `<dl>`
  - `data-nights-total` และ `data-nights-elapsed` ถูกต้องตามวันที่ (ใช้ freeze วันที่หรือส่ง `today` ผ่าน service)
  - ป้ายหน้าต่าง: "4 คืน" (ก่อนเข้า) / "เหลือ 2" (ระหว่างพัก) / "ครบ" (วันออก)
  - header ความปลอดภัยครบเหมือนเดิม
  - ไม่มี `alert(` ในหน้า
- หน้า `lodging_reservation_manage` ได้ตลับเทปและปุ่มยกเลิกยังอยู่
- `lodging_cassette_pass.css` มีบล็อก `prefers-reduced-motion: reduce` ที่ปิด transition/animation
- `lodging_cassette_pass.js` มีการตรวจ `prefers-reduced-motion` และ `visibilitychange`
- `theme_90s.css` และไฟล์ตลับเทปไม่มี `fonts.googleapis` หรือ URL ภายนอก
- `base.html` โหลด `theme_90s.css` หลัง `app.css`
- test เดิม `tests_ux16.py`, `tests_ux15.py`, `tests_lodging_v4.py`, `tests_r3_l_booking_flows.py`, `tests_p2_lodging_checkout.py`, `tests_phase_d_oct6_readiness.py`, `tests_ui4.py` ต้องผ่าน (ถ้าแก้ ให้อธิบายรายไฟล์)

## 4. เกณฑ์ผ่าน
- [ ] `uv run pytest` ผ่านทั้งหมด (ใส่ตัวเลขจริง)
- [ ] `uv run manage.py check` และ `makemigrations --check --dry-run` ผ่าน
- [ ] `collectstatic` ผ่าน (`DJANGO_SECRET_KEY=x uv run manage.py collectstatic --noinput`)
- [ ] ขนาดไฟล์ตามข้อ B1
- [ ] ภาพหน้าจอมือถือ 390px:
  - Gateway (การ์ดแฟ้ม)
  - `/online/` (ชิปปุ่มกด + แถบ dot-matrix)
  - คำขอห้องพัก
  - หน้าสถานะคำขอ (ตรา "รับเรื่องแล้ว")
  - บัตรตลับเทปด้าน A ตรง / ด้าน A ตอนเอียง / ด้าน B / QR เต็มจอ
- [ ] **สแกน QR จริง** จากหน้าจอมือถือ (ด้าน B และ dialog) ด้วยกล้องโทรศัพท์อีกเครื่อง แล้วเขียนผลใน PR
- [ ] ทดสอบเปิด "ลดการเคลื่อนไหว" ในเครื่อง (iOS: การช่วยเหลือการเข้าถึง → การเคลื่อนไหว) แล้วยืนยันว่าเทปไม่หมุน
- [ ] contrast ข้อความบนฉลากและแถบหูแฟ้มผ่าน 4.5:1

## 5. รูปแบบ PR
- ชื่อ: `feat(theme): 90s office layer + 3D cassette lodging pass`
- เนื้อหาภาษาไทย:
  - สรุป B1–B7
  - ภาพหน้าจอ
  - ผลสแกน QR
  - test เดิมที่แก้พร้อมเหตุผล
  - ขนาดไฟล์
  - หัวข้อ "ข้อสงสัย"
  - วิธีดูผลด้วยตาตัวเอง

## 6. จุดที่ Claude จะตรวจเป็นพิเศษ
1. QR ด้าน B เอียงได้ มีอะไรทับ หรือถูก crop ขอบขาว
2. ตลับเทปแสดงค่าผิดเมื่อ JS ไม่โหลด (ต้อง server render ถูกตั้งแต่แรก)
3. ข้อมูลบัตรอ่านไม่ได้ด้วยโปรแกรมอ่านหน้าจอ
4. animation ยังวิ่งตอนพลิกหรือตอนแท็บถูกซ่อน / ไม่เคารพ reduced-motion
5. ชั้นตกแต่งหลุดไปเปลี่ยน token หรือหน้าตาหน้าอื่นนอกขอบเขต
6. header ความปลอดภัยหน้าบัตรหายหรือเปลี่ยน
7. มีฟอนต์หรือไฟล์ภายนอก หรือ inline script ฝังข้อมูลส่วนตัว
