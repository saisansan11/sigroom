# PR-C: นกพิราบสื่อสารของครู (สัตว์เลี้ยงในไข่จากการสอนออนไลน์)

เขียน 3 ต.ค. 2569 · ผู้ทำ: Codex · ผู้ตรวจ: Claude
ต่อยอดจาก PR-B (stacked branch ตาม `docs/plans/2026-10-03-codex-runbook.md`)

ต้นแบบที่ผู้ใช้อนุมัติ: `docs/mockups/teaching-pigeon-mockup.html`
- เปิดใน Chrome แล้วลองกดทุกปุ่มก่อนเริ่ม
- ตัวควบคุม "จำลอง" ในต้นแบบ**ห้ามนำไปใช้**
- ภาพพิกเซลในต้นแบบใช้เป็นจุดเริ่มต้นได้ (ผู้ใช้จะปรับภาพในเวอร์ชันถัดไป) ให้แยกข้อมูลภาพไว้ไฟล์เดียวเพื่อเปลี่ยนง่าย

## 0. หลักการ (ห้ามละเมิด)
1. **รางวัลมาจากการสอนจริงเท่านั้น ไม่ใช่การจอง** เพื่อไม่ให้มีการจองเล่นที่กันห้องจริงไว้
2. **นกไม่ตาย ไม่ถอยขั้น ไม่หิว** ปุ่มให้อาหาร/ลูบหัวเป็นของเล่น ไม่มีผลกับการเติบโต
3. **ห้ามใช้คำว่า "ทามาก็อตจิ" / "Tamagotchi" หรือหน้าตาของสินค้า Bandai** ในโค้ด หน้าเว็บ ชื่อไฟล์ หรือ commit
4. เห็นนกได้เฉพาะเจ้าของ ไม่มีกระดานอันดับ และไม่เปิดเผยข้อมูลการสอนของคนอื่น
5. ปิดได้ทั้งระบบ (setting) และปิดได้รายบุคคล
6. ห้ามแตะกฎการจอง การกันจองซ้อน และสถานะการใช้ห้อง (usage) นกแค่ "อ่าน" ข้อมูลเหล่านั้น

## 1. กติกาการเลี้ยง (คำนวณจากข้อมูลที่มีอยู่)
"การสอนออนไลน์" ในแผนนี้ หมายถึง `Booking` ที่:
- `requester = ผู้ใช้`
- `room.room_category = ONLINE`
- `request_status = APPROVED`

| ค่า | วิธีคำนวณ |
|---|---|
| มีไข่ | มีแถว `TeachingPigeon` ของผู้ใช้ (สร้างตอนจองห้องออนไลน์สำเร็จครั้งแรก ดูข้อ 3) |
| ฟักแล้ว | `hatched_at` ไม่ว่าง หรือมีการสอนออนไลน์ที่ `start_at <= now` |
| สอนจบ (`taught`) | จำนวนการสอนออนไลน์ที่ `usage_status = USED` (ระบบตั้งให้อัตโนมัติหลังคาบจบโดย `usage.services` ผ่าน `run_jobs`) |
| ขั้นที่คำนวณได้ | ยังไม่ฟัก=0 ไข่ · ฟักแล้ว=1 ลูกนก · taught ≥ 5 = 2 นกรุ่น · ≥ 15 = 3 นกสื่อสาร · ≥ 30 = 4 นกสื่อสารติดยศ |
| ขั้นที่แสดง | `max(highest_stage, ขั้นที่คำนวณได้)` **ไม่ถอยขั้น** แม้ผู้ดูแลแก้ USED เป็น NO_SHOW ภายหลัง |
| อารมณ์ | `happy` ถ้ามีการสอนออนไลน์ที่ยกเลิก (`CANCELLED`) ภายใน 24 ชม. ที่ผ่านมา และยกเลิกก่อนเวลาเริ่มอย่างน้อย 24 ชม. · ไม่เช่นนั้น `sad` ถ้ามีการสอนที่ถูกบันทึก `NO_SHOW` และ `end_at` อยู่ใน 24 ชม. ที่ผ่านมา · ไม่เช่นนั้น `normal` |
| ห้องถัดไป | การสอนออนไลน์ที่ `end_at > now` และ `usage_status` ไม่ใช่ `DISPLACED` เรียงตาม `start_at` |

เวลาที่ยกเลิก: model ไม่มี `cancelled_at`
- ให้ใช้เวลาของ audit log action `"booking_cancelled"` ที่ `cancel_booking` บันทึก (`bookings/services.py`)
- ถ้าหาไม่ได้ ใช้ `updated_at` และเขียนไว้ในข้อสงสัย
- **ห้ามเพิ่มฟิลด์ใน Booking**

เกณฑ์ขั้นใส่เป็นค่าคงที่ไว้ที่เดียว (`PIGEON_STAGES`) ผู้ใช้จะปรับในเวอร์ชันถัดไป

## 2. Model (migration ใหม่ เพิ่มตารางอย่างเดียว ตรงกติกา expand/contract)
ใน `bookings/models.py` (หรือ `bookings/pigeon_models.py` แล้ว import ใน models ตามแบบ `lodging_models.py`)

```python
class TeachingPigeon(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="teaching_pigeon")
    name = models.CharField("ชื่อนก", max_length=20, blank=True)
    hidden = models.BooleanField("ไม่แสดงนก", default=False)
    highest_stage = models.PositiveSmallIntegerField(default=0)
    hatched_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```
- `uv run manage.py makemigrations bookings` ได้ migration เดียว ที่มีแค่ `CreateModel`
- admin: ลงทะเบียนแบบอ่านอย่างเดียว ยกเว้น `hidden` (ให้ผู้ดูแลปิดนกของบัญชีที่ใช้ชื่อไม่เหมาะสมได้)

## 3. Service `bookings/pigeon_services.py`
```python
PIGEON_STAGES = (("egg","ไข่",None), ("chick","ลูกนก",None), ("young","นกรุ่น",5), ("adult","นกสื่อสาร",15), ("rank","นกสื่อสารติดยศ",30))
PIGEON_NAME_SUGGESTIONS = ("น้องสาส์น", "จ่าพิราบ", "สื่อสารน้อย", "ไปรษณีย์")

def pigeon_enabled() -> bool                       # settings.SIGROOM_PIGEON_ENABLED (ค่าเริ่มต้น True อ่านจาก .env)
def grant_egg(user) -> bool                        # get_or_create; คืน True ถ้าเพิ่งได้ไข่ครั้งแรก
def pigeon_state(user, now=None) -> PigeonState | None   # อ่านอย่างเดียว ห้ามเขียน DB
def sync_pigeons(now=None) -> int                  # อัปเดต highest_stage / hatched_at ของทุกนก (เรียกจาก run_jobs)
def rename_pigeon(user, name) / set_pigeon_hidden(user, hidden)
```
- `PigeonState` (dataclass): `name`, `stage_key`, `stage_label`, `stage_index`, `taught`, `next_label`, `remaining_to_next`, `progress_pct`, `mood`, `next_booking` (start_at, end_at, room code), `hatched`, `hidden`
- `grant_egg` เรียกจาก `create_online_teaching_booking` (PR-A) **หลังจองสำเร็จเท่านั้น**
  - อยู่ใน transaction เดียวกัน
  - ถ้าระบบนกปิด (`pigeon_enabled()` เป็น False) ไม่สร้าง
  - **ห้ามให้การจองล้มเพราะเรื่องนก**: ถ้าสร้างนกผิดพลาด ให้ log แล้วจองต่อ
- `sync_pigeons` เพิ่มใน `run_jobs` **ต่อจาก**งานที่ตั้ง USED อัตโนมัติ
  - รันซ้ำได้ (idempotent) และไม่ลด `highest_stage`
- `rename_pigeon`: ตัดช่องว่างหัวท้าย, ความยาว ≤ 20, ห้ามมีอักขระควบคุม, ว่างได้ (แสดงเป็น "นกของคุณ"), บันทึก audit
- ทุกฟังก์ชันคืน None หรือไม่ทำอะไร ถ้าผู้ใช้ไม่มีสิทธิ์ `can_book_online_teaching` หรือระบบนกปิด

## 4. หน้าจอ
### 4.1 หน้า "นกพิราบสื่อสารของฉัน" `online/pigeon/` (name `bookings:online_pigeon`)
- `@login_required` และต้อง `can_book_online_teaching`
  - ถ้าไม่มีสิทธิ์: 403 แบบเดียวกับ POST ออนไลน์
  - ยังไม่มีไข่: หน้าอธิบาย "จองห้องสอนออนไลน์ครั้งแรกเพื่อรับไข่" + ปุ่มไป `/online/`
- โครงหน้าตามต้นแบบ:
  - เครื่องรูปไข่ + จอ canvas 32×24
  - ปุ่ม A/B/C พร้อมป้ายข้อความ
  - ตาราง "ข้อมูลนก" (`<dl>`) ที่อ่านได้แม้ไม่มี JS
  - ฟอร์มตั้งค่า (ชื่อใช้ `<input list>` + datalist จาก `PIGEON_NAME_SUGGESTIONS` ตามกติกาข้อ 7, checkbox ซ่อนนก) POST มาที่ path เดียวกัน แล้ว PRG redirect
- ข้อมูลส่งให้ JS ผ่าน `data-*` บน `#pigeon-device` (`data-stage`, `data-mood`, `data-hatched`, `data-name`, `data-taught`) **ห้ามใช้ inline script**
- `Cache-Control: private, no-store`

### 4.2 ภาพและการเคลื่อนไหว
- `static/js/pigeon_sprites.js`: ข้อมูลภาพพิกเซลทั้งหมด (EGG, EGG_CRACK, CHICK, BIRD, BIRD_BLINK, TUBE, CHEVRON, HEART, NOTE, RAIN) แยกจากโค้ด
- `static/js/pigeon.js`: วาด, เฟรม 4 ครั้ง/วินาที, ปุ่ม A/B/C, ฉากฟัก
  - หยุด timer เมื่อแท็บถูกซ่อน (`visibilitychange`)
  - reduced-motion: ไม่ขยับ ไม่กะพริบ ฟักแบบตัดภาพทันที
- **ฉากฟักเล่นครั้งเดียว:** เมื่อ `data-hatched="true"` และใน `localStorage` ยังไม่มี key `sigroom-pigeon-hatch-seen` ให้เล่นฉากฟักแล้วตั้ง key
  - ครอบ try/catch ถ้าใช้ localStorage ไม่ได้ ให้แสดงลูกนกเลย
- `static/css/pigeon.css`: เครื่องรูปไข่สีเขียวทหาร token ตามต้นแบบ ประกาศใน `:root` ของไฟล์นี้
- ขนาดไฟล์ (gzip): JS รวม ≤ 6 KB, CSS ≤ 4 KB

### 4.3 จุดที่นกปรากฏในระบบ
1. **หลังจองห้องออนไลน์ครั้งแรก** (`grant_egg` คืน True): ข้อความสำเร็จเพิ่มบรรทัด "คุณได้ไข่นกพิราบสื่อสาร 1 ฟอง ไข่จะฟักเมื่อถึงเวลาสอน" พร้อมลิงก์ไปหน้านก
2. **เพจเจอร์หน้าแรก (B8.2):** ถ้ามีนกและไม่ซ่อน เพิ่มข้อความหมุนเวียน 1 รายการ
   - ยังไม่ฟัก: "ไข่จะฟัก <วัน> <เวลา> น."
   - ฟักแล้ว: "<ชื่อนก> รอคุณสอน <วัน> <เวลา> น." / "<ชื่อนก> ดีใจ…" / "<ชื่อนก> เหงา…" ตามอารมณ์
   - ลิงก์เพจเจอร์ยังไป my_bookings ตามเดิม ส่วนหน้านกเข้าจากข้อ 3
3. **หน้า `/online/`:** ลิงก์เล็กมุมขวาบน "นกของฉัน" (เฉพาะผู้มีนกและไม่ซ่อน)
- ซ่อนนก (`hidden=True`) หรือระบบนกปิด: ข้อ 1–3 ไม่แสดงเลย แต่หน้า `online/pigeon/` ยังเข้าได้เพื่อเปิดนกกลับ (ยกเว้นเมื่อระบบนกปิดทั้งระบบ)

## 5. Settings
- `SIGROOM_PIGEON_ENABLED` อ่านจาก env ค่าเริ่มต้น `True` เพิ่มใน `.env.example` พร้อมคำอธิบายภาษาไทย
- ปิดแล้ว: ไม่สร้างไข่ใหม่, ไม่แสดงในหน้าใด ๆ, `online/pigeon/` ได้ 404 ส่วนข้อมูลเดิมไม่ลบ

## 6. Test (`bookings/tests_pigeon.py`)
- จองห้องออนไลน์สำเร็จครั้งแรก → มีนก 1 ตัว และข้อความได้ไข่ / ครั้งที่สอง → ยังมีนกตัวเดียว ไม่มีข้อความซ้ำ
- จองล้มเพราะชน → ไม่มีนก
- การจองห้องประเภทอื่นไม่ให้ไข่
- `grant_egg` เกิด exception (mock) → การจองยังสำเร็จ
- ขั้น: ก่อน start_at = ไข่ / หลัง start_at = ลูกนก / USED 5 = นกรุ่น / 15 / 30
- **ไม่ถอยขั้น:** USED 5 ครั้ง + `sync_pigeons` → highest 2 → แก้ 1 รายการเป็น NO_SHOW → ยังเป็นนกรุ่น
- การจองที่ยังไม่ใช้หรือถูกปฏิเสธไม่นับ
- อารมณ์: ยกเลิกล่วงหน้า 48 ชม. เมื่อ 2 ชม. ก่อน → happy / NO_SHOW เมื่อวาน → sad / ทั้งสองอย่าง → happy / เกิน 24 ชม. → normal
- `sync_pigeons` รันซ้ำแล้วผลเท่าเดิม และ `run_jobs` เรียกมัน
- หน้า `online/pigeon/`:
  - ไม่ login → login / ไม่ใช่ครู → 403 / ครูไม่มีไข่ → หน้าอธิบาย / มีนก → `<dl>` ครบและ `data-*` ถูกต้อง
  - มี `no-store` และไม่มี `<script>` ที่ฝังข้อมูล
- ผู้ใช้ A เปิดหน้าไม่เห็นข้อมูลนกของผู้ใช้ B
- ตั้งชื่อ: ยาว 21 ตัวอักษร → error / `<b>` ถูก escape / ว่างได้ / มี audit
- ซ่อนนก → เพจเจอร์และลิงก์ใน `/online/` หาย / ระบบนกปิด → 404 และไม่สร้างไข่ใหม่
- **ทั้ง repo:** grep ไม่พบ `tamagotchi` (ไม่สนตัวพิมพ์ใหญ่เล็ก) ยกเว้นในไฟล์แผนนี้

## 7. เกณฑ์ผ่าน
- [ ] `uv run pytest` ผ่านทั้งหมด (ใส่ตัวเลข)
- [ ] `manage.py check` ผ่าน · `makemigrations --check` หลังสร้าง migration แล้วไม่มีอะไรค้าง · migration มีแค่ `CreateModel`
- [ ] `uv run manage.py migrate` บนฐานว่างและฐานที่มีข้อมูล PR-A/PR-B ผ่าน
- [ ] ภาพหน้าจอมือถือ: หน้านก (ไข่/ลูกนก/นกติดยศ/เศร้า), ข้อความได้ไข่, เพจเจอร์ที่มีข้อความนก
- [ ] ทดสอบ reduced-motion แล้วนกไม่ขยับ

## 8. รูปแบบ PR
- ชื่อ: `feat(online): teaching pigeon — egg on first booking, grows with real teaching`
- base: `feat/theme-90s-cassette` (เปลี่ยนเป็น `feat/lodging-v5-2` เมื่อ PR-A และ PR-B merge แล้ว)
- เนื้อหาภาษาไทย: สรุป, ตารางกติกาการเลี้ยง, migration ที่เพิ่ม, ภาพหน้าจอ, ข้อสงสัย, วิธีดูผลด้วยตาตัวเอง
  - ใส่ขั้นตอนทดลองเองด้วย: จองห้องออนไลน์ → ดูข้อความได้ไข่ → รอเลยเวลาเริ่ม → เปิดหน้านกเห็นฉากฟัก

## 9. จุดที่ Claude จะตรวจเป็นพิเศษ
1. มีทางไหนที่ "จอง" แล้วนกโต (ต้องโตจาก USED เท่านั้น)
2. นกถอยขั้นได้
3. การจองล้มเพราะโค้ดนก
4. หน้าเว็บเขียน DB ตอน GET
5. ข้อมูลนกของคนหนึ่งรั่วไปอีกคน หรือหน้านกถูก cache
6. migration แตะตารางเดิม
7. คำว่า tamagotchi หรือภาพที่ลอกสินค้าเดิม
