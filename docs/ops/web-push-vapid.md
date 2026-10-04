# Web Push / VAPID สำหรับ SIGROOM

เอกสารนี้ใช้หลัง PR-5 ผ่าน QA และ deploy เว็บแล้วเท่านั้น ฟีเจอร์ push จะปิดเองและ URL ที่เกี่ยวข้องตอบ 404 เมื่อค่า VAPID ไม่ครบทั้ง 3 ค่า

## ค่าที่ระบบใช้

- `WEBPUSH_VAPID_PUBLIC_KEY` — public application server key แบบ base64url ใช้ฝั่ง browser
- `WEBPUSH_VAPID_PRIVATE_KEY` — private key แบบ base64url (RAW 32 ไบต์หรือ DER ตามที่ `py_vapid` รองรับ) ต้องเก็บเป็น secret
- `WEBPUSH_VAPID_SUBJECT` — ช่องทางติดต่อผู้ดูแล เช่น `mailto:ผู้ดูแล@signalschool.ac.th`

ห้าม commit private key, subscription endpoint, `p256dh` หรือ `auth` ลง Git/เอกสาร/log

## 1. สร้าง key pair บนเครื่องผู้ดูแล

ติดตั้ง dependencies ของ repo แล้วใช้เครื่องมือจาก `py-vapid` ใน environment เดียวกับแอป:

```powershell
uv run vapid --gen
uv run vapid --applicationServerKey
```

เก็บไฟล์ private key ที่สร้างไว้ในที่ปลอดภัยชั่วคราวเพื่อแปลง/นำเข้า Secret Manager แล้วลบทิ้งเมื่อยืนยันเสร็จ อย่าส่ง key ผ่านแชทหรืออีเมล

ตรวจรูปแบบที่ติดตั้งจริงได้ด้วย:

```powershell
uv run vapid --help
```

## 2. ตั้ง production

เป้าหมาย production ปัจจุบัน:

- Project: `sixth-storm-439008-u2`
- Region: `asia-southeast3`
- Cloud Run service: `sigroom`

ให้เก็บ `WEBPUSH_VAPID_PRIVATE_KEY` ใน Google Secret Manager แล้วอ้าง secret จาก Cloud Run service ส่วน `WEBPUSH_VAPID_PUBLIC_KEY` และ `WEBPUSH_VAPID_SUBJECT` เป็น env ปกติได้

ก่อน deploy ต้องตรวจว่า:

- private key ไม่ปรากฏใน `gcloud run services describe` แบบค่า plaintext
- `WEBPUSH_VAPID_SUBJECT` เป็นช่องทางติดต่อผู้ดูแลจริง ไม่ใช่อีเมลของผู้รับแจ้งเตือน
- เว็บใช้ HTTPS และ `PUBLIC_BASE_URL=https://sigroom.web.app`

## 3. หลังอัปเดต Cloud Run service

Cloud Run Job `sigroom-run-jobs` ต้องใช้ runtime config เดียวกับเว็บ เพราะ reminder job เป็นผู้เรียก `send_push()` ด้วย ให้ทำขั้น “อ่าน revision 100% แล้ว replace Job” ใน `docs/ops/run-jobs-cloud.md` ใหม่ทุกครั้งที่ image/env/secret ของเว็บเปลี่ยน

ห้ามสร้าง Scheduler ใหม่ชื่ออื่น ตัวเดิมคือ:

- Job: `sigroom-run-jobs`
- Scheduler: `sigroom-run-jobs-every-five-minutes`
- Schedule: `*/5 * * * *`
- Time zone: `Asia/Bangkok`

## 4. Acceptance หลังเปิด VAPID

1. Login บัญชีครูบน Chrome/Android หรือ Safari iOS ที่ติดตั้ง SIGROOM บน Home Screen
2. หน้า “การแจ้งเตือน” หรือ “จองห้องสอนออนไลน์” ต้องแสดงปุ่ม `เปิดแจ้งเตือนบนเครื่องนี้`
3. Permission ต้องถูกขอหลังผู้ใช้กดเท่านั้น
4. เปิดแล้ว refresh หน้าเดิม สถานะต้องยังเป็น “เปิดแล้ว”
5. Logout/login ด้วยบัญชีอื่นบน browser เดิม ต้องล้าง browser subscription ของบัญชีเดิมก่อน และห้ามรับ push ของเจ้าของเดิม
6. ปิดแจ้งเตือนแล้ว browser subscription ต้องถูกยกเลิกก่อนจึงลบทะเบียน server
7. สร้าง booking QA ที่เข้า reminder window แล้วรัน Job 1 ครั้ง: กระดิ่งและ push ต้องชี้ไป path ภายใน SIGROOM เท่านั้น ไม่มี query/fragment/external URL
8. รัน Job ซ้ำใน reminder window เดิม ต้องไม่สร้าง notification/push รอบเดียวกันซ้ำ เพราะฐานข้อมูลกัน `(booking, user, kind)`

## 5. Rollback

ปิด push โดยเอาค่า VAPID ค่าใดค่าหนึ่งออกจาก service แล้ว deploy revision ใหม่ จากนั้น replace Cloud Run Job ให้ตาม revision นั้น ฟีเจอร์ push จะปิด แต่กระดิ่งในเว็บและอีเมล reminder ยังทำงานตามเดิม

ถ้าต้องหยุด scheduled reminders ทั้งหมดชั่วคราว ให้ pause Scheduler ตาม `docs/ops/run-jobs-cloud.md` แทนการลบ Job หรือฐานข้อมูล subscription
