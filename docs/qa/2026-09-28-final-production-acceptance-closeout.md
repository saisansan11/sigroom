# SIGROOM Final Production Acceptance Closeout — 28 September 2026

## Decision

**FINAL PRODUCTION ACCEPTANCE = PASS**

This record closes the Production Acceptance campaign for SIGROOM after the merged lodging stack, production deployment, P2 Lodging E2E, P3 Online Teaching verification, and the 100-run real-user simulation.

This is a documentation-only closeout. It does **not** authorize or apply any further production behavior change, deployment, schema change, data migration, permission change, or cleanup mutation.

## Authoritative production baseline

- Repository: `saisansan11/sigroom`
- Integration / production branch: `feat/lodging-v5-2`
- Accepted PR stack: `#70 -> #69 -> #68`, merged into the production base
- Exact accepted production SHA: `edbe58fc7a2b3513c4ae76f9c81c1175f94a34be`
- Cloud Run service: `sigroom`
- Google Cloud project: `sixth-storm-439008-u2`
- Region: `asia-southeast3`
- Accepted revision: `sigroom-00067-cpc`
- Latest created revision: `sigroom-00067-cpc`
- Latest ready revision: `sigroom-00067-cpc`
- Traffic: **100%** to `sigroom-00067-cpc`
- No later production deployment was performed during closeout.

## Acceptance result matrix

| Gate | Final result | Evidence identity |
| --- | --- | --- |
| P1 role-specific production acceptance | PASS | Non-staff / non-superuser QA account with temporary role grants revoked after verification |
| P2 Production Lodging E2E | PASS | Final production lodging journey and cleanup evidence; accepted before the batch continuation |
| P3 Online Teaching | PASS | Production Online Teaching journey and final batch verification |
| Real-user simulation | **100/100 PASS** | Runs 003–050: `sigroom-migrate-jbcgh`; runs 051–100: `sigroom-migrate-bqqsw`; runs 001–002 belong to the P2 production E2E sequence rather than `RUN_001` / `RUN_002` Cloud Logging markers |
| QA privilege cleanup | PASS | Temporary permission/group count returned to zero; QA identities disabled; staff/superuser flags remained zero |
| Synthetic active-data cleanup | PASS | No active synthetic lodging rows from the final batch; no active Online Teaching QA holds after final batch |
| Migration job restoration | PASS | `sigroom-migrate` restored to baseline generation 71 and normal migration command; restore execution `sigroom-migrate-ng545` succeeded |
| Production identity after verification | PASS | Service remained on exact accepted SHA/revision; no additional production deploy |

## 100-run campaign evidence

### Runs 001–002

Runs 001–002 were completed as part of the final P2 Production Lodging E2E sequence before the large batch continuation. They are **not** represented by literal `RUN_001` or `RUN_002` messages in Cloud Logging. A read-only Cloud Logging query on 28 September 2026 returned no such markers.

Therefore this closeout does not fabricate batch-log identities for runs 001–002. Their provenance is the accepted P2 production E2E evidence, while the batch executions below provide explicit machine-log identities for runs 003–100.

The older historical ledger `docs/qa/2026-09-27-production-100-run-ledger.md` and earlier handoff documents recorded an interim **1/100** state before the final campaign was completed. Those files are preserved unchanged as historical evidence and must not be treated as the final acceptance status.

### Runs 003–050 — Lodging

Authoritative execution: `sigroom-migrate-jbcgh`

- Execution condition: `Completed=True`
- Task result: succeeded, exit 0
- Explicit log result: `LODGING_BATCH=PASS`
- Explicit log count: `LODGING_RUNS_PASS=48`
- Final occupancy check: `FINAL_OCCUPIED=4`
- Final free-bed check: `FINAL_FREE=12`
- Cleanup checks:
  - `QA_ROLE_AFTER=0`
  - `QA_ACTIVE_AFTER=0`
  - `QA_STAFF=0`
  - `QA_SUPER=0`
  - `ACTIVE_NEW_AFTER=0`

The execution emitted successful run markers through `RUN_050=PASS` and exited normally.

### Runs 051–100 — Online Teaching

Authoritative execution: `sigroom-migrate-bqqsw`

- Execution condition: `Completed=True`
- Task result: succeeded, exit 0
- Duration observed for the accepted execution: approximately 1m56.1s
- Explicit run markers: `RUN_051=PASS` through `RUN_100=PASS`
- Explicit log result: `ONLINE_BATCH=PASS`
- Explicit log count: `ONLINE_RUNS_PASS=50`
- Campaign terminal marker: `TOTAL_100_RUN=PASS`
- Pre-batch stale holding cleanup: `PREBATCH_ONLINE_HOLDINGS_CLEANED=0`
- Cleanup checks:
  - `QA_GROUP_AFTER=0`
  - `QA_ACTIVE_AFTER=0`
  - `QA_STAFF=0`
  - `QA_SUPER=0`
  - `QA_ACTIVE_HOLDS_AFTER=0`

The execution exited normally.

## Synthetic QA cleanup disposition

### Production-side cleanup — complete

The final accepted executions demonstrate that temporary privileges and active synthetic state were removed:

- QA accounts remained non-staff and non-superuser throughout the accepted checks.
- Temporary permission/group memberships were removed after use.
- QA credentials were disabled by setting unusable passwords and deactivating the final batch identities.
- Final Lodging batch left `ACTIVE_NEW_AFTER=0` for the generated lodging rows.
- Final Online Teaching batch left `QA_ACTIVE_HOLDS_AFTER=0`.
- The migration job was restored after verification, so the QA harness is not left as the default job command.

No additional production deletion is required for Final Acceptance. Historical released/cancelled records and audit traces should be retained unless a separate data-retention decision explicitly authorizes deletion. Removing audit evidence is **not** part of this closeout.

### Local-only QA screenshots — intentionally untouched

The detached deployment evidence worktree `F:\ogn_ROOM\.worktrees\deploy-edbe58f-20260928` still contains two untracked local files:

- `.qa-edge-probe.png`
- `.qa-screen.png`

They are not tracked by Git, are not part of production SHA `edbe58f...`, and were not deployed. They do not affect production behavior. They are left untouched as local evidence; deleting them is optional housekeeping and would require a separate explicit deletion decision.

## Migration job restoration

After the acceptance executions, `sigroom-migrate` was returned to its baseline operational configuration:

- Generation: `71`
- Normal command: `python manage.py migrate --noinput`
- Restore execution: `sigroom-migrate-ng545`
- Restore result: `Completed=True`, exit 0
- Migration output: `No migrations to apply.`

This restoration is part of the accepted terminal state.

## Cloud Logging interpretation note

Earlier exploratory / superseded job executions may remain visible in Cloud Logging, including failed attempts used while developing the verification harness. They are not the authoritative Final Acceptance executions. For the closeout decision, use:

- Lodging batch: `sigroom-migrate-jbcgh`
- Online Teaching final batch: `sigroom-migrate-bqqsw`
- Migration-job restore: `sigroom-migrate-ng545`
- Production service revision: `sigroom-00067-cpc`
- Production SHA: `edbe58fc7a2b3513c4ae76f9c81c1175f94a34be`

## Final closeout state

**Status: CLOSED / PASS**

- P2 Production Lodging E2E: PASS
- P3 Online Teaching: PASS
- 100-run Real-User Simulation: **100/100 PASS**
- Synthetic active QA state: CLEAN
- Temporary access: REVOKED
- QA credentials: DISABLED
- Migration job: RESTORED
- Production revision: UNCHANGED AFTER ACCEPTANCE
- Additional deploy during closeout: NONE
- Production behavior change during closeout: NONE

Any future feature change, production deployment, destructive QA-data deletion, or new production verification campaign requires a new explicit authorization and a new evidence record.
