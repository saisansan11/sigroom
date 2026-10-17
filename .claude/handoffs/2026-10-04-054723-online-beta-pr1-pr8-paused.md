# Handoff: SIGROOM online beta PR-1 ถึง PR-8 — หยุดตามคำสั่งผู้ใช้

## Session Metadata

- บันทึก: 4 ต.ค. 2569 เวลา 05:50 น. Asia/Bangkok โดยประมาณ
- Repo: saisansan11/sigroom; workspace หลัก F:/ogn_ROOM
- ผู้ใช้สั่งหยุดพัฒนาเพื่อส่งต่อเอเจนต์อื่นในช่วงใกล้ usage limit
- สถานะนี้ตรวจจาก Git/GitHub/Cloud จริงตอนหยุด; ห้ามใช้แทนการตรวจสถานะสดตอนเริ่มใหม่
- ไม่มี commit/push/merge/deploy ใหม่ระหว่างจัดทำ handoff นี้

## Current State Summary

เสร็จและขึ้น production แล้วเฉพาะ PR-1 #87 และ PR-2 #88. PR-3 เป็นงานที่ยังไม่ commit ใน worktree online-beta: full pytest รอบสุดท้ายผ่าน 1032 ข้อและ Browser QA ผ่าน แต่ยังไม่มี PR/CI/release. PR-4 ทำโค้ดแล้วแต่ยังต้องซ่อม database default ก่อนรวม stack. PR-5 ทำโค้ดส่วนใหญ่แล้วแต่ยังไม่มี migration/tests/คู่มือตั้ง push. PR-6 ทำแล้วและ parent ทดสอบเต็ม 896 ข้อผ่านบนฐาน PR-1 แต่ยังไม่ได้รวม stack/Browser QA/PR. PR-7 มีโค้ดและ migration ร่างแล้วแต่ยังไม่ทดสอบ. PR-8 ยังไม่ได้เริ่ม.

Production ล่าสุดคือ sigroom-00079-ksb รับ traffic 100% และใช้โค้ด merge PR #88. ไม่มี PR-3 ถึง PR-8 บน GitHub ณ เวลาหยุด. PR #82 ที่ยังเปิดเป็นงานคนละ scope ห้ามแตะ.

## Important Context

คำสั่งผู้ใช้ล่าสุดก่อนหยุดอนุญาตให้ทำครบ 8 PR, merge เมื่อปลอดภัย, deploy และทำเฟสถัดไปโดยไม่ถามสิทธิ์ซ้ำ. อนุญาตนี้แทนข้อห้าม merge/deploy/gcloud ในข้อความและ runbook เดิม แต่ไม่แทนข้อกำหนดรักษาความปลอดภัย, tests เดิม, ข้อมูลจริง, review และ CI. คำสั่งปัจจุบันคือหยุดแล้วทำ handoff; ห้ามทำ release ต่อใน turn นี้. เอเจนต์ใหม่ให้เริ่มเมื่อผู้ใช้สั่งทำต่อ.

อ่านให้ครบก่อนแก้:
- .agents/skills/sigroom-development-workflow/SKILL.md และ profile/checklist ที่เกี่ยวข้อง
- CLAUDE.md จาก worktree ที่ทำงานจริง
- docs/plans/2026-10-03-online-beta-runbook.md
- สำหรับ PR-6: docs/plans/2026-10-03-pr-d-google-login.md

Workflow ที่ใช้ใน session: sigroom-development-workflow + chatgpt-antigravity-flow. Runbook มอบหมาย Codex จึงใช้ Codex worker ได้ตามข้อยกเว้น agy; parent ตรวจอย่างอิสระและใช้ lnwjud MCP shell สำหรับ deterministic checks. รอบใหม่ต้องอ่าน skill นี้ตาม environment จริงก่อนเลือกวิธีทำงาน.

ห้าม force push, ลบ/skip tests เดิม, weaken permission/ExclusionConstraint, reset งานผู้อื่น, deploy tree สกปรก หรือ merge ถ้า gate ไม่ผ่าน. Schema ใช้ makemigrations และ expand migration. เปลี่ยน test เดิมได้เฉพาะพิสูจน์ว่า assertion ล้าสมัยและคง semantic coverage พร้อมอธิบายใน PR. user authorization supersedes old repo approval restrictions; ถ้า tool approval policy เป็น never ห้ามส่ง sandbox_permissions.

## Architecture Overview

ระบบ Django/PostgreSQL ใช้ uv และ Python 3.12, HTMX, template/CSS/JS เดิม; เพิ่ม pywebpush และ django-allauth ได้ตาม runbook ที่อนุมัติ. Booking business logic อยู่ services/models. การจองเตียงนักเรียนคือ CourseStudentLodging + cohort; คำขอข้าราชการทหารคือ Booking + PublicLodgingAccess, ไม่มี GeneralLodgingRequest. ใช้ข้อมูลจริงของ model เดิมและห้ามนับ cohort room holds เป็นจำนวนผู้พักอีกชุดหนึ่ง.

## Critical Files

| ตำแหน่งใน workspace หลัก | ใช้ทำอะไร |
|---|---|
| .agents/skills/sigroom-development-workflow/SKILL.md | workflow/gates |
| .worktrees/online-beta/CLAUDE.md | stack และข้อกำหนดปัจจุบัน |
| .worktrees/online-beta/docs/plans/2026-10-03-online-beta-runbook.md | ลำดับและเกณฑ์ PR ทั้ง 8 |
| .worktrees/online-beta/docs/handoffs/2026-10-04-online-beta-pr2.md | ผลตรวจ/เหตุผลอัปเดต tests PR2 |
| .worktrees/online-beta/docs/plans/pr3-booking-cassette-implementation.md | แผน PR3 |
| .worktrees/online-beta-pr4/docs/ops/run-jobs-cloud.md | วิธีตั้ง Cloud Job/Scheduler |
| .worktrees/online-beta-pr6/docs/google-login-setup.md | Google client/roster/ทดสอบ |
| .worktrees/online-beta-pr6/docs/handoffs/2026-10-04-online-beta-pr6-implementation.md | PR6 implementation และ tests เดิมที่ปรับ |
| .worktrees/online-beta-pr7/docs/plans/2026-10-04-lodging-dashboard-implementation.md | PR7 draft |
| .worktrees/online-beta/scripts/deploy-sigroom-production.ps1 | guard deploy production |

## Environment State

### Worktrees ที่ต้องรักษา

ทุกงาน PR3-7 ด้านล่างยังเป็น UNCOMMITTED WIP. ห้าม git clean/reset, ลบ worktree หรือ stage .tmp.

| Worktree ใต้ F:/ogn_ROOM/.worktrees | Branch | HEAD/base ณ หยุด | สถานะ |
|---|---|---|---|
| online-beta | feat/booking-cassette-pass | 372e4059b7c2b7c220d7ec57f1d9a34c68ffdeb0 | PR3 WIP; รวม merge PR2 แล้ว |
| online-beta-release | detached | 372e4059b7c2b7c220d7ec57f1d9a34c68ffdeb0 | clean, deploy PR2 เสร็จ |
| online-beta-pr2-fix | feat/service-shell | 3cfe87879e054a8046486442f8e36df1db11b481 | commit PR2 แก้ stale a11y; clean |
| online-beta-pr4 | task/online-beta-pr4 | 3f2d7ac9c767b9dd50cd6f1fc4386274d0f6f7bc | reminder WIP |
| online-beta-pr5 | task/online-beta-pr5 | 3f2d7ac9c767b9dd50cd6f1fc4386274d0f6f7bc | push WIP |
| online-beta-pr6 | task/online-beta-pr6 | 3f2d7ac9c767b9dd50cd6f1fc4386274d0f6f7bc | Google WIP ผ่าน full บนฐาน PR1 |
| online-beta-pr7 | task/online-beta-pr7 | 9d57b9ceb63aeb16d144a764b6ed5ec9150e3ec7 | dashboard WIP บน merge PR1 |

Root F:/ogn_ROOM อยู่ feat/lodging-v5-2 ที่ 9145a79ba7abbdac045c343cf6b3a283835e16e1 ซึ่งล้าหลัง remote. ไม่มี tracked change. มี untracked เดิม .claude/handoffs/, .tmp/, .worktrees/, แผน UX เก่า, repaired_tor_docs_20260923/ และโฟลเดอร์ข้อมูลห้องพักภาษาไทย. อย่ารวมเข้า commit. branch ตั้งต้น claude/online-classroom-planning-fc892e ยังมี worktree .claude/worktrees/online-classroom-planning-fc892e; ไม่ต้องเริ่มงาน PR1 ใหม่.

### Processes / local QA

- หยุด worker implement_pr2, implement_pr4, finish_pr6 แล้ว; ให้สรุปข้อความอย่างเดียว และทั้งหมดจบ checkpoint แล้ว.
- Local Django server port 8019 (exec session 34367) ถูกหยุดด้วย Ctrl+C ตอนทำ handoff. เปิดใหม่เมื่อต้อง Browser QA.
- Full test PR3 task 59fb959f-5c70-4350-a0f7-5ecad8a1fd38 จบ exit 0 แล้ว. ไม่มี test ที่ทราบว่ายัง running.
- .venv Python 3.12.10 ในแต่ละ worktree. PR5 uv sync สำเร็จ ติดตั้ง pywebpush 2.5.0 / py-vapid 1.9.4.
- helper .tmp/local_env.py โหลด root .env ใน process โดยไม่พิมพ์ค่า, ปฏิเสธ DB_HOST ที่ไม่ใช่ loopback, ใช้ DB แยก.
- DB local: sigroom_online_beta_qa, sigroom_online_beta_pr5_qa, sigroom_online_beta_pr6_qa, sigroom_online_beta_pr7_qa. pytest สร้าง test DB ตามชื่อเหล่านี้. อย่า run pytest สองชุดชน DB เดียวกัน.
- บัญชีสมมติ beta-qa-teacher / beta-qa-staff เป็นข้อมูล local QA เท่านั้น. ดู helper/seed เดิมหรือสร้าง credential สมมติใหม่ใน local; handoff ไม่บันทึก password.
- UI QA ผ่าน Codex in-app browser ID2 tab4; ถ้ามีใน sessionใหม่ใช้ bindingเดิมและอ่าน cua.rewriteDocumentation() ก่อน. UI interactions ให้ใช้ CUA เท่านั้น; ไม่สร้าง Playwright shell ใหม่แทน.
- Browser cache localhost เคยค้าง app.css; เปลี่ยน origin จาก 8018 เป็น 8019 จึงเห็น CSS ใหม่. Hard reload ที่ลองไม่แก้ cache. production ใช้ hashed static ตาม pipeline.

## Work Completed

### PR-1 — #87 เสร็จ/merge/deploy

URL: https://github.com/saisansan11/sigroom/pull/87
Branch: feat/online-quick-booking; base feat/lodging-v5-2.
Feature commit: 3f2d7ac9c767b9dd50cd6f1fc4386274d0f6f7bc.
Merge commit: 9d57b9ceb63aeb16d144a764b6ed5ec9150e3ec7.
Merged UTC 2026-10-03T21:40:54Z.

ทำหน้าจอง online แบบเลือกวัน/เวลา/ระยะเวลา/รุ่น แล้วกดจองห้องว่าง. รักษา permission และ database conflict guard. แก้ sync chips/calendar ให้ค่าตรงกันและไม่ใช้ JS ยาวเกินข้อกำหนด.

ผลตรวจ: full pytest 866 passed, 416 warnings, 140.35s; Node10; check/drift/diff ผ่าน. Browser teacher mobile390 และ desktop1280, actual quick booking, chips/calendar/month/preset/no-room states. screenshots docs/qa/online-beta/pr1. No-JS browserไม่ได้ทำ; ตรวจ source fallbackเท่านั้น. CIทั้ง6รวม PRSafetyGateผ่านก่อน merge.

Deploy CloudBuild 5fa3e59d-73d4-42ea-a6eb-0e1698a7ce5e SUCCESS2m33s; revision sigroom-00078-mth, traffic100%, smoke/home200. ก่อนหน้านั้น revision sigroom-00077-9xj เป็น rollback point.

### PR-2 — #88 เสร็จ/merge/deploy

URL: https://github.com/saisansan11/sigroom/pull/88
Branch: feat/service-shell; base feat/lodging-v5-2 หลัง PR1 merged.
Initial commit de3ff7e59ddf581408b4c162454c742c95047263.
Final head 3cfe87879e054a8046486442f8e36df1db11b481.
Merge commit 372e4059b7c2b7c220d7ec57f1d9a34c68ffdeb0.
Merged UTC 2026-10-03T22:27:11Z.

แยก classroom/meeting/online/lodging, service nav/my bookings/room statusไม่ปนกัน, gateway4ลิงก์ตรงและ lodgingเลือกนักเรียนหรือทหารที่หน้าstart, staff ops menuคงสิทธิ์เดิม. แก้ mobile ops dropdownที่ข้อความพันกัน.

ผลตรวจ parent full978 passed,444warnings132.13s. หลังCSSแก้มีfull exit0อีกครั้งแต่ outputของrunนั้นถูกtruncateจนสรุปcountไม่เห็น จึงไม่อ้างเวลาหรือcountรอบนั้นจากความจำ. Node10/check/drift/diffผ่าน. Worker targeted155. Browser teacher+staff390/1280 navigationทั้ง4, meetingกรองจริงและ timechangeคงcategory, lodgingpublicrequest/opsrights. screenshots12ภาพ docs/qa/online-beta/pr2.

CIครั้งแรก stale tests2กรณี (54/56 a11yผ่าน) เพราะเดิมคาดlodgingnestedlinks/3directcards. แก้เฉพาะtests/a11y/room-plan.spec.js+handoffโดยคง10viewport/48pxtouch/16pxtext/overflowassertions. เพิ่มตรวจ4cardsและ/start2ทาง. WorkerreviewPASS; parentactual10widthไม่มีoverflow. Final CI run37158228744 ทั้ง6PASS รวมa11y56และaggregate22:26:18Z. ไม่ได้mergeขณะCIfail.

Deploy CloudBuild 48f2b957-98f9-4457-84de-369078298fcf SUCCESS2m17s (createdUTC22:28:56), migrate/Firebase918files/home200. revision sigroom-00079-ksb traffic100%. Releaseworktreecleanตรวจหลังdeployแล้ว.

### PR-3 — บัตรตลับเทป ยังไม่ commit/PR

ทำ:
- services.booking_pass_context ตรวจ can_view_details ก่อนให้ข้อมูล, progressจากเวลาคาบclamp0..1, pendingชัดเจน.
- routes booking_pass และ booking_pass_qr_svg มีlogin/GET/no-store/noindex/no-referrer.
- QRเข้ารายละเอียดการจองจาก PUBLIC_BASE_URL เท่านั้น ไม่มีชื่อ/เบอร์/online linkในQR; originผิด/ว่างยังอ่านบัตรได้แต่QR503/แจ้งยังไม่พร้อม.
- onlineและgenericbookingsubmitไปpass; draftยังเก็บเดิม; detail/mybookingsมีลิงก์pass.
- shared templates/partials/cassette_pass.html ใช้กับbookingและlegacybedpass. SVG/flip/QR/reelsเดิมคงไว้, title/status/actionsเปลี่ยนตามcontext.
- online meeting URLใช้guardที่เข้มกว่าdetail; เอกสารข้อความรายละเอียดอ่านได้ไม่พึ่งJS; ICS/rebook/copy.
- หลังfullfirstpassแก้detailที่ can_decide ได้แต่ไม่มี can_view_details ให้ไม่แสดงปุ่มpass, ไม่ขยายสิทธิ์pass. Copyfallbackrelativepathแปลงเป็นfullbrowserURL (เฉพาะclipboard; QRยังcanonical).
- testsเดิมอัปเดตassertion redirect/sharedpartial extractionตามfeature, ไม่ลบหรือskip.

ผลล่าสุด:
- Worker full firstpass1029/486warnings210.36s task48b0abe1-4b84-4b36-9135-158538489bb0.
- หลังedgefix targeted52 passed46warnings7.71s, Node17 passed, uv sync --locked exit0.
- Full FINAL task59fb959f-5c70-4350-a0f7-5ecad8a1fd38 จบexit0: 1032 passed489warnings132.26s; parentอ่านผลจริงตอนหยุด (UTC22:47:16).
- check/migration drift/diff checkผ่านก่อน2edgefixท้าย; ต้องตรวจรอบล่าสุดก่อนcommit.
- parentอ่านsource/securitydiff/newtests/JS/sharedtemplateและ Browser QA แล้ว; parentยังไม่ได้runfullอิสระหลังfreeze (workerรันfullล่าสุด).

Browser QA: teacher390x844/1280x900 approvedonline+pendingmeeting+legacybed; Enter/Spaceflip, QRdialogopenclose, clipboardcanonicaldetail, actualICSdownload. document width=scroll390, consoleerror/warnว่าง. 7ภาพ docs/qa/online-beta/pr3 (online/pending/lodgingmobile+desktop, qrmobile). ไม่มีrealnoJS/reduced-motion browser run; source/Nodeเท่านั้น.

Scope tracked: bookings/lodging_views.py,online_teaching.py,role_home.py,services.py,views.py,urls.py; booking_detail/my_bookings/student_pass templates; cassetteCSS/JS; tests_phase_e_online_teaching,tests_r3_l_booking_flows,tests_service_shell,tests_task_first_a4_online,tests_ui5,tests_ux16 และ tests/cassette-interaction.test.cjs.
New: bookings/tests_booking_pass.py, templates/bookings/booking_pass.html, templates/bookings/partials/booking_result.html, templates/partials/cassette_pass.html, plan+7QAimages.
ห้ามรัน .tmp/pr3_extract.py ซ้ำ. ยังไม่มี PR3 handoff committed.

## Files Modified

PR4-7 มี WIP รายละเอียดต่อไปนี้; ให้ตรวจ git status/diff ของแต่ละ worktreeก่อนรวม. ห้าม copy trackedไฟล์ทั้งไฟล์จากฐานเก่าทับstackใหม่. ทำpatch/three-way mergeหรือเทียบblockเพื่อรักษาPR2/3/4/5.

### PR-4 — reminder implementation เสร็จ แต่มี repair ที่ยังไม่ได้ทำ

ทำkindบนNotification, conditionalunique booking/user/kindสำหรับkindไม่ว่าง, reminder2round, approvedonlineUPCOMINGเท่านั้น, locks/recheck/createatomic, emailon_commit failureไม่ล้มjob, run_jobsสรุปcounts, docs/ops/run-jobs-cloud.md.
Files: notifications/models.py,admin.py,new reminders.py/tests_reminders.py/migrations0002; approvals/services.py; bookings/management/commands/run_jobs.py; opsdoc.
Targeted53/check/drift/diffผ่านบนฐานPR1. ยังไม่มีfullบนstack/BrowserQA/CI.

CRITICAL: Notification.kind ปัจจุบันมี default="" แต่ยังไม่มี db_default="". Oldrevision INSERTที่ไม่ส่งkindจะพังNOTNULLหลังmigration. ต้องเพิ่มpersistentdb_default="", regenerateเฉพาะ0002ที่agentสร้างและยังUNTRACKEDผ่านmakemigrations (backupownfileก่อน), เพิ่มrawSQLlegacyINSERTtestomittingkind แล้วrerun. Rootยืนยันยังไม่แก้ตอนหยุด.
เมื่อรวมPR3ให้ลบtemporaryfixture _pass_route_dependency และimportNoReverseMatch ในtests_reminders; อย่าcommitfallbackที่ทำให้testrouteไม่มีจริง.

หน้าต่างremind30: startอยู่ใน(now+5,now+30] (เทียบdelta[-30,-5)); startreminder nowถึงnow+10. เงื่อนไขจองกระชั้น10นาทีให้เฉพาะstart: submitted_at/created_atต้อง<=start−30ก่อนส่ง30minround. ข้อสงสัยนี้อยู่doc.
ไม่retryemailอัตโนมัติหลังมีbellrow; แก้เวลาหลังส่งไม่ส่งkindเดิมซ้ำ.
DocsCloudพร้อม: private job sigroom-run-jobs, schedulerทุก5minAsia/Bangkok, task1retry0timeout240, copyactualwebrevisiondigest/env/secretrefs/CloudSQL/VPC/runtimeSA, jobscopedroles/run.invoker, OAuthtokenสำหรับGoogleRunAPI (ไม่ใช่OIDC), explicitprojectทุกgcloud. ยังไม่ได้ตั้งจริงบนCloud.

### PR-5 — push โค้ดส่วนใหญ่ ยังไม่ทดสอบ

ทำpywebpushdependency/uvlock/CLAUDE/env/settings/implementationplan, PushSubscriptionmodel, push.py validation/send, push_views.py status/subscribe/unsubscribe, URLs/sw.js, controls/CSS/JS/SW, ใส่ปุ่มonline+notifications.
EndpointHTTPSallowlist exactfcm.googleapis.com/updates.push.services.mozilla.com และApple/Windowsprovider suffix; rejectlocalhost/arbitraryhost/privateURL/userinfo/redirect/badkeys; lockuser+endpoint ownershipไม่ย้ายowner, cap10. ส่งtimeout5TTL600, 404/410ลบ, failureเพิ่มfailed_count, logsไม่เผยendpoint/key. SWเฉพาะpush+notificationclickไม่มีfetch/cache. URL/configปิด404เมื่อVAPIDไม่ครบ.
Parentอ่านpushservice/installedlibrarysignaturesบางส่วนแล้ว แต่ยังไม่ผ่านfullreview.

ยังขาด migration, pytest+Node tests, docs/ops/web-push-setup.md, เชื่อมPR4send_pushด้วยon_commitแยกemail, selfreviewและทุกgate.
Worktreeยังไม่มีNotificationskindจากPR4; ห้ามcopymodel/context_processorsทับ. helper settings_public_key()ควรยุบระหว่างreview. ต้องtestbrowserunsubscribeล้มหลังserverลบแล้วไม่แสดงopenedผิด.
ConfigconditionalURLimport: overrideVAPIDtestsต้องreloadURLmodules+clearcache.
UVsyncสำเร็จโดยparent; DBpr5/helperพร้อม. ยังไม่มีผลpytest.
VAPIDsubjectที่เลือกคือhttps://sigroom.web.app, ไม่สมมติอีเมล. ต้องตรวจpy_vapidkeyformatfrom_string/from_rawจากinstalledpackageก่อนสร้างkeysจริง. PR5migrationควรเป็นnotifications0003หลังPR4. Combinedlockต้องมีpywebpush+allauthทั้งคู่.

### PR-6 — Google/student auth ทำแล้ว fullผ่านบนฐานPR1

django-allauth65.19.7 (>=65<66) approved. ExplicitloginPOSTCSRF/callback/error3routesเท่านั้น, state/PKCE, signatureverifyIDtokenเสมอ, no signup/connect/passwordotherallauthroutes, noOAuth token storage. clientจากenvเท่านั้น, canonicalPUBLICcallbackไม่ใช้Hostheaders. schoolemail/verifiedboolTrue/hdexact; UID/emailbindingไม่ย้ายบัญชี, active/case-insensitiveemail, throttle+masked audit.
NewstudentautoaccountเฉพาะapprovedCourseStudentEnrollmentของcohortที่stateอ้างอิง: ไม่มีกลุ่ม/staff/superuser, unusablepassword,is_lodging_student. QR/domainอย่างเดียวไม่พิสูจน์รุ่น. ชื่อGoogle/ข้อมูลติดต่อจริงจากroster; ถ้าข้อมูลเดิมต้องมีแต่rosterไม่ครบ ให้กรอกเฉพาะที่ขาด ไม่สร้างข้อมูลปลอม.
Userflag+nullableCourseStudentLodging.user+unique/cohortuser+Enrollmentexpandschema. legacyuser-nulltokenpassเดิมยังpublic; newboundpassowner/courseoperatoronly, cancelrechecks.
Middleware+servicesdenyteacher/admin/approval/genericbookingแก่student. owncohortportal/bed only; militaryrequestpublicantispamเดิมคง.
ParentfixedUserflag default=False,db_default=False และregeneratedownuntrackedaccounts0004; allowpubliclodging_room_detailJSONที่redacted (publicaboutroominspector)โดยเพิ่มPII/rosterboundarytest. RawlegacyUserINSERTwithoutnewfieldtestยืนยันdbdefault.

ผลparentlatest896 passed444warnings188.84s task119a0039-2599-47ff-b117-530ccf4b4bb4 (exit0UTC22:39:26). Workerก่อนparentfix894/443warnings170.18s; Google28, regression127,lasttarget39,Node10/check/drift/diffผ่านก่อนparentfix. CountsในPR6handoffยังเป็น894 ต้องเติมผลparentตามจริง (และผลหลังintegrationต่อไป).

Scopetracked .env.example,CLAUDE; accounts/admin/middleware/models/views; bookings/admin/lodging_models/services/views/online_teaching/role_home/services; config/settings/urls; conftest; pyproject+uvlock; student_portal/login templates; oldtests10filesที่เพิ่มexplicitenrollmentfixtureไม่ใช่autouse.
New accounts/google_urls.py,google_views.py,social.py,tests_google_login.py,migrations0004; bookings/migrations0016Enrollment+bounduser; docsGoogle/handoff/plan; google_error template.
ยังไม่รวมPR2-5, BrowserQAหรือCI. Fixturesในtests_ui5และtask_first_a5โดนหลายPR ต้องmergeทั้งสองintent.
ต้องaugmentdocsGoogleให้คำสั่งSecretManager/CloudRunทีละบรรทัดครบ. Parentเพิ่งbrowseofficialGoogleCloudsecrets+OAuthdocsก่อนหยุด ยังไม่ได้แก้doc.
ยังไม่มีclientจริง: ปุ่มGoogleปิดบนprod. ต้องใช้schoolOAuthclient+realroster; อย่าสร้างจากข้อมูลเดา. BrowserloginON/OFF390+desktopและstudentownportalยังไม่ได้ทำ. RealGooglecallbackยังmockunitเท่านั้น.

### PR-7 — dashboard/billing implementation draft ยังไม่มีtests

21filesตามgitstatus: trackedbookings/admin.py,lodging_models.py,models.py,urls.py; resources/admin.py,models.py,management/commands/sync_lodging_room_registry.py; templates/base.html.
Newbilling/dashboard/dashboard_views; bookingmigrations0016+0017seed; resources0007+0008seed; implementationplan; dashboardCSS; dashboard/dashboard_room+2partialtemplates.

ทำResource.lodging_cooling default="",db_default=""เพื่อoldwriter; nullablelodging_rateบนBooking/CourseStudentLodging; LodgingRate daily/monthly/effective/persondefault/Adminroomoption; MeterReadingaironly/unitpriceblank/outnullable/negativeandin-outvalidation/auditevery save transaction+Admin.
OccupancyCourseStudentLodging+approvedBookingwithPublicLodgingAccess, allocation_statusไม่ใช่is_active, cohortholdไม่ซ้ำ. Decimaldaily×max1nights; wholeRoomelectricity; monthlycomparison>30เท่านั้น. Missing/conflictingratesแสดงข้อมูลขาดไม่เดา.
Dashboardday/floor/status, HTMX30secvisibleonly, colors+text+dots, drawer rate+meter, staffrights/PIIguard, CSVroomtotalsformulaescape, oldpageslinked.

Schema/data migrationสร้างด้วยmakemigrationsแล้ว; seedknownDORM/NNNcoolingonlyblankและ10RATESsnapshoteffective2026-10-03get_or_createไม่ทับoperatorchanges/reversenoop. ยังไม่migrate/verify.

ต้องเขียนทุกtests: nights/Decimal/rates/personvsroom/monthly/meter+auditAdmin/status/datecheckout/querybound/permission/PII/CSRF/CSV/racewrongUUID. ยังไม่แก้oldtests_ux1ที่คาดworkspaceเมนู; ต้องปรับและคงlinkoldpagecoverage.
จุดreview: เมตรย้อนหลังหลังcohortreleasedอาจถูกreject, supervisorPIIcrosscohort, recorded_byAdminreadonly, queryN+1และmobileHTMXdrawer. ยังไม่มีpytest/BrowserPASS.
PR7bookings0016ชนPR6bookings0016 ให้regenerateเลข/dependencyบนstackหลังPR6; ห้ามแก้migrationที่publishedแล้ว.

### PR-8 — ยังไม่ได้เริ่ม

ทำตามrunbook: CSS/JSใหม่ไม่เพิ่มlibrary, bodydata-ink=onเฉพาะgateway+onlineไม่staff; mouse-onlycanvasใต้contentpointer-eventsnone multiply, alpha<=.10 cap60 DPR<=1.5 drops6–10→28–40px1.2–1.8s, stopRAFidle/hidden. Click3–4themeCSScolors600–800ms clippedองค์ประกอบ, selectedstatic<=.18, navigationทันที, delegationรองรับHTMX, touchไม่มีtrail. Reducedmotionไม่มีcanvas/animationเหลือselectedstatic. NodeVMmeaningfultests+pytesttargets+CIcontrast4.5+actualscreens/clipถ้าทำได้.

## Decisions Made

- Permissionจากsessionล่าสุดอนุญาตmerge/deploy; gateไม่ลด.
- QRbookingใช้canonicaloriginconfigเท่านั้นเพื่อไม่สร้างลิงก์จากHostปลอม.
- นักเรียนต้องมีrosterยืนยันรุ่นเพื่อไม่ให้QRกลายเป็นสิทธิ์เข้าทุกรุ่น.
- Expandfieldsต้องpersistentDBdefaultเมื่อoldwriterยังINSERTได้ (PR4ยังค้าง, PR6/PR7ทำแล้ว).
- รายได้ค่าที่พักdefaultต่อคน, unitpriceว่าง, ค่าไฟรวมทั้งห้อง, monthlyไว้เทียบตามrunbook.
- รอCIaggregateผ่านและexactheadก่อนmerge; cleanexactSHAdeployment; rollbackapplicationไม่ย้อนschema.

## Production / Cloud State

Project sixth-storm-439008-u2; region asia-southeast3; CloudRun service sigroom; gcloud namedconfig sigroom; Firebasehosting:sigroom; public https://sigroom.web.app.
Auto-deploy trigger auto-deploy-sigroom ถูกdisabledและguardตรวจ. อย่าเปลี่ยนโปรเจกต์defaultหรือenabletrigger.

Latestmerge372e4059b7c2b7c220d7ec57f1d9a34c68ffdeb0.
Latestrevision sigroom-00079-ksb traffic100% (readactualตอนhandoff).
Liveimage digest:
asia-southeast3-docker.pkg.dev/sixth-storm-439008-u2/sigroom-repo/sigroom@sha256:1267e707312b6ea081d56da3fa0ea894ab26005b7931bb751133137649679420
Rollbackpreviousrevision sigroom-00078-mth(PR1).

FreshCloudSQLbackupก่อนPR1: instance sigroom-pg, ID1791063885035, SUCCESSFUL UTC2026-10-03T21:44:45.039Zถึง21:46:26.253Z. Backupoperatione6a26508-b60a-40ee-8ad3-12d600000064 DONE. ยังเป็นlatestตอนhandoff. ก่อนdeployschemaPR4/6/7ควรทำbackupใหม่และverifyสำเร็จ.

Deploymentต้องcleanreleaseworktreeHEAD40SHA=CommitSha, includinguntrackedcheck. ใช้guard:
    ./scripts/deploy-sigroom-production.ps1 -CommitSha <40-character-merge-sha>
    ./scripts/deploy-sigroom-production.ps1 -CommitSha <same-sha> -Deploy -ConfirmProduction DEPLOY
CloudBuildbuild/push exactimage, migrationjob sigroom-migrate --wait, CloudRun, collectstatic/Firebase/smoke. อย่าใช้directdeployแทนguard.
Logcollectstaticยาวมาก; redirectoutputไป .tmp/deploy-prN.log ในprimary (อย่าสร้างuntrackedในcleanreleaseก่อนguard). WarningsSMTP/HTTPS/proxyจากlocalcollectstaticไม่ใช่ข้อพิสูจน์ว่าprodSMTPผิด.

PUBLIC_BASE_URLprodตรวจแล้วhttps://sigroom.web.app. LatestreadUTC22:25ยังไม่มีGOOGLE_OAUTH_CLIENT_ID/SECRETหรือWEBPUSH_VAPID_PUBLIC/PRIVATE/SUBJECT. ระหว่างsessionไม่ได้เปลี่ยนGoogle/VAPID/Job/Scheduler. ต้องอ่านสดก่อนตั้ง.
Cloudmanualในrunbookเดิมถูกuserอนุญาตsafeoperationsภายหลัง แต่ยังไม่ได้ทำ:
1. PR4ตั้งsigroom-run-jobs+Schedulerทุก5minหลังdeployแล้วverifyjobexecution. OAuthleastprivjobinvoker. ต้องupdatejobimage/runtimeหลังทุกreleaseถัดไป มิฉะนั้นPR5pushจะไม่ถูกใช้ในงานตามเวลา.
2. PR5สร้างVAPIDcredentialsอย่างถูกformatเก็บSecretManagerไม่Git/log แล้วผูกruntimeและverify.
3. PR6schoolGoogleOAuthclient/branding/audienceตามข้อมูลจริง+secretrefs+exactcallback https://sigroom.web.app/auth/google/login/callback/ และrealroster. ไม่มีclientที่พิสูจน์แล้วให้ใช้ ไม่อ้างloginจริงผ่าน. ถ้าข้อมูล/ขั้นตอนจำเป็นต้องให้ผู้ดูแลทำ ให้บอกชัดในfinal.
4. Betaacceptanceจริงยังค้าง: realteacherสิทธิ์signalschool-teacher(ไม่ใช้superadminแทน), จองเริ่ม40min, 30/startbell+email, ครูอีกคนจองชนห้องไม่เสนอ. ต้องทราบactualusernameก่อนseedจริง ไม่แต่ง/เพิ่มคนจริงเองจากชื่อสมมติ.

## Immediate Next Steps

1. อ่านhandoffและinstructions แล้วgitfetch/readGitHubสด; ตรวจWIPทั้งหมดไม่ให้สูญหาย. เริ่มต่อที่primaryonline-beta(PR3) ไม่checkout/rootreset.
2. PR3finalfull1032จบแล้ว; ตรวจlatestcheck/drift/diff/independentreview+parentfullอิสระตามworkflow, เขียนhandoffพร้อม7actualscreens, commitThaiเฉพาะscope, push/openPRagainstverifiedbase/stackและattachartifactทันที. อ่านPRdiffCIทั้ง6ก่อนmergeexacthead; guarddeploycleanrelease.
3. รวมPR4เป็นfeat/teaching-remindersตามลำดับโดยรักษาPR3, ซ่อมdbdefaultและลบtemporaryroutefixture, full+reminderconsoleemail/bellBrowserQA, PRreview/CI/merge/deploy; ตั้งJobSchedulerตามdocและreadliveconfig.
4. PR5finishmissingmigration/tests/docs/on_commitindependentpush. Baseเก่าfilesต้องmergeblock ไม่overwrite. Verifykeyformatandmocktransportfailure, UI3states/iPhoneguide/SWnofetch/CSRF/ownership; allgatesก่อนPR/deploy. ตั้งVAPIDเฉพาะเมื่อreviewพร้อม.
5. รวมPR6Googleลงstack, combineddependencylock/migrationchain, updatehandoffcounts/docscommands, realBrowserQAON/OFF+studentowncohort, allregressionและCI. คำนึงcodefailclosedเมื่อยังไม่มีclient/roster; ไม่อ้างstudentGooglepathใช้งานจริง.
6. PR7finishtests/migrationintegration/independentreview+BrowserQA390desktopmeterdrawer beforePRrelease. Fixriskitemsaboveโดยไม่เดากฎคำนวณ.
7. เริ่มPR8implementationplan/isolatedbranchและallgates.
8. หลังdeployถัดไปทุกครั้ง updateprivatejobsruntimeimage/configให้ตรงเว็บ, verifyproductionrevision100%/smoke. รักษาrollback/backupIDsในledger.
9. Finalครบ8: PRnumber+branches, latestpytestแต่ละbranchจริง, merge/deploySHAs/revisions, รวมข้อสงสัย, Cloudstepsที่ทำแล้ว/ยังต้องuserทำ, หลักฐานQA. ขณะหยุดนี้ยังทำได้2/8releaseเท่านั้น.

## Potential Gotchas

- รวมworkerworktreesที่ฐานPR1กับstackPR2/3ด้วย3-waypatchหรือmanualblockreview. role_home/services/nav/templates/contextprocessors/models/testsชนหลายPR. อย่าคัดลอกทั้งไฟล์ทับ.
- MigrationnumbersPR6+7ชนbookings0016, PR5notificationsต้องต่อPR4. Regenerateownunpublisheddraftผ่านmakemigrationsบนfinalstack; ไม่editpublishedmigrations.
- PR4defaultPythonอย่างเดียวไม่พอสำหรับrollingoldwriter.
- Shared .env อาจมีข้อมูลจริง: อ่านในprocessไม่พิมพ์. Localwrapperloopbackguardเสมอ.
- MCPbackgroundpytestlaunchใช้ -q --disable-warnings + max_output_bytes>=18000; bytecapเป็นlaunchcapถาวร logsท้ายไม่กู้summaryที่truncatedได้. disable-warningsแค่presentation ไม่skiptests.
- ไม่runpytestพร้อมกันDBเดียว. Workerfullบนbaseเก่าไม่แทนfullfinalstack.
- CIa11yoldassertionsต้องclassifyไม่ลด48px/16px/10widths/contrast.
- BrowserJSreducedmotion/noJS/incomingpushจริงยังไม่ทดสอบถ้าไม่มีcapability/credentials; ระบุactualevidenceเท่านั้น.
- ไม่claimGoogleworksเพราะmockcallbackpasses; schoolclient+rosterยังค้าง.
- ห้ามใช้productionfakeQAcredentialsหรือเขียนproductionbookingเพื่ออ้างtestโดยไม่มีข้อมูลuserจริง.

## Assumptions Made

นับผล896ของPR6เป็นimplementationบนฐานPR1เท่านั้น และ1032ของPR3เป็นworkerfinalfullที่parentอ่านผลสำเร็จจริง. PR5/7ไม่มีผลtestsจึงไม่ถือพร้อมrelease. ระบุCloudstateตามเวลาที่อ่านสด และให้เอเจนต์ใหม่ตรวจใหม่ทุกครั้ง.

## Related Resources

- https://github.com/saisansan11/sigroom/pull/87
- https://github.com/saisansan11/sigroom/pull/88
- https://sigroom.web.app
- OfficialGoogleCloudsecrets: https://docs.cloud.google.com/run/docs/configuring/services/secrets
- OfficialSecretManager: https://docs.cloud.google.com/secret-manager/docs/creating-and-accessing-secrets
- OAuthwebserver: https://developers.google.com/identity/protocols/oauth2/web-server

## Ready-to-paste Prompt

ทำต่อ repo saisansan11/sigroom จาก F:/ogn_ROOM. อ่าน .claude/handoffs/2026-10-04-054723-online-beta-pr1-pr8-paused.md ให้จบ แล้วอ่าน workflow skill/CLAUDE/runbookและตรวจ Git/GitHub/Cloud สด. PR1#87และPR2#88merged+deployedแล้ว ห้ามทำซ้ำ. งานPR3-7ยังuncommittedอยู่ในworktreesที่handoffระบุ ห้ามลบ/reset/stage.tmpหรือcopyทั้งไฟล์จากbaseเก่าทับstack. เริ่มPR3feat/booking-cassette-passที่online-beta (fullล่าสุด1032ผ่าน,7BrowserQAimages), ทำgatesล่าสุด/handoff/commit/PR/CI แล้วmergeและguarddeployเมื่อปลอดภัย จากนั้นPR4-8ตามลำดับ. ผู้ใช้อนุญาตsafe merge/deploy/Cloudและไม่ให้ถามสิทธิ์ซ้ำ แต่ห้ามลดtest/security/reviewgatesหรือเดาข้อมูลบัญชีจริง. PR4ต้องซ่อมpersistentdb_defaultก่อนdeploy; PR5ยังขาดmigration/tests/docs/reminderintegration; PR6full896บนbasePR1ยังต้องรวมstack+BrowserQA+schoolclient/roster; PR7ยังไม่มีtests; PR8ยังไม่เริ่ม. ทำให้ครบแล้วรายงาน8PR/ผลpytest/ข้อสงสัย/Cloudงานที่ทำแล้วและค้างตามrunbook.

