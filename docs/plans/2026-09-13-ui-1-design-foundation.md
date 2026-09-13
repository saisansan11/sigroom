# SIGROOM UI-1 — Design Foundation

Date: 2026-09-13
Branch: `feat/ui-1-design-foundation`
Dependency: PR #16 (`fix/lodging-v5-2-final-review`) remains open; this phase is stacked on commit `b376944` and must target that branch until #16 is merged/rebased.

## Goal

Replace the global Tactical-HUD-heavy presentation with a calmer product-system foundation inspired by EMSO About and Apple-style product clarity, while keeping SIGROOM fast and operational. No booking/lodging business-rule redesign in this phase.

## Reference translation

EMSO About uses a dark canvas, very large Thai-safe typography, strong spacing, restrained fixed navigation, focused accent colors, and deliberate motion. SIGROOM will reuse those hierarchy principles but deliberately omit cinematic canvas scenes, metallic headline effects, scanlines, large decorative gradients, and continuous animation on operational screens.

## Scope

1. Update design context (`.impeccable.md`) to make product clarity the current UI source of truth.
2. Consolidate semantic design tokens in `static/css/app.css`:
   - typography scale and readable Thai line-height
   - spacing/radius
   - canvas/surface/border/shadow
   - status/accent colors
   - focus and motion
   - container widths and responsive behavior
3. Refine the global base layout and navigation without changing permissions/routes.
4. Normalize reusable UI foundation:
   - page heading / section title / eyebrow
   - primary/secondary actions
   - form controls / form panels
   - cards/panels
   - status badges / notices
   - empty/loading/error states
   - tables on narrow screens where existing markup supports it
5. Keep compatibility aliases/classes so existing pages do not require a broad template rewrite.
6. Add/adjust template hooks only when needed for semantics/accessibility or to remove global inline styling; do not alter business conditions.
7. Add focused regression assertions for key rendered pages/foundation hooks if existing tests do not protect them.

## Non-goals

- No homepage hero/availability/calendar content redesign (UI-2).
- No booking step-flow redesign (UI-3).
- No lodging hotel selector/key-card redesign (UI-4).
- No broad cleanup of every inline style in management templates.
- No schema/migration changes.
- No service/model/permission behavior changes.
- No deploy/security architecture changes.

## Risks and controls

- **Contrast regressions:** preserve semantic status tokens and inspect key roles/pages in browser.
- **Pico CSS interaction:** override through existing app stylesheet and verify form/button states.
- **Legacy class coupling:** keep aliases and change foundation incrementally rather than renaming all templates.
- **Stacked PR dependency:** PR base must be `fix/lodging-v5-2-final-review` until PR #16 is merged.
- **Unrelated working tree:** `.claude/handoffs/` is pre-existing untracked content and must remain untouched/uncommitted.

## Verification

Targeted tests: rendered/public/booking/lodging views affected by base template and UI hooks.

Required gates:
- `uv run manage.py check`
- `uv run manage.py makemigrations --check --dry-run`
- targeted pytest selection
- full `uv run pytest`
- `git diff --check`
- real Browser QA

Browser QA routes include at minimum `/`, booking search/form path, lodging public/student path, lodging management path, and representative logged-in operational screens. Exercise mobile and desktop widths, keyboard/focus, navigation, forms, and console/runtime errors. Record only roles/viewports actually completed.

## PR strategy

Open UI-1 as a stacked PR from `feat/ui-1-design-foundation` into `fix/lodging-v5-2-final-review`. Do not merge. After PR #16 lands, rebase/retarget UI-1 onto the resulting canonical base and rerun gates if the base changed.
