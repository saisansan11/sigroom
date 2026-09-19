# UX-23 — Lodging Isometric Explorer Handoff

**Date:** 2026-09-19
**Flow:** 2
**Base:** `origin/feat/lodging-v5-2` @ `701865a`
**Branch:** `feat/ux-23-lodging-isometric-explorer`
**Worktree:** `C:\Users\RTA\Documents\ChatGPT-Antigravity\worktrees\sigroom-ux23-isometric-explorer`

## Why this change
The previous explorer called itself 3D but rendered the complete floor as one flat SVG sheet and then applied CSS `rotateX/rotateZ` to the entire sheet. Visually it behaved like a rectangular card rotating in space rather than an architectural model.

UX-23 replaces that presentation with a lightweight self-hosted isometric model. Every room is now rendered as an SVG cuboid with independent top and side faces, supported by an extruded building base, corridor and facility blocks.

## Design / behaviour
- Room blocks are real pseudo-3D SVG geometry: top + X side + Y side.
- Floor 4 renders 57 room cuboids (114 visible room side faces); Floor 5 renders 30 cuboids (60 room side faces).
- Building base and corridor are separately extruded instead of being one rotating slab.
- Air-conditioned rooms, fan rooms and facilities use distinct top/side shading while retaining the existing bright hospitality palette.
- Selected rooms lift from the model and receive a stronger architectural highlight.
- Hover/focus gives small elevation only; there is no continuous idle animation.
- Four architectural camera directions are implemented by re-projecting geometry through `viewQuarter`; the scene no longer uses CSS `rotateX()` or `rotateZ()`.
- Drag/swipe left-right changes camera direction. Dedicated rotate-left / rotate-right buttons provide an obvious alternative.
- Zoom remains available via buttons, keyboard and wheel.
- Keyboard contract remains: Left/Right rotate, Up/Down zoom, +/- zoom, R reset, Escape closes room detail.
- Floor 4/5 switching, filters, detail panel, external floor links and text fallback remain operational.
- Canvas is an interactive `role="region"` rather than a static `role="img"` because it contains keyboard-focusable room controls.
- No WebGL, Three.js, Spline, remote CDN or remote 3D asset is used.

## Data preserved
No room facts were invented or changed.

- Floor 4: 57 lodging rooms, 114 beds, capacity 2.
- Floor 4 air: 401–407, 411–416, 449–460.
- Floor 4 fan: 417–448.
- 408, 409, 410 remain explicitly excluded as student lodging rooms.
- Floor 5: 501–530, 30 rooms, 120 beds, capacity 4, all air-conditioned.
- Existing facility labels `ห้องน้ำ ฝั่ง A`, `ห้องน้ำ ฝั่ง B`, `ห้องอาบน้ำ` are preserved.
- Explorer remains explicitly described as a schematic visualization, not BIM or a scale architectural drawing.

## Files changed
- `templates/lodging/lodging_about.html`
  - Loads the isolated UX-23 stylesheet after the existing lodging stylesheet.
  - Reworks only the interactive explorer section and preserves the rest of the lodging page.
- `static/js/lodging_about_explorer.js`
  - Replaces flat-sheet CSS rotation with per-room isometric geometry and four-view re-projection.
- `static/css/lodging_about_ux23.css`
  - New isolated model styling: cuboid faces, base, corridor, HUD, shadows, selected lift, responsive and reduced-motion behaviour.
- `bookings/tests_ux23_isometric_explorer.py`
  - 8 UX-23 contracts covering geometry, controls, no flat-scene rotation, accessibility hooks and remote-engine prohibition.
- `docs/plans/2026-09-19-ux-23-lodging-isometric-explorer.md`
- `docs/handoffs/2026-09-19-ux-23-lodging-isometric-explorer.md`

## Test / Quality Gate results
### Targeted regression
Command covered UX-23 plus UX-17/20/21A/21B/22:

`uv run --env-file F:/ogn_ROOM/.env pytest -q bookings/tests_ux23_isometric_explorer.py bookings/tests_ux17_showcase.py bookings/tests_ux20_lodging_about.py bookings/tests_ux21a_lodging_about.py bookings/tests_ux21b_lcp_media.py bookings/tests_ux22_responsive_media.py`

Result: **137 passed, 45 warnings, 0 failures**.

### Full regression
`uv run --env-file F:/ogn_ROOM/.env pytest -q`

Result: **505 passed, 206 warnings, 0 failures in 85.99s**.

### Additional gates
- `node --check static/js/lodging_about_explorer.js` — PASS.
- `git diff --check` — PASS.
- `python manage.py check` — `System check identified no issues (0 silenced)`.
- `python manage.py makemigrations --check --dry-run` — `No changes detected`.
- `uv run python scripts/generate_showcase_media.py --check` — `All expected variants are present, exact, and current.`

Warnings are existing environment/framework warnings (pilot HTTP `DJANGO_SECURE=0` used only for localhost/LAN QA, Django URLField future-scheme warning, and test staticfiles-directory warning); none are UX-23 test failures.

## Real Chrome QA
Real Chrome was driven through an isolated QA profile and local Django server. Final strict matrix used calibrated device metrics so measured `innerWidth × innerHeight` exactly matched every target:

| Viewport | Overflow | F4 model | Rotate | Room 401 | F5 model | Room 501 | Runtime / console / network errors |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 360×800 | none | 57 rooms / 114 side faces | 1/4 → 2/4 | 2 persons, air | 30 / 60 | 4 persons, air | 0 / 0 / 0 |
| 390×844 | none | 57 / 114 | PASS | PASS | 30 / 60 | PASS | 0 / 0 / 0 |
| 430×932 | none | 57 / 114 | PASS | PASS | 30 / 60 | PASS | 0 / 0 / 0 |
| 768×1024 | none | 57 / 114 | PASS | PASS | 30 / 60 | PASS | 0 / 0 / 0 |
| 1280×800 | none | 57 / 114 | PASS | PASS | 30 / 60 | PASS | 0 / 0 / 0 |
| 1440×900 | none | 57 / 114 | PASS | PASS | 30 / 60 | PASS | 0 / 0 / 0 |

The fan filter was also exercised in the first full matrix: Floor 4 produced exactly 32 visible fan rooms and 25 hidden lodging rooms, with room/floor switching remaining functional.

## Visual review
A real-browser screenshot of the explorer was inspected at desktop width. The new view visibly reads as an architectural floor model rather than a rotating card:
- raised building plinth / base;
- long central corridor;
- room cuboids with distinct top and side planes;
- facilities as separate mint cuboids;
- depth shading, ground shadow and readable room labels;
- architectural camera view indicator (`มุมมอง 1/4`).

No unsupported features such as stairs, elevators or interior furniture were added because there is no authoritative source data for them.

## Scope / merge state
- No backend model, database, auth, booking logic or room inventory source-of-truth was changed.
- No deployment performed.
- No merge performed.
- Stop at PR/CI and wait for explicit user approval before merge.
