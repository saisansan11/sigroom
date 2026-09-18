# UX-20 Lodging About Immersive Stay Experience — Implementation Plan

**Date:** 2026-09-19
**Feature:** Redesign `/lodging/about/` as an immersive hospitality stay showcase
**Phase:** UX-20 (Single Phase)
**Base Branch:** `feat/lodging-v5-2` (SHA `46584e32073f48b0a1e315572bc80d49a3f8f469`, PR #42 incorporated)
**Branch:** `feat/ux-20-lodging-about-immersive-stay`

---

## 1. Objective

Transform the public `/lodging/about/` page from a technical/academic summary document into a bright, inviting, and modern stay showcase (**"ที่พักน่าเข้าพัก"**). The page establishes an emotional first impression of comfort, cleanliness, and readiness, while keeping 100% of authoritative room inventory facts, official rates, floor explorer capabilities, and booking CTA links intact.

---

## 2. Scope

### In Scope
- **Presentation Layer Redesign**:
  - `templates/lodging/lodging_about.html`: Revise experience architecture into 8 distinct sections.
  - `static/css/lodging_about.css`: Modern visual language (soft 3D/isometric depth, sky blue & mint palette, ambient glows, card lift, and zero-overflow shield).
  - `static/js/lodging_about_explorer.js`: Expose `lkaSwitchFloor` helper and maintain all SVG isometric floor explorer logic.
- **Contract & Regression Tests**:
  - Maintain 100% pass on existing `bookings/tests_ux17_showcase.py` (85 tests).
  - Add dedicated `bookings/tests_ux20_lodging_about.py` (15 tests).
- **Documentation**:
  - `docs/plans/2026-09-19-ux-20-lodging-about-immersive-stay.md` (this plan).
  - `docs/handoffs/2026-09-19-ux-20-lodging-about-immersive-stay.md` (handoff).

### Strictly Out of Scope
- No database schema migrations or changes.
- No modifications to booking, allocation, or auth business logic.
- No external CDNs, Spline, Three.js, or WebGL libraries.
- No deployment (deploy is prohibited until explicitly approved).

---

## 3. Information Architecture

1. **Hero Section**: Modern hospitality copy ("ที่พักสะดวก สะอาด พร้อมเข้าพัก"), dual CTAs (`สำรวจห้องพัก` & `ดูห้องว่าง`), floating facts (87 rooms, 234 beds, Floor 5 all air, 3D map), and a pseudo-3D building card.
2. **Quick Highlights**: 4 rapid-read cards (87 rooms, 234 beds, 2–4 persons/room, 3D floor map).
3. **Room Experience**: 2 feature cards (2-person Floor 4 vs 4-person Floor 5) with real photos, feature highlights, and floor diagram cards (`floor4.png`, `floor5.png`).
4. **Interactive Floor Explorer**: Preserved `#lka-explorer` with Floor 4/5 toggle, filters, zoom/reset, room panel, and accessible fallback.
5. **Stay Photo Gallery**: Real photos as heroes (`room2p_444.jpg`, `room2p_222.jpg`, `room4p_3421.jpg`, `room4p_4444.jpg`) with featured mosaic.
6. **Facilities & Shared Spaces**: Structured cards for bathrooms & showers + 3-photo grid (`bath1.jpg`, `bath2.jpg`, `bath3.jpg`).
7. **Rates & Important Notes**: Relocated to lower section, summary stat cards (electricity: air 5 THB/unit, fan 200 THB/mo, 20-day rule), full official table with 5 categories, and `rates.png`.
8. **Final CTA**: Prominent call-to-action card linking to `bookings:lodging_index`.

---

## 4. Quality Gate Checklist

1. `uv run pytest bookings/tests_ux17_showcase.py -v`: **85 passed**
2. `uv run pytest bookings/tests_ux20_lodging_about.py -v`: **15 passed**
3. `uv run manage.py check`: **0 issues**
4. `uv run manage.py makemigrations --check --dry-run`: **No changes detected**
5. `uv run pytest -q`: **468 passed** across the entire test suite
6. `git diff --check`: **0 whitespace/format issues**
7. Browser QA: Documented protocol and interactive checks
8. Git & PR: Isolated branch, no unrelated files staged
