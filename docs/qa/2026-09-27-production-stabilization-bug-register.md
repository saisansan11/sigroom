# Production stabilization bug register — 27 Sep 2026

Baseline SHA: `9145a79ba7abbdac045c343cf6b3a283835e16e1`.
Production revision: `sigroom-00066-88b`, 100% traffic (read from Cloud Run service).
Migration execution: `sigroom-migrate-qskfn`, completed successfully (read from Cloud Run job execution).

## Observed findings

| ID | Priority | Evidence | Action | Status |
|---|---|---|---|---|
| STAB-01 | P2 | Cloud Run revision logs contain one 404 for `/favicon.ico` in the last 24 hours; the shared page head declares only `apple-touch-icon`. Local browser still requests the root icon URL when viewing an image directly. | Declare the existing `pwa-icon-192.png` as the browser icon and redirect `/favicon.ico` to that static file. | Fixed in branch; production pending separate approval. |

P0: no defect observed in the sampled requests or guest browser paths. P1: no defect observed in the tested guest paths; authenticated production role acceptance is still open. P2: STAB-01 is the only confirmed defect in this audit.

## Browser acceptance performed

- Guest service gateway at 320, 360, 390, 430, 768, 1024, and 1440 px: checked rendered page/3D section and page-level horizontal overflow; no overflow observed.
- At 320 px: booking CTA reached `/lodging/`; online teaching CTA reached Login with `next=/online/`; three staff entries reached Login with their respective `next` paths; `/online/STU-ONLINE-1/` also reached Login.
- At 320 px: switched 3D to floor 5, selected room 501 and read the room panel, enabled the fan filter, and opened the text-plan fallback. 3D view controls and room picker measured 44 px high. The page showed a mobile horizontal-gesture hint. No JavaScript console errors were captured in the tested production tab.
- Classroom/meeting appears as a disabled, "under development" service in the gateway. No booking submission was performed.
- Local browser after the fix: shared head pointed to `/static/img/pwa-icon-192.png`; direct icon URL rendered; `/favicon.ico` redirected to it (local server returned 302).

## Code gates performed

- Targeted `config/tests_v7_d.py` and `bookings/tests_lodging_service_gateway.py`: 19 passed.
- Full pytest after the final route change: 641 passed. Django check after the final change reported no issues; migration drift check reported no changes; `git diff --check` passed. CI belongs to the PR gate.

## Verification limits

- A 24-hour Cloud Run revision log sample contains 232 HTTP requests: 118 2xx, 113 3xx, one 4xx, zero 5xx. Sample latency p50 2.6 ms, p95 32.1 ms, maximum 2.35 s. These figures describe the logged sample, not a load test or client-side timing.
- Non-request revision logs show the initial deployment rollout and worker boot, with no later restart entry in the 24-hour sample. This is a log observation, not a restart metric.
- Guest requests to the three staff entries and online teaching routes redirected to Login with their intended `next` path. Post-login role routing remains unverified without role-specific access.
- No end-to-end production booking was created. P1 acceptance remains open for authenticated role routing and safe booking-flow execution.
