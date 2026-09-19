# UX-24 — 3D Visual Polish Handoff

**Date:** 2026-09-19
**Flow:** 2 (Codex direct implementation explicitly requested)
**Base:** `origin/feat/lodging-v5-2` @ `8ebd9b13c9f63bafdc0e3bff956d78e1b5151743`
**Branch:** `feat/ux-24-3d-visual-polish`
**Feature commit:** `398df9c0ceb8d7b0aa6484fc5e13555b52fa45d2`
**PR:** [#48 — UX-24: Polish lodging isometric explorer](https://github.com/saisansan11/sigroom/pull/48)
**Release state:** PR open for review; not merged or deployed.

## Outcome

UX-24 upgrades the merged UX-23 explorer into a brighter architectural light-table presentation while preserving the room inventory, filtering, fallback content, keyboard use, and not-BIM disclosure.

The model now has stronger face separation, shared directional gradients, a controlled ground shadow, compact controls, and a visible selection hierarchy. Room selection stays active while users rotate, zoom, or reset the view. Desktop shows a contextual side inspector; tablet and mobile show a fixed inspector near the selected model.

## Interaction changes

- Ordinary wheel input scrolls the page. Users zoom with the controls, keyboard, or Ctrl/Meta+wheel.
- Floor and filter changes clear an invalid selection. Escape closes the inspector.
- Selected rooms use outline, lift, and de-emphasis of other rooms instead of color alone.
- Mobile controls meet a 44px touch-target contract, and the reset control keeps a visible icon at narrow widths.
- The implementation uses local SVG, CSS, and vanilla JavaScript. It adds no remote assets, WebGL engine, or continuous animation loop.

## Data invariants

- Floor 4: 57 lodging rooms, 114 beds, 2 people per room; air 401–407, 411–416, 449–460; fan 417–448; 408–410 excluded.
- Floor 5: rooms 501–530, 30 rooms, 120 beds, 4 people per room, all air.
- Backend models, schema, booking rules, authentication, permissions, and privacy behavior remain unchanged.

## Verification

Automated gates:

- UX-24 plus UX-17/20/21A/21B/22/23 regression: `144 passed`.
- Full test suite: `512 passed, 207 warnings` in 79.84 seconds.
- `python manage.py check`: no issues.
- `python manage.py makemigrations --check --dry-run`: no changes.
- `python scripts/generate_showcase_media.py --check`: generated media is current.
- `node --check static/js/lodging_about_explorer.js`: passed.
- `git diff --check`: passed.

The warnings are the repository's existing Django/Python runtime warnings, including the pilot HTTP configuration, Django 6 URL-field transition, and absent local `staticfiles` directory. Tests reported no failures.

Browser QA:

- Tested 360×800, 390×844, 430×932, 768×1024, 1280×800, and 1440×900.
- Verified Floor 4 and Floor 5, room 401 and room 501, cooling/facility filters, rotate, zoom, reset, keyboard navigation, Escape, and ordinary wheel page scrolling.
- Room selection persisted through view changes and remained visible in the contextual inspector.
- All tested viewports had no horizontal overflow. The 768×1024 inspector fit without internal scrolling.
- Browser console reported zero errors and zero warnings.
- Scoped CSS, JavaScript, and image requests returned 200/304. Only the unrelated optional `/favicon.ico` request returned 404.

## Files

- `templates/lodging/lodging_about.html`
- `static/css/lodging_about_ux24.css`
- `static/js/lodging_about_explorer.js`
- `bookings/tests_ux24_3d_visual_polish.py`
- `docs/plans/2026-09-19-ux-24-3d-visual-polish.md`
- `docs/handoffs/2026-09-19-ux-24-3d-visual-polish.md`

## Review focus

- Visual hierarchy and lighting across desktop, tablet, and mobile.
- Selection clarity without implying real-time occupancy or BIM accuracy.
- Room inspector placement at 1024px and narrower.
- Wheel behavior, keyboard navigation, and touch-target sizing.

## Release guard

Do not merge or deploy until the user explicitly approves both actions.
