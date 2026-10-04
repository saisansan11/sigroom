# เปิดงานตามเวลา SIGROOM บน Google Cloud (ผู้ใช้รันเอง)

คู่มือนี้ใช้หลังผู้ใช้ merge/deploy PR-1 ถึง PR-4 และรัน migration แล้วเท่านั้น Codex ไม่ได้รันคำสั่ง Google Cloud และไม่ได้เปลี่ยนระบบจริง ไม่มี HTTP endpoint ใหม่สำหรับสั่งงาน

ปลายทาง: project `sixth-storm-439008-u2`, เว็บ `sigroom`, region `asia-southeast3` งานชื่อ `sigroom-run-jobs` และตัวปลุกชื่อ `sigroom-run-jobs-every-five-minutes`

เปิด **PowerShell** บนเครื่องที่ลง Google Cloud CLI และ login บัญชีผู้ดูแลโปรเจกต์ไว้แล้ว รันแต่ละบล็อกตามลำดับ คำสั่ง Google Cloud ทุกบรรทัดระบุ project โดยตรง ไม่อาศัย default config

## 1. เปิด API ที่งานต้องใช้

```powershell
gcloud services enable run.googleapis.com cloudscheduler.googleapis.com --project sixth-storm-439008-u2
```

## 2. อ่านเวอร์ชันเว็บที่รับผู้ใช้จริง

บล็อกนี้อ่าน config ไว้ในหน่วยความจำ ไม่พิมพ์ค่า env หรือ secret ลงหน้าจอ ถ้าเว็บแบ่ง traffic หลายเวอร์ชันจะหยุด ให้เลือกเวอร์ชันกับผู้ดูแลก่อน

```powershell
$sigroomService = gcloud run services describe sigroom --region asia-southeast3 --project sixth-storm-439008-u2 --format=json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw 'อ่านข้อมูลเว็บไม่สำเร็จ ให้หยุดก่อน' }
$sigroomTraffic = @($sigroomService.status.traffic | Where-Object { $_.percent -eq 100 })
if ($sigroomTraffic.Count -ne 1 -or -not $sigroomTraffic[0].revisionName) { throw 'เว็บยังไม่ได้ส่ง traffic 100% ไป revision เดียว ให้ผู้ดูแลเลือก revision ก่อน' }
$sigroomRevisionName = $sigroomTraffic[0].revisionName
$sigroomRevision = gcloud run revisions describe $sigroomRevisionName --region asia-southeast3 --project sixth-storm-439008-u2 --format=json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw 'อ่าน revision ไม่สำเร็จ ให้หยุดก่อน' }
if (@($sigroomRevision.spec.containers).Count -ne 1) { throw 'พบหลาย container ต้องให้ผู้ดูแลตรวจ config งานก่อน' }
if (-not $sigroomRevision.status.imageDigest -or -not $sigroomRevision.spec.serviceAccountName) { throw 'ไม่พบ image digest หรือ runtime service account ให้หยุดก่อน' }
```

## 3. เตรียม config งานโดยใช้ image และสิทธิ์เดียวกับเว็บ

คัดลอก image แบบ digest, env, **ชื่ออ้างอิง secret เดิม**, Cloud SQL, VPC, volume และ runtime service account จาก revision ที่ตรวจแล้ว เปลี่ยนเฉพาะคำสั่งเริ่มเป็น `python manage.py run_jobs` ไม่อ่านค่า Secret Manager และไม่สร้างกุญแจใหม่

ไฟล์ config จะอยู่ในโฟลเดอร์ชั่วคราวของเครื่องผู้ใช้ ถือว่าเป็นไฟล์ส่วนตัวเพราะ config เว็บอาจมี env ที่อ่อนไหว ห้าม commit หรือส่งไฟล์นี้ใน PR

```powershell
$sigroomSourceContainer = $sigroomRevision.spec.containers[0]
$sigroomJobContainer = @{ image = $sigroomRevision.status.imageDigest; command = @('python'); args = @('manage.py', 'run_jobs') }
foreach ($sigroomField in @('env', 'resources', 'volumeMounts')) {
    if ($null -ne $sigroomSourceContainer.$sigroomField) { $sigroomJobContainer[$sigroomField] = $sigroomSourceContainer.$sigroomField }
}
$sigroomRuntimeAnnotations = @{}
foreach ($sigroomAnnotation in @('run.googleapis.com/cloudsql-instances', 'run.googleapis.com/vpc-access-connector', 'run.googleapis.com/vpc-access-egress', 'run.googleapis.com/network-interfaces', 'run.googleapis.com/encryption-key')) {
    $sigroomValue = $sigroomRevision.metadata.annotations.$sigroomAnnotation
    if ($sigroomValue) { $sigroomRuntimeAnnotations[$sigroomAnnotation] = $sigroomValue }
}
$sigroomTaskSpec = @{ serviceAccountName = $sigroomRevision.spec.serviceAccountName; containers = @($sigroomJobContainer); timeoutSeconds = '240'; maxRetries = 0 }
if ($null -ne $sigroomRevision.spec.volumes) { $sigroomTaskSpec['volumes'] = $sigroomRevision.spec.volumes }
$sigroomJobConfig = @{
    apiVersion = 'run.googleapis.com/v1'
    kind = 'Job'
    metadata = @{ name = 'sigroom-run-jobs' }
    spec = @{ template = @{
        metadata = @{ annotations = $sigroomRuntimeAnnotations }
        spec = @{ taskCount = 1; parallelism = 1; template = @{ spec = $sigroomTaskSpec } }
    } }
}
$sigroomJobFile = Join-Path ([System.IO.Path]::GetTempPath()) ('sigroom-run-jobs-' + [guid]::NewGuid().ToString() + '.yaml')
[System.IO.File]::WriteAllText($sigroomJobFile, ($sigroomJobConfig | ConvertTo-Json -Depth 30), [System.Text.UTF8Encoding]::new($false))
```

JSON เป็นรูปแบบที่ YAML อ่านได้ จึงใช้ไฟล์นี้กับ `jobs replace` ได้โดยไม่ต้องติดตั้งตัวแปลงเพิ่ม งานมีเพียงหนึ่ง task, ไม่ retry อัตโนมัติ และหยุดเมื่อเกิน 4 นาที ดูเวลาจริงในขั้นทดสอบ หากเกินช่วง 5 นาทีให้ตรวจปริมาณงาน/SMTP ก่อนเปิด beta

ตรวจใน config ของเว็บว่ามี `PUBLIC_BASE_URL` เป็น URL HTTPS ของเว็บจริง, `DJANGO_DEBUG=0`, ฐานข้อมูลและ SMTP ถูกต้องอยู่แล้ว หากยังไม่มี ให้ผู้ดูแลตั้งค่าบนเว็บก่อน แล้วเริ่มขั้น 2 ใหม่ การแจ้งเตือนในเว็บยังสร้างได้เมื่อ SMTP ล้ม แต่การส่งอีเมลจะนับว่าไม่สำเร็จ

สร้างหรืออัปเดต **เฉพาะ Job** จาก config ที่เตรียมไว้:

```powershell
gcloud run jobs replace $sigroomJobFile --region asia-southeast3 --project sixth-storm-439008-u2
```

หลังสำเร็จลบไฟล์ส่วนตัวที่เพิ่งสร้างด้วยคำสั่งนี้:

```powershell
Remove-Item -LiteralPath $sigroomJobFile
```

หากขั้น replace ล้ม ให้ลบไฟล์ส่วนตัวด้วยบรรทัดเดียวกันและตรวจข้อความผิดพลาดกับผู้ดูแล

## 4. ทดสอบงานด้วยตนเองก่อนตั้งปลุก

ครูทดสอบที่มีสิทธิ์ `signalschool-teacher` จองคาบเริ่มใน 40 นาที แล้วรอเข้าสู่ช่วงเตือน 30 นาที รันงานหนึ่งครั้ง:

```powershell
gcloud run jobs execute sigroom-run-jobs --region asia-southeast3 --project sixth-storm-439008-u2 --wait
```

ดู log และสรุปจำนวนแจ้งเตือน โดยใช้คำสั่งนี้หลังแต่ละครั้ง:

```powershell
gcloud logging read 'resource.type="cloud_run_job" AND resource.labels.job_name="sigroom-run-jobs"' --limit 30 --order desc --project sixth-storm-439008-u2
```

รัน `jobs execute` อีกสองครั้งในช่วงเดิม ต้องไม่มีแถวกระดิ่งหรืออีเมลซ้ำ จำนวนรอบนั้นใน log ของครั้งที่ 2 และ 3 ต้องเป็น 0 เมื่อถึงเวลาเริ่มสอนจะได้อีกรอบหนึ่ง เปิดหน้ากระดิ่งด้วยบัญชีครูและตรวจว่าลิงก์ไปบัตรจองของตนเอง อีเมลมีห้อง วัน พ.ศ. เวลา และลิงก์เว็บจริง ห้ามใช้ console email backend บน production เพราะอาจเผย reset token และลิงก์ห้องเรียนใน log

## 5. สร้างบัญชีเฉพาะตัวปลุกและให้สิทธิ์เรียก Job นี้

บัญชีนี้ใช้เรียกงานเท่านั้น ไม่ใช่บัญชีที่เข้า PostgreSQL หรืออ่าน secret หากมีบัญชีชื่อนี้แล้ว ให้ข้ามเฉพาะบรรทัดสร้าง และตรวจว่าเป็นบัญชีของตัวปลุก SIGROOM

```powershell
gcloud iam service-accounts create sigroom-jobs-scheduler --display-name 'ตัวปลุกงาน SIGROOM' --project sixth-storm-439008-u2
```

ให้สิทธิ์เรียกเฉพาะ Job นี้:

```powershell
gcloud run jobs add-iam-policy-binding sigroom-run-jobs --member serviceAccount:sigroom-jobs-scheduler@sixth-storm-439008-u2.iam.gserviceaccount.com --role roles/run.invoker --region asia-southeast3 --project sixth-storm-439008-u2
```

ผู้สร้าง Scheduler ต้องมีสิทธิ์สร้าง Scheduler และ `iam.serviceAccounts.actAs` บนบัญชีตัวปลุกนี้อยู่แล้ว หากไม่มี ให้ผู้ดูแลให้สิทธิ์เฉพาะบัญชีนี้ก่อน ไม่จำเป็นต้องให้ Owner เพิ่ม

## 6. ตั้งปลุกทุก 5 นาที

ปลายทางเป็น Google API (`run.googleapis.com`) จึงใช้ **OAuth access token** ผ่าน `--oauth-service-account-email` ตามคู่มือ Google:

```powershell
gcloud scheduler jobs create http sigroom-run-jobs-every-five-minutes --location asia-southeast3 --schedule '*/5 * * * *' --time-zone Asia/Bangkok --uri 'https://run.googleapis.com/v2/projects/sixth-storm-439008-u2/locations/asia-southeast3/jobs/sigroom-run-jobs:run' --http-method POST --headers 'Content-Type=application/json' --message-body '{}' --oauth-service-account-email sigroom-jobs-scheduler@sixth-storm-439008-u2.iam.gserviceaccount.com --oauth-token-scope 'https://www.googleapis.com/auth/cloud-platform' --max-retry-attempts 0 --project sixth-storm-439008-u2
```

ถ้ามี Scheduler ชื่อนี้แล้ว ใช้ `gcloud scheduler jobs update http` แทน `create http` โดยคง argument ทั้งหมดในบรรทัดเดิม ห้ามสร้างตัวปลุกซ้ำชื่ออื่น

ตรวจข้อมูลตัวปลุก:

```powershell
gcloud scheduler jobs describe sigroom-run-jobs-every-five-minutes --location asia-southeast3 --project sixth-storm-439008-u2
```

สั่งตัวปลุกหนึ่งครั้งเพื่อทดสอบสิทธิ์ แล้วดู log ด้วยคำสั่งในขั้น 4:

```powershell
gcloud scheduler jobs run sigroom-run-jobs-every-five-minutes --location asia-southeast3 --project sixth-storm-439008-u2
```

Scheduler เรียก Run API สำเร็จยังไม่ได้ยืนยันว่า task ทำงานสำเร็จ ต้องดู execution ของ Job และ log ควบคู่กัน การเตือนจะไม่ทำงานย้อนหลังนอกหน้าต่างที่กำหนด

## เมื่อ deploy รุ่นใหม่ / เมื่อจำเป็นต้องหยุด

เมื่อเว็บเปลี่ยน image หรือ runtime config ให้ทำขั้น 2–3 ใหม่เพื่อให้ Job ตรงกับเว็บ การ deploy เว็บอย่างเดียวไม่อัปเดต Job ให้อัตโนมัติ และไม่ต้องสร้าง Scheduler เพิ่ม

หยุดเฉพาะตัวปลุกได้ด้วยคำสั่งนี้ โดยเก็บ Job และข้อมูลเดิมไว้:

```powershell
gcloud scheduler jobs pause sigroom-run-jobs-every-five-minutes --location asia-southeast3 --project sixth-storm-439008-u2
```

เปิดกลับหลังตรวจเสร็จ:

```powershell
gcloud scheduler jobs resume sigroom-run-jobs-every-five-minutes --location asia-southeast3 --project sixth-storm-439008-u2
```

## ข้อสงสัย / ข้อจำกัดของ PR-4

- แผนกำหนดหน้าต่างรอบก่อนสอนครอบคลุม 30 ถึงก่อน 5 นาที แต่กำหนดว่าจองเหลือ 10 นาทีได้เฉพาะรอบถึงเวลา จึงเลือกรอบก่อนสอนเฉพาะคำขอที่ส่งก่อนหรือเท่ากับ `start_at−30 นาที` (`created_at` เมื่อไม่มี `submitted_at`) เพื่อไม่ส่งรอบก่อนสอนย้อนหลังให้คำขอกระชั้น รอบถึงเวลาใช้ตามแผนทุกคำขอที่อนุมัติ
- การบังคับย้ายในระบบเดิมยังเก็บ `request_status=APPROVED` แต่เปลี่ยน `usage_status=DISPLACED` จึงเตือนเฉพาะ `usage_status=UPCOMING` เพื่อไม่ส่งลิงก์ห้องเดิมที่ไม่ได้ใช้ หรือคาบที่ปิดสถานะใช้งานแล้ว
- ฐานข้อมูลกันแจ้งซ้ำต่อ booking/user/kind แต่ไม่มีการส่งอีเมลซ้ำอัตโนมัติ หาก SMTP ล้ม กระดิ่งยังอยู่และ `email_failed` เพิ่ม 1 ผู้ดูแลดู log เพื่อแก้ SMTP
- การแก้เวลาใน booking เดิมหลังส่งรอบใดแล้วไม่ส่งรอบนั้นซ้ำ เพราะใช้ booking เดิมเป็นตัวกันซ้ำ แผนไม่ได้กำหนดให้แจ้งซ้ำเมื่อแก้เวลา
- `email_failed` เพิ่มใน `on_commit`; `run_jobs` ปกติเรียกนอก transaction ครอบใหญ่จึงสรุปผลได้ทันที ผู้เรียก service ภายใต้ outer `atomic()` ต้องรอ commit ก่อนอ่านจำนวนสุดท้าย
- ชื่อ secret และ Cloud SQL มาจากเว็บที่ใช้งานจริง ไม่สมมติค่าจากแผนเก่า เอกสารนี้ไม่ได้ยืนยันค่าปัจจุบันบน Cloud เพราะไม่มีการเรียก Cloud ในงานนี้

อ้างอิงที่ตรวจเมื่อ 3 ต.ค. 2569: [ตั้ง Cloud Run Job ด้วย Scheduler](https://docs.cloud.google.com/run/docs/execute/jobs-on-schedule), [รูปแบบ Job YAML](https://docs.cloud.google.com/run/docs/reference/yaml/v1), [สร้างหรือแทนที่ Job จากไฟล์](https://docs.cloud.google.com/sdk/gcloud/reference/run/jobs/replace), [การยืนยันตัวตนของ Scheduler](https://docs.cloud.google.com/scheduler/docs/http-target-auth)
