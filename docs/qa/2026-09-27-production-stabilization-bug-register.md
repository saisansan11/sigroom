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

## Authenticated QA follow-up — 27 Sep 2026

- After explicit approval, a one-time execution of the existing Production image created the separate, non-staff account `qa_p1_20260927` with a random server-side password. Execution `sigroom-migrate-d5gfj` succeeded and logged `QA_ACCOUNT_RESULT=CREATED`. The existing user tied to the primary QA mailbox was not changed.
- A password-reset request for the QA alias reached the generic completion page. Cloud Run request logs show the reset confirmation flow reached its completion page, and the QA account has an active, usable password. The password was never shown to the agent. A later read-only inspection execution failed because its optional audit query used the wrong field name; it had no database write.
- A screenshot of a failed login showed the existing username `wasan.t` on the Admin login page. The QA username is `qa_p1_20260927` and the ordinary login page is `/accounts/login/`. The user was asked to enter the QA password there. This does not establish a product defect or a successful authenticated test.
- Production remained at revision `sigroom-00066-88b`, 100% traffic, exact image SHA `9145a79ba7abbdac045c343cf6b3a283835e16e1`. The migration job retained generation 61 and its original `manage.py migrate --noinput` configuration after the temporary executions.
- The user subsequently signed into the ordinary login page as `qa_p1_20260927`; the browser showed the authenticated home page greeting `QA SIGROOM P1`. Authenticated navigation to `/lodging/staff/lodging/`, `/lodging/staff/online/`, `/lodging/staff/learning/`, and `/online/` showed the expected access-denied pages for the no-role account.
- The authenticated booking CTA opened `/book/` at step 1 of 5. Lodging CTA opened `/lodging/`, showing one open course with 12 of 16 beds available; its course page showed occupied beds without personal identities. In Edge, selecting DORM-104 bed 4 opened the registration dialog, and Cancel closed it. No form was submitted.
- No staff permission was granted and no Production booking was created. Positive staff role routing and P2–P4 remain pending.

## Staff entry follow-up — 27 Sep 2026

- The user entered an existing privileged account in the Edge browser without sharing credentials with the agent. The login-first `/lodging/staff/lodging/` route redirected to `/lodging/workspace/`, which rendered the lodging operations board with one open cohort, four assigned occupants, and twelve free beds.
- With the same authenticated session, `/lodging/staff/online/` and `/lodging/staff/learning/` each redirected to `/usage/`, which rendered the room usage workspace. The current list was empty; no record was edited.
- The QA account's three staff routes were previously denied. This verifies anonymous-to-login, no-role rejection, and privileged routing in the production browser. Positive routing for a non-superuser custodian/approver remains untested; the QA account has not been granted any staff permissions.

## Non-superuser role acceptance — 27 Sep 2026

The user explicitly approved temporary QA roles. Roles were granted one at a time to the non-superuser, non-staff account `qa_p1_20260927`, tested in the Production Edge InPrivate session, and revoked before the next role was granted. No booking, usage record, room data, or course data was created or edited.

- **Lodging approver:** a temporary secondary `ResourceApprover` row was created for `DORM-101`. `/lodging/staff/lodging/` reached `/lodging/workspace/` and rendered the lodging operations workspace. The role was then removed; Cloud Run job output logged `TEMP_ROLE_LODGING_REVOKED=1` and `TEMP_ROLE_LODGING_REMAIN=0`. A fresh browser navigation then showed the access-denied page stating that the account has no lodging-management permission.
- **Online-room custodian:** `qa_p1_20260927` was temporarily added as custodian of `STU-ONLINE-1`. `/lodging/staff/online/` redirected to `/usage/` and rendered the room-usage workspace. The role was then removed; job output logged `TEMP_ROLE_ONLINE_REVOKED=1` and `TEMP_ROLE_ONLINE_REMAIN=0`. A fresh navigation to the online staff route then showed the access-denied page stating that the account is not assigned to rooms in that section.
- **Learning/meeting-room custodian:** `qa_p1_20260927` was temporarily added as custodian of `MTG-1`. `/lodging/staff/learning/` redirected to `/usage/` and rendered the room-usage workspace. The role was then removed; job output logged `TEMP_ROLE_LEARNING_REVOKED=1` and `TEMP_ROLE_LEARNING_REMAIN=0`. A fresh navigation to the learning staff route then showed the same section-specific access denial.
- Before the online/learning grants, a read-only Production inspection confirmed the QA account was `is_superuser=False`, `is_staff=False`, had no lodging add/change permissions, no course-supervisor row, no lodging approver row, no active approver delegation, and `can_access_lodging_management=False` after the lodging role was revoked.
- The three positive-path checks therefore exercise the intended non-superuser approver/custodian branches rather than relying on the privileged-account result. All temporary role grants used for this acceptance were removed before the phase was closed.

**P1 authenticated role-routing acceptance: PASS.** P2 lodging E2E is the next phase. Production deployment and PR merge remain outside this acceptance and still require separate approval.

## P2 Lodging production acceptance — post-check-in release gap

### SIG-P2-001 — Severity P2 — No supported release/checkout path after lodging check-in

**Status:** OPEN in Production — reproduced on baseline `9145a79ba7abbdac045c343cf6b3a283835e16e1`. Staff checkout is implemented and verified locally on `codex/p2-lodging-checkout`; no deploy or merge performed.

**Reproduction (QA-only data):**
1. Public self-booking created `QA100-20260927-P2-CHECKIN-001` in cohort `nr-70`, room `DORM-104`, bed 4.
2. Non-superuser/non-staff QA account `qa_p1_20260927` received only temporary `bookings.change_courselodgingcohort` permission.
3. Production staff workspace contained the QA record (browser find result 1/1), and the authorized check-in page displayed the full QA identity.
4. Staff confirmed check-in through the Production UI. The page then displayed `รายงานตัวเรียบร้อยแล้ว` with the QA account as confirmer; DB audit contains `student_checked_in`.
5. After check-in, the workspace no longer renders cancel/no-show controls for that occupant. `release_lodging_reservation()` explicitly rejects any row whose `checked_in_at` is non-null. There is no checkout/release transition elsewhere in the current lodging flow.

**Expected:** An explicitly supported operational transition should exist for releasing/closing a checked-in QA/occupancy record when the acceptance lifecycle requires the bed to be returned, with authorization and immutable audit history.

**Actual:** A checked-in allocation cannot be released through the product path. Production acceptance cleanup required a QA-only audited `qa_cleanup_checkin_reset` followed by the normal staff cancellation service. This cleanup is evidence handling, not a user-facing PASS for the missing transition.

**Safety/cleanup:** The QA allocation was removed, `CourseLodgingRelease` has exactly one `cancelled`/`staff` record, private capability was deleted, FREE/OCCUPIED returned to 12/4, and all temporary permission/approver/delegation counts for the QA account returned to zero. Both the stale private management capability and the public pass return 404 after release.

**Acceptance impact:** P2 Lodging E2E is **NOT PASS** under the stated `check-in → release/cancel` criterion until this product-path gap is resolved or the acceptance criterion is formally changed.

**Local fix verification (28 Sep 2026):** Added a staff-only `checked_out` transition for checked-in occupants with a required reason. The release record retains check-in time and confirmer, records a distinct checkout audit action, removes active access, and returns the bed. Targeted tests and the full suite passed (645 tests). A temporary test-server browser run passed at 1280×844 and 390×844: the checkout form rendered, submission returned a success message, occupancy fell from 1 to 0, available beds rose from 1 to 2, and neither viewport overflowed. This verifies the branch locally; Production acceptance and the 100-run campaign remain open.
