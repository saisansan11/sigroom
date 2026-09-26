# SIGROOM Lodging About Redesign — Implementation Plan

Date: 2026-09-25
Flow: ChatGPT plan/review/QA + Antigravity implementation
Branch: `feat/lodging-about-redesign-20260925`
Base: `88fbfbc0d04b79c7b4ec37655be54aa98bc16bb7` (`origin/feat/lodging-v5-2`)
Production deployment: NOT authorized by this plan

## Goal
Redesign `/lodging/about/` into a bright, premium, school-appropriate lodging showcase that is mobile-first, visually lighter, easier to scan, and faster to act on. Keep real room imagery and authoritative lodging information, while reducing nested cards, scroll length, and the burden of the embedded 3D explorer on mobile.

## Non-negotiable invariants
- Keep public route and existing booking/general-request routes working.
- Preserve authoritative room facts and rate values from server-side source of truth; do not invent lodging data.
- Preserve existing floor/room mapping, room selection, filters, accessibility semantics, and no-PII behavior.
- Keep all media local; no CDN, Spline, Three.js, WebGL, or new remote dependency.
- Preserve floor-plan fallback and textual fallback.
- Preserve access to facilities, rates, original notice, and site map; they may be compressed/collapsed, not silently removed.
- Maintain reduced-motion behavior and prevent horizontal page overflow.

## Target information architecture
1. Compact existing site header/navigation
2. Hero: short headline + real room photo + two primary actions
3. Compact key facts: 87 rooms / 234 beds / floors 4–5 / 2–4 persons per room
4. Real-photo gallery with concise captions; mobile horizontal snap, desktop editorial mosaic
5. 3D preview hub with three explicit choices:
   - Open interactive 3D
   - Check room availability / booking flow
   - View room list / textual fallback
6. Interactive explorer shell
   - Mobile: collapsed by default; user explicitly opens it
   - Desktop/tablet-wide: expanded automatically by JS enhancement
   - Existing explorer DOM hooks and room behavior retained
7. Four-step user journey
8. Why SIGROOM / system advantages
9. Compact “information you should know” area that retains facilities, rates, original notice, floor-plan/site-map access without making the main narrative excessively long
10. FAQ (4–5 questions)
11. Final CTA

## Hero redesign
- Remove the pseudo-3D mockup from inside the hero and the nested card-within-card composition.
- Keep the best real room photograph (`room4p_3421`) as the hero visual using existing AVIF/WebP responsive sources.
- Copy should be shorter and correct the awkward existing second line.
- Primary CTA: `สำรวจห้องพัก` → gallery/3D preview area.
- Secondary CTA: `ดูแผนผัง 3D` → opens/focuses explorer.
- Keep a direct booking/general-request path visible without competing with hero hierarchy.
- Use light background, teal/cyan + navy accents, soft gradient, restrained shadow, no heavy borders.

## Gallery redesign
- Reuse only existing real photos and optimized derivatives.
- Desktop: one larger lead image plus supporting images in an editorial/mosaic layout.
- Mobile: horizontal scroll-snap carousel with one dominant card at a time; no page-level horizontal overflow.
- Captions remain concise and factual.

## 3D mobile behavior
- Add an explicit preview/launcher above the explorer.
- Wrap the heavy interactive explorer in a semantic expandable shell (`details` or equivalent accessible progressive enhancement).
- On narrow mobile, interactive explorer is closed on first load so it does not consume ~570px+ of vertical space before the user asks for it.
- On desktop/wide layout, JS may auto-open the shell to preserve existing desktop workflow.
- “ดูแผนผัง 3D” opens the shell, scrolls/focuses safely, and preserves keyboard operation.
- “ดูเป็นรายการห้อง” exposes the existing textual fallback without requiring 3D.
- Existing IDs (`lka-explorer`, floor toggles, filters, canvas, scene, room panel, controls) must remain stable unless tests and all JS references are migrated together.

## Scroll-length reduction
- Remove duplicated room-experience narrative where the same facts are already represented by stats/gallery/3D.
- Convert dense facilities/rates/original-plan information into compact progressive-disclosure blocks while preserving content and authoritative variables.
- Reduce repeated section headers, large card padding, and oversized vertical gaps on mobile.
- Keep final CTA visible without requiring users to pass repeated explanations.

## New content blocks
### Four steps
1. สำรวจห้องพัก — ดูภาพและแผนผัง
2. ตรวจสอบห้องว่าง — เลือกห้องที่เหมาะสม
3. จองผ่านระบบ — ทำรายการออนไลน์
4. พร้อมเข้าพัก — ใช้งานอย่างเป็นระบบ

### Why SIGROOM
- สำรวจห้องได้ล่วงหน้า
- ดูห้องว่างและเข้าสู่การจองได้เร็ว
- มีแผนผัง 3D พร้อมทางเลือกแบบข้อความ
- ใช้งานได้ทั้งมือถือและคอมพิวเตอร์
- ช่วยให้การจัดที่พักเป็นระบบมากขึ้น

### FAQ
Keep concise answers to:
- ที่พักอยู่ชั้นใด
- มีทั้งหมดกี่ห้อง/เตียง
- ดูห้องว่างที่ไหน
- 3D ใช้บนมือถือได้หรือไม่
- ต้องล็อกอินเมื่อใด / public information versus booking action

## Files expected to change
- `templates/lodging/lodging_about.html`
- `static/css/lodging_about.css`
- `static/css/lodging_about_ux27.css` (only where 3D responsive behavior needs adjustment)
- `static/js/lodging_about_explorer.js` (launcher/expand behavior only; do not rewrite room geometry)
- `bookings/tests_ux20_lodging_about.py`
- `bookings/tests_ux21a_lodging_about.py`
- `tests/a11y/room-plan.spec.js` and/or a focused lodging-about browser spec if required for mobile launcher behavior

## Test requirements
Targeted first:
- lodging about contract tests
- lodging showcase/performance tests affected by markup/media changes
- room-plan Playwright/a11y tests

Mandatory gates:
- `uv run manage.py check`
- `uv run manage.py makemigrations --check --dry-run`
- full `uv run pytest`
- `git diff --check`

## Browser QA
At minimum verify:
- Mobile 390x844 (iPhone-class)
- Mobile 412x915 (Android-class)
- Tablet ~768x1024
- Desktop 1440x900

For each relevant viewport:
- no page-level horizontal overflow
- hero and CTA visible/usable
- gallery readable and swipe/scroll behavior correct
- mobile explorer initially compact; launcher opens it
- desktop explorer works with floor/filter/room selection
- textual fallback reachable
- FAQ/details keyboard operable
- real images load without distortion
- Thai text wraps cleanly
- no critical axe violations

## Release discipline
- Antigravity implements only in this isolated worktree.
- ChatGPT/lnwjud reviews diff and runs tests/Browser QA.
- After green gates, commit/push and open PR against `feat/lodging-v5-2`.
- Do not merge and do not Production Deploy without a separate explicit approval.
