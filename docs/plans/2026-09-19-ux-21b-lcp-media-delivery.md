# UX-21B Lodging About LCP & Media Delivery Polish — Implementation Plan

**Date:** 2026-09-19
**Feature:** Optimize LCP and media delivery for `/lodging/about/`
**Phase:** UX-21B
**Base Commit:** `c9c0ca2413ecc395f9b9d37df1af7378e2a42db9`
**Branch:** `feat/ux-21b-lcp-media-delivery`
**Worktree:** `C:\Users\RTA\Documents\ChatGPT-Antigravity\worktrees\sigroom-ux21b-lcp-media`

---

## 1. Problem Diagnosis & Evidence

### Current State (from UX-21A):
1. **Hero LCP Image is Lazy Loaded**:
   In `templates/lodging/lodging_about.html` line 65:
   ```html
   <img src="{% static 'img/showcase/room4p_3421.jpg' %}" alt="ห้องพักปรับอากาศ บรรยากาศโปร่งสบาย" width="640" height="480" loading="lazy" decoding="async" class="lka-hero-main-img">
   ```
   Setting `loading="lazy"` on the primary above-the-fold hero photograph (`room4p_3421.jpg`) is a recognized Core Web Vitals anti-pattern. The browser defers fetching the image until after DOM parsing and layout calculation, needlessly delaying Largest Contentful Paint (LCP).

2. **Below-Fold Lazy Loading Discipline**:
   There are 12 additional images across the page:
   - 2 Room Experience cards (`room2p_444.jpg`, `room4p_3421.jpg`)
   - 2 Floor overview diagrams (`floor4.png`, `floor5.png`)
   - 4 Stay gallery photos (`room2p_444.jpg`, `room2p_222.jpg`, `room4p_3421.jpg`, `room4p_4444.jpg`)
   - 3 Bathroom facilities photos (`bath1.jpg`, `bath2.jpg`, `bath3.jpg`)
   - 1 Official rates announcement (`rates.png`)
   All of these are below the fold and correctly use `loading="lazy"`. This behavior must strictly be preserved.

3. **Preload Spam & Redundant Requests Prevention**:
   The hero image is directly present in the static HTML markup. Adding speculative `<link rel="preload">` in the `<head>` can cause network contention, double downloads if request credentials/headers differ, or wasted bandwidth. Modern browser preload scanners already discover `<img>` tags in HTML markup early when prioritized with `fetchpriority="high"`.

4. **Image Compression & Format Transcoding Evaluation**:
   The static showcase images were inspected:
   - `room4p_3421.jpg`: 270,183 bytes (natural dimensions 1479×1109, rendered in HTML layout with explicit attributes `width="640"` `height="480"`).
   - Total showcase folder: ~1.5 MB across 10 files.
   Given the modest file size, fast local static serving, and existing contract tests across UX-17, UX-20, and UX-21A that assert specific asset filenames (`room4p_3421.jpg`, `room2p_444.jpg`, etc.), changing image formats to WebP/AVIF or replacing binary files introduces unnecessary regression risk and git churn. Image compression/format transcoding is thus deferred with clear rationale to a future dedicated media-pipeline phase.


---

## 2. Planned Changes & Architecture

### A. Template Media Attributes (`templates/lodging/lodging_about.html`):
- Update the hero showcase image (`room4p_3421.jpg`) from `loading="lazy"` to:
  ```html
  <img src="{% static 'img/showcase/room4p_3421.jpg' %}" alt="ห้องพักปรับอากาศ บรรยากาศโปร่งสบาย" width="640" height="480" loading="eager" fetchpriority="high" decoding="async" class="lka-hero-main-img">
  ```
- Retain explicit `width="640"` and `height="480"` for aspect ratio stability (zero CLS).
- Retain `decoding="async"` for non-blocking main-thread painting.
- Keep all other 12 below-the-fold images strictly `loading="lazy"`.
- Do not introduce `<link rel="preload">` tags.

### B. Targeted Contract Tests (`bookings/tests_ux21b_lcp_media.py`):
Create targeted tests covering:
1. Public 200 access.
2. Hero image LCP contract: `loading="eager"` and `fetchpriority="high"` on `.lka-hero-main-img`.
3. Dimension and layout stability contract: explicit `width` and `height` attributes on hero and showcase images (protecting CLS).
4. Below-fold lazy loading contract: exactly 12 below-the-fold images have `loading="lazy"`.
5. Preload hygiene: no speculative `<link rel="preload" as="image">` in rendered HTML.
6. Multi-appearance asset hygiene: verify `room4p_3421.jpg` appears in hero as eager, while subsequent instances in experience and gallery remain lazy.

---

## 3. Strict Scoping & Invariants

- **Zero backend modifications**: No changes to models, views, forms, urls, or database migrations.
- **Zero layout regressions**: No CSS restructuring; preserve bright hospitality theme, interactive 3D explorer, and typography from UX-21A.
- **Preserve existing contract tests**: All 6 tests in `tests_ux21a_lodging_about.py` and all 19 tests in `tests_ux20_lodging_about.py` must continue to pass cleanly.

---

## 4. Verification & Quality Gates

1. **Targeted Tests**: `uv run --env-file F:/ogn_ROOM/.env pytest bookings/tests_ux21b_lcp_media.py -v`
2. **Regression Suite**: `uv run --env-file F:/ogn_ROOM/.env pytest bookings/tests_ux20_lodging_about.py bookings/tests_ux21a_lodging_about.py -v`
3. **Django Checks**: `uv run --env-file F:/ogn_ROOM/.env python manage.py check`
4. **Migration Check**: `uv run --env-file F:/ogn_ROOM/.env python manage.py makemigrations --check --dry-run`
5. **Git Whitespace Check**: `git diff --check`
6. **Full Test Suite**: `uv run --env-file F:/ogn_ROOM/.env pytest -q`
7. **Real Browser QA**: Chrome headless across 6 viewports (360x800, 390x844, 430x932, 768x1024, 1280x800, 1440x900) verifying no horizontal overflow, correct DOM attributes, zero console errors, and verified asset loading.
8. **Independent Review**: Review final diff, write handoff document, and report concise summary.
