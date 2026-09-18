# UX-20 Lodging About Immersive Stay Experience — Handoff

**Date:** 2026-09-19
**Session:** Antigravity Implementation
**Branch:** `feat/ux-20-lodging-about-immersive-stay`
**Base:** `feat/lodging-v5-2` (SHA `46584e32073f48b0a1e315572bc80d49a3f8f469`, PR #42 incorporated)

> **Status: IMPLEMENTATION COMPLETE — Quality Gates Passed, Ready for PR & Review**

---

## 1. Verified Base State

- Freshly branched from canonical base `feat/lodging-v5-2` at commit `46584e3` ("Merge pull request #42 from saisansan11/feat/ux-19-booking-edit-time-presets").
- Incorporates all previous merged PRs:
  - PR #40: `feat(ux-17): add dormitory showcase and interactive floor explorer`
  - PR #41: `feat(ux-18): improve student lodging portal on mobile`
  - PR #42: `UX-19: restore booking edit time presets`
- Untracked working-tree files (`.claude/handoffs/`, `.tmp/`, `docs/plans/2026-09-15-ux-3-my-bookings-tracking.md`, `ข้อมูลห้องพัก/`) preserved untouched and excluded from commits.

---

## 2. Files Changed (Scoped)

| File | Change | Description |
|------|--------|-------------|
| `bookings/lodging_views.py` | MODIFIED | Pass authoritative rate constants (`ELECTRICITY_AIR_BAHT_PER_UNIT`, `ELECTRICITY_FAN_FLAT_BAHT_PER_MONTH`, `MONTHLY_THRESHOLD_DAYS`) to `lodging_about()` template context |
| `templates/lodging/lodging_about.html` | MODIFIED | Added `data-explorer-floor="4"` / `"5"` to Room Experience cards; replaced hardcoded rate literals with context variables across subtitle, summary cards, and notes |
| `static/css/lodging_about.css` | MODIFIED | Modern hospitality aesthetic, soft 3D/isometric depth, sky blue & mint palette, ambient glows, overflow shield, reduced motion support |
| `static/js/lodging_about_explorer.js` | MODIFIED | Added `[data-explorer-floor]` event listener triggering `switchFloor()`, preserving `lkaSwitchFloor` helper and full isometric SVG floor explorer engine |
| `bookings/tests_ux20_lodging_about.py` | MODIFIED | Expanded contract tests to 19 tests covering view context, rate constants, non-hardcoded templates, and floor switcher wiring |
| `docs/plans/2026-09-19-ux-20-lodging-about-immersive-stay.md` | MODIFIED | In-repo plan document updated with review blocker resolution |
| `docs/handoffs/2026-09-19-ux-20-lodging-about-immersive-stay.md` | MODIFIED | This handoff document |

---

## 3. Design & Architecture Decisions

1. **Hospitality-First Visual Transformation**:
   Replaced dense academic summary tables with an engaging "Feel first, detail second" experience. The hero features high-impact Thai typography, floating stat chips, dual CTAs, and a soft 3D isometric building card with a clear non-BIM representational disclaimer.
2. **Room Experience Cards to Floor Explorer Wiring**:
   Room Experience feature cards (Floor 4: 2 persons vs Floor 5: 4 persons) feature semantic `data-explorer-floor="4"` and `data-explorer-floor="5"` attributes bound in `lodging_about_explorer.js` to `switchFloor()`. Preserves native anchor `href="#lka-explorer"` for progressive enhancement, maintains `aria-pressed` states, closes open room panels, and re-renders SVG maps dynamically.
3. **Single Source of Truth for Rates**:
   Eliminated duplicate hardcoded literals ("5 บาท", "200 บาท", "20 วัน") from `lodging_about.html`. Authoritative constants (`ELECTRICITY_AIR_BAHT_PER_UNIT`, `ELECTRICITY_FAN_FLAT_BAHT_PER_MONTH`, `MONTHLY_THRESHOLD_DAYS`) are imported from `bookings/lodging_about_data.py` and passed into the view context.
4. **Preservation of Interactive Floor Explorer Invariants**:
   Retained 100% of DOM hooks, event handlers, keyboard controls (arrows/+/-/R/Esc), touch rotation, zoom/reset, room detail panel, and `<details>` text fallback.
5. **Zero Backend Risk & Strict Scoping**:
   No changes to booking logic, models, permissions, auth, allocations, or database schema. Scope strictly bounded to PR #43 (unrelated `/favicon.ico` 404 left out as global/pre-existing debt).
6. **Performance & Security**:
   Zero external CDNs, zero WebGL, zero Three.js/Spline. Hardware-accelerated CSS transforms (`translateY`, `rotateX`, `opacity`), lazy loading on all below-the-fold imagery (12 lazy images), and strict `prefers-reduced-motion` fallbacks.

---

## 4. Verification & Quality Gates

### Automated Tests
- `uv run pytest bookings/tests_ux17_showcase.py -v`: **85 passed**
- `uv run pytest bookings/tests_ux20_lodging_about.py -v`: **19 passed**
- Combined showcase & UX-20 tests: **104 passed**
- Lodging regression tests (`tests_guest_and_lodging.py`, `tests_lodging_v4.py`, `tests_ux18.py`, `tests_ux19.py`): **37 passed**
- Full test suite: `uv run pytest -q`: **472 passed, 0 failures** in 1m 21s.
- Django checks: `uv run manage.py check`: **0 issues**
- Migration dry-run: `uv run manage.py makemigrations --check --dry-run`: **No changes detected**
- Whitespace validation: `git diff --check`: **Clean (0 errors)**

### Real Browser QA (Chrome CDP Headless Matrix)
- Tested across 5 viewports:
  - 360×800 (Mobile compact): `docScrollWidth=360, winInnerWidth=360` — **PASS (No overflow)**
  - 390×844 (Mobile standard): `docScrollWidth=390, winInnerWidth=390` — **PASS (No overflow)**
  - 430×932 (Mobile large): `docScrollWidth=430, winInnerWidth=430` — **PASS (No overflow)**
  - 768×1024 (Tablet portrait): `docScrollWidth=753, winInnerWidth=768` — **PASS (No overflow)**
  - 1280×720 (Desktop standard): `docScrollWidth=1265, winInnerWidth=1280` — **PASS (No overflow)**
- Interactions verified:
  - Floor 5 Experience card click -> `#lka-btn-f5.active`, `aria-pressed="true"`, Floor 5 rooms (501–530) rendered — **PASS**
  - Floor 4 Experience card click -> `#lka-btn-f4.active`, `aria-pressed="true"`, Floor 4 rooms (401–460) rendered — **PASS**
  - Filters (Air: 25 rooms, Fan: 32 rooms, All: 60 blocks) — **PASS**
  - Room Detail Panel (Click Room 401 opens panel, close button hides panel) — **PASS**
  - Zoom & Reset (zoom scale 1.3, reset scale 1.0) — **PASS**
  - Keyboard Interaction (Focus on Room 402 + Enter opens panel) — **PASS**
  - Rates Table Container (`overflow-x: auto`) on mobile — **PASS**
  - Console / Runtime Exceptions: **0** — **PASS**

---

## 5. Next Steps

1. Review git diff and commit scoped files on branch `feat/ux-20-lodging-about-immersive-stay`.
2. Push commit to remote `origin/feat/ux-20-lodging-about-immersive-stay` (PR #43).
3. Await GitHub Actions CI passing.
4. Provide new commit SHA and QA summary for final review.
5. **DO NOT MERGE** until explicit user approval.
