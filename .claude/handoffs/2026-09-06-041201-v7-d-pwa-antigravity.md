# Handoff: ส่งงาน V7-D PWA ให้ Antigravity ทำต่อ และส่งกลับให้ Codex ตรวจ

## Session Metadata

- Created: 2026-09-06 04:12:01 (Asia/Bangkok)
- Project: `F:\ogn_ROOM`
- Repository: `saisansan11/sigroom`
- Current branch: `feat/v7-d-pwa`
- Base branch while PR #13 is open: `feat/v7-c-fast`
- Base commit: `8d9262a`
- Status: งาน D ทำไว้เกือบครบใน working tree แต่ยังไม่ commit, push หรือเปิด PR

### Recent Commits

- `8d9262a` feat(v7-c): จองแบบเดิมอีกครั้ง + ช่วงเวลาสำเร็จรูป + ห้องโปรด
- `a227d45` feat(v7-b): หมวดห้องสอนออนไลน์ + ลิงก์ประชุมพร้อมสิทธิ์เข้มกว่า can_view_details
- `e8077a4` Merge pull request #11 from saisansan11/feat/v7-a-onestop

## Objective

รับช่วงงาน D จาก working tree ปัจจุบัน ตรวจทานและปรับให้ผ่านเกณฑ์ PWA สำหรับเว็บ จากนั้นเก็บหลักฐาน ตรวจคุณภาพ เปิด stacked PR และหยุดรอ Codex review

งานนี้ยังเป็นเว็บเดิม ไม่ใช่ native app และไม่ขึ้น App Store หรือ Play Store ผู้ใช้เปิดผ่าน browser ได้ตามปกติ ส่วนการติดตั้งไว้บนหน้าจอหลักเป็นเพียงตัวเลือกเพิ่มเติม

## Current State Summary

Work D ถูกพัฒนาและตรวจเบื้องต้นไว้เกือบครบใน working tree ของ `feat/v7-d-pwa` แล้ว แต่ทุกไฟล์ยังไม่ commit หรือ push และยังไม่มี PR งาน D การทดสอบอัตโนมัติล่าสุดผ่านทั้งหมด ส่วนที่ต้องรับช่วงคือทบทวน diff, ตรวจ UI ที่ 360px อีกครั้งพร้อมเก็บภาพ, อัปเดตผลจริงในเอกสาร, commit/push และเปิด stacked PR เทียบกับ `feat/v7-c-fast` จากนั้นหยุดรอ Codex ตรวจโดยไม่ merge หรือ deploy

## Important Context

- PR #13 คืองาน C และยังเปิดอยู่ งาน D จึงต้องวางซ้อนบน branch `feat/v7-c-fast` เพื่อไม่ให้ diff ปนกัน
- ผู้ใช้ต้องการเว็บ ไม่ได้ต้องการ native app; PWA ในที่นี้หมายถึงเว็บเดิมที่เลือกเพิ่มไว้บนหน้าจอหลักได้
- งานที่อยู่ใน working tree ผ่าน tests แล้ว การรับช่วงต้องรักษาและตรวจงานนั้นก่อนตัดสินใจแก้
- สิ่งที่ยังขาดจริงคือหลักฐาน screenshot ใน PR และ real-device install test ซึ่งอาจต้องบันทึกเป็น pending owner test

## Immediate Next Steps

1. ยืนยัน branch และตรวจ `git status --short` กับ `git diff` โดยไม่ทิ้งการเปลี่ยนแปลงเดิม
2. เทียบ implementation กับ acceptance criteria 12 ข้อและแผนต้นฉบับจาก commit ที่ระบุ
3. ทำ Visual QA/validation ใหม่ เก็บหลักฐาน แล้วเปิด stacked PR ตามข้อกำหนดด้านล่าง

## Scope and Acceptance Criteria

ต้องผ่านครบทุกข้อ:

1. มี `/manifest.webmanifest` ที่ตอบ HTTP 200 และ `Content-Type: application/manifest+json`
2. Manifest มีอย่างน้อย `name`, `short_name`, `lang`, `start_url`, `scope`, `display`, `theme_color`, `background_color` และ icons ขนาด 192x192 กับ 512x512
3. `templates/base.html` ลิงก์ manifest และมี meta สำหรับ theme color กับ iOS standalone
4. มี Apple touch icon
5. ไอคอน PWA เป็น PNG จริง ขนาดถูกต้อง และแสดงตัวตนของ SIGROOM
6. Manifest เข้าถึงได้แม้ผู้ใช้ยังไม่เปลี่ยนรหัสผ่านครั้งแรก
7. เมนูบัญชีทั้ง desktop และ mobile มีคู่มือติดตั้ง Android/Chrome 3 ขั้นตอน
8. เมนูเดียวกันมีคู่มือติดตั้ง iPhone/Safari 3 ขั้นตอน
9. คู่มือระบุชัดว่าระบบยังต้องใช้อินเทอร์เน็ต
10. ไม่มี service worker, offline cache, native wrapper หรือ app-store packaging ในงาน D
11. ตรวจ responsive ที่ viewport กว้าง 360px ตามรายการในหัวข้อ Visual QA และแนบภาพหลักฐานใน PR
12. รัน automated tests, Django checks, migration check และ diff check ผ่าน

## Authorized Changes

แก้ได้เฉพาะส่วนที่จำเป็นต่อ Work D และการทดสอบ/เอกสารของ Work D โดยให้รักษางาน A–C และพฤติกรรมเดิมทั้งหมด

ไฟล์ที่มีการเปลี่ยนแปลงอยู่แล้ว:

| File | Current change | Purpose |
|---|---|---|
| `accounts/middleware.py` | ยกเว้น manifest จาก initial-password gate | ให้ browser โหลด manifest ได้เสมอ |
| `config/urls.py` | เพิ่ม route `/manifest.webmanifest` | เสิร์ฟ manifest ด้วย content type ที่ถูกต้อง |
| `static/css/app.css` | เพิ่มสไตล์คู่มือติดตั้งและ scroll ของ account popover | รองรับ desktop/mobile |
| `templates/base.html` | เพิ่ม meta, manifest link, icon และ include คู่มือสองตำแหน่ง | เชื่อม PWA metadata กับทุกหน้า |
| `config/tests_v7_d.py` | เพิ่ม acceptance tests 5 รายการ | ป้องกัน regression ของงาน D |
| `docs/v7-notes.md` | บันทึกผลตรวจและงานที่ยังรอเจ้าของระบบ | หลักฐานตามแผน V7 |
| `scripts/generate_pwa_icons.py` | สคริปต์สร้างไอคอน | ทำให้ asset สร้างซ้ำได้ |
| `static/img/pwa-icon-192.png` | ไอคอน 192x192 | Manifest/Apple touch icon |
| `static/img/pwa-icon-512.png` | ไอคอน 512x512 | Manifest install surface |
| `templates/includes/pwa_install_guide.html` | คู่มือติดตั้ง Android/iPhone | ใช้ร่วมกันในเมนู desktop/mobile |
| `templates/manifest.webmanifest` | ข้อมูล PWA | Browser install metadata |

ห้ามทำโดยไม่มีคำสั่งใหม่จากเจ้าของระบบ:

- merge PR
- deploy ขึ้น hosting หรือ production
- เพิ่ม service worker หรือ offline support
- ทำ native app หรือ package สำหรับ app store
- เปลี่ยน scope ไปแก้งาน C ที่ไม่เกี่ยวกับ D
- เปลี่ยนฐาน PR จาก `feat/v7-c-fast` ขณะที่ PR #13 ยังไม่ merge

## Architecture and Existing Implementation

- แอปเป็น Django และทุกหน้าหลักสืบทอดจาก `templates/base.html`
- Manifest ใช้ `TemplateView` ใน `config/urls.py` ไม่ใช้ไฟล์ static โดยตรง เพื่อกำหนด URL และ content type ชัดเจน
- `accounts/middleware.py` มี initial-password gate ดังนั้น route manifest ต้องอยู่ใน allowlist
- คู่มือติดตั้งถูกแยกเป็น partial เดียว แล้ว include ใน account menu ทั้ง desktop และ mobile เพื่อลดข้อความซ้ำ
- ไม่มี service worker โดยตั้งใจ เพราะโจทย์คือ installable web ที่ยังออนไลน์ ไม่ใช่ offline-first PWA
- แผนต้นฉบับ Work D อ่านได้จาก `git show c8c5236:docs/v7-plan.md` เพราะไฟล์นั้นไม่ได้อยู่ใน branch ปัจจุบัน

### Architecture Overview

เส้นทางหลักคือ browser โหลดทุกหน้าผ่าน Django base template ซึ่งชี้ไปยัง manifest route; manifest อ้างถึง static PNG icons ขณะที่ middleware อนุญาตให้โหลด manifest ก่อนผ่าน first-login password flow คู่มือติดตั้งเป็น template partial ที่ใช้ร่วมกันใน account menu ทั้งสอง layout และ CSS ควบคุมความสูง/การเลื่อนของ popover บนจอเล็ก

### Critical Files

- `config/urls.py`: public manifest endpoint และ content type
- `templates/base.html`: PWA discovery metadata และจุด include คู่มือ
- `templates/manifest.webmanifest`: install metadata กับ icon declarations
- `accounts/middleware.py`: password-gate allowlist
- `templates/includes/pwa_install_guide.html`: ข้อความที่ผู้ใช้เห็น
- `static/css/app.css`: responsive behavior ของคู่มือและ popover
- `config/tests_v7_d.py`: acceptance tests ของงาน D

## Work Already Completed

- สร้าง branch `feat/v7-d-pwa` จากหัว PR #13 (`origin/feat/v7-c-fast`)
- เพิ่ม manifest route และ metadata ใน base template
- เพิ่มไอคอน PNG 192x192 และ 512x512 พร้อมสคริปต์สร้างซ้ำ
- เพิ่มคู่มือติดตั้ง Android/Chrome และ iPhone/Safari อย่างละ 3 ขั้นตอน
- เพิ่มข้อความเตือนว่าต้องใช้อินเทอร์เน็ต
- เพิ่ม tests สำหรับ manifest, icons, base metadata, คู่มือติดตั้ง และ password-gate bypass
- ตรวจหน้าเว็บที่ 360px ด้วย browser automation แล้ว ไม่พบ horizontal overflow ที่ระดับหน้า
- คืนค่าผู้ใช้ demo และลบข้อมูลจองชั่วคราวที่ใช้ตรวจภาพแล้ว
- หยุด development server แล้ว ไม่มี process ที่ต้องรับช่วง

ผลตรวจล่าสุดก่อนส่งต่อ:

- Work D tests: `5 passed`
- Full regression: `177 passed, 2 warnings`
- `manage.py check`: no issues
- `makemigrations --check --dry-run`: no changes detected
- `git diff --check`: ผ่าน มีเพียงคำเตือน line ending ของ `templates/base.html`

### Files Modified

รายการไฟล์และเหตุผลของแต่ละการเปลี่ยนแปลงอยู่ในตาราง Authorized Changes ด้านบน ทั้งหมดเป็น uncommitted Work D และต้องอยู่ใน final diff เว้นแต่ Antigravity พบข้อผิดพลาดพร้อมอธิบายเหตุผลที่ปรับ

### Decisions Made

- เลือก installable web ที่ยังต้องออนไลน์ แทน native/offline app เพื่อให้ตรงความต้องการผู้ใช้
- เสิร์ฟ manifest ผ่าน Django route เพื่อควบคุม URL และ response content type
- ใช้ PNG 192/512 และ partial เดียวสำหรับคู่มือติดตั้งสองตำแหน่ง
- เลื่อน real-device install test เป็น owner test หากยังไม่มี HTTPS URL/อุปกรณ์จริง โดยต้องระบุสถานะตามจริง

### Assumptions Made

- PR #13 และ branch `feat/v7-c-fast` ยังอยู่จนกว่าจะเปิด PR งาน D
- ไม่มี requirement ใหม่ให้เว็บทำงาน offline
- การเลื่อนภายในตารางหรือ account popover เป็น behavior ที่ยอมรับได้ ตราบใดที่ทั้งหน้าไม่ล้นแนวนอน
- เจ้าของระบบจะเป็นผู้อนุมัติ merge/deploy และทำ device acceptance ที่ต้องใช้อุปกรณ์จริง

## Antigravity Execution Plan

1. เปิด repo `F:\ogn_ROOM` และยืนยันว่าอยู่ branch `feat/v7-d-pwa`
2. อ่าน `git status --short` และ `git diff` ทั้งหมดก่อนแก้ ห้ามทิ้ง working-tree changes ที่มีอยู่
3. อ่าน Work D จาก `git show c8c5236:docs/v7-plan.md` แล้วเทียบกับ acceptance criteria ด้านบน
4. ตรวจ implementation ทุกไฟล์ในตาราง Authorized Changes โดยเฉพาะ URL, content type, path ของ icons, include คู่มือสองตำแหน่ง และ middleware allowlist
5. ตรวจว่าไม่มี service worker registration, cache strategy หรือ offline claim ถูกเพิ่มมา
6. เปิดเว็บใน local development server และตรวจ manifest/icon ผ่าน browser dev tools หรือ HTTP response
7. ทำ Visual QA ใหม่ที่ viewport กว้าง 360px ตาม checklist ด้านล่าง แก้เฉพาะ regression ของงาน D
8. บันทึก screenshot ของสถานะสำคัญเป็นไฟล์ที่แนบหรือวางใน PR ได้ โดยไม่ commit ข้อมูลส่วนตัวหรือ secret
9. อัปเดต `docs/v7-notes.md` ด้วยผลตรวจจริง วันที่ และสถานะ Android/iPhone real-device test ห้ามอ้างว่าผ่านหากยังไม่ได้ทดสอบจริง
10. รัน Validation Commands ทั้งหมด ถ้ามี failure ให้แก้เฉพาะสาเหตุที่อยู่ใน scope งาน D และรันซ้ำ
11. ตรวจ diff สุดท้ายให้ไม่มีไฟล์ชั่วคราว ฐานข้อมูล local screenshot ที่มีข้อมูลอ่อนไหว หรือการเปลี่ยนแปลงนอก scope จากนั้น commit และ push branch `feat/v7-d-pwa`
12. เปิด stacked PR โดยตั้ง base เป็น `feat/v7-c-fast` และ head เป็น `feat/v7-d-pwa` ใส่ผลทดสอบกับภาพหลักฐานให้ครบ แล้วหยุดรอ Codex review ห้าม merge หรือ deploy

## Visual QA Checklist at 360px

ตรวจทั้งการแสดงผล การกดใช้งาน และ horizontal overflow:

- หน้าแรกและรายการห้องว่าง
- หน้าค้นหา/เลือกห้องเพื่อจอง
- ฟอร์มจอง: สถานะสรุป
- ฟอร์มจอง: สถานะเลือกวัน เวลา และแก้ไข
- รายละเอียดการจอง
- รายการจองของฉัน โดยอนุญาตให้ตาราง scroll ภายใน container ได้
- หน้ารออนุมัติ
- lodging portal
- keycard ด้านหน้า
- keycard ด้านหลัง
- check-in
- reports
- notifications
- login
- account menu ที่เปิดคู่มือติดตั้งและเลื่อนอ่านได้ครบ

ภาพขั้นต่ำที่ควรแนบ PR:

- account menu บน mobile ที่เห็นหัวข้อ Android และ iPhone
- หน้า 360px ที่มี layout ซับซ้อนอย่างน้อย 2 หน้า เช่น booking form และ reports
- manifest response หรือ Application/Manifest panel ที่แสดงชื่อ สี และ icons ถูกต้อง

## Validation Commands

ใช้ Python/runtime และ test command ตามรูปแบบของ repo ปัจจุบัน ผลที่ต้องรายงานอย่างน้อย:

```powershell
python manage.py test config.tests_v7_d
python manage.py test
python manage.py check
python manage.py makemigrations --check --dry-run
git diff --check
git status --short
```

ถ้า full tests ชน permission ของ Windows temp directory ให้กำหนด `--basetemp` ไปยังโฟลเดอร์ชั่วคราวที่เขียนได้ภายใน workspace แล้วรันใหม่ ต้องแยกให้ชัดว่าเป็นปัญหา environment ไม่ใช่ test failure

## PR Requirements

- Title แนะนำ: `feat(v7-d): เพิ่ม PWA install metadata และคู่มือติดตั้งเว็บ`
- Base: `feat/v7-c-fast`
- Head: `feat/v7-d-pwa`
- อธิบายชัดว่ายังเป็นเว็บ ใช้งานผ่าน browser ได้เหมือนเดิม และการติดตั้งเป็น optional
- ระบุว่าไม่มี service worker/offline/native app
- ใส่รายการไฟล์สำคัญและผล automated validation
- แนบ Visual QA screenshots
- ระบุ real-device Android/iPhone test ว่า `passed`, `failed` หรือ `pending owner test` ตามความจริง
- เชื่อมโยง PR #13 ว่าเป็นฐานของ stacked PR
- หลังเปิด PR ให้ส่ง URL/หมายเลข PR กลับมาให้ Codex ตรวจ

## Blockers and Open Questions

- การติดตั้งจริงบน Android/Chrome และ iPhone/Safari ต้องใช้เครื่องจริงหลังมี URL ที่เข้าถึงผ่าน HTTPS; ถ้ายังทำไม่ได้ให้คงสถานะ `pending owner test` ใน `docs/v7-notes.md`
- ยังไม่มีไฟล์ screenshot ถูกเก็บไว้ใน repo/PR แม้ Codex เคยตรวจภาพครบแล้ว Antigravity ต้องจับภาพใหม่เพื่อเป็นหลักฐาน
- ตัวชี้วัดการใช้งานหลังปล่อยจริงต้องรอข้อมูล production ไม่ใช่เงื่อนไขก่อนเปิด PR
- พบเรื่องนอก scope: ฟอร์มแก้ไขการจองจากงาน C แสดงวัน/เวลาได้ แต่ไม่มีปุ่ม time presets เพราะ view ไม่ส่ง `time_presets` context ห้ามแอบแก้ใน PR งาน D ให้รายงาน Codex แยกต่างหาก

## Potential Gotchas

- Working tree มีงาน D ที่ยังไม่ commit อยู่แล้ว ห้าม reset, checkout ทับ หรือลบไฟล์เหล่านี้
- เอกสาร `.claude/handoffs/2026-09-06-041201-v7-d-pwa-antigravity.md` ใช้ประสานงานเท่านั้น ไม่ต้องใส่ใน product commit/PR
- PR #13 ยังเปิดอยู่ จึงต้องเปิด PR แบบ stacked เทียบกับ `feat/v7-c-fast`; ถ้าเทียบกับ main diff จะปนงาน C
- Local database มี migrations ของงาน B/C ใช้สำหรับตรวจภาพแล้ว แต่ Work D ไม่มี migration ใหม่
- อย่าใส่ credentials, demo password, cookies, database file หรือข้อมูลผู้ใช้ลง commit/PR/screenshot
- `purpose: "any maskable"` ใช้กับ icons ปัจจุบัน ต้องตรวจว่า artwork มี safe zone เหมาะสมก่อนคงค่าไว้
- Account popover ใช้ `max-height` และ `overflow`; ตรวจว่าเมนูเดิมและปุ่มออกจากระบบยังเข้าถึงได้ที่ 360px

## Environment State

- Current branch: `feat/v7-d-pwa`
- Development server: stopped
- Browser automation tab: closed/reset
- Uncommitted changes: มีตามตาราง Authorized Changes
- No deployment has been performed
- No secret values are required in this handoff

## Definition of Done

ถือว่างานของ Antigravity เสร็จเมื่อ:

- acceptance criteria 12 ข้อผ่านหรือมีรายการ pending ที่ซื่อสัตย์และมีเหตุผล
- automated validation ผ่าน
- Visual QA 360px ผ่านพร้อมภาพหลักฐาน
- `docs/v7-notes.md` อัปเดตตามผลจริง
- diff ไม่มีงานนอก scope หรือข้อมูลอ่อนไหว
- commit และ push อยู่บน `feat/v7-d-pwa`
- stacked PR เปิดจาก `feat/v7-d-pwa` ไป `feat/v7-c-fast`
- ส่ง PR ให้ Codex ตรวจและหยุดรอ โดยยังไม่ merge/deploy

## Short Instruction to Paste into Antigravity

> รับช่วง Work D (PWA สำหรับเว็บ) ใน `F:\ogn_ROOM` branch `feat/v7-d-pwa` โดยอ่านและทำตาม handoff นี้ทั้งหมด รักษา working-tree changes ที่มีอยู่ ตรวจ/แก้เฉพาะ scope งาน D เก็บภาพ Visual QA 360px รัน tests และ checks ให้ครบ อัปเดต `docs/v7-notes.md` ตามผลจริง แล้ว commit, push และเปิด stacked PR ไปที่ `feat/v7-c-fast` หลังเปิด PR ให้หยุดและส่ง URL/หมายเลข PR กลับมาเพื่อให้ Codex ตรวจ ห้าม merge, deploy, เพิ่ม service worker/offline หรือนำเรื่องนอก scope งาน C มาปน
