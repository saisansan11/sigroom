# PR-D: เข้าสู่ระบบด้วย Google (บัญชี @signalschool.ac.th)

เขียน 3 ต.ค. 2569 · ผู้ทำ: Codex · ผู้ตรวจ: Claude
ต่อยอดจาก PR-C (stacked ตาม `docs/plans/2026-10-03-codex-runbook.md`)

**ผู้ใช้อนุมัติแล้ว (3 ต.ค. 2569):** เพิ่มไลบรารี `django-allauth` เพื่อทำ Google login ถือเป็นการเปลี่ยน stack ตาม CLAUDE.md ที่ผู้ใช้อนุญาตแล้ว
- ให้เพิ่มบรรทัดในหัวข้อ "Stack" ของ `CLAUDE.md`:
  `- เข้าสู่ระบบด้วย Google: django-allauth (เฉพาะ provider Google, ไม่เปิดสมัครเอง) — ผู้ใช้อนุมัติ 3 ต.ค. 2569`

ข้อเท็จจริงจากโค้ดปัจจุบัน:
- ระบบ**ไม่เคยมี** Google login มาก่อน
- login ทำผ่าน `accounts.views.ThrottledLoginView` + ตัวกันเดารหัส
- PR-A (A6) ทำให้กรอกอีเมลได้แล้ว

## 0. หลักความปลอดภัย (ห้ามละเมิด — SRS หมวด 10)
1. **ไม่สร้างบัญชีใหม่จาก Google** เข้าได้เฉพาะผู้ใช้ที่มีอยู่ในระบบแล้วและ `is_active=True`
2. จับคู่บัญชีด้วย**อีเมลที่ Google ยืนยันแล้วเท่านั้น** ต้องผ่านทุกข้อ:
   - `email_verified == True`
   - อีเมลลงท้าย `@{ALLOWED_EMAIL_DOMAIN}`
   - claim `hd == ALLOWED_EMAIL_DOMAIN`
3. ห้ามเชื่อค่าจาก query string หรือ header ที่ผู้ใช้ปลอมได้ ข้อมูลตัวตนมาจาก ID token / userinfo ที่ allauth ตรวจลายเซ็นแล้วเท่านั้น
4. เริ่ม flow ด้วย **POST + CSRF** เท่านั้น (`SOCIALACCOUNT_LOGIN_ON_GET = False`)
5. ไม่เก็บ access token ถ้าไม่จำเป็น (`SOCIALACCOUNT_STORE_TOKENS = False`)
6. รหัสผ่านเดิมยังใช้ได้ Google เป็นทางเลือกเพิ่ม
7. secret อยู่ใน env เท่านั้น (`.env` / Secret Manager) ห้ามอยู่ในโค้ด และห้ามเก็บใน DB ผ่าน `SocialApp`
8. ไม่มี client id → ปุ่มไม่แสดง และ URL ของ Google ตอบ 404 ระบบต้องทำงานได้ครบโดยไม่มี Google

## 1. ติดตั้งและตั้งค่า
- `uv add "django-allauth[socialaccount]>=65,<66"` (ระบุเวอร์ชันที่ใช้จริงใน PR)
- `INSTALLED_APPS`: เพิ่ม `allauth`, `allauth.account`, `allauth.socialaccount`, `allauth.socialaccount.providers.google`
- `MIDDLEWARE`: เพิ่ม `allauth.account.middleware.AccountMiddleware`
- `AUTHENTICATION_BACKENDS`: `accounts.backends.UsernameOrEmailBackend` (จาก PR-A) + `allauth.account.auth_backends.AuthenticationBackend`
  - ตรวจว่า backend ของ allauth ไม่ทำให้ login ด้วยรหัสผ่านข้ามตัวกันเดารหัส
  - ถ้าข้าม ให้ใช้เฉพาะส่วน social และอธิบายใน PR
- Settings ที่ต้องมี (อ่านจาก env):
  ```python
  GOOGLE_OAUTH_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
  GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
  GOOGLE_LOGIN_ENABLED = bool(GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET)
  SOCIALACCOUNT_PROVIDERS = {"google": {
      "APP": {"client_id": GOOGLE_OAUTH_CLIENT_ID, "secret": GOOGLE_OAUTH_CLIENT_SECRET},
      "SCOPE": ["openid", "email", "profile"],
      "AUTH_PARAMS": {"hd": ALLOWED_EMAIL_DOMAIN, "prompt": "select_account"},
      "OAUTH_PKCE_ENABLED": True,
  }}
  SOCIALACCOUNT_LOGIN_ON_GET = False
  SOCIALACCOUNT_AUTO_SIGNUP = False
  SOCIALACCOUNT_STORE_TOKENS = False
  SOCIALACCOUNT_ADAPTER = "accounts.social.SchoolGoogleAdapter"
  ACCOUNT_ADAPTER = "accounts.social.NoSignupAccountAdapter"
  ```
- `.env.example`: เพิ่ม 2 ตัวแปรพร้อมคำอธิบายภาษาไทยว่าเอามาจากไหน
- URL: `path("auth/", include("allauth.urls"))` ใน `config/urls.py`
  - **ห้ามให้ทับ `/accounts/`** ที่มีอยู่
  - ปิดหน้าที่ไม่ใช้ของ allauth (signup, login, password ของ allauth): ให้ตอบ 404 หรือ redirect ไปหน้า login เดิม
  - เปิดเฉพาะ `auth/google/login/`, `auth/google/login/callback/` และหน้าแสดง error ของ social

## 2. Adapter (`accounts/social.py`) — กฎทั้งหมดอยู่ที่นี่
```python
class NoSignupAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request): return False

class SchoolGoogleAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request, sociallogin): return False
    def pre_social_login(self, request, sociallogin): ...
```
`pre_social_login` ทำตามลำดับ:
1. อ่าน `email`, `email_verified`, `hd` จาก `sociallogin.account.extra_data`
2. ไม่ผ่านกฎข้อ 0.2 → `raise ImmediateHttpResponse(redirect("login") + messages.error(...))`
   ข้อความกลาง: "บัญชี Google นี้ใช้เข้า SIGROOM ไม่ได้ ใช้บัญชี @signalschool.ac.th ที่ลงทะเบียนแล้ว"
3. หา `User` ด้วย `email__iexact` และ `is_active=True`
   - ไม่พบ → ข้อความ "บัญชีนี้ยังไม่ได้ลงทะเบียนใน SIGROOM ติดต่อผู้ดูแลระบบ" + redirect login
4. ถ้า `sociallogin` ยังไม่ผูกกับใคร → `sociallogin.connect(request, user)`
   - ถ้าผูกกับคนอื่นแล้ว (uid เดิมแต่อีเมลเปลี่ยน) → ปฏิเสธ
5. บันทึก audit:
   - สำเร็จ: `login_google` (เก็บอีเมลกับ uid ที่ปิดบางส่วน ห้ามเก็บ token)
   - ปฏิเสธ: `login_google_rejected` พร้อมเหตุผลแบบรหัส เช่น `domain`, `unverified`, `not_registered`, `inactive`, `uid_mismatch`

ตรวจว่าระบบบันทึกประวัติ login เดิม (`accounts/tests_login_ledger.py`) ใช้ signal `user_logged_in` หรือไม่
- ถ้าใช่: login ด้วย Google ต้องถูกบันทึกเหมือนกัน
- ถ้าไม่ใช่: ให้เรียกตัวบันทึกเดียวกัน

`must_change_password`: คงพฤติกรรม middleware เดิม (ผู้ใช้ใหม่ยังต้องตั้งรหัสครั้งแรก) แล้วเขียนไว้ในข้อสงสัยให้ผู้ใช้ตัดสินใจภายหลัง

## 3. URL ปลายทาง (callback) หลัง Firebase Hosting
- callback ต้องเป็น `PUBLIC_BASE_URL + "/auth/google/login/callback/"` เสมอ (ใช้ค่า `PUBLIC_BASE_URL` แบบเดียวกับ `get_canonical_public_url`) ห้ามสร้างจาก Host header
- หา hook ของ allauth เวอร์ชันที่ติดตั้งสำหรับกำหนด absolute URI (เช่น `build_absolute_uri` ใน adapter) แล้ว override
  - **มี test ยืนยันว่า `redirect_uri` ที่ส่งไป Google ใช้ `PUBLIC_BASE_URL`** แม้ request มี Host / X-Forwarded-Host อื่น
- cookie: production ใช้ `__session` และ `CSRF_USE_SESSIONS` อยู่แล้ว (Firebase ส่งต่อแค่ cookie ชื่อนี้) ห้ามให้ allauth พึ่ง cookie อื่น
- เครื่องพัฒนาใช้ `SESSION_COOKIE_SAMESITE="Strict"` ซึ่งทำให้ callback จาก Google ไม่ได้ส่ง session กลับมา
  - **ห้ามแก้ค่า production**
  - ให้เขียนวิธีทดสอบในเครื่องไว้ใน PR (ตั้ง env ให้เป็น Lax ชั่วคราว)

## 4. หน้า login
- `ThrottledLoginView.get_context_data` ส่ง `google_login_enabled = settings.GOOGLE_LOGIN_ENABLED`
- template (B9) แสดง "หรือ" + ปุ่ม Google แบบมาตรฐาน เป็น `<form method="post" action="{% provider_login_url 'google' %}">` + csrf + ส่ง `next` ต่อถ้ามี
- `next` ต้องผ่าน `url_has_allowed_host_and_scheme` แบบเดียวกับ LoginView (กัน open redirect)
- หลัง login สำเร็จ: ไป `next` หรือ `bookings:role_home` (จาก PR-A)

## 5. Test (`accounts/tests_google_login.py`) — mock ข้อมูลจาก Google ไม่ต้องต่อเน็ต
- ไม่มี client id → หน้า login ไม่มีปุ่ม และ `POST /auth/google/login/` ได้ 404
- มี client id → มีปุ่มเป็น form POST พร้อม csrf
- `GET /auth/google/login/` ไม่เริ่ม flow (ต้อง POST)
- `POST /auth/google/login/` → 302 ไป `accounts.google.com` ที่มี `hd=signalschool.ac.th` และ `redirect_uri` ขึ้นต้นด้วย `PUBLIC_BASE_URL` (ส่ง Host ปลอมมาด้วยใน test)
- adapter (เรียกตรงด้วย sociallogin ปลอม):
  - ผู้ใช้มีอยู่ + verified + domain ถูก + hd ถูก → ผูกบัญชีและ login ได้ / audit `login_google`
  - `email_verified=False` / โดเมนอื่น / `hd` ไม่ตรง / ไม่มีผู้ใช้ / `is_active=False` / uid ผูกกับคนอื่น → ปฏิเสธทุกกรณี, **จำนวน User ไม่เพิ่ม**, audit `login_google_rejected` พร้อมรหัสเหตุผลที่ถูกต้อง
  - อีเมลตัวพิมพ์ใหญ่เล็กต่างกัน → จับคู่ได้
- หน้า signup ของ allauth เข้าไม่ได้
- login ด้วยรหัสผ่าน + ตัวกันเดารหัสยังทำงาน (test เดิมผ่าน)
- `next=https://evil.example/` → ไม่ redirect ออกนอกระบบ

## 6. ขั้นตอนที่ผู้ใช้ต้องทำเอง (เขียนไว้ใน PR และไฟล์ `docs/google-login-setup.md`)
เขียนเป็นภาษาไทยทีละขั้น สำหรับคนไม่ถนัดโค้ด:
1. เข้า Google Cloud Console ด้วยบัญชีที่ดูแลโปรเจกต์ SIGROOM (โปรเจกต์เดียวกับ Cloud Run)
2. **APIs & Services → OAuth consent screen**
   - ถ้าโปรเจกต์อยู่ใต้องค์กร signalschool.ac.th: เลือก **Internal** (คนนอกโรงเรียนจะเข้าไม่ได้ตั้งแต่ฝั่ง Google)
   - ถ้าเลือก Internal ไม่ได้: ใช้ External แล้วระบบยังกันด้วยกฎข้อ 0.2 แต่ต้องกดส่งตรวจ/เพิ่ม test users ตามที่ Google แจ้ง
3. **Credentials → Create credentials → OAuth client ID → Web application**
   - Authorized redirect URI: `https://<โดเมนจริงของ SIGROOM>/auth/google/login/callback/`
4. นำ Client ID / Client secret ใส่ Secret Manager แล้วผูกเป็น env ของ Cloud Run (`GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`) ตรวจว่า `PUBLIC_BASE_URL` ตั้งเป็นโดเมนจริง
5. deploy ใหม่ แล้วเปิดหน้า login จะเห็นปุ่ม Google
6. วิธีตรวจด้วยตา:
   - ลองบัญชีโรงเรียนที่มีในระบบ → เข้าได้
   - ลอง Gmail ส่วนตัว → ถูกปฏิเสธพร้อมข้อความไทย

**Codex ห้ามทำขั้นตอนเหล่านี้เอง และห้ามใส่ค่า secret ใด ๆ ใน repo**

## 7. เกณฑ์ผ่าน
- [ ] `uv run pytest` ผ่านทั้งหมด (ใส่ตัวเลข)
- [ ] `manage.py check` / `check --deploy` (ด้วยค่า env production จำลอง) ไม่มีคำเตือนใหม่
- [ ] migration ของ allauth (ตาราง `socialaccount_*`, `account_*`) เป็นการเพิ่มตารางอย่างเดียว · `makemigrations --check` สะอาด
- [ ] `uv.lock` อัปเดต
- [ ] ไม่มี secret ใน diff (`git diff | grep -i secret` ตรวจเอง)
- [ ] ภาพหน้าจอหน้า login มี / ไม่มีปุ่ม Google

## 8. รูปแบบ PR
- ชื่อ: `feat(auth): sign in with Google for registered @signalschool.ac.th accounts`
- base: `feat/teaching-pigeon`
- เนื้อหาภาษาไทย:
  - สรุป
  - ตารางกฎการรับ/ปฏิเสธ
  - URL ที่เปิดและปิด
  - ขั้นตอนที่ผู้ใช้ต้องทำเอง (ลิงก์ไป `docs/google-login-setup.md`)
  - ข้อสงสัย

## 9. จุดที่ Claude จะตรวจเป็นพิเศษ
1. มีทางที่ Google สร้างบัญชีใหม่ได้ หรือเข้าบัญชีคนอื่นได้ (จับคู่ด้วยอีเมลที่ยังไม่ยืนยัน, โดเมนอื่น, uid ผูกซ้ำ)
2. `redirect_uri` สร้างจาก header ที่ปลอมได้
3. flow เริ่มด้วย GET ได้ (เสี่ยง login CSRF)
4. secret หลุดเข้า repo หรือ DB
5. allauth เปิดหน้า signup / reset password ของตัวเองซ้อนกับของเดิม
6. ตัวกันเดารหัสผ่านถูกข้าม
7. open redirect ผ่าน `next`
