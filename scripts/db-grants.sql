SET client_encoding = 'UTF8';

-- สิทธิ์ runtime ของบัญชี sigroom_app (least privilege — NF-02)
-- รันด้วยบัญชี postgres บนฐาน ogn_room:
--   psql -U postgres -d ogn_room -f scripts\db-grants.sql
-- ต้องรันซ้ำทุกครั้งหลัง migrate (เผื่อมีตาราง/sequence ใหม่)

GRANT CONNECT ON DATABASE ogn_room TO sigroom_app;
GRANT USAGE ON SCHEMA public TO sigroom_app;

-- ตารางงานปกติ: อ่าน/เพิ่ม/แก้/ลบ ได้ตามที่แอปต้องใช้
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO sigroom_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO sigroom_app;

-- audit log ต้อง append-only: เพิ่มและอ่านได้เท่านั้น ห้ามแก้/ลบ แม้ระบบถูกเจาะ
REVOKE UPDATE, DELETE, TRUNCATE ON audit_auditlog FROM sigroom_app;

-- ห้ามให้สิทธิ์เหล่านี้แก่ sigroom_app ไม่ว่ากรณีใด:
--   CREATEDB / CREATEROLE / SUPERUSER / เป็นเจ้าของตาราง
-- การทดสอบกู้คืน (restore-test.ps1) ให้ใช้บัญชี postgres ชั่วคราวตาม deploy-guide หมวด 7
