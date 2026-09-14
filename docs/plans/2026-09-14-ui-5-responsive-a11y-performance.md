# SIGROOM UI-5 Implementation Plan — Responsive / Accessibility / Performance Sweep

## Status
`IMPLEMENTATION & VERIFICATION COMPLETE — READY FOR PR`

## Overview
Phase UI-5 is the final phase of the SIGROOM UI Refresh. It performs a comprehensive, system-wide sweep of responsive design, accessibility (WCAG AA), and performance across all user personas:
1. **Guest / Public**: Homepage / calendar, room availability, lodging index, public masked check-in, masked booking detail, login.
2. **Student Lodging**: Lodging cohort portal, room cards & photo gallery modal, bed selection modal, digital key-card pass (flip & LINE share).
3. **Supervisor / Staff**: Cohort management, create cohort, cohort detail with master roster table, edit cohort with force-release danger zone, check-in verification.
4. **General Booking User**: Quick booking search, date/time picker, category tabs, booking form (steps 1–5), my bookings tabs, booking detail.
5. **Approver**: Approval queue (standard, series, amendments), approve/reject modal workflows, delegation management.
6. **Custodian / Room Manager**: Usage list & update workflows, monthly reports dashboard, outage management.

Target viewports to verify: **360, 390, 430, 768, 1280, 1440 px**.

---

## 1. Scope of Improvements

### 1. Responsive & Overflow Hardening (360px to 1440px)
- **Guest Mobile Header Navigation**:
  - In `templates/base.html`, unauthenticated guests at `<= 68rem` currently lose direct navigation between "สถานะห้องวันนี้" and "จองห้องพัก".
  - Provide accessible, mobile-friendly navigation for guests with accurate `aria-current="page"` conditional highlights.
- **Mobile Menu Semantics**:
  - Add missing `aria-current="page"` indicators for lodging links in authenticated mobile menu.
- **Sticky Booking Submit Bar Margin**:
  - In `static/css/app.css`, ensure `.booking-submit-bar` negative inline margin cannot produce horizontal scrolling on narrow screens (360px).
- **Responsive Tables & Containers**:
  - Verify `.table-wrap`, `.table-scroll`, and `.table-responsive-container` preserve smooth touch scroll (`-webkit-overflow-scrolling: touch`) and scrollbar visibility across all screens.
- **Room Availability & Search Cards**:
  - Ensure `.homepage-room-card` and `.room-card` gracefully wrap metadata and actions on narrow mobile viewports (360px/390px) without text clipping or button overflow.

### 2. Accessibility (a11y) & WCAG AA Compliance
- **Touch Target Sizing (>= 44x44px / 2.75rem)**:
  - `.category-pill`: Increase minimum height to 2.75rem for easy tapping on mobile.
  - `.fav-button`: Enforce 44x44px (`min-width: 2.75rem; min-height: 2.75rem`) touch target area.
  - `.compact-button`: On touch/mobile viewports (`<= 50rem`), scale to 44px min-height for reliable row actions.
  - `.room-gallery-nav`: Enforce >= 44px touch target (2.75rem).
  - `#roomGalleryDialog` close button and modal dismiss controls: Ensure full 44px touch hit-box.
- **Keyboard Navigation & Focus Management**:
  - Ensure high-visibility `:focus-visible` rings on all interactive elements.
  - Ensure gallery modal (`#roomGalleryDialog`) supports keyboard navigation (`ArrowLeft`, `ArrowRight`, `Escape`).
  - Ensure digital key-card pass supports keyboard flip (`Enter`, `Space`) with live `aria-pressed` and `aria-label` updates.
  - Ensure category pills communicate active state via `aria-pressed` or `aria-current`.
  - Ensure form error indicators properly focus field on error via `data-scroll-on-swap` and DOMContentLoaded autofocus.
- **Color Contrast & Legibility**:
  - Verify all typography and badge tints meet WCAG AA standards (>= 4.5:1 for normal text, >= 3:1 for large text and UI components).
  - Ensure Thai typography rendering has proper `line-height` and avoids awkward word breaks.
- **Reduced Motion**:
  - Maintain comprehensive `@media (prefers-reduced-motion: reduce)` disabling non-essential transitions, 3D flips, and animations, with `scroll-behavior: auto` in both CSS and JavaScript.

### 3. Performance & Layout Shift (CLS) Optimization
- **Restoration of Missing Lodging Gallery CSS**:
  - Re-add and optimize `.room-photo-wrap`, `.room-photo-cover`, `.room-photo-trigger`, `.room-gallery-viewport`, `.room-gallery-nav` with explicit aspect ratios (16:9 for covers, 4:3 for gallery viewport) to eliminate layout shifts.
- **Image Attributes**:
  - Add explicit `width`, `height`, `loading="lazy"`, and `decoding="async"` across thumbnail images (`room-card-thumb`, `tl-room-thumb`, `keycard-qr`, etc.) to guarantee zero Cumulative Layout Shift (CLS).
- **Font Rendering**:
  - Verify `fonts.css` maintains `font-display: swap` for instant text rendering without FOIT (Flash of Invisible Text).

---

## 2. Invariants & Non-Goals

- **Zero Database / Schema Changes**: No migrations (`makemigrations --check --dry-run` must produce 0 changes).
- **Zero Business Logic Mutations**: Conflict detection, transaction locks, phone deduplication, permission matrices, and calendar reservation semantics remain completely untouched.
- **Privacy Model Invariant**: Public and student views never expose roommate names, ranks, units, or phone numbers.
- **Out of Scope**:
  - No new backend models or fields.
  - No deployment or infrastructure changes.
  - No modifications to untracked files (`.claude/handoffs/`, `.tmp/`).

---

## 3. Targeted Test & Verification Plan

1. **Automated Tests**:
   - Create `bookings/tests_ui5.py` to assert:
     - Guest mobile navigation markup and correct `aria-current="page"` semantics.
     - Image tags have `loading="lazy"` and `decoding="async"`.
     - Touch targets and CSS rules exist for gallery, favorites, category pills, and compact buttons.
     - Reduced motion rules and keyboard accessibility hooks.
   - Run targeted test suites:
     - `uv run pytest bookings/tests_ui5.py bookings/tests_ui4.py bookings/tests_guest_and_lodging.py -q`
   - Run system gates:
     - `uv run manage.py check`
     - `uv run manage.py makemigrations --check --dry-run`
     - Full regression suite: `uv run pytest --tb=short -q` (must match or exceed 191 passed baseline)
     - `git diff --check`
2. **Browser QA Across All Target Viewports (360, 390, 430, 768, 1280, 1440 px)**:
   - **Guest / Public**:
     - Homepage `/` (`bookings:calendar`): check hero, availability, category pills, today board, calendar, guest banner.
     - Lodging Index `/lodging/`: check cohort cards, progress bars, select button.
     - Public Masked Check-in `/lodging/checkin/<id>/`: check masked card and responsive layout.
     - Login page `/login/`: check radar visual, form inputs, focus ring.
   - **Student Lodging**:
     - Student Portal `/lodging/c/<slug>/`: check room cards, cover photos, gallery modal open/prev/next/close, bed modal open/close.
     - Student Digital Pass `/lodging/pass/<slug>/<id>/`: check 3D keycard flip on click and keyboard (Space/Enter), LINE share button, clipboard copy.
   - **Supervisor / Staff**:
     - Lodging Manage `/lodging/manage/`: check cohorts list and create form side-by-side on desktop, single-column on mobile.
     - Cohort Detail `/lodging/cohort/<slug>/manage/`: check share banner, metrics, room grid, responsive roster table.
     - Cohort Edit `/lodging/cohort/<slug>/edit/`: check edit fields and superuser danger zone.
     - Staff Check-in `/lodging/checkin/<id>/`: check authorized details view and check-in confirmation button.
   - **Regular Booking User**:
     - Search `/search/`: stepper, date/time, presets, equipment details, room list, favorite buttons.
     - Book Form `/book/<room>/`: stepper, booking summary, review section, sticky submit bar.
     - My Bookings `/my/`: tabs, table with horizontal scroll, compact actions.
     - Booking Detail `/booking/<id>/`: status hero card, details dl/dd grid.
   - **Approver**:
     - Queue `/approvals/queue/`: cards, comparison grids, approve button, reject dropdown form.
   - **Custodian**:
     - Usage `/usage/`: usage list table, inline action buttons.
     - Reports `/reports/dashboard/`: monthly filters, report tables with scroll.

---

## 4. Verification Results

- **Targeted Tests**:
  `uv run pytest bookings/tests_ui5.py bookings/tests_ui4.py bookings/tests_guest_and_lodging.py -q`
  Result: **17 passed, 2 warnings** in 4.92s.
- **Django Check**:
  `uv run manage.py check`
  Result: **System check identified no issues (0 silenced)**.
- **Migration Check**:
  `uv run manage.py makemigrations --check --dry-run`
  Result: **No changes detected**.
- **Full Regression Suite**:
  `uv run pytest --tb=short -q`
  Result: **197 passed, 2 warnings** in 39.01s (increased from 191 baseline by 6 new UI-5 tests).
- **Git Diff Whitespace Check**:
  `git diff --check`
  Result: **PASS (clean)**.
- **Real Browser QA Matrix (Chrome CDP)**:
  - 16 pages across Guest, Student Lodging, Supervisor, Booking User, Approver, and Custodian personas.
  - 6 viewports tested: **360, 390, 430, 768, 1280, 1440 px** (total 96 combinations).
  - Horizontal overflow count: **0 (Zero)** across all viewports and routes.
  - Interactive exercises:
    - Guest mobile menu toggle & page navigation links at 360px: Verified.
    - Student booking modal open from bed CTA at 360px, input heights (51px >= 44px min), and focus trapping/restoration: Verified.
    - Student digital pass 3D keycard click flip (`aria-pressed="true"`) and keyboard Enter flip (`aria-pressed="false"`): Verified.
