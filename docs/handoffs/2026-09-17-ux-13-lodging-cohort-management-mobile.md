# UX-13 Lodging Cohort Management Mobile Clarity — Handoff

Status: READY FOR PR

## Scope

Changed only the planned UX-13 source, test, and documentation scope:

- `templates/lodging/manage_list.html`
- `static/css/app.css`
- `bookings/tests_ux13.py`
- `docs/plans/2026-09-17-ux-13-lodging-cohort-management-mobile.md`
- `docs/handoffs/2026-09-17-ux-13-lodging-cohort-management-mobile.md`

No views, services, models, URLs, settings, migrations, allocation rules, or check-in business logic were changed.
QA artifacts (`ux13-manage-plain-qa.html`, `ux13-manage-qa.html`, `ux13_browser_qa.mjs`, `ux13_qa_render.py`) remain untracked for local verification and are strictly excluded from staging.

## Implementation

1. **Direct Student-Portal Link & Share Affordances on Cohort Cards**:
   - Added direct "📋 คัดลอกลิงก์" button with visual feedback (`✓ คัดลอกสำเร็จ!`, `.is-copied`) and fallback for non-secure / legacy contexts.
   - Added "แชร์ผ่าน LINE ↗" link (`target="_blank" rel="noopener noreferrer"`) formatted with cohort title and canonical student portal URL (`https://line.me/R/share?text=...`).
   - Retained "ดูรายชื่อนักเรียน →", "เปิดหน้านักเรียน ↗", and "แก้ไข" affordances.

2. **Mobile Card Action Hierarchy & Touch Targets**:
   - Mobile (<768px / max-width: 47.99rem): Primary CTA ("ดูรายชื่อนักเรียน →") spans full width (`grid-column: 1 / -1`, `width: 100%`, `min-height: 44px`).
   - Secondary actions styled in a 2-column grid with `min-height: 44px` and safe wrapping.
   - Desktop (>=768px): Inline flex layout preserved without regression.

3. **Safe Text Wrapping for Thai Cohort Titles & Badges**:
   - Long Thai titles configured with `overflow-wrap: anywhere; word-break: break-word;`.
   - Status tags set with `white-space: normal;` preventing layout clipping or horizontal overflow on 360–430px viewports.

4. **Semantic Room Checklist & Accessibility**:
   - Replaced invalid outer `<label>` wrapping inner labels with semantic `<fieldset class="lodging-room-fieldset">` and `<legend>เลือกห้องพักที่เปิดให้จองในรอบนี้</legend>`.
   - Preserved exact form field name `name="rooms"` and checkbox values.
   - Checklist items styled with guaranteed `min-height: 44px` touch targets and visible `:focus-within` / `:focus-visible` keyboard focus outlines.

5. **Select All / Deselect All Controls**:
   - Added accessible action toolbar with "เลือกทั้งหมด" and "ยกเลิกทั้งหมด" buttons (`type="button"`).
   - Scoped vanilla JavaScript function `setRoomCheckboxes(checked)` strictly to `.lodging-room-checklist input[type="checkbox"][name="rooms"]`, preventing side-effects on other forms.

6. **Responsive Date Grid**:
   - Scoped `.lodging-manage-grid .grid-dates` to collapse from 2 columns to a single column below 48rem (`@media (max-width: 47.99rem)`), eliminating squashed date picker inputs on 480–767px screens.

## Verification Evidence

All release gates verified and recorded:

- **Targeted Pytest**:
  `uv run pytest -q bookings/tests_ux13.py bookings/tests_ux12.py bookings/tests_guest_and_lodging.py bookings/tests_lodging_v4.py`
  Result: **79 passed, 33 warnings**
- **Django System Check**:
  `uv run manage.py check`
  Result: **0 issues**
- **Migration Check**:
  `uv run manage.py makemigrations --check --dry-run`
  Result: **No changes detected**
- **Git Diff Check**:
  `git diff --check`
  Result: **PASS**
- **Full Test Suite**:
  `uv run pytest -q`
  Result: **316 passed, 145 warnings in 87.32s**
- **Browser QA (Playwright / CDP)**:
  `node ux13_browser_qa.mjs`
  Result: **PASS** across all viewports (`360`, `390`, `430`, `768`, `1280`, `1440`):
  - No horizontal overflow on any viewport
  - Mobile primary CTA full-width (`width: 100%`)
  - Secondary controls and touch targets >=44px
  - Semantic `<fieldset>` and `<legend>` present and valid
  - Select all / Deselect all room controls functioning correctly
  - Copy link feedback working (`✓ คัดลอกสำเร็จ!`)
  - LINE share URL link valid
  - Visible keyboard focus outlines on interactive elements
  - 0 console errors, 0 runtime exceptions, 0 failed network requests

## Independent Review

- Source implementation passed independent ChatGPT review.
- Final diff reviewed for strict scope containment and adherence to invariants.

## Release Gate

- Base branch: `feat/lodging-v5-2` (base commit `2f7a6f8`)
- Feature branch: `feat/ux-13-lodging-cohort-management-mobile`
- Stage ONLY 5 release files:
  - `templates/lodging/manage_list.html`
  - `static/css/app.css`
  - `bookings/tests_ux13.py`
  - `docs/plans/2026-09-17-ux-13-lodging-cohort-management-mobile.md`
  - `docs/handoffs/2026-09-17-ux-13-lodging-cohort-management-mobile.md`
- DO NOT MERGE without explicit user approval.
