# SIGROOM — Self-Service Password Reset Runbook

## เป้าหมาย

ให้ผู้ใช้ที่ลืมรหัสผ่านตั้งรหัสใหม่ด้วยตนเองผ่านอีเมลหน่วย `@signalschool.ac.th` โดยไม่ต้องให้ผู้ดูแลระบบทราบหรือส่งต่อรหัสผ่านชั่วคราว

## UX

1. หน้า `/accounts/login/` มีลิงก์ **ลืมรหัสผ่าน?**
2. ผู้ใช้กรอกอีเมลหน่วยที่ผูกกับบัญชี
3. ระบบตอบข้อความเดียวกันเสมอว่า หากอีเมลตรงกับบัญชีที่เปิดใช้งานจะส่งลิงก์ให้ เพื่อป้องกัน account enumeration
4. ผู้ใช้เปิดลิงก์ใช้ครั้งเดียวจากอีเมลและตั้งรหัสใหม่ตาม password policy ของ SIGROOM
5. เมื่อตั้งสำเร็จ token เดิมใช้ซ้ำไม่ได้ และผู้ใช้กลับไปเข้าสู่ระบบด้วยรหัสใหม่

## Security contract

- ใช้ Django password reset token generator; ไม่สร้าง token format เอง
- `PASSWORD_RESET_TIMEOUT` ค่าเริ่มต้น `3600` วินาที
- ส่งอีเมลเฉพาะบัญชี active + usable password ตามพฤติกรรม `PasswordResetForm` ของ Django
- แบบฟอร์มรับเฉพาะโดเมน `ALLOWED_EMAIL_DOMAIN`
- URL เก่าของ `django.contrib.auth.urls` ถูก shadow ด้วย view ชุดเดียวกัน เพื่อไม่ให้ bypass domain guard หรือ audit
- รหัสใหม่ใช้ `AUTH_PASSWORD_VALIDATORS` ชุดเดียวกับ login/initial-password flow
- การบันทึกรหัสใหม่ + `must_change_password=False` + audit อยู่ใน database transaction เดียวกัน
- Audit action: `password_reset_self_service`; ไม่เก็บ plaintext password, password hash หรือ reset token
- Production ห้ามใช้ `django.core.mail.backends.console.EmailBackend` เพราะ reset link/token จะเข้า application logs

## Email configuration

ค่าทั้งหมดอ่านจาก environment; ห้าม commit credential:

```text
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=<SMTP host>
EMAIL_PORT=587
EMAIL_HOST_USER=<SMTP username ถ้ามี>
EMAIL_HOST_PASSWORD=<secret>
EMAIL_USE_TLS=1
EMAIL_USE_SSL=0
EMAIL_TIMEOUT=10
DEFAULT_FROM_EMAIL=SIGROOM <noreply@signalschool.ac.th>
PASSWORD_RESET_TIMEOUT=3600
```

เลือก `EMAIL_USE_TLS=1` หรือ `EMAIL_USE_SSL=1` อย่างใดอย่างหนึ่งเท่านั้นตามผู้ให้บริการ SMTP

### Production Cloud Run

- เก็บ `EMAIL_HOST_PASSWORD` ใน Secret Manager และ map เป็น environment variable ของ service `sigroom`
- ค่า non-secret เช่น host/port/from address ใช้ Cloud Run environment variables ได้
- service account ต้องมีสิทธิ์อ่านเฉพาะ secret ที่จำเป็น
- ก่อนเปิดให้ผู้ใช้จริง ให้ส่ง test reset ไปยังบัญชีทดสอบ `@signalschool.ac.th` และตรวจว่า From, link host, TLS และ delivery ถูกต้อง
- ห้ามเปิด Production deploy หาก SMTP provider/credential ยังไม่พร้อม

## QA ก่อน deploy

```powershell
pytest accounts/tests_password_reset_self_service.py config/tests.py -q
python manage.py check
python manage.py makemigrations --check --dry-run
```

จากนั้นรัน full regression / security / accessibility gate ตาม CI ของ repository

## Rollback

ตัว feature ไม่มี schema migration การ rollback code ทำได้ด้วย revision/image ก่อนหน้า ส่วน SMTP secret/config เป็น infra แยกต่างหาก ให้ถอน mapping จาก Cloud Run เมื่อ rollback และคง secret ไว้เฉพาะช่วงตรวจสอบที่จำเป็นตามนโยบายหน่วย
