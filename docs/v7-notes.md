# บันทึกตรวจรับ V7

อัปเดตล่าสุด: 6 กันยายน 2569

## สรุปการ Deploy ขึ้น Production (V7 งาน B–D)

- **Integration Pull Request:** [#12](https://github.com/saisansan11/sigroom/pull/12) (Merged)
- **Production Target Branch:** `feat/lodging-v5-2`
- **Merge Commit SHA:** `aee9d1e23bdd298b9d6feb4d8871abdcc1a4eb8d`
- **Cloud SQL Pre-deploy Backup ID:** `1788648442850` (Status: SUCCESSFUL, เวลา `2026-09-05T22:47:22.850Z`)
- **Cloud Build ID:** `a5f3fa71-bb81-4055-b509-2b6bb8c41168` (Trigger: `auto-deploy-sigroom`, Status: SUCCESS)
- **Cloud Run Migration Job:** `sigroom-migrate` (Execution: `sigroom-migrate-pg5p2`, Status: EXECUTION_SUCCEEDED)
- **Applied Migrations (4 รายการ):**
  1. `resources.0005_alter_blackout_room_category_and_more`
  2. `accounts.0003_user_favorite_resources`
  3. `bookings.0010_booking_online_meeting_url`
  4. `bookings.0011_alter_referencevalue_field`
- **Cloud Run Active Revision:** `sigroom-00013-z2q` (Traffic: 100%)
- **Previous Revision (Rollback target):** `sigroom-00012-hpq`
- **Image Artifact:** `asia-southeast3-docker.pkg.dev/sixth-storm-439008-u2/sigroom-repo/sigroom:aee9d1e23bdd298b9d6feb4d8871abdcc1a4eb8d`
- **Visual Evidence Prerelease:** [v7-bcd-prod-qa](https://github.com/saisansan11/sigroom/releases/tag/v7-bcd-prod-qa)

---

## ผลการทดสอบ Production Smoke Test

| Endpoint / เส้นทาง | วิธีตรวจสอบ | ผลลัพธ์ที่คาดหวัง | ผลการตรวจจริง | สถานะ |
|---|---|---|---|---|
| `https://sixth-storm-439008-u2.web.app/` | HTTP GET | 200 OK, Guest Home | 200 OK, หน้าแรกโหลดสมบูรณ์ | ผ่าน |
| `https://sigroom.web.app/` | HTTP GET | 200 OK, Canonical Site | 200 OK, Firebase Rewrite สมบูรณ์ | ผ่าน |
| `/accounts/login/` | HTTP GET | 200 OK, ฟอร์มล็อกอิน | 200 OK | ผ่าน |
| `/admin/` | HTTP GET | 302 Redirect ไป `/admin/login/` | 302 Redirect | ผ่าน |
| `/manifest.webmanifest` | HTTP GET | 200 OK, `application/manifest+json` | 200 OK, `application/manifest+json` | ผ่าน |
| `/static/img/pwa-icon-192.png` | HTTP GET | 200 OK, `image/png` | 200 OK (PNG 192x192) | ผ่าน |
| `/static/img/pwa-icon-512.png` | HTTP GET | 200 OK, `image/png` | 200 OK (PNG 512x512) | ผ่าน |
| `/lodging/` | HTTP GET | 200 OK, Cohort Portal | 200 OK | ผ่าน |
| Authenticated Flows (จอง/ห้องโปรด/อนุมัติ) | Web Browser | ฟังก์ชันสำหรับผู้ใช้ล็อกอิน | pending owner authenticated smoke (ไม่ bypass/reset รหัสผ่านตาม Hard Stop Rules) | Pending |

---

## สรุปบันทึกการทำงาน (Cloud Run Log Summary)

- **Application Errors / 5xx:** 0 รายการ (ไม่มี 5xx, schema error หรือ migration error บน revision `sigroom-00013-z2q`)
- **สถานะคำขอและข้อความแจ้งเตือน:** คำขอใน Production Smoke Test ที่ระบุไว้ทั้งหมดผ่านด้วย 200 OK หรือ 302 Redirect; นอกเหนือจากนั้นพบ `GET /favicon.ico` ตอบ 404 จำนวน 1 ครั้ง (WARNING) ซึ่งไม่กระทบการทำงานของระบบ

---

## ตรวจสอบ Web App Manifest บน Production

- **URL:** `https://sixth-storm-439008-u2.web.app/manifest.webmanifest`
- **Content-Type:** `application/manifest+json`
- **JSON Metadata:**
  - `name`: "SIGROOM — ระบบจองห้อง รร.ส.สส."
  - `short_name`: "SIGROOM"
  - `start_url`: "/"
  - `scope`: "/"
  - `display`: "standalone"
  - `background_color`: "#0b1721"
  - `theme_color`: "#102433"
  - `icons`: 192x192 และ 512x512 (image/png, any maskable)

---

## บัญชีข้อมูลห้องหมวดออนไลน์ (Master Data Inventory)

- **จำนวนห้องหมวด `online` ปัจจุบันบน Production:** 0 ห้อง
- **การแสดงผลหน้าแรก:** การ์ด "ห้องสอนออนไลน์" (`#now-online`) ถูกซ่อนอัตโนมัติตามเงื่อนไข `Resource.objects.filter(room_category='online').exists()`
- **การคงสภาพ Master Data:** ไม่มีการรัน `seed_pilot` และไม่มีการสร้างห้องทดสอบบน Production
- **สถานะ:** `pending owner confirmation` รอเจ้าของระบบยืนยันจำนวนและรหัสห้องจริง (2 ห้องตาม rev.4 หรือ 3 ห้องตาม seed)

---

## งาน D — PWA และหน้าจอมือถือ 360px

สภาพแวดล้อมตรวจ: Django development server ในเครื่อง, Chrome DevTools Protocol (CDP) mobile viewport 360×800 px

เกณฑ์: หน้าเว็บต้องไม่กว้างเกิน viewport (`document.documentElement.scrollWidth <= window.innerWidth`)
และองค์ประกอบหลักต้องอ่าน/กดได้จากภาพหน้าจอ

| หน้า / สถานะ | scrollWidth | ผล |
|---|---:|---|
| หน้าแรกใหม่ (งาน A) | 360 px | ผ่าน |
| ค้นหาห้องว่าง | 360 px | ผ่าน |
| ฟอร์มจอง — โหมดสรุป | 360 px | ผ่าน |
| ฟอร์มจอง — โหมดวันเวลา | 360 px | ผ่าน |
| รายละเอียดการจอง | 360 px | ผ่าน |
| การจองของฉัน | 360 px | ผ่าน — ตารางเลื่อนภายในกรอบได้ |
| หน้ารออนุมัติ | 360 px | ผ่าน |
| portal เลือกเตียง | 360 px | ผ่าน |
| key card ด้านหน้า | 360 px | ผ่าน |
| key card ด้านหลัง (QR) | 360 px | ผ่าน — พลิกการ์ดแสดง QR code ถูกต้อง |
| หน้าเช็คอิน | 360 px | ผ่าน |
| หน้ารายงาน | 360 px | ผ่าน |
| หน้าแจ้งเตือน | 360 px | ผ่าน |
| login | 360 px | ผ่าน |
| account menu (คู่มือติดตั้ง) | 360 px | ผ่าน — แสดงคำแนะนำ 3 ขั้นตอน Android/iPhone |

หมายเหตุ: ตรวจสอบด้วย headless browser / CDP viewport 360×800 px โดยจำลอง session ผู้ใช้ทดสอบและล้าง session ชั่วคราวออกทั้งหมดหลังทดสอบเสร็จสิ้น ไม่มีการสร้างข้อมูลจองหรือเช็คอินค้างไว้ในระบบ

---

## ตรวจติดตั้งด้วยเครื่องจริง (Device Acceptance)

ขั้นนี้ต้องทำบนเว็บไซต์ HTTPS หลัง deploy งาน B–D แล้ว

| อุปกรณ์ | รุ่น / OS | ติดตั้งจากหน้าจอโฮม | เปิดแบบไม่มีแถบ URL | ผู้ตรวจ / วันที่ | ผล |
|---|---|---|---|---|---|
| Android | รอระบุหลัง deploy | รอทดสอบบน HTTPS | รอทดสอบบน HTTPS | เจ้าของระบบ | pending owner test |
| iPhone | รอระบุหลัง deploy | รอทดสอบบน HTTPS | รอทดสอบบน HTTPS | เจ้าของระบบ | pending owner test |

---

## ตัวชี้วัดผู้ใช้ใหม่ (3-User Acceptance Metrics)

เริ่มจับเวลาหลัง login สำเร็จและบัญชีมีข้อมูลครบ การกรอกข้อความนับรวมในเวลา แต่ไม่นับเป็นคลิก

| ผู้ทดลอง | ประเภทห้อง | จำนวนคลิก | เวลา | ผล |
|---|---|---:|---:|---|
| คนที่ 1 | รอกรอก | — | — | pending owner test |
| คนที่ 2 | รอกรอก | — | — | pending owner test |
| คนที่ 3 | รอกรอก | — | — | pending owner test |

---

## ประเด็นที่รับทราบ (Known Issues)

- **Time Presets ในหน้าแก้ไขการจอง (Booking Edit):**
  - ในโหมดร่าง (Draft edit) ฟอร์มยังคงมีช่องวันและเวลาให้แก้ไข แต่ปุ่มช่วงเวลาสำเร็จรูป (presets) จะไม่แสดงเนื่องจากวิว `booking_edit` ไม่ได้ส่ง `time_presets` เข้าไปใน template context
  - หลังส่งคำขอ (Post-submit) ฟิลด์วันและเวลาจะถูกล็อกตามนโยบาย `POST_SUBMIT_EDITABLE_FIELDS` เพื่อป้องกันการจองทับซ้อน
  - สำหรับการจองที่ได้รับอนุมัติแล้วและต้องการปรับเปลี่ยนเวลา ให้ใช้กระบวนการยื่นคำขอแก้ไข (Amendment) ตามขั้นตอน ไม่ใช่การยกเลิกแล้วจองใหม่ (Rebook)
