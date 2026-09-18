# UX-17 Dormitory Showcase — Implementation Plan

**Date:** 2026-09-18
**Feature:** Public dormitory showcase page `/lodging/about/`
**Phase:** Single phase (showcase page + explorer + tests + docs)

---

## Objective

Add a public, no-auth `/lodging/about/` page that presents the Signal School dormitory building to prospective lodgers. The page is linked from `/lodging/` and provides:
- Hero with key facts
- Interactive self-hosted isometric/2D floor explorer
- Room photo gallery (real photos only)
- Bathroom/facilities gallery
- Official rates table
- CTA back to the booking flow

---

## Scope

### In scope
- New public route `bookings:lodging_about` → `/lodging/about/`
- Template `templates/lodging/lodging_about.html`
- CSS `static/css/lodging_about.css`
- JS `static/js/lodging_about_explorer.js` (vanilla, self-hosted)
- Python data module `bookings/lodging_about_data.py` (single source of truth)
- Copy source assets to `static/img/showcase/`
- Link from `templates/lodging/lodging_index.html`
- Test suite `bookings/tests_ux17_showcase.py`
- Plan doc and handoff doc

### Explicitly out of scope
- No schema migration
- No React, no external CDN, no Spline, no WebGL
- No AI-generated replacement room images
- No modification of booking/lodging business logic
- No weakening of auth, CSRF, X-Frame-Options, or CSP
- No PR/merge/push — ChatGPT handles QA and commit
- No invented effective date for rates

---

## Real-world data (authoritative)

### Floor 4
| Type | Rooms | Count |
|------|-------|-------|
| Air | 401–407, 411–416, 449–460 | 25 |
| Fan | 417–448 | 32 |
| **Total** | | **57 rooms / 114 beds** |
| Excluded (not lodging) | 408, 409, 410 | — |

Beds per room: 2

### Floor 5
| Type | Rooms | Count |
|------|-------|-------|
| Air | 501–530 | 30 |
| **Total** | | **30 rooms / 120 beds** |

Beds per room: 4

### Building total
- **87 rooms / 234 beds**

### Shared facilities
- ห้องน้ำชั้น 4 และ 5 มี 2 ฝั่ง: โถปัสสาวะ 10, ห้องสุขา 10
- ห้องอาบน้ำชั้น 4 และ 5: ฝั่งละ 20 ห้อง

### Rates
| สังกัด | Air/day | Air/month | Fan/day | Fan/month |
|--------|---------|-----------|---------|-----------|
| บุคคลภายนอก | 150 | 2,500 | 100 | 2,000 |
| นขต.กรม.สส. | 100 | 2,000 | 70 | 1,500 |
| นขต.รร.ส.สส. | 50 | 1,500 | 40 | 800 |
| นายทหารนักเรียน | 50 | 1,500 | 40 | 800 |
| นายสิบนักเรียน | 40 | 1,000 | 30 | 800 |

Electricity: Air = 5 baht/unit · Fan = 200 baht/month flat
Monthly rule: 20+ days = 1 month

---

## Architecture decisions

1. **Single data source**: `bookings/lodging_about_data.py` defines all constants. View imports `RATES`, JS reads hard-coded identical data (to avoid a separate API endpoint). Tests import from the data module.

2. **Explorer**: Pure SVG + vanilla JS. No `setInterval`, no WebGL, no external library. Rooms rendered as SVG `<rect>` elements with data attributes. CSS3D transforms applied to the scene container for the isometric tilt feel. Drag, touch, keyboard, zoom all supported.

3. **Accessibility**: `tabindex="0"` on canvas, `aria-pressed` on toggles/filters, `aria-live="polite"` on room panel, keyboard shortcuts (arrows/+/-/R/Esc), `<details>` fallback.

4. **Overflow prevention**: `.lka-explorer-wrap` has `overflow: hidden`. No horizontal overflow at 360px.

5. **Reduced-motion**: CSS sets `transition: none` under `prefers-reduced-motion`. JS reads `REDUCED_MOTION` to disable any future auto-rotate if added.

6. **No PII**: View context only contains `RATES` list. No student query is performed. Template has no user-auth-dependent content blocks.

---

## Files changed

| File | Change |
|------|--------|
| `bookings/lodging_about_data.py` | **NEW** — data constants |
| `bookings/lodging_views.py` | **MODIFIED** — import + `lodging_about()` view |
| `bookings/urls.py` | **MODIFIED** — `lodging/about/` route |
| `templates/lodging/lodging_about.html` | **NEW** — showcase template |
| `templates/lodging/lodging_index.html` | **MODIFIED** — link to about page |
| `static/css/lodging_about.css` | **NEW** — scoped CSS |
| `static/js/lodging_about_explorer.js` | **NEW** — floor explorer JS |
| `static/img/showcase/*.{png,jpg}` | **NEW** — 10 copied assets |
| `bookings/tests_ux17_showcase.py` | **NEW** — test suite |
| `docs/plans/2026-09-18-ux-17-dormitory-showcase.md` | **NEW** — this plan |
| `docs/handoffs/2026-09-18-ux-17-dormitory-showcase.md` | **NEW** — handoff |

---

## Quality gate (run by ChatGPT)

1. `git diff --check`
2. `uv run manage.py check`
3. `uv run manage.py makemigrations --check --dry-run`
4. `uv run pytest bookings/tests_ux17_showcase.py -v`
5. `uv run pytest -q` (full suite)
6. Browser QA at 360, 390, 430, 768, 1280, 1440
7. Keyboard/touch/drag/zoom/filter/floor-toggle test
8. Console/network error review
