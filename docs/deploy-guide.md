# คู่มือติดตั้ง SIGROOM บนเครื่องหน่วย (B2)

เอกสารนี้พาไปทีละขั้นจนระบบเปิดใช้ใน LAN ได้จริง ทุกขั้นมี: คำสั่งที่คัดลอกได้ · ผลที่ควรเห็น · วิธีตรวจว่าสำเร็จ
ทำตามลำดับ **ห้ามข้าม** โดยเฉพาะหมวด 7 (สิทธิ์ฐานข้อมูล) ที่ต้องทำ**หลัง** migrate และทดสอบกู้คืนแล้วเท่านั้น

> **หลักการที่ใช้ทั้งเอกสาร**
> - ช่วง "ติดตั้ง/บำรุงรักษา" ใช้บัญชีฐานข้อมูล `postgres` (เจ้าของตาราง)
> - ช่วง "ให้บริการจริง" ระบบใช้บัญชี `sigroom_app` ที่สิทธิ์จำกัด — แก้/ลบ audit log ไม่ได้แม้ถูกเจาะระบบ
> - ห้ามให้สิทธิ์สร้าง/ลบฐานข้อมูล (CREATEDB) แก่ `sigroom_app` ไม่ว่ากรณีใด

---

## 1. สิ่งที่ต้องมีก่อนเริ่ม

- [ ] เครื่อง Windows 10/11 ของหน่วย พร้อมสิทธิ์ Administrator
- [ ] อินเทอร์เน็ตชั่วคราวสำหรับดาวน์โหลดโปรแกรม (ถ้าไม่มี → ภาคผนวก ก ติดตั้งออฟไลน์)
- [ ] IP คงที่ใน LAN ของเครื่องนี้ (ขอจากฝ่ายสารสนเทศ) — ในเอกสารนี้สมมุติเป็น `192.168.1.20`
- [ ] ปลายทางสำรองข้อมูล**คนละเครื่อง/ดิสก์**กับเครื่องนี้ เช่น แชร์เครือข่าย `\\SERVER-BACKUP\sigroom` หรือ external disk
- [ ] รายชื่อกำลังพล 30–50 คน เป็นไฟล์ CSV (UTF-8) หัวคอลัมน์ตามนี้เป๊ะ ๆ:
  ```
  username,email,rank,first_name,last_name,unit_code,phone,service_number
  ```
  โดย `unit_code` ต้องตรงกับหน่วยที่ `seed_pilot` สร้าง (HQ, EDU, COMM, EW, ADMIN — เพิ่ม/แก้หน่วยได้ใน Admin) และอีเมลเป็นโดเมน `@signalschool.ac.th`
- [ ] รายชื่อผู้อนุมัติจริงของแต่ละห้อง (ใครอนุมัติห้องไหน ใครเป็นสำรอง)
- [ ] USB สำหรับพาโปรเจกต์ข้ามเครื่อง

## 2. ติดตั้งโปรแกรมพื้นฐาน

ทำในเครื่องหน่วย เปิด **PowerShell แบบ Administrator** (คลิกขวา → Run as administrator)

### 2.1 uv (ตัวจัดการ Python — จะติดตั้ง Python 3.12 ให้เองอัตโนมัติ)

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

ปิดแล้วเปิด PowerShell ใหม่ แล้วตรวจ:

```powershell
uv --version
```

ควรเห็นเลขเวอร์ชัน ถ้าขึ้น "ไม่รู้จักคำสั่ง" ให้เรียกเต็มทาง: `& "$env:USERPROFILE\.local\bin\uv.exe" --version`

### 2.2 PostgreSQL 16

1. ดาวน์โหลด installer จาก https://www.enterprisedb.com/downloads/postgres-postgresql-downloads (เลือก 16.x Windows x86-64)
2. ติดตั้งแบบค่าเริ่มต้น (พอร์ต 5432) — ตอนถามรหัส `postgres` ให้**ตั้งรหัสยาวใหม่เฉพาะเครื่องนี้** จดใส่ซองปิดผนึกเก็บกับผู้ดูแล ห้ามใช้รหัสเดียวกับเครื่องพัฒนา
3. ไม่ต้องติดตั้ง Stack Builder

ตรวจ:

```powershell
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" --version
```

### 2.3 จำกัด PostgreSQL ให้คุยเฉพาะในเครื่องตัวเอง

เปิดไฟล์ `C:\Program Files\PostgreSQL\16\data\postgresql.conf` ด้วย Notepad (Run as administrator) หาบรรทัด `listen_addresses` แก้เป็น:

```
listen_addresses = 'localhost'
```

แล้ว restart service:

```powershell
Restart-Service postgresql-x64-16
```

ผล: ฐานข้อมูลรับการเชื่อมต่อจากในเครื่องนี้เท่านั้น เครื่องอื่นใน LAN มองไม่เห็นพอร์ต 5432

## 3. นำโปรเจกต์เข้าเครื่อง (git bundle)

**ที่เครื่องพัฒนา** สร้าง bundle ใส่ USB:

```powershell
cd F:\ogn_ROOM
git bundle create E:\sigroom.bundle main
```

**ที่เครื่องหน่วย** (สมมุติวางระบบไว้ที่ `C:\sigroom`):

```powershell
git clone E:\sigroom.bundle C:\sigroom -b main
cd C:\sigroom
uv sync
```

`uv sync` จะติดตั้ง Python 3.12 และแพ็กเกจทั้งหมด (ครั้งแรกใช้เน็ต ~2-5 นาที)
ตรวจ: `uv run python --version` ควรได้ `Python 3.12.x`

> ถ้าเครื่องหน่วยไม่มี git: ติดตั้งจาก https://git-scm.com/download/win (ค่าเริ่มต้นทั้งหมด) หรือใช้วิธีออฟไลน์ในภาคผนวก ก

## 4. ตั้งค่า `.env` production

```powershell
cd C:\sigroom
Copy-Item .env.example .env
notepad .env
```

สุ่ม SECRET_KEY ใหม่ (รันแล้วคัดลอกผลไปวาง):

```powershell
uv run python -c "import secrets; print(secrets.token_urlsafe(50))"
```

แก้ค่าใน `.env` ให้เป็นแบบนี้ (แทน `192.168.1.20` ด้วย IP จริงของเครื่อง):

```
DJANGO_SECRET_KEY=<ผลจากคำสั่งสุ่มข้างบน>
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=192.168.1.20,localhost,127.0.0.1
DJANGO_SECURE=0
CSRF_TRUSTED_ORIGINS=http://192.168.1.20:8000

DB_NAME=ogn_room
DB_USER=postgres
DB_PASSWORD=<รหัส postgres ที่ตั้งในข้อ 2.2>
DB_HOST=127.0.0.1
DB_PORT=5432

ALLOWED_EMAIL_DOMAIN=signalschool.ac.th

BACKUP_DIR=\\SERVER-BACKUP\sigroom
```

> ⚠️ **สองจุดที่พลาดบ่อยที่สุด**
> 1. `BACKUP_DIR` **ห้ามใช้ค่าตัวอย่าง `.\backups`** ใน production — นั่นคือดิสก์เดียวกับตัวเครื่อง ไฟไหม้/ดิสก์พังจะหายทั้งระบบทั้งสำรอง ต้องเป็น**เครื่องหรือดิสก์อื่น**
> 2. แชร์เครือข่ายต้องเขียนเป็น **UNC path** (`\\ชื่อเครื่อง\แชร์`) **ห้ามใช้ drive ที่ map ไว้** (เช่น `Z:\`) เพราะงานอัตโนมัติที่รันตอนไม่มีใคร login จะมองไม่เห็น drive พวกนั้น
>
> ตอนนี้ `DB_USER` ยังเป็น `postgres` ชั่วคราว — จะสลับเป็นบัญชีจำกัดสิทธิ์ในหมวด 7 หลังทุกอย่างพร้อม

> 📝 **บันทึกความเสี่ยงที่ยอมรับ:** `DJANGO_SECURE=0` เปิดใช้ HTTP ไม่เข้ารหัสภายใน LAN เท่านั้น ตามข้อตกลง pilot (SRS หมวด 10 ยังไม่บังคับจนกว่าจะเปิดอินเทอร์เน็ต) — ห้าม forward พอร์ตนี้ออกนอกหน่วยเด็ดขาด

## 5. สร้างฐานข้อมูลและตั้งระบบครั้งแรก

ยังใช้บัญชี `postgres` (เจ้าของตาราง) ทำทุกข้อในหมวดนี้

### 5.1 สร้างฐานข้อมูล

```powershell
& "C:\Program Files\PostgreSQL\16\bin\createdb.exe" -U postgres ogn_room
```

(ถามรหัส → ใส่รหัส postgres) ไม่มีข้อความอะไรขึ้น = สำเร็จ

### 5.2 สร้างตารางทั้งหมด

```powershell
cd C:\sigroom
uv run manage.py migrate
```

ควรเห็นรายการ `Applying ...` ยาว ๆ จบโดยไม่มี error — migration แรกจะสร้าง extension `btree_gist` ให้เอง (ต้องเป็น postgres จึงสร้างได้ นี่คือเหตุผลที่ยังไม่สลับบัญชี)

ตรวจกฎกันจองซ้อนที่ฐานข้อมูล (สำคัญที่สุดของระบบ):

```powershell
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -d ogn_room -c "SELECT conname FROM pg_constraint WHERE conname LIKE '%excl%';"
```

ต้องเห็นชื่อ constraint อย่างน้อย 1 แถว (exclusion constraint ของ BookingResource)

### 5.3 เก็บไฟล์ static

```powershell
uv run manage.py collectstatic --noinput
```

ควรจบด้วย "xxx static files copied"

### 5.4 สร้างบัญชีผู้ดูแลระบบเว็บ

```powershell
uv run manage.py createsuperuser
```

ตั้ง username/รหัสใหม่เฉพาะเครื่องนี้ (ห้ามใช้รหัสจากเครื่องพัฒนา) จดใส่ซองเดียวกับรหัส postgres

### 5.5 ข้อมูลตั้งต้น (ห้อง/หน่วย)

```powershell
uv run manage.py seed_pilot
```

> **ห้ามใส่ `--demo-users`** — บัญชี demo (somchai/wanida/somsak) มีรหัสสาธารณะอยู่ในโค้ด ใช้เฉพาะเครื่องพัฒนาเท่านั้น

ผล: หน่วย 5 หน่วย + ห้อง 8 ห้อง + อุปกรณ์กลาง **และ Blackout ตัวอย่าง 1 รายการ** จากนั้นเข้า Admin (`http://localhost:8000/admin/` — เปิด server ชั่วคราวด้วย `uv run manage.py runserver` ก่อน) เพื่อ:
- ⚠️ **ลบหรือแก้ Blackout ตัวอย่างชื่อ "วันหยุดชดเชย"** (Admin → Resources → Blackouts) — seed สร้างไว้สำหรับวันจันทร์ถัดไปเพื่อการทดลอง ถ้าปล่อยไว้**ทุกห้องจะถูกงดใช้ทั้งวันโดยไม่ตั้งใจ** ลบทิ้งหรือแก้เป็นวันหยุดจริงของหน่วย
- แก้ชื่อห้อง/อาคาร/ความจุ ให้ตรงของจริงของหน่วย

(ผู้อนุมัติของห้องยังตั้งไม่ได้ตอนนี้ — ต้องมีบัญชีผู้ใช้ก่อน ทำในข้อ 5.7)

### 5.6 นำเข้าหน่วยงานจริง

วางไฟล์หน่วยงานไว้ที่ `C:\sigroom\units.csv` (ดูรูปแบบตัวอย่างที่ `docs/examples/units-กศ.csv`) แล้ว:

```powershell
uv run manage.py import_units units.csv
```

คำสั่งนี้สร้างหรืออัปเดตชื่อหน่วยตาม `code` และผูก `parent` ตามรหัสหน่วยแม่ จึงรันซ้ำได้โดยไม่สร้างหน่วยซ้ำ

### 5.7 นำเข้ารายชื่อกำลังพลจริง

วางไฟล์ CSV (จากข้อ 1) ไว้ที่ `C:\sigroom\users.csv` แล้ว:

```powershell
uv run manage.py import_users users.csv
```

ระบบจะสร้างบัญชี สุ่มรหัสเริ่มต้นให้คนละชุด และออกไฟล์ `imported-users-YYYYMMDD.csv` (username + รหัสเริ่มต้น)

> 🔐 พิมพ์/แจกรหัสเริ่มต้นให้เจ้าตัว **แล้วลบไฟล์ imported-users-*.csv ทิ้งทันที** และลบ `users.csv` ด้วย
> ทุกคน login ครั้งแรกจะถูกบังคับตั้งรหัสใหม่เอง (หน้า S17)

### 5.8 ตั้งผู้อนุมัติจริงของแต่ละห้อง

ตอนนี้มีบัญชีครบแล้ว เข้า Admin → Resources → เลือกห้อง → กำหนด **Resource approvers**:
- ห้องที่นโยบาย "ต้องอนุมัติ" (MTG-1, MTG-CO) ต้องมีผู้อนุมัติหลัก 1 คน + สำรองอย่างน้อย 1 คน ตามรายชื่อจริงจากข้อ 1
- ห้องอนุมัติอัตโนมัติไม่บังคับ แต่ตั้งเจ้าหน้าที่ดูแลห้อง (custodian) ให้ครบตามผังหน่วย

## 6. ทดสอบสำรอง–กู้คืน (ต้องผ่านก่อนไปหมวด 7)

ทำตอนที่ `.env` ยังเป็น `postgres` เพราะการทดสอบกู้คืนต้องสร้าง/ลบฐานทดสอบ ซึ่งบัญชีจำกัดสิทธิ์ทำไม่ได้ (โดยตั้งใจ)

```powershell
cd C:\sigroom
powershell -ExecutionPolicy Bypass -File scripts\backup.ps1
powershell -ExecutionPolicy Bypass -File scripts\restore-test.ps1
```

ต้องเห็น:
- backup: `สำรองสำเร็จ: \\SERVER-BACKUP\sigroom\sigroom-YYYYMMDD-HHmm.dump`
- restore-test: `ผ่าน — กู้ ... สำเร็จ และ Booking ตรงกัน x แถว`

**ถ่ายภาพหน้าจอผล restore-test เก็บไว้** — เป็นหลักฐานเกณฑ์รับมอบข้อ 11 ของ SRS §15.2

ถ้า backup ไปแชร์เครือข่ายไม่สำเร็จ: ตรวจว่าพิมพ์ UNC ถูก, เข้าถึงแชร์จาก File Explorer ได้, และบัญชี Windows ที่จะใช้รัน Task Scheduler (หมวด 8) มีสิทธิ์เขียนแชร์นั้น

## 7. ล็อกสิทธิ์ฐานข้อมูล (least privilege + audit แก้ไม่ได้)

ถึงตอนนี้ระบบทำงานครบและกู้คืนได้แล้ว จึงค่อยลดสิทธิ์ runtime

### 7.1 สร้างบัญชี `sigroom_app` และให้สิทธิ์เท่าที่จำเป็น

รัน (ถามรหัส → รหัส postgres) — แทน `<รหัสยาวใหม่>` ด้วยรหัสสุ่มอีกชุด (ใช้คำสั่งสุ่มเดียวกับข้อ 4 ได้):

```powershell
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -d ogn_room -c "CREATE ROLE sigroom_app LOGIN PASSWORD '<รหัสยาวใหม่>' NOSUPERUSER NOCREATEDB NOCREATEROLE;"
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -d ogn_room -f scripts\db-grants.sql
```

`scripts/db-grants.sql` ให้สิทธิ์อ่าน/เขียนตารางงานปกติทั้งหมด แต่ **ตาราง `audit_auditlog` ได้เฉพาะ SELECT + INSERT** — เพิ่มได้ อ่านได้ แต่แก้/ลบไม่ได้ที่ระดับฐานข้อมูล (NF-02)

### 7.2 สลับ `.env` ให้ระบบใช้บัญชีจำกัดสิทธิ์

แก้ `.env` สองบรรทัด:

```
DB_USER=sigroom_app
DB_PASSWORD=<รหัสของ sigroom_app>
```

### 7.3 พิสูจน์ว่าล็อกจริง

```powershell
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U sigroom_app -d ogn_room -c "UPDATE audit_auditlog SET action='x';"
```

ต้องขึ้น **`ERROR: permission denied for table audit_auditlog`** — นี่คือผลที่ถูกต้อง (ถ้าทำสำเร็จแปลว่าล็อกไม่ติด ให้กลับไปรัน db-grants.sql ใหม่)

แล้วตรวจว่าระบบยังทำงานปกติด้วยบัญชีใหม่:

```powershell
uv run manage.py check --database default
```

ต้องได้ `System check identified no issues`

> 📌 **กติกาถาวรหลังจากนี้**
> - `migrate` รอบอนาคต (ตอนอัปเดตเวอร์ชัน): หยุด server → แก้ `.env` กลับเป็น `postgres` ชั่วคราว → `uv run manage.py migrate` → รัน `db-grants.sql` ซ้ำ (เผื่อมีตารางใหม่) → คืน `.env` เป็น `sigroom_app` → เปิด server → สำรองโค้ดเวอร์ชันใหม่ด้วย `git bundle create \\SERVER-BACKUP\sigroom\sigroom-code.bundle main` (นโยบายหน่วย: ไม่เก็บโค้ดบนคลาวด์ — bundle บนแชร์ backup คือสำเนานอกเครื่องเพียงชุดเดียว)
> - ทดสอบกู้คืนรายเดือน: ใช้วิธีสลับ `.env` แบบเดียวกัน (ดู pilot-checklist) — **ห้ามแก้ปัญหาด้วยการให้ CREATEDB แก่ sigroom_app**

## 8. งานอัตโนมัติ — Task Scheduler 3 งาน

เปิด Task Scheduler (กด Win พิมพ์ "Task Scheduler") → Create Task (ไม่ใช่ Basic Task) ทั้ง 3 งานตั้งเหมือนกันตรงนี้:
- แท็บ General: เลือก **"Run whether user is logged on or not"** + ติ๊ก "Run with highest privileges"
- **ห้ามติ๊ก "Do not store password"** — ตัวเลือกนั้นทำให้ task เข้าถึง network resource ไม่ได้ งาน Backup จะเขียน `\\SERVER-BACKUP\...` ไม่สำเร็จ
- ใช้บัญชี Windows ที่มีสิทธิ์เขียนแชร์ backup (ตอนกด OK ระบบจะถามรหัสของบัญชีนั้น — ใส่เพื่อให้ Windows เก็บ credential ไว้ใช้ตอนไม่มีใคร login)

หา full path ของ uv ก่อน (ใช้ในงานที่ 2) — รันแล้วจดผลไว้:

```powershell
(Get-Command uv.exe).Source
```

ปกติจะได้ `C:\Users\<บัญชี>\.local\bin\uv.exe` — ในตารางข้างล่างเขียนแทนด้วย `<UV>`

| | งานที่ 1: SIGROOM Server | งานที่ 2: SIGROOM Jobs | งานที่ 3: SIGROOM Backup |
|---|---|---|---|
| Trigger | At startup | ทุก 5 นาที (Repeat task every 5 minutes, Indefinitely) | Daily 19:00 |
| Action → Program | `powershell.exe` | `powershell.exe` | `powershell.exe` |
| Arguments | `-ExecutionPolicy Bypass -File C:\sigroom\scripts\run-server.ps1` | `-ExecutionPolicy Bypass -Command "cd C:\sigroom; & '<UV>' run manage.py run_jobs"` | `-ExecutionPolicy Bypass -File C:\sigroom\scripts\backup.ps1` |
| Settings เพิ่มเติม | "If the task fails, restart every 1 minute" (สูงสุด 3 ครั้ง) และ**เอาติ๊กออก** "Stop the task if it runs longer than..." | — | ติ๊ก "Run task as soon as possible after a scheduled start is missed" (เผื่อเครื่องปิดอยู่ตอน 19:00) |

> `run-server.ps1` เรียก Waitress (เว็บเซิร์ฟเวอร์ production) ที่พอร์ต 8000 — ไม่ใช่ `runserver` ของ Django ที่ใช้เฉพาะพัฒนา
> สคริปต์หา `uv.exe` ให้เองแม้ PATH ของ Task Scheduler ไม่ครบ และส่ง exit code ของ Waitress กลับ เพื่อให้เงื่อนไข restart on failure จับได้จริงเมื่อ server ล้ม

ตรวจแต่ละงาน — **เกณฑ์ต่างกัน**:
- **งานที่ 1 (Server):** คลิกขวา → Run แล้วดูคอลัมน์ Status ต้องเป็น **Running ค้างไว้** (เป็น process ที่รันตลอด — ห้ามใช้ Last Run Result ตัดสิน) และเปิด `http://localhost:8000` ต้องขึ้นหน้า login
- **งานที่ 2 และ 3:** คลิกขวา → Run แล้วดู **Last Run Result = `0x0`**

จากนั้น **restart เครื่องหนึ่งรอบ** แล้วเปิด `http://localhost:8000` — ต้องขึ้นหน้า login เองโดยไม่ต้องแตะอะไร

## 9. Firewall — เปิดพอร์ต 8000 เฉพาะวง LAN

PowerShell (Administrator) — แทน `192.168.1.0/24` ด้วยวง LAN จริงของหน่วย:

```powershell
New-NetFirewallRule -DisplayName "SIGROOM LAN" -Direction Inbound -Protocol TCP -LocalPort 8000 -RemoteAddress 192.168.1.0/24 -Action Allow
```

ตรวจ: จากเครื่องอื่นใน LAN เปิด `http://192.168.1.20:8000` ต้องเห็นหน้า login SIGROOM (จอเรดาร์)

## 10. ตรวจรับการติดตั้ง (ทำคู่กัน 2 คน)

- [ ] เปิดจาก**เครื่องอื่น**ใน LAN ได้ และจาก**มือถือ** (ต่อ Wi-Fi หน่วย) ได้
- [ ] login ด้วยบัญชีจริงที่ import → ถูกบังคับเปลี่ยนรหัส (S17) → เปลี่ยนแล้วเข้าหน้าแรกได้
- [ ] จองจริง 1 รายการครบวงจร: ค้นหา → จอง → ผู้อนุมัติจริงเห็นคิว → อนุมัติ → ขึ้นปฏิทิน → ผู้จองได้กระดิ่งแจ้งเตือน
- [ ] Admin → Audit log มีแถวบันทึกเหตุการณ์ข้างต้น
- [ ] ผล restore-test "ผ่าน" (ภาพหน้าจอจากหมวด 6)
- [ ] ทดสอบ `UPDATE audit_auditlog` ด้วย `sigroom_app` แล้วถูกปฏิเสธ (หมวด 7.3)
- [ ] restart เครื่องแล้วระบบกลับมาเอง (หมวด 8)
- [ ] `.env` ใช้ `sigroom_app` และไฟล์ `imported-users-*.csv` ถูกลบแล้ว
- [ ] Blackout ตัวอย่าง "วันหยุดชดเชย" ถูกลบหรือแก้เป็นวันหยุดจริงแล้ว (หมวด 5.5)

ครบทุกข้อ = การติดตั้งเสร็จสมบูรณ์ → ไปต่อที่ `docs/pilot-checklist.md`

---

## ภาคผนวก ก — ติดตั้งแบบออฟไลน์ (เครื่องหน่วยไม่มีอินเทอร์เน็ต)

เตรียมที่เครื่องพัฒนา (มีเน็ต) ใส่ USB:

1. Installer: Python 3.12 (python.org, Windows 64-bit), PostgreSQL 16, Git for Windows
2. แพ็กเกจ Python ทั้งหมดเป็นไฟล์ wheel:
   ```powershell
   cd F:\ogn_ROOM
   uv export --format requirements-txt --no-dev -o E:\sigroom-req.txt
   uv run python -m pip download -r E:\sigroom-req.txt -d E:\sigroom-wheels
   ```
3. git bundle ตามหมวด 3

ที่เครื่องหน่วย:

1. ติดตั้ง Python 3.12 (ติ๊ก "Add python.exe to PATH"), PostgreSQL 16, Git จาก installer ใน USB
2. clone จาก bundle ตามหมวด 3 แล้วสร้าง environment โดยไม่ใช้เน็ต:
   ```powershell
   cd C:\sigroom
   python -m venv .venv
   .venv\Scripts\python -m pip install --no-index --find-links E:\sigroom-wheels -r E:\sigroom-req.txt
   ```
3. ทุกคำสั่ง `uv run manage.py ...` ในคู่มือ แทนด้วย `.venv\Scripts\python manage.py ...`
4. Task งานที่ 1 (Server) แก้ Arguments เป็น:
   `-ExecutionPolicy Bypass -Command "cd C:\sigroom; .venv\Scripts\waitress-serve --listen=0.0.0.0:8000 config.wsgi:application"`
5. Task งานที่ 2 (Jobs) แก้เป็น: `-ExecutionPolicy Bypass -Command "cd C:\sigroom; .venv\Scripts\python manage.py run_jobs"`

(สคริปต์ backup/restore-test ใช้ได้ตามเดิม — ไม่พึ่ง uv)

## ภาคผนวก ข — ปัญหาที่พบบ่อย

| อาการ | สาเหตุ/ทางแก้ |
|---|---|
| `uv` ไม่รู้จักคำสั่ง | เปิด PowerShell ใหม่ หรือเรียกเต็มทาง `%USERPROFILE%\.local\bin\uv.exe` |
| เปิดจากเครื่องอื่นขึ้น Bad Request (400) | IP ไม่อยู่ใน `DJANGO_ALLOWED_HOSTS` ใน `.env` — เพิ่มแล้ว restart งาน SIGROOM Server |
| กด submit ฟอร์มแล้วขึ้น CSRF error (403) | `CSRF_TRUSTED_ORIGINS` ไม่ตรง — ต้องมี `http://` นำหน้าและพอร์ต `:8000` ครบ |
| Task รันมือได้แต่ตอนตั้งเวลาไม่ทำงาน | ไม่ได้เลือก "Run whether user is logged on or not" หรือใช้ mapped drive แทน UNC |
| backup FAILED: เขียนแชร์ไม่ได้ | บัญชีที่รัน Task ไม่มีสิทธิ์เขียนแชร์ — ทดสอบด้วย `echo test > \\SERVER-BACKUP\sigroom\test.txt` จากบัญชีนั้น |
| `permission denied` ตอน migrate | `.env` ยังเป็น `sigroom_app` — ทำตามกติกาในหมวด 7: สลับเป็น `postgres` ก่อน migrate |
| หน้าเว็บไม่มีสี/ฟอนต์เพี้ยน | ยังไม่ได้รัน `collectstatic` หลังอัปเดต — รันแล้ว restart งาน SIGROOM Server |
| login แล้วเด้งกลับหน้า login | เวลาเครื่อง server กับเครื่องผู้ใช้ต่างกันมาก — ตั้ง sync เวลากับ time server ของหน่วย |
