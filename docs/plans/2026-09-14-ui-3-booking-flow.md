# SIGROOM UI-3 Implementation Plan — Booking Flow Redesign

## Status
`READY FOR FINAL REVIEW`

## Overview
Phase UI-3 focuses on transforming the SIGROOM booking flow into a clear, predictable, 5-step operational journey:
**เวลา → ห้อง → รายละเอียด → ตรวจสอบ → ยืนยัน** (Time → Room → Details → Review → Confirmation)

This is a **presentation and user-experience improvement** phase. All underlying booking business rules, database constraints (`ExclusionConstraint`), permissions, and validation semantics remain untouched and strictly preserved.

---

## 1. Scope & Architecture

### Step Mapping
1. **Step 1 — เวลา (Time)**: `/book/` (`templates/bookings/book_search.html`)
2. **Step 2 — ห้อง (Room)**: HTMX result (`templates/bookings/partials/room_list.html`)
3. **Step 3 — รายละเอียด (Details)**: `/book/<room>/` (`templates/bookings/book_form.html`, `templates/bookings/partials/booking_fields.html`)
4. **Step 4 — ตรวจสอบ (Review)**: Pre-submit review region at the end of booking form (`booking_fields.html` / `series_preview.html`)
5. **Step 5 — ยืนยัน (Confirmation)**: Booking detail response (`templates/bookings/booking_detail.html`)

### Non-Goals / Invariants Preserved
- No business logic rewrites in `bookings/services.py` or `bookings/models.py`.
- No database migrations (`makemigrations --check --dry-run` must produce 0 changes).
- 15-minute slot validation, time window, allowed units, blackout, room/equipment conflicts, buffer before/after, database exclusion constraints, regular booking ↔ lodging cohort conflict, and approval policy remain intact.
- Existing prefill mechanisms (`frequent_values`, user defaults, rebook parameters) remain intact.
- Series booking behavior, conflict detection, and preview/creation semantics remain intact.
- Shift-next-slot recovery action remains intact.
- Public/guest vs authenticated requester permissions remain intact.

---

## 2. Key Components & Implementation Steps

### 2.1 Reusable Booking Stepper
- File: `templates/bookings/partials/booking_stepper.html`
- Component indicating steps 1 through 5 with states: `completed`, `current`, `upcoming`.
- Accessible markup: `<nav class="booking-stepper" aria-label="ขั้นตอนการจองห้อง">`, `<ol class="booking-stepper-list">`, `aria-current="step"`.
- Mobile responsive: Compact format on <= 480px / 360px without horizontal overflow.
- No continuous decorative animations.

### 2.2 Step 1: Search Time (`book_search.html`)
- Stepper integration (Step 1 active).
- Form hierarchy: Date → Start Time → End Time → Attendees → Quick Presets.
- Equipment filter under progressive disclosure `<details class="search-equipment-details">` (auto-open if equipment codes already selected).
- Primary CTA: `ค้นหาห้องว่าง` (prominent, single primary CTA).
- HTMX search indicator: `กำลังตรวจสอบห้องและอุปกรณ์…` (stable layout).

### 2.3 Step 2: Room Results (`partials/room_list.html`)
- Stepper integration (Step 2 active).
- Each available room card (`.room-result-card`):
  - Room photo thumb with lazy loading and placeholder fallback.
  - Room title, building, floor, capacity.
  - Approval policy badge (`อนุมัติอัตโนมัติ` vs `ต้องผ่านผู้อนุมัติ`).
  - Capacity suitability warning with clear text (`⚠ ความจุน้อยกว่าจำนวนที่ระบุ`).
  - Primary CTA: `จองห้องนี้` (prominent button, touch target >= 44px).
  - Favorite toggle: Secondary utility, non-distracting.
- Unavailable rooms: Clean `<details class="unavailable-list">` with clear reasons.

### 2.4 Step 3 & 4: Details & Review (`book_form.html`, `partials/booking_fields.html`)
- Stepper integration (Step 3/4).
- Selected Room & Time Summary (Section A):
  - Prominent summary banner with room name, date (Thai format), start-end time, approval expectation, and change link.
- Section B (Activity): Title, Purpose, Attendees, Online meeting URL (when applicable).
- Section C (Responsible Person): Unit, Responsible Name, Phone.
- Section D (Additional Options): Progressive disclosure `<details class="form-more">` (auto-open if error or `form.has_more_data`).
- Section E (Step 4 Review Before Submit):
  - Dedicated `.booking-review-panel` summarizing room, date/time, approval expectation, and clear submission CTA:
    - Primary CTA: `ยืนยันและส่งคำขอ` (or `ยืนยันการจอง` when auto-approved).
    - Secondary CTA: `บันทึกร่าง` (if `show_draft`).
    - Series CTA: `ตรวจสอบชุดการจอง →` (if series enabled).
- Error handling: Clear inline field errors and top-level notices; preserve all user inputs.

### 2.5 Step 5: Confirmation / Booking Detail (`booking_detail.html`)
- Stepper integration (Step 5 complete).
- Prominent status hero card above the fold:
  - Approved: `อนุมัติแล้ว` with clear confirmation guidance.
  - Pending: `ส่งคำขอแล้ว · รอผู้อนุมัติ` with tracking guidance ("ติดตามสถานะได้จาก “การจองของฉัน”").
  - Draft / Rejected / Expired / Cancelled: Clear status banner and next steps.
- Clean technical specifications and approval history timeline.
- Action toolbar for Approver (`อนุมัติ`, `ปฏิเสธ`) and Requester (`แก้ไข`, `ขอแก้ไข`, `ยกเลิก`, `จองแบบเดิมอีกครั้ง`).

### 2.6 Series Booking & My Bookings
- `series_preview.html`: Step 4 Review for recurring bookings with clean occurrence status table and `จองเฉพาะครั้งที่ว่าง` CTA.
- `series_detail.html`: Clean mobile-friendly view.
- `my_bookings.html`: Filter tabs and responsive table/card container preventing page-level horizontal overflow.

### 2.7 CSS Architecture (`static/css/app.css`)
- Reusable classes under `/* ===== UI-3 Booking Flow ===== */`:
  - `.booking-stepper`, `.booking-stepper-list`, `.booking-step`
  - `.booking-selection-summary`, `.booking-review-panel`, `.booking-review-grid`
  - `.room-result-card`, `.room-result-actions`
  - `.booking-confirmation-hero`
- Ensure touch targets >= 44px, visible keyboard focus rings, no horizontal overflow at 360px viewport.

### 2.8 Form Presentation Attributes (`bookings/forms.py`)
- Enrich form widgets with `inputmode` ("numeric", "tel"), `autocomplete` ("name", "tel", "off"), and useful placeholders without changing validation rules.

---

## 3. Verification Plan

### Automated Verification
1. `uv run manage.py check`
2. `uv run manage.py makemigrations --check --dry-run` (must report no changes)
3. Targeted booking tests:
   ```powershell
   uv run pytest bookings/tests_m2.py bookings/tests_m4.py bookings/tests_m5.py bookings/tests_m6b.py bookings/tests_trial_round1.py -q
   ```
4. Full regression suite:
   ```powershell
   uv run pytest --tb=short -q
   ```
5. Code style and whitespace check:
   ```powershell
   git diff --check
   ```

### Real Browser QA Matrix
- Viewports: 360, 390, 430, 768, 1280, 1440 px.
- Personas & Flows:
  - **Authenticated Requester**:
    - Search `/book/` → Choose Date/Time → Room Results → Select Room → Fill Form → Review Step → Submit → Confirmation Detail (`/bookings/<id>/`).
    - Test validation errors, draft save, and shift-next-slot recovery.
    - Test series preview & confirmation if supported.
  - **Guest**:
    - Access `/book/` unauthenticated or homepage CTA → verify login redirection/prompt.
  - **Approver**:
    - Access pending booking detail → verify `อนุมัติ` / `ปฏิเสธ` actions remain visible and functional.
- Quality Checks:
  - No horizontal page overflow at 360px.
  - Touch targets >= 44px.
  - Visible keyboard focus.
  - Zero browser console errors.
