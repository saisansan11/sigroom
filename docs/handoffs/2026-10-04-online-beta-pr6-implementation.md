# ส่งต่องาน PR-6 ให้ผู้ตรวจและรวมลง stack

ฐาน implementation: `task/online-beta-pr6` จาก PR-1 (`feat/online-quick-booking`); ผู้ทำงานหลักนำ diff ไปต่อ PR-5 และรัน acceptance/Browser QA/CI อีกครั้งก่อน release

## ผลงานและการตัดสินใจ

- django-allauth เฉพาะ Google (`>=65,<66`, ล็อก `65.19.7`) เพิ่มตาราง allauth เท่านั้น เส้นทาง signup/password/token/connect ของ allauth ไม่เปิด
- เริ่ม OAuth ด้วย POST + CSRF, PKCE และ state ที่ใช้ครั้งเดียว คง password backend/throttle เดิม ใช้ callback จาก `PUBLIC_BASE_URL` และตรวจลายเซ็น ID token ทุกครั้ง
- claim `email_verified` ต้องเป็น Boolean True, อีเมลโรงเรียน, `hd` ตรง และ UID ตรงกับบัญชีเดิม บัญชีปิดใช้/UID ผูกคนอื่น/UID เดิมเปลี่ยนปฏิเสธ
- secret ใช้ env เท่านั้น ไม่อ่าน SocialApp ในฐานข้อมูลเป็นแหล่ง credentials และไม่เปิด SocialApp ใน Admin ไม่เก็บ access/refresh token
- นักเรียนใหม่สร้างเฉพาะอีเมลในรายชื่อของรุ่นที่ยืนยันจาก state OAuth ไม่ใช้ QR หรือ school domain ให้สิทธิ์รุ่นอัตโนมัติ ไม่มี password/groups/staff/superuser
- ข้อมูลใหม่ `User.is_lodging_student` และ nullable `CourseStudentLodging.user` เป็น expand migrations เพิ่มรายชื่อ `CourseStudentEnrollment` สำหรับเจ้าหน้าที่
- ล็อกสิทธิ์นักเรียนทั้ง middleware และ services: จองเตียงของรุ่นที่มีสิทธิ์เท่านั้น เข้าครู/อนุมัติ/จัดการ/จองห้องทั่วไปไม่ได้ บัตรใหม่ดูและยกเลิกเฉพาะเจ้าของหรือผู้จัดหลักสูตร บัตรเก่า user=null ยังใช้ token เดิมได้
- ห้องพักข้าราชการทหารยังเปิดสาธารณะและตัวกัน spam เดิมคงอยู่ ฐานข้อมูลกันเตียงและ ExclusionConstraint เดิมคงอยู่
- ชื่อดึงจาก Google และตรวจซ้ำใน service ฝั่งเซิร์ฟเวอร์ ข้อมูลติดต่อเติมจากรายชื่อก่อนจอง

## test เดิมที่แก้ตามพฤติกรรม PR-6

ไม่มี test ถูกลบหรือ skip เพิ่ม fixture `enrolled_student` แบบเรียกอย่างชัดเจนใน `conftest.py`; fixture นี้สร้างสมาชิกที่เจ้าหน้าที่รับรอง ไม่เปิดสิทธิ์ทุกคนหรือ login แบบ autouse

| ไฟล์ | test ที่เปลี่ยน | เหตุผล |
|---|---|---|
| `bookings/tests_guest_and_lodging.py` | `test_course_lodging_student_booking_flow` | เพิ่มตรวจ anonymous → login และใช้ผู้จองคนละบัญชี/รายชื่อรุ่น ยังตรวจเตียงซ้ำ/จำนวนผู้พัก/PII เดิม |
| `bookings/tests_lodging_room_popup.py` | `test_selected_room_is_preserved_in_portal` | login สมาชิกก่อนตรวจห้องที่เลือกและข้อมูลไม่ถูกต้อง |
| `bookings/tests_lodging_v4.py` | `test_lodging_index_and_supervisor_isolation` | เพิ่ม anonymous redirect แล้วตรวจ single cohort ของสมาชิก คง staff isolation |
| `bookings/tests_phase_b_lodging_lifecycle.py` | `test_course_booking_window_blocks_before_open_even_on_direct_post` | login สมาชิกก่อนทดสอบการปฏิเสธก่อนเวลาเปิด ไม่ให้ login redirect บัง window assertion |
| `bookings/tests_task_first_a5_lodging.py` | single cohort / two cohorts / no open cohort | login สมาชิกที่มีรายชื่อรุ่นให้ตรงกับรายการที่ควรเห็น บัญชีไม่มีรุ่นยังเห็น empty state |
| `bookings/tests_ui4.py` | `test_public_portal_uses_privacy_safe_occupied_bed_text_and_share_link` | เข้าระบบสมาชิกก่อนตรวจว่าไม่มี PII ของเพื่อนร่วมรุ่น |
| `bookings/tests_ui5.py` | `test_student_portal_modal_a11y_and_reduced_motion` | login สมาชิกก่อนตรวจ focus/reduced motion |
| `bookings/tests_ux18.py` | `test_portal_public_privacy_and_accessible_bed_label` | login สมาชิกก่อนตรวจ PII และป้ายสำหรับ accessibility |
| `bookings/tests_v6_a.py` | available-room sort / jump+input / booking error modal | login สมาชิก คง sort/accessibility/คืนข้อมูลเมื่อชน และแยกผู้พยายามจองซ้ำให้ตรวจเตียงและเบอร์ซ้ำจริง |
| `resources/tests_v6_c.py` | gallery+placeholder / photo-prefetch N+1 | login สมาชิกก่อนตรวจ gallery และจำนวน query เมื่อเพิ่มห้อง |

ใหม่ `accounts/tests_google_login.py` ครอบคลุม disabled config, POST/CSRF, canonical callback แม้ Host/X-Forwarded-Host ปลอม, state ปลอม/ใช้ซ้ำ, signature/missing ID token, claim ผิด, inactive, UID คนอื่น, case-insensitive email, next, ledger, least privilege, QR/roster, ข้ามรุ่น, เจ้าของบัตร/ยกเลิก, direct service guard และ legacy token

## ข้อสงสัยและงานเตรียมข้อมูล

1. ฐานเดิมไม่มีรายชื่อสมาชิกของหลักสูตร จึงเพิ่มรายชื่อที่ผู้จัดหลักสูตรรับรองก่อนให้ Google สร้างบัญชี การกด QR ใดก็จองรุ่นนั้นได้จะละเมิดเงื่อนไข “รุ่นตัวเอง” ห้ามเปิดใช้จนเตรียมรายชื่อจริงแล้ว
2. ยศ/สังกัด/เบอร์โทรยังเป็นกฎข้อมูลเดิม ถ้ารายชื่อยังไม่ครบ ผู้ใช้เติมช่องที่ขาดในฟอร์มจองเตียง ระบบไม่สร้างเบอร์หรือยศปลอม ต้องเติมข้อมูลรายชื่อให้ครบเพื่อไม่ให้นักเรียนกรอกซ้ำ
3. `must_change_password` ของบัญชีเดิมคงเดิม แม้ใช้ Google; บัญชีนักเรียนใหม่ใช้รหัสผ่านไม่ได้ จึงไม่ตั้ง flag นี้
4. ไม่มี OAuth client จริงในเครื่อง จึงทดสอบ callback/claims/state ด้วย mock เท่านั้น การทดสอบ school login จริงบน Cloud ต้องใช้ client ของโรงเรียนและรายชื่อนักเรียนจริง ตาม `docs/google-login-setup.md`

## วิธีดูผลและขั้นตอนต่อ

อ่าน `docs/google-login-setup.md` สำหรับการเตรียมรายชื่อ OAuth client/env และการทดสอบด้วยตา ผู้ทำงานหลักต้องรวม PR-6 ต่อ PR-5, ตรวจ migration dependency ถ้ามี migration ใหม่ใน stack, รัน full pytest/Node/Django/diff, ทำภาพหน้า login มี/ไม่มีปุ่มทั้ง 390px และ desktop แล้วเปิด PR พร้อมผลจริง

ผลตรวจ implementation 4 ต.ค. 2569:

- full pytest: **894 ผ่าน**, 443 warnings, 170.18 วินาที
- Google suite: **28 ผ่าน**; ชุด portal/regression เดิมที่อัปเดตพร้อม Google: **127 ผ่าน**
- หลัง self review เพิ่มตรวจชื่อจาก Google ใน service: รันทดสอบ Google/booking flow/error modal ซ้ำ **39 ผ่าน**
- Node interaction: **10 ผ่าน**, ไม่มี skip
- Django check: ไม่มีปัญหา; makemigrations --check --dry-run: No changes detected; git diff --check: ผ่าน

Browser QA และ CI ยังเป็น gate ของผู้ทำงานหลักหลังรวม stack; ผลนี้ไม่ถือว่า release ผ่านแล้ว
