# UX-2 Express Booking Handoff — 2026-09-15

## 1. Verified repository state
- Integration base: `feat/lodging-v5-2`
- Base SHA at UX-2 start: `f136858603168d27f54c407b8bb52148eb9467b9`
- Feature branch: `feat/ux-2-express-booking`
- UX-1 is already merged into the integration base.
- `.claude/handoffs/` and `.tmp/` remain unrelated/untracked and were not staged, modified, cleaned, or deleted.
- No production deployment was performed.

## 2. UX-2 final behavior
The existing five-step booking contract remains unchanged:

`เวลา → ห้อง → รายละเอียด → ตรวจสอบ → ยืนยัน`

UX-2 only reduces cognitive load inside Step 3–4:
- selected room/date/time are shown as a compact summary at the top of Step 3;
- activity title/type/attendees remain the first required inputs;
- responsible/owner fields remain real editable form controls but are progressively disclosed;
- when the user profile is complete, the responsible section is closed by default and the summary says `ระบบเติมให้แล้ว`;
- when profile data is incomplete, or validation errors exist in the responsible fields, the section opens automatically and the summary says `กรุณาตรวจข้อมูล`;
- equipment, room setup, external attendees, notes, visibility, and series booking remain in the existing additional-options disclosure;
- the Step 4 review panel remains visible earlier in the page and synchronizes with edits to title, attendee count, responsible name, and unit;
- desktop uses a sticky review column; mobile/tablet widths fall back to normal document flow;
- the legacy UI-3 contract strings `สรุปการจอง` and `ตรวจสอบข้อมูลก่อนส่ง` remain in markup.

No booking validation rule, approval rule, conflict rule, permission, privacy boundary, or data model was changed.

## 3. Responsible/owner interaction QA
Local-only browser QA used `http://127.0.0.1:7357` with the seeded local account `somchai`.

### Complete profile
Verified in a real Chromium session:
- responsible disclosure is closed by default;
- summary displays `ผู้รับผิดชอบ · ระบบเติมให้แล้ว`;
- summary displays the prefilled name and phone;
- mouse click opens/closes the native details disclosure;
- the explicit Enter-key bridge toggles the focused summary while keeping focus on it;
- editing responsible name/phone updates the responsible summary immediately;
- Step 4 review synchronizes with the edited responsible data.

### Incomplete profile
For local QA only, `somchai.phone` was temporarily cleared and then restored to `0812345678` immediately after the test.

Verified:
- responsible disclosure opens automatically;
- summary changes to `ผู้รับผิดชอบ · กรุณาตรวจข้อมูล`;
- missing phone is shown as `ยังไม่มีเบอร์โทร`;
- the complete-profile message is not shown when data is incomplete.

### Validation error
With the same temporary local-only incomplete profile, a POST was exercised with a valid activity title and missing required responsible phone.

Verified:
- responsible disclosure remains/opened automatically;
- inline error `ฟิลด์นี้จำเป็น` is visible;
- previously entered activity title is preserved;
- responsible values are preserved;
- additional-options disclosure remains open when bound form data requires it;
- no user-entered form data was lost.

The seeded phone was restored after this check.

## 4. Main booking / draft / series QA
### Normal submit
A local-only booking was submitted through Step 3 and reached Step 5 successfully:
- title: `UX2 Browser QA submit`
- local booking id: `8642418e-1585-425a-bdcf-e55417710cff`
- result: existing auto-approval policy applied normally;
- room/date/time/responsible/attendee values rendered correctly on Step 5.

### Draft
A local-only draft was saved successfully:
- title: `UX2 Browser QA draft`
- local booking id: `372baf8c-e23c-43ef-934e-b15f107bee0b`
- result: Step 5 showed status `ร่าง` and no approval history had started.

### Series booking
Verified in the browser:
- `is_series` off: normal draft/submit actions are visible and series preview is hidden;
- `is_series` on: series fields appear, normal single-booking submit actions are hidden, series-preview action is shown;
- toggling `is_series` off restores the original single-booking action state.

All of the above used the local/dev database only. No production data was touched.

## 5. Responsive/browser quality
The preceding UX-2 browser QA on this same working tree covered widths:
- `360`
- `390`
- `430`
- `768`
- `1280`
- `1440`

It recorded no horizontal overflow, normal/static mobile review flow, sticky desktop review, approximately `2271px` page height at 360px, and approximately `1488px` at 1280px.

The final continuation rechecked the current code after the touch-target/shadow-token corrections:
- approximately 768px (`767px` reported because native Chrome sizing rounds by one pixel): no horizontal overflow; review `position: static`;
- `1280px`: no horizontal overflow; review `position: sticky`; page height about `1488px`;
- approximately 1440px (`1439px` reported because native Chrome sizing rounds by one pixel): no horizontal overflow; review `position: sticky`;
- `ตัวเลือกเพิ่มเติม` summary height measured about `43.99px`, i.e. the CSS 44px touch-target floor.

The managed native Chrome window enforces roughly a 500 CSS-pixel minimum, so 360/390/430 could not be re-forced in this final continuation without unsupported device emulation. Those three widths were already exercised immediately before this continuation, and no grid/breakpoint behavior was subsequently changed.

The connector did not expose a retained browser console/network stream during the final continuation. No runtime JavaScript failures, broken controls, navigation failures, or visible layout shifts were observed in the exercised interactions.

## 6. Automated verification
### UX-2 + UI-3 + booking regression
Command:
`uv run pytest bookings/tests_ux2.py bookings/tests_ui3.py bookings/tests_m2.py bookings/tests_m4.py bookings/tests_m5.py bookings/tests_m6b.py bookings/tests_trial_round1.py -q`

Result:
- **50 passed, 2 warnings**

### Full regression
Command:
`uv run pytest --tb=short -q`

Result:
- **220 passed, 2 warnings**

### Framework/schema/diff gates
- `uv run manage.py check` → **System check identified no issues (0 silenced)**
- `uv run manage.py makemigrations --check --dry-run` → **No changes detected**
- `git diff --check` → **PASS / clean**
- CSS variable scan → **no undefined `var(--...)` references detected**

The two pytest warnings are existing project/environment warnings and are not UX-2 failures.

## 7. Scoped files
UX-2 scoped files are:
- `bookings/forms.py`
- `bookings/tests_ux2.py`
- `static/css/app.css`
- `templates/bookings/book_form.html`
- `templates/bookings/partials/booking_fields.html`
- `docs/plans/2026-09-14-ux-2-express-booking.md`
- `docs/handoffs/2026-09-15-ux-2-express-booking.md`

Unrelated untracked paths that must remain untouched:
- `.claude/handoffs/`
- `.tmp/`

## 8. Invariants confirmed unchanged
- No model/schema changes.
- No migrations added or modified.
- No destructive migration.
- No booking conflict/business-rule changes.
- No approval/SLA/delegation logic changes.
- No server-side authorization change.
- No privacy-model change.
- No production deployment.
- No legacy UI-3 tests were weakened.

## 9. PR / merge policy
After staging only the scoped files, commit and push `feat/ux-2-express-booking`, then open the PR with:
- base: `feat/lodging-v5-2`
- head: `feat/ux-2-express-booking`

Before reporting readiness, verify the complete PR diff, exact head SHA, base/head branches, mergeability, and remote status checks/CI.

**Do not merge UX-2 automatically.** The authorized auto-merge scope covered UI-3/UI-4/UI-5 only. UX-2 must stop at **READY FOR MERGE** pending explicit user approval.
