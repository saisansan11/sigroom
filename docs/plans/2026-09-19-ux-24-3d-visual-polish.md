# UX-24 — 3D Visual Polish

**Date:** 2026-09-19
**Flow:** 2 (Codex direct implementation explicitly requested)
**Base:** `origin/feat/lodging-v5-2` @ `8ebd9b13c9f63bafdc0e3bff956d78e1b5151743`
**Branch:** `feat/ux-24-3d-visual-polish`
**Quality bar:** Flagship polish for the explorer; operational clarity remains primary.

## Post-merge UX-23 audit

The merged explorer is functionally complete and preserves room truth, but real-browser review found these polish gaps:

1. **Hierarchy:** floor/filter controls expand into two full-width bars and visually compete with the model.
2. **Depth / lighting:** solid face colors and a very light ground shadow make the long model read more like pastel blocks than a premium architectural object.
3. **Selection:** selection is mostly a darker outline. The room detail appears below the entire canvas, outside the click context, so users can miss it.
4. **State continuity:** rotating or resetting closes the selected room instead of preserving the user's inspection context.
5. **Scrolling:** wheel events over the large canvas always prevent page scrolling and unexpectedly zoom the model.
6. **Mobile:** the tall canvas plus below-canvas detail increases travel; primary controls need an explicit 44px contract and a compact selected-room treatment.

## Direction

Use a **sunlit architectural light table**: bright, calm, precise, with one coherent light direction, stronger face separation, crisp edges, a controlled contact shadow, and restrained cyan emphasis. No dark HUD or decorative spectacle.

## Implementation

- Add an isolated UX-24 stylesheet loaded after UX-23.
- Compact the floor/filter controls and make the model the dominant surface.
- Recompose the explorer as model stage + contextual room inspector on desktop; use a dismissible bottom inspector on narrow screens.
- Add shared SVG gradients and a single shared model shadow treatment; do not add per-room blur filters.
- Persist room selection through camera rotation, zoom, and reset; clear it on floor/filter changes or Escape.
- Add non-color selection cues and subtle de-emphasis of unselected rooms.
- Allow ordinary wheel scrolling; zoom by buttons/keyboard and Ctrl/Meta+wheel only.
- Preserve all room data, filtering, fallback text, keyboard/touch behavior, reduced motion, and not-BIM disclosure.
- Add UX-24 contract tests and phase handoff.

## Scope

Expected files:
- `templates/lodging/lodging_about.html`
- `static/css/lodging_about_ux24.css` (new)
- `static/js/lodging_about_explorer.js`
- `bookings/tests_ux24_3d_visual_polish.py` (new)
- `docs/handoffs/2026-09-19-ux-24-3d-visual-polish.md` (new)

## Non-goals

- No backend/model/database/auth/booking logic changes.
- No room inventory or capacity changes.
- No WebGL, external asset, remote CDN, continuous animation, invented architecture, deployment, or merge.

## Verification

- UX-24 targeted tests plus UX-17/20/21A/21B/22/23 regression.
- `node --check`, Django check, migration drift check, media check, full pytest, and `git diff --check`.
- Real browser at 360×800, 390×844, 430×932, 768×1024, 1280×800, and 1440×900.
- Exercise floor 4/5, filters, room 401/501, rotate, zoom/reset, keyboard, Escape, mobile inspector, ordinary wheel page scroll, overflow, console, and runtime errors.
