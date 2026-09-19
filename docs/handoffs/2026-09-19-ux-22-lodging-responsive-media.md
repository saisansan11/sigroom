# UX-22 — Lodging Responsive Media Pipeline Handoff

**Date:** 2026-09-19
**Flow:** Flow 2
**Branch:** `feat/ux-22-lodging-responsive-media`
**Base:** `a1ffb21fea1492197e9fca0434837d4b551855e5` (`feat/lodging-v5-2`)
**Worktree:** `C:\Users\RTA\Documents\ChatGPT-Antigravity\worktrees\sigroom-ux22-responsive-media`

## 1. Scope and result

UX-22 adds deterministic responsive modern image delivery for the public `/lodging/about/` showcase without changing booking logic, auth, permissions, models, migrations, or the existing hospitality design.

The page keeps every original JPG/PNG URL as the final `<img>` fallback. Seven photographic originals now use semantic `<picture>` markup with AVIF first, WebP second, and original JPG fallback. Three PNG diagram/document assets use full-size lossless WebP modern sources with original PNG fallback after measured savings and exact decoded-pixel equality were verified.

No speculative image preload was added. The hero retains `loading="eager"`, `fetchpriority="high"`, `decoding="async"`; all 12 below-fold fallback images remain lazy and non-high-priority.

## 2. Changed files

Tracked/source/docs:
- `static/css/lodging_about.css`
- `templates/lodging/lodging_about.html`
- `bookings/tests_ux22_responsive_media.py`
- `scripts/generate_showcase_media.py`
- `docs/plans/2026-09-19-ux-22-lodging-responsive-media.md`
- `docs/handoffs/2026-09-19-ux-22-lodging-responsive-media.md`

Generated media directory contains exactly 29 files under `static/img/showcase/generated/`:
- `bath1-640.avif`, `bath1-640.webp`, `bath1-1280.avif`, `bath1-1280.webp`
- `bath2-640.avif`, `bath2-640.webp`, `bath2-1280.avif`, `bath2-1280.webp`
- `bath3-640.avif`, `bath3-640.webp`, `bath3-1280.avif`, `bath3-1280.webp`
- `room2p_222-640.avif`, `room2p_222-640.webp`
- `room2p_444-640.avif`, `room2p_444-640.webp`, `room2p_444-1280.avif`, `room2p_444-1280.webp`
- `room4p_3421-640.avif`, `room4p_3421-640.webp`, `room4p_3421-1280.avif`, `room4p_3421-1280.webp`
- `room4p_4444-640.avif`, `room4p_4444-640.webp`, `room4p_4444-1280.avif`, `room4p_4444-1280.webp`
- `floor4.webp`, `floor5.webp`, `rates.webp`

All original JPG and PNG files remain present and unchanged.

## 3. Generator contract

`script/generate_showcase_media.py` is deterministic and has an exact-manifest `--check` mode.

Encoding parameters:
- photo WebP: quality 80, method 6
- photo AVIF: quality 65
- resize: Pillow LANCZOS; aspect ratio preserved
- never upscale: 640w for eligible photos, 1280w only when source width is at least 1280
- PNG modern candidates: full intrinsic size, lossless WebP, method 6, `exact=True`
- orientation normalized with EXIF transpose

`--check` verifies:
- missing generated files
- unexpected/extra files
- exact deterministic output bytes
- format and dimensions
- stale/corrupt outputs
- lossless PNG→WebP decoded pixel equality

Final generator verification: **PASS — `All expected variants are present, exact, and current.`**

## 4. Measured media sizes

| Source | Generated candidate | Dimensions | Original | Generated | Reduction |
|---|---|---:|---:|---:|---:|
| bath1.jpg | bath1-640.avif | 640×480 | 197,027 B | 19,315 B | 90.2% |
| bath1.jpg | bath1-640.webp | 640×480 | 197,027 B | 18,638 B | 90.5% |
| bath1.jpg | bath1-1280.avif | 1280×960 | 197,027 B | 49,425 B | 74.9% |
| bath1.jpg | bath1-1280.webp | 1280×960 | 197,027 B | 45,692 B | 76.8% |
| bath2.jpg | bath2-640.avif | 640×480 | 275,856 B | 26,079 B | 90.5% |
| bath2.jpg | bath2-640.webp | 640×480 | 275,856 B | 26,372 B | 90.4% |
| bath2.jpg | bath2-1280.avif | 1280×960 | 275,856 B | 80,822 B | 70.7% |
| bath2.jpg | bath2-1280.webp | 1280×960 | 275,856 B | 75,538 B | 72.6% |
| bath3.jpg | bath3-640.avif | 640×480 | 252,337 B | 25,038 B | 90.1% |
| bath3.jpg | bath3-640.webp | 640×480 | 252,337 B | 26,378 B | 89.5% |
| bath3.jpg | bath3-1280.avif | 1280×960 | 252,337 B | 69,820 B | 72.3% |
| bath3.jpg | bath3-1280.webp | 1280×960 | 252,337 B | 71,512 B | 71.7% |
| room2p_222.jpg | room2p_222-640.avif | 640×480 | 42,688 B | 12,771 B | 70.1% |
| room2p_222.jpg | room2p_222-640.webp | 640×480 | 42,688 B | 11,698 B | 72.6% |
| room2p_444.jpg | room2p_444-640.avif | 640×480 | 106,889 B | 12,222 B | 88.6% |
| room2p_444.jpg | room2p_444-640.webp | 640×480 | 106,889 B | 10,978 B | 89.7% |
| room2p_444.jpg | room2p_444-1280.avif | 1280×960 | 106,889 B | 34,069 B | 68.1% |
| room2p_444.jpg | room2p_444-1280.webp | 1280×960 | 106,889 B | 27,126 B | 74.6% |
| room4p_3421.jpg | room4p_3421-640.avif | 640×480 | 270,183 B | 20,749 B | 92.3% |
| room4p_3421.jpg | room4p_3421-640.webp | 640×480 | 270,183 B | 21,850 B | 91.9% |
| room4p_3421.jpg | room4p_3421-1280.avif | 1280×960 | 270,183 B | 63,432 B | 76.5% |
| room4p_3421.jpg | room4p_3421-1280.webp | 1280×960 | 270,183 B | 60,684 B | 77.5% |
| room4p_4444.jpg | room4p_4444-640.avif | 640×480 | 132,608 B | 14,506 B | 89.1% |
| room4p_4444.jpg | room4p_4444-640.webp | 640×480 | 132,608 B | 13,332 B | 89.9% |
| room4p_4444.jpg | room4p_4444-1280.avif | 1280×960 | 132,608 B | 39,344 B | 70.3% |
| room4p_4444.jpg | room4p_4444-1280.webp | 1280×960 | 132,608 B | 33,438 B | 74.8% |
| floor4.png | floor4.webp | 961×596 | 32,084 B | 9,488 B | 70.4% |
| floor5.png | floor5.webp | 955×411 | 14,073 B | 4,274 B | 69.6% |
| rates.png | rates.webp | 736×781 | 75,780 B | 11,368 B | 85.0% |

The 10 original showcase files total 1,399,525 B. The generated directory contains multiple resolution/format alternatives and totals 935,958 B; that generated-directory total is **not** presented as a page-transfer comparison because a browser selects only one candidate per rendered occurrence.

## 5. Automated quality gates

- UX-22 + UI5 + UX-20 + UX-21A + UX-21B targeted regression: **45/45 PASS**
- generator `--check`: **PASS**
- `git diff --check`: **PASS**
- `python manage.py check`: **System check identified no issues (0 silenced)**
- `python manage.py makemigrations --check --dry-run`: **No changes detected**
- full `pytest -q`: **497 passed, 205 warnings, 0 failures in 76.30s**

`F:/ogn_ROOM/.env` was used only as the opaque `--env-file` argument. Its contents were not read, copied, or printed.

## 6. Real Chrome Browser QA

Route/persona: public Guest at `http://127.0.0.1:8013/lodging/about/` using isolated Google Chrome profiles/processes and CDP-controlled exact viewport metrics.

| Viewport | scrollWidth | innerWidth | Horizontal overflow | Modern currentSrc | Loaded images |
|---|---:|---:|---|---:|---:|
| 360×800 | 345 | 360 | No | 13/13 | 13/13 |
| 390×844 | 375 | 390 | No | 13/13 | 13/13 |
| 430×932 | 415 | 430 | No | 13/13 | 13/13 |
| 768×1024 | 753 | 768 | No | 13/13 | 13/13 |
| 1280×800 | 1265 | 1280 | No | 13/13 | 13/13 |
| 1440×900 | 1425 | 1440 | No | 13/13 | 13/13 |

Browser contract verified at all six viewport targets:
- hero resolves to AVIF (`room4p_3421-640.avif`; tablet selected `room4p_3421-1280.avif`)
- hero remains eager / high priority / async
- hero network request count = exactly 1 per navigation
- hero initial and final Chrome network priority = `High`
- all 12 below-fold fallback `<img>` nodes = lazy
- below-fold eager count = 0
- below-fold high-priority count = 0
- 13/13 images retain explicit width/height
- image preload count = 0
- browser original JPG/PNG image requests = 0 when modern formats are supported
- runtime exceptions = 0
- application console errors = 0

Interaction path verified at all six viewport targets:
1. Floor 5 toggle → `aria-pressed=true`, Room 501 renders.
2. Floor 4 toggle → `aria-pressed=true`, Room 401 renders.
3. Click Room 401 → room panel opens and displays `ห้อง 401`, `ชั้น 4`, `ปรับอากาศ`, `2 คน`.

The only observed HTTP 4xx during QA is the pre-existing global `/favicon.ico` 404. It is unrelated to UX-22 media and is already documented as baseline debt in earlier SIGROOM UX handoffs. No UX-22 image/static asset failed.

Original fallback URL verification: **10/10 original JPG/PNG URLs returned HTTP 200** under the QA Django server.

## 7. Independent review and safety invariants

Complete diff review found no change outside UX-22 scope. Source changes are limited to the lodging-about responsive `<picture>` markup and the minimal `.lka-picture` CSS wrapper; the remaining additions are the generator, tests, docs, and generated media.

Verified invariants:
- no booking/business-logic changes
- no auth/permission changes
- no model/database/migration changes
- no original JPG/PNG deletion or modification
- no speculative preload
- hero priority contract preserved
- below-fold lazy contract preserved
- no upscaled generated candidates
- PNG lossless modern variants preserve exact decoded pixels
- isolated worktree only; untracked work in `F:\ogn_ROOM` untouched
- no deployment performed

## 8. Lifecycle state

At handoff-writing time the branch has not yet been merged or deployed. After the final pytest result is recorded, perform final diff/status review, stage only the scoped UX-22 files, commit, push, open a PR into `feat/lodging-v5-2`, and verify CI/mergeability.

**Hard stop:** do not merge until the user gives explicit approval.
