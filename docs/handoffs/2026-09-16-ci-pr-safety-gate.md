# SIGROOM CI / PR Safety Gate — Handoff

## Status
`GITHUB CI PASS + BRANCH PROTECTION ACTIVE — FINAL DOCS CI PENDING`

## Verified source of truth
- Repository: `saisansan11/sigroom`
- Default/integration branch: `feat/lodging-v5-2`
- Base SHA used for this phase: `5ee980c6134433977947f03203bc23b0fa0dbe9c` (merged PR #26)
- Isolated branch: `chore/ci-pr-safety-gate`
- Implementation commit: `54bf134cc4360336f5c766cf03c7e199f41624a2`
- PR: #27 — `CI: Add SIGROOM PR Safety Gate`
- PR URL: https://github.com/saisansan11/sigroom/pull/27
- Canonical `F:\ogn_ROOM` contained unrelated local changes and was not used for implementation.

## Files changed
1. `.github/workflows/pr-safety-gate.yml`
   - GitHub Actions safety workflow.
   - Python 3.12 + PostgreSQL 16.
   - immutable SHA pins for checkout/setup-python/setup-uv.
   - pinned uv 0.11.19 and pip-audit 2.10.1.
   - least-privilege `contents: read`.
   - concurrency cancellation.
   - four verification jobs plus aggregate `PR Safety Gate`.
2. `.agents/skills/sigroom-development-workflow/checklists/release-gate.md`
   - future PRs explicitly require `PR Safety Gate` once available.
3. `docs/build-plan.md`
   - records that CI gate was intentionally brought forward before pilot completion.
4. `docs/plans/2026-09-16-ci-pr-safety-gate.md`
   - implementation/verification/rollout rationale and acceptance criteria.
5. `docs/handoffs/2026-09-16-ci-pr-safety-gate.md`
   - this handoff.

## CI design
Jobs observed on GitHub:
- `Repository checks`
- `Critical regression`
- `Full regression`
- `Security audit`
- aggregate `PR Safety Gate`

`PR Safety Gate` uses `if: always()` and fails unless every subordinate job result is `success`, giving branch protection one stable required-check context.

## Local verification observed 2026-09-16
- workflow YAML/structure validation: PASS.
- action references: 12 immutable 40-character SHAs.
- Python runtime: 3.12.10.
- Critical regression selection: **68 passed**.
- Full regression: **237 passed**.
- `uv run manage.py check`: PASS / 0 issues.
- `uv run manage.py makemigrations --check --dry-run`: No changes detected.
- locked hashed runtime dependency export + `pip-audit==2.10.1`: **No known vulnerabilities found**.
- Django production-like deploy check: only documented `security.W005` and `security.W021` remain; workflow fails if any other Django deploy security warning/error appears.
- `git diff --check`: PASS.
- Browser QA: not applicable because this phase changes automation/docs only.

## GitHub CI observed
First real PR run:
- Workflow: `SIGROOM PR Safety`
- Run ID: `35029859996`
- Result: **SUCCESS**.
- `Repository checks`: SUCCESS.
- `Critical regression`: SUCCESS.
- `Full regression`: SUCCESS.
- `Security audit`: SUCCESS.
- `PR Safety Gate`: SUCCESS.

One non-blocking setup-uv cache annotation was observed: parallel jobs attempted to reserve the same cache key. The job still passed and dependencies/tests were unaffected. This is CI cache noise, not a correctness failure.

## Branch protection active on `feat/lodging-v5-2`
Verified through GitHub after applying protection:
- required status check: `PR Safety Gate`.
- strict/up-to-date branch required: `true`.
- pull-request review rule enabled with required approving reviews = `0` (single-maintainer repo; PR required without self-review deadlock).
- rules enforced for administrators: `true`.
- force pushes: disabled.
- branch deletion: disabled.
- no user/team push restriction added.

This means even the repository administrator should not be able to bypass the required PR/check flow under normal GitHub protection behavior.

## Security decisions
- No repository/deployment secrets are used by CI.
- External Actions are pinned to immutable SHAs.
- Runtime dependency audit comes from the hashed `uv.lock` export.
- `security.W005` (`SECURE_HSTS_INCLUDE_SUBDOMAINS`) and `security.W021` (`SECURE_HSTS_PRELOAD`) are intentionally not auto-enabled merely to make CI green; enabling them requires an explicit domain-wide HTTPS/HSTS policy decision.

## Invariants for future phases
- Do not rename/remove `PR Safety Gate` casually; branch protection depends on this exact context.
- Do not add `write` permissions to CI without a concrete need and review.
- Keep PostgreSQL-backed tests in CI because SIGROOM relies on PostgreSQL-specific constraints, including `btree_gist` behavior.
- Do not weaken/skip failed tests merely to make the gate green.
- Browser QA remains a manual project gate for user-facing changes; CI does not replace it.
- Merge remains an explicit user decision even when GitHub CI is green.

## Deferred notes
- HSTS includeSubDomains/preload policy needs a future deployment/domain decision.
- setup-uv cache reservation warning can be optimized later if desired; it does not fail the gate.

## Final steps for this phase
1. Commit and push this handoff/update.
2. Require the new PR-triggered CI run on the latest HEAD to pass again.
3. Re-query PR mergeability/checks and branch protection.
4. Report `READY FOR MERGE` and wait for explicit user merge approval.
5. After merge, verify the workflow also passes on the protected default-branch push event.

## Ready-to-paste next-chat prompt
Continue SIGROOM from live repo state. Re-read `AGENTS.md` and `.agents/skills/sigroom-development-workflow/SKILL.md`. Verify PR #27 and branch protection live from GitHub before trusting this handoff. The CI phase added `.github/workflows/pr-safety-gate.yml` with aggregate required check `PR Safety Gate`; default branch `feat/lodging-v5-2` is protected with strict required checks, PR-required flow, admin enforcement, force-push/delete disabled, and 0 required approvals for the single-maintainer workflow. Do not merge without explicit user instruction. After PR #27 is merged, verify the push-triggered CI run on the default branch passes, then continue the next scoped SIGROOM phase in a new isolated branch/worktree.
