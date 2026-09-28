# P2 Lodging checkout handoff — 28 Sep 2026

## Verified state

- Repository: `saisansan11/sigroom`; Production base `feat/lodging-v5-2` at `9145a79ba7abbdac045c343cf6b3a283835e16e1`.
- Cloud Run `sigroom` in `sixth-storm-439008-u2` / `asia-southeast3` still serves revision `sigroom-00066-88b` at 100% traffic.
- Dependency PR [#68](https://github.com/saisansan11/sigroom/pull/68) is open against `feat/lodging-v5-2`, with its checks passing.
- This phase uses branch `codex/p2-lodging-checkout`, implementation commit `a50d53bad3870d98484689eed6a3fa42fe5a31c5`, and stacked PR [#69](https://github.com/saisansan11/sigroom/pull/69) against `codex/p0-p1-production-stabilization`. PR #69 was mergeable when checked; all six CI checks, including **PR Safety Gate**, passed.

## Change and decision

- `bookings/lodging_models.py` and migration `0015` add a distinct `checked_out` release outcome and preserve check-in time and confirming staff in release history.
- `bookings/lodging_services.py` permits only authorized staff to check out an already checked-in guest, requires a reason, records `lodging_checked_out`, deletes active private access, and returns the bed. Checkout can close a stay after the cohort end date. Cancellation and no-show remain for guests who have not checked in.
- `bookings/lodging_operations.py`, `templates/lodging/workspace.html`, and `static/css/lodging_operations.css` add the staff checkout form, confirmation, and feedback.
- `bookings/tests_p2_lodging_checkout.py` covers history, audit, inventory, authorization, invalid transitions and reasons, after-end checkout, duplicate submission, and stale links.
- `docs/plans/2026-09-28-p2-lodging-checkout.md`, the production bug register, and the 100-run ledger preserve scope and evidence. The ledger remains **1/100** with run 001 failed and its QA data cleaned up.
- The QA cleanup reset used on the old Production revision is evidence handling only; it is not treated as the product checkout path.

## Gates observed

- Targeted lodging tests: 17 passed before adding the after-end case; the final case passed in the full suite.
- Full local regression: **645 passed, 286 warnings** with `pytest -q --disable-warnings --maxfail=1 --tb=short`.
- `manage.py check`: no issues. `makemigrations --check --dry-run`: no changes. `git diff --check`: passed.
- Browser QA against a temporary local test database: authorized staff checkout at 1280×844 and 390×844. The form rendered, submission showed success, occupied beds changed 1→0 and free beds 1→2. Neither viewport had horizontal overflow or page errors. Automated request checks also covered an outsider's 403 and stale public/private links.
- The pushed PR diff was reread on GitHub and contains the intended ten implementation, test, plan, and QA files. PR #69 CI: Repository checks, Critical regression, Full regression, Security audit, Accessibility audit, and PR Safety Gate all passed.

## Open work and invariants

- **P2 Production acceptance remains open.** Production still runs the old revision and has no checkout control. Do not mark `SIG-P2-001` closed until the supported path passes there.
- The 100-run campaign remains 1/100: Lodging 1, Online Teaching 0. Continue recording actual journeys and cleanup; do not infer passes from local tests.
- Keep QA records separate from real-user reservations, never expose private capability links or credentials, and verify active QA rows, temporary roles, audit, inventory, and 5xx after each Production batch.
- Preserve the unrelated untracked `.claude/handoffs/` directory in the worktree. Local environment warnings concerned empty SMTP host and insecure HTTP settings in the local env file; Django reported no system-check issues.
- Do not merge PR #68 or #69 without an explicit user instruction. Deployment requires separate authorization under the Production acceptance handoff.

## Next phase prompt

> Re-verify live Git/GitHub, PR #68 and #69, Cloud Run revision, and the SIGROOM workflow skill before taking action. Review the stacked PR dependency and current CI. With explicit merge/deployment authorization, promote the approved code, run migration checks, and repeat the P2 Lodging booking → check-in → staff checkout → bed release → stale-link acceptance on QA-only Production records. Then continue the 100-run ledger, including Online Teaching journeys, clean up each batch, and report actual totals and defects. Preserve unrelated work and do not touch real-user reservations.
