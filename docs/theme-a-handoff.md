# Handoff: SIGROOM UX/UI ธีม A "สมุดทะเบียนห้อง" — รอบ 3 เป็นต้นไป

เขียน 2 ต.ค. 2569 สำหรับ agent ที่มารับงานต่อ อ่านไฟล์นี้ให้จบก่อนลงมือ

## 0. อ่านก่อนเริ่ม (ตามลำดับ)
1. `CLAUDE.md` กติกาที่ห้ามละเมิด ได้แก่ กันจองซ้อนที่ DB, กฎธุรกิจอยู่ใน services.py, ข้อความภาษาไทย, datalist rule 7, ต้องมี test
2. `docs/theme-a-ledger.md` สเปกธีมที่ผู้ใช้อนุมัติแล้ว (สี ฟอนต์ ชุดสถานะ ลายเซ็นภาพ)
3. `docs/mockups/sigroom-ledger-mockup.html` ร่างหน้าแรกและหน้าจองที่อนุมัติแล้ว
4. ไฟล์นี้

ผู้ใช้ทำงานคนเดียวและไม่ถนัดโค้ด ให้รายงานเป็นภาษาไทยง่าย ๆ ทุกครั้ง บอกว่า "แก้อะไร ทำไม เห็นผลที่ไหน" และบอกวิธีดูผลด้วยตาตัวเอง

## 1. สถานะปัจจุบัน
- worktree: `F:\ogn_ROOM\.claude\worktrees\ux-ui-performance-improvements-41f93e`
- branch: `claude/ux-theme-a` แตกจาก `origin/feat/lodging-v5-2` @ 71d7c33 (PR #77) ไม่ได้ track upstream **ยังไม่ push และยังไม่มี PR**
- commit ของงานนี้ (เรียงเก่าไปใหม่)
  | commit | เนื้อหา |
  |---|---|
  | cff29cd | ระยะ 0: splash `public/index.html`, static ผ่าน Firebase CDN (`STATIC_ROOT=public/static`), manifest hash + cache 1 ปี, หน้าแรกย้ายไป `/home/` (`/` ยังใช้ได้ = `calendar_root`), FullCalendar defer, gunicorn --preload, `deploy-sigroom.cmd` |
  | 567b0bc | ธีม A1: reskin ทั้งระบบ (ฟอนต์ Sarabun + Noto Serif Thai self-host, token กระดาษ/หมึก/ตรา), หน้าแรกใหม่ + ทะเบียนห้องวันนี้ แตะช่องว่างจองได้ (`bookings/board.py`) |
  | d463b1e | ธีม A2: จอง 3 ขั้นหน้าเดียว (ชิป + HTMX + คำแนะนำเวลา/วันอื่น + prefill ผู้รับผิดชอบ + ตราประทับครั้งเดียว + .ics), login/logout/reset เป็นแผ่นฟอร์มกระดาษ |
- pytest: **751 passed** ที่ d463b1e
- branch เก่า `claude/ux-ui-performance-improvements-41f93e` และ `backup/phase0-old-base` (ถ้ามี) อิงโค้ดเก่า 201 commit **ห้ามใช้ ทิ้งได้**

## 2. วิธีรัน (worktree ไม่มี .env)
```bash
uv sync
uv run --env-file F:/ogn_ROOM/.env pytest -q
uv run --env-file F:/ogn_ROOM/.env manage.py check
DJANGO_SECRET_KEY=x uv run --env-file F:/ogn_ROOM/.env manage.py collectstatic --noinput
```
- ห้ามคัดลอกหรือพิมพ์เนื้อหา `.env` ออกมา
- dev server ใช้ preview config ชื่อ `django-worktree` (port 8010) ใน `.claude/launch.json`
- **หลัง collectstatic ทุกครั้งต้อง restart preview server** เพราะ server cache manifest ไว้ ถ้าไม่ restart ไฟล์ใหม่จะได้ 500
- `.env` ตั้ง DEBUG=0 ทำให้ static ต้อง collect ก่อน ส่วน settings จะ fallback ไปใช้ storage แบบไม่มี hash เองเมื่อยังไม่มี `public/static/staticfiles.json`
- ผู้ใช้ทดสอบในเครื่อง: `theme_tester` (ผู้อนุมัติ + ผู้ดูแลห้อง B1-101) รหัสผ่านอยู่ใน `docs/.local-test-user.txt` (gitignored) ห้ามพิมพ์รหัสในแชต
- DB dev ถูก migrate ถึง bookings 0015 แล้ว มีการจองทดสอบของ theme_tester ห้อง B1-101 อยู่ 3 รายการ

## 3. งานที่เหลือ: รอบ 3 "เก็บงานให้เรียบทั้งระบบ"
ทำทีละข้อ ปิดแต่ละข้อด้วย pytest ผ่านและเปิดดูในเบราว์เซอร์ที่ 1280 กับ 375 (ห้ามมี scroll แนวนอน, touch target ≥44px) แล้ว commit แยกข้อ

| # | งาน | ไฟล์หลัก | เกณฑ์รับ | โมเดลแนะนำ |
|---|---|---|---|---|
| R3-1 | คิวอนุมัติเป็นแถวทะเบียน ไม่ใช่การ์ดซ้อนการ์ด: แถวละคำขอ (ห้อง · วันเวลา · ผู้ขอ · หน่วย · ธงข้อความ) ปุ่มอนุมัติ/ปฏิเสธในแถว รายละเอียดเป็น disclosure | `templates/approvals/queue.html`, `approvals/views.py` (เฉพาะ context การแสดงผล), `app.css` | ไม่มีกล่องในกล่อง, สถานะใช้ชุดเดียวกับสเปก, ปฏิเสธยังบังคับเหตุผล, เทส approvals ผ่าน | Sonnet |
| R3-2 | หน้า "การจองของฉัน" เป็นตารางทะเบียน แบ่ง กำลังจะถึง / ที่ผ่านมา / ยกเลิก ใช้ตราสถานะ เอา ← ↻ ออก | `templates/bookings/my_bookings.html`, `series_detail.html`, `online_teaching_book.html` | ไม่เหลือลูกศรตกแต่ง, มือถือเป็นรายการบรรทัด | Sonnet |
| R3-3 | รายงาน / การใช้งานห้อง / ผู้รักษาการ / งดใช้ห้อง / แจ้งเตือน: ตรวจทีละหน้าให้เข้าชุด (หัวตารางขีด ink 2px, ตัวเลขใช้ tabular-nums, ไม่มี card ซ้อน) | `templates/reports/dashboard.html`, `usage/list.html`, `approvals/delegation.html`, `resources/outage.html`, `notifications/list.html` | ภาพหน้าจอแต่ละหน้าดูเป็นระบบเดียวกับหน้าแรก | Sonnet |
| R3-4 | `accounts/first_password_change.html` ใช้ `auth-sheet` แบบเดียวกับหน้า login (ตอนนี้ยังเป็น `auth-card` เก่า) | template + css | ตรงกับ login | Haiku/Sonnet |
| R3-5 | หน้าที่พัก: `/lodging/about/` (hero ใหญ่, explorer 3D/isometric, gradient 28 จุดที่แค่เปลี่ยนสี), student portal, บัตรผ่าน keycard 3D flip, check-in → ลด gradient/เงา/การ์ดซ้อน ให้เป็นกระดาษ คงฟังก์ชันเดิมทุกอย่าง | `templates/lodging/*`, `static/css/lodging_*.css` | ไม่มี gradient ตกแต่ง, ภาษาไทยอ่านชัด, เทส lodging ผ่าน **ถามผู้ใช้ก่อนตัด explorer 3D หรือ keycard flip** | Opus (หน้าใหญ่ ต้องใช้วิจารณญาณ) |
| R3-6 | หน้าแรกบนมือถือ: แถบงาน 3 ช่องซ้อนเป็นกล่องสูง → ให้กระชับ (เช่น 2 แถว หรือแถวรายการ), ชิปหมวดห้องห่อ 3 แถว → ให้เลื่อนแนวนอนในกล่องตัวเอง | `templates/bookings/calendar.html`, `app.css` | ส่วนบนสุดของมือถือ 375×812 เห็นทั้งปุ่ม "จองห้อง" และเริ่มเห็นทะเบียน | Sonnet |
| R3-7 | ลบ CSS ที่ตายแล้วใน `app.css`: `booking-express-*`, `booking-review-*`, `booking-search-v2`, `booking-path-card` และ selector อื่นที่ grep ไม่เจอใน templates/JS/tests | `static/css/app.css` | grep ยืนยันทีละ selector ก่อนลบ, หน้าตาไม่เปลี่ยน | Haiku |
| R3-8 | ไอคอน PWA ยังเป็นสีมืด → ทำใหม่โทนกระดาษ (พื้น #F5F1E6, ตัว "S" serif สีหมึก หรือกรอบตรา) ด้วย `scripts/generate_pwa_icons.py` | `static/img/pwa-icon-*`, script | ไอคอนเข้ากับ theme_color #F5F1E6 | Sonnet |
| R3-9 | อัปเดต `.impeccable.md` ให้เป็นทิศทาง Ledger (ตอนนี้ยังบรรยาย HUD/cyan/IBM Plex) โดยอ้าง `docs/theme-a-ledger.md` | `.impeccable.md` | ไม่เหลือคำอธิบาย HUD | Haiku |
| R3-10 | ใต้ตราประทับในหน้ารายละเอียดยังมีกล่อง "อนุมัติแล้ว" ซ้ำ → รวมเป็นที่เดียว (ต้องแก้เทสที่ผูกกล่องนี้อย่างตั้งใจ) | `templates/bookings/booking_detail.html` + tests | สถานะแสดงครั้งเดียว | Sonnet |

ลำดับแนะนำ: R3-7 → R3-9 → R3-4 → R3-10 → R3-1 → R3-2 → R3-3 → R3-6 → R3-8 → R3-5 (R3-5 ใหญ่และต้องถามผู้ใช้ก่อน)

### เรื่องที่รอผู้ใช้ตอบ (ห้ามเดาเอง)
- คำแนะนำ "วันถัดไปที่ว่าง" และชิปวันข้ามเสาร์-อาทิตย์ (agent ตัดสินเองตอน A2) **รอผู้ใช้ยืนยัน** ถ้าหลักสูตรใช้วันหยุดด้วยต้องเปลี่ยนใน `search_date_choices` / `next_available_date` (`bookings/services.py`)
- R3-5: จะเก็บ explorer 3D และ keycard flip ไว้หรือไม่

## 4. หลังรอบ 3: ส่งขึ้นเว็บจริง (ต้องได้คำยืนยันจากผู้ใช้ทุกขั้น)
1. `git fetch` แล้วเช็กว่า `origin/feat/lodging-v5-2` มี commit ใหม่หรือไม่ ถ้ามีให้ merge เข้า branch นี้แล้วแก้ conflict (คำสั่ง reset/merge บางคำสั่งถูก classifier บล็อก ให้ขอผู้ใช้หรือให้ผู้ใช้รันเอง) แล้วรัน pytest ให้ผ่าน
2. push branch แล้วเปิด PR เข้า `feat/lodging-v5-2` (มี `.github/workflows/pr-safety-gate.yml`) โดยเขียนคำอธิบายเป็นภาษาไทยและแนบภาพหน้าจอ
3. ผู้ใช้ merge เอง
4. ผู้ใช้ดับเบิลคลิก `deploy-sigroom.cmd` แล้วพิมพ์ `DEPLOY` (ครั้งแรกต้อง `firebase login`) สคริปต์จะทำ preflight → Cloud Build (build, migrate job, deploy) → collectstatic → `firebase deploy --only hosting:sigroom` → smoke check `https://sigroom.web.app/home/`
   - **ห้าม agent รัน deploy เอง**
   - ห้ามเปิด trigger `auto-deploy-sigroom` (ตั้งใจปิดไว้ ดู `docs/production-deploy-guard.md`)
   - **ต้องเตือนผู้ใช้ก่อน deploy:** หน้าแรกย้ายไป `/home/` แล้ว `/` บน Firebase จึงกลายเป็นหน้า splash ทำให้คนที่บันทึก bookmark `/` ไว้จะเห็น splash แวบหนึ่งก่อนเข้าหน้าแรก (ถือว่าปกติ)

## 5. ข้อเท็จจริงที่ตัดสินแล้ว (อย่าถามซ้ำ)
- ธีม A เป็นโหมดสว่างอย่างเดียว ยังไม่ทำโหมดมืด
- เลขไทยใช้เฉพาะวันที่เต็มและหัวกระดาษ ส่วนเวลา จำนวน และรหัสห้องใช้เลขอารบิก
- Cloud Run **ไม่เปิดเครื่องค้าง** (min-instances=0) เพราะมีคนใช้นาน ๆ ครั้งและช่วงเปิดหลักสูตร ส่วน startup-cpu-boost เปิดอยู่แล้ว
- deploy แบบปุ่มเดียว (`deploy-sigroom.cmd`) ไม่ใช่ auto-deploy ทุก push
- หน้าเข้าสู่ระบบเอาภาพทหารออกแล้ว
- เลือกโมเดลตามความยากของงาน: Haiku สำหรับงาน mechanical, Sonnet สำหรับงานตามสเปก, Opus สำหรับงานที่ต้องใช้วิจารณญาณหรือกระทบกฎการจอง และระบุเหตุผลการเลือกเมื่อรายงาน

## 6. ข้อสังเกตที่เจอระหว่างทาง (นอกขอบเขต แจ้งผู้ใช้ได้)
- Cloud Run service มี `DB_PASSWORD`, `DJANGO_SECRET_KEY` และ `EMAIL_HOST_PASSWORD` เป็น env var ธรรมดา ควรย้ายไป Secret Manager ก่อนเปิดใช้กว้าง (SRS หมวด 10)
- `run_jobs` (งานทุก 5 นาที เช่น SLA และ no-show) ยังไม่เห็นว่ามีตัวเรียกบน Cloud ต้องเช็กกับผู้ใช้ว่าตั้ง Cloud Scheduler หรือ Cloud Run Job ไว้หรือยัง เพราะ Cloud Scheduler API ของโปรเจกต์ EMSO ปิดอยู่ ส่วนของ SIGROOM ยังไม่ได้ตรวจ
- gcloud ในเครื่องผู้ใช้มี active config = `default` (โปรเจกต์ signal-nco-ew ของแอป EMSO) คำสั่งของ SIGROOM ต้องใส่ `--project sixth-storm-439008-u2` หรือ `--configuration=sigroom` เสมอ
