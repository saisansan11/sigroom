# UX-21A Lodging About Bright Hospitality Re-direction — Implementation Plan

**Date:** 2026-09-19
**Feature:** Redesign `/lodging/about/` from dark tech/AI template to a bright, welcoming hospitality showcase
**Phase:** UX-21A
**Base Branch:** `feat/lodging-v5-2` (commit `d8cdf11`, incorporating PR #43)
**Branch:** `feat/ux-21a-lodging-about-bright-hospitality`

---

## 1. Problem Diagnosis & Motivation

Following user feedback on `/lodging/about/`:
- *"ไม่ค่อยว้าว"*
- *"เหมือนเว็บ AI ทั่วไป"*
- *"สีมืดไป"*

### Specific Issues:
1. **Hero section is excessively dark**: Uses dark navy/black radial gradients with tech-grid overlays (`oklch(0.12 ...)` + 32px cyber dots).
2. **Generic AI/SaaS landing page vibe**: Heavy dark-glass surfaces, glowing cyan borders, and floating metric pills feel like a Web3 or developer tooling page.
3. **Pseudo-3D isometric schematic dominates without emotional warmth**: A blocky wireframe isometric card occupies 50% of the hero viewport, looking like a server rack monitor rather than a welcoming place to stay.
4. **Real photographs are sidelined**: High-quality photographs of actual rooms, beds, and facilities are buried well below the fold.
5. **Cold mood & tone**: Lacks the bright, airy, clean, and welcoming hospitality atmosphere of a premium student/trainee residence.

---

## 2. Redesign Principles & Target Aesthetic

1. **Real Imagery as the Hero Star**:
   - The hero visual prominently displays real room photographs with a layered/collage hospitality card treatment.
   - Highlighting room features (Floor 5 air-conditioned, separate individual beds, clean & secure).
2. **Bright, Sunlit Hospitality Palette**:
   - **Canvas/Background**: Luminous off-white / light sky-tinted background (`#f8fafc`, `#f0f9ff`, `#f0fdf4`).
   - **Surfaces/Cards**: Clean, crisp white (`#ffffff`) with gentle soft borders (`#e2e8f0`, `#bae6fd`) and natural drop shadows (`rgba(15, 23, 42, 0.06)`).
   - **Typography**: Deep navy / midnight slate (`#0f172a`, `#1e293b`) for headings and key text, slate (`#334155`, `#475569`) for body text. Zero harsh pure-black or dim muted text.
   - **Hospitality Accents**:
     - Sky blue (`#0284c7`, `#0ea5e9`, `#e0f2fe`) — primary friendly hospitality tone.
     - Mint / Aqua (`#0d9488`, `#14b8a6`, `#ccfbf1`) — freshness, air conditioning, sanitation.
     - Warm Sand / Amber (`#d97706`, `#fef3c7`) — comfort, warmth, individual bed spaces.
3. **3D as Supportive Accent, Not the Hero**:
   - The isometric 3D building element is retained as a refined, compact decorative preview badge/chip supporting the explorer section, rather than dominating the hero.
   - Preserves the clear disclaimer: `* ภาพจำลองเชิงสัญลักษณ์เพื่อความเข้าใจเบื้องต้น · ไม่ใช่แบบสถาปัตยกรรม BIM หรือระบุขนาดจริง`.
4. **Emotional Sequence**:
   - *"น่าเข้าพักก่อน"* (Welcoming hospitality first) -> *"ค่อยพาไปสำรวจผัง"* (then interactive explorer).
5. **Zero Functional/Logic Regressions**:
   - Interactive SVG floor explorer (`#lka-explorer`, Floor 4/5 switching, filters, zoom, keyboard/drag, text fallback) remains 100% operational with a crisp, bright architectural shell.
   - All authoritative rate constants and calculation notes preserved from single source of truth.
   - Zero modifications to backend business logic, booking flows, or data models.

---

## 3. Scoped Changes

| File | Change | Description |
|------|--------|-------------|
| `templates/lodging/lodging_about.html` | MODIFIED | Upgrade Hero to a real-photo-first hospitality showcase card with layered badges; elevate quick highlights, room experiences, gallery, facilities, and rates within a bright hospitality shell |
| `static/css/lodging_about.css` | MODIFIED | Complete palette overhaul: remove dark gradients/grids/neon glows; introduce bright hospitality tokens, white surfaces, soft shadows, sky/mint/amber accents, and crisp light explorer styling |
| `bookings/tests_ux20_lodging_about.py` | MODIFIED / MAINTAINED | Ensure all 19 contract tests pass with zero regression; update/add contract tests for bright hospitality visual tokens if needed |
| `docs/plans/2026-09-19-ux-21a-lodging-about-bright-hospitality.md` | NEW | This implementation plan |
| `docs/handoffs/2026-09-19-ux-21a-lodging-about-bright-hospitality.md` | NEW | Final handoff documentation |

---

## 4. Quality Gate Verification

1. Relevant lodging/about tests:
   - `uv run pytest bookings/tests_ux20_lodging_about.py -v`
   - `uv run pytest bookings/tests_ux17_showcase.py -v`
2. Django checks:
   - `uv run manage.py check`
   - `uv run manage.py makemigrations --check --dry-run`
3. Whitespace / Git hygiene:
   - `git diff --check`
4. Browser QA across 5 responsive viewports:
   - 360px (compact mobile)
   - 390px (standard mobile)
   - 430px (large mobile)
   - 768px (tablet portrait)
   - 1280px (desktop)
   - Verify zero horizontal overflow, interaction correctness (floor switching, filters, zoom, room panel), and capture before/after screenshots.
5. Pull Request:
   - Isolated branch `feat/ux-21a-lodging-about-bright-hospitality` targeting base `feat/lodging-v5-2`.
   - Wait for GitHub Actions CI.
   - Present summary and stop for ChatGPT/user approval to merge.
