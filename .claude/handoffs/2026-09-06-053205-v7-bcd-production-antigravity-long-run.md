# Handoff: V7 งาน B–D ขึ้น Production แบบ Long Run แล้วส่ง Codex ตรวจครั้งเดียว

## Session Metadata

- Created: 2026-09-06 05:32 (Asia/Bangkok)
- Project: `F:\ogn_ROOM`
- Repository: `saisansan11/sigroom`
- Current local branch at handoff: `feat/v7-d-pwa`
- Integration head: `origin/feat/v7-b-online` at `93a9365`
- Production branch: `feat/lodging-v5-2`
- Production URL: `https://sixth-storm-439008-u2.web.app/`
- Canonical Firebase site: `https://sigroom.web.app/`
- Continues from: `2026-09-06-041201-v7-d-pwa-antigravity.md`
- Intended executor: Antigravity
- Final reviewer: Codex in the current pinned task `ตรวจรับ SIGROOM หลัง Antigravity`

## Current State Summary

งาน A อยู่บน production แล้ว ส่วนงาน B, C และ D รวมอยู่บน branch `feat/v7-b-online` ผ่าน PR #13 และ #14 ปัจจุบัน PR #12 ยังเปิดจาก `feat/v7-b-online` ไป `feat/lodging-v5-2` และกลายเป็น integration PR ที่รวม B–D จำนวนประมาณ 33 ไฟล์ แม้ชื่อและคำอธิบายยังกล่าวถึงงาน B เป็นหลัก Production ยังรัน revision `sigroom-00012-hpq` จาก image commit `e8077a4` จึงยังไม่มีงาน B–D ผู้ใช้ขอให้ Antigravity ทำงานรอบยาวจน deploy และตรวจ production เสร็จ แล้วส่งหลักฐานชุดเดียวให้ Codex ตรวจภายหลังผ่านมือถือ

## Immediate Next Steps

1. อ่าน Hard Stop Rules และ Authorization ให้ครบก่อนเรียกคำสั่งใด
2. ตรวจ working tree, remote refs และสถานะ PR #12 โดยไม่แตะ `.claude/handoffs/`
3. switch ไป exact integration head `feat/v7-b-online` และรัน Phase 2 validation ทั้งชุด
4. ปรับ title/body PR #12 ให้สะท้อน B–D แล้วสร้าง backup ตาม Phase 3
5. เมื่อทุก gate ผ่าน จึง merge PR #12 และทำ Phase 4–10 ต่อเนื่องจนส่ง final review packet

## Files Modified by This Handoff Session

- `.claude/handoffs/2026-09-06-053205-v7-bcd-production-antigravity-long-run.md` — เอกสารประสานงานเท่านั้น ห้าม commit เข้า product PR

ไม่มี source code หรือ production configuration ถูกแก้ในระหว่างจัดทำ handoff นี้

## Assumptions Made

- PR #12 ยัง OPEN และ mergeable เมื่อ Antigravity เริ่มงาน; หากเปลี่ยนต้องตรวจใหม่
- Cloud Build trigger และ production branch ยังตรงกับข้อมูลใน Important Context
- เจ้าของตั้งใจอนุญาต long run ของ B–D รวม merge/deploy แต่ยังไม่อนุญาต Work E
- Production migrations ทั้ง 4 ไฟล์เป็น expand-compatible ตามที่รีวิวไว้
- Antigravity อาจไม่มี production credential จึงต้องยอมรับ authenticated smoke เป็น pending แทนการ bypass

## Potential Gotchas

- การ merge PR #12 จะ trigger production deployment อัตโนมัติทันที
- PR #12 body เดิมรายงานเพียง 159 tests และ 2 migrations ซึ่งล้าสมัย
- `feat/v7-b-online` รวม merge commits ของ PR #13/#14 แล้ว อย่าพยายาม cherry-pick ซ้ำ
- ชื่อ Firebase project URL กับ site URL มีสองแบบ ต้องตรวจทั้งคู่แต่ใช้ project URL เป็นหลัก
- คำว่า 404 ของ manifest ถูกต้องเฉพาะก่อน deploy หลัง deploy ต้องเป็น 200
- อย่าใช้ค่า “latest build” เป็นหลักฐานถ้าไม่ได้เทียบ commit SHA
- Release QA เป็น public artifact ต้องตรวจภาพไม่ให้มีข้อมูลจริงก่อน upload

## Authorization for This Long Run

คำสั่งล่าสุดของเจ้าของระบบอนุญาตให้ Antigravity ทำขั้นตอนต่อไปนี้ต่อเนื่องโดยไม่ต้องรอ Codex ตรวจระหว่างทาง หากทุก gate ผ่าน:

1. ตรวจและแก้เฉพาะข้อผิดพลาดใน integration scope งาน B–D
2. ปรับ title/body ของ PR #12 ให้ตรงกับขอบเขตจริง
3. สร้าง Cloud SQL on-demand backup ก่อน deploy
4. merge PR #12 เข้า `feat/lodging-v5-2`
5. เฝ้า Cloud Build จน build, migrate และ deploy จบ
6. ตรวจ production แบบ public และ authenticated เฉพาะเมื่อมี session/login ที่ถูกต้องอยู่แล้ว
7. เก็บหลักฐานที่ไม่มีข้อมูลอ่อนไหว
8. เปิด documentation-only acceptance PR หากต้องอัปเดต `docs/v7-notes.md`
9. ทำ rollback ไป revision เดิมได้เฉพาะเมื่อ deployment ใหม่มีอาการเสียหายชัดเจนตามเกณฑ์ Rollback ด้านล่าง
10. ส่ง final review packet ชุดเดียว แล้วหยุดรอ Codex

การอนุญาตนี้ไม่ครอบคลุมงาน E, การเดาข้อมูล master data, การรีเซ็ตรหัสผ่าน, การสร้าง session ข้ามหน้า login, การ restore ฐานข้อมูล หรือการลบ branch/release/backup

## Hard Stop Rules

ห้ามทำรายการต่อไปนี้:

- ห้ามเริ่ม Work E หรือสร้าง migration ราคา/มิเตอร์ เพราะเจ้าของยังไม่ตอบคำถาม 5 ข้อ
- ห้ามรัน `seed_pilot` บน production
- ห้ามสร้างห้องออนไลน์จริงจนยืนยันจำนวน/ชื่อ เนื่องจากเอกสาร rev.4 ระบุ 2 ห้อง แต่ seed/PR ระบุ 3 ห้อง
- ห้าม reset password ของ production หรือ local user
- ห้ามสร้าง Django session ด้วย shell หรือพิมพ์ session key/cookie/token ลง log
- ห้ามอ่านหรือแสดงค่า Secret Manager secret
- ห้ามใส่ password, cookie, API key, phone, attendee data หรือข้อมูลผู้ใช้จริงใน screenshot/PR comment
- ห้าม push ตรงเข้า `feat/lodging-v5-2`; การเปลี่ยนโค้ด production ต้องผ่าน PR #12 เท่านั้น
- ห้ามแก้ข้อมูลการจองจริงเพื่อ smoke test ถ้าลบคืนอย่างปลอดภัยไม่ได้
- ห้าม restore Cloud SQL backup โดยไม่มีคำสั่งใหม่จากเจ้าของระบบ
- ห้ามลบ release `v7-d-qa`, feature branches หรือ backup หลังงานเสร็จ
- ห้ามทำ manual deployment ข้าม Cloud Build pipeline เว้นแต่ใช้ rollback ตามเกณฑ์ที่กำหนด

## Important Context

- PR #13 และ PR #14 ถูก merge เข้า `feat/v7-b-online` แล้ว
- PR #12 ยังเปิดและ mergeable แต่ title/body ล้าสมัย ปัจจุบันรวม B+C+D
- PR #12 ไม่มี GitHub Actions checks; ต้องยืนยันด้วย local validation และ Cloud Build
- Cloud Build trigger `auto-deploy-sigroom` ทำงานเมื่อ push เข้า branch `feat/lodging-v5-2`
- Pipeline ใช้ image tag `$COMMIT_SHA`, รัน `sigroom-migrate` ก่อน deploy และหยุดถ้า migration ล้มเหลว
- Production revision ก่อนรอบนี้คือ `sigroom-00012-hpq`; image เดิมลงท้ายด้วย `e8077a410dff023e2d69fb50a0e518b44d8064f2`
- การทดสอบล่าสุดบน feature head ผ่าน `177 passed`
- Work D ไม่มี service worker/offline โดยตั้งใจ เว็บต้องใช้เครือข่าย
- Production `/manifest.webmanifest` ยัง 404 ก่อน deploy และต้องเปลี่ยนเป็น 200 หลัง deploy
- Admin username คือ `admin` แต่ handoff นี้ไม่มี password และห้ามถาม/บันทึก password ใน PR
- Working tree มี `.claude/handoffs/` แบบ untracked เพื่อประสานงาน ห้าม commit โฟลเดอร์นี้
- Local development server ต้องไม่ค้างหลังจบงาน

## Architecture Overview

- Django modular monolith ให้บริการผ่าน Cloud Run `sigroom` ใน region `asia-southeast3`
- Firebase Hosting site `sigroom` rewrite ทุก path ไป Cloud Run และใช้ CDN สำหรับ static assets
- PostgreSQL 16 อยู่ใน Cloud SQL instance `sigroom-pg` เชื่อมผ่าน private Cloud SQL socket
- Environment secrets `DB_PASSWORD` และ `DJANGO_SECRET_KEY` มาจาก Secret Manager
- Cloud Build service account คือ `sigroom-build-sa@...`; runtime ใช้ `sigroom-run-sa@...`
- Production deploy branch คือ `feat/lodging-v5-2`, ไม่ใช่ `main`
- Migration job ต้องใช้ image SHA เดียวกับ service deployment เพื่อกัน build race

## Critical Files and Resources

| Item | Purpose | Check |
|---|---|---|
| `cloudbuild.yaml` | build → push → migrate → deploy | ใช้ `$COMMIT_SHA` และ migrate ก่อน deploy |
| `firebase.json` | Firebase rewrite ไป Cloud Run | site `sigroom`, region Bangkok |
| `bookings/migrations/0010_*` | online meeting URL | expand migration |
| `resources/migrations/0005_*` | online room category choices | expand migration |
| `accounts/migrations/0003_*` | favorite rooms M2M | expand migration |
| `bookings/migrations/0011_*` | time preset choice | expand migration |
| `bookings/services.py` | availability, rebook, presets, permissions | business rules อยู่ service |
| `config/tests_v7_d.py` | manifest/PWA acceptance | 5 tests |
| `docs/v7-notes.md` | QA/device/user metrics | อัปเดตเฉพาะผลจริง |
| PR #12 | final integration PR B–D | ต้องแก้ title/body ก่อน merge |
| Release `v7-d-qa` | local visual evidence | เก็บไว้ ไม่ลบ |

## Decisions Already Made

| Decision | Rationale |
|---|---|
| ให้ Antigravity ทำ long run จน production QA | ผู้ใช้จะพาลูกเที่ยวและต้องการ Codex ตรวจครั้งเดียวภายหลัง |
| ใช้ PR #12 เป็น integration PR B–D | C/D ถูกรวมเข้า branch B แล้วและ PR #12 เป็นทางเดียวเข้าสู่ production branch |
| สร้าง backup ก่อน merge | PR มี 4 migrations และ production มีข้อมูลใช้งานจริง |
| ใช้ Cloud Build pipeline เท่านั้น | pipeline ผูก image SHA, migration และ deploy ไว้ถูกลำดับแล้ว |
| อนุญาต rollback เฉพาะ service revision | expand migrations รองรับ old app; ไม่ย้อน DB โดยพลการ |
| ไม่สร้างห้องออนไลน์จริง | จำนวน 2/3 ห้องยังขัดกัน ต้องรอเจ้าของยืนยัน |
| ไม่เริ่ม Work E | ราคา/การแบ่งค่าไฟ/วิธีนับวันยังต้องตัดสินใจ 5 ข้อ |

## Phase 0 — Safety and Workspace Preparation

1. อ่าน handoff นี้ทั้งหมดก่อนเริ่ม
2. เปิด `F:\ogn_ROOM` และตรวจ `git status --short --branch`
3. อย่าลบหรือ commit `.claude/handoffs/`
4. fetch remote refs และตรวจว่า:
   - PR #12 ยัง OPEN
   - base = `feat/lodging-v5-2`
   - head = `feat/v7-b-online`
   - mergeable = MERGEABLE
5. ตรวจว่า `origin/feat/v7-b-online` มี merge commit PR #13 (`47e8cc6`) และ PR #14 (`93a9365`)
6. สร้างหรือ switch local tracking branch `feat/v7-b-online` โดยไม่ทับไฟล์ผู้ใช้
7. บันทึก SHA ของ integration head, production head, Cloud Run revision และ image ก่อนเปลี่ยนอะไร
8. ตรวจว่าไม่มี process จาก dev server หรือ test runner ค้าง

ถ้าพบ dirty changes ที่ไม่ใช่ `.claude/handoffs/` ให้หยุดและรายงาน ห้าม stash/reset/checkout ทับโดยเดา

## Phase 1 — Repair PR #12 Metadata

แก้ชื่อ PR #12 เป็น:

`feat(v7): รวมงาน B–D ห้องออนไลน์ จองเร็ว และ PWA`

แก้ body ให้มีหัวข้ออย่างน้อย:

1. งาน B: online category, meeting URL, link permissions, online card
2. งาน C: rebook, time presets, favorite rooms, time-flake stabilization
3. งาน D: manifest, icons, install guide, 360px QA
4. Migration ทั้ง 4 ไฟล์ พร้อมระบุ expand-compatible
5. Full test result ล่าสุดจาก exact integration head
6. `manage.py check`, migration check และ diff check
7. ลิงก์ PR #13, PR #14 และ release `v7-d-qa`
8. ข้อจำกัด: no service worker, no offline, no native app
9. Production plan: Cloud Build auto-deploy on merge
10. Deferred: actual device test, 3-user metrics, production online-room creation, Work E

อย่าลบประวัติ/ความคิดเห็นเดิมใน PR ใช้การแก้ body เพื่อให้สถานะล่าสุดอ่านได้จากมือถือ

## Phase 2 — Exact-Head Pre-Merge Validation

รันจาก `feat/v7-b-online` ที่ตรงกับ remote head:

```powershell
uv run pytest
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py showmigrations --plan
git diff --check origin/feat/lodging-v5-2...HEAD
git diff --name-status origin/feat/lodging-v5-2...HEAD
git status --short --branch
```

Expected baseline:

- `177 passed`
- system check 0 issues
- no missing migrations
- integration diff ประมาณ 33 files
- migrations ที่เพิ่ม 4 ไฟล์
- ไม่มี `.env`, database, screenshot with sensitive data, handoff หรือ temp files

ทำ targeted security tests เพิ่ม:

- ผู้จองเห็น online meeting URL
- superuser/infosec/assigned staff เห็น URL ตาม policy
- same-unit user ที่ไม่มีสิทธิ์ไม่เห็น URL
- guest/unauthorized ไม่เห็น URL
- notification ไม่ฝัง URL
- favorite toggle ป้องกัน open redirect
- manifest public และ password-gate bypass

ตรวจ source เพิ่ม:

- ไม่มี `serviceWorker`, `sw.js`, offline cache
- ไม่มี `seed_pilot` ถูกเรียกใน deploy pipeline
- ไม่มี secret literal
- `time_presets` ไม่โผล่ใน summary mode

ถ้า validation fail:

- แก้เฉพาะ regression ที่เกี่ยวกับ B–D
- commit บน `feat/v7-b-online`
- push และรัน validation ใหม่ทั้งหมด
- ถ้าต้องเปลี่ยน business rule หรือข้อมูล production ให้หยุด ห้ามเดา

## Phase 3 — Pre-Deploy Backup and Rollback Record

ก่อน merge PR #12:

1. สร้าง Cloud SQL on-demand backup ของ instance `sigroom-pg`
2. รอ backup สถานะ SUCCESS
3. บันทึก backup ID และ creation time ใน final packet ห้ามบันทึก secret
4. บันทึก production branch SHA ก่อน merge
5. บันทึก Cloud Run revision `sigroom-00012-hpq` และ old image SHA
6. ตรวจว่า migration job `sigroom-migrate` อยู่ในสถานะพร้อมใช้งาน
7. ตรวจ Cloud Build trigger `auto-deploy-sigroom` ยังจับ `^feat/lodging-v5-2$`

ห้าม merge หาก backup ไม่สำเร็จหรือ migration job หาย

## Phase 4 — Merge PR #12 and Monitor Deployment

เมื่อ Phase 0–3 ผ่านครบ ให้ merge PR #12 แบบ merge commit เข้า `feat/lodging-v5-2` ตาม authorization รอบนี้

หลัง merge:

1. บันทึก merge commit SHA และเวลา
2. หา Cloud Build ที่ trigger จาก SHA นั้น ห้ามดูแค่ build ล่าสุดโดยไม่เทียบ SHA
3. เฝ้า build จนจบ โดยตรวจแต่ละช่วง:
   - Docker build
   - push `$COMMIT_SHA`
   - push `latest`
   - update/execute `sigroom-migrate`
   - Cloud Run deploy
4. บันทึก Cloud Build ID, status, start/end time
5. ยืนยัน migration job execution สำเร็จ
6. ยืนยัน Cloud Run latest ready revision ใช้ image SHA เดียวกับ merge commit
7. ยืนยัน traffic 100% ไป revision ใหม่
8. ยืนยัน Firebase Hosting ยัง rewrite ไป service `sigroom` region `asia-southeast3`

ถ้า build หรือ migration fail ก่อน deploy:

- production เดิมยังอยู่ ให้หยุด
- เก็บ build log URL และสรุป root cause
- ห้าม manual deploy ข้าม migration

ถ้า migration ผ่านแต่ service deploy fail:

- ยืนยัน revision เดิมยังรับ traffic
- ห้ามย้อน migration เพราะ migrations เป็น expand
- เก็บหลักฐานและหยุด

## Phase 5 — Production Smoke Test

ใช้ `https://sixth-storm-439008-u2.web.app/` เป็น primary URL และตรวจ `https://sigroom.web.app/` ด้วย

### Public checks

ตรวจ HTTP/status และ browser rendering:

- `/` หน้าแรก guest
- `/accounts/login/`
- `/admin/` ต้อง redirect ไปหน้า admin login
- `/manifest.webmanifest` ต้อง 200 และ `application/manifest+json`
- icon 192 และ 512 ต้อง 200 และเป็น PNG
- `/lodging/` และ active cohort portal ที่เปิดเผยต่อ guest
- static CSS/JS ไม่มี 404 สำคัญ

ตรวจ manifest fields:

- name/short_name/lang
- start_url `/`
- scope `/`
- display `standalone`
- theme/background colors
- icon paths/sizes/types

### Authenticated checks

ใช้เฉพาะ browser session ที่ login ถูกต้องอยู่แล้ว หรือ login ผ่านหน้าเว็บด้วย credential ที่เจ้าของให้โดยตรง ห้าม reset password หรือสร้าง session ด้วย shell

ถ้า login ได้ ให้ตรวจ:

- account menu desktop/mobile และ install guide
- หน้าแรกหลัง login
- ค้นหาห้อง
- booking summary mode
- booking date/time mode
- my bookings
- booking detail
- approvals
- reports
- notifications
- favorite toggle โดยใช้ข้อมูลทดสอบที่ย้อนคืนได้
- rebook flow โดยหยุดก่อนส่งคำขอจริงถ้าไม่มี test record

ถ้าไม่มี credential/session ให้ระบุ `pending owner authenticated smoke` ห้ามพยายาม bypass

### Database and logs

- ตรวจ migrations ใหม่ทั้ง 4 applied
- ตรวจ Cloud Run error logs หลัง deploy อย่างน้อย 10–15 นาที
- ต้องไม่มี 500 burst, database column error, migration error หรือ static asset error
- ห้ามเปิดเผย query parameters/cookies/user data ในรายงาน

## Phase 6 — Production Visual Evidence

เก็บ screenshot ที่ไม่มีข้อมูลอ่อนไหว:

1. Guest home หลัง deploy
2. Manifest response
3. Mobile 360px login
4. Mobile 360px account/install guide เฉพาะถ้ามี valid session
5. Booking/search/report อย่างละภาพ เฉพาะเมื่อเป็นข้อมูล demo/blank
6. Cloud Build success summary ที่ไม่แสดง secrets
7. Cloud Run revision/traffic summary ที่ไม่แสดง env values

สร้าง prerelease ชื่อ `v7-bcd-prod-qa` target ไปที่ production merge SHA แล้วอัปโหลดเฉพาะภาพปลอดภัย หรือใช้ artifact link ที่เปิดจากมือถือได้เทียบเท่า

อย่าอัปโหลด:

- password/session cookie
- Secret Manager values
- ชื่อ/เบอร์โทร/ข้อมูลจองจริง
- Cloud SQL connection credentials
- browser storage หรือ developer tools ที่มี token

## Phase 7 — Production Master-Data Inventory Only

ตรวจแบบ read-only ว่ามีห้อง category `online` บน production กี่ห้อง พร้อม code/name/building/owner/capacity/policy โดยใช้ Admin ที่ login ถูกต้องหรือ safe read-only management command

จากนั้น:

- ถ้ามีห้องออนไลน์จริงอยู่แล้ว ให้บันทึกรายการและทดสอบ card/search โดยไม่แก้ข้อมูล
- ถ้าไม่มี ให้บันทึก `pending owner confirmation`
- ถ้ามี 2 หรือ 3 ห้องแต่ข้อมูลไม่ตรงแผน ให้รายงานความต่าง
- ห้ามสร้าง/แก้/ลบห้องในรอบนี้
- ห้ามรัน `seed_pilot`

เหตุผล: แผน rev.4 กล่าวถึง 2 ห้อง แต่ seed และ PR body กล่าวถึง 3 ห้อง การเลือกแทนเจ้าของจะสร้าง master data ผิดได้

## Phase 8 — PWA and User Acceptance Status

Antigravity ตรวจได้เฉพาะ browser/PWA metadata บน HTTPS ในรอบนี้

ให้คงรายการต่อไปนี้เป็น pending จนเจ้าของทำเอง:

- Android Chrome: add to home screen, icon, standalone launch
- iPhone Safari: add to home screen, icon, standalone launch
- ผู้ใช้จริง 3 คน: จองครั้งแรกไม่เกิน 2 นาที
- เส้นทางปกติทุกประเภทห้องไม่เกิน 3 คลิก

ห้ามกรอกว่า passed จาก emulator/CDP แทนเครื่องจริง

## Phase 9 — Documentation-Only Acceptance PR

หลัง production smoke เสร็จ:

1. สร้าง branch `docs/v7-bcd-production-acceptance` จาก production branch หลัง merge
2. อัปเดต `docs/v7-notes.md` เฉพาะผลที่ตรวจจริง
3. เพิ่ม:
   - deploy commit/revision/build ID
   - backup ID
   - public/authenticated smoke table
   - manifest production result
   - online room inventory
   - device/user metrics ที่ยัง pending
   - known issue time presets ใน booking edit หากยังอยู่
4. เปิด PR ไป `feat/lodging-v5-2`
5. ห้าม merge documentation PR ให้ Codex ตรวจพร้อม final packet

## Rollback Criteria

Rollback Cloud Run traffic ไป revision เดิม `sigroom-00012-hpq` ได้ทันทีเมื่อพบอย่างใดอย่างหนึ่ง:

- production home/login/admin ตอบ 5xx ต่อเนื่อง
- application boot fail หรือ revision ใหม่ไม่ Ready
- database schema error จาก code ใหม่
- login/session ใช้งานไม่ได้ทุกบัญชีผ่าน Firebase
- guest route เปิดเผยข้อมูลที่ควรถูก mask
- online meeting URL รั่วแก่ guest/unauthorized user

ขั้น rollback:

1. เก็บหลักฐาน error และ timestamp
2. ส่ง traffic 100% กลับ revision เดิม
3. ตรวจ home/login อีกครั้ง
4. ห้าม restore database
5. บันทึก `ROLLED_BACK` พร้อมเหตุผลใน final packet
6. หยุดงานและรอ Codex/owner

สิ่งต่อไปนี้ไม่ใช่เหตุให้ rollback ทันที:

- screenshot ไม่สวย
- PWA install บนอุปกรณ์จริงยัง pending
- ไม่มีห้องออนไลน์ production
- test data ไม่พร้อม
- warning ที่ไม่ทำให้ผู้ใช้ใช้งานไม่ได้

## Phase 10 — Cleanup

ก่อนส่งมอบ:

- ปิด local dev server/test runner
- ลบเฉพาะ temp files ที่ Antigravity สร้างเอง
- ไม่ลบ backup, release, branch หรือ logs
- ตรวจ `git status` ไม่มีไฟล์ชั่วคราวนอกจาก `.claude/handoffs/` ที่มีอยู่ก่อน
- ตรวจ production traffic/revision รอบสุดท้าย
- ตรวจว่าไม่มี active privileged session ที่ Antigravity สร้างด้วยวิธี bypass; ตามกติกาไม่ควรมีตั้งแต่แรก

## Final Review Packet for Mobile

Antigravity ต้องส่งรายงานเดียวที่อ่านบนมือถือได้ โดยเริ่มบรรทัดแรกว่า:

`ANTIGRAVITY_DONE — READY_FOR_CODEX_REVIEW`

รายงานต้องมีข้อมูลต่อไปนี้ตามลำดับ:

1. PR #12 URL, final title, merge status และ merge SHA
2. Production branch SHA ก่อน/หลัง
3. Cloud SQL backup ID/status/time
4. Cloud Build ID/status และลิงก์
5. Migration job execution status
6. Old revision/image และ new revision/image
7. Traffic allocation
8. Automated validation exact counts
9. Production smoke table: URL/check/status/evidence
10. Manifest production content type และ icon status
11. Cloud Run error-log summary
12. Online-room inventory และเหตุผลที่ไม่แก้ข้อมูล
13. PWA Android/iPhone status ตามจริง
14. 3-user metrics status ตามจริง
15. QA evidence release/artifact URL
16. Documentation acceptance PR URL
17. Rollback status: not needed / performed พร้อมเหตุผล
18. Security statement: no secrets printed, no password reset, no forged sessions
19. Remaining blockers สูงสุด 5 ข้อ
20. ข้อความสุดท้าย: `STOPPED — NO WORK E STARTED`

ห้ามส่งเพียงข้อความว่า “เสร็จ 100%” ต้องมี ID/SHA/URL/status ให้ Codexตรวจย้อนกลับได้

## Mobile Return Channel

เจ้าของระบบจะกลับมาคุยกับ Codex ผ่านมือถือใน task ชื่อ `ตรวจรับ SIGROOM หลัง Antigravity`

เมื่อ Antigravity จบ ให้เจ้าของส่งอย่างใดอย่างหนึ่งใน task นี้:

- วาง final review packet ทั้งชุด หรือ
- ส่งข้อความ: `ตรวจรับงาน Antigravity ตาม PR #12 และ docs acceptance PR` พร้อม URL ของ documentation PR

Codex จะตรวจ GitHub, Cloud Build, Cloud Run, production URLs, screenshots, tests และ rollback state ครั้งเดียวจาก packet นี้

## Deferred Work

รายการต่อไปนี้ไม่อยู่ใน long run นี้:

- Work E เรตราคาห้องพัก/มิเตอร์/ใบสรุป
- การตอบคำถามราคา 5 ข้อ
- การสร้างห้องออนไลน์ production
- Android/iPhone real-device acceptance
- การทดสอบผู้ใช้จริง 3 คน
- การ merge documentation acceptance PR
- การ deploy งาน E

## Definition of Done for Antigravity

Antigravity จบงานรอบนี้เมื่อ:

- PR #12 metadata ตรงกับ B–D
- exact-head validation ผ่าน
- backup สำเร็จ
- PR #12 merged ตาม authorization
- Cloud Build/migrate/deploy สำเร็จ หรือ rollback สำเร็จตามเกณฑ์
- production public smoke ผ่าน
- authenticated smoke ผ่านเท่าที่มี credential ถูกต้อง โดยไม่มี bypass
- production evidence เปิดจากมือถือได้และไม่มีข้อมูลอ่อนไหว
- online-room inventory ถูกบันทึกโดยไม่แก้ master data
- documentation acceptance PR เปิดแต่ยังไม่ merge
- final review packet ครบ 20 ข้อ
- ไม่มี Work E หรือ action นอก scope
- หยุดรอ Codex review

## Short Instruction to Paste into Antigravity

> เปิดและอ่านไฟล์ `F:\ogn_ROOM\.claude\handoffs\2026-09-06-053205-v7-bcd-production-antigravity-long-run.md` ทั้งหมด แล้วทำตามทุก Phase ต่อเนื่องจนถึง final review packet ผู้ใช้ออกไปพาลูกเที่ยวและอนุญาต long run รวมการตรวจ PR #12, backup, merge, เฝ้า Cloud Build, production smoke, evidence และ documentation acceptance PR เมื่อทุก gate ผ่าน ห้าม reset password, forge session, run seed บน production, สร้างห้องจริง, เริ่ม Work E, restore database หรือลบทรัพยากรหลัก หากเกิด critical production failure ให้ rollback service revision ตามเกณฑ์ในเอกสาร แล้วส่งรายงานเดียวที่ขึ้นต้น `ANTIGRAVITY_DONE — READY_FOR_CODEX_REVIEW` และหยุดรอ Codex
