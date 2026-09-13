# UI-2 — Homepage / Availability / Calendar

**Phase:** UI-2  
**Branch:** `feat/ui-2-homepage-availability` (จาก `feat/ui-1-design-foundation`)  
**Date:** 2026-09-14  
**Status:** FINAL APPROVED

---

## Background

UI-1 เสร็จและ stack เป็น PR #17 (`feat/ui-1-design-foundation` → base `fix/lodging-v5-2-final-review`)

```
feat/lodging-v5-2
  └── fix/lodging-v5-2-final-review   PR #16 OPEN/MERGEABLE
        └── feat/ui-1-design-foundation   PR #17 OPEN/MERGEABLE
              └── feat/ui-2-homepage-availability   PR #18 (ใหม่)
```

---

## 1. Branch Strategy และความเสี่ยง Stack ชั้น 3

Branch `feat/ui-2-homepage-availability` cut จาก `feat/ui-1-design-foundation`  
PR #18 target base = `feat/ui-1-design-foundation` (ชั่วคราว)

| เหตุการณ์ | สิ่งที่ต้องทำ |
|---|---|
| #16 + #17 ถูก merge ตามลำดับ | **retarget PR #18** ไปหา base จริง |
| หลัง retarget ทุกครั้ง | **rerun full regression + Browser QA ทั้งหมด ก่อน claim DONE** |

> [!WARNING]
> retarget PR base เพียงอย่างเดียว **ไม่เพียงพอ**  
> ต้อง rerun full regression + Browser QA ทุกครั้งก่อน report PASS  
> ห้าม merge PR ใด ๆ โดยไม่รับคำสั่งจากผู้ใช้

---

## 2. Scope

### เปลี่ยน

| ไฟล์ | ประเภท |
|---|---|
| `templates/bookings/calendar.html` | template restructure + JS: mobile headerToolbar เท่านั้น |
| `static/css/app.css` | เพิ่ม CSS classes ใหม่ (ไม่ลบที่ยังใช้อยู่) |

### ไม่เปลี่ยน

- `bookings/views.py`, services, models, migrations
- Business logic: availability, conflict, permission, privacy
- Lodging calendar semantics (V5.1 invariants)
- FullCalendar bundle — ไม่เพิ่ม dependency ใหม่
- Templates อื่นทุกไฟล์, `.claude/handoffs/`

---

## 3. Template-Data Guardrail

> [!IMPORTANT]
> Status badge "ว่างอยู่" ใช้เฉพาะ **context variables ที่ views.py ส่งมาอยู่แล้ว**
>
> **Variables ที่ใช้ได้:**
> - `homepage_availability.groups[*].cards[*]` → definition คือห้องว่าง → badge "ว่างอยู่" (static)
> - `stat_in_use`, `stat_free_now` → ตัวเลข statusband
> - `board_rows[*].blocks[*].cls` → block state ใน today-board
>
> **ห้ามทำ:** เพิ่ม query/filter ใน template, แก้ `views.py` โดยไม่มี change request
>
> **ถ้าข้อมูลไม่มีใน context → หยุด → อัปเดต plan → รอ approve ก่อน**

---

## 4. Calendar Mobile — Verified Constraints

### ข้อเท็จจริงจากการตรวจ bundle

- FC 6.1.21 (`index.global.min.js`) **ไม่มี List plugin** → `listDay` ใช้ไม่ได้
- `eventClick` guard **ไม่มีอยู่จริงใน calendar.html ปัจจุบัน** — lodging-reserved non-clickable เพราะ `display: "background"` จาก views.py และไม่มี `url` field ใน event JSON → FC จัดการให้เองโดยไม่ต้อง eventClick handler

### Mobile Acceptance Criteria (ยึดตามข้อเท็จจริง)

**Desktop (≥ 768px):**
- คง `initialView: 'timeGridWeek'` — เหมือนเดิม
- Filter bar + legend ยังแสดง
- `selectable: category !== 'lodging'` คงอยู่
- Booking event click → `/bookings/<id>/` ต้องไม่ regress

**Mobile (< 640px — 360/390/430) — Today-focused fallback:**
- `initialView` คงเป็น `'timeGridDay'` — เป็น **Today-focused mobile fallback** ของ UI-2
  - เหตุผล: `listDay` ไม่มีใน bundle (List plugin ไม่ได้รวม); `timeGridDay` แสดงเฉพาะวันปัจจุบันโดย default จึงให้พฤติกรรม agenda-like ที่เพียงพอโดยไม่เพิ่ม dependency
  - ลด noise ด้วยการปรับ `headerToolbar` mobile ให้กระชับ: `prev/next` + `today` + `timeGridWeek` toggle
  - ไม่เปิด week grid เป็นค่าเริ่มต้น — user ต้องกด toggle เองถ้าต้องการดูภาพรวมสัปดาห์
  - ไม่สร้าง custom agenda view หรือ plugin เพิ่มในเฟสนี้

**Lodging-reserved invariant:**
- `display: "background"` (หรือ `"block"` เมื่อ filter ห้องเดียว) จาก views.py → FC ไม่ให้ click อยู่แล้ว
- **ไม่ต้องเพิ่ม eventClick guard** — รักษา mechanism เดิม
- QA ต้องยืนยันว่า click lodging-reserved event ยัง non-navigable ทุก viewport

> [!NOTE]
> JS changes ใน scope มีเพียง: ปรับ `headerToolbar` mobile ให้ toggle `timeGridWeek` ได้  
> `events` endpoint, `extraParams`, `select` callback, `selectable` — ไม่เปลี่ยน

---

## 5. Implementation Detail

### Hero Section (แทน `page-heading` เดิม)

```
Authenticated:
  eyebrow: "ศูนย์งาน SIGROOM"
  h1:      "ห้องที่คุณต้องใช้ ควรหาเจอได้ในไม่กี่วินาที"
  sub:     "ดูห้องว่างช่วงถัดไป จองได้ทันที ไม่ต้องโทรถาม"
  CTA 1:   "ดูห้องว่างตอนนี้ ↓"  → anchor #homepage-availability
  CTA 2:   "จองห้อง →"            → /book/

Guest:
  eyebrow: "ระบบจองและบริหารการใช้ห้อง รร.ส.สส."
  h1:      "สถานะห้องและที่พักวันนี้"
  sub:     "ตรวจสอบห้องที่ว่างอยู่จริง — เข้าสู่ระบบเพื่อจอง"
  CTA 1:   "เข้าสู่ระบบ →"  → /accounts/login/?next=/book/
  CTA 2:   "จองห้องพัก →"   → /lodging/
```

### Entry Cards
- ลบ `<span aria-hidden="true">01</span>` (02/03/04)
- คง `hud-tag` category label ที่มีความหมาย

### Availability Section
- เพิ่ม `id="homepage-availability"` ที่ `<section class="homepage-availability">`
- เพิ่ม `.avail-status-badge` pill "ว่างอยู่" (green, static)
- `homepage-room-card` grid: `5rem minmax(0,1fr) auto`

### Status Band — เรียงลำดับใหม่ใน template
1. ว่างตอนนี้ (green) — `stat_free_now`
2. กำลังใช้งาน (cyan) — `stat_in_use`
3. Mission Clock / รออนุมัติ

### Guest Banner
- ลบ `hud-tag "Guest Access"`
- เปลี่ยน h3 → h2 พร้อม copy สุภาพ

### Calendar JS — mobile headerToolbar
เพิ่ม `timeGridWeek` option ใน mobile toolbar right:
```js
headerToolbar: compact
  ? {left: 'prev,next', center: 'title', right: 'today,timeGridWeek'}
  : {left: 'prev,next today', center: 'title', right: 'timeGridDay,timeGridWeek,dayGridMonth'},
```
`initialView` คงเดิม (`timeGridDay` บน mobile)

### CSS ใหม่ (UI-2 section)
- `.hero-section`, `.hero-headline`, `.hero-sub`, `.hero-actions`
- `.avail-status-badge` pill
- responsive: hero CTA full-width ≤ 480px

---

## 6. Definition of Done

- [ ] หน้า `/` ไม่มีข้อมูลซ้ำที่เด่นกว่า task หลัก "หาห้องว่าง"
- [ ] Primary CTA เห็นได้ **โดยไม่ scroll** บน desktop 1280px และ mobile 390px
- [ ] Viewport ตรวจครบ: 360 / 390 / 430 / 768 / 1280 / 1440
- [ ] Guest + authenticated requester ตรวจจริง
- [ ] Approver + Custodian ตรวจจริง (role-actions ยังแสดงถูก)
- [ ] `uv run pytest` — **all tests PASS; บันทึกจำนวนจริง ณ เวลารัน** (baseline ≈180 แต่ไม่ lock เป็น invariant เพราะ stacked PR อาจเปลี่ยน) — ห้ามแก้ test เพียงเพราะ markup เปลี่ยน
- [ ] `uv run manage.py check` — PASS
- [ ] `makemigrations --check --dry-run` — No changes detected
- [ ] `git diff --check` — PASS
- [ ] Lodging calendar: non-clickable semantics คงอยู่ (QA จริงทุก viewport)
- [ ] Booking event click ใน calendar ยังทำงาน (ทุก viewport)
- [ ] ไม่มี page-level horizontal overflow ในทุก viewport
- [ ] Touch targets ≥ 44px สำหรับ hero CTA และ availability book button
- [ ] PR diff อ่านซ้ำหลัง push ก่อน report complete

---

## 7. Verification Plan

```powershell
uv run manage.py check
uv run manage.py makemigrations --check --dry-run
uv run pytest bookings/ --tb=short -q        # targeted
uv run pytest --tb=short -q                  # full regression
git diff --check
```

**Browser QA:** Guest / Requester / Approver / Custodian  
**Viewports:** 360 / 390 / 430 / 768 / 1280 / 1440  
**Pages:** `/` / `/book/` / `/approvals/` / `/usage/`

---

## 8. Out of Scope

- Booking form flow (UI-3)
- Lodging visual redesign (UI-4)
- Full a11y/performance audit (UI-5)
- `views.py`, services, models, migrations
- เพิ่ม FullCalendar plugin ใหม่
- Merge PR #16 / #17
