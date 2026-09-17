# SIGROOM UX-15 — Lodging Check-in Mobile Clarity & Privacy

Status: IMPLEMENTED & VERIFIED (READY FOR REVIEW)
Date: 2026-09-18

## Verified Base

- Repository: `saisansan11/sigroom`
- Base commit: `47d77062b591529d604aa2db462a6f4f16963022` (Merge pull request #37 from saisansan11/feat/ux-14-lodging-cohort-edit-mobile)
- Base branch: `origin/feat/lodging-v5-2`
- Active branch: `feat/ux-15-lodging-checkin-mobile`
- Isolated worktree: `C:\Users\RTA\Documents\ChatGPT-Antigravity\worktrees\sigroom-ux15-checkin-mobile`

## Evidence & Problem Analysis

1. **Squashed Key-Value Rows on Mobile (<768px)**:
   In `checkin.html`, `.checkin-details-row` used a fixed desktop flex layout with label `width: 38%` and value `width: 62%` right-aligned. At 360px viewport width, the value column had only ~155px of width. Multi-line content (long cohort titles, unit names, health notes) ballooned in height (~128px) in an unnatural, hard-to-read right-aligned column.
2. **Room Pill Multi-line Wrapping at 360px**:
   The room indicator `.checkin-room-pill` (`padding: .35rem 1.2rem; font-size: 1.15rem;`) wrapped across two lines on 360px viewports, reaching 65px in height and crowding above-the-fold content.
3. **Suboptimal List Semantics**:
   The details container was a generic `<div class="checkin-details-list">` with `<span>` children. Using semantic `<dl class="checkin-details-list">`, `<dt class="checkin-details-label">`, and `<dd class="checkin-details-value">` with an explicit `aria-label="รายละเอียดการรายงานตัว"` provides standard screen reader and assistive technology affordances.
4. **Touch Targets and Focus Visibility**:
   On mobile, action links (such as telephone links and the "กลับไปที่บัตรดิจิทัล" secondary link) lacked guaranteed >=44px minimum touch targets and visible `:focus` / `:focus-visible` styling (`outline: none` in Pico defaults).
5. **Breakpoint Alignment**:
   While the repository utilizes both `30rem` and `47.99rem` for different components, UX-15 selected `47.99rem` (<768px) for this check-in card component to align with the modern UI-refresh standard.

## Goals & Scope

### In Scope

1. **Presentation update in `templates/lodging/checkin.html`**:
   - Upgrade details list to semantic `<dl class="checkin-details-list" aria-label="รายละเอียดการรายงานตัว">`.
   - Wrap each item in `<div class="checkin-details-row">` containing `<dt class="checkin-details-label">` and `<dd class="checkin-details-value">`.
   - Add `.checkin-phone-link` class to telephone anchor.
   - Add `.checkin-footer-btn` class to the back-to-digital-pass anchor.
   - Strictly preserve all template logic: privacy masking for anonymous view (`masked_label`, no unit/phone/submit button), full details for supervisors (`student.rank`, `student.full_name`, `student.origin_unit`, `student.phone`, confirm check-in form), and checked-in success notices.
2. **CSS update in `static/css/app.css`**:
   - Add zero-margin reset for `dt` and `dd` (`margin: 0;`).
   - Add visible focus outline rules (`outline: 2px solid var(--cyan) !important; outline-offset: 2px !important; box-shadow: ...`) for check-in buttons and links.
   - Add scoped `/* UX-15 Lodging Check-in Mobile Clarity */` section under `@media (max-width: 47.99rem)`:
     - Stack `.checkin-details-row` into vertical column (`flex-direction: column; align-items: flex-start;`).
     - Set label and value to `width: 100%; text-align: left;`.
     - Apply `overflow-wrap: anywhere;` for natural Thai text wrapping.
     - Adjust `.checkin-room-pill` font and padding for compact single-line rendering at 360px (`height < 50px`).
     - Enforce min-height >= 44px for submit button, footer button, and mobile phone link.
3. **Automated tests in `bookings/tests_ux15.py`**:
   - 8 focused contract tests covering DOM semantics, footer navigation, single-template integrity, CSS breakpoint `47.99rem`, dl/dt/dd reset, focus visible styling, mobile layout contracts, and URL/view contracts.
4. **Verification Gates**:
   - Targeted pytest (`tests_ux15.py`, `tests_v6_b.py`, `tests_ui4.py`, `tests_ux14.py`, `tests_guest_and_lodging.py`, `tests_lodging_v4.py`).
   - `uv run manage.py check`.
   - `uv run manage.py makemigrations --check --dry-run`.
   - Full regression suite `uv run pytest -q` (348 passed).
   - `git diff --check`.
   - Real-route Browser QA (`ux15_browser_real_qa.mjs`) against live Django test server with headless Chrome CDP across 360, 390, 430, 768, 1280, 1440 px viewports and real POST check-in mutation.
5. **Documentation & Handoff**:
   - Write `docs/plans/2026-09-18-ux-15-lodging-checkin-mobile.md` and `docs/handoffs/2026-09-18-ux-15-lodging-checkin-mobile.md`.

### Out of Scope / Non-Goals

- No changes to `bookings/lodging_views.py`, `lodging_services.py`, models, URLs, or backend permissions.
- No changes to `select_for_update()` concurrency control or duplicate check-in prevention.
- No commit, push, PR creation, merge, or touching `F:\ogn_ROOM`.
- Local QA scripts and rendered test files remain untracked and uncommitted.

## Hard Invariants

1. Privacy invariants: anonymous/public users must NEVER see full name, phone number, origin unit, or check-in confirmation button.
2. Authorization invariants: check-in POST must reject unauthorized users with 403.
3. Desktop layout (>=768px / 48rem) must remain 2-column side-by-side with right-aligned values.
4. Mobile max-width breakpoint is `47.99rem`.
5. No duplicate mobile template or split template logic.
6. Untracked local QA scripts and artifacts must not be staged or committed.
