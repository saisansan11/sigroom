# SIGROOM UX-7 — Outage Management Mobile Clarity — Handoff

## Status
`LOCAL PASS — PR/CI PENDING`

## Source of truth / base
- Repo: `saisansan11/sigroom`
- Protected integration branch: `feat/lodging-v5-2`
- Verified base: `bca392d7e4e27699657a8cbc48097c2ca1e6952b` (merge of PR #28 / UX-6)
- Branch: `feat/ux-7-outage-mobile`
- Worktree: `C:\Users\RTA\Documents\ChatGPT-Antigravity\worktrees\sigroom-ux7-outage-mobile`
- Canonical `F:\ogn_ROOM` had unrelated stale UX-3 changes and was intentionally left untouched.

## Why UX-7
The custodian outage page still inherited generic `.table-wrap table { min-width: 42rem; }`. On phones this made the active operational action `สิ้นสุดก่อนกำหนด` require horizontal scrolling. UX-7 fixes only that presentation friction.

## Files in scope
- `templates/resources/outage.html`
- `static/css/app.css`
- `resources/tests_ux7.py`
- `docs/plans/2026-09-16-ux-7-outage-management-mobile.md`
- this handoff

Local QA file `ux7-outage-qa.html` is disposable/untracked evidence and must never be staged.

## Implementation
### Template
The existing outage list remains one canonical semantic table. Only page-scoped hooks were added:
- `outage-list-wrap`, `outage-table`
- `outage-row`, `outage-row-active`, `outage-row-ended`
- `outage-time`, `outage-reason`, `outage-status-cell`, `outage-action-cell`
- `outage-end-form`, `outage-end-button`

Preserved unchanged:
- custodian authorization behavior
- `{% if item.ended_early_at %}` / `{% if not item.ended_early_at %}` semantics
- POST endpoint `{% url 'resources:outage_end' item.id %}`
- CSRF token
- exact button copy `สิ้นสุดก่อนกำหนด`
- outage creation/preview/confirm flows

### CSS
Marker: `/* UX-7 Outage Management Mobile Clarity */`.
Only under `@media (max-width: 47.99rem)`:
- remove the generic table min-width for this page only
- visually hide `<thead>` while retaining it in DOM
- render each row as status → time → reason → action card
- long Thai reason wraps with `overflow-wrap:anywhere`
- active action is full-width and ≥44 px
- ended row uses dashed border + soft surface, not color alone
- ended row's empty action cell is hidden with a selector specific enough to override the general mobile `td { display:block }` rule

At exactly 768 px and above, the original semantic desktop table remains.

## Independent review / Browser finding
Initial implementation was delegated to Codex. Independent Chrome QA found one real CSS specificity defect: the ended row's empty action cell still computed `display:block`. The finding was sent back to Codex; selector changed to:
`.outage-table .outage-row-ended > .outage-action-cell { display: none; }`
and `resources/tests_ux7.py` gained a regression guard. All affected gates were rerun after the fix.

## Automated verification — final code
- Targeted `resources/tests.py resources/tests_ux7.py`: **9 passed, 6 warnings**
- `manage.py check`: **0 issues**
- `manage.py makemigrations --check --dry-run`: **No changes detected**
- Full pytest: **244 passed, 117 warnings in 72.94s**
- `git diff --check`: PASS

Known warnings only:
- local LAN `DJANGO_SECURE=0` warning
- Django 6 URLField transition warning
- isolated worktree has no collected `staticfiles/` directory

## Browser QA — final code
Persona: disposable local custodian fixture rendered by Django authenticated test client. Active + ended-early outages were created locally; active reason intentionally contained long Thai text. Fixture rows were deleted after render. Managed Chrome exercised the real rendered page; destructive POST was not submitted.

Viewports: **360 / 390 / 430 / 768 / 1280 / 1440**.

Final results:
- 360/390/430: no page/wrapper/row/reason horizontal overflow; table `display:block`; `min-width:0`; row grid areas `status`, `time`, `reason`, `action`; action height ≈51 px; ended row dashed; ended action cell `display:none`.
- 768/1280/1440: mobile media query false; table/row return to desktop semantic layout; no horizontal overflow.
- keyboard: actual Tab focus reached `สิ้นสุดก่อนกำหนด` with visible cyan ≈2.7 px outline.
- changed resources: app CSS + HTMX loaded; no `Network.loadingFailed`; no JS exceptions.
- static QA server only showed expected manifest/favicon 404s because it does not implement Django app routes; not a changed-resource failure.

## Security / business invariants
UX-7 must not change:
- who can manage an outage
- overlap/conflict behavior
- booking status restoration when ending an outage
- notification/audit semantics
- model/schema/transactions
- privacy behavior
No such code was changed.

## PR / CI
PR: pending at this handoff commit.
GitHub `SIGROOM PR Safety` / aggregate `PR Safety Gate`: pending. Do not report READY FOR MERGE until the final PR HEAD is green.

## Deferred next candidate
Do not assume automatically. After UX-7 merge, refetch the protected integration branch and inspect remaining live friction. `templates/approvals/delegation.html` was observed as another generic table candidate, but it must be revalidated against the newly merged source before selecting UX-8.

## Next-chat prompt
Continue SIGROOM from live repo after UX-7. Read `AGENTS.md`, `.agents/skills/sigroom-development-workflow/SKILL.md`, UI refresh profile, and this handoff. Fetch `origin/feat/lodging-v5-2`, verify PR/CI/base state, then discover the next evidence-based UX friction. Preserve all booking/lodging/outage permissions, privacy, conflict, and transaction invariants. Use an isolated worktree and the full mandatory gate including Browser QA and `PR Safety Gate`.
