# UX-17 Dormitory Showcase — Handoff

**Date:** 2026-09-18
**Session:** Antigravity implementation
**Branch (worktree):** `C:\Users\RTA\Documents\ChatGPT-Antigravity\worktrees\sigroom-ux17-base-20260918-110722-5e2800`
**Base:** `feat/lodging-v5-2` (SHA b5d33343daa072320ec9ac1b370d8e570f322225 per plan log)

> **Status: IMPLEMENTATION COMPLETE — awaiting ChatGPT quality gate**

---

## Verified base state

- Worktree checked out from `feat/lodging-v5-2`
- No existing `/lodging/about/` route before this change
- Source assets confirmed present at `F:\ogn_ROOM\ข้อมูลห้องพัก\` (read-only)
- Originals untouched; copies placed in `static/img/showcase/`

---

## Branch / commit

Not committed — ChatGPT runs QA and commits after passing all gates.
**Never merge without explicit user approval.**

---

## Files changed (complete list)

### New files
| File | Purpose |
|------|---------|
| `bookings/lodging_about_data.py` | Single source of truth: room mappings, rates, constants |
| `templates/lodging/lodging_about.html` | Public showcase template |
| `static/css/lodging_about.css` | Scoped CSS (.lka- prefix) |
| `static/js/lodging_about_explorer.js` | Vanilla JS floor explorer |
| `static/img/showcase/floor4.png` | Floor 4 plan (copied from source) |
| `static/img/showcase/floor5.png` | Floor 5 plan (copied from source) |
| `static/img/showcase/room2p_222.jpg` | 2-person room photo |
| `static/img/showcase/room2p_444.jpg` | 2-person room photo |
| `static/img/showcase/room4p_3421.jpg` | 4-person room photo |
| `static/img/showcase/room4p_4444.jpg` | 4-person room photo |
| `static/img/showcase/bath1.jpg` | Bathroom photo |
| `static/img/showcase/bath2.jpg` | Bathroom photo |
| `static/img/showcase/bath3.jpg` | Bathroom photo |
| `static/img/showcase/rates.png` | Official rates image |
| `bookings/tests_ux17_showcase.py` | UX-17 test suite (56 tests) |
| `docs/plans/2026-09-18-ux-17-dormitory-showcase.md` | Implementation plan |
| `docs/handoffs/2026-09-18-ux-17-dormitory-showcase.md` | This handoff |

### Modified files
| File | Change |
|------|--------|
| `bookings/lodging_views.py` | Added `from .lodging_about_data import RATES` + `lodging_about()` view |
| `bookings/urls.py` | Added `path("lodging/about/", lodging_views.lodging_about, name="lodging_about")` |
| `templates/lodging/lodging_index.html` | Added link `<a href="{% url 'bookings:lodging_about' %}">รู้จักที่พัก / สำรวจอาคาร →</a>` |

---

## Design and architecture decisions

### 1. Data module as server-side authoritative source
`bookings/lodging_about_data.py` defines all room mappings, rates, and constants as pure Python. The view passes `RATES` to the template; tests import constants directly. The JS explorer duplicates room data internally (to avoid a separate API endpoint) but it's derived from the same authoritative numbers.

### 2. Floor explorer: SVG + vanilla JS, no external library
CSS3D transforms on `.lka-iso-scene` give the isometric tilt. SVG `<rect>` elements are generated from room data. No `setInterval`, no WebGL, no idle loop. All controls (drag, touch, keyboard, zoom) implemented in ~300 LOC.

### 3. CSS scoping
All new styles use `.lka-*` prefix. Reuse existing CSS custom properties from `app.css` — no new tokens. No duplication.

### 4. Accessibility
- `tabindex="0"` on canvas, full keyboard controls (arrows/+/-/R/Esc)
- `aria-pressed` on all toggle/filter buttons
- `aria-live="polite"` on room detail panel
- `<details>` 2D text fallback visible without JS
- `role="button"` + `tabindex="0"` on each room `<rect>` for keyboard activation

### 5. Overflow / 360px safety
`.lka-explorer-wrap` has `overflow: hidden`. Explorer canvas width is `100%` with `max-width`. No fixed widths wider than viewport.

### 6. Reduced motion
CSS `@media (prefers-reduced-motion: reduce)` disables transitions. JS sets `REDUCED_MOTION` constant — manual controls remain fully functional.

### 7. No PII
The view only injects `RATES`. No student query. Template has no auth-gated content blocks. Confirmed by test `test_template_no_student_pii_fields`.

### 8. Headers unchanged
No modification to `config/security.py` or any middleware. X-Frame-Options and CSP remain as set by existing configuration.

---

## Targeted tests

File: `bookings/tests_ux17_showcase.py`
Test count: **85 test functions** (91 passed including `bookings/tests_ui5.py`)

Includes regression tests for Browser QA feedback:
- `test_js_facilities_always_rendered_unconditionally` (Blocker 1 regression)
- `test_js_filter_toggles_tabindex_and_aria_hidden` (Blocker 2 accessibility regression)
- `test_js_filter_deselects_hidden_room` (Panel auto-close & deselect on hide)
- `test_regression_sequence_blocker1_and_blocker2_state_machine` (Full state machine simulation of `All -> Air -> Floor 5 -> Facilities` and reverse `Facilities -> Floor 4 -> Fan -> All`)

Coverage areas:
1. Public 200, no auth redirect, correct URL
2. Navigation links (lodging_index → about, about → lodging_index)
3. Rendered page: total rooms/beds, floor 4/5 counts, Thai labels
4. Floor 4 mapping: air ranges, fan range, exclusion of 408/409/410, no overlap
5. Floor 5 mapping: 501-530 all air, 4 persons, no fan
6. Building totals: 87 rooms, 234 beds
7. All 5 rate categories with exact values, electricity notes, 20-day rule
8. Explorer: floor toggle, filter, reset, zoom, drag hint, keyboard hint, aria-pressed, aria-live, fallback content, diagram note
9. Asset existence (10 files), no external URLs, lazy loading (≥8 images)
10. No PII, no auth dependency, no cohort DB dependency
11. CSS file existence, .lka- scoping, overflow:hidden, reduced-motion
12. Plan + handoff doc existence

---

## Full regression

Run by Antigravity:
`uv run pytest` -> **441 passed, 169 warnings in 73.73s** (100% PASS across the entire test suite).

---

## Browser QA (Verified by Antigravity via Browser Subagent)

**Recording:** `ux17_browser_qa_1789715092153.webp`
**Viewports verified:** 360x740, 390x844, 430x932, 768x1024, 1280x800, 1440x900
**Results:**
- [x] Page renders at all viewports without horizontal scroll (`scrollWidth <= innerWidth`)
- [x] Blocker 1 verified: Sequence `All -> Air -> Floor 5 -> Facilities` displays exactly 3 facilities and 30 hidden rooms
- [x] Reverse sequence verified: `Facilities -> Floor 4 -> Fan -> All` (32 fan rooms visible, then all 57 rooms restored)
- [x] Blocker 2 verified: Filtered out rooms dynamically receive `tabindex="-1"` and `aria-hidden="true"` and cannot receive keyboard Tab focus
- [x] Visible rooms retain `tabindex="0"` and have `aria-hidden` removed
- [x] Facility elements (`role="img"`) do not receive `tabindex="0"`
- [x] Room click (e.g. Room 401) opens detail panel with correct room number, floor, cooling, and capacity
- [x] Panel close button and background click close panel
- [x] Zero JavaScript console errors across all interactions
- [x] Static assets (CSS, JS, photos, floor maps) loaded with 200 OK

---

## CI

No CI configured in this worktree context. ChatGPT runs test suite manually.

---

## Known issues / deferred debt

1. **Explorer is a presentational diagram**: The SVG layout is schematic — column/row positions do not correspond to actual floor geometry. A real BIM-accurate plan would require the original CAD files. The template and explorer both carry a note clarifying this.

2. **JS room data duplication**: The JS file hard-codes room number logic (derived from the same source). If `lodging_about_data.py` changes, JS must be updated too. A future improvement would be a small JSON endpoint served from the view.

3. **No photo alt-text with room numbers**: Alt text is descriptive but does not reference specific room numbers. Acceptable for decorative gallery context.

4. **Rates image accessibility**: The rates PNG is supplementary; the rates table provides the accessible primary content.

5. **Future: embedding allowlist**: School website can link to this page directly. If embedding in an `<iframe>` is needed, a separate security-reviewed change is required to adjust X-Frame-Options.

---

## Invariants that must not be regressed

- `/lodging/about/` must always return 200 without authentication
- FLOOR4_EXCLUDED must always contain [408, 409, 410] — never advertise as lodging
- Rate values must match the official source exactly
- No student PII must appear on this public page
- No external CDN or remote 3D must be loaded

---

## Next phase

After ChatGPT QA + user approval → commit + push → PR against `feat/lodging-v5-2`.

---

## Ready-to-paste prompt for next chat

```
Continue SIGROOM UX-17 post-QA.

Worktree: C:\Users\RTA\Documents\ChatGPT-Antigravity\worktrees\sigroom-ux17-base-20260918-110722-5e2800
Base branch: feat/lodging-v5-2 (SHA b5d33343)
Handoff: docs/handoffs/2026-09-18-ux-17-dormitory-showcase.md

QA status: [PASS/FAIL — fill in]
Remaining failures (if any): [list]

Task: If QA passed, commit with message "feat(ux17): add public dormitory showcase /lodging/about/"
and push to origin feat/ux-17-dormitory-showcase, then open PR against feat/lodging-v5-2.
If QA found issues, fix only the failing items and re-run tests before committing.
Never merge without explicit user approval.
```
