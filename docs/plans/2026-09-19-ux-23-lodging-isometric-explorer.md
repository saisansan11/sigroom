# UX-23 — Lodging Isometric Explorer

**Date:** 2026-09-19
**Flow:** 2
**Base:** `origin/feat/lodging-v5-2` @ `701865a`
**Branch:** `feat/ux-23-lodging-isometric-explorer`

## Problem
The current explorer calls itself 3D but renders a flat SVG floor sheet and then rotates the entire sheet with CSS `rotateX/rotateZ`. The result reads visually like a rectangular card or piece of paper spinning rather than an architectural model.

## Goal
Replace the flat rotating sheet with a lightweight architectural pseudo-3D/isometric model that feels spatial and premium while remaining fast, accessible, mobile-friendly, self-hosted, and compatible with the existing factual room data and interactions.

## Design direction
1. Render every room as a true isometric cuboid using separate top/front/side SVG faces instead of a flat rectangle.
2. Add an extruded building base and an isometric corridor zone so the floor reads as a model rather than a card.
3. Keep room numbers on the top face and preserve click/keyboard selection.
4. Selected room lifts visually and gets a clear focus halo; hover/focus gives subtle elevation, not continuous animation.
5. Replace free-form slab rotation with discrete architectural camera orientations. Drag left/right or use rotate controls to switch view; the model is re-projected, not CSS-spun as one flat plane.
6. Keep zoom controls and keyboard support. Arrow Left/Right rotate the model; +/- zoom; R resets; Escape closes the room panel.
7. Preserve Floor 4 / Floor 5 switching, all filters, room detail panel, fallback text, room counts, cooling types, capacities, and non-lodging exclusions.
8. Keep the bright hospitality visual language. No dark sci-fi treatment.
9. No WebGL, Three.js, Spline, remote CDN, remote asset, or continuous animation loop.
10. Respect `prefers-reduced-motion` and keep all touch targets usable on narrow screens.

## Accessibility / truthfulness
- Explorer remains a schematic visualization, not BIM or a scale architectural drawing.
- Every bookable room remains keyboard focusable with an explicit Thai aria-label.
- Filtered rooms are removed from the keyboard tab order.
- Floor and filter buttons retain `aria-pressed` state.
- A text fallback remains available.

## Expected files
- `templates/lodging/lodging_about.html`
- `static/css/lodging_about.css`
- `static/js/lodging_about_explorer.js`
- `bookings/tests_ux17_showcase.py` only where the legacy interaction contract intentionally changes
- `bookings/tests_ux23_isometric_explorer.py`
- `docs/handoffs/2026-09-19-ux-23-lodging-isometric-explorer.md`

## Quality gates
- Targeted UX-23 + UX-17/20/21A/21B/22 regression passes.
- Full pytest passes.
- `manage.py check` passes.
- `makemigrations --check --dry-run` reports no changes.
- `git diff --check` passes.
- Real Chrome QA at 360x800, 390x844, 430x932, 768x1024, 1280x800, 1440x900.
- No horizontal overflow.
- Floor 4/5, filter, zoom, rotate-view, reset, room selection, close panel all work.
- Room 401 and Room 501 can be selected and show correct details.
- No runtime JS exceptions or application console errors.
- Do not merge until explicit user approval.
