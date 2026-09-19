# UX-22 — Lodging Responsive Media Pipeline

**Date:** 2026-09-19
**Flow:** Flow 2 — ChatGPT plans/reviews; Antigravity implements
**Base:** `a1ffb21fea1492197e9fca0434837d4b551855e5` (`origin/feat/lodging-v5-2`)
**Branch:** `feat/ux-22-lodging-responsive-media`
**Scope:** `/lodging/about/` static showcase media only

## 1. Evidence and problem

UX-21B fixed LCP scheduling but intentionally deferred responsive modern formats. The current `static/img/showcase` set has 10 originals totaling 1,399,525 bytes. Seven are photographic JPEGs; three are PNG floor/rates diagrams. Several photos are ~1477 px wide while rendered around 640 px or smaller, so mobile browsers currently download more pixels/bytes than needed.

Baseline UI5 + UX-21B contract tests pass 7/7 on this base. Pillow 12.3 in the current environment supports both WebP and AVIF; no new native encoder dependency is required.

## 2. Invariants

- Keep every original JPG/PNG file and URL unchanged as the final `<img>` fallback.
- Keep hero fallback `room4p_3421.jpg` with `loading="eager"`, `fetchpriority="high"`, `decoding="async"`, explicit width/height.
- Keep all 12 below-fold fallback `<img>` elements `loading="lazy"`; none may get eager/high priority.
- Keep alt text, layout, bright-hospitality visual design, Floor 4/5 explorer, Room 401 detail behavior, privacy/auth/business logic unchanged.
- No speculative image preload tags.
- No backend/model/auth/database/migration changes.
- Do not touch `F:/ogn_ROOM`; only pass `F:/ogn_ROOM/.env` opaquely to `uv run --env-file` commands.

## 3. Architecture and exact variant strategy

Use a deterministic Pillow generator committed to the repo (prefer `scripts/generate_showcase_media.py`) and commit generated assets.

### Photographic JPEGs
Candidate originals:
- `bath1.jpg`, `bath2.jpg`, `bath3.jpg`
- `room2p_222.jpg`, `room2p_444.jpg`
- `room4p_3421.jpg`, `room4p_4444.jpg`

For each photo, generate AVIF and WebP candidates only at widths that do not upscale:
- 640w for every photo whose source width is >= 640.
- 1280w only when source width is >= 1280.

Use stable deterministic filenames under `static/img/showcase/generated/`, e.g. `<stem>-640.avif`, `<stem>-640.webp`, `<stem>-1280.avif`, `<stem>-1280.webp`.

Use consistent encoder parameters recorded in the generator. Preserve aspect ratio and strip accidental metadata unless needed for orientation. Re-running the generator must reproduce the same file set and dimensions.

### PNG diagrams/documents
`floor4.png`, `floor5.png`, `rates.png` stay as original PNG fallbacks. A measured lossless WebP experiment is allowed only when it preserves full intrinsic dimensions and exact decoded pixels.

**Decision after measurement:** keep full-size lossless WebP modern sources for all three PNG assets. Exact pixel-equality checks pass, while byte size falls from 32,084 B to 9,488 B for `floor4` (-70.4%), 14,073 B to 4,274 B for `floor5` (-69.6%), and 75,780 B to 11,368 B for `rates` (-85.0%). The original PNG files and URLs remain unchanged as fallbacks.

### Markup
For photographic occurrences in `templates/lodging/lodging_about.html`, use semantic:
`<picture>` → AVIF `<source>` → WebP `<source>` → existing original `<img>` fallback.

Use `srcset` width descriptors and `sizes` appropriate to each rendered slot. Do not reference a 1280 candidate for `room2p_222.jpg` because its source is 662w. Do not upscale.

Before wrapping images, inspect `static/css/lodging_about.css` for direct-child/grid/flex selectors. Add the smallest wrapper class/rules only if needed to preserve exact layout, dimensions, border radius/object-fit and no baseline gap. Do not redesign.

## 4. Byte-benefit rule

Measure generated output sizes against the corresponding original and record exact bytes. Keep a generated modern candidate only if it is meaningfully smaller for its intended width. Do not claim savings from theoretical format efficiency. If a candidate is larger or not useful, omit it from markup and document why.

## 5. Tests

Add `bookings/tests_ux22_responsive_media.py` covering at minimum:
- `/lodging/about/` public 200.
- `<picture>` source order = AVIF then WebP then original `<img>` fallback for photo slots.
- Original fallback filenames remain present and unchanged.
- Referenced modern files exist and Pillow reports expected dimensions/format.
- No candidate width exceeds source width; no upscaling.
- Hero fallback retains eager/high/async + explicit dimensions.
- Exactly 12 below-fold fallback images remain lazy and non-high-priority.
- No `<link rel="preload" as="image">` spam.
- Generated assets used in markup are smaller than their relevant original/full-size transfer target as appropriate.
- Generator manifest/output is deterministic enough to detect missing/stale variants.

If a legacy regex test becomes stale due to `<picture>`, modernize it narrowly while preserving the original invariant; do not weaken global image discipline.

## 6. Quality gates

Run:
1. UX-22 tests plus `tests_ui5.py::test_image_performance_attributes_in_templates` and UX-20/21A/21B regressions.
2. `uv run --env-file F:/ogn_ROOM/.env python manage.py check`
3. `uv run --env-file F:/ogn_ROOM/.env python manage.py makemigrations --check --dry-run`
4. `git diff --check`
5. `uv run --env-file F:/ogn_ROOM/.env pytest -q`
6. Real Chrome QA at 360x800, 390x844, 430x932, 768x1024, 1280x800, 1440x900:
   - no horizontal overflow/layout shift/regression;
   - Floor 4/5 toggle and Room 401 detail pass;
   - zero JS exceptions/console errors;
   - Chrome selects AVIF or WebP when supported;
   - selected hero modern asset is requested early/high priority and only once per navigation;
   - no preload spam/duplicate transfer;
   - original fallback URL still returns HTTP 200.
7. Independent complete diff review.

## 7. Handoff and lifecycle

Create `docs/handoffs/2026-09-19-ux-22-lodging-responsive-media.md` with exact changed files, generator parameters, original/generated byte table, measured savings, test counts, browser QA evidence, deferred decisions and invariants.

**Hard stop for Antigravity:** no commit, push, PR, merge, deploy, branch/worktree deletion. ChatGPT performs review and Git lifecycle after verification.
