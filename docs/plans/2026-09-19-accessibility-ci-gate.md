# Accessibility CI Gate — scoped delta after UI-5

## Scope

This work is intentionally smaller than the originally proposed UX-25. UI-5 already completed a broad responsive/accessibility sweep. The remaining delta is limited to accessibility regression protection for the newer Lodging About isometric explorer plus an automated PR gate.

## Changes

1. Add Playwright + axe-core automated checks for representative public routes at desktop and mobile widths.
2. Add an `Accessibility audit` job to `.github/workflows/pr-safety-gate.yml` and require it from `PR Safety Gate`.
3. Harden the Lodging About explorer only where UX-23/24 introduced new risks:
   - preserve room focus across SVG re-render when rotating/resetting;
   - Escape closes the selected-room inspector and restores focus to the originating room control when possible;
   - narrow live-region announcements so the entire inspector is not repeatedly announced.
4. Add focused Django/static-contract regression tests for the explorer semantics and CI wiring.
5. Update pilot checklist to distinguish the automated phase-1 gate from a future full WCAG/screen-reader acceptance audit.

## Verification

- targeted pytest for new/related tests
- `uv run manage.py check`
- `uv run manage.py makemigrations --check --dry-run`
- full pytest regression
- `git diff --check`
- Playwright/axe locally against a running Django server
- browser QA for keyboard focus, Escape, mobile inspector, reduced motion, and JS-disabled fallback

## Non-goals

- no visual redesign
- no architecture change
- no claim of complete WCAG 2.2 AA certification from axe alone
- no merge or deploy without user approval
