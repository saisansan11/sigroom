# SIGROOM UX-13 — Lodging Cohort Management Mobile Clarity

Status: IMPLEMENTATION COMPLETE / VERIFIED (ChatGPT Review Passed)
Date: 2026-09-17

## Verified base

- Repository: `saisansan11/sigroom`
- Base branch: `feat/lodging-v5-2`
- Base commit: `2f7a6f88cb0faebc9cb7d3fffc10c0e7ef466020` (merge of PR #34 / UX-12)
- UX-13 branch: `feat/ux-13-lodging-cohort-management-mobile`
- Isolated worktree: `C:\Users\RTA\Documents\ChatGPT-Antigravity\worktrees\sigroom-ux13-lodging-cohort-management-mobile`

## Evidence / problem

1. In `templates/lodging/manage_list.html`, each cohort management card only provides "ดูรายชื่อนักเรียน →", "แก้ไข", and "เปิดหน้านักเรียน ↗". Supervisors who need to quickly distribute registration links to student LINE groups must navigate to the detail page first, whereas other lodging views already offer direct copy and LINE share affordances.
2. On mobile viewports (<768px), cohort card actions are not mobile-optimized: primary action is not full width, and secondary touch targets are inconsistent (<44px).
3. Long Thai cohort titles and status badges in card headers can wrap awkwardly or risk clipping on narrow screens (360–430px).
4. The room checklist in the create cohort form has invalid HTML semantics: an outer `<label>` wraps inner `<label class="lodging-checklist-item">` elements, which is invalid HTML and violates accessibility standards.
5. Supervisors must toggle room checkboxes individually with no accessible "Select all" / "Deselect all" controls, which is tedious when managing batches of dorm rooms.
6. Individual room checklist items lack guaranteed 44px minimum touch targets and explicit keyboard focus visibility.
7. The check-in / check-out date grid (`.grid-dates`) uses a 2-column layout that squashes date picker inputs on 480–767px viewports (below 48rem).

## Goal

Enhance `templates/lodging/manage_list.html` and `static/css/app.css` for mobile clarity, accessibility, and speed of operational task completion, while strictly preserving desktop layout (>=768px), form bindings, and backend authorization.

## Scope

### 1. Template (`templates/lodging/manage_list.html`)

- **Student-portal link affordances on cohort cards**:
  - Add "📋 คัดลอกลิงก์" button with copy feedback (`✓ คัดลอกสำเร็จ!`, `.is-copied`) and fallback for non-secure / legacy contexts.
  - Add "แชร์ผ่าน LINE ↗" link (`target="_blank" rel="noopener noreferrer"`) using the existing `lodging_portal` route pattern (`line.me/R/share?text=...`).
  - No server or API changes required.
- **Card action hierarchy & touch targets**:
  - Primary action ("ดูรายชื่อนักเรียน →") styled for full-width presentation on mobile screens.
  - Secondary action touch targets >=44px.
  - Preserve desktop (>=768px) inline flex layout.
- **Title & badge wrapping**:
  - Long Thai titles and status tags wrap safely without clipping on narrow screens.
- **Semantic room checklist**:
  - Replace invalid outer `<label>` with `<fieldset class="lodging-room-fieldset">` and `<legend>`.
  - Preserve exact POST field name `name="rooms"` and checkbox values.
- **Select all / Deselect all controls**:
  - Accessible toolbar with "เลือกทั้งหมด" and "ยกเลิกทั้งหมด" buttons (`type="button"`).
  - Minimal, framework-free vanilla JavaScript scoped strictly to `.lodging-room-checklist input[name="rooms"]`, never affecting other checkboxes.
- **Date grid responsiveness**:
  - Ensure `.grid-dates` collapses to a single column below 48rem (max-width: 47.99rem) so 480–767px does not squash date controls.
- **Explicit exclusions**:
  - DO NOT add quick-jump or task bar (out of approved scope).

### 2. CSS (`static/css/app.css`)

- Add scoped `/* UX-13 Lodging Cohort Management Mobile Clarity */` section:
  - Semantics-neutral resets for `<fieldset class="lodging-room-fieldset">` and `<legend>`.
  - Room checklist item touch target >=44px (`min-height: 44px`) and keyboard focus visibility (`:focus-visible`, `:focus-within`).
  - Selection tools styling on desktop and mobile.
  - Mobile query `@media (max-width: 47.99rem)`:
    - Card header flex column / wrapping for long Thai titles and status badges.
    - Card actions grid / full-width primary action and >=44px secondary touch targets.
    - `.grid-dates` 1 column layout.
    - Room selection buttons full width / touch-safe.
  - Strict constraints: No `:has()` selector, no broad unrelated cleanup, desktop (>=768px) layout preserved.

### 3. Tests (`bookings/tests_ux13.py`)

- Protect permission boundaries:
  - Anonymous user redirects to login.
  - User with `can_create=True` (or superuser) can view and submit create form.
  - User with `can_create=False` can view assigned cohorts but cannot see create form and cannot POST.
  - Unrelated user cannot manage cohorts.
- Protect template semantics:
  - Verify semantic `<fieldset>` and `<legend>` for room checklist; no nested `<label>` in outer `<label>`.
  - Verify exact `name="rooms"` checkboxes.
  - Verify Select all / Deselect all button affordances and JS scope.
  - Verify copy button, feedback text, fallback, and LINE share links on cohort cards.
- Protect CSS contracts:
  - Verify UX-13 CSS marker.
  - Verify breakpoint `47.99rem` (and no `48rem`).
  - Verify date grid 1-column contract below 48rem.
  - Verify touch targets >=44px for primary action, secondary actions, and room checklist items.
  - Verify no `:has()` selector anywhere in UX-13 CSS.

### 4. Handoff (`docs/handoffs/2026-09-17-ux-13-lodging-cohort-management-mobile.md`)

- Record verified results, diff, test counts, and browser QA evidence.

## Hard invariants

- Do not edit `bookings/lodging_views.py`, services, models, URLs, settings, migrations, `cohort_detail.html`, UX-12 tests, or business rules.
- Do not rename form POST fields (`title`, `slug`, `check_in_date`, `check_out_date`, `beds_per_room`, `rooms`, `note`).
- Stage only the 5 approved release files (`templates/lodging/manage_list.html`, `static/css/app.css`, `bookings/tests_ux13.py`, `docs/plans/2026-09-17-ux-13-lodging-cohort-management-mobile.md`, `docs/handoffs/2026-09-17-ux-13-lodging-cohort-management-mobile.md`).
- Do not stage or delete QA artifacts (`ux13-manage-plain-qa.html`, `ux13-manage-qa.html`, `ux13_browser_qa.mjs`, `ux13_qa_render.py`).
- No unrelated formatting or cleanup.
- DO NOT MERGE without explicit user instruction.

## Verification gates & Recorded Evidence

1. Independent diff self-review: **PASS** (passed independent ChatGPT review and Antigravity release diff review).
2. Targeted pytest:
   `uv run pytest -q bookings/tests_ux13.py bookings/tests_ux12.py bookings/tests_guest_and_lodging.py bookings/tests_lodging_v4.py`
   Result: **79 passed, 33 warnings**
3. Django system check:
   `uv run manage.py check`
   Result: **0 issues**
4. Migration check:
   `uv run manage.py makemigrations --check --dry-run`
   Result: **No changes detected**
5. Git diff check:
   `git diff --check`
   Result: **PASS**
6. Full regression test suite:
   `uv run pytest -q`
   Result: **316 passed, 145 warnings in 87.32s**
7. Real Browser QA:
   `node ux13_browser_qa.mjs`
   Result: **PASS** across viewports `360`, `390`, `430`, `768`, `1280`, `1440`:
   - No horizontal overflow
   - Mobile primary CTA full width
   - Secondary controls and touch targets >=44px
   - Semantic `<fieldset>` and `<legend>` present
   - Select all / Deselect all functions correctly
   - Copy button feedback works (`✓ คัดลอกสำเร็จ!`)
   - LINE link share URL valid
   - Visible keyboard focus outlines present
   - No console errors, runtime exceptions, or failed requests
