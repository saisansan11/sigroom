# SIGROOM UX-14 — Lodging Cohort Edit Mobile Clarity & Accessibility

Status: IMPLEMENTED & VERIFIED (READY FOR REVIEW)
Date: 2026-09-17

## Verified Base

- Repository: `saisansan11/sigroom`
- Base commit: `16cfb36247bea59fdddcbc06056b0bc442379b58` (Merge pull request #36 from saisansan11/feat/ux-3-my-bookings-tracking)
- Base branch: `feat/lodging-v5-2`
- Active branch: `feat/ux-14-lodging-cohort-edit-mobile`
- Isolated worktree: `C:\Users\RTA\Documents\ChatGPT-Antigravity\worktrees\sigroom-ux14-discovery`

## Evidence & Problem Analysis

1. **Invalid HTML Nesting & Accessibility Violation**:
   `templates/lodging/cohort_edit.html` (lines 48–59) wraps the entire room checklist in an outer `<label>ห้องพักที่จัดสรรในรอบนี้ <div class="lodging-room-checklist">...<label class="lodging-checklist-item">...</label>...</div></label>`. Nesting `<label>` elements is invalid HTML and confuses assistive technologies, whereas UX-13 normalized the create form in `manage_list.html` to a semantic `<fieldset class="lodging-room-fieldset">` and `<legend>`.
2. **Missing Batch Room Selection Affordances**:
   Supervisors editing an active lodging cohort must toggle each room individually. There are no "Select all" or "Deselect all" controls, making batch modification tedious and error-prone.
3. **Date Grid Layout Squashing Below 48rem**:
   The date picker grid (`.grid-dates`) uses a 2-column layout (`grid-template-columns: 1fr 1fr;`). In `app.css`, single-column collapse was historically only defined below 30rem (480px), squashing date pickers on standard mobile and small tablet viewports between 480px and 767px (<48rem). UX-13 addressed this for `.lodging-manage-grid .grid-dates`, but `cohort_edit.html` is inside `.lodging-edit-card`, leaving it squashed.
4. **Touch Targets & Focus Visibility**:
   Room checklist items, standalone checkbox labels (`.lodging-checkbox-label`), and form actions need guaranteed minimum touch targets of >=44px and visible keyboard focus (`:focus-visible` / `:focus-within`) for WCAG 2.1 AA compliance.
5. **Narrow-Screen Readability & Danger Zone Presentation**:
   On mobile viewports (360px–430px), long Thai cohort titles, danger zone warnings, and form action buttons ("ยกเลิก" / "บันทึกการเปลี่ยนแปลง") need safe text wrapping and full-width mobile action stacking without altering backend authorization, CSRF, or POST semantics.

## Goals & Scope

### In Scope

1. **Presentation update in `templates/lodging/cohort_edit.html`**:
   - Replace outer invalid `<label>` with semantic `<fieldset class="lodging-room-fieldset">` and `<legend>ห้องพักที่จัดสรรในรอบนี้</legend>`.
   - Add accessible "เลือกทั้งหมด" and "ยกเลิกทั้งหมด" button controls (`type="button"`, `.lodging-selection-btn`) in `.lodging-room-selection-tools`.
   - Add minimal vanilla JS function `setRoomCheckboxes(checked)` scoped strictly to the room checklist inside `cohort_edit.html`.
   - Preserve all existing form fields, input types, attributes, selected/checked states, and exact POST field names:
     - `title`
     - `check_in_date`
     - `check_out_date`
     - `allocation_status`
     - `beds_per_room`
     - `is_active`
     - `rooms` (getlist)
     - `note`
     - `force_release` (superuser danger zone)
     - `release_reason` (superuser danger zone)
   - Preserve superuser-only boundary (`{% if user.is_superuser %}`) for the danger zone.
   - Clarify action hierarchy ("ยกเลิก" secondary link, "บันทึกการเปลี่ยนแปลง" primary submit).
2. **CSS update in `static/css/app.css`**:
   - Add scoped `/* UX-14 Lodging Cohort Edit Mobile Clarity */` section.
   - Reuse existing UX-13 tokens and patterns where available (`.lodging-room-fieldset`, `.lodging-selection-btn`, `.lodging-room-checklist`).
   - Define mobile breakpoint strictly as `@media (max-width: 47.99rem)` (desktop >=768px / 48rem unchanged).
   - Ensure `.lodging-edit-card .grid-dates` collapses to 1 column below 48rem.
   - Ensure full-width and minimum 44px touch targets for `.lodging-edit-card .form-actions`.
   - Ensure minimum 44px touch target and keyboard focus for `.lodging-edit-card .lodging-checkbox-label`.
   - Improve danger zone mobile padding and safe text wrapping for Thai headers and warning messages.
   - Strictly avoid `:has()` selector.
3. **Automated tests in `bookings/tests_ux14.py`**:
   - Permission boundaries: anonymous redirects to login; unrelated users receive 403; cohort supervisor and users with change permission receive 200; superuser sees danger zone.
   - Danger zone isolation: normal supervisors never see danger zone controls or fields (`force_release`, `release_reason`); superuser sees danger zone and can submit force release.
   - Exact POST contracts: verify all fields submit and persist correctly.
   - HTML semantics: fieldset and legend present; no nested outer `<label>` wrapping checklist.
   - Selection tools: Select all / Deselect all buttons present, `type="button"`, strictly scoped JS selector.
   - CSS contracts: UX-14 marker present; breakpoint `47.99rem`; no `:has()` selector; touch targets >=44px; single-column dates below 48rem.
   - Business logic integrity: models, views, URLs, services unchanged.
4. **Verification Gates**:
   - Targeted pytest (UX-14, UX-13, UX-12, lodging v4, guest/lodging).
   - `uv run manage.py check`.
   - `uv run manage.py makemigrations --check --dry-run`.
   - Full regression suite `uv run pytest -q`.
   - `git diff --check`.
   - Real Browser QA using headless Chrome CDP across 360, 390, 430, 768, 1280, 1440 px viewports.
5. **Documentation & Handoff**:
   - Write `docs/handoffs/2026-09-17-ux-14-lodging-cohort-edit-mobile.md` with observed evidence.

### Out of Scope / Non-Goals

- No modification to `bookings/lodging_views.py`, `lodging_services.py`, `models.py`, `urls.py`, `settings.py`, or database migrations.
- No change to allocation algorithms, conflict checks, or transaction handling.
- No changes to UX-13 files or test contracts.
- No commit, push, PR creation, merge, or touching `F:\ogn_ROOM`.

## Hard Invariants

1. Authorization must remain server-side: normal supervisors cannot access danger zone actions.
2. Form POST parameter names must match exactly: `title`, `check_in_date`, `check_out_date`, `allocation_status`, `beds_per_room`, `is_active`, `rooms`, `note`, `force_release`, `release_reason`.
3. Desktop layout (>=768px / 48rem) must remain visually and functionally unchanged.
4. Mobile max-width breakpoint is `47.99rem` (never `48rem`).
5. No `:has()` pseudo-class in CSS.
6. Untracked local QA scripts or outputs must not be staged.

## Branch & Worktree Strategy

- Base: `feat/lodging-v5-2` @ `16cfb36`
- Worktree branch: `feat/ux-14-lodging-cohort-edit-mobile`
- Isolated working directory: `C:\Users\RTA\Documents\ChatGPT-Antigravity\worktrees\sigroom-ux14-discovery`
