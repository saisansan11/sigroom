# เปิด Google login และทางเข้าจองเตียงของนักเรียน

ระบบมีปุ่มเดียวจาก QR ของรุ่นไปยัง Google แล้วกลับมาหน้าเลือกเตียง ไม่มีหน้าสมัครบัญชี ข้อมูลที่พิสูจน์ว่าเป็นนักเรียนของรุ่นมาจากรายชื่อที่ผู้จัดหลักสูตรยืนยัน ระบบไม่ถือ QR หรือโดเมนอีเมลเป็นหลักฐานสมาชิก

## เตรียมรายชื่อนักเรียนก่อนเปิดใช้

1. เข้าหน้าผู้ดูแลระบบด้วยบัญชีเจ้าหน้าที่ที่มีสิทธิ์จัดการรายชื่อนักเรียน
2. เลือก **รายชื่อนักเรียนที่มีสิทธิ์จองเตียง** → **เพิ่ม**
3. เลือกรุ่นหลักสูตรและอีเมล `@signalschool.ac.th` ของนักเรียน เปิด **อนุญาตให้จองเตียง**
4. ใส่ยศ สังกัด และเบอร์โทรจากข้อมูลจริงของหลักสูตรให้ครบ นักเรียนจึงไม่ต้องกรอกซ้ำตอนเลือกเตียง ชื่อดึงจาก Google ไม่ต้องสร้างบัญชีหรือตั้งรหัสผ่านให้ล่วงหน้า
5. ถ้าเป็นบัญชีเดิมที่ใช้รหัสผ่านแทน Google ให้เลือกบัญชีของนักเรียนในรายชื่อด้วย อีเมลต้องตรงกัน
6. ส่ง QR ของรุ่นจากหน้าจัดการหลักสูตรตามปกติ

ผู้ที่ไม่มีรายชื่อในรุ่นจะถูกปฏิเสธและไม่มีบัญชีใหม่เกิดขึ้น เจ้าหน้าที่ที่มีบัญชีโรงเรียนอยู่แล้วใช้ Google เข้า SIGROOM ได้โดยไม่ต้องอยู่ในรายชื่อนักเรียน แต่การจองเตียงต้องมี membership หรือสิทธิ์ผู้จัดหลักสูตร หากข้อมูลติดต่อในรายชื่อยังไม่ครบ นักเรียนจะเติมเฉพาะช่องที่ขาดในฟอร์มยืนยันเตียงเดิม ระบบไม่เดายศหรือเบอร์โทร

## สร้าง OAuth client บน Google Cloud

1. เปิด Google Cloud Console ด้วยบัญชีที่ดูแลโปรเจกต์ `sixth-storm-439008-u2` และตรวจชื่อโปรเจกต์ให้ตรง
2. เปิด **Google Auth Platform** → **Branding** (หรือ **APIs & Services → OAuth consent screen** หาก Console แสดงเมนูเดิม) กำหนดชื่อ SIGROOM และอีเมลผู้ดูแลตามข้อมูลจริง
3. หน้า **Audience** เลือก **Internal** หากโปรเจกต์อยู่ในองค์กรโรงเรียนและตัวเลือกพร้อมใช้ หากไม่มี ให้เลือก External และทำตามขั้นตอน test users/การตรวจสอบที่ Google แสดง ระบบยังตรวจโดเมนและ claim `hd` ทุกครั้ง
4. หน้า **Clients** → **Create client** → **Web application**
5. ใน **Authorized redirect URIs** ใส่โดเมนจริงของ SIGROOM ตาม `PUBLIC_BASE_URL` ต่อด้วย `/auth/google/login/callback/` ให้ตรงทุกตัว เช่น `https://โดเมนจริง/auth/google/login/callback/` ห้ามใช้ตัวอย่างนี้แทนโดเมนจริง
6. นำ Client ID และ Client secret เก็บใน Secret Manager แล้วผูกกับ Cloud Run เป็น `GOOGLE_OAUTH_CLIENT_ID` และ `GOOGLE_OAUTH_CLIENT_SECRET` โดยใช้ขั้นตอนด้านล่าง ไม่ใส่ใน Git หรือในตาราง SocialApp
7. ตรวจ `PUBLIC_BASE_URL` เป็น origin แบบ HTTPS ของโดเมนจริง ไม่มี path/query ต่อท้าย แล้วเผยแพร่ revision ที่ผ่านการตรวจ

ขาด Client ID หรือ secret อย่างใดอย่างหนึ่งจะซ่อนปุ่ม และ URL Google ตอบ 404 รหัสผ่านและตัวกันเดารหัสเดิมยังทำงานเหมือนเดิม

## ตั้ง Secret Manager และ Cloud Run แบบไม่เผยค่า secret

ตัวอย่างนี้ตั้งชื่อ secret คงที่ แต่ **ไม่ใส่ค่าจริงใน command line** ให้ผู้ดูแลบันทึก Client ID และ Client secret ลงไฟล์ชั่วคราวคนละไฟล์บนเครื่องที่ควบคุมได้ แล้วใช้ `--data-file` เท่านั้น จากนั้นลบไฟล์ทันทีเมื่อยืนยันเสร็จ

```powershell
$project = 'sixth-storm-439008-u2'
$region = 'asia-southeast3'
$service = 'sigroom'
$runtimeSa = 'sigroom-run-sa@sixth-storm-439008-u2.iam.gserviceaccount.com'
$idSecret = 'sigroom-google-oauth-client-id'
$clientSecret = 'sigroom-google-oauth-client-secret'
```

สร้าง secret เฉพาะเมื่อยังไม่มี:

```powershell
gcloud secrets describe $idSecret --project $project *> $null
if ($LASTEXITCODE -ne 0) { gcloud secrets create $idSecret --replication-policy=automatic --project $project }
gcloud secrets describe $clientSecret --project $project *> $null
if ($LASTEXITCODE -ne 0) { gcloud secrets create $clientSecret --replication-policy=automatic --project $project }
```

เพิ่ม version จากไฟล์ชั่วคราวโดยไม่ echo ค่าออกหน้าจอ:

```powershell
gcloud secrets versions add $idSecret --data-file='<ไฟล์ Client ID ชั่วคราว>' --project $project
gcloud secrets versions add $clientSecret --data-file='<ไฟล์ Client secret ชั่วคราว>' --project $project
```

ให้ service account ของ SIGROOM อ่านได้เฉพาะสอง secret นี้:

```powershell
gcloud secrets add-iam-policy-binding $idSecret --member "serviceAccount:$runtimeSa" --role roles/secretmanager.secretAccessor --project $project
gcloud secrets add-iam-policy-binding $clientSecret --member "serviceAccount:$runtimeSa" --role roles/secretmanager.secretAccessor --project $project
```

ผูก secret เข้ากับ Cloud Run ด้วย `--update-secrets` เพื่อ **ไม่ลบ secret อื่นที่ service ใช้อยู่**:

```powershell
gcloud run services update $service --region $region --project $project `
  --update-secrets "GOOGLE_OAUTH_CLIENT_ID=${idSecret}:latest,GOOGLE_OAUTH_CLIENT_SECRET=${clientSecret}:latest"
```

หลัง update ต้องยืนยันว่า traffic 100% ไป revision เดียว, หน้า login แสดงปุ่มตามที่คาด และ `gcloud run services describe` แสดงเพียงการอ้างชื่อ Secret Manager ไม่ใช่ plaintext จากนั้นทำขั้น “อ่าน revision 100% แล้ว replace Job” ใน `docs/ops/run-jobs-cloud.md` ใหม่ เพราะ policy ของ SIGROOM กำหนดให้ `sigroom-run-jobs` ตาม runtime config ของเว็บทุกครั้งที่ image/env/secret เปลี่ยน แม้ Google login จะใช้เฉพาะ request ฝั่งเว็บ

เมื่อ QA เสร็จให้ลบไฟล์ Client ID/secret ชั่วคราวจากเครื่อง และห้ามนำไฟล์นั้นเข้า Git, handoff, log หรือแชท

เอกสารอ้างอิง: [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect) และ [OAuth สำหรับเว็บเซิร์ฟเวอร์](https://developers.google.com/identity/protocols/oauth2/web-server) อธิบายการตั้ง client/callback และตรวจ `email_verified` กับ `hd`

## ทดสอบด้วยตนเอง

1. เปิดหน้าเข้าสู่ระบบ ต้องเห็น **เข้าสู่ระบบด้วย Google** เป็นปุ่มส่ง POST
2. ลองบัญชีโรงเรียนที่ลงทะเบียนแล้ว ต้องเข้าได้และมีประวัติ login เดิม
3. ลอง Gmail ส่วนตัว ต้องถูกปฏิเสธและไม่มีบัญชีใหม่
4. สแกน QR ของรุ่นด้วยนักเรียนที่อยู่ในรายชื่อ กด Google เลือกบัญชีโรงเรียน ต้องกลับหน้าเลือกเตียงของรุ่นทันที
5. เลือกเตียงแล้วกดยืนยัน ข้อมูลติดต่อถูกเติมจากรายชื่อ ชื่อใช้ชื่อจาก Google
6. เปิด QR ของรุ่นอื่นที่ไม่มีรายชื่อ ต้องเข้าหน้าเลือกเตียงไม่ได้
7. บัญชีนักเรียนเปิด `/online/`, `/approvals/`, `/lodging/manage/` หรือ `/admin/` ต้องถูกปฏิเสธ
8. ออกจากระบบแล้วเปิดบัตรที่ผูกบัญชีใหม่ ต้องดูไม่ได้ บัตรเดิมที่ยังไม่มีบัญชีเจ้าของใช้ token เดิมได้

บัญชีเดิมที่มี `must_change_password=True` ยังคงถูกส่งไปตั้งรหัสผ่านตาม middleware เดิม บัญชีนักเรียนที่สร้างจาก Google ใช้รหัสผ่านไม่ได้และไม่ต้องตั้งรหัสครั้งแรก

## ทดสอบบนเครื่องพัฒนา

ใช้ OAuth client แยกสำหรับการทดสอบ และเพิ่ม callback ของ localhost ที่ตรงกับ `PUBLIC_BASE_URL` อย่าใช้ค่าจริงในไฟล์ที่ส่งขึ้น Git ตั้งค่าต่อไปนี้ใน `.env` ของเครื่องพัฒนา:

```text
PUBLIC_BASE_URL=http://127.0.0.1:8000
DJANGO_DEV_OAUTH_SAMESITE=Lax
```

ตั้ง Client ID/secret ของ client สำหรับทดสอบใน env ของเครื่อง แล้วรันทีละคำสั่ง:

```text
uv sync --python 3.12
uv run manage.py migrate
uv run manage.py runserver
```

ค่า Lax นี้ใช้ได้เฉพาะ DEBUG ของเครื่องพัฒนา production ยังคงค่า cookie เดิม (`__session`, CSRF ใน session, SameSite Lax) เมื่อทดสอบเสร็จเอา `DJANGO_DEV_OAUTH_SAMESITE` ออก

## ปิดใช้งานหรือย้อน revision

นำ env Google ออกอย่างน้อยหนึ่งตัวเพื่อปิดปุ่มและ routes ได้ทันที ข้อมูล User/รายชื่อ/เจ้าของบัตรเป็นการเพิ่ม schema จึงคงไว้เมื่อย้อน application revision อย่าย้อน migration หรือลบตาราง allauth ที่มีข้อมูลแล้ว การย้อน application เป็นเวอร์ชันก่อน PR6 จะคืนเส้นทางจองเตียงสาธารณะเดิม จึงต้องจำกัดทางเข้าจองเตียงระหว่างการย้อน revision
