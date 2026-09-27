# SIGROOM Production 100-Run Real-User Simulation Ledger

Date: 2026-09-27
Production baseline: `9145a79ba7abbdac045c343cf6b3a283835e16e1`
Cloud Run target: `sigroom` / `sixth-storm-439008-u2` / `asia-southeast3`
Safety prefix: `QA100-20260927-...`
Target: at least 100 completed journeys, approximately 50 Lodging + 50 Online Teaching.

Rules: QA/test records only; never modify real-user bookings; conflicts only between QA records; cleanup after each scenario/batch; do not expose capability tokens; no merge/deploy without separate approval.

| Run | System | Persona | Viewport | Scenario | Expected | Actual | Result | Object ID(s) | Cleanup | Latency/error | Bug |
|---:|---|---|---|---|---|---|---|---|---|---|---|
| 001 | lodging | public student + authorized non-superuser staff | Chrome desktop + Edge InPrivate desktop | Public booking DORM-104/4 → digital pass/private management separation → staff workspace visibility → authorized check-in → post-check-in release/cleanup → stale private/public endpoint verification | Booking and check-in succeed; supported release returns bed; stale capabilities cannot duplicate state | Booking/pass/workspace/check-in succeeded. Product has no supported release/checkout after `checked_in_at`; QA-only audited reset was required before normal staff release. Stale private management and public pass both returned 404 after release. | FAIL | `ad2dbf64-123f-4575-9fd8-7b0d6d27935a` | COMPLETE — active=0, release=1 (`cancelled`/`staff`), capability=0, FREE/OCCUPIED=12/4, temp roles=0 | No 5xx observed in browser journey; one rejected malformed Cloud Run inspection/probe command did not mutate product state | SIG-P2-001 |

## Batch summaries

### Runs 001–001

- Completed: 1
- Passed: 0
- Failed: 1
- Defects found: 1 (`SIG-P2-001`, Severity P2)
- Cleanup completeness: PASS for QA data and temporary roles
- Active QA bookings after batch: 0
- Cohort `nr-70`: FREE 12 / OCCUPIED 4 (baseline restored)

## Running totals

- Completed journeys: 1 / 100
- Lodging: 1 / ~50
- Online Teaching: 0 / ~50
- PASS: 0
- FAIL: 1
- P0: 0
- P1: 0
- P2: 1
- P3: 0

Do not mark 100-run acceptance complete until the ledger reaches at least 100 completed journeys and final orphan/temp-role/active-QA/5xx/audit checks are performed.
